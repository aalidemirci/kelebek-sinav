"""Katılımcı çözümleyici testleri (T4 — K7) — kabul kriterleri.

Seviye/şube karışık senaryolar; öğrenci iki derse düşemez; oturumlar arası
zaman çakışması; ortak kitapçık tek grup. OYS `test_participants.py`'den
UYARLA: GROUPS tipi testleri düştü (TB7 — grup zinciri taşınmadı), grup
dedupe senaryosu şube tekrarına çevrildi; auth/RBAC yok (tek kullanıcı).
"""

from __future__ import annotations

from datetime import time

import pytest
from rest_framework.test import APIClient

from apps.okul.models import Student, StudentStatus
from apps.sinav import participants, services
from apps.sinav.models import ParticipantType
from apps.sinav.tests.oturum_yardim import ders, oturum, sube

pytestmark = pytest.mark.django_db


# ===========================================================================
# Çözümleyici — tipler ve karışık senaryolar
# ===========================================================================


def test_level_resolution_splits_conflict_groups_per_level() -> None:
    """Tur 241: aynı dersin seviyeleri AYRI satır — gruplar satır bazında ayrışır."""
    sube(9, "A", students=1, start_no=101)
    sube(10, "A", students=1, start_no=201)
    s9 = Student.objects.get(student_number="101")
    s10 = Student.objects.get(student_number="201")
    course = ders("Coğrafya", levels=[9, 10])
    session = oturum()
    services.add_session_course(
        session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    services.add_session_course(
        session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=10
    )

    result = participants.resolve_session(session)

    assert result.total_count == 2
    by_student = {p.student_id: p for p in result.participants}
    assert by_student[s9.pk].conflict_group == f"{course.pk}:9"
    assert by_student[s10.pk].conflict_group == f"{course.pk}:10"
    assert not result.has_blocking_conflicts


def test_shared_booklet_single_conflict_group() -> None:
    """Ortak kitapçık (K7): aynı dersin shared satırları tek grup sayılır (Tur 241)."""
    sube(9, "A", students=1, start_no=101)
    sube(10, "A", students=1, start_no=201)
    course = ders("Seçmeli Astronomi", levels=[9, 10])
    session = oturum()
    services.add_session_course(
        session,
        course_id=course.pk,
        participant_type=ParticipantType.LEVEL,
        level=9,
        shared_booklet=True,
    )
    services.add_session_course(
        session,
        course_id=course.pk,
        participant_type=ParticipantType.LEVEL,
        level=10,
        shared_booklet=True,
    )

    groups = {p.conflict_group for p in participants.resolve_session(session).participants}
    assert groups == {f"{course.pk}:*"}


def test_sections_resolution() -> None:
    """Şube bazlı atama yalnız seçilen şubenin öğrencilerini çözer."""
    sube(9, "A", students=1, start_no=101)
    section_b = sube(9, "B", students=1, start_no=201)
    sb = Student.objects.get(student_number="201")
    course = ders("Fizik", levels=[9])
    session = oturum()
    services.add_session_course(
        session,
        course_id=course.pk,
        participant_type=ParticipantType.SECTIONS,
        section_ids=[section_b.pk],
    )

    result = participants.resolve_session(session)
    assert [p.student_id for p in result.participants] == [sb.pk]
    assert result.participants[0].class_section == "B"


def test_dedupe_within_course_is_silent() -> None:
    """Aynı derse iki kez çözülen öğrenci TEK kez sayılır (sessiz ders-içi dedupe)."""
    section = sube(11, "B", students=2, start_no=301)
    course = ders("Seçmeli İngilizce", levels=[11])
    session = oturum()
    sc = services.add_session_course(
        session,
        course_id=course.pk,
        participant_type=ParticipantType.SECTIONS,
        section_ids=[section.pk],
    )
    # Servis section_ids'i tekler; ders-içi dedupe'u sınamak için satır elle çoğaltılır.
    sc.section_ids = [section.pk, section.pk]
    sc.save(update_fields=["section_ids"])

    result = participants.resolve_session(session)
    assert result.total_count == 2  # her öğrenci teklendi
    assert not result.has_blocking_conflicts


def test_mixed_types_in_one_session() -> None:
    """Seviye + şube karışık tek oturumda (kabul kriteri; GROUPS alınmadı — TB7)."""
    section_a = sube(9, "A", students=1, start_no=101)
    sube(10, "A", students=1, start_no=201)
    s9a = Student.objects.get(student_number="101")
    s10 = Student.objects.get(student_number="201")

    c1 = ders("Coğrafya", levels=[10])
    c2 = ders("Fizik", levels=[9])
    session = oturum()
    services.add_session_course(
        session, course_id=c1.pk, participant_type=ParticipantType.LEVEL, level=10
    )
    services.add_session_course(
        session,
        course_id=c2.pk,
        participant_type=ParticipantType.SECTIONS,
        section_ids=[section_a.pk],
    )

    result = participants.resolve_session(session)
    assert result.total_count == 2
    assert {p.student_id for p in result.participants} == {s9a.pk, s10.pk}
    assert not result.has_blocking_conflicts
    assert len({p.conflict_group for p in result.participants}) == 2


def test_student_in_two_courses_is_blocking_conflict() -> None:
    """Öğrenci iki derse düşemez (kabul kriteri) — sert çakışma raporlanır."""
    section = sube(9, "A", students=1, start_no=101)
    s1 = Student.objects.get(student_number="101")
    c1 = ders("Coğrafya", levels=[9])
    c2 = ders("Seçmeli İngilizce", levels=[9])
    session = oturum()
    services.add_session_course(
        session, course_id=c1.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    services.add_session_course(
        session,
        course_id=c2.pk,
        participant_type=ParticipantType.SECTIONS,
        section_ids=[section.pk],
    )

    result = participants.resolve_session(session)
    assert result.has_blocking_conflicts
    assert s1.pk in result.duplicate_students
    assert sorted(result.duplicate_students[s1.pk]) == ["Coğrafya", "Seçmeli İngilizce"]
    # Uyarı metni AD İÇERMEZ (KVKK) — okul no ile işaret eder.
    assert any("Okul No 101" in w and "2 derse düşüyor" in w for w in result.warnings)
    assert all(s1.full_name not in w for w in result.warnings)


def test_inactive_student_excluded_from_level() -> None:
    """Ayrılan (LEFT) öğrenci seviye çözümüne girmez."""
    sube(9, "A", students=2, start_no=101)
    active = Student.objects.get(student_number="101")
    gone = Student.objects.get(student_number="102")
    gone.status = StudentStatus.LEFT
    gone.save(update_fields=["status"])
    course = ders("Kimya", levels=[9])
    session = oturum()
    services.add_session_course(
        session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=9
    )

    ids = {p.student_id for p in participants.resolve_session(session).participants}
    assert ids == {active.pk}


def test_empty_course_and_missing_refs_warn() -> None:
    """Silinen/olmayan şube id'si uyarıya düşer (atlanır); liste boş kalır."""
    course = ders("Coğrafya", levels=[12])
    session = oturum()
    sc = services.add_session_course(
        session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=12
    )
    # Referans bütünlüğü: silinen şube id'si uyarıya düşer (atlanır).
    sc.participant_type = ParticipantType.SECTIONS
    sc.section_ids = [99999]
    sc.save()

    result = participants.resolve_session(session)
    assert result.total_count == 0
    assert any("bulunamadı" in w for w in result.courses[0].warnings)


# ===========================================================================
# Oturumlar arası zaman çakışması (K3)
# ===========================================================================


def test_overlapping_sessions_report_shared_students() -> None:
    """Zaman aralığı kesişen oturumlardaki ortak öğrenci okul no ile raporlanır."""
    sube(9, "A", students=1, start_no=101)
    s1 = Student.objects.get(student_number="101")
    course1 = ders("Coğrafya", levels=[9])
    course2 = ders("Fizik", levels=[9])

    session_a = oturum(name="Sabah Oturumu", start_time=time(9, 0), duration_minutes=60)
    services.add_session_course(
        session_a, course_id=course1.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    session_b = oturum(name="Çakışan Oturum", start_time=time(9, 30), duration_minutes=60)
    services.add_session_course(
        session_b, course_id=course2.pk, participant_type=ParticipantType.LEVEL, level=9
    )

    conflicts = participants.overlapping_session_conflicts(session_a)
    assert len(conflicts) == 1
    assert "Çakışan Oturum" in conflicts[0]
    # Ad değil okul no listelenir (KVKK).
    assert "No: 101" in conflicts[0]
    assert s1.full_name not in conflicts[0]


def test_non_overlapping_sessions_no_conflict() -> None:
    """Aynı gün ama kesişmeyen saat aralıkları çakışma üretmez."""
    sube(9, "A", students=1, start_no=101)
    course1 = ders("Coğrafya", levels=[9])
    course2 = ders("Fizik", levels=[9])
    session_a = oturum(name="Sabah", start_time=time(9, 0), duration_minutes=60)
    services.add_session_course(
        session_a, course_id=course1.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    session_b = oturum(name="Öğle", start_time=time(10, 0), duration_minutes=60)
    services.add_session_course(
        session_b, course_id=course2.pk, participant_type=ParticipantType.LEVEL, level=9
    )

    assert participants.overlapping_session_conflicts(session_a) == []


# ===========================================================================
# API — katılımcı önizleme ucu
# ===========================================================================


def test_api_participants_endpoint() -> None:
    """`GET /exam-sessions/<id>/participants/` — sayılar + çakışma + ders kırılımı."""
    section = sube(9, "A", students=1, start_no=101)
    c1 = ders("Coğrafya", levels=[9])
    c2 = ders("Fizik", levels=[9])
    session = oturum()
    services.add_session_course(
        session, course_id=c1.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    services.add_session_course(
        session,
        course_id=c2.pk,
        participant_type=ParticipantType.SECTIONS,
        section_ids=[section.pk],
    )

    resp = APIClient().get(f"/api/v1/exam-sessions/{session.pk}/participants/")
    assert resp.status_code == 200
    assert resp.data["total_count"] == 2
    assert resp.data["has_blocking_conflicts"] is True
    # Uyarı metni AD İÇERMEZ (KVKK) — okul no ile işaret eder.
    assert any("Okul No 101" in w for w in resp.data["warnings"])
    assert len(resp.data["courses"]) == 2
    numbers = {p["student_number"] for c in resp.data["courses"] for p in c["participants"]}
    assert numbers == {"101"}
