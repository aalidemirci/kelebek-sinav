"""`okul` salt-okunur sorguları — view'lar ORM'e buradan erişir (katman disiplini).

Arama Türkçe-katlamalı yapılır: `normalize_header` (Türkçe→ASCII küçük harf) iki
tarafı da katlar. Ad-soyad alanları ŞİFRELİ olduğundan (U3) ada dokunan her
arama/sıralama ZORUNLU olarak Python tarafındadır (TB3) — yeni ad sorgusu ORM
filtresiyle YAZILMAZ; yerel ölçek (≤1000 kayıt) bunu ucuzlatır. Okul no, sınıf
ve şube düz alanlardır; süzgeçleri DB tarafında kalır.
"""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet

from apps.okul import normalize
from apps.okul.excel_ogrenci import normalize_header
from apps.okul.models import (
    ClassSection,
    ImportRun,
    Personnel,
    SchoolConfig,
    SchoolTerm,
    SchoolYear,
    Student,
    StudentStatus,
)


def school_years() -> QuerySet[SchoolYear]:
    return SchoolYear.objects.all()


def active_school_year() -> SchoolYear | None:
    return SchoolYear.objects.filter(is_active=True).first()


def school_terms(*, school_year_id: int) -> QuerySet[SchoolTerm]:
    return SchoolTerm.objects.filter(school_year_id=school_year_id)


def grade_levels() -> list[dict[str, Any]]:
    """UI seçicileri için geçerli seviye listesi — okul türünden türetilir (U4)."""
    config = SchoolConfig.load()
    return [
        {"value": lvl, "label": "Hazırlık" if lvl == 0 else str(lvl)} for lvl in config.grade_levels
    ]


def grade_level_values() -> tuple[int, ...]:
    """Geçerli seviye değerleri (doğrulama için)."""
    return SchoolConfig.load().grade_levels


def personnel_list(
    *, search: str = "", only_active: bool = False
) -> list[Personnel] | QuerySet[Personnel]:
    """Personel listesi; ad sıralaması ve araması Python tarafında (şifreli ad)."""
    qs = Personnel.objects.all()
    if only_active:
        qs = qs.filter(is_active=True)
    if search.strip():
        needle = normalize_header(search)
        return [
            p
            for p in qs
            if needle in normalize_header(p.full_name)
            or needle in normalize_header(p.title)
            or needle in normalize_header(p.branch)
        ]
    return qs


def personnel_sorted(*, only_active: bool = False) -> list[Personnel]:
    """Ada göre TR-katlamalı sıralı personel (gözetmen listeleri, seçiciler)."""
    rows = list(
        Personnel.objects.filter(is_active=True) if only_active else Personnel.objects.all()
    )
    return sorted(rows, key=lambda p: normalize_header(p.full_name))


def class_sections(*, school_year_id: int | None = None) -> QuerySet[ClassSection]:
    """Şube kataloğu; yıl verilmezse aktif yıl kullanılır."""
    qs = ClassSection.objects.select_related("school_year")
    if school_year_id is not None:
        return qs.filter(school_year_id=school_year_id)
    active = active_school_year()
    if active is None:
        return qs.none()
    return qs.filter(school_year=active)


def get_class_section(section_id: int) -> ClassSection | None:
    return ClassSection.objects.filter(pk=section_id).first()


def student_list(
    *,
    class_level: int | None = None,
    class_section: str = "",
    search: str = "",
    only_active: bool = False,
) -> list[Student] | QuerySet[Student]:
    """Öğrenci listesi. `only_active` VARSAYILAN OLARAK KAPALIDIR.

    Sicil ekranı ayrılmış öğrenciyi de göstermek zorundadır (geçmiş oturumların
    öğrencisi kaybolmasın); süzgeci yalnız YENİ kayıt bağlayan seçiciler
    (autocomplete) açar.
    """
    qs = Student.objects.all()
    if only_active:
        qs = qs.filter(status=StudentStatus.ACTIVE)
    if class_level is not None:
        qs = qs.filter(class_level=class_level)
    if class_section.strip():
        # Kayıtlar import/serializer'da _ascii_upper ile katlanır ('ş' → 'S');
        # filtre de AYNI katlamadan geçmeli, yoksa Türkçe harfli şube bulunamaz.
        qs = qs.filter(class_section=normalize._ascii_upper(class_section.strip()))
    if search.strip():
        needle = normalize_header(search)
        return [
            s
            for s in qs
            if needle in normalize_header(s.full_name)
            or needle in normalize_header(s.student_number)
        ]
    return qs


def get_student(student_id: int) -> Student | None:
    """Tek öğrenci (canlı) — yoksa None. Sınav modülünün okuma kanalı."""
    return Student.objects.filter(pk=student_id).first()


def find_student_by_number(student_number: str) -> Student | None:
    """Okul numarasıyla AKTİF canlı öğrenci arar (upsert eşleştirme kanalı).

    Okul no DÜZ alandır — DB filtresi şifreli kipte de çalışır (DD'deki TCKN
    Python-dolambacı burada gerekmez; tasarım §6).
    """
    aranan = (student_number or "").strip()
    if not aranan:
        return None
    return Student.objects.filter(student_number=aranan, status=StudentStatus.ACTIVE).first()


def get_personnel(personnel_id: int) -> Personnel | None:
    """Tek personel (canlı) — yoksa None."""
    return Personnel.objects.filter(pk=personnel_id).first()


def get_school_year(school_year_id: int) -> SchoolYear | None:
    """Tek ders yılı (canlı) — yoksa None."""
    return SchoolYear.objects.filter(pk=school_year_id).first()


def students_all() -> QuerySet[Student]:
    return Student.objects.all()


def import_runs(*, source_type: str = "") -> QuerySet[ImportRun]:
    qs = ImportRun.objects.all()
    if source_type:
        qs = qs.filter(source_type=source_type)
    return qs


def setup_status() -> dict[str, Any]:
    """Kurulum sihirbazı durum özeti (FE açılış yönlendirmesi bundan okur)."""
    config = SchoolConfig.load()
    return {
        "setup_completed": config.setup_completed,
        "school_name": config.school_name,
        "has_active_school_year": active_school_year() is not None,
        "student_count": Student.objects.count(),
        "personnel_count": Personnel.objects.count(),
        "class_section_count": class_sections().count(),
    }


def distinct_class_levels() -> list[int]:
    """Sicilde fiilen kayıtlı sınıf seviyeleri (artan, tekilleştirilmiş)."""
    values = Student.objects.exclude(class_level=None).values_list("class_level", flat=True)
    return sorted({int(v) for v in values})
