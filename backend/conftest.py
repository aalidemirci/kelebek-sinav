"""Kök test ayarları — çizelge verisi testlerden YALITILIR.

Katalog senkronu artık ders listesi, ayar kaydı, kurulum tamamlama, ders yılı
aktivasyonu ve takvim havuzu doldurma yollarından KENDİLİĞİNDEN koşar
(tasarım §7.2). Depodaki gerçek çizelgeler (`data/ders-cizelgeleri`) testte
okunursa her okul yapılandırması dokunuşu ~60 MEB dersi yükler ve "havuzda tam
şu dersler var" diyen takvim testleri sessizce şişer. Bu yüzden her test
boş bir katalog diziniyle başlar; gerçek dosyaları sınayan testler
(`apps/dersler/tests/test_catalog_programs.py`, `test_catalog.py`) yolu
İMPORT ANINDA sabitler, sentetik veri kullananlar `settings`/`override_settings`
ile kendi dizinini verir.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def _cizelge_verisi_yalitilir(settings: Any, tmp_path: Path) -> None:
    settings.CATALOG_DIR = tmp_path / "cizelge-yok"
    settings.COURSE_ALIAS_FILE = tmp_path / "takma-ad-yok.md"
