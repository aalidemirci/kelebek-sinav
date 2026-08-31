"""2D yerleşim planı — şema doğrulama + numaralandırma birim testleri (T3).

Yol haritası T3 kabul kriteri: tekli/ikili/üçlü × mobilya konumları × devre
dışı sıralar kombinasyonlarında numaralandırma; plan JSON şema validasyonu.
DB gerekmez — saf birim testleri.
"""

from __future__ import annotations

import math

import pytest
from django.core.exceptions import ValidationError

from apps.sinav import layout
from apps.sinav.models import DeskType, FurnitureKind, NumberingScheme


def _plan(
    desks: list[dict[str, object]],
    furniture: list[dict[str, object]] | None = None,
    rows: int = 5,
    cols: int = 4,
) -> dict[str, object]:
    return {
        "grid": {"rows": rows, "cols": cols},
        "desks": desks,
        "furniture": furniture or [],
    }


def _desk(
    row: int, col: int, type_: str = DeskType.SINGLE, disabled: bool = False
) -> dict[str, object]:
    return {"row": row, "col": col, "type": type_, "disabled": disabled}


def _teacher_desk(row: int, col: int) -> dict[str, object]:
    return {"kind": FurnitureKind.TEACHER_DESK, "row": row, "col": col}


def _seat_route(
    plan_dict: dict[str, object], scheme: str = NumberingScheme.S_PATTERN
) -> list[tuple[int, int, int]]:
    """(desk_row, desk_col, slot) listesi — seat_no sırasında."""
    plan = layout.validate_layout_plan(plan_dict)
    return [(s.desk_row, s.desk_col, s.slot) for s in layout.numbered_seats(plan, scheme)]


# ===========================================================================
# Şema doğrulama
# ===========================================================================


def test_validate_default_plan() -> None:
    plan = layout.validate_layout_plan(layout.DEFAULT_LAYOUT_PLAN)
    # 6 satır = ön cephe bandı (satır 0) + 5 sıra öğrenci alanı.
    assert plan.rows == 6 and plan.cols == 4
    assert plan.capacity == 0


@pytest.mark.parametrize(
    "bad",
    [
        "liste değil",
        [],
        {"desks": []},  # grid yok
        {"grid": {"rows": 0, "cols": 4}, "desks": [], "furniture": []},
        {"grid": {"rows": 5, "cols": 31}, "desks": [], "furniture": []},
        {"grid": {"rows": "5", "cols": 4}, "desks": [], "furniture": []},
        {"grid": {"rows": 5, "cols": 4}, "desks": {}, "furniture": []},
        {"grid": {"rows": 5, "cols": 4}, "desks": [], "furniture": [], "ekstra": 1},
    ],
)
def test_validate_rejects_malformed_top_level(bad: object) -> None:
    with pytest.raises(ValidationError):
        layout.validate_layout_plan(bad)


