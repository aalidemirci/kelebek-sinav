"""Seçmeli dersin şube kapsamı (03.09.2026) — kapsamın TEK KAYNAĞI ders havuzu.

Kapsam neden burada yaşıyor: idareci "bu seçmeliyi hangi şubeler alıyor"u bir
kez girer, dört sınav takvimi de aynı bilgiyi kullanır. Takvim girdisi kendi
kopyasını tutmaya devam eder (snapshot) — o tarafın testleri
`apps/sinav/tests/test_calendar.py` içindedir.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.dersler import selectors, services
from apps.dersler.models import Course, CourseSectionOffering, CourseType
from apps.okul.models import ClassSection, SchoolYear
from apps.okul.services import sections as sections_service

pytestmark = pytest.mark.django_db


def _yil() -> SchoolYear:
    yil: SchoolYear = SchoolYear.objects.create(
        name="2026-2027",
        start_date="2026-09-01",
        end_date="2027-06-30",
        is_active=True,
    )
    return yil


def _sube(yil: SchoolYear, level: int, ad: str) -> ClassSection:
    sube: ClassSection = ClassSection.objects.create(
        school_year=yil, class_level=level, class_section=ad
    )
    return sube


def _secmeli(ad: str = "Almanca", levels: list[int] | None = None) -> Course:
    ders: Course = Course.objects.create(
        name=ad, levels=levels or [9], course_type=CourseType.ELECTIVE
    )
    return ders


def test_kapsam_seviye_seviye_yazilir_ve_okunur() -> None:
    yil = _yil()
    a, b = _sube(yil, 9, "A"), _sube(yil, 9, "B")
    c = _sube(yil, 10, "C")
    ders = _secmeli(levels=[9, 10])

    services.set_course_sections(
        course_id=ders.pk,
        school_year_id=yil.pk,
        offerings=[
            {"level": 9, "section_ids": [a.pk, b.pk]},
            {"level": 10, "section_ids": [c.pk]},
        ],
    )

    harita = selectors.course_section_map(yil.pk)
    assert harita[(ders.pk, 9)] == [a.pk, b.pk]
    assert harita[(ders.pk, 10)] == [c.pk]


def test_kaydetme_tam_degistirmedir() -> None:
    """Gönderilmeyen seviye SİLİNİR — diyalog dersin tüm seviyelerini gösterir."""
    yil = _yil()
    a = _sube(yil, 9, "A")
    c = _sube(yil, 10, "C")
    ders = _secmeli(levels=[9, 10])
    services.set_course_sections(
        course_id=ders.pk,
        school_year_id=yil.pk,
        offerings=[{"level": 9, "section_ids": [a.pk]}, {"level": 10, "section_ids": [c.pk]}],
    )

    services.set_course_sections(
        course_id=ders.pk, school_year_id=yil.pk, offerings=[{"level": 9, "section_ids": [a.pk]}]
    )

    assert selectors.course_section_map(yil.pk) == {(ders.pk, 9): [a.pk]}


def test_bos_liste_kaydi_siler() -> None:
    yil = _yil()
    a = _sube(yil, 9, "A")
    ders = _secmeli()
    services.set_course_sections(
        course_id=ders.pk, school_year_id=yil.pk, offerings=[{"level": 9, "section_ids": [a.pk]}]
    )

    services.set_course_sections(
        course_id=ders.pk, school_year_id=yil.pk, offerings=[{"level": 9, "section_ids": []}]
    )

    assert selectors.course_section_map(yil.pk) == {}
    assert not CourseSectionOffering.objects.filter(course=ders).exists()


def test_zorunlu_derse_kapsam_yazilamaz() -> None:
    """Zorunlu ders seviyenin tamamında okutulur; kapsam yalnız seçmelide anlamlı."""
    yil = _yil()
    a = _sube(yil, 9, "A")
    zorunlu = Course.objects.create(name="Matematik", levels=[9], course_type=CourseType.COMMON)

    with pytest.raises(ValidationError, match="yalnız seçmeli"):
        services.set_course_sections(
            course_id=zorunlu.pk,
            school_year_id=yil.pk,
            offerings=[{"level": 9, "section_ids": [a.pk]}],
        )


def test_baska_seviyenin_subesi_reddedilir() -> None:
    yil = _yil()
    c = _sube(yil, 10, "C")
    ders = _secmeli(levels=[9, 10])

    with pytest.raises(ValidationError, match="seviyeye ait değil"):
        services.set_course_sections(
            course_id=ders.pk,
            school_year_id=yil.pk,
            offerings=[{"level": 9, "section_ids": [c.pk]}],
        )


def test_silinmis_sube_okuma_aninda_duser() -> None:
    """JSON listede FK koruması yok: canlılık okurken süzülür (takvimle aynı kalıp)."""
    yil = _yil()
    a, b = _sube(yil, 9, "A"), _sube(yil, 9, "B")
    ders = _secmeli()
    services.set_course_sections(
        course_id=ders.pk,
        school_year_id=yil.pk,
        offerings=[{"level": 9, "section_ids": [a.pk, b.pk]}],
    )

    sections_service.delete_class_section(ClassSection.objects.get(pk=b.pk))

    assert selectors.course_section_map(yil.pk) == {(ders.pk, 9): [a.pk]}


def test_kapsam_ders_yilina_baglidir() -> None:
    """Şube yıla ait: başka yılın haritası bu yılın kapsamını göstermez."""
    yil = _yil()
    a = _sube(yil, 9, "A")
    diger = SchoolYear.objects.create(
        name="2027-2028", start_date="2027-09-01", end_date="2028-06-30"
    )
    ders = _secmeli()
    services.set_course_sections(
        course_id=ders.pk, school_year_id=yil.pk, offerings=[{"level": 9, "section_ids": [a.pk]}]
    )

    assert selectors.course_section_map(diger.pk) == {}


def test_api_kapsam_yazma_okuma() -> None:
    yil = _yil()
    a, b = _sube(yil, 9, "A"), _sube(yil, 9, "B")
    ders = _secmeli()
    client = APIClient()

    yaz = client.put(
        f"/api/v1/courses/{ders.pk}/sections/",
        {"offerings": [{"level": 9, "section_ids": [a.pk, b.pk]}]},
        format="json",
    )
    assert yaz.status_code == 200
    assert yaz.data["offerings"] == [{"level": 9, "section_ids": [a.pk, b.pk]}]

    oku = client.get(f"/api/v1/courses/{ders.pk}/sections/")
    assert oku.status_code == 200 and oku.data["offerings"][0]["section_ids"] == [a.pk, b.pk]

    liste = client.get("/api/v1/courses/section-offerings/")
    assert liste.status_code == 200
    assert liste.data["results"] == [{"course": ders.pk, "level": 9, "section_ids": [a.pk, b.pk]}]


def test_api_aktif_yil_yoksa_turkce_hata() -> None:
    """Aktif yıl yoksa uç 400 döner — sayfa sütunu boş kalır, çökmez."""
    ders = _secmeli()

    yanit = APIClient().get(f"/api/v1/courses/{ders.pk}/sections/")

    assert yanit.status_code == 400
    assert "Aktif ders yılı yok" in str(yanit.data)
