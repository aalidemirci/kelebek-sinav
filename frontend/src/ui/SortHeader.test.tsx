// Paylaşılan sıralama şeridi (Tur 364) testi: aktif alan aria-pressed; yeni alana
// tıklayınca artan ile başlar; aktif alana tekrar tıklayınca yön değişir (artan↔azalan).
// nextSort saf fonksiyonu ayrıca birim test edilir. Türkçe collation + sayısal
// sıralama backend'de (pytest test_students_list / test_users_list).

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import SortHeader, { nextSort } from "./SortHeader";

const FIELDS = [
  { key: "name", label: "Ad" },
  { key: "number", label: "Okul No" },
];

describe("nextSort", () => {
  it("yeni alan → artan; aktif alan → yön çevirir", () => {
    expect(nextSort("name", "number")).toBe("number"); // yeni alan artan
    expect(nextSort("name", "name")).toBe("-name"); // artan → azalan
    expect(nextSort("-number", "number")).toBe("number"); // azalan → artan
  });
});

describe("SortHeader", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("varsayılan: ilk alan aktif; ikinci alana tıklayınca o alana geçer", async () => {
    const onChange = vi.fn();
    render(<SortHeader fields={FIELDS} value="name" onChange={onChange} />);
    expect(screen.getByRole("button", { name: /Ad/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /Okul No/ })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    await userEvent.click(screen.getByRole("button", { name: /Okul No/ }));
    expect(onChange).toHaveBeenCalledWith("number");
  });

  it("aktif alana tekrar tıklayınca yön değişir (name → -name)", async () => {
    const onChange = vi.fn();
    render(<SortHeader fields={FIELDS} value="name" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: /Ad/ }));
    expect(onChange).toHaveBeenCalledWith("-name");
  });

  it("-number iken ikinci alan aktif; tıklayınca artana döner, ilk alana tıklayınca ona geçer", async () => {
    const onChange = vi.fn();
    render(<SortHeader fields={FIELDS} value="-number" onChange={onChange} />);
    const noBtn = screen.getByRole("button", { name: /Okul No/ });
    expect(noBtn).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(noBtn);
    expect(onChange).toHaveBeenCalledWith("number");

    onChange.mockClear();
    await userEvent.click(screen.getByRole("button", { name: /Ad/ }));
    expect(onChange).toHaveBeenCalledWith("name");
  });
});
