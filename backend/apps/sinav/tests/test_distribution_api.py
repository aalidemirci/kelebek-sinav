"""Dağıtım servisi + API testleri — snapshot yazımı, durum, takas, doluluk.

OYS `test_distribution_api.py`'den KS'ye uyarlandı: auth/RBAC ve AccessLog
(SENSITIVE_READ) düştü (authsuz tek kullanıcı, denetim modülü yok); GROUPS
katılımcı tipi alınmadı (TB7) — sert çakışma aynı seviyeye iki LEVEL dersiyle
kurulur. Ortak kurucular `oturum_yardim`'dan gelir.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.okul.models import Student
from apps.sinav import reports, services
from apps.sinav.models import (
    DeskType,
    ExamRoom,
    ExamSession,
    ExamSessionRoom,
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
    ihlal = next(v for v in report.hard_violations if "Katı dağıtım ihlali" in v)
    # İdareci dili: salon ADI + ders ADI + 1 tabanlı konum; ham kimlik/anahtar yok.
    assert "D-201" in ihlal and "Sınıf” sınavına giren" in ihlal and ". sütun" in ihlal
    assert "grubu" not in ihlal and "id=" not in ihlal and "(0," not in ihlal

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


def test_onde_ayni_sinav_orani_ilk_dolu_sirayi_saymaz() -> None:
    """Pay: önündeki sırada aynı sınavdan biri olan; payda: ilk dolu satırın arkasındakiler."""
    koltuklar = [
        (1, 0, "a"),  # ilk dolu satır: paydaya girmez
        (1, 0, "b"),
        (2, 0, "a"),  # önünde a var
        (2, 1, "a"),  # önünde sıra yok
        (3, 0, "b"),  # önünde yalnız a var
        (3, 1, "b"),  # önünde a var
    ]

    assert services._front_same_percent(koltuklar) == 25.0
    # Plan bilinmiyorsa (silinmiş salon) ön sıra bir satır öndedir.
    assert services._front_same_percent([(1, 0, "a"), (3, 0, "a")]) == 0.0


def test_onde_ayni_sinav_orani_plana_konmamis_satiri_atlar() -> None:
    """Önündeki sıra plandaki bir önceki sıradır: koridor bırakılan satır oranı sıfırlamaz."""
    koltuklar = [(1, 0, "a"), (3, 0, "a")]

    assert services._front_same_percent(koltuklar, [(1, 0), (3, 0)]) == 100.0
    # Planda olup boş kalan sıra gerçekten öndedir: üstünden atlanmaz.
    assert services._front_same_percent(koltuklar, [(1, 0), (2, 0), (3, 0)]) == 0.0
    # Sütununun ilk sırasındakinin önünde kimse yoktur: ilk dolu satır gibi paydaya girmez.
    assert services._front_same_percent([(1, 0, "a"), (3, 1, "a")], [(1, 0), (3, 1)]) is None


def test_onde_ayni_sinav_orani_bosluksuz_planda_plan_bilgisiyle_degismez() -> None:
    """Motor denetimi belgesindeki oran tabloları boşluksuz plandadır, geçerli kalmalıdır."""
    plan = [(satir, sutun) for satir in (1, 2, 3, 4) for sutun in (0, 1)]
    koltuklar = [
        (2, 0, "a"),  # 1. satır boş: ilk dolu satır burası
        (3, 0, "a"),
        (3, 1, "b"),
        (4, 0, "b"),
        (4, 1, "b"),
    ]

    assert services._front_same_percent(koltuklar, plan) == 50.0
    assert services._front_same_percent(koltuklar) == 50.0


def test_onde_ayni_sinav_orani_tek_ondalikla_yuvarlanir() -> None:
    """Ekran tek ondalık basar: üçte bir %33 değil %33,3 döner."""
    koltuklar = [
        (1, 0, "a"),
        (1, 1, "b"),
        (1, 2, "b"),
        (2, 0, "a"),  # önünde a var
        (2, 1, "a"),  # önünde yalnız b var
        (2, 2, "a"),  # önünde yalnız b var
    ]

    assert services._front_same_percent(koltuklar) == 33.3


def test_onde_ayni_sinav_orani_tek_dolu_satirda_hesaplanmaz() -> None:
    assert services._front_same_percent([(1, 0, "a"), (1, 1, "b")]) is None
    assert services._front_same_percent([]) is None


def test_elle_bos_satir_birakilmis_salonda_oran_sifir_gorunmez() -> None:
    """Tek sınavlı salonda herkesin önünde aynı sınav vardır; koridor bunu değiştirmez."""
    sube(9, "A", students=8, start_no=101)
    c9 = ders("Coğrafya", levels=[9])
    session = oturum()
    services.add_session_course(
        session, course_id=c9.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    plan = {
        "grid": {"rows": 5, "cols": 2},
        "desks": [{"row": r, "col": c, "type": DeskType.DOUBLE} for r in (2, 4) for c in (0, 1)],
        "furniture": [],
    }
    services.set_session_rooms(session, [{"room_id": salon("D-201", plan=plan).pk}])
    services.distribute_session(session, seed=42)

    (satir,) = services.room_exam_mix(session)

    assert satir["exam_count"] == 1
    assert satir["front_same_percent"] == 100.0


def _uc_sirali_tek_sinav_oturumu() -> ExamSession:
    """Üç tekli sıralı salonda üç öğrenci, tek sınav: her sıra doludur."""
    sube(9, "A", students=3, start_no=101)
    c9 = ders("Coğrafya", levels=[9])
    session = oturum()
    services.add_session_course(
        session, course_id=c9.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    plan = {
        "grid": {"rows": 4, "cols": 1},
        "desks": [{"row": r, "col": 0, "type": DeskType.SINGLE} for r in (1, 2, 3)],
        "furniture": [],
    }
    services.set_session_rooms(session, [{"room_id": salon("D-201", plan=plan).pk}])
    services.distribute_session(session, seed=42)
    return session


def test_planda_olup_bos_kalan_sira_salon_oraninda_atlanmaz() -> None:
    """Oran salonun PLANINDAN okunur: dolu sıralardan kurulursa boş sıranın üstünden atlar."""
    session = _uc_sirali_tek_sinav_oturumu()
    (once,) = services.room_exam_mix(session)
    assert once["front_same_percent"] == 100.0

    SeatAssignment.objects.get(session=session, desk_row=2).delete()

    (sonra,) = services.room_exam_mix(session)
    assert sonra["exam_count"] == 1
    assert sonra["front_same_percent"] == 0.0


def test_taslaga_alinan_oturumda_sinav_cesidi_listesi_bostur() -> None:
    """Silinmiş yerleşim sayılmaz: koltuklar kayıtta durur ama ekranda salon satırı kalmaz."""
    session = _kelebek_oturumu()
    services.distribute_session(session, seed=42)
    assert services.room_exam_mix(session)

    services.revert_session_to_draft(session)

    assert SeatAssignment.all_objects.filter(session=session).exists()
    assert services.room_exam_mix(session) == []
    assert APIClient().get(f"{URL}{session.pk}/seating/").data["exam_mix"] == []


def test_yerlesim_ucu_salon_basina_sinav_cesidini_verir_kayit_yazmaz() -> None:
    session = _kelebek_oturumu()
    services.distribute_session(session, seed=42)
    onceki = list(
        SeatAssignment.objects.filter(session=session)
        .order_by("pk")
        .values_list("pk", "updated_at")
    )
    parametreler = dict(ExamSession.objects.get(pk=session.pk).distribution_params)

    data = APIClient().get(f"{URL}{session.pk}/seating/").data

    (satir,) = data["exam_mix"]
    assert set(satir) == {"room_id", "exam_count", "front_same_percent"}
    assert satir["room_id"] == data["occupancy"][0]["room_id"]
    assert satir["exam_count"] == 2
    assert 0 <= satir["front_same_percent"] <= 100
    # Hesap yan etkisizdir ve dağıtım kaydına geçmez.
    sonraki = list(
        SeatAssignment.objects.filter(session=session)
        .order_by("pk")
        .values_list("pk", "updated_at")
    )
    assert sonraki == onceki
    assert ExamSession.objects.get(pk=session.pk).distribution_params == parametreler


def test_sinav_cesidi_doluluk_listesiyle_ayni_salon_sirasinda_gelir() -> None:
    """İki liste aynı ekranda durur: salon sırası kimliğe göre değil, oturuma göre dizilir."""
    session = _kelebek_oturumu(student_count=16)
    birinci = ExamSessionRoom.objects.get(session=session).room
    ikinci = salon("A-101", plan=PLAN_3X2_DOUBLE)
    services.set_session_rooms(session, [{"room_id": ikinci.pk}, {"room_id": birinci.pk}])
    services.distribute_session(session, seed=42)
    assert birinci.pk < ikinci.pk  # kimlik sırası oturum sırasının tersidir

    data = APIClient().get(f"{URL}{session.pk}/seating/").data

    doluluk = [o["room_id"] for o in data["occupancy"] if o["placed"]]
    assert doluluk == [ikinci.pk, birinci.pk]
    assert [satir["room_id"] for satir in data["exam_mix"]] == doluluk


def test_sinav_cesidi_ekranda_kalir_evraka_gitmez(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hesap dağıtım ve R8 yolunda HİÇ çağrılmaz: kayda ve evraka giden yol budur.

    Anahtar adına bakmak yetmez: oran iç içe ya da başka adla da yazılabilir. R8
    `room_occupancy`yi ve `distribution_params`ı basar, bu yüzden ikisi de sınanır.
    """

    def _cagrilmamali(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Sınav çeşidi hesabı dağıtım ya da evrak yoluna girdi")

    monkeypatch.setattr(services, "room_exam_mix", _cagrilmamali)
    monkeypatch.setattr(services, "_front_same_percent", _cagrilmamali)
    session = _kelebek_oturumu()
    services.distribute_session(session, seed=42)
    session = ExamSession.objects.get(pk=session.pk)
    services.render_session_report(session, "r8")

    assert all("front_same_percent" not in row for row in services.room_occupancy(session))
    kayit = json.dumps(session.distribution_params)
    assert not any(iz in kayit for iz in ("front_same", "exam_mix", "exam_count"))
    kaynak = Path(reports.__file__).read_text(encoding="utf-8")
    assert "front_same" not in kaynak and "exam_mix" not in kaynak


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
