"""Dağıtım servisi + API testleri — snapshot yazımı, durum, takas, doluluk.

OYS `test_distribution_api.py`'den KS'ye uyarlandı: auth/RBAC ve AccessLog
(SENSITIVE_READ) düştü (authsuz tek kullanıcı, denetim modülü yok); GROUPS
katılımcı tipi alınmadı (TB7) — sert çakışma aynı seviyeye iki LEVEL dersiyle
kurulur. Ortak kurucular `oturum_yardim`'dan gelir.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.okul.models import Student
from apps.sinav import services
from apps.sinav.models import (
    DeskType,
    ExamRoom,
    ExamSession,
    ExamSessionStatus,
    LayoutMode,
    ParticipantType,
    SeatAssignment,
    SeatStatus,
)
from apps.sinav.tests.oturum_yardim import ders, oturum, salon, sube

pytestmark = pytest.mark.django_db

URL = "/api/v1/exam-sessions/"

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


def _yerlesim_haritasi(session: ExamSession) -> dict[int, tuple[int, int, int, int]]:
    """Öğrenci → koltuk kimliği (determinizm karşılaştırması için)."""
    return {
        a.student_id: (a.room_id, a.desk_row, a.desk_col, a.slot)
        for a in SeatAssignment.objects.filter(session=session)
    }


# ===========================================================================
# Servis — dağıtım
# ===========================================================================


def test_distribute_writes_snapshots_and_status() -> None:
    session = _kelebek_oturumu()
    session, result, report = services.distribute_session(session, seed=42)

    assert session.status == ExamSessionStatus.DISTRIBUTED
    assert session.distribution_params["seed"] == 42
    assert session.distribution_params["placed"] == 8
    assert report.is_valid
    rows = list(SeatAssignment.objects.filter(session=session))
    assert len(rows) == 8 == len(result.placements)
    sample = rows[0]
    assert sample.full_name and sample.student_number and sample.class_label
    assert ":" in sample.conflict_group


def test_distribute_same_seed_is_deterministic() -> None:
    """Aynı seed → aynı dağıtım (CLAUDE.md §3) — yeniden dağıtımda da."""
    session = _kelebek_oturumu()
    _, result, _ = services.distribute_session(session, seed=42)
    assert result.seed == 42
    first = _yerlesim_haritasi(session)

    services.distribute_session(session, seed=42)
    assert _yerlesim_haritasi(session) == first


def test_redistribute_replaces_previous_assignments() -> None:
    session = _kelebek_oturumu()
    services.distribute_session(session, seed=1)
    first_ids = set(SeatAssignment.objects.filter(session=session).values_list("id", flat=True))

    services.distribute_session(session, seed=2)  # DAĞITILDI durumunda yeniden dağıt
    second_ids = set(SeatAssignment.objects.filter(session=session).values_list("id", flat=True))

    assert first_ids.isdisjoint(second_ids)
    # Eski satırlar soft-delete (tarihsel iz).
    assert SeatAssignment.all_objects.filter(
        id__in=first_ids, deleted_at__isnull=False
    ).count() == len(first_ids)


def test_distribute_blocked_when_approved() -> None:
    session = _kelebek_oturumu()
    session.status = ExamSessionStatus.APPROVED
    session.save(update_fields=["status"])
    with pytest.raises(ValidationError, match="yeniden dağıtılamaz"):
        services.distribute_session(session, seed=1)


def test_distribute_blocked_on_student_conflict() -> None:
    """Öğrenci iki derste → dağıtım reddedilir (GROUPS yok; iki LEVEL dersi)."""
    sube(9, "A", students=2, start_no=101)
    c1 = ders("Coğrafya", levels=[9])
    c2 = ders("Seçmeli İngilizce", levels=[9])
    session = oturum()
    services.add_session_course(
        session, course_id=c1.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    services.add_session_course(
        session, course_id=c2.pk, participant_type=ParticipantType.LEVEL, level=9
    )

    with pytest.raises(ValidationError, match="birden çok derse"):
        services.distribute_session(session, seed=1)


def test_distribute_butterfly_requires_rooms() -> None:
    sube(9, "A", students=1, start_no=101)
    course = ders("Coğrafya", levels=[9])
    session = oturum()
    services.add_session_course(
        session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    with pytest.raises(ValidationError, match="salon"):
        services.distribute_session(session, seed=1)


def test_distribute_strict_escalates_first_ring() -> None:
    """Katı mod: 1. halka komşuluğu sert ihlaldir — 3x2 planda 8 öğrenciyle
    kaçınılmazdır (rapor geçersiz); normal modda aynı kurulum ihlalsizdir."""
    session = _kelebek_oturumu()
    _, _, report = services.distribute_session(session, seed=5, strict=True)
    assert session.distribution_params["strict"] is True
    assert not report.is_valid
    assert any("Katı mod ihlali" in v for v in report.hard_violations)

    _, _, gevsek = services.distribute_session(session, seed=5)
    assert gevsek.is_valid


def test_distribute_occupancy_gap_warning() -> None:
    """K1: doluluk farkı eşiği aşınca uyarı üretilir ve params'a kalıcılaşır."""
    session = _kelebek_oturumu()
    main = ExamRoom.objects.get(name="D-201")
    ek = salon("Ek Oda", plan=PLAN_3X2_DOUBLE)
    services.set_session_rooms(
        session,
        [{"room_id": main.pk}, {"room_id": ek.pk, "capacity_override": 1}],
    )

    _, result, _ = services.distribute_session(session, seed=1)

    # Kota: 7/12 (%58) + 1/1 (%100) → fark eşik üstü.
    assert any("doluluk farkı yüksek" in w for w in result.warnings)
    assert any("doluluk farkı yüksek" in w for w in session.distribution_params["warnings"])


