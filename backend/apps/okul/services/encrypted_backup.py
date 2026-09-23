"""Kullanıcının istediğinde indirebildiği şifreli SQLite yedeği."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from desktop.backup import database_snapshot
from desktop.backup_crypto import encrypt_bytes, load_public_key, usable_recovery_header
from django.conf import settings

from apps.okul.services import app_password


class EncryptedBackupError(ValueError):
    """Kullanıcıya gösterilebilen yedek oluşturma hatası."""


def create_encrypted_backup() -> tuple[bytes, str]:
    """Tutarlı veritabanı görüntüsünü RAM'de şifreleyip indirmeye hazırlar."""
    if app_password.is_locked():
        raise EncryptedBackupError(
            "Şifreli yedek oluşturmak için uygulama parolasıyla kilidi açın."
        )

    data_dir = app_password.state_path().parent
    database_path = Path(str(settings.DATABASES["default"]["NAME"]))
    if not database_path.is_file():
        raise EncryptedBackupError("Yedeklenecek veritabanı bulunamadı.")

    # Başlık, güncel ve kullanılabilir güvenlik dosyasından gelir: başlığı olmayan
    # bir yedek hiçbir parolayla açılamazdı (günlük yedekle aynı kural).
    header = usable_recovery_header(data_dir)
    if header is None:
        raise EncryptedBackupError(
            "Güvenlik dosyası (guvenlik.json) okunamadığı için şifreli yedek oluşturulamadı."
        )
    try:
        public_key = load_public_key(data_dir)
        encrypted = encrypt_bytes(
            database_snapshot(database_path),
            public_key,
            recovery_header=header,
        )
    except ValueError as exc:
        raise EncryptedBackupError(str(exc)) from exc
    except (OSError, sqlite3.Error) as exc:
        raise EncryptedBackupError("Şifreli yedek oluşturulamadı.") from exc

    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d-%H%M%S")
    return encrypted, f"kelebek-sinav-yedek-{timestamp}.ksbak"
