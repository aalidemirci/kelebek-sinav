// TextField — etiket/alan bağı, zorunlu işareti ve hata duyurusu. Formların
// tamamı bu bileşenden geçtiği için erişilebilirlik sözleşmesi burada sabitlenir:
// hata metni `role="alert"` ile BELİRDİĞİ anda duyurulur ve alana
// `aria-describedby` ile bağlanır; yardımcı metin statiktir, duyurulmaz.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import TextField from "./TextField";

describe("TextField", () => {
  it("etiket alana bağlıdır ve yazılan değer onChange'e ulaşır", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TextField label="Salon adı" value="" onChange={onChange} />);

    await user.type(screen.getByLabelText("Salon adı"), "A");

    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("zorunlu alanda yıldız gösterir ve alanı required işaretler", () => {
    render(<TextField label="Oturum adı" required defaultValue="" />);

    expect(screen.getByText("*")).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toBeRequired();
  });

  it("hata metni alert olarak duyurulur ve alana bağlanır", () => {
    render(<TextField label="Kapasite" error="Kapasite 1-60 arasında olmalı." defaultValue="" />);

    const alan = screen.getByLabelText("Kapasite");
    const hata = screen.getByRole("alert");
    expect(hata).toHaveTextContent("Kapasite 1-60 arasında olmalı.");
    expect(alan).toHaveAttribute("aria-invalid", "true");
    expect(alan).toHaveAttribute("aria-describedby", hata.id);
  });

  it("yardımcı metin duyurulmaz ama alana bağlanır; hata varsa yerini hataya bırakır", () => {
    const { rerender } = render(
      <TextField label="Dağıtım numarası" helperText="Boş bırakılırsa rastgele." defaultValue="" />,
    );

    const yardim = screen.getByText("Boş bırakılırsa rastgele.");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Dağıtım numarası")).toHaveAttribute(
      "aria-describedby",
      yardim.id,
    );
    expect(screen.getByLabelText("Dağıtım numarası")).not.toHaveAttribute("aria-invalid");

    rerender(
      <TextField
        label="Dağıtım numarası"
        helperText="Boş bırakılırsa rastgele."
        error="Sayı girin."
        defaultValue=""
      />,
    );

    expect(screen.queryByText("Boş bırakılırsa rastgele.")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Sayı girin.");
  });

  it("boş etiketle <label> basmaz; erişilebilir ad aria-label'dan gelir", () => {
    const { container } = render(<TextField label="" aria-label="Öğrenci ara" defaultValue="" />);

    expect(container.querySelector("label")).toBeNull();
    expect(screen.getByRole("textbox", { name: "Öğrenci ara" })).toBeInTheDocument();
  });
});