# ===========================================================================
# Servis — klasik düzen (kendi dersliğinde)
# ===========================================================================


def test_distribute_home_classroom_uses_linked_rooms() -> None:
    section = sube(9, "A")
    for i in range(3):  # okul no ters sırayla girilir — çıktı no sıralı olmalı
        Student.objects.create(
            first_name=f"AD{i}",
            last_name="SOYAD9A",
            student_number=str(110 - i),
            class_level=9,
            class_section="A",
        )
    course = ders("Coğrafya", levels=[9])
    session = oturum(layout_mode=LayoutMode.HOME_CLASSROOM)
    services.add_session_course(
        session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    salon("9-A Dersliği", plan=PLAN_3X2_DOUBLE, linked_section_id=section.pk)

    session, result, report = services.distribute_session(session, seed=1)
    assert report.is_valid
    numbers = [
        a.student_number for a in SeatAssignment.objects.filter(session=session).order_by("seat_no")
    ]
    assert numbers == sorted(numbers, key=int)  # okul no sırası


def test_distribute_home_classroom_missing_mapping() -> None:
    sube(9, "A", students=1, start_no=101)
    course = ders("Coğrafya", levels=[9])
    session = oturum(layout_mode=LayoutMode.HOME_CLASSROOM)
    services.add_session_course(
        session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    with pytest.raises(ValidationError, match="Derslik eşlemesi eksik: 9/A"):
        services.distribute_session(session, seed=1)


def test_seating_report_detects_plan_change_after_distribution() -> None:
    session = _kelebek_oturumu()
    services.distribute_session(session, seed=1)

    exam_room = ExamRoom.objects.get(name="D-201")
    services.update_exam_room(
        exam_room,
        layout_plan={
            "grid": {"rows": 1, "cols": 1},
            "desks": [{"row": 0, "col": 0, "type": "SINGLE"}],
            "furniture": [],
        },
    )
    report = services.seating_report(session)
    assert not report.is_valid
    assert any("planı dağıtımdan sonra değişmiş" in v for v in report.hard_violations)


# ===========================================================================
# Servis — koltuk takası (üç aşamalı yazım)
# ===========================================================================


def test_swap_seats_exchanges_and_marks_manual() -> None:
    """Takas sonucu: koltuk kimlikleri TAM değişir (üç aşamalı yazım, seat_no
    dahil), iki satır MANUAL olur; aynı gruptan takas raporu bozmaz."""
    session = _kelebek_oturumu()
    services.distribute_session(session, seed=42)
    a, b = list(
        SeatAssignment.objects.filter(session=session, class_label="9/A").order_by("seat_no")
    )[:2]
    a_eski = (a.room_id, a.desk_row, a.desk_col, a.slot, a.seat_no)
    b_eski = (b.room_id, b.desk_row, b.desk_col, b.slot, b.seat_no)

    _, report = services.swap_seats(session, assignment_a_id=a.pk, assignment_b_id=b.pk)

    a.refresh_from_db()
    b.refresh_from_db()
    assert (a.room_id, a.desk_row, a.desk_col, a.slot, a.seat_no) == b_eski
    assert (b.room_id, b.desk_row, b.desk_col, b.slot, b.seat_no) == a_eski
    assert a.status == SeatStatus.MANUAL and b.status == SeatStatus.MANUAL
    assert report.is_valid  # aynı grup içi takas ayrışmayı değiştirmez


def test_swap_seats_guards() -> None:
    taslak = _kelebek_oturumu()
    with pytest.raises(ValidationError, match="takas yalnız dağıtılmış"):
        services.swap_seats(taslak, assignment_a_id=1, assignment_b_id=2)

    services.distribute_session(taslak, seed=1)
    row = SeatAssignment.objects.filter(session=taslak).first()
    assert row is not None
    with pytest.raises(ValidationError, match="iki FARKLI koltuk"):
        services.swap_seats(taslak, assignment_a_id=row.pk, assignment_b_id=row.pk)
    with pytest.raises(ValidationError, match="bulunamadı"):
        services.swap_seats(taslak, assignment_a_id=row.pk, assignment_b_id=999_999)


# ===========================================================================
# API
# ===========================================================================


def test_api_distribute_and_seating_flow() -> None:
    session = _kelebek_oturumu()
    client = APIClient()

    resp = client.post(f"{URL}{session.pk}/distribute/", {"seed": 42}, format="json")
    assert resp.status_code == 200
    assert resp.data["status"] == "DISTRIBUTED"
    assert resp.data["seed"] == 42
    assert resp.data["placed"] == 8
    assert resp.data["report"]["is_valid"] is True

    seating = client.get(f"{URL}{session.pk}/seating/")
    assert seating.status_code == 200
    assert seating.data["rooms"][0]["room_name"] == "D-201"
    assert len(seating.data["rooms"][0]["assignments"]) == 8
    row = seating.data["rooms"][0]["assignments"][0]
    assert {"full_name", "student_number", "class_label", "seat_no", "conflict_group"} <= set(row)
    assert seating.data["report"]["is_valid"] is True
    # Tur 241 (talep 9a): lejant etiketleri — grup anahtarı insan-okur derse çözülür.
    labels = seating.data["conflict_group_labels"]
    assert set(labels) == {
        a["conflict_group"] for r in seating.data["rooms"] for a in r["assignments"]
    }
    assert "Coğrafya — 9. Sınıf" in labels.values()
    assert "Fizik — 10. Sınıf" in labels.values()


def test_api_distribute_validation_error_turkce() -> None:
    session = oturum()  # ders/salon yok
    resp = APIClient().post(f"{URL}{session.pk}/distribute/", {}, format="json")
    assert resp.status_code == 400


def test_seating_response_includes_occupancy_and_k1_metrics() -> None:
    """K1 (OYS Tur 645): seating yanıtı occupancy + yeni rapor metriklerini taşır."""
    session = _kelebek_oturumu()
    services.distribute_session(session, seed=42)

    data = APIClient().get(f"{URL}{session.pk}/seating/").data

    assert "occupancy" in data and len(data["occupancy"]) == 1
    occ = data["occupancy"][0]
    assert {"room_id", "room_name", "capacity", "placed", "percent"} <= set(occ)
    assert occ["capacity"] == 12 and occ["placed"] == 8
    assert occ["percent"] == pytest.approx(66.7)

    report = data["report"]
    assert "cross_group_same_section_first_ring_pairs" in report
    assert report["room_counts"] == {str(occ["room_id"]): 8}


def test_api_swap_seats() -> None:
    session = _kelebek_oturumu()
    services.distribute_session(session, seed=42)
    a, b = list(
        SeatAssignment.objects.filter(session=session, class_label="9/A").order_by("seat_no")
    )[:2]
    client = APIClient()

    resp = client.post(
        f"{URL}{session.pk}/swap-seats/",
        {"assignment_a": a.pk, "assignment_b": b.pk},
        format="json",
    )
    assert resp.status_code == 200
    assert {row["status"] for row in resp.data["swapped"]} == {SeatStatus.MANUAL}
    assert resp.data["report"]["is_valid"] is True

    bad = client.post(
        f"{URL}{session.pk}/swap-seats/",
        {"assignment_a": "abc", "assignment_b": b.pk},
        format="json",
    )
    assert bad.status_code == 400
