// planEdit saf yardımcıları (T10) — tıkla-yerleştir durum dönüşümleri.
// Şema doğrulama + numaralandırma BACKEND'dedir; burada yalnız UI dönüşümü test edilir.

import { describe, expect, it } from "vitest";

import type { LayoutPlan } from "./api";
import {
  FRONT_BAND_ROWS,
  applyTool,
  capacityOf,
  cellContent,
  deskRowCount,
  emptyPlan,
  resizeDeskArea,
  resizeGrid,
} from "./planEdit";

function planWith(partial: Partial<LayoutPlan> = {}): LayoutPlan {
  return { grid: { rows: 3, cols: 3 }, desks: [], furniture: [], ...partial };
}

describe("applyTool", () => {
  it("boş hücreye sıra yerleştirir; aynı hücreye yenisi ESKİSİNİ DEĞİŞTİRİR", () => {
    let plan = applyTool(planWith(), 1, 2, { kind: "desk", deskType: "DOUBLE" });
    expect(cellContent(plan, 1, 2).desk).toEqual({ row: 1, col: 2, type: "DOUBLE" });

    plan = applyTool(plan, 1, 2, { kind: "desk", deskType: "TRIPLE" });
    expect(plan.desks).toHaveLength(1);
    expect(cellContent(plan, 1, 2).desk?.type).toBe("TRIPLE");
  });

  it("sıra üstüne mobilya konunca sıra kalkar (hücrede tek öğe)", () => {
    let plan = applyTool(planWith(), 0, 0, { kind: "desk", deskType: "SINGLE" });
    plan = applyTool(plan, 0, 0, { kind: "furniture", furniture: "DOOR" });
    expect(cellContent(plan, 0, 0).desk).toBeUndefined();
    expect(cellContent(plan, 0, 0).furniture?.kind).toBe("DOOR");
  });

  it("öğretmen masası planda TEK olabilir — yenisi konunca eskisi kalkar", () => {
    let plan = applyTool(planWith(), 0, 0, { kind: "furniture", furniture: "TEACHER_DESK" });
    plan = applyTool(plan, 2, 2, { kind: "furniture", furniture: "TEACHER_DESK" });
    const teacherDesks = plan.furniture.filter((f) => f.kind === "TEACHER_DESK");
    expect(teacherDesks).toEqual([{ kind: "TEACHER_DESK", row: 2, col: 2 }]);
  });

  it("silgi hücreyi boşaltır; devre-dışı anahtarı yalnız sırada çalışır", () => {
    let plan = applyTool(planWith(), 1, 1, { kind: "desk", deskType: "DOUBLE" });
    plan = applyTool(plan, 1, 1, { kind: "toggle-disabled" });
    expect(cellContent(plan, 1, 1).desk?.disabled).toBe(true);
    plan = applyTool(plan, 1, 1, { kind: "toggle-disabled" });
    expect(cellContent(plan, 1, 1).desk?.disabled).toBe(false);

    // Boş hücrede toggle no-op; silgi dolu hücreyi temizler.
    expect(applyTool(plan, 0, 0, { kind: "toggle-disabled" })).toBe(plan);
    plan = applyTool(plan, 1, 1, { kind: "erase" });
    expect(plan.desks).toHaveLength(0);
  });
});

describe("capacityOf", () => {
  it("aktif koltukları toplar; devre dışı sıra sayılmaz", () => {
    const plan = planWith({
      desks: [
        { row: 0, col: 0, type: "SINGLE" },
        { row: 0, col: 1, type: "DOUBLE" },
        { row: 0, col: 2, type: "TRIPLE", disabled: true },
      ],
    });
    expect(capacityOf(plan)).toBe(3); // 1 + 2; üçlü devre dışı
  });
});

describe("resizeGrid", () => {
  it("kırpılan alandaki sıra/mobilya atılır, kalanlar korunur", () => {
    const plan = planWith({
      desks: [
        { row: 0, col: 0, type: "SINGLE" },
        { row: 2, col: 2, type: "DOUBLE" },
      ],
      furniture: [{ kind: "DOOR", row: 2, col: 0 }],
    });
    const resized = resizeGrid(plan, 2, 2);
    expect(resized.grid).toEqual({ rows: 2, cols: 2 });
    expect(resized.desks).toEqual([{ row: 0, col: 0, type: "SINGLE" }]);
    expect(resized.furniture).toEqual([]);
  });
});

describe("emptyPlan", () => {
  it("backend DEFAULT_LAYOUT_PLAN ile aynı boş şemayı üretir", () => {
    // 6 satır = ÖN CEPHE bandı (satır 0) + 5 sıra öğrenci alanı; backend
    // `layout.DEFAULT_LAYOUT_PLAN` ile birebir kalmalı.
    expect(emptyPlan()).toEqual({ grid: { rows: 6, cols: 4 }, desks: [], furniture: [] });
  });
});

describe("ön cephe bandı (31.08.2026 saha bulgusu)", () => {
  it("satır sayımı ÖĞRENCİ sıralarını verir, bandı saymaz", () => {
    // default_section_plan: 1 band + 5 sıra = 6 ızgara satırı.
    expect(deskRowCount({ grid: { rows: 6, cols: 4 }, desks: [], furniture: [] })).toBe(5);
    expect(FRONT_BAND_ROWS).toBe(1);
  });

  it("öğrenci alanı büyürken ön cephe bandı korunur", () => {
    const plan = {
      grid: { rows: 6, cols: 4 },
      desks: [{ row: 1, col: 0, type: "DOUBLE" as const }],
      furniture: [{ kind: "TEACHER_DESK" as const, row: 0, col: 3 }],
    };
    const buyuk = resizeDeskArea(plan, 8, 4);
    expect(buyuk.grid.rows).toBe(9); // 8 sıra + 1 band
    expect(buyuk.furniture).toHaveLength(1); // band öğesi DURUYOR
    expect(deskRowCount(buyuk)).toBe(8);
  });

  it("öğrenci alanı küçülünce taşan sıralar düşer, band düşmez", () => {
    const plan = {
      grid: { rows: 6, cols: 4 },
      desks: [
        { row: 1, col: 0, type: "DOUBLE" as const },
        { row: 5, col: 0, type: "DOUBLE" as const },
      ],
      furniture: [{ kind: "DOOR" as const, row: 0, col: 0 }],
    };
    const kucuk = resizeDeskArea(plan, 2, 4);
    expect(kucuk.grid.rows).toBe(3);
    expect(kucuk.desks).toHaveLength(1); // satır 5 kırpıldı
    expect(kucuk.furniture).toHaveLength(1);
  });
});
