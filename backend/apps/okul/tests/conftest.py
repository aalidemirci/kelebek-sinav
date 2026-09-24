"""`okul` testlerinin ortak güvenlik fikstürleri (KENDİLİĞİNDEN uygulanmaz).

`guvenlik_ortami`: test kendi güvenlik dosyası + yedek dizini ile koşar,
Argon2 ucuz profile iner, gecikme merdiveni `sleep` çağırmaz, anahtar
sıfırlanır. Aynı kurulum `test_app_password.py`'de modül içi (autouse) durur;
yeni güvenlik test modülleri bunu `pytest.mark.usefixtures` ile ister.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from apps.okul.services import app_password
from shared import crypto


@pytest.fixture
def guvenlik_ortami(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Güvenlik dizinini döndürür (`guvenlik.json` + `yedekleme.json` burada durur)."""
    guvenlik_dizini = tmp_path / "veri"
    guvenlik_dizini.mkdir()
    monkeypatch.setenv(app_password.ENV_SECURITY_DIR, str(guvenlik_dizini))
    monkeypatch.setenv(app_password.ENV_BACKUP_DIR, str(tmp_path / "yedek"))
    # Ucuz Argon2 profili — YALNIZ maliyet; algoritma ve dosya biçimi üretimdekiyle aynı.
    monkeypatch.setattr(
        crypto, "DEFAULT_KDF", crypto.KdfParams(time_cost=1, memory_cost=8, parallelism=1)
    )
    monkeypatch.setattr(app_password, "FAILURE_DELAYS", (0.0,))
    crypto.unload_key()
    yield guvenlik_dizini
    crypto.unload_key()
