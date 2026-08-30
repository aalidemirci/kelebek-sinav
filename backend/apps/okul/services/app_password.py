"""Opsiyonel uygulama parolası — kurma, açma, değiştirme, kaldırma, kurtarma.

Tasarım §6 + §10.2. `shared.crypto` kriptografik ilkelleri (Argon2id türetme,
zarf sarmalama, şifreli alanlar) sağlar; bu modül BÜTÜN AKIŞI yönetir:

    guvenlik.json (veri dizini)          SQLite (db.sqlite3)
    ├── kdf parametreleri                ├── okul_student.first_name .. token
    ├── parola: {tuz, sarmal(DEK)}       ├── okul_student.last_name ... token
    ├── kurtarma: {tuz, sarmal(DEK)}     └── okul_schoolconfig
    └── gecis: TAMAM|SIFRELENIYOR|COZULUYOR    └── app_password_hash = parmak izi

**DEK (veri anahtarı) hiçbir yerde açık durmaz**; iki kez sarmalanır: bir kez
paroladan türetilen anahtarla, bir kez de yazdırılabilir kurtarma anahtarından
türetilenle. Parola unutulursa kurtarma anahtarı veriyi kurtarır (tasarım §6:
"parola unutma = veri kaybı olmasın").

NEDEN GÜVENLİK DOSYASI VERİ DİZİNİNDE, DB'DE DEĞİL?
  * Yedekler (`backups/gunluk-*.ksbak`) X25519 + AES-256-GCM kapsayıcılarıdır.
    Sarmallar orada olmadığı için USB'ye/Drive'a alınan bir yedek TEK BAŞINA
    açılamaz — parolalı kipin en somut kazancı budur.
  * Buna karşılık DB'de yalnız anahtarın PARMAK İZİ durur; yanlış eşleşme
    (başka kurulumun güvenlik dosyası) sessizce bozuk çözme yerine açık ret
    üretir.

YARIM KALAN GEÇİŞ (kritik tasarım sorusu 3): sıralama, her kesinti noktasında
verinin OKUNUR ve geçişin TAMAMLANABİLİR kalacağı şekilde kurulmuştur:

    1. Geçiş öncesi şifreli yedek (`pre-parola-*.ksbak`)
    2. guvenlik.json yazılır (gecis=SIFRELENIYOR) ......... anahtar artık kayıp değil
    3. TEK veritabanı işlemi: tüm satırlar + parmak izi ... ya hep ya hiç
    4. guvenlik.json güncellenir (gecis=TAMAM)

  Kesinti 2-3 arası: DB düz, dosya var → kilit açılır, `resume` tamamlar.
  Kesinti 3 içinde: işlem geri alınır (SQLite atomiktir) → 2 ile aynı durum.
  Kesinti 3-4 arası: DB şifreli + parmak izi yazılı; `resume` yalnız dosyadaki
  damgayı düzeltir (satır yeniden yazımı zaten fikirdeş/idempotenttir).
  Ayrıca alan okuması karışık duruma toleranslıdır (`shared.crypto` notu):
  yarısı şifreli tablo hatasız okunur.

YANLIŞ PAROLA DENEMESİ (kritik tasarım sorusu 4): kalıcı kilitlenme YOKTUR —
tek kullanıcılı çevrimdışı bir programda hesabı açacak bir yönetici yoktur,
kilitlenme kendi kendine hizmet reddi olurdu. Bunun yerine (a) Argon2id maliyeti
her denemeyi ~0,2 sn yapar, (b) art arda hatalarda süreç-içi kademeli gecikme
uygulanır. Gerçek koruma çevrimdışı saldırıya karşı Argon2id parametreleri +
tam disk şifrelemesidir (BitLocker/LUKS) — arayüz metni bunu açıkça söyler.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

from desktop.backup import database_snapshot, encrypt_legacy_backups
from desktop.backup_crypto import (
    BACKUP_SUFFIX,
    BackupCryptoError,
    config_path,
    encrypt_to_path,
    ensure_public_config,
    load_public_key,
    recovery_metadata,
)
from django.apps import apps as django_apps
from django.conf import settings
from django.db import connection, models, transaction
from django.utils import timezone

from apps.okul.models import SchoolConfig
from shared import crypto

logger = logging.getLogger("kelebek_sinav.guvenlik")

# --- Dosya/dizin çözümü -----------------------------------------------------
STATE_FILE_NAME = "guvenlik.json"
# Testler ve taşınabilir kip için: verilirse güvenlik dosyasının/yedeklerin yeri.
ENV_SECURITY_DIR = "KS_SECURITY_DIR"
ENV_BACKUP_DIR = "KS_BACKUP_DIR"

STATE_VERSION = 1

# Geçiş durumu damgaları (dosyada saklanır).
TRANSITION_DONE = "TAMAM"
TRANSITION_ENCRYPTING = "SIFRELENIYOR"
TRANSITION_DECRYPTING = "COZULUYOR"

MIN_PASSWORD_LENGTH = 8

# Kurtarma anahtarı: 20 rastgele bayt → base32 (32 karakter) → 8 dörtlü grup.
RECOVERY_KEY_BYTES = 20
RECOVERY_GROUP_SIZE = 4
# Base32 alfabesinde 0/1/8/9 yoktur; elle yazımda en sık karışan ikili düzeltilir.
_RECOVERY_FIXUPS = str.maketrans({"0": "O", "1": "I", "8": "B"})

# Art arda yanlış denemede uygulanan gecikme (saniye). Son değer tavandır.
FAILURE_DELAYS: tuple[float, ...] = (0.0, 0.0, 1.0, 2.0, 4.0)
_failed_attempts = 0


class AppPasswordError(ValueError):
    """Kullanıcıya gösterilecek Türkçe hata (view katmanı 400'e çevirir)."""


# ---------------------------------------------------------------------------
# Yol yardımcıları
# ---------------------------------------------------------------------------
def _data_dir() -> Path:
    return Path(os.environ.get(ENV_SECURITY_DIR) or settings.DATA_DIR)


def state_path() -> Path:
    """`guvenlik.json` yolu — veri dizininde, db.sqlite3'ün yanında."""
    return _data_dir() / STATE_FILE_NAME


def backup_dir() -> Path:
    """Yedek dizini. Paketlenmiş kipte `<veri kökü>/backups` (desktop/paths.py)."""
    override = os.environ.get(ENV_BACKUP_DIR)
    if override:
        return Path(override)
    # settings.DATA_DIR = <kök>/data → yedekler <kök>/backups (desktop/paths.py yerleşimi).
    return Path(settings.DATA_DIR).parent / "backups"


# ---------------------------------------------------------------------------
# Durum dosyası
# ---------------------------------------------------------------------------
def read_state() -> dict[str, Any] | None:
    """Güvenlik dosyasını okur; yoksa None. Bozuksa Türkçe hata yükseltir."""
    path = state_path()
    if not path.is_file():
        return None
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AppPasswordError(
            "Güvenlik dosyası (guvenlik.json) okunamadı ya da bozuk. Veri klasöründeki "
            "yedeğinizden geri alın; dosya olmadan şifreli alanlar açılamaz."
        ) from exc
    if not isinstance(data, dict):
        raise AppPasswordError("Güvenlik dosyası (guvenlik.json) beklenen biçimde değil.")
    return data


def _write_state(data: dict[str, Any]) -> None:
    """Dosyayı ATOMİK yazar (önce .tmp, sonra yerine koy) — yarım dosya kalmaz."""
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _archive_state() -> Path | None:
    """Parola kaldırılırken dosyayı SİLMEZ, arşivler.

    Gerekçe: eski yedekler (`gunluk-*.ksbak`) hâlâ ESKİ anahtarla şifrelidir.
    Dosya silinseydi o yedekler sonsuza dek açılamaz hâle gelirdi; arşiv kopyası
    (eski parolayla) geri dönüş yolunu açık tutar.
    """
    path = state_path()
    if not path.is_file():
        return None
    damga = timezone.localtime().strftime("%Y-%m-%d-%H%M%S")
    hedef = path.with_name(f"guvenlik-arsiv-{damga}.json")
    path.replace(hedef)
    logger.info("Güvenlik dosyası arşivlendi: %s", hedef.name)
    return hedef


# ---------------------------------------------------------------------------
# Geçiş öncesi yedek
# ---------------------------------------------------------------------------
def database_file() -> Path | None:
    """Canlı veritabanı dosyasının yolu; dosya tabanlı değilse (testler) None."""
    if connection.vendor != "sqlite":  # pragma: no cover — program yalnız SQLite kullanır
        return None
    ad = str(connection.settings_dict.get("NAME") or "")
    # Django'nun SQLite test veritabanı bellek içidir (`file:...mode=memory...`).
    if not ad or ad == ":memory:" or "mode=memory" in ad:
        return None
    return Path(ad)


def take_transition_backup(label: str) -> Path | None:
    """Geçiş ÖNCESİ tam veritabanı kopyası alır; yolunu döndürür (alınamazsa None).

    Masaüstü kabuğuyla aynı RAM-içi SQLite görüntüsü ve `.ksbak` şifreli kapsayıcı
    yordamları kullanılır. Adı rotasyon desenlerine ÇAKIŞMAZ (`pre-parola-*`);
    kabuğun 14 günlük rotasyonu bu dosyalara DOKUNMAZ — parola geçişi yılda bir
    olur, kopyası kasten kalıcıdır.

    KOPYA AYRI BİR BAĞLANTIDAN alınır (canlı Django bağlantısından DEĞİL): açık
    bir işlem varken `sqlite3.Connection.backup()` SQLITE_BUSY'de sonsuz döngüye
    girer — testte donma olarak yakalandı. Ayrı bağlantı WAL dosyasını da
    okuduğu için kopya tutarlıdır.

    Bellek-içi veritabanında (testler) yedek ATLANIR ve None döner; çağıranlar
    yedeği zorunlu koşul saymaz, ama gerçek kurulumda daima alınır.
    """
    kaynak = database_file()
    if kaynak is None or not kaynak.exists():
        logger.warning("Veritabanı dosya tabanlı değil; geçiş öncesi yedek atlandı.")
        return None
    hedef_dizin = backup_dir()
    hedef_dizin.mkdir(parents=True, exist_ok=True)
    damga = timezone.localtime().strftime("%Y-%m-%d-%H%M%S")
    hedef = hedef_dizin / f"pre-parola-{label}-{damga}{BACKUP_SUFFIX}"
    try:
        encrypt_to_path(
            database_snapshot(kaynak),
            hedef,
            load_public_key(_data_dir()),
            recovery_header=recovery_metadata(_data_dir()),
        )
    except (sqlite3.Error, OSError, BackupCryptoError):
        logger.exception("Geçiş öncesi yedek alınamadı.")
        raise AppPasswordError(
            "Güvenlik değişikliği öncesi yedek alınamadı; işlem yapılmadı. "
            "Veri klasöründe yer olduğundan emin olup yeniden deneyin."
        ) from None
    logger.info("Geçiş öncesi yedek alındı: %s", hedef.name)
    return hedef


# ---------------------------------------------------------------------------
# Şifreli alan kayıt defteri + toplu yeniden yazma
# ---------------------------------------------------------------------------
def encrypted_field_map() -> list[tuple[type[models.Model], tuple[str, ...]]]:
    """Şifreli alan taşıyan tüm modeller — elle liste YOK, koddan okunur.

    Yeni bir `EncryptedTextField` eklendiğinde geçiş aracı onu KENDİLİĞİNDEN
    kapsar; unutulan alan yüzünden yarı şifreli sicil oluşmaz.
    """
    sonuc: list[tuple[type[models.Model], tuple[str, ...]]] = []
    for model in django_apps.get_models():
        alanlar = tuple(f.name for f in crypto.encrypted_fields_of(model))
        if alanlar:
            sonuc.append((model, alanlar))
    return sonuc


def protected_field_labels() -> list[str]:
    """Arayüzde "hangi alanlar korunuyor" listesi (Türkçe, tekilleştirilmiş)."""
    etiketler: list[str] = []
    for model, _ in encrypted_field_map():
        for alan in crypto.encrypted_fields_of(model):
            etiket = str(getattr(alan, "verbose_name", alan.name))
            if etiket not in etiketler:
                etiketler.append(etiket)
    return etiketler


def _rewrite_rows() -> int:
    """Tüm şifreli alanları OKUYUP GERİ YAZAR; yazılan satır sayısını döndürür.

    Yön, o anki yazma kipiyle belirlenir: anahtar yüklü + normal kip → şifreler;
    `crypto.plaintext_writes()` içinde → çözer. İki yönde de FİKİRDEŞTİR
    (idempotent): okuma daima düz metin verdiğinden ikinci koşu aynı sonucu
    üretir, çift şifreleme OLUŞAMAZ.
    """
    toplam = 0
    for model, alanlar in encrypted_field_map():
        # Soft-delete edilmiş satırlar da kapsanır: silinmiş öğrencinin adı
        # de kişisel veridir (`all_objects`).
        manager = getattr(model, "all_objects", model._default_manager)
        for nesne in manager.all().iterator(chunk_size=200):
            nesne.save(update_fields=list(alanlar))
            toplam += 1
    return toplam


def _write_fingerprint(value: str) -> None:
    config, _ = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
    config.app_password_hash = value
    config.save(update_fields=["app_password_hash", "updated_at"])


def _stored_fingerprint() -> str:
    return SchoolConfig.load().app_password_hash


# ---------------------------------------------------------------------------
# Kurtarma anahtarı
# ---------------------------------------------------------------------------
def generate_recovery_key() -> str:
    """Yazdırılabilir kurtarma anahtarı üretir (ör. `A1B2-C3D4-...`, 8 grup)."""
    ham = base64.b32encode(os.urandom(RECOVERY_KEY_BYTES)).decode("ascii").rstrip("=")
    return "-".join(
        ham[i : i + RECOVERY_GROUP_SIZE] for i in range(0, len(ham), RECOVERY_GROUP_SIZE)
    )


def normalize_recovery_key(value: str) -> str:
    """Kullanıcının yazdığı anahtarı normalleştirir (tire/boşluk, küçük harf, 0/1/8)."""
    sade = "".join(ch for ch in value.strip().upper() if ch.isalnum())
    return sade.translate(_RECOVERY_FIXUPS)


# ---------------------------------------------------------------------------
# Deneme gecikmesi
# ---------------------------------------------------------------------------
def _delay_after_failure() -> None:
    """Kademeli gecikme — klavye başındaki deneyene karşı; kalıcı kilit YOK."""
    global _failed_attempts
    gecikme = FAILURE_DELAYS[min(_failed_attempts, len(FAILURE_DELAYS) - 1)]
    _failed_attempts += 1
    if gecikme:
        time.sleep(gecikme)


def _reset_failures() -> None:
    global _failed_attempts
    _failed_attempts = 0


# ---------------------------------------------------------------------------
# Durum sorgusu
# ---------------------------------------------------------------------------
def is_password_set() -> bool:
    """Güvenlik dosyası var mı? (JSON ayrıştırmaz — her istekte çağrılabilir)"""
    return state_path().is_file()


def is_locked() -> bool:
    """Parola ayarlı ve anahtar bellekte değil mi?"""
    return is_password_set() and not crypto.is_unlocked()


def status() -> dict[str, Any]:
    """Arayüzün okuduğu durum özeti (sır içermez)."""
    state = read_state()
    gecis = str(state.get("gecis", TRANSITION_DONE)) if state else TRANSITION_DONE
    return {
        "password_set": state is not None,
        "locked": state is not None and not crypto.is_unlocked(),
        "transition_pending": state is not None and gecis != TRANSITION_DONE,
        "transition": gecis if state is not None and gecis != TRANSITION_DONE else "",
        "protected_fields": protected_field_labels(),
    }


# ---------------------------------------------------------------------------
# Kurma / kaldırma / değiştirme
# ---------------------------------------------------------------------------
def _validate_password(password: str) -> str:
    parola = password.strip()
    if len(parola) < MIN_PASSWORD_LENGTH:
        raise AppPasswordError(f"Parola en az {MIN_PASSWORD_LENGTH} karakter olmalıdır.")
    return parola


def _build_state(data_key: bytes, *, password: str, recovery_key: str) -> dict[str, Any]:
    kdf = crypto.DEFAULT_KDF
    parola_tuz = crypto.new_salt()
    kurtarma_tuz = crypto.new_salt()
    return {
        "surum": STATE_VERSION,
        "olusturma": timezone.localtime().isoformat(timespec="seconds"),
        "kdf": kdf.to_dict(),
        "parola": {
            "salt": base64.b64encode(parola_tuz).decode("ascii"),
            "sarmal": crypto.wrap_key(
                data_key,
                wrapping_key=crypto.derive_key(password, salt=parola_tuz, params=kdf),
            ),
        },
        "kurtarma": {
            "salt": base64.b64encode(kurtarma_tuz).decode("ascii"),
            "sarmal": crypto.wrap_key(
                data_key,
                wrapping_key=crypto.derive_key(
                    normalize_recovery_key(recovery_key), salt=kurtarma_tuz, params=kdf
                ),
            ),
        },
        "gecis": TRANSITION_ENCRYPTING,
    }


def enable(*, password: str) -> str:
    """Parolayı kurar, hassas alanları şifreler; TEK SEFERLİK kurtarma anahtarını döndürür.

    Dönen kurtarma anahtarı hiçbir yerde AÇIK saklanmaz — çağıran onu kullanıcıya
    bir kez gösterir (yazdırma/indirme), sonrasında yalnız sarmalı kalır.
    """
    if read_state() is not None:
        raise AppPasswordError("Uygulama parolası zaten kurulu.")
    parola = _validate_password(password)

    veri_anahtari = crypto.new_data_key()
    kurtarma = generate_recovery_key()
    state = _build_state(veri_anahtari, password=parola, recovery_key=kurtarma)
    # Sıra kritik: dosya ÖNCE yazılır. Ters sırada, şifreleme ile dosya yazımı
    # arasındaki bir kesinti anahtarı yok ederdi (veri kaybı).
    _write_state(state)
    yedek_ayar_yolu = _data_dir() / "yedekleme.json"
    onceki_yedek_ayari = yedek_ayar_yolu.read_bytes() if yedek_ayar_yolu.is_file() else None
    try:
        ensure_public_config(_data_dir(), veri_anahtari, replace=True)
        encrypt_legacy_backups(backup_dir(), _data_dir())
        take_transition_backup("acilis")
    except Exception:  # noqa: BLE001 - başarısız kurulumun iki dosyası birlikte geri alınır
        state_path().unlink(missing_ok=True)
        if onceki_yedek_ayari is None:
            yedek_ayar_yolu.unlink(missing_ok=True)
        else:
            yedek_ayar_yolu.write_bytes(onceki_yedek_ayari)
        raise

    crypto.load_key(veri_anahtari)
    _run_encrypt_pass(veri_anahtari)
    state["gecis"] = TRANSITION_DONE
    _write_state(state)
    _reset_failures()
    logger.info("Uygulama parolası kuruldu; hassas alanlar şifrelendi.")
    return kurtarma


def _run_encrypt_pass(data_key: bytes) -> int:
    """Şifreleme geçişi — satırlar ve parmak izi TEK işlemde yazılır."""
    with transaction.atomic():
        yazilan = _rewrite_rows()
        _write_fingerprint(crypto.key_fingerprint(data_key))
    return yazilan


def _run_decrypt_pass() -> int:
    """Çözme geçişi — satırlar düz yazılır, parmak izi TEK işlemde temizlenir."""
    with transaction.atomic(), crypto.plaintext_writes():
        yazilan = _rewrite_rows()
        _write_fingerprint("")
    return yazilan


def unlock(*, password: str) -> None:
    """Parolayla kilidi açar; yarım kalmış geçiş varsa tamamlar."""
    state = read_state()
    if state is None:
        raise AppPasswordError("Uygulama parolası kurulu değil.")
    veri_anahtari = _unwrap_with_password(state, password)
    _adopt_key(state, veri_anahtari)


def unlock_with_recovery(*, recovery_key: str, new_password: str) -> None:
    """Kurtarma anahtarıyla açar ve YENİ parola belirler (parola sıfırlama).

    Kurtarma sarmalı DEĞİŞMEZ — aynı yazdırılmış anahtar geçerli kalır. Yeni bir
    anahtar üretmek, kullanıcının elindeki kâğıdı sessizce geçersizleştirirdi.
    """
    state = read_state()
    if state is None:
        raise AppPasswordError("Uygulama parolası kurulu değil.")
    parola = _validate_password(new_password)
    veri_anahtari = _unwrap_with_recovery(state, recovery_key)

    kdf = crypto.KdfParams.from_dict(dict(state.get("kdf", {})))
    tuz = crypto.new_salt()
    state["parola"] = {
        "salt": base64.b64encode(tuz).decode("ascii"),
        "sarmal": crypto.wrap_key(
            veri_anahtari, wrapping_key=crypto.derive_key(parola, salt=tuz, params=kdf)
        ),
    }
    _write_state(state)
    _adopt_key(state, veri_anahtari)
    logger.info("Kurtarma anahtarıyla giriş yapıldı; parola yenilendi.")


def change_password(*, current_password: str, new_password: str) -> None:
    """Parolayı değiştirir. Veri YENİDEN ŞİFRELENMEZ — yalnız sarmal yenilenir."""
    state = read_state()
    if state is None:
        raise AppPasswordError("Uygulama parolası kurulu değil.")
    yeni = _validate_password(new_password)
    veri_anahtari = _unwrap_with_password(state, current_password)

    kdf = crypto.KdfParams.from_dict(dict(state.get("kdf", {})))
    tuz = crypto.new_salt()
    state["parola"] = {
        "salt": base64.b64encode(tuz).decode("ascii"),
        "sarmal": crypto.wrap_key(
            veri_anahtari, wrapping_key=crypto.derive_key(yeni, salt=tuz, params=kdf)
        ),
    }
    _write_state(state)
    _adopt_key(state, veri_anahtari)
    logger.info("Uygulama parolası değiştirildi.")


def disable(*, password: str) -> None:
    """Parolayı kaldırır: alanlar düz metne döner, güvenlik dosyası arşivlenir."""
    state = read_state()
    if state is None:
        raise AppPasswordError("Uygulama parolası kurulu değil.")
    veri_anahtari = _unwrap_with_password(state, password)
    crypto.load_key(veri_anahtari)

    take_transition_backup("kaldirma")
    state["gecis"] = TRANSITION_DECRYPTING
    _write_state(state)

    _run_decrypt_pass()
    _archive_state()
    _drop_backup_public_key()
    crypto.unload_key()
    logger.info("Uygulama parolası kaldırıldı; alanlar düz metne döndürüldü.")


def resume_pending(*, force: bool = False) -> dict[str, Any]:
    """Yarım kalmış geçişi tamamlar. Anahtarın yüklü olması gerekir.

    `force=True`: damga "tamam" dese bile şifreleme geçişi YENİDEN koşulur.
    Geçiş fikirdeş olduğu için bu güvenlidir ve destek senaryosunun elidir —
    örneğin satırların bir bölümü elle/yedekten düz metin dönmüşse
    (`manage.py app_password resume --force`).
    """
    state = read_state()
    if state is None:
        return {"resumed": False, "rows": 0, "transition": ""}
    if not crypto.is_unlocked():
        raise AppPasswordError("Geçişi tamamlamak için önce parolayla açın.")

    gecis = str(state.get("gecis", TRANSITION_DONE))
    if gecis == TRANSITION_DECRYPTING:
        satir = _run_decrypt_pass()
        _archive_state()
        _drop_backup_public_key()
        crypto.unload_key()
        logger.info("Yarım kalan parola kaldırma işlemi tamamlandı.")
        return {"resumed": True, "rows": satir, "transition": TRANSITION_DECRYPTING}

    parmak = crypto.active_fingerprint() or ""
    if force or gecis == TRANSITION_ENCRYPTING or _stored_fingerprint() != parmak:
        satir = _run_encrypt_pass(_require_raw_key())
        state["gecis"] = TRANSITION_DONE
        _write_state(state)
        logger.info("Şifreleme geçişi tamamlandı (%d kayıt).", satir)
        return {"resumed": True, "rows": satir, "transition": TRANSITION_ENCRYPTING}
    return {"resumed": False, "rows": 0, "transition": ""}


def lock() -> None:
    """Anahtarı bellekten düşürür. Parola kurulu değilse bir şey yapmaz."""
    crypto.unload_key()


# ---------------------------------------------------------------------------
# İç yardımcılar
# ---------------------------------------------------------------------------
def _require_raw_key() -> bytes:
    ham = crypto.active_key()
    if ham is None:  # pragma: no cover — çağrı yerleri kilidin açık olduğunu doğrular
        raise AppPasswordError("Veri anahtarı bellekte değil; parolayla yeniden açın.")
    return ham


def _drop_backup_public_key() -> None:
    """Parolasız kipe dönüşte yedek açık anahtarını kaldırır (K9 iki kip).

    Dosya kalsaydı günlük yedekler, sarmalı artık yalnız `guvenlik-arsiv-*` +
    ESKİ parolayla çözülebilen bir anahtarla şifrelenmeye devam ederdi. Eski
    şifreli `.ksbak` yedekleri etkilenmez: çözümleri açık anahtarı değil,
    arşivlenen durum dosyasındaki sarmalı ister.
    """
    config_path(_data_dir()).unlink(missing_ok=True)


def _adopt_key(state: dict[str, Any], data_key: bytes) -> None:
    """Anahtarı yükler, DB eşleşmesini doğrular, gerekiyorsa geçişi tamamlar."""
    parmak = crypto.key_fingerprint(data_key)
    kayitli = _stored_fingerprint()
    gecis = str(state.get("gecis", TRANSITION_DONE))
    if kayitli and kayitli != parmak:
        raise AppPasswordError(
            "Bu güvenlik dosyası bu veritabanına ait değil (anahtar eşleşmiyor). "
            "Doğru guvenlik.json dosyasını veri klasörüne koyup yeniden deneyin; "
            "yanlış dosyayla açmak kayıtları okunamaz hâle getirir."
        )
    crypto.load_key(data_key)
    ensure_public_config(_data_dir(), data_key)
    encrypt_legacy_backups(backup_dir(), _data_dir())
    _reset_failures()
    if gecis != TRANSITION_DONE or not kayitli:
        resume_pending()


def _unwrap_with_password(state: dict[str, Any], password: str) -> bytes:
    bolum = dict(state.get("parola", {}))
    return _unwrap(bolum, state, password, "Parola hatalı.")


def _unwrap_with_recovery(state: dict[str, Any], recovery_key: str) -> bytes:
    bolum = dict(state.get("kurtarma", {}))
    return _unwrap(
        bolum,
        state,
        normalize_recovery_key(recovery_key),
        "Kurtarma anahtarı hatalı. Yazdırdığınız kâğıttaki anahtarı olduğu gibi girin.",
    )


def _unwrap(bolum: dict[str, Any], state: dict[str, Any], secret: str, hata_mesaji: str) -> bytes:
    tuz_b64 = str(bolum.get("salt", ""))
    sarmal = str(bolum.get("sarmal", ""))
    if not tuz_b64 or not sarmal:
        raise AppPasswordError(
            "Güvenlik dosyası eksik (tuz veya sarmal yok); yedeğinizden geri alın."
        )
    kdf = crypto.KdfParams.from_dict(dict(state.get("kdf", {})))
    sarmalama = crypto.derive_key(secret, salt=base64.b64decode(tuz_b64), params=kdf)
    try:
        return crypto.unwrap_key(sarmal, wrapping_key=sarmalama)
    except Exception as exc:  # noqa: BLE001 — InvalidToken ve biçim hataları aynı yanıta çıkar
        _delay_after_failure()
        raise AppPasswordError(hata_mesaji) from exc
