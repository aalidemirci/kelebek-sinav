"""Sınav yoklama (girmedi) takibi testleri (Tur 245, talep 1).

Servis guard'ları (yalnız ONAYLI/ARŞİV), snapshot kopyası, mükerrer reddi,
mazeret güncelleme (arşivde de açık), soft-delete telafisi + API akışı.
OYS `test_attendance.py`'den UYARLA: RBAC/AccessLog testleri düştü (authsuz
tek kullanıcı — DD §6 kalıbı); kurulum `oturum_yardim` kurucularıyla.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.sinav import services
from apps.sinav.models import (
    ExamAttendanceRecord,
    ExamSession,
    ExamSessionStatus,
    ExcuseStatus,
    ParticipantType,
    SeatAssignment,
)
from apps.sinav.tests.oturum_yardim import ders, oturum, salon, sube

pytestmark = pytest.mark.django_db

URL = "/api/v1/exam-attendance-records/"


def _dagitilmis_oturum() -> ExamSession:
    """2 ders (9 + 10. seviye) × 4 öğrenci, tek 8 koltuklu salonlu dağıtım."""
    sube(9, "A", students=4, start_no=101)
    sube(10, "B", students=4, start_no=201)
    c9 = ders("Coğrafya", levels=[9])
    c10 = ders("Fizik", levels=[10])
    session = oturum(name="2. Ortak Sınav")
    services.add_session_course(
        session, course_id=c9.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    services.add_session_course(
        session, course_id=c10.pk, participant_type=ParticipantType.LEVEL, level=10
    )
    room = salon("D-201")
    services.set_session_rooms(session, [{"room_id": room.pk}])
    services.distribute_session(session, seed=42)
    return session


def _onayli_oturum() -> ExamSession:
    return services.approve_session(_dagitilmis_oturum())


def test_mark_absent_copies_snapshot_and_defaults_pending() -> None:
    """Girmedi kaydı SeatAssignment snapshot'ını kopyalar; mazeret PENDING başlar."""
    session = _onayli_oturum()
    assignment = SeatAssignment.objects.filter(session=session).first()
    assert assignment is not None
    record = services.mark_absent(session, seat_assignment_id=assignment.pk)
    assert record.excuse_status == ExcuseStatus.PENDING
    assert record.full_name == assignment.full_name
    assert record.student_number == assignment.student_number
    assert record.class_label == assignment.class_label
    assert record.room_id == assignment.room_id
    assert record.seat_no == assignment.seat_no


def test_mark_absent_blocked_outside_approved() -> None:
    """Guard: işaretleme yalnız ONAYLI/ARŞİV oturumda (DAĞITILDI reddedilir)."""
    session = _dagitilmis_oturum()  # DISTRIBUTED
    assignment = SeatAssignment.objects.filter(session=session).first()
    assert assignment is not None
    with pytest.raises(ValidationError, match="onaylanmış oturumda"):
        services.mark_absent(session, seat_assignment_id=assignment.pk)


def test_mark_absent_duplicate_rejected_then_remark_after_unmark() -> None:
    """Mükerrer işaretleme reddedilir; soft-delete telafisi sonrası yeniden açılır."""
    session = _onayli_oturum()
    assignment = SeatAssignment.objects.filter(session=session).first()
    assert assignment is not None
    record = services.mark_absent(session, seat_assignment_id=assignment.pk)
    with pytest.raises(ValidationError, match="zaten girmedi"):
        services.mark_absent(session, seat_assignment_id=assignment.pk)
    services.unmark_absent(record)  # yanlış işaretleme telafisi (soft-delete)
    assert ExamAttendanceRecord.all_objects.get(pk=record.pk).deleted_at is not None
    services.mark_absent(session, seat_assignment_id=assignment.pk)  # yeniden işaretlenebilir


def test_excuse_update_open_in_archive() -> None:
    """Mazeret durumu/notu ARŞİVDE DE güncellenir (belge sonradan gelir)."""
    session = _onayli_oturum()
    assignment = SeatAssignment.objects.filter(session=session).first()
    assert assignment is not None
    record = services.mark_absent(session, seat_assignment_id=assignment.pk)
    services.archive_session(session)
    session.refresh_from_db()
    assert session.status == ExamSessionStatus.ARCHIVED
    updated = services.update_attendance_record(
        record, excuse_status=ExcuseStatus.EXCUSED, note="Rapor no 123, 10.06.2026"
    )
    assert updated.excuse_status == ExcuseStatus.EXCUSED
    assert updated.note == "Rapor no 123, 10.06.2026"


def test_mark_absent_foreign_assignment_rejected() -> None:
    """Başka oturumun/olmayan yerleşim kaydı reddedilir."""
    session = _onayli_oturum()
    with pytest.raises(ValidationError, match="bulunamadı"):
        services.mark_absent(session, seat_assignment_id=999999)


def test_api_flow() -> None:
    """API akışı: işaretle → listele → mazeret güncelle → sil (soft-delete)."""
    session = _onayli_oturum()
    assignment = SeatAssignment.objects.filter(session=session).first()
    assert assignment is not None
    client = APIClient()

    resp = client.post(
        URL,
        {"session_id": session.pk, "seat_assignment_id": assignment.pk, "note": "Veli aradı"},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["excuse_status"] == "PENDING"
    record_id = resp.data["id"]

    listing = client.get(f"{URL}?session={session.pk}")
    assert listing.status_code == 200
    assert listing.data["count"] == 1

    patch = client.patch(f"{URL}{record_id}/", {"excuse_status": "EXCUSED"}, format="json")
    assert patch.status_code == 200 and patch.data["excuse_status"] == "EXCUSED"

    assert client.delete(f"{URL}{record_id}/").status_code == 204
    assert client.get(f"{URL}?session={session.pk}").data["count"] == 0


def test_api_guard_returns_400_turkce() -> None:
    """Onaysız oturumda API işaretlemesi Türkçe 400 döner (guard serviste)."""
    session = _dagitilmis_oturum()  # DISTRIBUTED
    assignment = SeatAssignment.objects.filter(session=session).first()
    assert assignment is not None
    resp = APIClient().post(
        URL,
        {"session_id": session.pk, "seat_assignment_id": assignment.pk},
        format="json",
    )
    assert resp.status_code == 400
    assert "onaylanmış oturumda" in str(resp.data)
