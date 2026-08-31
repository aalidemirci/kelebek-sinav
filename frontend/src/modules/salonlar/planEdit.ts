// Salon planı düzenleme yardımcıları (T10 — tıkla-yerleştir, ADR-0016 kararı:
// DnD kütüphanesi yok). Bunlar SALT UI durum dönüşümleridir (immutable);
// şema doğrulama + koltuk numaralandırma iş kuralı BACKEND'dedir
// (layout.validate_layout_plan / preview-seats ucu — CLAUDE.md §10).

import type { DeskCell, DeskTypeCode, FurnitureCell, FurnitureKindCode, LayoutPlan } from "./api";

/** Palet aracı: sıra tipi, mobilya, devre dışı anahtarı veya silgi. */
export type Tool =
  | { kind: "desk"; deskType: DeskTypeCode }
  | { kind: "furniture"; furniture: FurnitureKindCode }
  | { kind: "toggle-disabled" }
  | { kind: "erase" };

export const DESK_SEAT_COUNT: Record<DeskTypeCode, number> = {
  SINGLE: 1,
  DOUBLE: 2,
  TRIPLE: 3,
};

export const DESK_LABELS: Record<DeskTypeCode, string> = {
  SINGLE: "Tekli sıra",
  DOUBLE: "İkili sıra",
  TRIPLE: "Üçlü sıra",
};

export const FURNITURE_LABELS: Record<FurnitureKindCode, string> = {
  DOOR: "Kapı",
  BLACKBOARD: "Yazı tahtası",
  SMART_BOARD: "Akıllı tahta",
  TEACHER_DESK: "Öğretmen masası",
};

export const FURNITURE_ICONS: Record<FurnitureKindCode, string> = {
  DOOR: "door_front",
  BLACKBOARD: "edit_square",
  SMART_BOARD: "tv",
  TEACHER_DESK: "co_present",
};

export interface CellContent {
  desk?: DeskCell;
  furniture?: FurnitureCell;
}

/** Hücredeki öğe (boşsa iki alan da undefined). */
export function cellContent(plan: LayoutPlan, row: number, col: number): CellContent {
  return {
    desk: plan.desks.find((d) => d.row === row && d.col === col),
    furniture: plan.furniture.find((f) => f.row === row && f.col === col),
  };
}

/** Aktif koltuk toplamı — yalnız CANLI sayaç görseli; kesin değer backend önizlemesinden. */
export function capacityOf(plan: LayoutPlan): number {
  return plan.desks.filter((d) => !d.disabled).reduce((sum, d) => sum + DESK_SEAT_COUNT[d.type], 0);
}

function withoutCell(plan: LayoutPlan, row: number, col: number): LayoutPlan {
  return {
    ...plan,
    desks: plan.desks.filter((d) => !(d.row === row && d.col === col)),
    furniture: plan.furniture.filter((f) => !(f.row === row && f.col === col)),
  };
}

/**
 * Seçili aracı hücreye uygular (immutable). Dolu hücreye yerleştirme mevcut
 * öğeyi DEĞİŞTİRİR (editör hızlı düzeltme UX'i). Öğretmen masası planda tek
 * olabilir (backend kuralının UI kolaylığı) — yenisi konunca eskisi kalkar.
 */
export function applyTool(plan: LayoutPlan, row: number, col: number, tool: Tool): LayoutPlan {
  if (tool.kind === "erase") return withoutCell(plan, row, col);
  if (tool.kind === "toggle-disabled") {
    const desk = cellContent(plan, row, col).desk;
    if (!desk) return plan;
    return {
      ...plan,
      desks: plan.desks.map((d) =>
        d.row === row && d.col === col ? { ...d, disabled: !d.disabled } : d,
      ),
    };
  }
  if (tool.kind === "desk") {
    const cleared = withoutCell(plan, row, col);
    return {
      ...cleared,
      desks: [...cleared.desks, { row, col, type: tool.deskType }],
    };
  }
  // furniture
  let cleared = withoutCell(plan, row, col);
  if (tool.furniture === "TEACHER_DESK") {
    cleared = {
      ...cleared,
      furniture: cleared.furniture.filter((f) => f.kind !== "TEACHER_DESK"),
    };
  }
  return {
    ...cleared,
    furniture: [...cleared.furniture, { kind: tool.furniture, row, col }],
  };
}

/** Grid'i yeniden boyutlandırır; kırpılan alandaki öğeler atılır. */
export function resizeGrid(plan: LayoutPlan, rows: number, cols: number): LayoutPlan {
  return {
    grid: { rows, cols },
    desks: plan.desks.filter((d) => d.row < rows && d.col < cols),
    furniture: plan.furniture.filter((f) => f.row < rows && f.col < cols),
  };
}

/**
 * ÖN CEPHE BANDI — ızgaranın 0. satırı: öğretmen masası, tahta ve kapının
 * yeri. Öğrenci sırası ALANI 1. satırdan başlar.
 *
 * Sözleşme `layout.py` başlığındandır ("satır 0 üst = ön cephe") ve
 * `default_section_plan` mobilyayı tam olarak buraya koyar. Saha bulgusu
 * (31.08.2026): editörün "Satır" alanı bu bandı da sayıyordu (5 sıralık
 * derslikte "6" yazıyordu) ve kullanıcı bunu öğrenci alanı sanıyordu.
 */
export const FRONT_BAND_ROWS = 1;

/** Öğrenci sırası satır sayısı (ön cephe bandı hariç). */
export function deskRowCount(plan: LayoutPlan): number {
  return Math.max(0, plan.grid.rows - FRONT_BAND_ROWS);
}

/** ÖĞRENCİ ALANINI boyutlandırır; ön cephe bandı korunur. */
export function resizeDeskArea(plan: LayoutPlan, deskRows: number, cols: number): LayoutPlan {
  return resizeGrid(plan, deskRows + FRONT_BAND_ROWS, cols);
}

/** Yeni salon için boş varsayılan plan (ön cephe bandı + 5 sıra öğrenci alanı). */
export function emptyPlan(): LayoutPlan {
  return { grid: { rows: 5 + FRONT_BAND_ROWS, cols: 4 }, desks: [], furniture: [] };
}
