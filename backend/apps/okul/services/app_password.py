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

"PAROLA KURULU MU?" — FAIL-CLOSED DURUM SORGUSU: cevap güvenlik dosyasının
VARLIĞI **ya da** DB'deki anahtar parmak izidir (`is_password_set`). Parola
isteğe bağlıdır ve parolasız kip meşrudur; ama parolasız kip YALNIZ ikisinin de
yokluğudur. Parmak izi dolu + dosya yok ya da dosya var ama kullanılamıyor
(boş, bozuk, sarmal bölümleri eksik — tek kural
`desktop.backup_crypto.is_usable_security_state`) = **güvenlik dosyası kayıp**
(`security_file_missing`). Bu durumda program "parolasız"a dönmez: kilit kapısı
yalnız durum, sıfırlama ve yedekten geri yükleme yollarını açık bırakır
(`lock_middleware`), `enable()` reddeder, şifreli alanlar anahtarsız yazmaz
(`shared.crypto.KeyMissingError`). Çıkış yolları: dosyanın sağlam kopyasını
geri koymak ya da yedekten geri yüklemek (geri yükleme dosyayı yedeğin
kurtarma başlığından yeniden yazar — `backup_restore._ensure_state_file`).
Tek istisna: dosya kullanılamıyor AMA parmak izi BOŞ ise veritabanında o
dosyanın anahtarıyla şifrelenmiş satır yoktur (satırlar ve parmak izi tek
işlemde yazılır); "güvenlik dosyasını sıfırla" yolu dosyayı arşivleyip
parolasız kipe döner (`state_reset_available`, `reset_unusable_state`).

KURTARMA ANAHTARINI YENİLEME (görev devri): `renew_recovery_key(password=…)`
yalnız kilit açıkken çalışır, parolayı bellekteki anahtara karşı doğrular ve
AYNI DEK'i YENİ anahtar + YENİ tuzla sarmalar. Önceki `guvenlik.json` önce
`guvenlik-arsiv-<damga>.json` olarak KOPYALANIR (asıl dosya hiçbir an yok
olmaz), sonra yeni durum atomik yazılır; yeni anahtar yanıtla BİR KEZ döner ve
hiçbir günlüğe yazılmaz. DEK değişmediği için kayıtlar yeniden şifrelenmez ve
bunun dürüst sonucu arayüzde/kılavuzda söylenir: yenilemeden ÖNCE alınmış
yedekler (başlıklarında o günün dosyası vardır) ve arşiv dosyası eski anahtarla
açılmaya devam eder. Yenileme eski kâğıdı BU BİLGİSAYARDAKİ güncel dosya için
geçersiz kılar; ele geçmiş bir anahtara karşı tam koruma değildir.

ESKİ DÜZ METİN KALINTISI: şifreleme geçişi satırları yerinde yeniden yazar;
SQLite eski sürümü boş sayfalarda ve WAL'da bırakabilir. Bağlantılar
`secure_delete=ON` ile açılır (config/settings.py) ve geçişin sonunda WAL ana
dosyaya işlenip sıfırlanır, dosya VACUUM ile yeniden kurulur
(`scrub_free_pages`). Yedek dosyalarına dokunulmaz.

Güvenlik dosyasını değiştiren işlemler süreç içi bir kilitle (`_state_lock`)
sıralanır: oku-değiştir-yaz arasına başka bir yazım girip onu ezmesin.

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
import threading
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
    parse_security_state,
    recovery_metadata,
)
from django.apps import apps as django_apps
from django.conf import settings
from django.db import DatabaseError, connection, models, transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

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

#: Kenara alınan güvenlik dosyalarının ad öneki (`guvenlik-arsiv-<damga>.json`);
#: geri yükleme (`backup_restore._ensure_state_file`) ve `recovery_metadata`
#: aynı deseni kullanır.
STATE_ARCHIVE_PREFIX = "guvenlik-arsiv-"

