from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import cast
from unittest import mock

import pytest
from desktop.backup_crypto import MAGIC, decrypt_bytes, ensure_public_config
from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework.test import APIClient

from apps.okul.services import app_password, encrypted_backup


def test_veritabani_ramde_sifrelenerek_ksbak_uretilir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    database = data_dir / "db.sqlite3"
    secret = "ogrenci-kisisel-verisi"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE kayit (deger TEXT)")
        connection.execute("INSERT INTO kayit VALUES (?)", (secret,))

    data_key = b"\x42" * 32
    ensure_public_config(data_dir, data_key)
    monkeypatch.setattr(app_password, "state_path", lambda: data_dir / "guvenlik.json")
    monkeypatch.setattr(app_password, "is_locked", lambda: False)
    monkeypatch.setitem(settings.DATABASES["default"], "NAME", database)

    content, filename = encrypted_backup.create_encrypted_backup()

    assert filename.endswith(".ksbak")
    assert content.startswith(MAGIC)
    assert secret.encode() not in content
    restored = decrypt_bytes(content, data_key)
    assert restored.startswith(b"SQLite format 3")
    assert secret.encode() in restored


def test_kilitliyken_yedek_olusturulmaz(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_password, "is_locked", lambda: True)

    with pytest.raises(encrypted_backup.EncryptedBackupError, match="kilidi açın"):
        encrypted_backup.create_encrypted_backup()


def test_indirme_ucu_sifreli_dosyayi_ek_olarak_dondurur() -> None:
    with mock.patch(
        "apps.okul.views.encrypted_backup_service.create_encrypted_backup",
        return_value=(b"KSBAK-encrypted", "yedek.ksbak"),
    ):
        response = APIClient().post("/api/v1/backups/encrypted/")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/octet-stream"
    assert "yedek.ksbak" in response["Content-Disposition"]
    assert isinstance(response, StreamingHttpResponse)
    content = cast(Iterable[bytes], response.streaming_content)
    assert b"".join(content) == b"KSBAK-encrypted"
