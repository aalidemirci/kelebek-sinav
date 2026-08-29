// Tur 43 — Button bileşeninin temel davranış testi (M3 varyantlar + tıklama
// + state layer DOM'da). React Testing Library + Vitest.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import Button from "./Button";

describe("Button", () => {
  it("içeriğini ekrana basar", () => {
    render(<Button>Kaydet</Button>);
    expect(screen.getByRole("button", { name: "Kaydet" })).toBeInTheDocument();
  });

  it("tıklandığında onClick handler'ı çağırır", async () => {
    const user = userEvent.setup();
    const handler = vi.fn();
    render(<Button onClick={handler}>Tıkla</Button>);

    await user.click(screen.getByRole("button", { name: "Tıkla" }));

    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("disabled iken tıklamayı yakalamaz", async () => {
    const user = userEvent.setup();
    const handler = vi.fn();
    render(
      <Button onClick={handler} disabled>
        Pasif
      </Button>,
    );

    await user.click(screen.getByRole("button", { name: "Pasif" }));

    expect(handler).not.toHaveBeenCalled();
  });

  it("varsayılan varyant 'filled' (M3 birincil eylem)", () => {
    render(<Button>Birincil</Button>);
    const btn = screen.getByRole("button");
    // M3: filled → bg-primary text-on-primary
    expect(btn.className).toMatch(/bg-primary/);
    expect(btn.className).toMatch(/text-on-primary/);
  });

  it("outlined varyantı border ve primary text alır", () => {
    render(<Button variant="outlined">Anahat</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toMatch(/border-outline/);
    expect(btn.className).toMatch(/text-primary/);
  });

  it("tonal varyantı secondary-container kullanır", () => {
    render(<Button variant="tonal">İkincil</Button>);
    expect(screen.getByRole("button").className).toMatch(/bg-secondary-container/);
  });

  it("block prop'u tam genişlik ekler", () => {
    render(<Button block>Geniş</Button>);
    expect(screen.getByRole("button").className).toMatch(/w-full/);
  });

  it("merkezî .state-layer örtü span'i içerir (M3 §7.5, Tur 313)", () => {
    const { container } = render(<Button>X</Button>);
    const layer = container.querySelector('[aria-hidden="true"]');
    expect(layer).not.toBeNull();
    expect(layer?.className).toMatch(/state-layer/);
  });

  it("yoğunluk değişkeninden gelen kontrol yüksekliğini kullanır", () => {
    render(<Button>Hedef</Button>);
    expect(screen.getByRole("button").className).toContain("min-h-[var(--ks-control-height)]");
  });
});
