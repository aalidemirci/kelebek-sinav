"""Sınav oturumu servis + API testleri — taslak kilidi, Adım 0, sihirbaz uçları.

OYS `test_session_api.py`'den KS'ye uyarlandı: RBAC/anonim senaryoları düştü
(authsuz tek kullanıcı), `created_by`/User damgaları ad-snapshot'a döndü (B12),
Adım 0 sözleşmesi beyan esaslı (B10) — nakil hareket sorgusu yerine son öğrenci
aktarımının tazeliği döner. Kurucular `oturum_yardim`'dan gelir; ders havuzu
typeahead testi dersler uygulamasının kendi testlerindedir.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dersler.models import Course
from apps.okul.models import ImportRun, SchoolConfig, Student, StudentStatus
from apps.sinav import selectors, services
from apps.sinav.models import ExamSessionRoom, ExamSessionStatus, ParticipantType
from apps.sinav.tests.oturum_yardim import ders, donem, oturum, salon, sube

pytestmark = pytest.mark.django_db

URL = "/api/v1/exam-sessions/"


# ===========================================================================
# Service — taslak kilidi + Adım 0
# ===========================================================================


def test_create_session_requires_term() -> None:
    with pytest.raises(ValidationError, match="Dönem bulunamadı"):
        oturum(term_id=99999)


def test_update_session_blocked_when_not_draft() -> None:
    session = oturum()
    session.status = ExamSessionStatus.APPROVED
    session.save(update_fields=["status"])
    with pytest.raises(ValidationError, match="yalnız taslak"):
        services.update_exam_session(session, name="Yeni Ad")
    with pytest.raises(ValidationError, match="yalnız taslak"):
        services.confirm_transfer_check(session)


def test_update_session_rejects_protected_fields() -> None:
    session = oturum()
    with pytest.raises(ValidationError, match="güncellenemez"):
        services.update_exam_session(session, status=ExamSessionStatus.APPROVED)


def test_confirm_transfer_check_records_who_when() -> None:
    """Adım 0 beyanı ad + zaman damgalar; ad kenar boşluklarından arındırılır."""
    session = oturum()
    services.confirm_transfer_check(session, confirmed_by_name="  Örnek   MÜDÜR ")
    session.refresh_from_db()
    assert session.transfer_check_confirmed_by_name == "Örnek MÜDÜR"
    assert session.transfer_check_confirmed_at is not None


def test_confirm_transfer_check_default_stamp_is_principal() -> None:
    """Ad verilmezse kurulumdaki müdür adı basılır (B12); kurulum yoksa boş kalır."""
    bos = oturum()
    services.confirm_transfer_check(bos)
    bos.refresh_from_db()
    assert bos.transfer_check_confirmed_by_name == ""
    assert bos.transfer_check_confirmed_at is not None

    SchoolConfig.objects.create(pk=SchoolConfig.SINGLETON_PK, principal_name="Örnek MÜDÜR")
    session = oturum(name="Müdürlü Oturum")
    services.confirm_transfer_check(session)
    session.refresh_from_db()
    assert session.transfer_check_confirmed_by_name == "Örnek MÜDÜR"


def test_add_session_course_validations() -> None:
    session = oturum()
    course = ders("Coğrafya", levels=[9])
    inactive = ders("Eski Ders", levels=[9])
    Course.objects.filter(pk=inactive.pk).update(is_active=False)

    with pytest.raises(ValidationError, match="bulunamadı"):
        services.add_session_course(
            session, course_id=inactive.pk, participant_type=ParticipantType.LEVEL, level=9
        )
    with pytest.raises(ValidationError, match="seviye seçin"):
        services.add_session_course(
            session, course_id=course.pk, participant_type=ParticipantType.LEVEL
        )
    with pytest.raises(ValidationError, match="en az bir şube"):
        services.add_session_course(
            session, course_id=course.pk, participant_type=ParticipantType.SECTIONS
        )

    row = services.add_session_course(
        session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    assert row.level == 9
    with pytest.raises(ValidationError, match="zaten ekli"):
        services.add_session_course(
            session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=9
        )


def test_remove_session_course_soft_deletes() -> None:
    session = oturum()
    course = ders("Coğrafya", levels=[9])
    row = services.add_session_course(
        session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    services.remove_session_course(row)
    assert session.courses.count() == 0
    # Aynı ders yeniden eklenebilir (canlı tekillik).
    services.add_session_course(
        session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=9
    )


def test_set_session_rooms_replace_semantics() -> None:
    session = oturum()
    room_a = salon("D-201")
    room_b = salon("D-202")
    room_c = salon("D-203")

    services.set_session_rooms(
        session, [{"room_id": room_a.pk}, {"room_id": room_b.pk, "capacity_override": 20}]
    )
    rows = list(selectors.session_rooms(session.pk))
    assert [(r.room_id, r.order, r.capacity_override) for r in rows] == [
        (room_a.pk, 0, None),
        (room_b.pk, 1, 20),
    ]

    # Replace: a çıkar, c girer; b'nin sırası değişir.
    services.set_session_rooms(session, [{"room_id": room_c.pk}, {"room_id": room_b.pk}])
    rows = list(selectors.session_rooms(session.pk))
    assert [r.room_id for r in rows] == [room_c.pk, room_b.pk]
    closed = ExamSessionRoom.all_objects.get(session=session, room=room_a)
    assert closed.deleted_at is not None

    with pytest.raises(ValidationError, match="iki kez"):
        services.set_session_rooms(session, [{"room_id": room_b.pk}, {"room_id": room_b.pk}])


def test_remove_exam_session_soft_deletes_children() -> None:
    session = oturum()
    course = ders("Coğrafya", levels=[9])
    services.add_session_course(
        session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    room = salon("D-201")
    services.set_session_rooms(session, [{"room_id": room.pk}])

    services.remove_exam_session(session)
    assert selectors.get_exam_session(session.pk) is None
    assert selectors.session_rooms(session.pk).count() == 0


def test_pre_check_summary_counts() -> None:
    """Adım 0 (B10): seviye sayıları + son aktarım tazeliği; nakil sorgusu YOK."""
    sube(9, "A", students=1, start_no=101)
    sube(10, "A", students=1, start_no=201)
    sube(9, "B", students=1, start_no=111)
    Student.objects.filter(student_number="111").update(status=StudentStatus.LEFT)

    data = services.pre_check_summary()
    assert data["active_students_by_level"] == {9: 1, 10: 1}
    assert data["last_student_import"] is None  # hiç aktarım yapılmamış
    assert "transfer_movements" not in data  # B10: e-Okul nakil sorgusu alınmadı

    ImportRun.objects.create(
        source_type="STUDENTS",
        file_name="ogrenciler.xlsx",
        file_hash="a" * 64,
        status="COMPLETED",
        finished_at=timezone.now(),
    )
    fresh = services.pre_check_summary()["last_student_import"]
    assert fresh is not None
    assert fresh["file_name"] == "ogrenciler.xlsx"
    assert fresh["finished_at"] is not None


# ===========================================================================
# API — sihirbaz uçları (auth yok: çıplak istemci)
# ===========================================================================


def test_api_create_and_wizard_flow() -> None:
    term = donem()
    section = sube(9, "A", students=1, start_no=101)
    course = ders("Coğrafya", levels=[9])
    room = salon("D-201")
    client = APIClient()

    # Adım 0 — ön kontrol verisi + oturum oluştur + beyan.
    pre = client.get(f"{URL}pre-check/")
    assert pre.status_code == 200
    assert pre.data["active_students_by_level"] == {9: 1}
    assert pre.data["last_student_import"] is None

    resp = client.post(
        URL,
        {
            "name": "1. Ortak Sınav",
            "exam_date": "2026-11-16",
            "start_time": "09:00",
            "duration_minutes": 60,
            "term_id": term.pk,
        },
        format="json",
    )
    assert resp.status_code == 201
    session_id = resp.data["id"]
    assert resp.data["status"] == "DRAFT"
    assert resp.data["term_id"] == term.pk

    confirm = client.post(
        f"{URL}{session_id}/confirm-transfer-check/",
        {"confirmed_by_name": "Örnek MÜDÜR"},
        format="json",
    )
    assert confirm.status_code == 200
    assert confirm.data["transfer_check_confirmed_by_name"] == "Örnek MÜDÜR"
    assert confirm.data["transfer_check_confirmed_at"] is not None

    # Adım 2 — ders ekle (şube bazlı).
    add = client.post(
        f"{URL}{session_id}/courses/",
        {
            "course_id": course.pk,
            "participant_type": "SECTIONS",
            "section_ids": [section.pk],
        },
        format="json",
    )
    assert add.status_code == 201

    # Adım 3 — salonlar.
    rooms = client.put(
        f"{URL}{session_id}/rooms/", {"rooms": [{"room_id": room.pk}]}, format="json"
    )
    assert rooms.status_code == 200
    assert rooms.data["rooms"][0]["room_name"] == "D-201"

    # Katılımcı çözümü.
    parts = client.get(f"{URL}{session_id}/participants/")
    assert parts.status_code == 200
    assert parts.data["total_count"] == 1
    assert parts.data["has_blocking_conflicts"] is False
    assert parts.data["courses"][0]["participants"][0]["student_number"] == "101"

    # Detayda dersler + salonlar gömülü.
    detail = client.get(f"{URL}{session_id}/")
    assert detail.data["courses"][0]["course_name"] == "Coğrafya"
    assert detail.data["rooms"][0]["room_name"] == "D-201"


def test_api_terms_endpoint() -> None:
    """Sihirbaz dönem seçici: aktif yılın dönemleri id + etiketle döner (PII yok)."""
    term = donem()
    resp = APIClient().get(f"{URL}terms/")
    assert resp.status_code == 200
    options = resp.data["terms"]
    assert any(opt["id"] == term.pk for opt in options)
    assert all(set(opt) == {"id", "label"} for opt in options)


def test_api_list_status_filter() -> None:
    draft = oturum()
    approved = oturum(name="Onaylı Oturum")
    approved.status = ExamSessionStatus.APPROVED
    approved.save(update_fields=["status"])
    client = APIClient()

    assert client.get(URL).data["count"] == 2
    resp = client.get(f"{URL}?status=DRAFT")
    assert [row["id"] for row in resp.data["results"]] == [draft.pk]


def test_api_session_course_patch_delete() -> None:
    session = oturum()
    course = ders("Coğrafya", levels=[9, 10])
    row = services.add_session_course(
        session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    client = APIClient()

    resp = client.patch(
        f"/api/v1/exam-session-courses/{row.pk}/",
        {"participant_type": "LEVEL", "level": 10, "shared_booklet": True},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["level"] == 10
    assert resp.data["display_label"] == "Coğrafya — 10. Sınıf (ortak kitapçık)"
    assert resp.data["shared_booklet"] is True

    assert client.delete(f"/api/v1/exam-session-courses/{row.pk}/").status_code == 204
    assert session.courses.count() == 0


def test_api_delete_session() -> None:
    session = oturum()
    client = APIClient()
    assert client.delete(f"{URL}{session.pk}/").status_code == 204
    assert selectors.get_exam_session(session.pk) is None

    # Taslak olmayan silinemez.
    other = oturum(name="Onaylı")
    other.status = ExamSessionStatus.APPROVED
    other.save(update_fields=["status"])
    assert client.delete(f"{URL}{other.pk}/").status_code == 400


# ===========================================================================
# Tur 241 (talep 2) — tek seviye kuralları
# ===========================================================================


def test_add_session_course_level_must_be_in_course_pool() -> None:
    session = oturum()
    course = ders("Coğrafya", levels=[9])
    with pytest.raises(ValidationError, match="okutulmuyor"):
        services.add_session_course(
            session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=11
        )


def test_same_course_different_levels_two_rows_allowed() -> None:
    session = oturum()
    course = ders("Matematik", levels=[9, 10])
    r9 = services.add_session_course(
        session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    r10 = services.add_session_course(
        session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=10
    )
    assert r9.pk != r10.pk
    with pytest.raises(ValidationError, match="zaten ekli"):
        services.add_session_course(
            session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=9
        )


def test_sections_mixed_levels_rejected() -> None:
    session = oturum()
    course = ders("Fizik", levels=[9, 10])
    s9 = sube(9, "C")
    s10 = sube(10, "C")
    with pytest.raises(ValidationError, match="tek seviyeye"):
        services.add_session_course(
            session,
            course_id=course.pk,
            participant_type=ParticipantType.SECTIONS,
            section_ids=[s9.pk, s10.pk],
        )
    # Homojen şubelerde seviye türetilir:
    row = services.add_session_course(
        session,
        course_id=course.pk,
        participant_type=ParticipantType.SECTIONS,
        section_ids=[s9.pk],
    )
    assert row.level == 9


def test_shared_booklet_flag_synced_across_siblings() -> None:
    session = oturum()
    course = ders("Kimya", levels=[9, 10])
    services.add_session_course(
        session,
        course_id=course.pk,
        participant_type=ParticipantType.LEVEL,
        level=9,
        shared_booklet=True,
    )
    with pytest.raises(ValidationError, match="ortak kitapçık"):
        services.add_session_course(
            session,
            course_id=course.pk,
            participant_type=ParticipantType.LEVEL,
            level=10,
            shared_booklet=False,
        )
