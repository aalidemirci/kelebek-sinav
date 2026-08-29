// Tur 46 — ThemeSwitcher davranış testi.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ThemeSwitcher from "./ThemeSwitcher";

describe("ThemeSwitcher", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    delete window.pywebview;
  });
  afterEach(() => {
    document.documentElement.removeAttribute("data-theme");
    delete window.pywebview;
  });

  it("varsayılan açık tema; tıklanınca karanlığa geçer", async () => {
    const user = userEvent.setup();
    render(<ThemeSwitcher />);

    const btn = screen.getByRole("button", { name: /karanlık temaya geç/i });
    expect(btn).toHaveAttribute("aria-pressed", "false");
    expect(document.documentElement.getAttribute("data-theme")).toBeNull();

    await user.click(btn);

    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(window.localStorage.getItem("oys-theme")).toBe("dark");
    expect(screen.getByRole("button", { name: /açık temaya geç/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("yoğunluğa duyarlı kare hedef kullanır", () => {
    render(<ThemeSwitcher />);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("h-[var(--ks-control-height)]");
    expect(btn.className).toContain("w-[var(--ks-control-height)]");
  });

  it("merkezî .state-layer örtü span'ı içerir (M3 §7.5, Tur 313)", () => {
    const { container } = render(<ThemeSwitcher />);
    const layer = container.querySelector('[aria-hidden="true"]');
    expect(layer).not.toBeNull();
    expect(layer?.className).toMatch(/state-layer/);
  });

  it("tema değişimini Windows başlık çubuğuna iletir", async () => {
    const user = userEvent.setup();
    const setTitlebarTheme = vi.fn().mockResolvedValue(true);
    window.pywebview = { api: { set_titlebar_theme: setTitlebarTheme } };

    render(<ThemeSwitcher />);
    expect(setTitlebarTheme).toHaveBeenCalledWith(false);

    await user.click(screen.getByRole("button", { name: /karanlık temaya geç/i }));
    expect(setTitlebarTheme).toHaveBeenLastCalledWith(true);
  });
});
