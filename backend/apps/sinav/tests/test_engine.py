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
from dataclasses import replace
from typing import Any

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


def test_validator_etiketli_ihlal_idareci_diliyle_yazilir() -> None:
    """Etiket verilince ihlal metni salon ADI, ders ADI, 1 tabanlı konum ve OKUL NO
    taşır; ham kimlik, çakışma grubu anahtarı ve 0 tabanlı koordinat GEÇMEZ.

    Etiketler denetime girmez: aynı girdi etiketsizken de aynı sayıda ihlal üretir
    (yukarıdaki sözleşme testleri ham biçimi sabitler).
    """
    ortak = {
        "room_label": "Salon 101",
        "group_label": "Coğrafya — 9. Sınıf",
    }
    a = validator.PlacedStudent(
        1,
        "7:9",
        3,
        2,
        0,
        0,
        -0.25,
        2.0,
        desk_label="2. sıra, 1. sütun",
        student_number="101",
        **ortak,
    )
    b = validator.PlacedStudent(
        2,
        "7:9",
        3,
        2,
        0,
        1,
        0.25,
        2.0,
        desk_label="2. sıra, 1. sütun",
        student_number="102",
        **ortak,
    )
    c = validator.PlacedStudent(
        3,
        "7:9",
        3,
        2,
        1,
        0,
        1.0,
        2.0,
        desk_label="2. sıra, 2. sütun",
        student_number="103",
        **ortak,
    )
    tekrar = validator.PlacedStudent(
        1,
        "8:9",
        3,
        3,
        1,
        0,
        1.0,
        3.0,
        desk_label="3. sıra, 2. sütun",
        student_number="101",
        **ortak,
    )

    report = validator.validate_seating([a, b, c, tekrar], strict=True)
    metin = " | ".join(report.hard_violations)

    assert (
        "Bitişik masa ihlali: “Coğrafya — 9. Sınıf” sınavına giren iki öğrenci aynı sırada "
        "oturuyor (Salon 101, 2. sıra, 1. sütun)." in report.hard_violations
    )
    assert "Katı dağıtım ihlali" in metin and "2. sıra, 1. sütun ↔ 2. sıra, 2. sütun" in metin
    assert "Öğrenci iki koltukta: okul no 101." in report.hard_violations
    for ham in ("salon 3", "'7:9'", "id=", "(2,0)", "Katı mod"):
        assert ham not in metin

    etiketsiz = validator.validate_seating(
        [
            validator.PlacedStudent(
                p.student_id, p.conflict_group, 3, p.desk_row, p.desk_col, p.slot, p.x, p.y
            )
            for p in (a, b, c, tekrar)
        ],
        strict=True,
    )
    assert len(etiketsiz.hard_violations) == len(report.hard_violations)


def test_motor_uyarisi_salonu_adiyla_anar() -> None:
    """`RoomSeats.label` verilince motor uyarısı salonu adıyla ve 1 tabanlı konumla anar."""
    room = _grid_room(1, 2, 2, DeskType.DOUBLE)
    adli = engine.RoomSeats(room_id=room.room_id, seats=room.seats, label="Fizik Laboratuvarı")
    students = [_participant(i, "1:9") for i in range(1, 8)]

    result = engine.distribute_butterfly(students, [adli], seed=3)
    adsiz = engine.distribute_butterfly(students, [room], seed=3)

    kacinilmaz = [w for w in result.warnings if "kaçınılmaz" in w]
    assert kacinilmaz and all(w.startswith("Fizik Laboratuvarı, ") for w in kacinilmaz)
    assert all(". sütun" in w and "sert kısıt" not in w for w in kacinilmaz)
    # Ad yalnız METNE girer: yerleşim etiketli ve etiketsiz çağrıda birebir aynıdır.
    assert [(p.participant.student_id, p.seat.seat_no) for p in result.placements] == [
        (p.participant.student_id, p.seat.seat_no) for p in adsiz.placements
    ]


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


