"""Opsiyonel uygulama parolası — anahtar tutucu, Argon2id türetme, şifreli alanlar.

Tasarım §6 + §10.2 kararının ALT KATMANIDIR: SQLCipher ve "kapanışta dosyayı
şifrele" reddedildi; seçilen yol OYS'nin (Okul Yönetim Sistemi) sahada test
edilmiş `shared/fields.py` Fernet alan şifrelemesidir. Bu dosya o alanı bu
programın gerçeklerine uyarlar. OYS'den FARKLAR:

1. **Anahtar ayardan değil, ÇALIŞMA ZAMANINDAN gelir.** OYS'de anahtar
   `settings.FIELD_ENCRYPTION_KEY` (.env) ile sabittir; burada kullanıcı
   parolasından türetilir ve programın kilidi açılana kadar YOKTUR. Bu yüzden
   `lru_cache`'li Fernet KULLANILAMAZ — anahtar süreç ömrü içinde yüklenir,
   boşaltılır, değişir.
2. **Parolasız kip birinci sınıf vatandaştır.** Kullanıcı parola koymadıysa
   alanlar DÜZ yazılır (tasarım §10.2: "Varsayılan (parolasız): hassas alanlar
   DÜZ"). Aynı alan sınıfı iki kipte de çalışır; şema tek biçimdir.
3. **Yazma/okuma ayrı ayarlanabilir** (`plaintext_writes()`): parola kaldırma
   geçişinde satırlar ŞİFRELİ okunup DÜZ yazılır. Tek bayrakla bu yapılamazdı.

ANAHTARIN BELLEKTEKİ YERİ (kritik tasarım sorusu 1): anahtar süreç-genelinde,
bu modülün `_holder` nesnesinde tutulur ve kilit açıldıktan sonra **süreç ömrü
boyunca** bellekte kalır. Gerekçe: program authsuz ve tek kullanıcılıdır —
anahtarı bağlayacağımız bir oturum/istek kimliği yoktur; gömülü sunucu (waitress)
yalnız bu kullanıcının penceresine hizmet eder (`desktop/session_guard.py`).
Anahtarı her istekte yeniden türetmek Argon2id maliyetini (~0,2 sn) her tıklamaya
yayardı. Kilitleme = programı kapatmak VEYA açık "Kilitle" eylemi
(`POST /security/lock/` → `unload_key()`). Anahtar diske YAZILMAZ, loglanmaz,
hata mesajında yankılanmaz.

BLIND INDEX YOKTUR (tasarım §10.2): yerel ölçekte (≤1000 öğrenci) eşleştirme
bellek içinde çözülür. Bunun bedeli: **şifreleme açıkken şifreli alan üzerinde
DB tarafı filtre/LIKE çalışmaz** (`Student.objects.filter(tckn=...)` daima boş
döner — Fernet her şifrelemede farklı token üretir). Şifreli alanla eşleştirme
yapan tek yer içe aktarmadır; o yol `apps.okul.selectors.find_student_by_tckn`
üzerinden Python tarafına alınmıştır. Aynı sebeple `uq_student_tckn_alive`
kısıtı şifreli kipte KOPYA YAKALAYAMAZ — tekillik yine servis katmanında korunur.
"""

from __future__ import annotations

import base64
import hmac
import secrets
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, cast

from argon2.low_level import Type as Argon2Type
from argon2.low_level import hash_secret_raw
from cryptography.fernet import Fernet, InvalidToken
from django.db import models

# Veri anahtarı (DEK) uzunluğu — Fernet 32 baytlık anahtar ister.
KEY_BYTES = 32
# Argon2id tuzu (parola başına ve kurtarma anahtarı başına ayrı üretilir).
SALT_BYTES = 16


