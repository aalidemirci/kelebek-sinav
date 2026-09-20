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
from apps.sinav import layout, services
from apps.sinav.models import (
    ExamRoom,
    ExamSession,
    ExamSessionRoom,
    ExamSessionStatus,
    RuleScope,
    RuleType,
    SeatAssignment,
    SeatStatus,
)
from apps.sinav.tests.oturum_yardim import dagitilmis_oturum as _dagitilmis_oturum
from apps.sinav.tests.oturum_yardim import oturum, salon

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
    assert "kural ihlali var" in message and "sert kısıt" not in message
    assert "AD0" not in message and "SOYAD" not in message  # kurucu ad kalıbı sızmadı


def test_revert_to_draft_clears_seating_keeps_definitions() -> None:
    """DAĞITILDI → TASLAK (18.09.2026): yerleşim silinir, tanım korunur, yeniden dağıtılır."""
    session = _dagitilmis_oturum()
    course_count = session.courses.count()
    room_count = session.rooms.count()
    assert SeatAssignment.objects.filter(session=session).exists()
    assert session.distribution_params.get("seed") is not None

    session = services.revert_session_to_draft(session)
    assert session.status == ExamSessionStatus.DRAFT
    assert session.distribution_params == {}
    assert not SeatAssignment.objects.filter(session=session).exists()
    # Sihirbaz Adım 2-3 dolu döner: ders/salon satırlarına dokunulmaz.
    assert session.courses.count() == course_count
    assert session.rooms.count() == room_count

    # Taslak yeniden düzenlenebilir ve yeniden dağıtılabilir (tam döngü).
    services.update_exam_session(session, name="Düzeltilmiş Oturum")
    session, _result, report = services.distribute_session(session, seed=3)
    assert session.status == ExamSessionStatus.DISTRIBUTED and report.is_valid
    assert SeatAssignment.objects.filter(session=session).exists()


def test_revert_to_draft_guards() -> None:
    draft = oturum(name="Taslak Oturum")
    with pytest.raises(ValidationError, match="yalnız dağıtılmış"):
        services.revert_session_to_draft(draft)

    session = _dagitilmis_oturum()
    services.approve_session(session)
    with pytest.raises(ValidationError, match="yalnız dağıtılmış"):
        services.revert_session_to_draft(session)


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


def test_api_revert_to_draft() -> None:
    session = _dagitilmis_oturum()
    client = APIClient()
    base = f"/api/v1/exam-sessions/{session.pk}"

    resp = client.post(f"{base}/revert-to-draft/")
    assert resp.status_code == 200 and resp.data["status"] == "DRAFT"
    assert client.post(f"{base}/revert-to-draft/").status_code == 400  # taslak yeniden alınamaz


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

    # A12: kuralla sabitlenmiş koltuk takasla sessizce bozulmaz (ret okul no ile, adsız).
    SeatAssignment.objects.filter(pk=rows[0].pk).update(status=SeatStatus.PINNED)
    with pytest.raises(ValidationError, match="yerleştirme kuralıyla sabitlenmiş") as excinfo:
        services.swap_seats(session, assignment_a_id=rows[0].pk, assignment_b_id=rows[1].pk)
    assert rows[0].student_number in str(excinfo.value)
    assert rows[0].full_name not in str(excinfo.value)
    SeatAssignment.objects.filter(pk=rows[0].pk).update(status=SeatStatus.NORMAL)

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


# ===========================================================================
# Boş koltuğa taşıma (sürükle-bırak'ın takas OLMAYAN yarısı)
# ===========================================================================


def _bos_koltuk(session: ExamSession, room: ExamRoom) -> layout.Seat:
    """Salondaki ilk BOŞ koltuk (plan sırasına göre)."""
    dolu = {
        (a.desk_row, a.desk_col, a.slot)
        for a in SeatAssignment.objects.filter(session=session, room=room)
    }
    for seat in services.room_seats(room):
        if (seat.desk_row, seat.desk_col, seat.slot) not in dolu:
            return seat
    raise AssertionError("Salonda boş koltuk kalmadı (test kurulumu).")


