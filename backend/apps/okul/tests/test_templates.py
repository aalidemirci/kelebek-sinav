"""İndirilebilir içe aktarma şablonları (tasarım §4.7/2) — gidiş-dönüş sözleşmesi.

Şablonun var olma nedeni TEKTİR: idareci doldurur ve AYNI içe aktarma ucuna
yükler; "ayrı bir şablon kod yolu" YOKTUR. Bu yüzden asıl sabitlenen davranış
başlık metni değil GİDİŞ-DÖNÜŞTÜR — şablon başlıkları parser sinonimlerinden
koparsa program kendi verdiği dosyayı geri okuyamaz ve hata kullanıcıya
"zorunlu sütun bulunamadı" diye yansır.

Örnek satırlar uydurmadır (KVKK): şablon depoya ve dağıtım paketine girer.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import cast

import pytest
from django.http import StreamingHttpResponse
from rest_framework.test import APIClient

from apps.okul import excel_ogrenci
from apps.okul.models import ClassSection, Personnel, SchoolYear, Student
from apps.okul.services import imports as import_service
from apps.okul.services import templates as template_service

XLSX_TURU = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _dolu_satirlar(xlsx: bytes) -> list[list[str]]:
    """Şablonu İÇE AKTARMANIN KENDİ okuyucusuyla açar (boş satırlar elenir)."""
    satirlar = excel_ogrenci.read_sheet(xlsx)
    return [
        [str(hucre) for hucre in satir]
        for satir in satirlar
        if any(str(hucre or "").strip() for hucre in satir)
    ]


def _govde(yanit: object) -> bytes:
    assert isinstance(yanit, StreamingHttpResponse)
    return b"".join(cast(Iterable[bytes], yanit.streaming_content))


def test_ogrenci_sablonu_baslik_satiri_ve_tek_ornek_satir_tasir() -> None:
    """Şablon = başlık + TEK örnek satır; idareci örneği silip kendi listesini yazar."""
    satirlar = _dolu_satirlar(template_service.student_template_xlsx())

    assert satirlar[0] == list(template_service.STUDENT_TEMPLATE_HEADERS)
    assert len(satirlar) == 2
    # Örnek satır yer tutucudur — gerçek bir kişiye benzeyen ad taşımaz (KVKK).
    assert satirlar[1] == ["9/A", "1001", "ÖRNEK", "ÖĞRENCİ"]


def test_personel_sablonu_baslik_satiri_ve_tek_ornek_satir_tasir() -> None:
    satirlar = _dolu_satirlar(template_service.personnel_template_xlsx())

    assert satirlar[0] == list(template_service.PERSONNEL_TEMPLATE_HEADERS)
    assert len(satirlar) == 2
    assert satirlar[1][:2] == ["ÖRNEK", "ÖĞRETMEN"]


@pytest.mark.django_db
def test_ogrenci_sablonu_ice_aktarma_ucundan_oldugu_gibi_gecer() -> None:
    """Gidiş-dönüş: indirilen şablon HİÇ dokunulmadan aynı uca yüklenebilir.

    Ayrı şablon kod yolu yoktur — başlıklar parser sinonimleriyle tanınır.
    Başlıklardan biri sinonim listesinden koparsa bu test "zorunlu sütun
    bulunamadı" ile düşer.
    """
    SchoolYear.objects.create(
        name="2026-2027", start_date=date(2026, 9, 1), end_date=date(2027, 6, 30), is_active=True
    )

    rapor = import_service.commit_students_file(
        file_bytes=template_service.student_template_xlsx(), file_name="sablon-ogrenci.xlsx"
    )

    assert rapor.skipped == []
    assert (rapor.total_rows, rapor.processed, rapor.created_students) == (1, 1, 1)
    ogrenci = Student.objects.get(student_number="1001")
    assert (ogrenci.first_name, ogrenci.last_name) == ("ÖRNEK", "ÖĞRENCİ")
    assert ogrenci.class_label == "9/A"
    # Şube kataloğu da tohumlanır: şablon yolu import yolunun TAMAMINI kullanır.
    assert ClassSection.objects.filter(class_level=9, class_section="A").exists()


@pytest.mark.django_db
def test_personel_sablonu_ice_aktarma_ucundan_oldugu_gibi_gecer() -> None:
    """Ayrı 'Adı' / 'Soyadı' sütunları + 'Görevi' / 'Branşı' sinonimleri tanınır."""
    rapor = import_service.commit_personnel_file(
        file_bytes=template_service.personnel_template_xlsx(), file_name="sablon-personel.xlsx"
    )

    assert rapor.skipped == []
    assert (rapor.total_rows, rapor.processed, rapor.created_personnel) == (1, 1, 1)
    kisi = Personnel.objects.get()
    assert kisi.full_name == "ÖRNEK ÖĞRETMEN"
    assert (kisi.title, kisi.branch) == ("Öğretmen", "Matematik")


@pytest.mark.parametrize(
    ("yol", "dosya_adi", "basliklar"),
    [
        (
            "/api/v1/templates/students/",
            "sablon-ogrenci.xlsx",
            template_service.STUDENT_TEMPLATE_HEADERS,
        ),
        (
            "/api/v1/templates/personnel/",
            "sablon-personel.xlsx",
            template_service.PERSONNEL_TEMPLATE_HEADERS,
        ),
    ],
)
@pytest.mark.django_db
def test_sablon_indirme_ucu_excel_eki_dondurur(
    yol: str, dosya_adi: str, basliklar: tuple[str, ...]
) -> None:
    """Uç sözleşmesi: tarayıcı/WebView dosyayı EK olarak ve .xlsx adıyla indirir.

    Veritabanına dokunmaz (kurulumdan önce, boş programda da indirilebilmeli).
    """
    yanit = APIClient().get(yol)

    assert yanit.status_code == 200
    assert yanit["Content-Type"] == XLSX_TURU
    assert "attachment" in yanit["Content-Disposition"]
    assert dosya_adi in yanit["Content-Disposition"]
    assert _dolu_satirlar(_govde(yanit))[0] == list(basliklar)