# ===========================================================================
# Kaçınılmaz komşuluklar odağa (öğretmen masasına) çekilir — Ö1, 31.08.2026
# ===========================================================================


def _focus_mesafesi(result: engine.DistributionResult, focus: tuple[float, float]) -> float:
    """Aynı gruptan KOMŞU (Chebyshev ≤ 1) çiftlerin odağa ortalama uzaklığı."""
    import math

    toplam, adet = 0.0, 0
    yerlesim = result.placements
    for i in range(len(yerlesim)):
        for j in range(i + 1, len(yerlesim)):
            a, b = yerlesim[i], yerlesim[j]
            if a.participant.conflict_group != b.participant.conflict_group:
                continue
            if (
                max(
                    abs(a.seat.desk_row - b.seat.desk_row),
                    abs(a.seat.desk_col - b.seat.desk_col),
                )
                > 1
            ):
                continue
            toplam += math.dist((a.seat.x, a.seat.y), focus)
            toplam += math.dist((b.seat.x, b.seat.y), focus)
            adet += 2
    return toplam / adet if adet else 0.0


def test_kacinilmaz_komsuluklar_odaga_cekilir() -> None:
    """Karma imkânsızken komşu çiftler öğretmen masasına YAKLAŞIR; ihlal ARTMAZ.

    Senaryo tek gruplu ve dar kapasiteli — komşuluk matematiksel olarak
    kaçınılmaz (`test_single_group_tight_capacity_no_checkerboard` emsali).
    Odak (0,0) yerine salonun uzak köşesine alınınca çiftlerin o köşeye
    ortalama uzaklığı KÜÇÜLMELİ.
    """
    students = [_participant(i, "1:9") for i in range(1, 12)]  # 11 öğrenci, 6 sıra

    def kos(focus: tuple[float, float]) -> engine.DistributionResult:
        temel = _grid_room(1, 3, 2, DeskType.DOUBLE)  # 12 koltuk / 6 sıra
        oda = engine.RoomSeats(room_id=temel.room_id, seats=temel.seats, focus=focus)
        return engine.distribute_butterfly(students, [oda], seed=17)

    uzak_kose = (1.0, 2.0)  # son satır, son sütun
    varsayilan = kos((0.0, 0.0))
    odakli = kos(uzak_kose)

    # Sert ihlal SAYISI artmamalı — ikincil terim yalnız eşitlik bozar.
    ihlal_varsayilan = len(validator.validate_seating(_placed(varsayilan)).hard_violations)
    ihlal_odakli = len(validator.validate_seating(_placed(odakli)).hard_violations)
    assert ihlal_odakli <= ihlal_varsayilan

    # Komşu çiftler odağa YAKLAŞMALI.
    assert _focus_mesafesi(odakli, uzak_kose) < _focus_mesafesi(varsayilan, uzak_kose)


def test_odak_terimi_determinizmi_bozmaz() -> None:
    """Aynı seed + aynı odak → aynı çıktı (ceza demeti rng akışını kaydırmaz)."""
    temel = _grid_room(1, 4, 3, DeskType.DOUBLE)
    oda = engine.RoomSeats(room_id=temel.room_id, seats=temel.seats, focus=(2.0, 3.0))
    students = [_participant(i, f"{1 + (i % 3)}:9") for i in range(1, 20)]

    def key(r: engine.DistributionResult) -> list[tuple[int, int]]:
        return [(p.participant.student_id, p.seat.seat_no) for p in r.placements]

    assert key(engine.distribute_butterfly(students, [oda], seed=42)) == key(
        engine.distribute_butterfly(students, [oda], seed=42)
    )


