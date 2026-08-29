// Tur 262 (F32) — Icon `size` prop'u: merkezî boyut eşlemesi regresyon testi.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Icon from "./Icon";

describe("Icon", () => {
  it("size prop'u merkezî eşlemden tip ölçeği sınıfı üretir", () => {
    render(<Icon name="check" size="lg" label="Onay" />);
    const el = screen.getByRole("img", { name: "Onay" });
    expect(el.className).toContain("material-symbols-outlined");
    expect(el.className).toContain("text-lg");
  });

  it("size verilmezse boyut sınıfı eklemez (bağlam font-size'ı geçerli)", () => {
    render(<Icon name="check" label="Onay" />);
    const el = screen.getByRole("img", { name: "Onay" });
    expect(el.className).not.toMatch(/\btext-(xs|sm|base|lg|xl|2xl|3xl|4xl|5xl)\b/);
  });

  it("size + className birlikte çalışır; label'sız ikon aria-hidden olur", () => {
    const { container } = render(<Icon name="error" size="sm" className="text-error" />);
    const el = container.querySelector("span");
    expect(el?.className).toContain("text-sm");
    expect(el?.className).toContain("text-error");
    expect(el?.getAttribute("aria-hidden")).toBe("true");
  });
});