@dataclass(frozen=True)
class KdfParams:
    """Argon2id maliyet parametreleri.

    Varsayılan, RFC 9106'nın "düşük bellek" profilidir (64 MiB / t=3 / p=4):
    okul bilgisayarında ~0,2 sn sürer, ama çalınmış bir veri klasörüne karşı
    kaba kuvvet denemesini de aynı oranda pahalılaştırır. Parametreler
    `guvenlik.json` içinde SAKLANIR; ileride artırılırsa eski dosyalar kendi
    parametreleriyle açılmaya devam eder (ileri uyumluluk).
    """

    time_cost: int = 3
    memory_cost: int = 65536  # KiB → 64 MiB
    parallelism: int = 4

    def to_dict(self) -> dict[str, int]:
        return {
            "time_cost": self.time_cost,
            "memory_cost": self.memory_cost,
            "parallelism": self.parallelism,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KdfParams:
        return cls(
            time_cost=int(data.get("time_cost", cls.time_cost)),
            memory_cost=int(data.get("memory_cost", cls.memory_cost)),
            parallelism=int(data.get("parallelism", cls.parallelism)),
        )


# Modül düzeyi varsayılan — testler ucuz profile indirir (Argon2 kasten yavaştır).
DEFAULT_KDF = KdfParams()


# ---------------------------------------------------------------------------
# Anahtar türetme ve sarmalama (zarf şifreleme)
# ---------------------------------------------------------------------------
# Neden ZARF (envelope) şifreleme? Kurtarma anahtarı şartı bunu ZORUNLU kılar:
# aynı veriyi hem parolayla hem kurtarma anahtarıyla açabilmek için, alanları
# şifreleyen anahtar (DEK) ikisinden de BAĞIMSIZ olmalı ve iki ayrı sarmalda
# saklanmalıdır. Yan faydaları:
#   * Parola değişimi veriyi YENİDEN ŞİFRELEMEZ — yalnız sarmal değişir (anlık,
#     yarıda kalma riski yok).
#   * DEK hiç değişmediği için ESKİ YEDEKLER (`gunluk-*.sqlite3`) parola
#     değiştikten sonra da açılabilir kalır.


def new_data_key() -> bytes:
    """Rastgele veri anahtarı (DEK) üretir."""
    return secrets.token_bytes(KEY_BYTES)


def new_salt() -> bytes:
    """Rastgele Argon2id tuzu üretir."""
    return secrets.token_bytes(SALT_BYTES)


def derive_key(secret: str, *, salt: bytes, params: KdfParams | None = None) -> bytes:
    """Parola/kurtarma anahtarından Argon2id ile 32 baytlık sarmalama anahtarı türetir."""
    kdf = params or DEFAULT_KDF
    return hash_secret_raw(
        secret=secret.encode("utf-8"),
        salt=salt,
        time_cost=kdf.time_cost,
        memory_cost=kdf.memory_cost,
        parallelism=kdf.parallelism,
        hash_len=KEY_BYTES,
        type=Argon2Type.ID,
    )


def _fernet_for(raw_key: bytes) -> Fernet:
    """Ham 32 bayttan Fernet örneği (Fernet base64 kodlu anahtar ister)."""
    return Fernet(base64.urlsafe_b64encode(raw_key))


def wrap_key(data_key: bytes, *, wrapping_key: bytes) -> str:
    """DEK'i sarmalar (şifreler). Dönen metin `guvenlik.json` içinde saklanır."""
    return _fernet_for(wrapping_key).encrypt(data_key).decode("ascii")


def unwrap_key(wrapped: str, *, wrapping_key: bytes) -> bytes:
    """Sarmalı çözer. Yanlış parola/kurtarma anahtarında `InvalidToken` yükselir.

    AYRI BİR "doğrulama hash'i" TUTULMAZ: Fernet token'ı kimlik doğrulamalıdır
    (HMAC), yani sarmalın başarıyla çözülmesi parolanın doğruluğunun kanıtıdır.
    Ayrıca bir parola özeti saklamak, o özeti çevrimdışı kırma denemesine hedef
    yapardı — az sır, az yüzey.
    """
    return _fernet_for(wrapping_key).decrypt(wrapped.encode("ascii"))


def key_fingerprint(data_key: bytes) -> str:
    """Veri anahtarının tek yönlü parmak izi (DB ↔ güvenlik dosyası eşleşmesi için).

    `SchoolConfig.app_password_hash` alanına yazılır. Parolanın özeti DEĞİLDİR:
    DB kopyaları (yedekler) okul dışına çıkabilir, içlerinde parola özeti
    bulunması çevrimdışı kaba kuvvete davetiye olurdu.
    """
    return "v1:" + hmac.new(data_key, b"ks-anahtar-parmak-izi", sha256).hexdigest()


# ---------------------------------------------------------------------------
# Süreç-geneli anahtar tutucu
# ---------------------------------------------------------------------------
class _KeyHolder:
    """Çalışma zamanı anahtar durumu (süreç geneli, iş parçacığı güvenli).

    `waitress` istekleri birden çok iş parçacığında karşılar; durum tek
    kullanıcıya ait olduğu için süreç geneli tutulur, kilitle korunur.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._fernet: Fernet | None = None
        self._raw: bytes | None = None
        self._encrypt_writes = True

    def load(self, raw_key: bytes) -> None:
        with self._lock:
            self._raw = raw_key
            self._fernet = _fernet_for(raw_key)
            self._encrypt_writes = True

    def unload(self) -> None:
        with self._lock:
            self._raw = None
            self._fernet = None
            self._encrypt_writes = True

    @property
    def unlocked(self) -> bool:
        return self._fernet is not None

    def fingerprint(self) -> str | None:
        raw = self._raw
        return key_fingerprint(raw) if raw is not None else None

    def raw(self) -> bytes | None:
        return self._raw

    def read_fernet(self) -> Fernet | None:
        return self._fernet

    def write_fernet(self) -> Fernet | None:
        return self._fernet if self._encrypt_writes else None

    @contextmanager
    def plaintext_writes(self) -> Iterator[None]:
        with self._lock:
            onceki = self._encrypt_writes
            self._encrypt_writes = False
        try:
            yield
        finally:
            with self._lock:
                self._encrypt_writes = onceki


_holder = _KeyHolder()


def load_key(raw_key: bytes) -> None:
    """Veri anahtarını belleğe alır (kilidi açar)."""
    _holder.load(raw_key)


def unload_key() -> None:
    """Anahtarı bellekten düşürür (kilitler). Diske hiçbir şey yazılmaz."""
    _holder.unload()


def is_unlocked() -> bool:
    """Veri anahtarı bellekte mi?"""
    return _holder.unlocked


def active_fingerprint() -> str | None:
    """Yüklü anahtarın parmak izi; anahtar yoksa None."""
    return _holder.fingerprint()


def active_key() -> bytes | None:
    """Yüklü veri anahtarı (ham). YALNIZ geçiş aracı içindir; asla loglanmaz/döndürülmez."""
    return _holder.raw()


def writes_encrypted() -> bool:
    """Yeni yazmalar şifrelenecek mi? (anahtar yüklü VE düz-yazma kipi kapalı)"""
    return _holder.write_fernet() is not None


@contextmanager
def plaintext_writes() -> Iterator[None]:
    """Blok boyunca yazmalar DÜZ yapılır; okuma şifre çözmeye devam eder.

    Parola kaldırma geçişinin can damarı: satır şifreli okunur, düz yazılır.
    """
    with _holder.plaintext_writes():
        yield


# ---------------------------------------------------------------------------
# Model alanları
# ---------------------------------------------------------------------------
class EncryptedTextField(models.TextField):  # type: ignore[type-arg]  # Any davranışı korunur
    """Anahtar yüklüyse Fernet ile şifreli, değilse DÜZ saklayan metin alanı.

    Python tarafında daima düz metin (str) gibi davranır. DB sütunu TEXT'tir;
    parolasız kipte içerik düz metin, parolalı kipte base64 Fernet token'ıdır.

    KARIŞIK DURUM TOLERANSI: `from_db_value` çözemediği değeri OLDUĞU GİBİ
    döndürür. Bu, geçiş yarıda kalsa bile (elektrik kesintisi) tablonun okunur
    kalmasını sağlar — yarısı şifreli, yarısı düz bir tablo hatasız okunur ve
    geçiş kaldığı yerden tamamlanabilir.
    """

    description = "Parola konulduğunda Fernet ile şifrelenen metin alanı"

    def get_prep_value(self, value: Any) -> str | None:
        """Python değeri → DB'ye yazılacak metin (gerekiyorsa şifreli)."""
        if value is None:
            return None
        text = str(value)
        # Boş dize ŞİFRELENMEZ: "veri yok" hâli DB'de de boş görünmeli — kısmi
        # tekillik kısıtları (`~Q(tckn="")`) ve `blank=True` semantiği buna dayanır.
        if text == "":
            return ""
        fernet = _holder.write_fernet()
        if fernet is None:
            return text
        return fernet.encrypt(text.encode("utf-8")).decode("ascii")

    def from_db_value(self, value: Any, expression: Any, connection: Any) -> str | None:
        """DB'den okunan metin → düz metin (token ise çözülür)."""
        if value is None or value == "":
            return cast("str | None", value)
        fernet = _holder.read_fernet()
        if fernet is None:
            # Kilitli: token çözülemez, olduğu gibi döner (okunamaz ama patlamaz).
            return cast("str | None", value)
        try:
            return fernet.decrypt(str(value).encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeEncodeError, UnicodeDecodeError):
            # Şifrelenmemiş eski/yarım-geçiş verisi veya anahtar uyuşmazlığı.
            # UnicodeEncodeError: Fernet token'ı daima ASCII'dir; Türkçe harf
            # içeren değer tanım gereği düz metindir (OYS Tur 522 dersi).
            return cast("str | None", value)


class EncryptedCharField(EncryptedTextField):
    """CharField arayüzlü şifreli alan (form/serializer `max_length` doğrulaması için)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Şifreli token düz metinden uzundur → DB sütunu TEXT kalır; max_length
        # YALNIZ doğrulama amaçlıdır. Atama super SONRASINDA: `Field.__init__`
        # kendi (None) değeriyle ezer (OYS F52 dersi).
        max_length = kwargs.pop("max_length", None)
        super().__init__(*args, **kwargs)
        self.max_length = max_length

    def deconstruct(self) -> tuple[str, str, list[Any], dict[str, Any]]:
        """Göç dosyasına `max_length`'i geri koyar (`__init__`'te pop'landı)."""
        name, path, args, kwargs = cast(
            "tuple[str, str, list[Any], dict[str, Any]]", super().deconstruct()
        )
        if self.max_length is not None:
            kwargs["max_length"] = self.max_length
        return name, path, args, kwargs


def encrypted_fields_of(model: type[models.Model]) -> tuple[models.Field[Any, Any], ...]:
    """Modelin şifreli alanları (kayıt defteri elle tutulmaz, koddan okunur)."""
    return tuple(f for f in model._meta.get_fields() if isinstance(f, EncryptedTextField))