def test_move_seat_to_empty_marks_manual_and_renumbers() -> None:
    """Taşınan satır hedefin plan numarasını alır ve ELLE işaretlenir."""
    session = _dagitilmis_oturum(per_level=3)  # 6 öğrenci, 8 koltuk → 2 boş
    room = ExamRoom.objects.get(session_rooms__session=session)
    row = SeatAssignment.objects.filter(session=session).order_by("seat_no").first()
    assert row is not None
    eski_damga = row.updated_at
    hedef = _bos_koltuk(session, room)

    moved, report = services.move_seat(
        session,
        assignment_id=row.pk,
        room_id=room.pk,
        desk_row=hedef.desk_row,
        desk_col=hedef.desk_col,
        slot=hedef.slot,
    )

    assert (moved.desk_row, moved.desk_col, moved.slot) == (
        hedef.desk_row,
        hedef.desk_col,
        hedef.slot,
    )
    # Koltuk numarası taşınan satırdan DEĞİL, hedef salonun planından gelir.
    assert moved.seat_no == hedef.seat_no
    assert moved.status == SeatStatus.MANUAL
    assert report.is_valid, report.hard_violations
    # Kitapçık bayatlık damgası ilerlemeli (CLAUDE.md §3).
    assert moved.updated_at > eski_damga


def test_move_seat_across_rooms() -> None:
    """Hedef başka bir oturum salonu olabilir (salonlar arası taşıma)."""
    session = _dagitilmis_oturum(rooms=2, per_level=4)
    row = SeatAssignment.objects.filter(session=session).order_by("seat_no").first()
    assert row is not None
    other = ExamRoom.objects.filter(session_rooms__session=session).exclude(pk=row.room_id).first()
    assert other is not None
    hedef = _bos_koltuk(session, other)

    moved, _report = services.move_seat(
        session,
        assignment_id=row.pk,
        room_id=other.pk,
        desk_row=hedef.desk_row,
        desk_col=hedef.desk_col,
        slot=hedef.slot,
    )
    assert moved.room_id == other.pk and moved.seat_no == hedef.seat_no


def test_move_seat_guards() -> None:
    session = _dagitilmis_oturum(per_level=3)
    room = ExamRoom.objects.get(session_rooms__session=session)
    row = SeatAssignment.objects.filter(session=session).order_by("seat_no").first()
    assert row is not None
    hedef = _bos_koltuk(session, room)

    def tasi(**kwargs: object) -> None:
        cagri: dict[str, object] = {
            "assignment_id": row.pk,
            "room_id": room.pk,
            "desk_row": hedef.desk_row,
            "desk_col": hedef.desk_col,
            "slot": hedef.slot,
        }
        cagri.update(kwargs)
        services.move_seat(session, **cagri)  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="bulunamadı"):
        tasi(assignment_id=987654)
    with pytest.raises(ValidationError, match="zaten bu koltukta"):
        tasi(desk_row=row.desk_row, desk_col=row.desk_col, slot=row.slot)
    with pytest.raises(ValidationError, match="planında yok"):
        tasi(desk_row=9)

    # Dolu koltuğa taşıma reddedilir — orası takasın işidir.
    komsu = SeatAssignment.objects.filter(session=session).exclude(pk=row.pk).first()
    assert komsu is not None
    with pytest.raises(ValidationError, match="başka bir öğrenci var"):
        tasi(desk_row=komsu.desk_row, desk_col=komsu.desk_col, slot=komsu.slot)

    # Oturumun salonlarından olmayan salon.
    yabanci = salon("D-999")
    with pytest.raises(ValidationError, match="salonlarından değil"):
        tasi(room_id=yabanci.pk)

    # A12: kuralla sabitlenmiş koltuk taşımayla da bozulmaz; ret ADSIZDIR.
    SeatAssignment.objects.filter(pk=row.pk).update(status=SeatStatus.PINNED)
    with pytest.raises(ValidationError, match="yerleştirme kuralıyla sabitlenmiş") as excinfo:
        tasi()
    assert row.student_number in str(excinfo.value)
    assert row.full_name not in str(excinfo.value)
    SeatAssignment.objects.filter(pk=row.pk).update(status=SeatStatus.NORMAL)

    services.approve_session(session)
    with pytest.raises(ValidationError, match="yalnız dağıtılmış"):
        tasi()


