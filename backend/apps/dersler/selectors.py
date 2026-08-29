"""Ders havuzu salt-okunur sorguları.

SQLite'ta JSONField `levels__contains` YOKTUR (K11) — seviye süzgeci Python
tarafında yapılır (`courses_for_level`); ~60 derslik katalogda maliyet yok.
Ad süzgeci (`q`) SQL `icontains` + Python TR-katlamalı süzgecin birleşimidir:
SQLite yalnız ASCII'de harf-duyarsızdır, 'matematik' araması 'MATEMATİK'
kaydını tek başına SQL ile bulamazdı.
"""

from __future__ import annotations

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
