"""Oturum durum makinesi testleri — onay/kilit/arşiv + koltuk takası (T9/T11 çekirdeği).

OYS `test_session_lifecycle.py`'den KS'ye uyarlandı: RBAC/AccessLog düştü
(authsuz tek kullanıcı), R1-R9/ZIP evrak testleri `test_reports.py`'de (F4);
onay damgası kullanıcı yerine ad-snapshot'tır (B12). Kabul kriteri çekirdeği
korunur: onaylı oturum değiştirilemez; onay yalnız İHLAL=0 yerleşimde.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.okul.models import SchoolConfig
from apps.sinav import services
from apps.sinav.models import (
    ExamSession,
    ExamSessionStatus,
    RuleScope,
    RuleType,
    SeatAssignment,
    SeatStatus,
)
from apps.sinav.tests.oturum_yardim import dagitilmis_oturum as _dagitilmis_oturum
from apps.sinav.tests.oturum_yardim import oturum

pytestmark = pytest.mark.django_db


def _corrupt_with_violation(session: ExamSession) -> None:
    """Aynı çakışma grubundan iki öğrenciyi aynı sıraya taşır (sert ihlal)."""
    first = SeatAssignment.objects.filter(session=session).order_by("seat_no").first()
    assert first is not None
    other = (
        SeatAssignment.objects.filter(session=session, conflict_group=first.conflict_group)
        .exclude(pk=first.pk)
        .first()
    )
    assert other is not None
    other.room_id = first.room_id
    other.desk_row = first.desk_row
    other.desk_col = first.desk_col
    other.slot = 0 if first.slot == 1 else 1
    other.seat_no = 99  # salon içi tekillik korunur
    other.save()


# ===========================================================================
# Durum geçişleri + kilit
# ===========================================================================


def test_approve_reopen_archive_flow() -> None:
    session = _dagitilmis_oturum()

    session = services.approve_session(session, approved_by_name="Örnek MÜDÜR")
    assert session.status == ExamSessionStatus.APPROVED
    assert session.approved_by_name == "Örnek MÜDÜR" and session.approved_at is not None

    # Yeniden açma onay damgalarını temizler.
    session = services.reopen_session(session)
    assert session.status == ExamSessionStatus.DISTRIBUTED
    assert session.approved_by_name == "" and session.approved_at is None

    services.approve_session(session, approved_by_name="Örnek MÜDÜR")
    session = services.archive_session(session)
    assert session.status == ExamSessionStatus.ARCHIVED

    # Arşiv salt-okunur: geri açılamaz, yeniden onaylanamaz.
    with pytest.raises(ValidationError, match="yalnız onaylı oturum"):
        services.reopen_session(session)
    with pytest.raises(ValidationError, match="yalnız dağıtılmış"):
        services.approve_session(session)


def test_approve_default_stamp_is_principal() -> None:
    """Ad verilmezse kurulumdaki müdür adı damgalanır (B12)."""
    SchoolConfig.objects.create(pk=SchoolConfig.SINGLETON_PK, principal_name="Örnek MÜDÜR")
    session = _dagitilmis_oturum()
    session = services.approve_session(session)
    assert session.approved_by_name == "Örnek MÜDÜR"


def test_approve_guards() -> None:
    draft = oturum(name="Taslak Oturum")
    with pytest.raises(ValidationError, match="yalnız dağıtılmış"):
        services.approve_session(draft)
    with pytest.raises(ValidationError, match="yalnız onaylı"):
        services.archive_session(draft)

    # İhlalli yerleşim onaylanamaz; mesaj SAYI içerir, öğrenci adı ASLA (KVKK).
    session = _dagitilmis_oturum()
    _corrupt_with_violation(session)
    with pytest.raises(ValidationError) as exc_info:
        services.approve_session(session)
    message = str(exc_info.value)
    assert "sert kısıt ihlali" in message
    assert "AD0" not in message and "SOYAD" not in message  # kurucu ad kalıbı sızmadı


def test_locked_session_rejects_edits() -> None:
    session = _dagitilmis_oturum()
    services.approve_session(session)

    with pytest.raises(ValidationError, match="yalnız taslak"):
        services.update_exam_session(session, name="Yeni Ad")
    with pytest.raises(ValidationError, match="yalnız taslak"):
        services.set_session_rooms(session, [])
    with pytest.raises(ValidationError, match="yeniden dağıtılamaz"):
        services.distribute_session(session, seed=1)

    # T9 kilidi: onaylı oturuma SESSION kapsamlı kural eklenemez.
    student_id = int(
        SeatAssignment.objects.filter(session=session).values_list("student_id", flat=True)[0]
    )
    with pytest.raises(ValidationError, match="kural eklenemez"):
        services.create_placement_rule(
            student_id=student_id,
            rule_type=RuleType.FRONT_ROW,
            scope=RuleScope.SESSION,
            session=session,
        )


# ===========================================================================
# API — durum makinesi (auth yok: çıplak istemci)
# ===========================================================================


def test_api_lifecycle() -> None:
    session = _dagitilmis_oturum()
    client = APIClient()
    base = f"/api/v1/exam-sessions/{session.pk}"

    resp = client.post(f"{base}/approve/", {"approved_by_name": "Örnek MÜDÜR"}, format="json")
    assert resp.status_code == 200 and resp.data["status"] == "APPROVED"
    assert resp.data["approved_by_name"] == "Örnek MÜDÜR"
    assert client.post(f"{base}/approve/").status_code == 400  # ikinci onay ret
    assert client.post(f"{base}/reopen/").status_code == 200
    client.post(f"{base}/approve/")
    assert client.post(f"{base}/archive/").status_code == 200
    assert client.post(f"{base}/reopen/").status_code == 400  # arşiv geri açılamaz

    draft = oturum(name="Taslak Oturum")
    assert client.post(f"/api/v1/exam-sessions/{draft.pk}/approve/").status_code == 400


# ===========================================================================
# Koltuk takası (T11 — Tur 232)
# ===========================================================================


def test_swap_seats_marks_manual_and_reports() -> None:
    session = _dagitilmis_oturum(rooms=2, per_level=6)
    a, b = list(SeatAssignment.objects.filter(session=session).order_by("pk")[:2])
    a_seat = (a.room_id, a.desk_row, a.desk_col, a.slot, a.seat_no)
    b_seat = (b.room_id, b.desk_row, b.desk_col, b.slot, b.seat_no)

    swapped, report = services.swap_seats(session, assignment_a_id=a.pk, assignment_b_id=b.pk)
    by_pk = {row.pk: row for row in swapped}
    new_a, new_b = by_pk[a.pk], by_pk[b.pk]
    assert (new_a.room_id, new_a.desk_row, new_a.desk_col, new_a.slot, new_a.seat_no) == b_seat
    assert (new_b.room_id, new_b.desk_row, new_b.desk_col, new_b.slot, new_b.seat_no) == a_seat
    assert new_a.status == SeatStatus.MANUAL and new_b.status == SeatStatus.MANUAL
    assert report is not None  # bağımsız doğrulayıcı anlık çalıştı


def test_swap_seats_guards() -> None:
    session = _dagitilmis_oturum()
    rows = list(SeatAssignment.objects.filter(session=session)[:2])

    with pytest.raises(ValidationError, match="iki FARKLI koltuk"):
        services.swap_seats(session, assignment_a_id=rows[0].pk, assignment_b_id=rows[0].pk)
    with pytest.raises(ValidationError, match="bulunamadı"):
        services.swap_seats(session, assignment_a_id=rows[0].pk, assignment_b_id=987654)

    services.approve_session(session)
    with pytest.raises(ValidationError, match="yalnız dağıtılmış"):
        services.swap_seats(session, assignment_a_id=rows[0].pk, assignment_b_id=rows[1].pk)


def test_api_swap_seats() -> None:
    session = _dagitilmis_oturum()
    a, b = list(SeatAssignment.objects.filter(session=session).order_by("pk")[:2])
    client = APIClient()
    url = f"/api/v1/exam-sessions/{session.pk}/swap-seats/"

    resp = client.post(url, {"assignment_a": a.pk, "assignment_b": b.pk}, format="json")
    assert resp.status_code == 200
    assert {row["id"] for row in resp.data["swapped"]} == {a.pk, b.pk}
    assert "is_valid" in resp.data["report"]

    assert (
        client.post(url, {"assignment_a": "x", "assignment_b": b.pk}, format="json").status_code
        == 400
    )
