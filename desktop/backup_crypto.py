"""Kelebek Sınav yedek kapsayıcısı.

Yedekleme için asimetrik zarf şifrelemesi kullanılır: veri anahtarından türetilen
X25519 özel anahtar yalnız uygulama parolası açıldığında elde edilebilir; açık
anahtar ise başlangıçta parola sorulmadan yedek alınabilmesi için diskte tutulur.
Yedek içeriği AES-256-GCM ile hem şifrelenir hem de doğrulanır.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b"KSBAK\x02"
CONFIG_FILE_NAME = "yedekleme.json"
BACKUP_SUFFIX = ".ksbak"
_NONCE_BYTES = 12
_PUBLIC_BYTES = 32
_LENGTH_BYTES = 4
_PRIVATE_INFO = b"KelebekSinav/backup/private/v1"
_ENVELOPE_INFO = b"KelebekSinav/backup/envelope/v1"


class BackupCryptoError(ValueError):
    """Bozuk/uyumsuz yedek veya anahtar hatası."""


def _hkdf(value: bytes, *, info: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(value)


def private_key_from_data_key(data_key: bytes) -> X25519PrivateKey:
    """Uygulama DEK'inden alan şifrelemesinden bağımsız yedek özel anahtarı türetir."""
    return X25519PrivateKey.from_private_bytes(_hkdf(data_key, info=_PRIVATE_INFO))


def public_key_bytes(data_key: bytes) -> bytes:
    return (
        private_key_from_data_key(data_key)
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    )


def config_path(data_dir: Path) -> Path:
    return data_dir / CONFIG_FILE_NAME


def ensure_public_config(data_dir: Path, data_key: bytes, *, replace: bool = False) -> Path:
    """Açık yedek anahtarını atomik yazar; mevcut farklı anahtarı sessizce ezmez."""
    path = config_path(data_dir)
    encoded = base64.b64encode(public_key_bytes(data_key)).decode("ascii")
    if path.is_file() and not replace:
        current = load_public_key(data_dir)
        if current.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ) != base64.b64decode(encoded):
            raise BackupCryptoError("Yedekleme anahtarı bu veri anahtarıyla eşleşmiyor.")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(
        json.dumps({"surum": 1, "algoritma": "X25519+AES-256-GCM", "acik_anahtar": encoded}),
        encoding="utf-8",
    )
    temp.replace(path)
    return path


def load_public_key(data_dir: Path) -> X25519PublicKey:
    try:
        raw = json.loads(config_path(data_dir).read_text(encoding="utf-8"))
        key = base64.b64decode(str(raw["acik_anahtar"]), validate=True)
        if len(key) != _PUBLIC_BYTES:
            raise ValueError
        return X25519PublicKey.from_public_bytes(key)
    except (OSError, KeyError, ValueError, TypeError) as exc:
        raise BackupCryptoError(
            "Şifreli yedekleme anahtarı yok veya bozuk; önce uygulama parolasını kurup açın."
        ) from exc


def can_encrypt(data_dir: Path) -> bool:
    try:
        load_public_key(data_dir)
    except BackupCryptoError:
        return False
    return True


def recovery_metadata(data_dir: Path) -> bytes:
    """Parolayla DEK'i açmaya yarayan, kişisel veri içermeyen kurtarma başlığı."""
    current = data_dir / "guvenlik.json"
    candidates = [current] if current.is_file() else []
    candidates.extend(sorted(data_dir.glob("guvenlik-arsiv-*.json"), reverse=True))
    return candidates[0].read_bytes() if candidates else b""


def encrypt_bytes(
    plaintext: bytes,
    public_key: X25519PublicKey,
    *,
    recovery_header: bytes = b"",
) -> bytes:
    ephemeral = X25519PrivateKey.generate()
    ephemeral_public = ephemeral.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    aes_key = _hkdf(ephemeral.exchange(public_key), info=_ENVELOPE_INFO)
    nonce = os.urandom(_NONCE_BYTES)
    if len(recovery_header) > 1_000_000:
        raise BackupCryptoError("Yedek kurtarma başlığı beklenenden büyük.")
    header = (
        MAGIC
        + ephemeral_public
        + nonce
        + len(recovery_header).to_bytes(_LENGTH_BYTES, "big")
        + recovery_header
    )
    return header + AESGCM(aes_key).encrypt(nonce, plaintext, header)


def encrypt_to_path(
    plaintext: bytes,
    target: Path,
    public_key: X25519PublicKey,
    *,
    recovery_header: bytes = b"",
) -> None:
    """Şifreli kapsayıcıyı atomik yazar."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    temp.unlink(missing_ok=True)
    try:
        temp.write_bytes(encrypt_bytes(plaintext, public_key, recovery_header=recovery_header))
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)


def embedded_recovery_metadata(container: bytes) -> bytes:
    """Yedekteki parola KDF/sarmal bilgisini geri yükleme aracına verir."""
    fixed_len = len(MAGIC) + _PUBLIC_BYTES + _NONCE_BYTES + _LENGTH_BYTES
    if len(container) <= fixed_len or not container.startswith(MAGIC):
        raise BackupCryptoError("Dosya geçerli bir Kelebek Sınav yedeği değil.")
    length_start = fixed_len - _LENGTH_BYTES
    metadata_len = int.from_bytes(container[length_start:fixed_len], "big")
    end = fixed_len + metadata_len
    if end >= len(container):
        raise BackupCryptoError("Yedek başlığı bozuk veya eksik.")
    return container[fixed_len:end]


def decrypt_bytes(container: bytes, data_key: bytes) -> bytes:
    """Geri yükleme/test aracı; kimlik doğrulaması başarısızsa açık hata verir."""
    fixed_len = len(MAGIC) + _PUBLIC_BYTES + _NONCE_BYTES + _LENGTH_BYTES
    if len(container) <= fixed_len or not container.startswith(MAGIC):
        raise BackupCryptoError("Dosya geçerli bir Kelebek Sınav yedeği değil.")
    offset = len(MAGIC)
    ephemeral = X25519PublicKey.from_public_bytes(container[offset : offset + _PUBLIC_BYTES])
    nonce_start = offset + _PUBLIC_BYTES
    nonce_end = nonce_start + _NONCE_BYTES
    nonce = container[nonce_start:nonce_end]
    metadata_len = int.from_bytes(container[nonce_end:fixed_len], "big")
    header_len = fixed_len + metadata_len
    if header_len >= len(container):
        raise BackupCryptoError("Yedek başlığı bozuk veya eksik.")
    aes_key = _hkdf(
        private_key_from_data_key(data_key).exchange(ephemeral),
        info=_ENVELOPE_INFO,
    )
    try:
        return AESGCM(aes_key).decrypt(nonce, container[header_len:], container[:header_len])
    except Exception as exc:  # InvalidTag ayrıntısı kullanıcıya/saldırgana sızdırılmaz.
        raise BackupCryptoError("Yedek anahtarı yanlış veya dosyanın bütünlüğü bozulmuş.") from exc
