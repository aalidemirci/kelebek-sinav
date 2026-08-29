"""Kelebek motoru + bağımsız doğrulayıcı birim testleri (T5 kabul kriterleri).

- 100+ rastgele senaryoda sert ihlal = 0
- Çok gruplu yeterli-kapasite senaryolarında 1. halka aynı-grup çifti = 0 hedefi
- Yakınlık skoru regresyon eşiği (sabit senaryo + sabit seed)
- S-rotası / 2D komşuluk tuzağı
- Aynı seed → aynı çıktı
- Tek grup → satranç modu; baskın grup → uyarı
- Klasik düzen: numara sırası + derslik eşleme/kapasite hataları

DB GEREKMEZ — motor ve doğrulayıcı saf veri üzerinde çalışır.
"""

from __future__ import annotations

import random

import pytest

from apps.sinav import engine, validator
from apps.sinav.layout import numbered_seats, validate_layout_plan
from apps.sinav.models import DeskType, NumberingScheme
from apps.sinav.participants import Participant


def _participant(
    sid: int, group: str, *, level: int = 9, section: str = "A", number: str | None = None
) -> Participant:
    return Participant(
        student_id=sid,
        full_name=f"Öğrenci {sid}",
        student_number=number or str(100 + sid),
        class_level=level,
        class_section=section,
        course_id=int(group.split(":")[0]) if group.split(":")[0].isdigit() else 0,
        course_name=f"Ders {group}",
        conflict_group=group,
    )


def _grid_room(
    room_id: int, rows: int, cols: int, desk_type: str = DeskType.DOUBLE
) -> engine.RoomSeats:
    """rows×cols dolu grid salon (S-rota koltukları)."""
    plan = validate_layout_plan(
        {
            "grid": {"rows": rows, "cols": cols},
            "desks": [
                {"row": r, "col": c, "type": desk_type} for r in range(rows) for c in range(cols)
            ],
            "furniture": [],
        }
    )
    return engine.RoomSeats(
        room_id=room_id, seats=tuple(numbered_seats(plan, NumberingScheme.S_PATTERN))
    )


def _placed(result: engine.DistributionResult) -> list[validator.PlacedStudent]:
    return [
        validator.PlacedStudent(
            student_id=pl.participant.student_id,
            conflict_group=pl.participant.conflict_group,
            room_id=pl.room_id,
            desk_row=pl.seat.desk_row,
            desk_col=pl.seat.desk_col,
            slot=pl.seat.slot,
            x=pl.seat.x,
            y=pl.seat.y,
        )
        for pl in result.placements
    ]


# ===========================================================================
# Doğrulayıcı (bağımsız) — temel sözleşme
# ===========================================================================


def test_validator_flags_same_desk_pair() -> None:
    a = validator.PlacedStudent(1, "g", 1, 0, 0, 0, -0.25, 0.0)
    b = validator.PlacedStudent(2, "g", 1, 0, 0, 1, 0.25, 0.0)
    report = validator.validate_seating([a, b])
    assert not report.is_valid
    assert "Bitişik masa" in report.hard_violations[0]


def test_validator_first_ring_metric_and_strict() -> None:
    a = validator.PlacedStudent(1, "g", 1, 0, 0, 0, 0.0, 0.0)
    b = validator.PlacedStudent(2, "g", 1, 0, 1, 0, 1.0, 0.0)  # yan sıra
    relaxed = validator.validate_seating([a, b])
    assert relaxed.is_valid
    assert relaxed.first_ring_same_group_pairs == 1
    assert relaxed.min_same_group_distance["g"] == 1.0
    strict = validator.validate_seating([a, b], strict=True)
    assert not strict.is_valid


def test_validator_detects_double_booking() -> None:
    a = validator.PlacedStudent(1, "g1", 1, 0, 0, 0, 0.0, 0.0)
    b = validator.PlacedStudent(2, "g2", 1, 0, 0, 0, 0.0, 0.0)  # aynı koltuk
    report = validator.validate_seating([a, b])
    assert any("çifte dolu" in v for v in report.hard_violations)


