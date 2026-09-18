// Autocomplete — ARIA 1.2 combobox sözleşmesi (18.09.2026 değerlendirmesi):
// rol ve durum öznitelikleri SARMALAYICI div'de değil, odağı alan INPUT'tadır.
// Seçim/klavye davranışı da burada sabitlenir (bileşenin ilk birim testi).

import { useState } from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import Autocomplete from "./Autocomplete";

interface Kisi {
  id: number;
  ad: string;
  muaf?: boolean;
}

// KVKK: adlar uydurmadır.
const KISILER: Kisi[] = [
  { id: 1, ad: "Ayşe Yılmaz" },
  { id: 2, ad: "Ayhan Demir", muaf: true },
  { id: 3, ad: "Aylin Kaya" },
];

const search = (q: string) =>
  Promise.resolve(
    KISILER.filter((k) => k.ad.toLocaleLowerCase("tr").includes(q.toLocaleLowerCase("tr"))),
  );

/** Gerçek kullanımın aynası: seçim ebeveynde tutulur, seçilince alan chip'e döner. */
function Alan({
  label,
  ariaLabel,
  onSelect,
}: {
  label: string;
  ariaLabel?: string;
  onSelect: (k: Kisi) => void;
}) {
  const [secili, setSecili] = useState<Kisi | null>(null);
  return (
    <Autocomplete<Kisi>
      label={label}
      ariaLabel={ariaLabel}
      selected={secili}
      search={search}
      onSelect={(k) => {
        setSecili(k);
        onSelect(k);
      }}
      onClear={() => setSecili(null)}
      getKey={(k) => k.id}
      getLabel={(k) => k.ad}
      getDisabled={(k) => (k.muaf ? "muaf" : undefined)}
      minChars={1}
      debounceMs={0}
    />
  );
}

function renderAlan(props: { label?: string; ariaLabel?: string } = {}) {
  const onSelect = vi.fn();
  render(
    <Alan label={props.label ?? "Öğretmen"} ariaLabel={props.ariaLabel} onSelect={onSelect} />,
  );
  return { onSelect };
}

describe("Autocomplete — ARIA 1.2 combobox", () => {
  it("rol INPUT'tadır: etiketle bulunan alan combobox'tır, sarmalayıcı rol taşımaz", () => {
    renderAlan();

    const alan = screen.getByLabelText(/Öğretmen/);
    expect(alan.tagName).toBe("INPUT");
    expect(alan).toHaveAttribute("role", "combobox");
    expect(alan).toHaveAttribute("aria-haspopup", "listbox");
    expect(alan).toHaveAttribute("aria-autocomplete", "list");
    // Tek combobox vardır ve o da input'tur (eski desende rol div'deydi).
    expect(screen.getAllByRole("combobox")).toEqual([alan]);
    expect(alan.parentElement).not.toHaveAttribute("role");
  });

  it("kapalıyken aria-expanded=false ve aria-controls yok; açılınca listeye işaret eder", async () => {
    const user = userEvent.setup();
    renderAlan();
    const alan = screen.getByRole("combobox", { name: /Öğretmen/ });

    expect(alan).toHaveAttribute("aria-expanded", "false");
    expect(alan).not.toHaveAttribute("aria-controls");

    await user.type(alan, "ay");
    const liste = await screen.findByRole("listbox");
    expect(alan).toHaveAttribute("aria-expanded", "true");
    expect(alan).toHaveAttribute("aria-controls", liste.id);
    expect(within(liste).getAllByRole("option")).toHaveLength(3);
  });

  it("ok tuşlarıyla vurgu aria-activedescendant ile izlenir; Enter seçer ve liste kapanır", async () => {
    const user = userEvent.setup();
    const { onSelect } = renderAlan();
    const alan = screen.getByRole("combobox", { name: /Öğretmen/ });

    await user.type(alan, "ay");
    const secenekler = within(await screen.findByRole("listbox")).getAllByRole("option");
    expect(alan).toHaveAttribute("aria-activedescendant", secenekler[0].id);

    await user.keyboard("{ArrowDown}{ArrowDown}");
    expect(alan).toHaveAttribute("aria-activedescendant", secenekler[2].id);
    expect(secenekler[2]).toHaveAttribute("aria-selected", "true");

    await user.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledWith(KISILER[2]);
    // Seçimden sonra liste kapanır ve alan seçili chip'e döner.
    await waitFor(() => expect(screen.queryByRole("listbox")).not.toBeInTheDocument());
    expect(screen.getByText("Aylin Kaya")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Seçimi temizle" })).toBeInTheDocument();
  });

  it("seçilemeyen öğe görünür ama ne tıkla ne Enter ile seçilir (neden etiketiyle)", async () => {
    const user = userEvent.setup();
    const { onSelect } = renderAlan();
    const alan = screen.getByRole("combobox", { name: /Öğretmen/ });

    await user.type(alan, "ayhan");
    const secenek = await screen.findByRole("option", { name: /Ayhan Demir/ });
    expect(secenek).toHaveAttribute("aria-disabled", "true");
    expect(within(secenek).getByText(/muaf/)).toBeInTheDocument();

    await user.click(secenek);
    await user.keyboard("{Enter}");
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("Escape listeyi kapatır", async () => {
    const user = userEvent.setup();
    renderAlan();
    const alan = screen.getByRole("combobox", { name: /Öğretmen/ });

    await user.type(alan, "ay");
    await screen.findByRole("listbox");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(alan).toHaveAttribute("aria-expanded", "false");
  });

  it("görsel etiket yokken erişilebilir ad ariaLabel'dan gelir", () => {
    renderAlan({ label: "", ariaLabel: "D-204 için gözetmen ata" });
    expect(screen.getByRole("combobox", { name: "D-204 için gözetmen ata" })).toBeInTheDocument();
  });
});
