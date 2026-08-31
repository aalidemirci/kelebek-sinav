"""2D salon yerleşim planı — JSON şema doğrulama + koltuk numaralandırma (T3).

ADR-0016 §7: `ExamRoom.layout_plan` şeması servis katmanında doğrulanır;
kapasite plandan hesaplanır. Numaralandırma koltuk sırasını plandan türetir
(dönemlik kılavuz: öğretmen masasına en yakın sıradan başlayan S düzeni).

Koordinat sözleşmesi (T5 kelebek motorunun mesafe metriği de bunu kullanacak):
- Grid hücresi 1×1 birim; satır 0 üst (kroki çiziminde ön cephe), sütun 0 sol.
- Bir sıra (desk) TEK grid hücresi kaplar; tekli/ikili/üçlü fark koltuk
  sayısıdır. Koltuğun gerçek koordinatı: y = satır, x = sütun + hücre içi ofset
  (koltuklar hücre genişliğine eşit aralıklı serilir) — aynı sıradaki komşu
  koltuklar arası mesafe < 1 olur; "bitişik masa" denetimi yine de mesafeden
  değil (desk_row, desk_col) kimliğinden yapılmalıdır.

Numaralandırma kuralları (deterministik; birim testlerin omurgası):
1. Referans nokta: ÖĞRETMEN MASASI; yoksa yazı tahtası → akıllı tahta → (0,0).
2. Başlangıç sırası: referansa Öklid uzaklığı en küçük AKTİF sıra
   (eşitlikte küçük satır, sonra küçük sütun).
3. Sütun gezme yönü: başlangıç sırası salonun sol yarısındaysa soldan sağa,
   değilse sağdan sola (aktif sıra sütun aralığının ortasına göre).
4. Satır gezme yönü (taban): başlangıç sırası ön yarıdaysa önden arkaya,
   değilse arkadan öne.
5. S_DUZENI: her sütunda satır yönü bir öncekinin TERSİ (kesintisiz S rotası);
   DUZ: her sütun taban yönde.
6. Sıra içi koltuklar rota akış yönünde numaralanır (soldan sağa gezilirken
   soldaki koltuk önce); `slot` alanı her zaman fiziksel sol→sağ indekstir.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from django.core.exceptions import ValidationError

from apps.sinav.models import DeskType, FurnitureKind, NumberingScheme

MAX_GRID_ROWS = 30
MAX_GRID_COLS = 30

DESK_SEAT_COUNT: dict[str, int] = {
    DeskType.SINGLE: 1,
    DeskType.DOUBLE: 2,
    DeskType.TRIPLE: 3,
}

# Mobilya yönü (kapı menteşesi / tahta cephesi) — editör çizimi için, opsiyonel.
VALID_FACINGS: frozenset[str] = frozenset({"N", "E", "S", "W"})

_ALLOWED_PLAN_KEYS = frozenset({"grid", "desks", "furniture"})
_ALLOWED_DESK_KEYS = frozenset({"row", "col", "type", "disabled"})
_ALLOWED_FURNITURE_KEYS = frozenset({"kind", "row", "col", "facing"})

#: Boş salon için geçerli asgari plan (yeni kayıt varsayılanı).
DEFAULT_LAYOUT_PLAN: dict[str, object] = {
    "grid": {"rows": 5, "cols": 4},
    "desks": [],
    "furniture": [],
}


def default_section_plan(desk_rows: int = 5, cols: int = 4) -> dict[str, object]:
    """Şube dersliği varsayılan planı (Tur 637): ikili sıralar cols×desk_rows.

    Kullanıcı isteği: 40 koltuklu derslik (4 sütun × 5 sıra ikili = 40); öğretmen
    masası EN SAĞ sütunun ÖNÜNDE, kapı SOL ÖNde. Koordinat sözleşmesi (layout.py
    başlığı): satır 0 = ÖN cephe, sütun 0 = SOL. Bu yüzden mobilya satır 0'a,
    sıralar satır 1..desk_rows'a yerleşir.

    `desk_rows`/`cols` çağıran tarafça büyütülebilir (kalabalık şube). Üretilen
    plan `validate_layout_plan`'ı geçer; öğretmen masası tek olduğundan
    numaralandırma referansı sağ-ön köşedir (S rotası sağdan başlar).
    """
    grid_rows = desk_rows + 1  # satır 0 mobilya cephesi
    desks: list[dict[str, object]] = [
        {"row": row, "col": col, "type": DeskType.DOUBLE}
        for row in range(1, desk_rows + 1)
        for col in range(cols)
    ]
    furniture: list[dict[str, object]] = [
        {"kind": FurnitureKind.DOOR, "row": 0, "col": 0},
        {"kind": FurnitureKind.TEACHER_DESK, "row": 0, "col": cols - 1},
    ]
    return {
        "grid": {"rows": grid_rows, "cols": cols},
        "desks": desks,
        "furniture": furniture,
    }


@dataclass(frozen=True)
class Desk:
    """Plandaki tek sıra hücresi (doğrulanmış)."""

    row: int
    col: int
    desk_type: str  # DeskType değeri
    disabled: bool

    @property
    def seat_count(self) -> int:
        return DESK_SEAT_COUNT[self.desk_type]


@dataclass(frozen=True)
class Furniture:
    """Plandaki mobilya öğesi (doğrulanmış)."""

    kind: str  # FurnitureKind değeri
    row: int
    col: int
    facing: str = ""


@dataclass(frozen=True)
class LayoutPlan:
    """Doğrulanmış yerleşim planı."""

    rows: int
    cols: int
    desks: tuple[Desk, ...]
    furniture: tuple[Furniture, ...]

    @property
    def active_desks(self) -> tuple[Desk, ...]:
        return tuple(d for d in self.desks if not d.disabled)

    @property
    def capacity(self) -> int:
        return sum(d.seat_count for d in self.active_desks)


@dataclass(frozen=True)
class Seat:
    """Numaralandırılmış tek koltuk.

    `slot` fiziksel sol→sağ indeks (rapor/kroki sabiti); `seat_no` rota
    sırasına göre 1'den başlayan koltuk numarasıdır. (x, y) gerçek koordinat —
    T5 mesafe metriği ve kroki çizimi bunu kullanır.
    """

    desk_row: int
    desk_col: int
    desk_type: str
    slot: int
    seat_no: int
    x: float
    y: float


# ---------------------------------------------------------------------------
# Şema doğrulama
# ---------------------------------------------------------------------------
def _err(message: str) -> ValidationError:
    return ValidationError(message)


def _require_int(value: object, label: str, *, lo: int, hi: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _err(f"{label} tam sayı olmalı (gelen: {value!r}).")
    if not lo <= value <= hi:
        raise _err(f"{label} {lo}-{hi} aralığında olmalı (gelen: {value}).")
    return value


def validate_layout_plan(plan: object) -> LayoutPlan:
    """Ham JSON planı doğrular ve tipli `LayoutPlan` döndürür.

    Hatalar Türkçe mesajlı ``ValidationError`` olarak fırlatılır; çağıran
    (servis/serializer) bunu standart hata yanıtına çevirir.
    """
    if not isinstance(plan, dict):
        raise _err("Yerleşim planı bir nesne (JSON object) olmalı.")
    unknown = set(plan) - _ALLOWED_PLAN_KEYS
    if unknown:
        raise _err(f"Bilinmeyen plan alanları: {', '.join(sorted(unknown))}.")

    grid = plan.get("grid")
    if not isinstance(grid, dict):
        raise _err("Plan 'grid' nesnesi (satır/sütun) içermeli.")
    rows = _require_int(grid.get("rows"), "grid.rows", lo=1, hi=MAX_GRID_ROWS)
    cols = _require_int(grid.get("cols"), "grid.cols", lo=1, hi=MAX_GRID_COLS)

    occupied: dict[tuple[int, int], str] = {}

    desks_raw = plan.get("desks", [])
    if not isinstance(desks_raw, list):
        raise _err("'desks' bir liste olmalı.")
    desks: list[Desk] = []
    for i, item in enumerate(desks_raw):
        if not isinstance(item, dict):
            raise _err(f"desks[{i}] bir nesne olmalı.")
        unknown = set(item) - _ALLOWED_DESK_KEYS
        if unknown:
            raise _err(f"desks[{i}] bilinmeyen alan: {', '.join(sorted(unknown))}.")
        row = _require_int(item.get("row"), f"desks[{i}].row", lo=0, hi=rows - 1)
        col = _require_int(item.get("col"), f"desks[{i}].col", lo=0, hi=cols - 1)
        desk_type = item.get("type")
        if desk_type not in DESK_SEAT_COUNT:
            raise _err(
                f"desks[{i}].type geçersiz: {desk_type!r}. "
                f"Geçerli tipler: {', '.join(DESK_SEAT_COUNT)}."
            )
        disabled = item.get("disabled", False)
        if not isinstance(disabled, bool):
            raise _err(f"desks[{i}].disabled true/false olmalı.")
        cell = (row, col)
        if cell in occupied:
            raise _err(f"({row}, {col}) hücresi iki kez kullanılmış (sıra çakışması).")
        occupied[cell] = "desk"
        desks.append(Desk(row=row, col=col, desk_type=str(desk_type), disabled=disabled))

    furniture_raw = plan.get("furniture", [])
    if not isinstance(furniture_raw, list):
        raise _err("'furniture' bir liste olmalı.")
    furniture: list[Furniture] = []
    teacher_desk_count = 0
    for i, item in enumerate(furniture_raw):
        if not isinstance(item, dict):
            raise _err(f"furniture[{i}] bir nesne olmalı.")
        unknown = set(item) - _ALLOWED_FURNITURE_KEYS
        if unknown:
            raise _err(f"furniture[{i}] bilinmeyen alan: {', '.join(sorted(unknown))}.")
        kind = item.get("kind")
        if kind not in FurnitureKind.values:
            raise _err(
                f"furniture[{i}].kind geçersiz: {kind!r}. "
                f"Geçerli türler: {', '.join(FurnitureKind.values)}."
            )
        row = _require_int(item.get("row"), f"furniture[{i}].row", lo=0, hi=rows - 1)
        col = _require_int(item.get("col"), f"furniture[{i}].col", lo=0, hi=cols - 1)
        facing = item.get("facing", "")
        if facing and facing not in VALID_FACINGS:
            raise _err(f"furniture[{i}].facing geçersiz: {facing!r} (N/E/S/W).")
        cell = (row, col)
        if cell in occupied:
            raise _err(f"({row}, {col}) hücresi iki kez kullanılmış (mobilya çakışması).")
        occupied[cell] = "furniture"
        if kind == FurnitureKind.TEACHER_DESK:
            teacher_desk_count += 1
            if teacher_desk_count > 1:
                raise _err("Planda en fazla bir öğretmen masası olabilir.")
        furniture.append(Furniture(kind=str(kind), row=row, col=col, facing=str(facing)))

    return LayoutPlan(rows=rows, cols=cols, desks=tuple(desks), furniture=tuple(furniture))


# ---------------------------------------------------------------------------
# Numaralandırma
# ---------------------------------------------------------------------------
_REFERENCE_PRIORITY: tuple[str, ...] = (
    FurnitureKind.TEACHER_DESK,
    FurnitureKind.BLACKBOARD,
    FurnitureKind.SMART_BOARD,
)


def reference_cell(plan: LayoutPlan) -> tuple[int, int]:
    """Salonun ODAK hücresi: öğretmen masası → tahta → akıllı tahta → (0, 0).

    İki tüketicisi vardır ve ikisi de AYNI noktayı kastetmek zorundadır:
    (1) numaralandırma başlangıcı (kural 1); (2) "ön sıra / öğretmen masasına
    yakın" kavramı (motor ceza demeti ve yerleştirme kuralları). İkinci bir
    doğruluk kaynağı doğmasın diye public'tir. Dönüş (satır, sütun) — motorun
    `focus` alanı (x=sütun, y=satır) EKSEN SIRASI TERSTİR, çeviren taraf dikkat.
    """
    for kind in _REFERENCE_PRIORITY:
        cells = sorted((f.row, f.col) for f in plan.furniture if f.kind == kind)
        if cells:
            return cells[0]
    return (0, 0)


def _start_desk(plan: LayoutPlan, ref: tuple[int, int]) -> Desk:
    """Referansa en yakın aktif sıra (kural 2)."""
    return min(
        plan.active_desks,
        key=lambda d: (math.dist((d.row, d.col), ref), d.row, d.col),
    )


def numbered_seats(plan: LayoutPlan, scheme: str) -> list[Seat]:
    """Koltukları plandan numaralandırır (modül docstring'indeki kurallar).

    Devre dışı sıralar atlanır; dönen liste `seat_no` artan sıralıdır.
    Boş plan (aktif sıra yok) → boş liste.
    """
    if scheme not in NumberingScheme.values:
        raise _err(f"Geçersiz numaralandırma düzeni: {scheme!r}.")
    active = plan.active_desks
    if not active:
        return []

    ref = reference_cell(plan)
    start = _start_desk(plan, ref)

    desk_cols = sorted({d.col for d in active})
    desk_rows = sorted({d.row for d in active})
    col_mid = (desk_cols[0] + desk_cols[-1]) / 2
    row_mid = (desk_rows[0] + desk_rows[-1]) / 2
    left_to_right = start.col <= col_mid  # kural 3
    front_to_back = start.row <= row_mid  # kural 4

    visit_cols = desk_cols if left_to_right else list(reversed(desk_cols))

    by_col: dict[int, list[Desk]] = {}
    for desk in active:
        by_col.setdefault(desk.col, []).append(desk)

    seats: list[Seat] = []
    seat_no = 0
    for idx, col in enumerate(visit_cols):
        descending = (
            (not front_to_back)
            if scheme == NumberingScheme.STRAIGHT
            else (
                front_to_back == bool(idx % 2)  # S: tek indeksli sütunlarda taban yönün tersi
            )
        )
        column_desks = sorted(by_col[col], key=lambda d: d.row, reverse=descending)
        for desk in column_desks:
            size = desk.seat_count
            # Rota akış yönünde koltuk sırası (kural 6); slot fiziksel sol→sağ.
            slots = range(size) if left_to_right else range(size - 1, -1, -1)
            for slot in slots:
                seat_no += 1
                seats.append(
                    Seat(
                        desk_row=desk.row,
                        desk_col=desk.col,
                        desk_type=desk.desk_type,
                        slot=slot,
                        seat_no=seat_no,
                        x=desk.col + (slot - (size - 1) / 2) / size,
                        y=float(desk.row),
                    )
                )
    return seats