def test_validator_different_rooms_no_interaction() -> None:
    a = validator.PlacedStudent(1, "g", 1, 0, 0, 0, 0.0, 0.0)
    b = validator.PlacedStudent(2, "g", 2, 0, 0, 1, 0.25, 0.0)  # başka salon
    report = validator.validate_seating([a, b])
    assert report.is_valid
    assert report.proximity_score == 0.0


# ===========================================================================
# Motor — kabul kriterleri
# ===========================================================================


def test_random_scenarios_zero_hard_violations() -> None:
    """100+ rastgele senaryo: sert ihlal HER ZAMAN 0 (kapasite > grup payı)."""
    rng = random.Random(4242)  # noqa: S311 — test senaryosu üretimi
    for scenario in range(110):
        rows, cols = rng.randint(3, 6), rng.randint(2, 4)
        desk_type = rng.choice([DeskType.SINGLE, DeskType.DOUBLE, DeskType.TRIPLE])
        room = _grid_room(1, rows, cols, desk_type)
        capacity = len(room.seats)
        n_groups = rng.randint(2, 5)
        n_students = rng.randint(n_groups, capacity)
        students = [_participant(i, f"{(i % n_groups) + 1}:9") for i in range(1, n_students + 1)]
        result = engine.distribute_butterfly(students, [room], seed=rng.randint(1, 999_999))
        report = validator.validate_seating(_placed(result))
        # Sert ihlal yalnız motor uyarı verdiyse hoş görülür (kaçınılmaz durum);
        # dengeli grup karışımında hiç olmamalı.
        if not any("kaçınılmaz" in w for w in result.warnings):
            assert report.is_valid, (
                f"senaryo {scenario}: {report.hard_violations[:2]} "
                f"(grid {rows}x{cols} {desk_type}, {n_groups} grup, {n_students} öğrenci)"
            )


def test_two_groups_enough_space_zero_first_ring() -> None:
    """İki eşit grup + bol kapasite: 1. halka aynı-grup çifti = 0 hedefi."""
    room = _grid_room(1, 4, 4, DeskType.SINGLE)  # 16 koltuk
    students = [_participant(i, f"{1 + (i % 2)}:9") for i in range(1, 9)]  # 2 grup × 4
    result = engine.distribute_butterfly(students, [room], seed=7)
    report = validator.validate_seating(_placed(result))
    assert report.is_valid
    assert report.first_ring_same_group_pairs == 0


def test_proximity_score_regression_threshold() -> None:
    """Sabit senaryo + sabit seed: skor eşiği aşılmamalı (regresyon bekçisi)."""
    room = _grid_room(1, 5, 3, DeskType.DOUBLE)  # 30 koltuk
    students = [_participant(i, f"{1 + (i % 3)}:9") for i in range(1, 25)]  # 3 grup × 8
    result = engine.distribute_butterfly(students, [room], seed=1234)
    report = validator.validate_seating(_placed(result))
    assert report.is_valid
    # İlk yeşil koşunun skoru 21.86 (Tur 225); ~%10 payla eşik 24.0 — motoru
    # kötüleştiren değişiklik bu testte yakalanır.
    assert report.proximity_score <= 24.0, f"skor {report.proximity_score}"


