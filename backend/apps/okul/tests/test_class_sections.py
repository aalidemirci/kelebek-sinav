"""Şube kataloğu (ClassSection) — elle ekleme/silme ucu ve doğrulamaları.

Şube kataloğu çoğunlukla içe aktarmayla tohumlanır (`test_imports.py`); burada
ELLE ekleme yolu sabitlenir. Salon-şube eşlemesi, takvim kapsamı ve şube
yoklaması bu kataloğa bağlandığı için üç kural kritiktir:

- Şube harfi içe aktarmayla AYNI katlamadan geçer (Türkçe büyük harf; ASCII'ye
  katlanmaz) — 10/I ile 10/İ ayrı şubelerdir ve liste Türk alfabesiyle sıralanır.
- Teklik (ders yılı, seviye, şube) üzerindendir ve yalnız CANLI kayıtları sayar:
  aynı şube başka yılda açılabilir, silinen şube yeniden eklenebilir.
- Liste varsayılan olarak AKTİF ders yılını gösterir (eski yılın şubeleri seçicilere
  karışmaz).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.okul.models import ClassSection, SchoolYear

pytestmark = pytest.mark.django_db

URL = "/api/v1/class-sections/"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _yil(name: str = "2026-2027", start: int = 2026, *, aktif: bool = True) -> SchoolYear:
    yil: SchoolYear = SchoolYear.objects.create(
        name=name,
        start_date=date(start, 9, 1),
        end_date=date(start + 1, 6, 30),
        is_active=aktif,
    )
    return yil


def _ekle(client: APIClient, yil: SchoolYear, level: int, harf: str) -> Any:
    return client.post(
        URL, {"school_year": yil.pk, "class_level": level, "class_section": harf}, format="json"
    )


def _etiketler(yanit: Any) -> list[str]:
    veri = yanit.json()
    satirlar = veri["results"] if isinstance(veri, dict) else veri
    return [s["class_label"] for s in satirlar]


def test_sube_harfi_turkce_buyutulur_ve_etiketler_cozulur(client: APIClient) -> None:
    yil = _yil()

    yanit = _ekle(client, yil, 10, " ş ")

    assert yanit.status_code == 201
    veri = yanit.json()
    assert veri["class_section"] == "Ş"
    assert veri["class_label"] == "10/Ş"
    assert veri["school_year_name"] == "2026-2027"
    assert (veri["group"], veri["group_name"]) == (None, "")


def test_i_ve_noktali_i_ayri_subelerdir(client: APIClient) -> None:
    """e-Okul şubeleri Türk alfabesiyle açar (…H, I, İ, J…): iki harf TEK şubeye çökmemeli."""
    yil = _yil()

    assert _ekle(client, yil, 10, "ı").status_code == 201  # → 'I'
    assert _ekle(client, yil, 10, "i").status_code == 201  # → 'İ'

    assert set(
        ClassSection.objects.filter(class_level=10).values_list("class_section", flat=True)
    ) == {"I", "İ"}


def test_ayni_yilda_ayni_sube_ikinci_kez_eklenemez(client: APIClient) -> None:
    """Mükerrer denetimi KATLAMADAN SONRA yapılır: 'a' ile 'A' aynı şubedir."""
    yil = _yil()
    assert _ekle(client, yil, 9, "A").status_code == 201

    tekrar = _ekle(client, yil, 9, "a")

    assert tekrar.status_code == 400
    assert "zaten kayıtlı" in str(tekrar.json()["fields"]["class_section"])
    assert ClassSection.objects.filter(class_level=9, class_section="A").count() == 1


def test_ayni_sube_baska_ders_yilinda_acilabilir(client: APIClient) -> None:
    """Şube yıla bağlıdır: 9/A her yıl yeniden açılır."""
    eski = _yil(name="2025-2026", start=2025, aktif=False)
    yeni = _yil()

    assert _ekle(client, eski, 9, "A").status_code == 201
    assert _ekle(client, yeni, 9, "A").status_code == 201


def test_silinen_sube_yeniden_eklenebilir(client: APIClient) -> None:
    """Silme soft'tur ve teklik yalnız canlı kayıtları sayar."""
    yil = _yil()
    ilk_id = _ekle(client, yil, 9, "A").json()["id"]

    assert client.delete(f"{URL}{ilk_id}/").status_code == 204
    assert not ClassSection.objects.filter(pk=ilk_id).exists()
    assert ClassSection.all_objects.filter(pk=ilk_id).exists()

    yeniden = _ekle(client, yil, 9, "A")
    assert yeniden.status_code == 201 and yeniden.json()["id"] != ilk_id


def test_seviye_okul_turunun_kumesine_karsi_dogrulanir(client: APIClient) -> None:
    yil = _yil()

    yanit = _ekle(client, yil, 8, "A")

    assert yanit.status_code == 400
    assert "9, 10, 11, 12" in str(yanit.json()["fields"]["class_level"])


def test_liste_seviye_sonra_turk_alfabesiyle_siralanir(client: APIClient) -> None:
    """SQLite sıralaması BINARY'dir (Ç/İ/Ş 'Z'den sonra düşer) — liste Python'da sıralanır."""
    yil = _yil()
    for level, harf in ((10, "Z"), (10, "Ç"), (10, "İ"), (10, "I"), (10, "C"), (9, "Ş"), (9, "S")):
        ClassSection.objects.create(school_year=yil, class_level=level, class_section=harf)

    assert _etiketler(client.get(URL)) == [
        "9/S",
        "9/Ş",
        "10/C",
        "10/Ç",
        "10/I",
        "10/İ",
        "10/Z",
    ]


def test_liste_varsayilan_olarak_aktif_yili_gosterir(client: APIClient) -> None:
    eski = _yil(name="2025-2026", start=2025, aktif=False)
    yeni = _yil()
    ClassSection.objects.create(school_year=eski, class_level=12, class_section="A")
    ClassSection.objects.create(school_year=yeni, class_level=9, class_section="A")

    assert _etiketler(client.get(URL)) == ["9/A"]
    assert _etiketler(client.get(URL, {"school_year": str(eski.pk)})) == ["12/A"]


def test_aktif_yil_yokken_liste_bostur(client: APIClient) -> None:
    """Kurulum sihirbazı ders yılı açılmadan bu ucu çağırabilir — hata değil boş liste."""
    pasif = _yil(aktif=False)
    ClassSection.objects.create(school_year=pasif, class_level=9, class_section="A")

    yanit = client.get(URL)

    assert yanit.status_code == 200
    assert _etiketler(yanit) == []


def test_sayisal_olmayan_ders_yili_suzgeci_400(client: APIClient) -> None:
    yanit = client.get(URL, {"school_year": "bu-yil"})

    assert yanit.status_code == 400
    assert "sayısal" in str(yanit.json()["fields"]["school_year"])


def test_olmayan_sube_silinemez_404(client: APIClient) -> None:
    yanit = client.delete(f"{URL}999999/")

    assert yanit.status_code == 404
    assert yanit.json()["message"] == "Kayıt bulunamadı."
