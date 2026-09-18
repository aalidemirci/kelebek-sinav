"""`okul` serializer doğrulamalarının başka dosyada sınanmayan dalları.

Kişi/şube/küme/zümre doğrulamaları kendi test dosyalarındadır (`test_persons`,
`test_class_sections`, `test_section_groups`, `test_departments`). Burada kalanlar:

- `SchoolConfigSerializer.level_programs` — kademeli dönüşüm/çok programlı okulun
  seviye → çizelge ataması. Bozuk gövde katalog senkronuna ULAŞMADAN, hangi
  kısmının yanlış olduğunu söyleyen Türkçe mesajla reddedilmelidir (bilinmeyen
  anahtar/geçersiz seviye/teklenme `dersler/tests/test_catalog_programs.py`'da).
- `SchoolYearSerializer` — tarih sırası ve ad tekliği.
- `ImportRequestSerializer` — dosya ile pano metni BİRBİRİNİ DIŞLAR.

Çizelge verisi sentetiktir (`tmp_path`); kişisel veri yoktur.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.okul.models import ImportRun, SchoolConfig, SchoolYear
from apps.okul.serializers import ImportRequestSerializer

pytestmark = pytest.mark.django_db

AYAR_URL = "/api/v1/setup/school-config/"
YIL_URL = "/api/v1/school-years/"

AL_MD = """
- program_key: al-test
- ad: AL test
- okul_turu: ANADOLU_LISESI
- hazirlik: hayır
- yururluk: 2025-2026
- kademeli: hayır