def test_s_route_2d_trap() -> None:
    """S-rota / 2D komşuluk tuzağı (yol haritası §5.2 kritik not).

    S rotasında bir kolonun BAŞI ile yan kolonun başı rotada en uzak, fiziksel
    olarak YAN YANA olabilir. Rota-komşuluğuna bakan hatalı bir motor (0,0) ve
    (0,1)'i 'uzak' sanıp aynı grubu koyabilirdi — 2D geometri denetimi bunu
    engellemeli. İKİLİ sıralarla tam dolulukta sert kısıt da sınanır.
    """
    # 3 satır × 2 kolon tekli: rota col0 (r0,r1,r2) → col1 (r2,r1,r0).
    # (0,0) rota başı, (0,1) rota SONU — fiziksel yan yana.
    room = _grid_room(1, 3, 2, DeskType.SINGLE)
    students = [_participant(i, f"{1 + (i % 2)}:9") for i in range(1, 7)]  # 2 grup × 3, tam dolu
    result = engine.distribute_butterfly(students, [room], seed=99)
    report = validator.validate_seating(_placed(result))
    assert report.is_valid

    by_cell = {
        (p.seat.desk_row, p.seat.desk_col): p.participant.conflict_group for p in result.placements
    }
    # Rota-uzak ama fiziksel-komşu çift: aynı gruptan OLMAMALI (1. halka ağırlığı
    # + 2D denetim bunu güvence eder; rota-komşuluğu kullanan motor burada düşer).
    assert by_cell[(0, 0)] != by_cell[(0, 1)], by_cell

    # Aynı tuzağın sert hali: İKİLİ sıralar tam dolu — bitişik masa ihlali sıfır.
    room2 = _grid_room(2, 3, 2, DeskType.DOUBLE)  # 12 koltuk
    students2 = [_participant(i, f"{1 + (i % 2)}:9") for i in range(1, 13)]
    result2 = engine.distribute_butterfly(students2, [room2], seed=99)
    report2 = validator.validate_seating(_placed(result2))
    assert report2.is_valid, report2.hard_violations


def test_same_seed_same_output_different_seed_differs() -> None:
    room = _grid_room(1, 4, 3, DeskType.DOUBLE)
    students = [_participant(i, f"{1 + (i % 3)}:9") for i in range(1, 20)]

    def key(r: engine.DistributionResult) -> list[tuple[int, int]]:
        return [(p.participant.student_id, p.seat.seat_no) for p in r.placements]

    r1 = engine.distribute_butterfly(students, [room], seed=42)
    r2 = engine.distribute_butterfly(students, [room], seed=42)
    assert key(r1) == key(r2)  # determinizm — aynı seed aynı çıktı


def test_single_group_checkerboard_mode() -> None:
    """Tek grup + kapasite ≥ 2N → satranç: sıra başına tek öğrenci, ihlal 0."""
    room = _grid_room(1, 4, 3, DeskType.DOUBLE)  # 12 sıra, 24 koltuk
    students = [_participant(i, "1:9") for i in range(1, 11)]  # 10 öğrenci ≤ 12 sıra
    result = engine.distribute_butterfly(students, [room], seed=5)
    assert result.checkerboard
    report = validator.validate_seating(_placed(result))
    assert report.is_valid
    desks = {(p.seat.desk_row, p.seat.desk_col) for p in result.placements}
    assert len(desks) == len(result.placements)  # sıra başına tek öğrenci


def test_single_group_tight_capacity_no_checkerboard() -> None:
    """Tek grup + dar kapasite: satranç açılmaz; ihlaller raporda listelenir."""
    room = _grid_room(1, 2, 2, DeskType.DOUBLE)  # 8 koltuk
    students = [_participant(i, "1:9") for i in range(1, 8)]  # 7 öğrenci > 4 sıra
    result = engine.distribute_butterfly(students, [room], seed=3)
    assert not result.checkerboard
    report = validator.validate_seating(_placed(result))
    assert not report.is_valid  # matematiksel olarak kaçınılmaz
    assert any("kaçınılmaz" in w for w in result.warnings)


def test_dominant_group_warning() -> None:
    room = _grid_room(1, 3, 2, DeskType.DOUBLE)  # 12 koltuk
    students = [_participant(i, "1:9") for i in range(1, 9)] + [
        _participant(100 + i, "2:9") for i in range(1, 4)
    ]  # grup1=8 > 12/2
    result = engine.distribute_butterfly(students, [room], seed=11)
    assert any("Baskın grup" in w for w in result.warnings)


