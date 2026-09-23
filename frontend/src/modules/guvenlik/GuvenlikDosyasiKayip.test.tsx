// Güvenlik dosyası kayıp ekranı: ne olduğunu ve çıkış yollarını söyler; yeni
// parola kurma yolu SUNMAZ. "Sıfırla" kartı yalnız backend `reset_available`
// derse görünür ve onaydan sonra çalışır.

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";

const guvenlik = vi.hoisted(() => ({ sifirla: vi.fn() }));

vi.mock("./api", () => ({ guvenlikApi: guvenlik }));
vi.mock("./YedektenGeriYukleme", () => ({
  default: ({ kayipKipi }: { kayipKipi?: boolean }) => (
    <p>{kayipKipi ? "Geri yükleme kartı (kayıp kipi)" : "Geri yükleme kartı"}</p>
  ),
}));

import GuvenlikDosyasiKayip from "./GuvenlikDosyasiKayip";

function ekranaBas(sifirlanabilir = false) {
  const denetle = vi.fn();
  render(
    <ConfirmProvider>
      <GuvenlikDosyasiKayip onYenidenDenetle={denetle} sifirlanabilir={sifirlanabilir} />
    </ConfirmProvider>,
  );
  return denetle;
}

describe("GuvenlikDosyasiKayip", () => {
  beforeEach(() => vi.clearAllMocks());

  it("ne olduğunu ve iki çıkış yolunu söyler, yeni parola yolu sunmaz", async () => {
    const kullanici = userEvent.setup();
    const denetle = ekranaBas();

    expect(screen.getByText(/Yeni parola da kurulamaz/)).toBeInTheDocument();
    expect(
      screen.getByText(/guvenlik.json dosyasını veri klasörüne geri koyun/),
    ).toBeInTheDocument();
    expect(screen.getByText(/güvenlik dosyasını da içinde taşır/)).toBeInTheDocument();
    expect(screen.getByText("Geri yükleme kartı (kayıp kipi)")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Parola koy/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /sıfırla/i })).toBeNull();

    await kullanici.click(screen.getByRole("button", { name: "Yeniden denetle" }));
    expect(denetle).toHaveBeenCalledTimes(1);
  });

  it("sıfırlanabilirken onaydan sonra sıfırlar ve durumu yeniden okutur", async () => {
    const kullanici = userEvent.setup();
    guvenlik.sifirla.mockResolvedValue({});
    const denetle = ekranaBas(true);

    expect(screen.getByText(/hiçbir kaydı korumuyor/)).toBeInTheDocument();
    await kullanici.click(screen.getByRole("button", { name: "Güvenlik dosyasını sıfırla" }));
    const diyalog = await screen.findByRole("dialog", {
      name: "Güvenlik dosyası sıfırlansın mı?",
    });
    await kullanici.click(within(diyalog).getByRole("button", { name: "Sıfırla" }));

    expect(guvenlik.sifirla).toHaveBeenCalledTimes(1);
    expect(denetle).toHaveBeenCalledTimes(1);
  });

  it("onay verilmezse sıfırlamaz", async () => {
    const kullanici = userEvent.setup();
    ekranaBas(true);

    await kullanici.click(screen.getByRole("button", { name: "Güvenlik dosyasını sıfırla" }));
    const diyalog = await screen.findByRole("dialog");
    await kullanici.click(within(diyalog).getByRole("button", { name: "Vazgeç" }));

    expect(guvenlik.sifirla).not.toHaveBeenCalled();
  });

  it("sıfırlama reddedilirse backend iletisini gösterir", async () => {
    const kullanici = userEvent.setup();
    guvenlik.sifirla.mockRejectedValue(
      new ApiError(409, "sifirlama_uygun_degil", "Güvenlik dosyası sıfırlanamaz."),
    );
    const denetle = ekranaBas(true);

    await kullanici.click(screen.getByRole("button", { name: "Güvenlik dosyasını sıfırla" }));
    const diyalog = await screen.findByRole("dialog");
    await kullanici.click(within(diyalog).getByRole("button", { name: "Sıfırla" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Güvenlik dosyası sıfırlanamaz.");
    expect(denetle).not.toHaveBeenCalled();
  });
});
