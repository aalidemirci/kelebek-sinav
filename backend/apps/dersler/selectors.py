"""Ders havuzu salt-okunur sorguları.

SQLite'ta JSONField `levels__contains` YOKTUR (K11) — seviye süzgeci Python
tarafında yapılır (`courses_for_level`); ~60 derslik katalogda maliyet yok.
Ad süzgeci (`q`) SQL `icontains` + Python TR-katlamalı süzgecin birleşimidir:
SQLite yalnız ASCII'de harf-duyarsızdır, 'matematik' araması 'MATEMATİK'
kaydını tek başına SQL ile bulamazdı.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from django.db.models import QuerySet

from apps.dersler.models import Course, CourseAlias, CourseSource
from apps.dersler.text import canon_course_key, course_match_key


def courses(
    *,
    course_type: str | None = None,
    include_inactive: bool = False,
) -> QuerySet[Course]:
    """Ders kataloğu (ad sıralı). Varsayılan yalnız aktif dersler."""
    qs = Course.objects.all()
    if not include_inactive:
        qs = qs.filter(is_active=True)
    if course_type:
        qs = qs.filter(course_type=course_type)
    return qs.order_by("name")


def courses_sorted(
    *,
    course_type: str | None = None,
    include_inactive: bool = False,
) -> list[Course]:
    """Ders kataloğu, TÜRK ALFABESİ sırasıyla (kullanıcıya gösterilen listeler).

    `courses()` DB `order_by("name")` kullanır ve SQLite karşılaştırması
    BINARY'dir: 'Çağdaş…', 'İklim…', 'Ölçme…' gibi adlar Z'den SONRAYA düşer.
    Emsal `okul.selectors.class_sections_sorted`/`subject_departments_sorted`
    (CLAUDE.md §2). Katalog ~60 satır — Python tarafı maliyetsiz.
    """
    from apps.okul import normalize

    return sorted(
        courses(course_type=course_type, include_inactive=include_inactive),
        key=lambda c: normalize.tr_sort_key(c.name),
    )


def courses_for_level(
    level: int,
    *,
    course_type: str | None = None,
    include_inactive: bool = False,
) -> list[Course]:
    """Seviyeye uygun dersler — Python süzme (K11: SQLite'ta jsonb @> yok)."""
    return [
        c
        for c in courses(course_type=course_type, include_inactive=include_inactive)
        if level in {int(lvl) for lvl in (c.levels or [])}
    ]


def search_courses(rows: QuerySet[Course] | list[Course], q: str) -> list[Course]:
    """TR-katlamalı ad araması (küçük katalog — Python tarafı)."""
    needle = course_match_key(q)
    if not needle:
        return list(rows)
    return [c for c in rows if needle in course_match_key(c.name)]


def get_course(course_id: int, *, active_only: bool = True) -> Course | None:
    qs = Course.objects.filter(pk=course_id)
    if active_only:
        qs = qs.filter(is_active=True)
    return qs.first()


def course_names_by_ids(course_ids: set[int]) -> dict[int, str]:
    """id → ad eşlemesi (çakışma grubu etiketleri; pasif/silinmiş de çözülür).

    Çakışma grubu anahtarı geçmiş oturumlardan gelebilir — ders sonradan
    pasifleşmiş olsa da etiket üretilmelidir (all_objects).
    """
    rows = Course.all_objects.filter(pk__in=course_ids).values_list("pk", "name")
    return {int(pk): name for pk, name in rows}


def course_by_name(name: str) -> Course | None:
    """Canlı kayıtta ada göre ders (yoksa None)."""
    return Course.objects.filter(name=" ".join(name.split())).first()


def course_by_normalized_name(name: str) -> Course | None:
    """Canlı kayıtta normalize (TR-duyarsız + şapka) ada göre ders (yoksa None)."""
    key = course_match_key(name)
    if not key:
        return None
    # SoftDeleteManager Any döndürür (shared.models) — somut tip bildirilir.
    adaylar: list[Course] = list(Course.objects.all())
    for course in adaylar:
        if course_match_key(course.name) == key:
            return course
    return None


def meb_course_by_normalized_name(name: str) -> Course | None:
    """Normalize edilmiş ada göre MEB kataloğu dersi (yoksa None)."""
    key = course_match_key(name)
    if not key:
        return None
    adaylar: list[Course] = list(Course.objects.filter(source=CourseSource.MEB_CATALOG))
    for course in adaylar:
        if course_match_key(course.name) == key:
            return course
    return None


def course_by_alias(name: str) -> Course | None:
    """Takma ad tablosundan kanonik ders; hedef silinmiş/pasifse None."""
    key = course_match_key(name)
    if not key:
        return None
    alias = CourseAlias.objects.filter(alias_key=key).select_related("course").first()
    if alias is None:
        return None
    course: Course = alias.course
    if course.deleted_at is not None or not course.is_active:
        return None
    return course


def _session_course_counts(course_ids: list[int]) -> dict[int, int]:
    """Ders başına sınav kullanım sayısı — sınav modülü (F3) yokken boş."""
    from django.apps import apps as django_apps
    from django.db.models import Count

    try:
        esc = django_apps.get_model("sinav", "ExamSessionCourse")
    except LookupError:
        return {}
    return {
        row[0]: row[1]
        for row in esc.objects.filter(course_id__in=course_ids, deleted_at__isnull=True)
        .values_list("course_id")
        .annotate(n=Count("id"))
    }


def _split_catalog_elective_cluster(
    canon_key: str, members: list[Course]
) -> list[tuple[str, list[Course]]]:
    """Resmi adı 'Seçmeli X' olan MEB dersini öneksiz 'X' ile mükerrer SAYMA.

    (OYS Tur 661 istisnası.) Önekli üyelerden en az biri MEB kataloğundansa
    önekli küme ayrı değerlendirilir.
    """
    split: list[tuple[str, list[Course]]] = []
    pool: list[Course] = []
    by_prefix: dict[bool, list[Course]] = {True: [], False: []}
    for m in members:
        by_prefix[course_match_key(m.name) != canon_key].append(m)
    prefixed = by_prefix[True]
    if prefixed and any(m.source == CourseSource.MEB_CATALOG for m in prefixed):
        if len(prefixed) >= 2:
            split.append((f"seçmeli {canon_key}", prefixed))
        pool.extend(by_prefix[False])
    else:
        pool = members
    if pool:
        split.append((canon_key, pool))
    return split


def duplicate_course_candidates() -> list[dict[str, Any]]:
    """Kanonik anahtarı çakışan canlı Course kümeleri — mükerrer temizliği.

    Her ders için sınav kullanım sayısı + önerilen kanonik (öneksiz > MEB
    kaynaklı > en çok kullanılan > en küçük id). Salt okunur; PII yok.
    """
    live = list(Course.objects.all().order_by("name"))
    by_key: dict[str, list[Course]] = {}
    for course in live:
        by_key.setdefault(canon_course_key(course.name), []).append(course)
    collisions: dict[str, list[Course]] = {}
    for key, cluster in by_key.items():
        if not key or len(cluster) < 2:
            continue
        for sub_key, sub_members in _split_catalog_elective_cluster(key, cluster):
            if len(sub_members) >= 2:
                collisions[sub_key] = sub_members
    if not collisions:
        return []

    ids = [c.pk for cs in collisions.values() for c in cs]
    exam_counts = _session_course_counts(ids)

    result: list[dict[str, Any]] = []
    for key, courses_in in sorted(collisions.items()):
        members: list[dict[str, Any]] = []
        for c in courses_in:
            members.append(
                {
                    "id": c.pk,
                    "name": c.name,
                    "course_type": c.course_type,
                    "levels": sorted(int(lvl) for lvl in (c.levels or [])),
                    "course_source": c.source,
                    "has_prefix": course_match_key(c.name) != canon_course_key(c.name),
                    "exam_count": exam_counts.get(c.pk, 0),
                }
            )

        def _rank(m: dict[str, Any]) -> tuple[int, int, int, int]:
            return (
                0 if not m["has_prefix"] else 1,  # öneksiz kanonik olmaya adaydır
                0 if m["course_source"] == CourseSource.MEB_CATALOG else 1,
                -m["exam_count"],
                m["id"],
            )

        suggested = min(members, key=_rank)
        result.append(
            {
                "canon_key": key,
                "suggested_canonical_id": suggested["id"],
                "courses": sorted(members, key=lambda m: str(m["name"])),
            }
        )
    return result


# ---------------------------------------------------------------------------
# F6 — takvim köprüleri (OYS ders_yapisi servis arayüzünün YERELLEŞTİRİLMİŞ
# karşılıkları — B8). KS'de ders programı/kayıt (LessonGroup/LessonEnrollment)
# zinciri YOKTUR (tasarım §11 ALMA); bu üç fonksiyon OYS imzalarını korur ama
# katalog + öğrenci seviye sayımlarından beslenir. `course_level_student_ids`
# bilinçli olarak boş döner → günlük sınav yükü sayımında her ders "seviyenin
# tamamını kapsar" sayılır (konservatif düşüş — ADR-0044 karar 13, risk #4:
# bu varsayım GEVŞETİLEMEZ).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CourseLevelPair:
    """Havuz doldurma çifti — OYS taught_course_levels satırıyla aynı yüzey."""

    course_id: int
    course_name: str
    level: int


@dataclass(frozen=True)
class CoverageGroup:
    """Katılımcı kapsam grubu — OYS course_level_coverage satırıyla aynı yüzey."""

    label: str
    student_count: int
    whole_sections: bool


def taught_course_levels(
    school_year_id: int | None = None,
    *,
    course_types: Sequence[str] | None = None,
    exam_modes: Sequence[str] | None = None,
) -> list[CourseLevelPair]:
    """Havuz doldurma kaynağı — KS sapması: program verisi yok (B6/B8).

    OYS'de canlı LessonGroup'lardan "fiilen okutulan" çiftler gelirdi; KS'de
    kaynak aktif ders kataloğu × (dersin seviyeleri ∩ okulun seviye kümesi ∩
    AKTİF ÖĞRENCİSİ OLAN seviyeler). Öğrenci filtresi havuzu okulda gerçekten
    sınav yapılabilecek seviyelere daraltır; fazlalıklar havuzdan elle silinir.
    `school_year_id` OYS imza uyumu içindir (öğrenci kayıtları tek-yıl yereldir).

    `course_types` / `exam_modes` verilirse katalog o değerlere daraltılır;
    None = süzme yok (geriye dönük uyumlu). Otomatik havuz doldurma bunlarla
    "zorunlu + yazılı"ya iner, seçmeli seçim ekranı "seçmeli + yazılı"ya —
    süzgeç ÇAĞIRANDA, burada politika yok.

    Çıktı TÜRK ALFABESİ sıralıdır (ad, sonra seviye): DB `order_by("name")`
    SQLite'ta BINARY olduğundan 'Çağdaş…'/'İklim…' listenin sonuna düşerdi ve
    bu liste doğrudan kullanıcıya (havuz + seçmeli seçim ekranı) gidiyor.
    """
    from apps.okul import normalize
    from apps.okul import selectors as okul_selectors

    del school_year_id  # imza uyumu — KS öğrenci kayıtları aktif yıla aittir
    counts = okul_selectors.active_student_counts_by_level()
    student_levels = {lvl for lvl, n in counts.items() if n > 0}
    school_levels = set(okul_selectors.grade_level_values())
    qs = Course.objects.filter(is_active=True)
    if course_types is not None:
        qs = qs.filter(course_type__in=list(course_types))
    if exam_modes is not None:
        qs = qs.filter(exam_mode__in=list(exam_modes))
    pairs: list[CourseLevelPair] = []
    for course in sorted(qs, key=lambda c: normalize.tr_sort_key(c.name)):
        for level in sorted(set(course.levels) & school_levels & student_levels):
            pairs.append(CourseLevelPair(course_id=course.pk, course_name=course.name, level=level))
    return pairs


def course_level_student_ids(
    *, course_id: int, level: int, school_year_id: int, on_date: Any = None
) -> set[int]:
    """Derse kayıtlı öğrenci kümesi — KS v1'de kayıt verisi YOK, hep boş döner.

    Boş dönüş, `_daily_exam_load`'da dersin "seviyenin tamamını kapsadığı"
    konservatif varsayımını tetikler (OYS ADR-0044 karar 13 ile birebir).
    Seçmeli ders kayıtları ileride gelirse yalnız bu fonksiyon dolar; sayım
    algoritması değişmez.
    """
    del course_id, level, school_year_id, on_date
    return set()


def course_level_coverage(
    *, course_id: int, level: int, school_year_id: int, on_date: Any = None
) -> list[CoverageGroup]:
    """Katılımcı kapsam önizlemesi — KS v1: her ders seviyenin tamamını kapsar."""
    from apps.dersler.services import level_label
    from apps.okul import selectors as okul_selectors

    del course_id, school_year_id, on_date
    counts = okul_selectors.active_student_counts_by_level()
    label = level_label(level)
    display = f"{label}. sınıf" if label.isdigit() else label
    return [
        CoverageGroup(
            label=f"{display} — seviyenin tamamı",
            student_count=counts.get(level, 0),
            whole_sections=True,
        )
    ]


def course_section_map(school_year_id: int) -> dict[tuple[int, int], list[int]]:
    """(ders, seviye) → CANLI şube pk listesi — ders havuzunda girilen kapsam.

    Sınav takvimi kapsamının kaynağıdır; takvim girdisi bundan ÖN-DOLAR ama
    kendi kopyasını yazar (`CourseSectionOffering` docstring'i).

    Silinmiş şube okuma anında düşürülür: `section_ids` bir JSON listedir, FK
    koruması yoktur (takvim girdisiyle aynı kalıp — `services_calendar
    ._live_section_ids`). Şube pk'leri TEK sorguda süzülür; kapsamı tümüyle
    ölmüş kayıt sözlüğe boş liste ile girer, çağıran "tanımsız" ile "boş"u
    ayırt edebilsin (havuz doldurma ikisini de atlar, arayüz uyarır).
    """
    from apps.dersler.models import CourseSectionOffering
    from apps.okul.models import ClassSection

    kayitlar = list(CourseSectionOffering.objects.filter(school_year_id=school_year_id))
    if not kayitlar:
        return {}
    tum_ids: set[int] = set()
    for kayit in kayitlar:
        tum_ids.update(int(sid) for sid in kayit.section_ids or [])
    canli = set(
        ClassSection.objects.filter(pk__in=tum_ids, school_year_id=school_year_id).values_list(
            "pk", flat=True
        )
    )
    return {
        (kayit.course_id, int(kayit.level)): [
            int(sid) for sid in kayit.section_ids or [] if int(sid) in canli
        ]
        for kayit in kayitlar
    }
