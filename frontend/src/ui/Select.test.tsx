// Select — yerel <select> üzerinde etiket bağı, yer tutucu ve hata duyurusu.
// TextField ile AYNI erişilebilirlik sözleşmesini taşır (hata `role="alert"`).

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import Select from "./Select";

const DUZENLER = [
  { value: "BUTTERFLY", label: "Kelebek (karışık dağıtım)" },
  { value: "HOME_CLASSROOM", label: "Kendi dersliğinde" },
];

describe("Select", () => {
  it("seçenekleri listeler ve seçim onChange'e ulaşır", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Select label="Düzen" options={DUZENLER} value="BUTTERFLY" onChange={onChange} />);

    await user.selectOptions(screen.getByLabelText("Düzen"), "HOME_CLASSROOM");

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(screen.getAllByRole("option")).toHaveLength(2);
  });

  it("yer tutucu boş değerli ilk seçenektir; verilmezse basılmaz", () => {
    const { rerender } = render(
      <Select label="Salon" options={DUZENLER} placeholder="Seçin" defaultValue="" />,
    );

    const secenekler = screen.getAllByRole("option") as HTMLOptionElement[];
    expect(secenekler[0]).toHaveTextContent("Seçin");
    expect(secenekler[0].value).toBe("");

    rerender(<Select label="Salon" options={DUZENLER} defaultValue="BUTTERFLY" />);
    expect(screen.getAllByRole("option")).toHaveLength(2);
  });

  it("hata metni alert olarak duyurulur ve alana bağlanır", () => {
    render(<Select label="Dönem" options={DUZENLER} error="Dönem seçin." defaultValue="" />);

    const alan = screen.getByLabelText("Dönem");
    const hata = screen.getByRole("alert");
    expect(hata).toHaveTextContent("Dönem seçin.");
    expect(alan).toHaveAttribute("aria-invalid", "true");
    expect(alan).toHaveAttribute("aria-describedby", hata.id);
  });

  it("yardımcı metin duyurulmaz", () => {
    render(
      <Select label="Tür" options={DUZENLER} helperText="Sonradan değişmez." defaultValue="" />,
    );

    expect(screen.getByText("Sonradan değişmez.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
