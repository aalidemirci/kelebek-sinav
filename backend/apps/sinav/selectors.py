"""sinav salt-okunur sorguları — salon (F2) + oturum (F3) + kitapçık (F5) + takvim (F6)."""

from __future__ import annotations

from datetime import date

from django.db.models import Q, QuerySet

from apps.sinav.models import (
    BookletRun,
    ExamAttendanceRecord,
    ExamCalendar,
    ExamCalendarEntry,
    ExamRoom,
    ExamSession,
    ExamSessionCourse,
    ExamSessionRoom,
    ExamTrackItem,
    PlacementRule,
    QuestionDocument,
    SeatAssignment,
)


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


# ---------------------------------------------------------------------------
# F3 — oturum akışı
# ---------------------------------------------------------------------------
def exam_sessions(*, status: str | None = None) -> QuerySet[ExamSession]:
    """Oturum listesi (tarih azalan; dönem join'li)."""
    qs = ExamSession.objects.select_related("semester", "semester__school_year")
    if status:
        qs = qs.filter(status=status)
    return qs.order_by("-exam_date", "start_time")


def get_exam_session(session_id: int) -> ExamSession | None:
    """Tek canlı oturumu id ile getirir — yoksa None."""
    return ExamSession.objects.select_related("semester").filter(pk=session_id).first()


def get_session_course(sc_id: int) -> ExamSessionCourse | None:
    """Tek canlı oturum dersini id ile getirir (session+course join'li)."""
    return ExamSessionCourse.objects.select_related("session", "course").filter(pk=sc_id).first()


def placement_rules(*, session_id: int | None = None) -> QuerySet[PlacementRule]:
    """Canlı yerleştirme kuralları (öğrenci + hedef salon join'li).

    `session_id` verilirse o oturum İÇİN GEÇERLİ kurallar: oturuma özel +
    kalıcı kurallar. KVKK md. 6: gerekçe yalnız kategori düzeyindedir.
    """
    qs = PlacementRule.objects.select_related("student", "target_room", "session")
    if session_id is not None:
        qs = qs.filter(Q(session_id=session_id) | Q(session__isnull=True))
    return qs.order_by("-created_at")


def session_seat_assignments(session_id: int) -> QuerySet[SeatAssignment]:
    """Oturumun canlı yerleşimi (salon join'li; salon + koltuk no sıralı).

    KİŞİSEL VERİ (snapshot) içerir — sıralama düz alanlarda kalır (TB3).
    """
    return (
        SeatAssignment.objects.filter(session_id=session_id)
        .select_related("room")
        .order_by("room_id", "seat_no")
    )


def session_rooms(session_id: int) -> QuerySet[ExamSessionRoom]:
    """Oturumun salonları (kullanım sırasına göre, salon join'li)."""
    return (
        ExamSessionRoom.objects.filter(session_id=session_id)
        .select_related("room")
        .order_by("order", "id")
    )


def attendance_records(*, session_id: int | None = None) -> QuerySet[ExamAttendanceRecord]:
    """Sınav yoklama kayıtları — KİŞİSEL VERİ (snapshot ad/no)."""
    qs = ExamAttendanceRecord.objects.select_related("room")
    if session_id is not None:
        qs = qs.filter(session_id=session_id)
    return qs.order_by("room__name", "seat_no")


def question_document_for(session_course_id: int) -> QuestionDocument | None:
    """Oturum dersinin canlı soru dosyası — yoksa None."""
    return (
        QuestionDocument.objects.select_related("session_course__course")
        .filter(session_course_id=session_course_id)
        .first()
    )


def booklet_runs(*, session_id: int | None = None) -> QuerySet[BookletRun]:
    """Kitapçık koşuları (en yeni önce)."""
    qs = BookletRun.objects.all()
    if session_id is not None:
        qs = qs.filter(session_id=session_id)
    return qs.order_by("-created_at")


# ---------------------------------------------------------------------------
# F6 — sınav takvimi (OYS FAZ T selectors'tan UYARLA)
# ---------------------------------------------------------------------------


def exam_calendars(
    *, school_year_id: int | None = None, semester_id: int | None = None, status: str | None = None
) -> QuerySet[ExamCalendar]:
    """Takvim listesi (başlangıç azalan; dönem/yıl join'li)."""
    qs = ExamCalendar.objects.select_related("semester__school_year")
    if school_year_id is not None:
        qs = qs.filter(semester__school_year_id=school_year_id)
    if semester_id is not None:
        qs = qs.filter(semester_id=semester_id)
    if status:
        qs = qs.filter(status=status)
    return qs.order_by("-start_date")


def get_exam_calendar(calendar_id: int) -> ExamCalendar | None:
    return (
        ExamCalendar.objects.select_related("semester__school_year").filter(pk=calendar_id).first()
    )


def calendar_entries(
    calendar_id: int, *, placed: bool | None = None
) -> QuerySet[ExamCalendarEntry]:
    qs = ExamCalendarEntry.objects.select_related("course").filter(calendar_id=calendar_id)
    if placed is True:
        qs = qs.filter(placed_date__isnull=False)
    elif placed is False:
        qs = qs.filter(placed_date__isnull=True)
    return qs.order_by("course__name", "level")


def get_calendar_entry(entry_id: int) -> ExamCalendarEntry | None:
    return (
        ExamCalendarEntry.objects.select_related("calendar", "course").filter(pk=entry_id).first()
    )


def entries_for_slot(
    calendar_id: int, on_date: date, period_no: int
) -> QuerySet[ExamCalendarEntry]:
    return ExamCalendarEntry.objects.select_related("course").filter(
        calendar_id=calendar_id, placed_date=on_date, period_no=period_no
    )


def track_items(*, include_inactive: bool = False) -> QuerySet[ExamTrackItem]:
    qs = ExamTrackItem.objects.all()
    if not include_inactive:
        qs = qs.filter(is_active=True)
    return qs.order_by("order", "id")


def get_track_item(item_id: int) -> ExamTrackItem | None:
    return ExamTrackItem.objects.filter(pk=item_id).first()


# Not: slot→oturum salon ön-seçimi F3'teki `section_rooms_for_levels` (satır
# ~35, list dönen sürüm) ile yapılır — OYS'deki QuerySet sürümünün KS karşılığı
# zaten oydu; ikinci bir kopya AÇILMAZ.
