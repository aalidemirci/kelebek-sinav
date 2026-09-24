// Kurtarma anahtarını yenileme kartı: onay diyaloğu DÜRÜST metni (eski yedekler
// eski anahtarla açılır; yenileme tam iptal değildir) gösterir, parolayı ister;
// yanlış parolada backend iletisi görünür; başarıda yeni anahtar kurulumdaki
// diyalogla, "kaydettim" onaylanmadan kapanmayacak biçimde gösterilir.

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { SnackbarProvider } from "../../ui/SnackbarProvider";

const guvenlik = vi.hoisted(() => ({ kurtarmaAnahtariniYenile: vi.fn() }));

vi.mock("./api", () => ({ guvenlikApi: guvenlik }));
vi.mock("../../lib/download", () => ({ saveBlob: vi.fn() }));

import KurtarmaAnahtariniYenileKarti from "./KurtarmaAnahtariniYenileKarti";

const YENI = "WXYZ-2345-ABCD-EFGH-IJKL-MNOP-QRST-UVWX";

function ekranaBas() {
  return render(
    <SnackbarProvider>
      <KurtarmaAnahtariniYenileKarti okulAdi="Deneme Anadolu Lisesi" />
    </SnackbarProvider>,
  );
}

async function diyaloguAc(kullanici: ReturnType<typeof userEvent.setup>) {
  await kullanici.click(screen.getByRole("button", { name: "Kurtarma anahtarını yenile" }));
  return screen.findByRole("dialog", { name: "Kurtarma anahtarı yenilensin mi?" });
}

describe("KurtarmaAnahtariniYenileKarti", () => {
  beforeEach(() => vi.clearAllMocks());

  it("parola değişiminin eski anahtarı geçersiz kılmadığını söyler", () => {
    ekranaBas();
    expect(screen.getByText(/Parolayı değiştirmek eski kurtarma anahtarını/)).toBeInTheDocument();
  });

  it("onay diyaloğu eski yedekler ve tam iptal olmadığı konusunda dürüsttür", async () => {
    const kullanici = userEvent.setup();
    ekranaBas();
    const diyalog = await diyaloguAc(kullanici);

    expect(within(diyalog).getByText(/eski anahtarla açılmaya devam eder/)).toBeInTheDocument();
    expect(within(diyalog).getByText(/tam koruma değildir/)).toBeInTheDocument();
    expect(within(diyalog).getByText(/Eski anahtar bu bilgisayardaki/)).toBeInTheDocument();
    // Parola girilmeden üretim düğmesi kapalı.
    expect(within(diyalog).getByRole("button", { name: "Yeni anahtar üret" })).toBeDisabled();
  });

  it("yanlış parolada backend iletisini gösterir, anahtar göstermez", async () => {
    const kullanici = userEvent.setup();
    guvenlik.kurtarmaAnahtariniYenile.mockRejectedValue(
      new ApiError(400, "validation_error", "Parola hatalı."),
    );
    ekranaBas();
    const diyalog = await diyaloguAc(kullanici);

    await kullanici.type(within(diyalog).getByLabelText(/Uygulama parolası/), "yanlis-parola");
    await kullanici.click(within(diyalog).getByRole("button", { name: "Yeni anahtar üret" }));

    expect(await within(diyalog).findByText("Parola hatalı.")).toBeInTheDocument();
    expect(screen.queryByTestId("kurtarma-anahtari")).toBeNull();
  });

  it("başarıda yeni anahtarı gösterir ve onaysız kapatmaz", async () => {
    const kullanici = userEvent.setup();
    guvenlik.kurtarmaAnahtariniYenile.mockResolvedValue({ recovery_key: YENI });
    ekranaBas();
    const diyalog = await diyaloguAc(kullanici);

    await kullanici.type(within(diyalog).getByLabelText(/Uygulama parolası/), "Deneme-Parola-1");
    await kullanici.click(within(diyalog).getByRole("button", { name: "Yeni anahtar üret" }));

    expect(guvenlik.kurtarmaAnahtariniYenile).toHaveBeenCalledWith("Deneme-Parola-1");
    const anahtarDiyalogu = await screen.findByRole("dialog", {
      name: "Yeni kurtarma anahtarınız",
    });
    expect(within(anahtarDiyalogu).getByTestId("kurtarma-anahtari")).toHaveTextContent(YENI);
    expect(
      within(anahtarDiyalogu).getByText(/eski anahtarla açılmaya devam eder/),
    ).toBeInTheDocument();
    const kapat = within(anahtarDiyalogu).getByRole("button", { name: "Kapat" });
    expect(kapat).toBeDisabled();

    await kullanici.click(within(anahtarDiyalogu).getByRole("checkbox"));
    await kullanici.click(kapat);
    expect(screen.queryByRole("dialog", { name: "Yeni kurtarma anahtarınız" })).toBeNull();
  });
});
