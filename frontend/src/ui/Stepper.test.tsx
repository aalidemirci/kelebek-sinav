// Tur 108 — Stepper primitifi: render + durum işaretleri + aria-current. RTL + Vitest.
// 18.09.2026: `onSelect` ile tamamlanmış adımlar tıklanabilir/klavyeyle seçilebilir.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

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

  it("onSelect verilmezse ray salt görseldir — hiçbir adım düğme değildir", () => {
    render(<Stepper items={ITEMS} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("onSelect verilince YALNIZ tamamlanmış adım düğmedir; tıklanınca anahtar + sıra döner", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<Stepper items={ITEMS} onSelect={onSelect} />);

    // Atlanan, güncel ve gelecek adım tıklanamaz — tek düğme tamamlanmış adımdır.
    const dugmeler = screen.getAllByRole("button");
    expect(dugmeler).toHaveLength(1);
    expect(dugmeler[0]).toHaveAccessibleName("Dilekçe adımına dön");
    expect(screen.queryByRole("button", { name: /Rehberlik/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Müdür değ\./ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Kurul/ })).not.toBeInTheDocument();

    await user.click(dugmeler[0]);
    expect(onSelect).toHaveBeenCalledWith("a", 0);
  });

  it("tamamlanmış adım klavyeyle seçilir (Tab ile odak, Enter ile çalıştırma)", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<Stepper items={ITEMS} onSelect={onSelect} />);

    await user.tab();
    expect(screen.getByRole("button", { name: "Dilekçe adımına dön" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith("a", 0);
  });
});
