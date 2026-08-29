// Kilit ekranı testi (F5-D5): parolayla açma, yanlış parolada Türkçe hata,
// "parolamı unuttum" → kurtarma anahtarı + yeni parola akışı.
// API istemcisi vi.mock ile taklit edilir — ağ yok. Auth yok (tek kullanıcı).

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const guvenlik = vi.hoisted(() => ({
  durum: vi.fn(),
  kur: vi.fn(),
  ac: vi.fn(),
  kilitle: vi.fn(),
  kurtar: vi.fn(),
  parolaDegistir: vi.fn(),
  kaldir: vi.fn(),
}));

vi.mock("./api", () => ({ guvenlikApi: guvenlik }));

import KilitEkrani from "./KilitEkrani";

describe("KilitEkrani", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("doğru parolayla kilidi açar", async () => {
    const kullanici = userEvent.setup();
    guvenlik.ac.mockResolvedValue({ locked: false });
    const onAcildi = vi.fn();
    render(<KilitEkrani onAcildi={onAcildi} />);

    await kullanici.type(screen.getByLabelText(/Uygulama parolası/), "Deneme-Parola-1");
    await kullanici.click(screen.getByRole("button", { name: "Aç" }));

    await waitFor(() => expect(onAcildi).toHaveBeenCalledTimes(1));
    expect(guvenlik.ac).toHaveBeenCalledWith("Deneme-Parola-1");
  });

  it("yanlış parolada backend mesajını gösterir ve içeri almaz", async () => {
    const kullanici = userEvent.setup();
    guvenlik.ac.mockRejectedValue(new Error("Parola hatalı."));
    const onAcildi = vi.fn();
    render(<KilitEkrani onAcildi={onAcildi} />);

    await kullanici.type(screen.getByLabelText(/Uygulama parolası/), "yanlis-parola");
    await kullanici.click(screen.getByRole("button", { name: "Aç" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Parola hatalı.");
    expect(onAcildi).not.toHaveBeenCalled();
  });

  it("kurtarma anahtarıyla açar ve yeni parola belirletir", async () => {
    const kullanici = userEvent.setup();
    guvenlik.kurtar.mockResolvedValue({ locked: false });
    const onAcildi = vi.fn();
    render(<KilitEkrani onAcildi={onAcildi} />);

    await kullanici.click(screen.getByRole("button", { name: "Parolamı unuttum" }));
    await kullanici.type(screen.getByLabelText(/Kurtarma anahtarı/), "AAAA-BBBB");
    await kullanici.type(screen.getByLabelText(/Yeni parola/), "Yeni-Parola-9");
    await kullanici.click(screen.getByRole("button", { name: "Kurtar ve aç" }));

    await waitFor(() => expect(onAcildi).toHaveBeenCalledTimes(1));
    expect(guvenlik.kurtar).toHaveBeenCalledWith("AAAA-BBBB", "Yeni-Parola-9");
  });

  it("yarım kalan geçişte kullanıcıyı bilgilendirir", () => {
    render(<KilitEkrani onAcildi={vi.fn()} yarimGecis />);
    expect(screen.getByText(/yarıda kalmış/i)).toBeInTheDocument();
  });

  it("korumanın tam disk şifreleme OLMADIĞINI açıkça yazar", () => {
    render(<KilitEkrani onAcildi={vi.fn()} />);
    expect(screen.getByText(/TAM DİSK ŞİFRELEME/)).toBeInTheDocument();
    expect(screen.getByText(/BitLocker/)).toBeInTheDocument();
  });
});
