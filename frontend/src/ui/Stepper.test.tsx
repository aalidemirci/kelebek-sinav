// Tur 108 — Stepper primitifi: render + durum işaretleri + aria-current. RTL + Vitest.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Stepper from "./Stepper";
import type { StepperItem } from "./Stepper";

const ITEMS: StepperItem[] = [
  { key: "a", label: "Dilekçe", icon: "description", status: "done" },
  { key: "b", label: "Rehberlik", icon: "psychology", status: "skipped" },
  { key: "c", label: "Müdür değ.", icon: "gavel", status: "current" },
  { key: "d", label: "Kurul", icon: "how_to_vote", status: "upcoming" },
];

describe("Stepper", () => {
  it("tüm adımları etiketleriyle basar", () => {
    render(<Stepper items={ITEMS} ariaLabel="Süreç" />);
    expect(screen.getByText("Dilekçe")).toBeInTheDocument();
    expect(screen.getByText("Müdür değ.")).toBeInTheDocument();
  });

  it("güncel adım aria-current=step alır", () => {
    render(<Stepper items={ITEMS} />);
    const current = screen.getByText("Müdür değ.").closest("li");
    expect(current).toHaveAttribute("aria-current", "step");
    expect(current?.querySelector(".rounded-full")).toHaveClass("ring-inset");
  });

  it("atlanan adımda 'atlandı' notu gösterilir", () => {
    render(<Stepper items={ITEMS} />);
    expect(screen.getByText("atlandı")).toBeInTheDocument();
  });
});
