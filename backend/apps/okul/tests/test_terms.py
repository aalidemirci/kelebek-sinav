"""Ders yılı dönemleri — kurulum, tarih doğrulaması ve tarihten dönem çözümü.

Dönem, sınav takviminin bağlandığı birimdir (`ExamCalendar.semester`) ve mevzuat
pencereleri dönem sınırlarına kırpılır; yanlış kurulmuş dönem takvim penceresini
de kaydırır. Sabitlenen sözleşmeler:

- İki dönem ders yılının UÇLARINA yaslanır: 1. dönem yıl başlangıcında başlar,
  2. dönem yıl bitişinde biter — idareci yalnız aradaki iki tarihi verir.
- Yeniden yapılandırma mevcut iki satırı GÜNCELLER, üçüncü satır açmaz.
- Yarıyıl tatili hiçbir döneme ait değildir; dönem aranan tarih oraya düşerse
  sessizce komşu döneme yuvarlanmaz.
"""

from __future__ import annotations

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.okul.models import SchoolTerm, SchoolYear
from apps.okul.services import terms

pytestmark = pytest.mark.django_db

BIRINCI_BITIS = date(2027, 1, 15)
IKINCI_BASLANGIC = date(2027, 2, 1)


def _yil(name: str = "2026-2027", start: int = 2026) -> SchoolYear:
    yil: SchoolYear = SchoolYear.objects.create(
        name=name, start_date=date(start, 9, 1), end_date=date(start + 1, 6, 30)
    )
    return yil


def _donemli_yil() -> SchoolYear:
    yil = _yil()
    terms.configure_terms(yil, first_end=BIRINCI_BITIS, second_start=IKINCI_BASLANGIC)
    return yil


def test_donemler_ders_yilinin_uclarina_yaslanir() -> None:
    yil = _yil()

    donemler = terms.configure_terms(yil, first_end=BIRINCI_BITIS, second_start=IKINCI_BASLANGIC)

    assert [(d.sequence, d.start_date, d.end_date) for d in donemler] == [
        (1, yil.start_date, BIRINCI_BITIS),
        (2, IKINCI_BASLANGIC, yil.end_date),
    ]
    assert [d.name for d in donemler] == ["1. dönem", "2. dönem"]


def test_yeniden_yapilandirma_ayni_satirlari_gunceller() -> None:
    """Takvimler dönem satırına FK verir: yeniden kurulum satırı DEĞİŞTİRMEMELİ, güncellemeli."""
    yil = _donemli_yil()
    onceki = {d.sequence: d.pk for d in SchoolTerm.objects.filter(school_year=yil)}

    terms.configure_terms(yil, first_end=date(2027, 1, 22), second_start=date(2027, 2, 8))

    guncel = list(SchoolTerm.objects.filter(school_year=yil).order_by("sequence"))
    assert {d.sequence: d.pk for d in guncel} == onceki
    assert (guncel[0].end_date, guncel[1].start_date) == (date(2027, 1, 22), date(2027, 2, 8))


@pytest.mark.parametrize(
    ("first_end", "second_start", "beklenen"),
    [
        (date(2026, 8, 31), IKINCI_BASLANGIC, "ders yılı başlangıcından önce"),
        (BIRINCI_BITIS, date(2027, 7, 1), "ders yılı bitişinden sonra"),
        (BIRINCI_BITIS, BIRINCI_BITIS, "1. dönem bittikten sonra"),  # aynı gün de çakışmadır
        (IKINCI_BASLANGIC, BIRINCI_BITIS, "1. dönem bittikten sonra"),
    ],
)
def test_gecersiz_donem_tarihleri_turkce_gerekceyle_reddedilir(
    first_end: date, second_start: date, beklenen: str
) -> None:
    yil = _donemli_yil()

    with pytest.raises(ValueError, match=beklenen):
        terms.configure_terms(yil, first_end=first_end, second_start=second_start)

    # Ret hiçbir şey yazmaz: önceki geçerli kurulum yerinde durur.
    birinci = SchoolTerm.objects.get(school_year=yil, sequence=1)
    assert birinci.end_date == BIRINCI_BITIS


