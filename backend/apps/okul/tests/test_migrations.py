"""`okul` veri göçlerinin davranış testleri.

`0007_aihl_b_grubu_program_anahtarlari`: AİHL B grubu çizelge programı yedi program
dosyasına bölündü (19.09.2026); kayıtlı `SchoolConfig.level_programs` içindeki ESKİ
anahtar yenilerine açılır. Göç dosyası DONDURULMUŞTUR (anahtarları inline taşır); bu
testler o davranışı sabitler ve göçün KAPATTIĞI tuzağı belgeler: bilinmeyen anahtar
taşıyan Okul Bilgileri kaydedilemez (`validate_level_programs`) ve çizelge matrisi
bayat anahtarı kaldıracak kutu çizmez. Emsal: `dersler/tests/test_catalog.py
::TestGocSiniflandirmasi`. Çizelge verisi sentetiktir (`tmp_path`); kişisel veri yok.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from django.apps import apps as django_apps
from rest_framework.test import APIClient

from apps.okul.models import SchoolConfig

AYAR_URL = "/api/v1/setup/school-config/"
ANA = "anadolu-imam-hatip-lisesi-2025"
ESKI = "anadolu-imam-hatip-lisesi-program-proje-2025"

PROGRAM_MD = """
- program_key: {key}
- ad: {key}
- okul_turu: ANADOLU_IMAM_HATIP_LISESI
- yururluk: 2025-2026

| Ders | Seviyeler | Tür | Sınav |
|---|---|---|---|
| {ders} | 9-12 | SECMELI | YAZILI |
"""


def _goc() -> ModuleType:
    return importlib.import_module("apps.okul.migrations.0007_aihl_b_grubu_program_anahtarlari")


class TestAnahtarAcma:
    """Saf işlev — DB gerekmez."""

    def test_eski_anahtar_yerinde_yedi_programa_acilir(self) -> None:
        goc = _goc()
        yeni, degisti = goc._anahtarlari_ac({"9": [ANA, ESKI], "10": [ESKI, "baska"]})
        assert degisti
        assert yeni["9"] == [ANA, *goc._YENI_ANAHTARLAR]
        assert yeni["10"] == [*goc._YENI_ANAHTARLAR, "baska"]  # konum korunur
        assert len(goc._YENI_ANAHTARLAR) == 7 and ESKI not in goc._YENI_ANAHTARLAR

    def test_elle_eklenmis_yeni_anahtar_teklenir(self) -> None:
        goc = _goc()
        spor = goc._YENI_ANAHTARLAR[0]
        yeni, _ = goc._anahtarlari_ac({"11": [spor, ESKI]})
        assert yeni["11"] == list(goc._YENI_ANAHTARLAR)

    def test_eski_anahtar_yoksa_dokunulmaz(self) -> None:
        goc = _goc()
        atama = {"9": ["fen-lisesi-2025"], "10": []}
        assert goc._anahtarlari_ac(atama) == (atama, False)
        assert goc._anahtarlari_ac({}) == ({}, False)

    @pytest.mark.parametrize("bozuk", [None, [], "metin", {"9": ESKI}, {"9": None}])
    def test_beklenmeyen_bicime_dokunulmaz(self, bozuk: Any) -> None:
        # Biçimi düzeltmek bu göçün işi değildir; açılışı düşürmemesi yeter.
        assert _goc()._anahtarlari_ac(bozuk) == (bozuk, False)


@pytest.mark.django_db
class TestKayitliYapilandirma:
    @pytest.fixture
    def cizelgeler(self, settings: Any, tmp_path: Path) -> None:
        """Ana çizelge + yedi B grubu programı, göçün KENDİ anahtar listesinden üretilir."""
        for sira, key in enumerate((ANA, *_goc()._YENI_ANAHTARLAR)):
            (tmp_path / f"{key}.md").write_text(
                PROGRAM_MD.format(key=key, ders=f"Ders {sira}"), encoding="utf-8"
            )
        settings.CATALOG_DIR = tmp_path
        settings.COURSE_ALIAS_FILE = tmp_path / "takma-ad-yok.md"

    def test_goc_kayitli_atamayi_cevirir_ve_kaydetme_tuzagini_kapatir(
        self, cizelgeler: None
    ) -> None:
        goc = _goc()
        bayat = {"9": [ANA, ESKI], "12": [ANA]}
        SchoolConfig.objects.create(
            pk=SchoolConfig.SINGLETON_PK, school_name="Örnek AİHL", level_programs=bayat
        )
        client = APIClient()
        # TUZAK: bayat anahtar durdukça Okul Bilgileri hiçbir alanıyla kaydedilemez.
        yanit = client.put(
            AYAR_URL, {"school_name": "Örnek AİHL", "level_programs": bayat}, format="json"
        )
        assert yanit.status_code == 400
        assert "Bilinmeyen çizelge programı" in str(yanit.json()["fields"]["level_programs"])

        goc.b_grubu_anahtarini_bol(django_apps, None)

        iyilesen = SchoolConfig.load().level_programs
        assert iyilesen == {"9": [ANA, *goc._YENI_ANAHTARLAR], "12": [ANA]}
        yanit = client.put(
            AYAR_URL, {"school_name": "Örnek AİHL", "level_programs": iyilesen}, format="json"
        )
        assert yanit.status_code == 200
        assert yanit.json()["level_programs"] == iyilesen

    def test_goc_yinelenince_ve_kayit_yokken_zararsiz(self) -> None:
        goc = _goc()
        goc.b_grubu_anahtarini_bol(django_apps, None)  # kurulmamış veritabanı
        assert not SchoolConfig.objects.exists()
        SchoolConfig.objects.create(pk=SchoolConfig.SINGLETON_PK, level_programs={"10": [ESKI]})
        goc.b_grubu_anahtarini_bol(django_apps, None)
        goc.b_grubu_anahtarini_bol(django_apps, None)
        assert SchoolConfig.load().level_programs == {"10": list(goc._YENI_ANAHTARLAR)}