| Ders | Seviyeler | Tür | Sınav |
|---|---|---|---|
| Coğrafya | 9, 10 | ORTAK | YAZILI |
"""


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def cizelge(settings: Any, tmp_path: Path) -> str:
    """Tek programlı sentetik çizelge dizini → bilinen program anahtarı."""
    kok = tmp_path / "cizelge"
    kok.mkdir()
    (kok / "al.md").write_text(AL_MD, encoding="utf-8")
    settings.CATALOG_DIR = kok
    return "al-test"


# ---------------------------------------------------------------------------
# Seviye → çizelge programı ataması
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("govde", "beklenen"),
    [
        (["al-test"], "sözlük olmalıdır"),
        ({"dokuz": ["al-test"]}, "sayısal olmalıdır"),
        ({"9": "al-test"}, "program listesi bekleniyor"),
        ({"9": [7]}, "Bilinmeyen çizelge programı"),
    ],
)
def test_bozuk_seviye_atamasi_gerekcesiyle_reddedilir(
    client: APIClient, cizelge: str, govde: Any, beklenen: str
) -> None:
    """Gövdenin HANGİ kısmı yanlışsa mesaj onu söyler; ayar satırı yazılmaz."""
    yanit = client.put(
        AYAR_URL, {"school_name": "Örnek AL", "level_programs": govde}, format="json"
    )

    assert yanit.status_code == 400
    assert beklenen in str(yanit.json()["fields"]["level_programs"])
    assert SchoolConfig.load().school_name == ""


def test_bos_seviye_atamasi_varsayilana_donus_demektir(client: APIClient, cizelge: str) -> None:
    """Boş değer hata değil "varsayılan atamaya dön"dür: kayıtlı atama silinir."""
    client.put(
        AYAR_URL,
        {"school_name": "Örnek AL", "level_programs": {"9": [cizelge]}},
        format="json",
    )
    assert SchoolConfig.load().level_programs == {"9": [cizelge]}

    yanit = client.put(AYAR_URL, {"school_name": "Örnek AL", "level_programs": ""}, format="json")

    assert yanit.status_code == 200
    assert yanit.json()["level_programs"] == {}
    assert SchoolConfig.load().level_programs == {}


def test_okulun_seviye_kumesi_disindaki_gecerli_seviye_kabul_edilir(
    client: APIClient, cizelge: str
) -> None:
    """Hazırlıksız okulda Hazırlık (0) ataması REDDEDİLMEZ: plan onu yok sayar,
    hazırlık sonradan açılırsa atama hazır durur. Anahtar dizgeye normalize edilir."""
    yanit = client.put(
        AYAR_URL,
        {"school_name": "Örnek AL", "has_prep_class": False, "level_programs": {0: [cizelge]}},
        format="json",
    )

    assert yanit.status_code == 200
    assert yanit.json()["level_programs"] == {"0": [cizelge]}


# ---------------------------------------------------------------------------
# Ders yılı
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bitis", ["2026-09-01", "2026-06-30"])
def test_ders_yili_bitisi_baslangictan_sonra_olmalidir(client: APIClient, bitis: str) -> None:
    """Aynı gün de reddedilir — sıfır günlük ders yılına dönem kurulamaz."""
    yanit = client.post(
        YIL_URL, {"name": "2026-2027", "start_date": "2026-09-01", "end_date": bitis}, format="json"
    )

    assert yanit.status_code == 400
    assert "başlangıçtan sonra" in str(yanit.json()["fields"]["end_date"])
    assert not SchoolYear.objects.exists()


def test_ders_yili_adi_tekildir_ve_yeni_yil_pasif_acilir(client: APIClient) -> None:
    """Çakışma 500 (IntegrityError) DEĞİL 400'dür. Aktiflik yalnız `activate/` ucundan
    değişir — gövdeyle gönderilen `is_active` yok sayılır (tek-aktif kuralı serviste)."""
    govde = {
        "name": "2026-2027",
        "start_date": "2026-09-01",
        "end_date": "2027-06-30",
        "is_active": True,
    }

    ilk = client.post(YIL_URL, govde, format="json")
    assert ilk.status_code == 201 and ilk.json()["is_active"] is False

    tekrar = client.post(YIL_URL, govde, format="json")
    assert tekrar.status_code == 400
    assert "name" in tekrar.json()["fields"]
    assert SchoolYear.objects.count() == 1


# ---------------------------------------------------------------------------
# İçe aktarma girdisi: dosya YA DA metin
# ---------------------------------------------------------------------------


def _dosya() -> SimpleUploadedFile:
    return SimpleUploadedFile("liste.xlsx", b"icerik", content_type="application/octet-stream")


@pytest.mark.parametrize(
    "govde",
    [
        {},
        {"text": "   \n "},  # yalnız boşluk = metin yok
    ],
)
def test_ice_aktarma_girdisi_bos_olamaz(govde: dict[str, Any]) -> None:
    serializer = ImportRequestSerializer(data=govde)

    assert not serializer.is_valid()
    assert "tam olarak biri" in str(serializer.errors)


def test_ice_aktarma_girdisi_dosya_ve_metni_birlikte_kabul_etmez(client: APIClient) -> None:
    """İkisi birden gelirse hangisinin işleneceği belirsizdir — sessiz tercih yerine ret.

    Ret ayrıştırmadan ÖNCEDİR: geçmişe FAILED/PREVIEWED izi de düşmez.
    """
    yanit = client.post(
        "/api/v1/imports/students/preview/",
        {"file": _dosya(), "text": "Sınıf\tOkul No\tAdı Soyadı\n9/A\t101\tDENEME ÖĞRENCİ"},
        format="multipart",
    )

    assert yanit.status_code == 400
    assert yanit.json()["code"] == "validation_error"
    assert "tam olarak biri" in str(yanit.json()["fields"]["non_field_errors"])
    assert not ImportRun.objects.exists()


def test_ice_aktarma_metni_bosluklari_kirpilmadan_tasinir() -> None:
    """Pano metninde baştaki sekme BOŞ HÜCREDİR; kırpılırsa sütunlar bir sola kayar."""
    metin = "\tOkul No\tAdı Soyadı\n"

    serializer = ImportRequestSerializer(data={"text": metin})

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["text"] == metin