def test_sinir_gunleri_doneme_dahildir() -> None:
    """Dönemin ilk ve son günü o döneme aittir (uç günlere sınav konabilir)."""
    yil = _donemli_yil()

    def sira(gun: date) -> int | None:
        donem = terms.term_for_date(yil, gun)
        return donem.sequence if donem is not None else None

    assert sira(yil.start_date) == 1
    assert sira(BIRINCI_BITIS) == 1
    assert sira(IKINCI_BASLANGIC) == 2
    assert sira(yil.end_date) == 2


def test_yariyil_tatili_hicbir_doneme_ait_degildir() -> None:
    yil = _donemli_yil()

    assert terms.term_for_date(yil, date(2027, 1, 25)) is None
    with pytest.raises(ValueError, match="bir dönemine denk gelmiyor"):
        terms.require_term_for_date(yil, date(2027, 1, 25))


def test_donemi_kurulmamis_yilda_gerekce_kurulumu_gosterir() -> None:
    """İki hata AYRI söylenir: 'tarih dönem dışında' ile 'dönem hiç kurulmamış' aynı şey değil."""
    yil = _yil()

    with pytest.raises(ValueError, match="dönem tarihleri tanımlanmamış"):
        terms.require_term_for_date(yil, date(2026, 10, 1))


def test_donem_cozumu_baska_ders_yilina_tasmaz() -> None:
    """Aynı tarihi kapsayan BAŞKA yılın dönemi dönmez (yıl devri sonrası eski yıl durur)."""
    eski = _yil(name="2025-2026", start=2025)
    terms.configure_terms(eski, first_end=date(2026, 1, 16), second_start=date(2026, 2, 2))
    yeni = _donemli_yil()

    bulunan = terms.require_term_for_date(yeni, date(2026, 10, 1))

    assert bulunan.school_year_id == yeni.pk
    assert terms.term_for_date(eski, date(2026, 10, 1)) is None


# ---------------------------------------------------------------------------
# Uç sözleşmesi
# ---------------------------------------------------------------------------


def test_api_donem_listesi_kurulumdan_once_bos_sonra_iki_satir() -> None:
    yil = _yil()
    client = APIClient()
    url = f"/api/v1/school-years/{yil.pk}/terms/"

    assert client.get(url).json() == []

    client.put(
        url,
        {"first_term_end": "2027-01-15", "second_term_start": "2027-02-01"},
        format="json",
    )
    satirlar = client.get(url).json()
    assert [(s["sequence"], s["name"]) for s in satirlar] == [(1, "1. dönem"), (2, "2. dönem")]
    assert {s["school_year"] for s in satirlar} == {yil.pk}


def test_api_gecersiz_donem_tarihi_400_ve_gerekce_mesajda() -> None:
    """Servisin Türkçe gerekçesi snackbar'a (`message`) taşınır — 500 ya da genel cümle değil."""
    yil = _yil()

    yanit = APIClient().put(
        f"/api/v1/school-years/{yil.pk}/terms/",
        {"first_term_end": "2027-02-01", "second_term_start": "2027-01-15"},
        format="json",
    )

    assert yanit.status_code == 400
    assert yanit.json()["code"] == "validation_error"
    assert "1. dönem bittikten sonra" in yanit.json()["message"]
    assert not SchoolTerm.objects.filter(school_year=yil).exists()


def test_api_eksik_tarih_alan_hatasi_olarak_doner() -> None:
    yil = _yil()

    yanit = APIClient().put(
        f"/api/v1/school-years/{yil.pk}/terms/", {"first_term_end": "2027-01-15"}, format="json"
    )

    assert yanit.status_code == 400
    assert set(yanit.json()["fields"]) == {"second_term_start"}


def test_api_olmayan_ders_yili_404() -> None:
    client = APIClient()

    assert client.get("/api/v1/school-years/999999/terms/").status_code == 404
    yanit = client.put(
        "/api/v1/school-years/999999/terms/",
        {"first_term_end": "2027-01-15", "second_term_start": "2027-02-01"},
        format="json",
    )
    assert yanit.status_code == 404
    assert yanit.json()["message"] == "Kayıt bulunamadı."
