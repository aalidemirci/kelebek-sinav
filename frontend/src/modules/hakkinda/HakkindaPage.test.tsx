// Hakkında sayfası testleri: üst yazı dil bilgisi düzeltmesi ve şifreleme
// yöntemi adlarının YALNIZ bu sayfada geçmesi (docs/sozluk.md §1 — ayar
// ekranları "güçlü şifrelemeyle korunur" der).

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HakkindaPage from "./HakkindaPage";

describe("HakkindaPage", () => {
  it("üst yazı geliştiriciyi, iletişim bilgilerini ve kullanım koşullarını sayar", () => {
    render(<HakkindaPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Hakkında ve Lisans" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Programın geliştiricisi, iletişim bilgileri ve kullanım koşulları."),
    ).toBeInTheDocument();
  });

  it("teknik bilgiler kartı şifreleme yöntemlerini adıyla verir", () => {
    render(<HakkindaPage />);

    expect(screen.getByRole("heading", { level: 2, name: "Teknik bilgiler" })).toBeInTheDocument();
    expect(screen.getByText(/X25519 ve AES-256-GCM/)).toBeInTheDocument();
    expect(screen.getByText(/Argon2id/)).toBeInTheDocument();
  });
});
