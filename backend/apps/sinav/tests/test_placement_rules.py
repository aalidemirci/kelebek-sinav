"""Yerleştirme kuralları — servis + motor entegrasyonu + API testleri.

Kabul kriterleri: sabit öğrenci HER dağıtımda yerinde (farklı seed'lerde);
kendi dersliği kuralı kelebek motorunu deliyor; ön sıra / belirli salon /
ayrı salon; önceki oturum farklılığı; kural CRUD.

OYS `test_placement_rules.py`'den KS'ye uyarlandı: RBAC ve AccessLog
(SENSITIVE_READ) düştü (authsuz tek kullanıcı); StudentEnrollment yok —
öğrenci doğrudan okul no ile bulunur. Ortak kurucular `oturum_yardim`'dan.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.okul.models import ClassSection, Student
from apps.sinav import services
from apps.sinav.models import (
    DeskType,
    ExamRoom,
    ExamSession,
    ExamSessionStatus,
    LayoutMode,
    ParticipantType,
    PlacementRule,
    RuleReason,
    RuleScope,
    RuleType,
    SeatAssignment,
    SeatStatus,
)
from apps.sinav.tests.oturum_yardim import ders, oturum, salon, sube

pytestmark = pytest.mark.django_db

#: 12 koltuklu salon (3x2 ikili sıra) — 8 öğrenciyle 4 koltuk pay kalır.
PLAN_3X2_DOUBLE: dict[str, Any] = {
    "grid": {"rows": 3, "cols": 2},
    "desks": [{"row": r, "col": c, "type": DeskType.DOUBLE} for r in range(3) for c in range(2)],
    "furniture": [],
}


def _kelebek_oturumu(student_count: int = 8) -> ExamSession:
    """9/A + 10/A öğrencileri iki dersle (iki çakışma grubu) + 12 koltuklu salon."""
    sube(9, "A", students=student_count // 2, start_no=101)
    sube(10, "A", students=student_count // 2, start_no=201)
    c9 = ders("Coğrafya", levels=[9])
    c10 = ders("Fizik", levels=[10])
    session = oturum()
    services.add_session_course(
        session, course_id=c9.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    services.add_session_course(
        session, course_id=c10.pk, participant_type=ParticipantType.LEVEL, level=10
    )
    room = salon("D-201", plan=PLAN_3X2_DOUBLE)
    services.set_session_rooms(session, [{"room_id": room.pk}])
    return session


def _ilk_ogrenci_id() -> int:
    """No 101'li 9/A öğrencisinin id'si (kural hedefi olarak kullanılır)."""
    return int(Student.objects.get(student_number="101").pk)


# ===========================================================================
# Servis — kural CRUD doğrulamaları
# ===========================================================================


def test_create_rule_validations() -> None:
    _kelebek_oturumu()
    sid = _ilk_ogrenci_id()

    with pytest.raises(ValidationError, match="Öğrenci bulunamadı"):
        services.create_placement_rule(student_id=999_999, rule_type=RuleType.FRONT_ROW)
    with pytest.raises(ValidationError, match="hedef salon zorunludur"):
        services.create_placement_rule(student_id=sid, rule_type=RuleType.FIXED_ROOM)
    with pytest.raises(ValidationError, match="hedef salon almaz"):
        services.create_placement_rule(
            student_id=sid, rule_type=RuleType.FRONT_ROW, target_room_id=1
        )
    with pytest.raises(ValidationError, match="oturum seçin"):
        services.create_placement_rule(
            student_id=sid, rule_type=RuleType.FRONT_ROW, scope=RuleScope.SESSION
        )

    rule = services.create_placement_rule(
        student_id=sid, rule_type=RuleType.FRONT_ROW, reason_category=RuleReason.HEALTH
    )
    assert rule.scope == RuleScope.PERMANENT
    with pytest.raises(ValidationError, match="zaten canlı bir kural"):
        services.create_placement_rule(student_id=sid, rule_type=RuleType.FRONT_ROW)
    # Kaldır → yeniden eklenebilir (canlı tekillik).
    services.remove_placement_rule(rule)
    services.create_placement_rule(student_id=sid, rule_type=RuleType.FRONT_ROW)


def test_rule_blocked_on_locked_session() -> None:
    """Onaylı/arşiv oturuma kural eklenemez — yerleşim değiştirilemez (kilit)."""
    session = _kelebek_oturumu()
    sid = _ilk_ogrenci_id()
    session.status = ExamSessionStatus.APPROVED
    session.save(update_fields=["status"])
    with pytest.raises(ValidationError, match="kural eklenemez"):
        services.create_placement_rule(
            student_id=sid,
            rule_type=RuleType.FRONT_ROW,
            scope=RuleScope.SESSION,
            session=session,
        )


def test_session_rule_overrides_permanent() -> None:
    session = _kelebek_oturumu()
    sid = _ilk_ogrenci_id()
    services.create_placement_rule(student_id=sid, rule_type=RuleType.FRONT_ROW)
    services.create_placement_rule(
        student_id=sid,
        rule_type=RuleType.HOME_CLASSROOM,
        scope=RuleScope.SESSION,
        session=session,
    )
    effective = services._effective_rules(session, [sid])
    assert effective[sid].rule_type == RuleType.HOME_CLASSROOM


# ===========================================================================
# Motor entegrasyonu — kabul kriterleri
# ===========================================================================


def test_pinned_student_stays_across_seeds() -> None:
    """Sabit öğrenci HER dağıtımda yerinde (farklı seed'ler) — kabul kriteri."""
    session = _kelebek_oturumu()
    sid = _ilk_ogrenci_id()
    room = salon("Z-101", plan=PLAN_3X2_DOUBLE)
    services.create_placement_rule(
        student_id=sid, rule_type=RuleType.FIXED_ROOM, target_room_id=room.pk
    )

    seats: set[tuple[int, int]] = set()
    for seed in (1, 2, 3):
        services.distribute_session(session, seed=seed)
        row = SeatAssignment.objects.get(session=session, student_id=sid)
        assert row.status == SeatStatus.PINNED
        assert row.room_id == room.pk
        seats.add((row.room_id, row.seat_no))
    assert len(seats) == 1  # koltuk da sabit (deterministik pin)


def test_home_classroom_rule_pierces_butterfly() -> None:
    """Kendi dersliği kuralı kelebek motorunu deliyor — kabul kriteri."""
    session = _kelebek_oturumu()
    sid = _ilk_ogrenci_id()  # 9/A öğrencisi
    section = ClassSection.objects.get(class_level=9, class_section="A")
    own_room = salon("9-A Dersliği", plan=PLAN_3X2_DOUBLE, linked_section_id=section.pk)
    services.create_placement_rule(
        student_id=sid, rule_type=RuleType.HOME_CLASSROOM, reason_category=RuleReason.DISABILITY
    )

    _, result, report = services.distribute_session(session, seed=42)

    row = SeatAssignment.objects.get(session=session, student_id=sid)
    assert row.room_id == own_room.pk  # kelebek salonuna DEĞİL kendi dersliğine
    assert row.status == SeatStatus.PINNED
    assert report.is_valid
    # Diğer 7 öğrenci kelebek salonunda.
    assert SeatAssignment.objects.filter(session=session).exclude(pk=row.pk).count() == 7
    assert SeatAssignment.objects.filter(session=session, room_id=own_room.pk).count() == 1


def test_home_classroom_rule_missing_room_raises() -> None:
    session = _kelebek_oturumu()
    sid = _ilk_ogrenci_id()
    services.create_placement_rule(student_id=sid, rule_type=RuleType.HOME_CLASSROOM)
    with pytest.raises(ValidationError, match="bağlı derslik tanımlı değil"):
        services.distribute_session(session, seed=1)


def test_front_row_rule() -> None:
    session = _kelebek_oturumu()
    sid = _ilk_ogrenci_id()
    services.create_placement_rule(student_id=sid, rule_type=RuleType.FRONT_ROW)

    services.distribute_session(session, seed=7)
    row = SeatAssignment.objects.get(session=session, student_id=sid)
    assert row.status == SeatStatus.PINNED
    assert row.desk_row == 0  # plandaki en ön sıra


def test_separate_room_excluded_from_butterfly() -> None:
    """AYRI_SALON: hedef salon kelebekten çıkar; öğrenci orada tek başına."""
    session = _kelebek_oturumu()
    sid = _ilk_ogrenci_id()
    lone_room = salon("Tekil Oda", plan=PLAN_3X2_DOUBLE)
    # Ayrı salonu oturum salonlarına da ekle — dağıtım onu kelebekten çıkarmalı.
    main_room = ExamRoom.objects.get(name="D-201")
    services.set_session_rooms(session, [{"room_id": main_room.pk}, {"room_id": lone_room.pk}])
    services.create_placement_rule(
        student_id=sid, rule_type=RuleType.SEPARATE_ROOM, target_room_id=lone_room.pk
    )

    _, result, _ = services.distribute_session(session, seed=5)

    in_lone = SeatAssignment.objects.filter(session=session, room_id=lone_room.pk)
    assert in_lone.count() == 1
    assert in_lone.first().student_id == sid  # type: ignore[union-attr]
    assert any("kelebek dağıtımından çıkarıldı" in w for w in result.warnings)


def test_rules_not_applied_in_home_classroom_layout() -> None:
    """Klasik düzende kural uygulanmaz — yalnız uyarı düşer (öğrenci zaten
    kendi dersliğinde)."""
    section = sube(9, "A", students=3, start_no=101)
    course = ders("Coğrafya", levels=[9])
    session = oturum(layout_mode=LayoutMode.HOME_CLASSROOM)
    services.add_session_course(
        session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    salon("9-A Dersliği", plan=PLAN_3X2_DOUBLE, linked_section_id=section.pk)
    services.create_placement_rule(student_id=_ilk_ogrenci_id(), rule_type=RuleType.FRONT_ROW)

    _, result, _ = services.distribute_session(session, seed=1)

    assert any("klasik düzende uygulanmaz" in w for w in result.warnings)
    assert not SeatAssignment.objects.filter(session=session, status=SeatStatus.PINNED).exists()


def test_previous_session_seat_avoided() -> None:
    """Önceki oturum farklılığı: öğrenci mümkünse aynı sıraya dönmez."""
    session_a = _kelebek_oturumu()
    services.distribute_session(session_a, seed=11)
    prev = {
        a.student_id: (a.room_id, a.desk_row, a.desk_col)
        for a in SeatAssignment.objects.filter(session=session_a)
    }

    # Aynı katılımcılar + aynı salonla ikinci oturum.
    c9b = ders("Tarih", levels=[9])
    c10b = ders("Kimya", levels=[10])
    session_b = oturum(name="2. Ortak Sınav", exam_date=date(2026, 11, 17))
    services.add_session_course(
        session_b, course_id=c9b.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    services.add_session_course(
        session_b, course_id=c10b.pk, participant_type=ParticipantType.LEVEL, level=10
    )
    room = ExamRoom.objects.get(name="D-201")
    services.set_session_rooms(session_b, [{"room_id": room.pk}])

    services.distribute_session(session_b, seed=11)  # AYNI seed — fark cezadan gelmeli
    same_desk = 0
    for a in SeatAssignment.objects.filter(session=session_b):
        if prev.get(a.student_id) == (a.room_id, a.desk_row, a.desk_col):
            same_desk += 1
    # 12 koltuk / 8 öğrenci: ceza terimi çoğunu farklı sıraya itmeli.
    assert same_desk <= 2, f"{same_desk} öğrenci önceki sırasında"


# ===========================================================================
# API — CRUD (authsuz tek kullanıcı; RBAC/AccessLog yok)
# ===========================================================================

URL = "/api/v1/placement-rules/"


def test_api_crud() -> None:
    session = _kelebek_oturumu()
    sid = _ilk_ogrenci_id()
    client = APIClient()

    resp = client.post(
        URL,
        {"student_id": sid, "rule_type": "FRONT_ROW", "reason_category": "IEP"},
        format="json",
    )
    assert resp.status_code == 201
    rule_id = resp.data["id"]
    assert resp.data["student_name"]  # UI kolaylığı — şifreli ad Python'da çözülür
    assert resp.data["scope"] == RuleScope.PERMANENT

    listing = client.get(URL)
    assert listing.status_code == 200
    assert listing.data["count"] == 1

    # ?session= süzgeci: kalıcı kural o oturum İÇİN de geçerlidir.
    for_session = client.get(f"{URL}?session={session.pk}")
    assert for_session.data["count"] == 1

    bad = client.post(URL, {"student_id": sid, "rule_type": "FIXED_ROOM"}, format="json")
    assert bad.status_code == 400  # hedef salon zorunlu (Türkçe mesaj servisten)

    assert client.delete(f"{URL}{rule_id}/").status_code == 204
    assert PlacementRule.objects.count() == 0
