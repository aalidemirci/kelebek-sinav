// Tur 122 — M3 Snackbar (sunum) davranış testi: role=status/alert, eylem butonu,
// kapat ikonu (aria-label). React Testing Library + Vitest.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import Snackbar from "./Snackbar";

describe("Snackbar", () => {
  it("mesajı role=status (polite) ile basar", () => {
    render(<Snackbar message="Kurum bilgisi kaydedildi." />);
    expect(screen.getByRole("status")).toHaveTextContent("Kurum bilgisi kaydedildi.");
  });

  it("assertive=true hata için role=alert ile basar", () => {
    render(<Snackbar message="Kayıt başarısız." assertive />);
    expect(screen.getByRole("alert")).toHaveTextContent("Kayıt başarısız.");
  });

  it("eylem butonuna tıklayınca onClick çağrılır", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Snackbar message="Bildirim silindi." action={{ label: "Geri al", onClick }} />);
    await user.click(screen.getByRole("button", { name: "Geri al" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("onDismiss verilince kapat (×) ikonu basar ve tıklanınca çağrılır", async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();
    render(<Snackbar message="Bilgi." onDismiss={onDismiss} />);
    await user.click(screen.getByRole("button", { name: "Kapat" }));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("onDismiss yokken kapat ikonu basmaz", () => {
    render(<Snackbar message="Bilgi." />);
    expect(screen.queryByRole("button", { name: "Kapat" })).toBeNull();
  });
});