# Güvenlik dosyasını oku-değiştir-yaz işlemlerinin süreç içi sırası (modül başlığı).
# Yeniden girilebilir: kurtarmayla açılış `_adopt_key` → `resume_pending` zincirini
# kilit içindeyken çağırır.
_state_lock = threading.RLock()

# Kilit kapısının üç hâli (`gate_state`; ara katman tek sorguyla karar verir).
GATE_OPEN = "acik"
GATE_LOCKED = "kilitli"
GATE_MISSING = "kayip"

# Kullanıcıya görünen iletiler. Ara katman ve arayüz aynı metni kullanır.
SECURITY_FILE_MISSING_MESSAGE = (
    "Güvenlik dosyası (guvenlik.json) bulunamadı ya da okunamıyor. Kayıtlar açılamaz. "
    "Dosyanın sağlam bir kopyasını veri klasörüne geri koyun ya da bir yedekten geri yükleyin."
)
_NOT_SET_MESSAGE = "Uygulama parolası kurulu değil."
_WRONG_PASSWORD_MESSAGE = "Parola hatalı."  # noqa: S105 — kullanıcı iletisi, parola değil
_LOCKED_MESSAGE = "Kayıtlar kilitli. Önce uygulama parolasıyla kilidi açın."
RESET_NOT_ALLOWED_MESSAGE = (
    "Güvenlik dosyası sıfırlanamaz: bu yol yalnız güvenlik dosyası okunamıyorken ve "
    "kayıtların anahtarı henüz veritabanına işlenmemişken açıktır. Dosyanın sağlam bir "
    "kopyasını veri klasörüne geri koyun ya da bir yedekten geri yükleyin."
)


class AppPasswordError(ValueError):
    """Kullanıcıya gösterilecek Türkçe hata (view katmanı 400'e çevirir)."""


class StateResetNotAllowed(AppPasswordError):
    """Sıfırlama koşulları sağlanmıyor (görünüm 409 `sifirlama_uygun_degil` döner)."""


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


def _require_state() -> dict[str, Any]:
    """Güvenlik dosyasını okur; yoksa KAYIP mı hiç kurulmamış mı olduğunu söyler."""
    state = read_state()
    if state is None:
        if _stored_fingerprint():
            raise AppPasswordError(SECURITY_FILE_MISSING_MESSAGE)
        raise AppPasswordError(_NOT_SET_MESSAGE)
    return state


def _write_state(data: dict[str, Any]) -> None:
    """Dosyayı ATOMİK yazar (önce .tmp, sonra yerine koy) — yarım dosya kalmaz."""
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def archive_target() -> Path:
    """Boş bir `guvenlik-arsiv-<damga>.json` yolu (aynı saniyede ikinci arşiv ezilmez).

    Arşiv dosyaları eski yedekleri açan TEK sarmal olabilir; aynı saniyede
    yapılan iki işlem (ör. yenileme + geri yükleme) birbirinin arşivini ezmemeli.
    """
    yol = state_path()
    damga = timezone.localtime().strftime("%Y-%m-%d-%H%M%S")
    arsiv = yol.with_name(f"{STATE_ARCHIVE_PREFIX}{damga}.json")
    sira = 2
    while arsiv.exists():
        arsiv = yol.with_name(f"{STATE_ARCHIVE_PREFIX}{damga}-{sira}.json")
        sira += 1
    return arsiv


def _copy_state_to_archive() -> Path:
    """Güncel güvenlik dosyasının baytlarını arşive KOPYALAR (asıl dosya yerinde kalır).

    Arşiv de atomik yazılır (.tmp → yerine koy): yarım arşiv dosyası kalmaz.
    """
    arsiv = archive_target()
    temp = arsiv.with_name(arsiv.name + ".tmp")
    temp.write_bytes(state_path().read_bytes())
    temp.replace(arsiv)
    return arsiv