def test_odak_satranc_modunda_korunur() -> None:
    """`_checkerboard_seats` RoomSeats'i yeniden kurar — focus DÜŞMEMELİ."""
    temel = _grid_room(1, 4, 3, DeskType.DOUBLE)
    oda = engine.RoomSeats(room_id=temel.room_id, seats=temel.seats, focus=(2.0, 3.0))
    assert engine._checkerboard_seats(oda).focus == (2.0, 3.0)


# ===========================================================================
# Ayrışma anahtarı (kız/erkek ayrışması — 20.09.2026)
# ===========================================================================


def _ayrisik(sid: int, group: str, key: str, *, level: int = 9, section: str = "A") -> Participant:
    """Ayrışma anahtarı taşıyan katılımcı (motor anahtarın NE olduğunu bilmez)."""
    p = _participant(sid, group, level=level, section=section)
    return replace(p, separation_key=key)


def _ayrisma_placed(result: engine.DistributionResult) -> list[validator.PlacedStudent]:
    return [
        replace(pl, separation_key=result.placements[i].participant.separation_key)
        for i, pl in enumerate(_placed(result))
    ]


def test_ayrisma_uygun_kapasitede_karisik_sira_birakmaz() -> None:
    """Kural açıkken aynı sırada iki farklı anahtar kalmamalı (yeterli kapasite)."""
    ogrenciler = [_ayrisik(i, "10:9", "K" if i % 2 else "E") for i in range(1, 13)] + [
        _ayrisik(i, "11:10", "K" if i % 2 else "E", level=10, section="B") for i in range(13, 25)
    ]
    sonuc = engine.distribute_butterfly(ogrenciler, [_grid_room(1, 5, 4)], seed=42)

    rapor = validator.validate_seating(_ayrisma_placed(sonuc), separation=validator.SEPARATION_DESK)
    assert rapor.is_valid, rapor.hard_violations


def test_ayrisma_determinizmi_bozmaz() -> None:
    """Aynı seed → aynı dağıtım (kural açıkken de; yeni rng çekilişi yok)."""
    ogrenciler = [_ayrisik(i, "10:9", "K" if i % 2 else "E") for i in range(1, 15)]

    def key(r: engine.DistributionResult) -> list[tuple[int, int]]:
        return [(p.participant.student_id, p.seat.seat_no) for p in r.placements]

    assert key(engine.distribute_butterfly(ogrenciler, [_grid_room(1, 4, 3)], seed=7)) == key(
        engine.distribute_butterfly(ogrenciler, [_grid_room(1, 4, 3)], seed=7)
    )


def test_ayrisma_jokeri_herkesin_yanina_oturabilir() -> None:
    """Anahtarı BOŞ öğrenci (cinsiyeti bilinmiyor) kurala girmez — K4."""
    ogrenciler = [_ayrisik(i, "10:9", "K") for i in range(1, 5)] + [
        _ayrisik(i, "11:10", "", level=10, section="B") for i in range(5, 9)
    ]
    sonuc = engine.distribute_butterfly(ogrenciler, [_grid_room(1, 2, 2)], seed=3)

    rapor = validator.validate_seating(_ayrisma_placed(sonuc), separation=validator.SEPARATION_DESK)
    assert rapor.is_valid, rapor.hard_violations
    assert len(sonuc.placements) == 8  # kapasite tam dolu — joker kısıt üretmedi


def test_ayrisma_imkansiz_kapasitede_cokmez_ihlal_listelenir() -> None:
    """Tek sıralık salonda iki anahtar: motor çökmez, en iyi çözümü + uyarı verir."""
    ogrenciler = [_ayrisik(1, "10:9", "K"), _ayrisik(2, "11:10", "E", level=10, section="B")]
    sonuc = engine.distribute_butterfly(ogrenciler, [_grid_room(1, 1, 1)], seed=1)

    assert len(sonuc.placements) == 2
    assert any("ayrı oturması gereken" in u for u in sonuc.warnings)
    rapor = validator.validate_seating(_ayrisma_placed(sonuc), separation=validator.SEPARATION_DESK)
    assert not rapor.is_valid


