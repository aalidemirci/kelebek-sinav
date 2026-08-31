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
    SubjectDepartment,
)


def school_years() -> QuerySet[SchoolYear]:
    return SchoolYear.objects.all()


def active_school_year() -> SchoolYear | None:
    return SchoolYear.objects.filter(is_active=True).first()


def school_terms(*, school_year_id: int) -> QuerySet[SchoolTerm]:
    return SchoolTerm.objects.filter(school_year_id=school_year_id)


def get_school_term(term_id: int) -> SchoolTerm | None:
    """Tek dönem (canlı) — yoksa None. Sınav modülünün dönem köprüsü."""
    return SchoolTerm.objects.filter(pk=term_id).select_related("school_year").first()


def active_student_counts_by_level() -> dict[int, int]:
    """Seviye başına AKTİF öğrenci sayısı (sınav Adım 0 ön kontrol verisi; PII yok)."""
    counts: dict[int, int] = {}
    qs = (
        Student.objects.filter(status=StudentStatus.ACTIVE)
        .exclude(class_level=None)
        .values_list("class_level", flat=True)
    )
    for level in qs:
        counts[int(level)] = counts.get(int(level), 0) + 1
    return dict(sorted(counts.items()))


def last_student_import() -> ImportRun | None:
    """Son TAMAMLANMIŞ öğrenci içe aktarması (Adım 0: 'liste ne kadar taze?')."""
    return ImportRun.objects.filter(source_type="STUDENTS", status="COMPLETED").first()


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


def class_sections_sorted(*, school_year_id: int | None = None) -> list[ClassSection]:
    """Şube kataloğu, TÜRK ALFABESİ sırasıyla (listeleme/görüntü için).

    `ClassSection.Meta.ordering` DB sıralamasıdır ve SQLite karşılaştırması
    BINARY'dir (UTF-8 bayt = kod noktası sırası). Şube harfi artık ASCII'ye
    KATLANMADIĞI için orada 'Ç/Ğ/İ/Ö/Ş/Ü' harfleri 'Z'den sonraya düşer —
    10/I ile 10/İ listenin iki ucuna ayrılırdı. Sıralama bu yüzden Python'da,
    `normalize.tr_sort_key` ile yapılır (yerel ölçek: ~50 şube).
    """
    return sorted(
        class_sections(school_year_id=school_year_id),
        key=lambda s: (s.class_level, normalize.tr_sort_key(s.class_section)),
    )


def get_class_section(section_id: int) -> ClassSection | None:
    return ClassSection.objects.filter(pk=section_id).first()


def subject_departments(*, board_only: bool = False) -> QuerySet[SubjectDepartment]:
    """Zümre kataloğu (başkan bağıyla)."""
    qs = SubjectDepartment.objects.select_related("head")
    if board_only:
        qs = qs.filter(is_board_member=True)
    return qs


def subject_departments_sorted(*, board_only: bool = False) -> list[SubjectDepartment]:
    """Zümre kataloğu, TÜRK ALFABESİ sırasıyla (liste ekranı + imza bloğu).

    `Meta.ordering` pk'dir; zümre adı düz metin olsa da SQLite karşılaştırması
    BINARY'dir (Ç/Ğ/İ/Ö/Ş/Ü kod noktası olarak Z'den sonra) — sıralama bu yüzden
    Python'da, `normalize.tr_sort_key` ile (ClassSection emsali).
    """
    return sorted(
        subject_departments(board_only=board_only),
        key=lambda d: normalize.tr_sort_key(d.name),
    )


def get_subject_department(department_id: int) -> SubjectDepartment | None:
    return SubjectDepartment.objects.filter(pk=department_id).first()


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
        # Kayıtlar import/serializer'da tr_upper ile büyütülür ('ş' → 'Ş');
        # filtre de AYNI katlamadan geçmeli, yoksa Türkçe harfli şube bulunamaz.
        qs = qs.filter(class_section=normalize.tr_upper(class_section.strip()))
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
