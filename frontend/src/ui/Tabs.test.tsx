// Tur 60 — Tabs primitifi: render + aktif sekme + tıklama. RTL + Vitest.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import Tabs, { tabPanelProps } from "./Tabs";

const ITEMS = [
  { key: "a", label: "Bir", icon: "shield" },
  { key: "b", label: "İki" },
];

describe("Tabs", () => {
  it("tüm sekmeleri role=tab ile basar", () => {
    render(<Tabs items={ITEMS} active="a" onChange={() => {}} />);
    expect(screen.getAllByRole("tab")).toHaveLength(2);
    expect(screen.getByRole("tab", { name: /Bir/ })).toBeInTheDocument();
  });

  it("aktif sekme aria-selected=true alır", () => {
    render(<Tabs items={ITEMS} active="b" onChange={() => {}} />);
    expect(screen.getByRole("tab", { name: "İki" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /Bir/ })).toHaveAttribute("aria-selected", "false");
  });

  it("tıklamada onChange ilgili key ile çağrılır", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Tabs items={ITEMS} active="a" onChange={onChange} />);
    await user.click(screen.getByRole("tab", { name: "İki" }));
    expect(onChange).toHaveBeenCalledWith("b");
  });

  it("yoğunluğa duyarlı sekme yüksekliği kullanır", () => {
    render(<Tabs items={ITEMS} active="a" onChange={() => {}} />);
    expect(screen.getByRole("tab", { name: /Bir/ }).className).toContain(
      "h-[var(--ks-control-height)]",
    );
  });

  // C3 (Tur 116) — WAI-ARIA klavye navigasyonu + roving tabindex.
  it("roving tabindex: yalnız aktif sekme tabIndex=0, diğerleri -1", () => {
    render(<Tabs items={ITEMS} active="a" onChange={() => {}} />);
    expect(screen.getByRole("tab", { name: /Bir/ })).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("tab", { name: "İki" })).toHaveAttribute("tabindex", "-1");
  });

  it("Sağ ok bir sonraki sekmeye geçer (otomatik etkinleştirme)", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Tabs items={ITEMS} active="a" onChange={onChange} />);
    screen.getByRole("tab", { name: /Bir/ }).focus();
    await user.keyboard("{ArrowRight}");
    expect(onChange).toHaveBeenCalledWith("b");
  });

  it("Sol ok başta iken sona sarar", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Tabs items={ITEMS} active="a" onChange={onChange} />);
    screen.getByRole("tab", { name: /Bir/ }).focus();
    await user.keyboard("{ArrowLeft}");
    expect(onChange).toHaveBeenCalledWith("b");
  });

  it("End son sekmeye, Home ilk sekmeye götürür", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Tabs items={ITEMS} active="a" onChange={onChange} />);
    screen.getByRole("tab", { name: /Bir/ }).focus();
    await user.keyboard("{End}");
    expect(onChange).toHaveBeenLastCalledWith("b");
    await user.keyboard("{Home}");
    expect(onChange).toHaveBeenLastCalledWith("a");
  });

  // C5 (Tur 136) — WAI-ARIA tabpanel bağı (id + aria-controls + aria-labelledby).
  it("idBase verilince sekme id + aria-controls alır", () => {
    render(<Tabs items={ITEMS} active="a" onChange={() => {}} idBase="x" />);
    const tab = screen.getByRole("tab", { name: /Bir/ });
    expect(tab).toHaveAttribute("id", "x-tab-a");
    expect(tab).toHaveAttribute("aria-controls", "x-panel");
  });

  it("idBase verilmezse sekme id/aria-controls taşımaz (geriye uyum)", () => {
    render(<Tabs items={ITEMS} active="a" onChange={() => {}} />);
    const tab = screen.getByRole("tab", { name: /Bir/ });
    expect(tab).not.toHaveAttribute("id");
    expect(tab).not.toHaveAttribute("aria-controls");
  });

  it("tabPanelProps panel rol/id/aria-labelledby döndürür (aktif sekmeye bağlı)", () => {
    expect(tabPanelProps("x", "b")).toEqual({
      role: "tabpanel",
      id: "x-panel",
      "aria-labelledby": "x-tab-b",
    });
  });
});
