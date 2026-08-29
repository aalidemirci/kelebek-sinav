// planEdit saf yardımcıları (T10) — tıkla-yerleştir durum dönüşümleri.
// Şema doğrulama + numaralandırma BACKEND'dedir; burada yalnız UI dönüşümü test edilir.

import { describe, expect, it } from "vitest";

import type { LayoutPlan } from "./api";
import { applyTool, capacityOf, cellContent, emptyPlan, resizeGrid } from "./planEdit";

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
    expect(emptyPlan()).toEqual({ grid: { rows: 5, cols: 4 }, desks: [], furniture: [] });
  });
});