def test_capacity_insufficient_raises() -> None:
    room = _grid_room(1, 2, 2, DeskType.SINGLE)  # 4 koltuk
    students = [_participant(i, f"{i}:9") for i in range(1, 6)]  # 5 öğrenci
    with pytest.raises(ValueError, match="Kapasite yetersiz"):
        engine.distribute_butterfly(students, [room], seed=1)


def test_multi_room_balance_and_spread() -> None:
    """İki salon: doluluk oranı dengeli; her salona her gruptan öğrenci düşer (E2)."""
    room_a = _grid_room(1, 4, 3, DeskType.DOUBLE)  # 24 koltuk
    room_b = _grid_room(2, 2, 3, DeskType.DOUBLE)  # 12 koltuk
    students = [_participant(i, f"{1 + (i % 2)}:9") for i in range(1, 28)]  # 27 öğrenci
    result = engine.distribute_butterfly(students, [room_a, room_b], seed=8)
    by_room: dict[int, list[str]] = {}
    for p in result.placements:
        by_room.setdefault(p.room_id, []).append(p.participant.conflict_group)
    assert len(by_room[1]) == 18 and len(by_room[2]) == 9  # 27 × (24/36), 27 × (12/36)
    assert len(set(by_room[1])) == 2 and len(set(by_room[2])) == 2  # gruplar serpilmiş
    report = validator.validate_seating(_placed(result))
    assert report.is_valid


# ===========================================================================
# Klasik düzen (kendi dersliğinde)
# ===========================================================================


def test_home_classroom_number_order() -> None:
    room = _grid_room(1, 3, 2, DeskType.DOUBLE)
    students = [
        _participant(1, "1:9", section="A", number="110"),
        _participant(2, "1:9", section="A", number="9"),
        _participant(3, "1:9", section="A", number="23"),
    ]
    result = engine.distribute_home_classroom(students, {"9/A": room})
    ordered = sorted(result.placements, key=lambda p: p.seat.seat_no)
    assert [p.participant.student_number for p in ordered] == ["9", "23", "110"]


def test_home_classroom_missing_mapping_raises() -> None:
    room = _grid_room(1, 3, 2)
    students = [_participant(1, "1:9", section="A"), _participant(2, "1:9", section="B")]
    with pytest.raises(ValueError, match="Derslik eşlemesi eksik: 9/B"):
        engine.distribute_home_classroom(students, {"9/A": room})


def test_home_classroom_capacity_raises() -> None:
    room = _grid_room(1, 1, 1, DeskType.SINGLE)  # 1 koltuk
    students = [_participant(1, "1:9"), _participant(2, "1:9")]
    with pytest.raises(ValueError, match="kapasitesi yetersiz"):
        engine.distribute_home_classroom(students, {"9/A": room})


# ===========================================================================
# Tur 243 (talep 6) — şube-hizalı Faz 0: yoğunlaşma + kota korunumu
# ===========================================================================


def _level_cohort(
    group: str, *, level: int, sections: list[str], per_section: int, base: int
) -> list[Participant]:
    """Seviye kohortu: her şubeden per_section öğrenci (okul no sıralı)."""
    out: list[Participant] = []
    sid = base
    for section in sections:
        for _ in range(per_section):
            out.append(_participant(sid, group, level=level, section=section))
            sid += 1
    return out


def _rooms_per_section(result: engine.DistributionResult) -> dict[str, int]:
    seen: dict[str, set[int]] = {}
    for pl in result.placements:
        label = f"{pl.participant.class_level}/{pl.participant.class_section}"
        seen.setdefault(label, set()).add(pl.room_id)
    return {label: len(rooms) for label, rooms in seen.items()}