def test_move_seat_kapasite_sinirini_asamaz() -> None:
    """Kapasite sınırı dağıtımda rota başından uygulanır; elle taşıma da aşamaz."""
    session = _dagitilmis_oturum(per_level=3)  # 8 koltuklu salon, 6 öğrenci
    session_room = ExamSessionRoom.objects.get(session=session)
    hedef = _bos_koltuk(session, session_room.room)
    # Dağıtımdan SONRA daraltılan sınır (idareci salonun bir kısmını kapattı).
    ExamSessionRoom.objects.filter(pk=session_room.pk).update(capacity_override=hedef.seat_no - 1)
    row = SeatAssignment.objects.filter(session=session).order_by("seat_no").first()
    assert row is not None

    with pytest.raises(ValidationError, match="kapasite sınırı"):
        services.move_seat(
            session,
            assignment_id=row.pk,
            room_id=session_room.room_id,
            desk_row=hedef.desk_row,
            desk_col=hedef.desk_col,
            slot=hedef.slot,
        )


def test_move_seat_tek_basina_oturma_kuralini_bozmaz() -> None:
    """ "Tek başına otursun" kuralıyla boşaltılan kardeş koltuğa öğrenci konamaz.

    Dağıtım bu koltukları motora HİÇ vermez (sahte SeatAssignment yazılmaz), bu
    yüzden boş görünürler — elle taşımada kural burada korunur (A12 deseni).
    """
    session = _dagitilmis_oturum(rooms=2, per_level=3)
    ilk = SeatAssignment.objects.filter(session=session).order_by("pk").first()
    assert ilk is not None and ilk.student_id is not None
    services.create_placement_rule(
        student_id=ilk.student_id,
        rule_type=RuleType.FIXED_ROOM,
        scope=RuleScope.SESSION,
        session=session,
        target_room_id=ilk.room_id,
        solo_desk=True,
    )
    session, _result, _report = services.distribute_session(session, seed=42)

    yalniz = SeatAssignment.objects.get(session=session, student_id=ilk.student_id)
    assert yalniz.status == SeatStatus.PINNED
    kardes = next(
        s
        for s in services.room_seats(ExamRoom.objects.get(pk=yalniz.room_id))
        if (s.desk_row, s.desk_col) == (yalniz.desk_row, yalniz.desk_col) and s.slot != yalniz.slot
    )
    baskasi = SeatAssignment.objects.filter(session=session).exclude(pk=yalniz.pk).first()
    assert baskasi is not None

    with pytest.raises(ValidationError, match="tek başına ayrılmıştır") as excinfo:
        services.move_seat(
            session,
            assignment_id=baskasi.pk,
            room_id=yalniz.room_id,
            desk_row=kardes.desk_row,
            desk_col=kardes.desk_col,
            slot=kardes.slot,
        )
    # KVKK: gerekçede okul numarası geçer, ad geçmez.
    assert yalniz.student_number in str(excinfo.value)
    assert yalniz.full_name not in str(excinfo.value)


def test_api_move_seat() -> None:
    session = _dagitilmis_oturum(per_level=3)
    room_id = ExamSessionRoom.objects.get(session=session).room_id
    room = ExamRoom.objects.get(pk=room_id)
    row = SeatAssignment.objects.filter(session=session).order_by("seat_no").first()
    assert row is not None
    hedef = _bos_koltuk(session, room)
    client = APIClient()
    url = f"/api/v1/exam-sessions/{session.pk}/move-seat/"

    resp = client.post(
        url,
        {
            "assignment": row.pk,
            "room": room_id,
            "desk_row": hedef.desk_row,
            "desk_col": hedef.desk_col,
            "slot": hedef.slot,
        },
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["moved"]["seat_no"] == hedef.seat_no
    assert resp.data["moved"]["status"] == SeatStatus.MANUAL
    assert "is_valid" in resp.data["report"]

    eksik = client.post(url, {"assignment": row.pk, "room": room_id}, format="json")
    assert eksik.status_code == 400