def _archive_state() -> Path | None:
    """Parola kaldırılırken dosyayı SİLMEZ, arşivler.

    Gerekçe: eski yedekler (`gunluk-*.ksbak`) hâlâ ESKİ anahtarla şifrelidir.
    Dosya silinseydi o yedekler sonsuza dek açılamaz hâle gelirdi; arşiv kopyası
    (eski parolayla) geri dönüş yolunu açık tutar.
    """
    path = state_path()
    if not path.is_file():
        return None
    hedef = archive_target()
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


# Parmak izi sorgusu HAM SQL'dir: parolasız kipte şifreli alanın her yazımında
# (`shared.crypto` yoklayıcısı) ve her API isteğinde (kilit kapısı) sorulur.
# Ölçüm (24.09.2026, parolasız kipte 1000 öğrenci kaydı, DEBUG kapalı):
# yoklayıcısız 0,30 sn; ORM sorgusuyla ~1,4 sn; ham imleçle 0,46 sn. Tablo/sütun
# adı modelden okunur.
_FINGERPRINT_SQL = "SELECT {sutun} FROM {tablo} WHERE {pk} = %s".format(  # noqa: S608
    sutun=SchoolConfig._meta.get_field("app_password_hash").column,
    tablo=SchoolConfig._meta.db_table,
    pk=SchoolConfig._meta.pk.column if SchoolConfig._meta.pk else "id",
)


def _stored_fingerprint() -> str:
    """DB'deki anahtar parmak izi (yalnız o sütun, ham SQL — sık sorulur)."""
    with connection.cursor() as cursor:
        cursor.execute(_FINGERPRINT_SQL, [SchoolConfig.SINGLETON_PK])
        satir = cursor.fetchone()
    return str(satir[0] or "") if satir is not None else ""


# ---------------------------------------------------------------------------
# Eski düz metin kalıntısının temizliği
# ---------------------------------------------------------------------------
def scrub_free_pages(cursor: Any) -> bool:
    """WAL'ı ana dosyaya işleyip sıfırlar, dosyayı VACUUM ile yeniden kurar.

    Şifreleme geçişi satırları yerinde yeniden yazar; eski (düz) sürüm WAL
    çerçevelerinde ve boş sayfalarda kalabilir. Sıra: (1) WAL'daki her çerçeve
    ana dosyaya işlenir ve WAL sıfır boya indirilir, (2) VACUUM yalnız canlı
    içeriği yeni bir dosyaya kopyalar — boş sayfalar ve serbest liste taşınmaz,
    (3) VACUUM'un kendi WAL çerçeveleri de işlenip sıfırlanır. `cursor` DB-API
    imleci olmalıdır; açık işlem İÇİNDE çağrılamaz (VACUUM reddeder).

    Denetim noktası başka bir bağlantının okuması yüzünden tamamlanamazsa False
    döner (çağıran uyarı yazar; geçiş yine geçerlidir).
    """
    tam = True
    for adim in ("PRAGMA wal_checkpoint(TRUNCATE)", "VACUUM", "PRAGMA wal_checkpoint(TRUNCATE)"):
        cursor.execute(adim)
        if adim.startswith("PRAGMA"):
            sonuc = cursor.fetchone()
            # (meşgul, WAL çerçevesi, işlenen) — meşgul=1 ise denetim yarım kaldı.
            if sonuc is not None and int(sonuc[0]) != 0:
                tam = False
    return tam


