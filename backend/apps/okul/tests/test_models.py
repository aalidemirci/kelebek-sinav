"""`okul` modelleri — kısıtlar, singleton, seviye türetimi (KS uyarlaması).

DD test kalıbından uyarlandı: TCKN/veli/tatil testleri kalktı; okul türünden
seviye türetimi (U4), okul-no upsert kısıtı ve şube kataloğu eklendi.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.db import IntegrityError

from apps.okul.models import (
    ClassSection,
    SchoolConfig,
    SchoolType,
    SchoolYear,
    Student,
    StudentStatus,
    grade_levels_for,
)


@pytest.mark.django_db
class TestSchoolConfig:
    def test_load_kayit_yokken_kaydedilmemis_varsayilan_doner(self) -> None:
        config = SchoolConfig.load()
        assert config.pk is None
        assert config.setup_completed is False
        assert SchoolConfig.objects.count() == 0  # okuma yazmaz

    def test_load_mevcut_sati̇ri_doner(self) -> None:
        SchoolConfig.objects.create(pk=SchoolConfig.SINGLETON_PK, school_name="Örnek AL")
        assert SchoolConfig.load().school_name == "Örnek AL"


class TestGradeLevels:
    def test_anadolu_lisesi_varsayilan_9_12(self) -> None:
        assert grade_levels_for(SchoolType.ANADOLU_LISESI, has_prep_class=False) == (9, 10, 11, 12)

    def test_hazirlik_bayragi_sifir_seviyesini_ekler(self) -> None:
        assert grade_levels_for(SchoolType.ANADOLU_LISESI, has_prep_class=True) == (
            0,
            9,
            10,
            11,
            12,
        )

    def test_bilinmeyen_tur_anadolu_lisesine_duser(self) -> None:
        """Veri dosyası eklenmeden tür seçilirse program kırılmaz (konservatif düşüş)."""
        assert grade_levels_for("BILINMEYEN", has_prep_class=False) == (9, 10, 11, 12)


@pytest.mark.django_db
class TestSchoolYear:
    def test_ayni_ad_canli_kayitta_tekil(self) -> None:
        SchoolYear.objects.create(
            name="2026-2027", start_date=date(2026, 9, 1), end_date=date(2027, 6, 30)
        )
        with pytest.raises(IntegrityError):
            SchoolYear.objects.create(
                name="2026-2027", start_date=date(2026, 9, 1), end_date=date(2027, 6, 30)
            )

    def test_silinen_yilin_adi_yeniden_kullanilabilir(self) -> None:
        yil = SchoolYear.objects.create(
            name="2026-2027", start_date=date(2026, 9, 1), end_date=date(2027, 6, 30)
        )
        yil.delete()  # soft delete
        SchoolYear.objects.create(
            name="2026-2027", start_date=date(2026, 9, 1), end_date=date(2027, 6, 30)
        )

    def test_tek_aktif_yil_kisiti(self) -> None:
        SchoolYear.objects.create(
            name="2025-2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 6, 30),
            is_active=True,
        )
        with pytest.raises(IntegrityError):
            SchoolYear.objects.create(
                name="2026-2027",
                start_date=date(2026, 9, 1),
                end_date=date(2027, 6, 30),
                is_active=True,
            )


@pytest.mark.django_db
class TestStudent:
    def test_ayni_okul_no_aktif_canli_kayitta_tekil(self) -> None:
        Student.objects.create(first_name="A", last_name="B", student_number="101")
        with pytest.raises(IntegrityError):
            Student.objects.create(first_name="C", last_name="D", student_number="101")

    def test_ayrilan_ogrencinin_numarasi_yeniden_verilebilir(self) -> None:
        eski = Student.objects.create(first_name="A", last_name="B", student_number="101")
        eski.status = StudentStatus.LEFT
        eski.save(update_fields=["status"])
        Student.objects.create(first_name="C", last_name="D", student_number="101")

    def test_numarasiz_kayitlar_kisit_disi(self) -> None:
        Student.objects.create(first_name="A", last_name="B")
        Student.objects.create(first_name="C", last_name="D")  # patlamaz

    def test_class_label_bicimleri(self) -> None:
        assert (
            Student(first_name="A", last_name="B", class_level=10, class_section="A").class_label
            == "10/A"
        )
        assert (
            Student(first_name="A", last_name="B", class_level=0, class_section="B").class_label
            == "Hz/B"
        )
        assert Student(first_name="A", last_name="B").class_label == ""

    def test_full_name(self) -> None:
        assert Student(first_name="EMRE CAN", last_name="YILMAZ").full_name == "EMRE CAN YILMAZ"


@pytest.mark.django_db
class TestClassSection:
    def test_ayni_yil_ve_sube_tekil(self) -> None:
        yil = SchoolYear.objects.create(
            name="2026-2027", start_date=date(2026, 9, 1), end_date=date(2027, 6, 30)
        )
        ClassSection.objects.create(school_year=yil, class_level=10, class_section="A")
        with pytest.raises(IntegrityError):
            ClassSection.objects.create(school_year=yil, class_level=10, class_section="A")

    def test_hazirlik_etiketi(self) -> None:
        yil = SchoolYear.objects.create(
            name="2026-2027", start_date=date(2026, 9, 1), end_date=date(2027, 6, 30)
        )
        sube = ClassSection.objects.create(school_year=yil, class_level=0, class_section="A")
        assert sube.class_label == "Hz/A"