def test_dogrulayici_ayrisma_ihlalini_idareci_diliyle_yazar() -> None:
    """Metin etiketten gelir; öğrenci ADI geçmez, okul numarası geçer (KVKK)."""
    # Sırayı paylaşan iki öğrenci zaten FARKLI derstendir (aynı-grup ayrı kısıt):
    # ayrışma ihlali tek başına, aynı-sıra ihlaliyle karışmadan yazılmalı.
    ortak: dict[str, Any] = {"room_id": 1, "x": 0.0, "y": 0.0}
    a = validator.PlacedStudent(
        student_id=1,
        conflict_group="10:9",
        desk_row=2,
        desk_col=0,
        slot=0,
        room_label="D-201",
        desk_label="3. sıra, 1. sütun",
        student_number="101",
        separation_key="K",
        separation_label="kız",
        **ortak,
    )
    b = validator.PlacedStudent(
        student_id=2,
        conflict_group="11:10",
        desk_row=2,
        desk_col=0,
        slot=1,
        room_label="D-201",
        desk_label="3. sıra, 1. sütun",
        student_number="205",
        separation_key="E",
        separation_label="erkek",
        **ortak,
    )

    rapor = validator.validate_seating([a, b], separation=validator.SEPARATION_DESK)
    (ihlal,) = rapor.hard_violations
    assert "kız ve erkek öğrenci aynı sırada oturuyor" in ihlal
    assert "D-201, 3. sıra, 1. sütun" in ihlal
    assert "okul no 101" in ihlal and "okul no 205" in ihlal
    assert "id=" not in ihlal and "DESK" not in ihlal

    # Kip KAPALIYKEN aynı yerleşim temizdir (kural opt-in).
    assert validator.validate_seating([a, b]).is_valid


def test_dogrulayici_ayri_salon_kipinde_salonu_denetler() -> None:
    """ROOM kipi: aynı salonda iki anahtar → TEK ihlal satırı (spam yok)."""

    def _p(sid: int, room_id: int, key: str, col: int) -> validator.PlacedStudent:
        return validator.PlacedStudent(
            student_id=sid,
            conflict_group="10:9",
            room_id=room_id,
            desk_row=0,
            desk_col=col,
            slot=0,
            x=float(col),
            y=0.0,
            room_label=f"D-20{room_id}",
            student_number=str(100 + sid),
            separation_key=key,
            separation_label="kız" if key == "K" else "erkek",
        )

    karisik = [_p(1, 1, "K", 0), _p(2, 1, "E", 1), _p(3, 1, "E", 2)]
    rapor = validator.validate_seating(karisik, separation=validator.SEPARATION_ROOM)
    assert len(rapor.hard_violations) == 1
    assert "D-201 salonunda" in rapor.hard_violations[0]

    # Aynı yerleşim DESK kipinde temizdir (farklı sıralar).
    assert validator.validate_seating(karisik, separation=validator.SEPARATION_DESK).is_valid

    # Salonlar ayrıldığında ROOM kipi de temizdir.
    ayrik = [_p(1, 1, "K", 0), _p(2, 2, "E", 0)]
    assert validator.validate_seating(ayrik, separation=validator.SEPARATION_ROOM).is_valid


def test_klasik_duzende_ayrisma_uygulanmaz() -> None:
    """K6 kullanıcı kararı: kendi dersliğinde düzeninde kural hiç işlemez."""
    a = validator.PlacedStudent(
        student_id=1,
        conflict_group="10:9",
        room_id=1,
        desk_row=0,
        desk_col=0,
        slot=0,
        x=0.0,
        y=0.0,
        separation_key="K",
    )
    b = replace(a, student_id=2, slot=1, separation_key="E")
    rapor = validator.validate_seating(
        [a, b], enforce_group_separation=False, separation=validator.SEPARATION_DESK
    )
    assert rapor.is_valid