def _scrub_plaintext_remnants() -> None:
    """Şifreleme geçişinden sonra eski düz metin sayfalarını temizler (modül başlığı).

    İşlem kapandıktan SONRA koşar (`on_commit`; atomik blok dışındaysa hemen):
    VACUUM açık işlem içinde çalışmaz. Bellek içi veritabanında (testler)
    temizlenecek dosya yoktur. Hata geçişi geri almaz — satırlar zaten şifrelidir,
    yalnız eski sayfaların temizliği bir sonraki geçişe kalır.
    """
    if database_file() is None:
        return

    def _kos() -> None:
        try:
            with connection.cursor() as cursor:
                tam = scrub_free_pages(cursor)
        except DatabaseError:
            logger.warning("Eski düz metin kalıntıları temizlenemedi (veritabanı meşgul).")
            return
        if not tam:
            logger.warning("Eski düz metin kalıntılarının temizliği yarım kaldı (okuyucu vardı).")

    transaction.on_commit(_kos)


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
    """Uygulama parolası kurulu mu? Fail-closed: dosya VAR **ya da** DB parmak izi dolu.

    Dosya varsa DB'ye gidilmez (JSON da ayrıştırılmaz). Dosya yoksa parmak izi
    sorulur: dolu olması parolanın kurulduğunu, dosyanın ise KAYBOLDUĞUNU
    gösterir — program "parolasız"a dönmez. Parolasız kip = ikisi de yok.
    `shared.crypto` bu işlevi şifreli alanların anahtarsız yazım kapısı olarak
    kullanır (`apps.okul.apps.OkulConfig.ready`).
    """
    if state_path().is_file():
        return True
    return bool(_stored_fingerprint())


def _state_file_usable(path: Path) -> bool:
    """Var olan güvenlik dosyası DEK'i açmaya yeter biçimde mi? (tek kural: backup_crypto)"""
    try:
        ham = path.read_bytes()
    except OSError:
        return False
    return parse_security_state(ham) is not None


def gate_state() -> str:
    """Kilit kapısının hâli: `GATE_MISSING` | `GATE_LOCKED` | `GATE_OPEN`.

    Ara katman her API isteğinde bunu sorar; dosya bir kez okunur, DB'ye en çok
    bir kez gidilir (parmak izi yalnız dosya yokken sorulur).

    * dosya var, kullanılamıyor → kayıp (parmak izinden bağımsız: dosyanın neyi
      koruduğu bilinemez; olağan kilit ekranı hiçbir parolayla açılmazdı);
    * dosya var, kullanılabilir → anahtar bellekteyse açık, değilse kilitli;
    * dosya yok, parmak izi dolu → kayıp (anahtar bellekte olsa bile: bir sonraki
      kilitte açılamayacak bir durumda çalışmaya devam edilmez);
    * dosya yok, parmak izi boş → parolasız kip, açık.
    """
    yol = state_path()
    if yol.is_file():
        if not _state_file_usable(yol):
            return GATE_MISSING
        return GATE_OPEN if crypto.is_unlocked() else GATE_LOCKED
    if _stored_fingerprint():
        return GATE_MISSING
    return GATE_OPEN


def security_file_missing() -> bool:
    """Güvenlik dosyası kayıp mı? (yok + parmak izi dolu, ya da var ama kullanılamıyor)"""
    return gate_state() == GATE_MISSING


def is_locked() -> bool:
    """Parola kurulu ve anahtar bellekte değil mi? (anahtar bellekteyse DB'ye gidilmez)"""
    return not crypto.is_unlocked() and is_password_set()


def state_reset_available() -> bool:
    """ "Güvenlik dosyasını sıfırla" yolu açık mı?

    İKİ koşul birden (biri eksikse yol görünmez, uç 409 döner):

    1. güvenlik dosyası VAR ama kullanılamıyor (boş, bozuk, bölümleri eksik —
       `gate_state` ile aynı kural). Dosya hiç yoksa ve parmak izi boşsa zaten
       parolasız kiptir, sıfırlanacak bir şey yoktur; parmak izi doluysa dosya
       kayıptır ve çıkış yolu sağlam kopya ya da yedektir;
    2. DB'de anahtar parmak izi BOŞ. Şifreleme geçişi satırları ve parmak izini
       TEK işlemde yazar, parola kaldırma da ikisini tek işlemde temizler; parmak
       izi boşsa veritabanında bu dosyanın anahtarıyla şifrelenmiş satır yoktur.

    Yedekler bu kararı etkilemez: her şifreli yedek kendi güvenlik dosyasını
    başlığında taşır, arşivlenen dosya da silinmez.
    """
    yol = state_path()
    if not yol.is_file() or _state_file_usable(yol):
        return False
    return not _stored_fingerprint()


