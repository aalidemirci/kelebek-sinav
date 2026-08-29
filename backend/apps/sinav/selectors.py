"""sinav salt-okunur sorguları — F2 kesiti."""

from __future__ import annotations

from django.db.models import QuerySet

from apps.sinav.models import ExamRoom


def exam_rooms(*, include_inactive: bool = False) -> QuerySet[ExamRoom]:
    """Salon listesi (ada göre sıralı; linked_section join'li).

    Varsayılan yalnız aktif salonlar — oturum planlaması bunlardan seçer.
    """
    qs = ExamRoom.objects.select_related("linked_section")
    if not include_inactive:
        qs = qs.filter(is_active=True)
    return qs.order_by("name")


def get_exam_room(room_id: int) -> ExamRoom | None:
    return ExamRoom.objects.select_related("linked_section").filter(pk=room_id).first()


def section_rooms_for_levels(levels: set[int]) -> list[ExamRoom]:
    """Verilen seviyelerin ŞUBE DERSLİKLERİ (aktif + canlı şubeli salonlar).

    Sihirbaz salon ön-seçimi ve klasik düzen eşlemesi (F3) bu listeden okur;
    `linked_section`'sız serbest salonlar dahil edilmez.
    """
    return list(
        exam_rooms()
        .filter(
            linked_section__isnull=False,
            linked_section__deleted_at__isnull=True,
            linked_section__class_level__in=sorted(levels),
        )
        .order_by("linked_section__class_level", "linked_section__class_section")
    )