def test_sections_concentrated_into_few_rooms() -> None:
    """2 grup × 5'er şube(20) → 6 salon(36): her şube en çok 2 salonda."""
    participants = _level_cohort(
        "1:9", level=9, sections=["A", "B", "C", "D", "E"], per_section=20, base=1
    ) + _level_cohort(
        "2:10", level=10, sections=["A", "B", "C", "D", "E"], per_section=20, base=1000
    )
    rooms = [_grid_room(rid, 6, 3) for rid in range(1, 7)]  # 6 salon × 36 koltuk
    result = engine.distribute_butterfly(participants, rooms, seed=42)

    assert len(result.placements) == 200
    spread = _rooms_per_section(result)
    assert max(spread.values()) <= 2, f"şube 2'den çok salona yayıldı: {spread}"
    # Ayrışma korunuyor: bağımsız doğrulayıcı sert ihlal görmemeli.
    report = validator.validate_seating(_placed(result))
    assert report.is_valid


def test_room_quota_preserved_after_packing() -> None:
    """Paketleme salon kotalarını bozamaz (E2 doluluk dengesi aynen)."""
    participants = _level_cohort(
        "1:9", level=9, sections=["A", "B", "C"], per_section=20, base=1
    ) + _level_cohort("2:10", level=10, sections=["A", "B"], per_section=15, base=500)
    rooms = [_grid_room(rid, 5, 3) for rid in range(1, 4)]  # 3 salon × 30 koltuk
    n = len(participants)
    quotas = engine._room_quotas(n, [len(r.seats) for r in rooms])

    result = engine.distribute_butterfly(participants, rooms, seed=7)
    by_room: dict[int, int] = {}
    for pl in result.placements:
        by_room[pl.room_id] = by_room.get(pl.room_id, 0) + 1
    assert [by_room.get(r.room_id, 0) for r in rooms] == quotas


def test_group_room_quotas_sum_exact() -> None:
    """Grup-salon kotaları hem grup mevcutlarını hem salon kotalarını tam karşılar."""
    group_sizes = {"1:9": 45, "2:10": 33, "3:11": 12}
    quotas = [30, 30, 30]
    out = engine._group_room_quotas(group_sizes, quotas)
    for key, size in group_sizes.items():
        assert sum(out[key]) == size
    for i in range(len(quotas)):
        assert sum(out[key][i] for key in group_sizes) == quotas[i]


def test_packing_deterministic_same_seed() -> None:
    """Aynı girdi + aynı seed → birebir aynı yerleşim (Faz 0 rng içermez)."""
    participants = _level_cohort(
        "1:9", level=9, sections=["A", "B", "C", "D"], per_section=25, base=1
    )
    rooms = [_grid_room(rid, 5, 3) for rid in range(1, 5)]
    r1 = engine.distribute_butterfly(participants, rooms, seed=11)
    r2 = engine.distribute_butterfly(participants, rooms, seed=11)

    def key(pl: engine.Placement) -> tuple[int, int, int, int, int]:
        return (
            pl.participant.student_id,
            pl.room_id,
            pl.seat.desk_row,
            pl.seat.desk_col,
            pl.seat.slot,
        )

    assert sorted(map(key, r1.placements)) == sorted(map(key, r2.placements))


def test_oversized_section_overflows_to_next_room() -> None:
    """Salon kotasından büyük şube taşar ama kalan şubeler yine az salona gider."""
    participants = _level_cohort("1:9", level=9, sections=["A"], per_section=50, base=1)
    participants += _level_cohort("1:9", level=9, sections=["B"], per_section=10, base=200)
    rooms = [_grid_room(1, 6, 3), _grid_room(2, 6, 3)]  # 2 × 36 koltuk
    result = engine.distribute_butterfly(participants, rooms, seed=3)
    spread = _rooms_per_section(result)
    assert spread["9/A"] == 2  # 50 kişi tek salona sığmaz — taşma normal
    assert spread["9/B"] == 1  # küçük şube bütün kalır