def reset_unusable_state() -> str:
    """Kullanılamayan güvenlik dosyasını arşivler, programı parolasız kipe döndürür.

    Yalnız `state_reset_available()` doğruyken çalışır; aksi hâlde
    `StateResetNotAllowed`. Dosya SİLİNMEZ, `guvenlik-arsiv-<damga>.json` adıyla
    kenara alınır; yedek açık anahtarı (`yedekleme.json`) da
    `yedekleme-arsiv-<damga>.json` olur — kalsaydı günlük yedekler güvenlik
    dosyası olmadan alınamaz, atlanırdı. Arşiv dosyasının adını döndürür.
    """
    with _state_lock:
        if not state_reset_available():
            raise StateResetNotAllowed(RESET_NOT_ALLOWED_MESSAGE)
        arsiv = archive_target()
        state_path().replace(arsiv)
        yedek_ayari = config_path(_data_dir())
        if yedek_ayari.is_file():
            damga = arsiv.stem.removeprefix(STATE_ARCHIVE_PREFIX)
            yedek_ayari.replace(yedek_ayari.with_name(f"yedekleme-arsiv-{damga}.json"))
        crypto.unload_key()
        _reset_failures()
    logger.warning("Kullanılamayan güvenlik dosyası arşivlendi (%s).", arsiv.name)
    return arsiv.name