@pytest.mark.parametrize(
    "desk",
    [
        {"row": 9, "col": 0, "type": DeskType.SINGLE},  # grid dışı satır (rows=5)
        {"row": 0, "col": 4, "type": DeskType.SINGLE},  # grid dışı sütun (cols=4)
        {"row": 0, "col": 0, "type": "DORTLU"},  # geçersiz tip
        {"row": 0, "col": 0, "type": DeskType.SINGLE, "disabled": "evet"},
        {"row": 0, "col": 0, "type": DeskType.SINGLE, "renk": "mavi"},  # bilinmeyen alan
        {"row": 0.5, "col": 0, "type": DeskType.SINGLE},  # int değil
    ],
)
def test_validate_rejects_bad_desk(desk: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        layout.validate_layout_plan(_plan([desk]))


def test_validate_rejects_cell_collisions() -> None:
    # Sıra-sıra çakışması.
    with pytest.raises(ValidationError, match="iki kez"):
        layout.validate_layout_plan(_plan([_desk(1, 1), _desk(1, 1, DeskType.DOUBLE)]))
    # Sıra-mobilya çakışması.
    with pytest.raises(ValidationError, match="iki kez"):
        layout.validate_layout_plan(_plan([_desk(1, 1)], [_teacher_desk(1, 1)]))


def test_validate_rejects_bad_furniture() -> None:
    with pytest.raises(ValidationError, match="kind"):
        layout.validate_layout_plan(_plan([], [{"kind": "SAKSI", "row": 0, "col": 0}]))
    with pytest.raises(ValidationError, match="facing"):
        layout.validate_layout_plan(
            _plan([], [{"kind": FurnitureKind.DOOR, "row": 0, "col": 0, "facing": "X"}])
        )
    with pytest.raises(ValidationError, match="en fazla bir öğretmen masası"):
        layout.validate_layout_plan(_plan([], [_teacher_desk(0, 0), _teacher_desk(0, 1)]))


def test_capacity_counts_only_active_desks() -> None:
    plan = layout.validate_layout_plan(
        _plan(
            [
                _desk(0, 0, DeskType.SINGLE),
                _desk(1, 0, DeskType.DOUBLE),
                _desk(2, 0, DeskType.TRIPLE),
                _desk(3, 0, DeskType.TRIPLE, disabled=True),
            ]
        )
    )
    assert plan.capacity == 1 + 2 + 3


# ===========================================================================
# Numaralandırma — rota (S düzeni / düz)
# ===========================================================================


def test_empty_plan_yields_no_seats() -> None:
    plan = layout.validate_layout_plan(_plan([]))
    assert layout.numbered_seats(plan, NumberingScheme.S_PATTERN) == []


def test_invalid_scheme_rejected() -> None:
    plan = layout.validate_layout_plan(_plan([_desk(0, 0)]))
    with pytest.raises(ValidationError):
        layout.numbered_seats(plan, "ZIGZAG")


def test_s_pattern_serpentine_route_teacher_front_left() -> None:
    """Öğretmen masası ön-solda: kolon 1 önden arkaya, kolon 2 arkadan öne (S).

    Sıralar 1.-3. satırlarda; ön satır (0) mobilyaya ayrılmış (gerçek sınıf düzeni).
    """
    desks = [_desk(r, c) for r in range(1, 4) for c in range(2)]  # 3 satır × 2 kolon tekli
    route = _seat_route(_plan(desks, [_teacher_desk(0, 0)], rows=4, cols=3))
    assert route == [
        (1, 0, 0),
        (2, 0, 0),
        (3, 0, 0),  # kolon 0: ön→arka
        (3, 1, 0),
        (2, 1, 0),
        (1, 1, 0),  # kolon 1: arka→ön (S)
    ]


def test_straight_route_same_direction_each_column() -> None:
    desks = [_desk(r, c) for r in range(1, 4) for c in range(2)]
    route = _seat_route(
        _plan(desks, [_teacher_desk(0, 0)], rows=4, cols=3), NumberingScheme.STRAIGHT
    )
    assert route == [
        (1, 0, 0),
        (2, 0, 0),
        (3, 0, 0),
        (1, 1, 0),
        (2, 1, 0),
        (3, 1, 0),  # düz: her kolon ön→arka
    ]


def test_teacher_desk_front_right_reverses_column_order() -> None:
    """Öğretmen masası ön-sağda: kolonlar sağdan sola gezilir."""
    desks = [_desk(r, c) for r in range(2) for c in range(3)]
    route = _seat_route(_plan(desks, [_teacher_desk(0, 3)], rows=3, cols=4))
    cols_in_order = [c for _, c, _ in route]
    assert cols_in_order == [2, 2, 1, 1, 0, 0]
    assert route[0] == (0, 2, 0)  # başlangıç: referansa en yakın aktif sıra


def test_teacher_desk_back_corner_starts_from_back() -> None:
    """Öğretmen masası arka köşede: satır yönü arkadan öne başlar."""
    desks = [_desk(r, 0) for r in range(3)]
    route = _seat_route(_plan(desks, [_teacher_desk(2, 1)], rows=3, cols=2))
    assert [r for r, _, _ in route] == [2, 1, 0]


def test_no_furniture_falls_back_to_origin() -> None:
    """Mobilya yoksa referans (0,0) — sol-ön köşeden başlar."""
    desks = [_desk(r, c) for r in range(2) for c in range(2)]
    route = _seat_route(_plan(desks))
    assert route[0] == (0, 0, 0)
    assert [c for _, c, _ in route] == [0, 0, 1, 1]


def test_blackboard_used_when_no_teacher_desk() -> None:
    """Öğretmen masası yoksa yazı tahtası referans alınır."""
    desks = [_desk(r, c) for r in range(2) for c in range(2)]
    route = _seat_route(
        _plan(desks, [{"kind": FurnitureKind.BLACKBOARD, "row": 1, "col": 3}], rows=2, cols=4)
    )
    assert route[0][1] == 1  # sağdaki kolondan başlar (tahtaya yakın)


def test_disabled_desks_skipped_numbering_continuous() -> None:
    """Devre dışı sıra atlanır; koltuk numaraları boşluksuz akar."""
    desks = [_desk(0, 0), _desk(1, 0, disabled=True), _desk(2, 0)]
    plan = layout.validate_layout_plan(_plan(desks, [_teacher_desk(0, 1)]))
    seats = layout.numbered_seats(plan, NumberingScheme.S_PATTERN)
    assert [(s.seat_no, s.desk_row) for s in seats] == [(1, 0), (2, 2)]


# ===========================================================================
# Numaralandırma — sıra içi koltuklar (ikili/üçlü) + koordinatlar
# ===========================================================================


def test_multi_seat_desk_slots_follow_route_direction() -> None:
    """Soldan sağa rotada ikili sıranın sol koltuğu önce; sağdan solda tersi."""
    desks = [_desk(0, 0, DeskType.DOUBLE), _desk(0, 2, DeskType.DOUBLE)]
    # Soldan sağa (öğretmen sol kenarda): slot sırası 0,1.
    route_lr = _seat_route(_plan(desks, [_teacher_desk(1, 0)], rows=2, cols=4))
    assert route_lr[:2] == [(0, 0, 0), (0, 0, 1)]
    # Sağdan sola (öğretmen sağ kenarda): başlangıç (0,2), slot sırası 1,0.
    route_rl = _seat_route(_plan(desks, [_teacher_desk(1, 3)], rows=2, cols=4))
    assert route_rl[:2] == [(0, 2, 1), (0, 2, 0)]


def test_center_teacher_desk_tiebreak_deterministic() -> None:
    """Eşit uzaklıkta iki aday sırada tie-break (satır, sütun) — merkez masa."""
    desks = [_desk(0, 0, DeskType.DOUBLE), _desk(0, 2, DeskType.DOUBLE)]
    route = _seat_route(_plan(desks, [_teacher_desk(0, 1)], rows=2, cols=3))
    assert route[0][1] == 0  # (0,0) kazanır → soldan sağa


def test_triple_desk_three_seats_numbered() -> None:
    desks = [_desk(0, 0, DeskType.TRIPLE)]
    plan = layout.validate_layout_plan(_plan(desks))
    seats = layout.numbered_seats(plan, NumberingScheme.S_PATTERN)
    assert [s.seat_no for s in seats] == [1, 2, 3]
    assert [s.slot for s in seats] == [0, 1, 2]
    # Hücre içi x ofsetleri eşit aralıklı ve hücre merkezine simetrik.
    xs = [s.x for s in seats]
    assert xs == sorted(xs)
    assert math.isclose(sum(xs) / 3, 0.0, abs_tol=1e-9)  # col=0 merkez


def test_seat_coordinates_match_grid() -> None:
    desks = [_desk(2, 3, DeskType.DOUBLE)]
    plan = layout.validate_layout_plan(_plan(desks, rows=4, cols=5))
    seats = layout.numbered_seats(plan, NumberingScheme.S_PATTERN)
    assert all(s.y == 2.0 for s in seats)
    assert math.isclose(seats[0].x, 3 - 0.25) and math.isclose(seats[1].x, 3 + 0.25)


def test_same_desk_gap_can_equal_cross_desk_gap() -> None:
    """Aynı-sıra ve komşu-sıra koltuk araları çakışabilir (her ikisi 0.5) —
    T5'te 'bitişik masa' denetimi mesafeden DEĞİL desk kimliğinden yapılmalı."""
    desks = [_desk(0, 0, DeskType.DOUBLE), _desk(0, 1, DeskType.DOUBLE)]
    plan = layout.validate_layout_plan(_plan(desks))
    seats = layout.numbered_seats(plan, NumberingScheme.S_PATTERN)
    by_key = {(s.desk_col, s.slot): s for s in seats}
    same_desk = abs(by_key[(0, 0)].x - by_key[(0, 1)].x)
    cross_desk = abs(by_key[(0, 1)].x - by_key[(1, 0)].x)
    assert same_desk == cross_desk == 0.5  # bitişiklik mesafeden DEĞİL desk kimliğinden!


def test_mixed_desk_types_full_route() -> None:
    """Karışık tip + devre dışı + mobilya: kabul kriteri kombinasyon testi."""
    desks = [
        _desk(0, 0, DeskType.SINGLE),
        _desk(1, 0, DeskType.DOUBLE),
        _desk(0, 2, DeskType.TRIPLE),
        _desk(1, 2, DeskType.SINGLE, disabled=True),
    ]
    furniture = [
        _teacher_desk(0, 1),
        {"kind": FurnitureKind.DOOR, "row": 2, "col": 0, "facing": "W"},
        {"kind": FurnitureKind.SMART_BOARD, "row": 2, "col": 2},
    ]
    plan = layout.validate_layout_plan(_plan(desks, furniture, rows=3, cols=3))
    assert plan.capacity == 1 + 2 + 3
    seats = layout.numbered_seats(plan, NumberingScheme.S_PATTERN)
    assert [s.seat_no for s in seats] == list(range(1, 7))
    # Kolon 0 (ön→arka): tekli sonra ikili; kolon 2 (S: arka→ön ama 1,2 devre dışı → yalnız üçlü).
    assert [(s.desk_col, s.desk_row) for s in seats] == [
        (0, 0),
        (0, 1),
        (0, 1),
        (2, 0),
        (2, 0),
        (2, 0),
    ]


def test_determinism_same_plan_same_route() -> None:
    desks = [_desk(r, c, DeskType.DOUBLE) for r in range(4) for c in range(3)]
    plan_dict = _plan(desks, [_teacher_desk(4, 0)], rows=5, cols=3)
    assert _seat_route(plan_dict) == _seat_route(plan_dict)