def status() -> dict[str, Any]:
    """Arayüzün okuduğu durum özeti (sır içermez). HİÇ hata yükseltmez.

    Kullanılamayan ya da kayıp güvenlik dosyası `security_file_missing` olarak
    raporlanır (arayüz kayıp ekranını gösterir); durum ucu hata dönseydi arayüz
    ne kilit ne kayıp ekranını gösterebilirdi.
    """
    kayip = security_file_missing()
    state: dict[str, Any] | None = None
    if not kayip:
        try:
            state = read_state()
        except AppPasswordError:  # iki okuma arasında bozulduysa (yarış) — yine kayıp
            kayip = True
    kurulu = state is not None or kayip
    gecis = str(state.get("gecis", TRANSITION_DONE)) if state else TRANSITION_DONE
    return {
        "password_set": kurulu,
        "locked": kurulu and not crypto.is_unlocked(),
        "security_file_missing": kayip,
        # Kayıp ekranındaki "sıfırla" yolu (yalnız veritabanında korunan satır yokken).
        "reset_available": kayip and state_reset_available(),
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

    DB'de anahtar parmak izi doluysa REDDEDER: parola daha önce kurulmuş ve
    güvenlik dosyası kaybolmuştur; yeni anahtar üretmek eski kayıtları okunamaz
    bırakır ve kilidi güvenlik dosyasının varlığına bağlı kılardı (modül başlığı).
    """
    if read_state() is not None:
        raise AppPasswordError("Uygulama parolası zaten kurulu.")
    if _stored_fingerprint():
        raise AppPasswordError(
            "Uygulama parolası daha önce kurulmuş, ancak güvenlik dosyası (guvenlik.json) "
            "bulunamadı. Yeni parola kurulamaz; dosyanın sağlam bir kopyasını veri klasörüne "
            "geri koyun ya da bir yedekten geri yükleyin."
        )
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
    """Şifreleme geçişi — satırlar ve parmak izi TEK işlemde yazılır.

    İşlem kapanınca eski düz sürümlerin kaldığı sayfalar temizlenir
    (`_scrub_plaintext_remnants`).
    """
    with transaction.atomic():
        yazilan = _rewrite_rows()
        _write_fingerprint(crypto.key_fingerprint(data_key))
    _scrub_plaintext_remnants()
    return yazilan


def _run_decrypt_pass() -> int:
    """Çözme geçişi — satırlar düz yazılır, parmak izi TEK işlemde temizlenir."""
    with transaction.atomic(), crypto.plaintext_writes():
        yazilan = _rewrite_rows()
        _write_fingerprint("")
    return yazilan


def unlock(*, password: str) -> None:
    """Parolayla kilidi açar; yarım kalmış geçiş varsa tamamlar."""
    state = _require_state()
    veri_anahtari = _unwrap_with_password(state, password)
    _adopt_key(state, veri_anahtari)


@sensitive_variables("password", "veri_anahtari")
def _check_password(state: dict[str, Any], password: str) -> bytes:
    """Parolayı verilen duruma VE bellekteki anahtara karşı doğrular; DEK'i döndürür.

    Sarmal çözülür ve çıkan DEK'in parmak izi yüklü anahtarınkiyle
    karşılaştırılır: başka bir kurulumdan getirilmiş (parolası bilinen) bir
    `guvenlik.json` ile işlem yapılamaz. Kilitliyken doğrulama yapılmaz.
    """
    aktif = crypto.active_fingerprint()
    if aktif is None:
        raise AppPasswordError(_LOCKED_MESSAGE)
    veri_anahtari = _unwrap_with_password(state, password)
    if crypto.key_fingerprint(veri_anahtari) != aktif:
        _delay_after_failure()
        raise AppPasswordError(_WRONG_PASSWORD_MESSAGE)
    _reset_failures()
    return veri_anahtari


@sensitive_variables("password", "veri_anahtari", "yeni_anahtar")
def renew_recovery_key(*, password: str) -> str:
    """Kurtarma anahtarını yeniler; YENİ anahtarı döndürür (yanıtta BİR KEZ gösterilir).

    Görev devri içindir: önceki görevlinin elindeki kâğıt bu bilgisayardaki
    güncel güvenlik dosyasını artık açmaz. Yalnız kilit açıkken; parola
    `_check_password` kuralıyla doğrulanır (yanlışsa "Parola hatalı." + kademeli
    gecikme ve hiçbir dosya değişmez). Sonra:

    1. güncel `guvenlik.json` `guvenlik-arsiv-<damga>.json` olarak KOPYALANIR
       (asıl dosya yerinde kalır: kesinti dosyayı kayıp hâline düşürmez);
    2. aynı DEK YENİ anahtar ve YENİ tuzla sarmalanır; parola bölümü, KDF
       parametreleri ve geçiş damgası olduğu gibi kalır;
    3. yeni durum atomik yazılır.

    DEK değişmez: kayıtlar yeniden şifrelenmez, yedek anahtarı (`yedekleme.json`)
    aynen kalır. Yenilemeden ÖNCE alınmış yedekler ve arşiv dosyası eski anahtarla
    açılmaya devam eder (modül başlığı). Anahtar hiçbir günlüğe, iletiye ya da
    istisnaya yazılmaz.
    """
    with _state_lock:
        state = _require_state()
        veri_anahtari = _check_password(state, password)
        yeni_anahtar = generate_recovery_key()
        kdf = crypto.KdfParams.from_dict(dict(state.get("kdf", {})))
        tuz = crypto.new_salt()
        yeni_durum = dict(state)
        yeni_durum["kurtarma"] = {
            "salt": base64.b64encode(tuz).decode("ascii"),
            "sarmal": crypto.wrap_key(
                veri_anahtari,
                wrapping_key=crypto.derive_key(
                    normalize_recovery_key(yeni_anahtar), salt=tuz, params=kdf
                ),
            ),
        }
        arsiv = _copy_state_to_archive()
        _write_state(yeni_durum)
    logger.info(
        "Kurtarma anahtarı yenilendi; önceki güvenlik dosyası %s olarak saklandı.", arsiv.name
    )
    return yeni_anahtar


def unlock_with_recovery(*, recovery_key: str, new_password: str) -> None:
    """Kurtarma anahtarıyla açar ve YENİ parola belirler (parola sıfırlama).

    Kurtarma sarmalı DEĞİŞMEZ — aynı yazdırılmış anahtar geçerli kalır. Yeni bir
    anahtar üretmek, kullanıcının elindeki kâğıdı sessizce geçersizleştirirdi.
    Anahtar yalnız kullanıcı isteyince yenilenir (`renew_recovery_key`).
    """
    with _state_lock:
        state = _require_state()
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
    """Parolayı değiştirir. Veri YENİDEN ŞİFRELENMEZ — yalnız sarmal yenilenir.

    Kurtarma sarmalına dokunmaz: görev devrinde kurtarma anahtarı ayrıca
    yenilenir (`renew_recovery_key`).
    """
    with _state_lock:
        state = _require_state()
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
    with _state_lock:
        state = _require_state()
        veri_anahtari = _unwrap_with_password(state, password)
        crypto.load_key(veri_anahtari)

        take_transition_backup("kaldirma")
        state["gecis"] = TRANSITION_DECRYPTING
        _write_state(state)

        _run_decrypt_pass()
        _finish_disable()
    logger.info("Uygulama parolası kaldırıldı; alanlar düz metne döndürüldü.")


def _finish_disable() -> None:
    """Çözme geçişinin kapanışı: önce yedek açık anahtarı kalkar, SONRA dosya arşivlenir.

    Sıra kesinti güvenliği içindir: ters sırada ikisi arasında kesilen bir işlem
    "güvenlik dosyası yok + yedek anahtarı var" bırakırdı — günlük yedek o hâlde
    kurtarma başlığı bulamaz ve alınamaz. Bu sırayla kesinti dosyayı
    (gecis=COZULUYOR) yerinde bırakır; kilit açılışı geçişi tamamlar.
    """
    _drop_backup_public_key()
    _archive_state()
    crypto.unload_key()


def resume_pending(*, force: bool = False) -> dict[str, Any]:
    """Yarım kalmış geçişi tamamlar. Anahtarın yüklü olması gerekir.

    `force=True`: damga "tamam" dese bile şifreleme geçişi YENİDEN koşulur.
    Geçiş fikirdeş olduğu için bu güvenlidir ve destek senaryosunun elidir —
    örneğin satırların bir bölümü elle/yedekten düz metin dönmüşse
    (`manage.py app_password resume --force`).
    """
    with _state_lock:
        state = read_state()
        if state is None:
            return {"resumed": False, "rows": 0, "transition": ""}
        if not crypto.is_unlocked():
            raise AppPasswordError("Geçişi tamamlamak için önce parolayla açın.")

        gecis = str(state.get("gecis", TRANSITION_DONE))
        if gecis == TRANSITION_DECRYPTING:
            satir = _run_decrypt_pass()
            _finish_disable()
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
    # replace=True (birleşme incelemesi): bu noktada DEK, DB parmak izine karşı
    # KANITLANDI — otorite dosya değil anahtardır. Bayat/uyumsuz yedekleme.json
    # (ör. çapraz-DEK geri yükleme artığı) burada sessizce onarılır; replace=False
    # olsaydı kilit açma her denemede "anahtar eşleşmiyor" hatasıyla düşerdi.
    ensure_public_config(_data_dir(), data_key, replace=True)
    encrypt_legacy_backups(backup_dir(), _data_dir())
    _reset_failures()
    if gecis != TRANSITION_DONE or not kayitli:
        resume_pending()


def _unwrap_with_password(state: dict[str, Any], password: str) -> bytes:
    bolum = dict(state.get("parola", {}))
    return _unwrap(bolum, state, password, _WRONG_PASSWORD_MESSAGE)


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
