// Güvenlik ayarları testi (F5-D5): parola koyma → kurtarma anahtarı diyaloğunun
// ONAYSIZ KAPANMAMASI, parola değiştirme/kaldırma akışları ve dürüst KVKK metni.
// En kritik iddia: kurtarma anahtarı ekranda GÖRÜNÜR ve "kaydettim" işaretlenene
// kadar "Kapat" düğmesi kapalıdır (anahtar bir daha üretilemez).

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";

const guvenlik = vi.hoisted(() => ({
  durum: vi.fn(),
  kur: vi.fn(),
  ac: vi.fn(),
  kilitle: vi.fn(),
  kurtar: vi.fn(),
  parolaDegistir: vi.fn(),
  kaldir: vi.fn(),
}));
const download = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("./api", () => ({ guvenlikApi: guvenlik }));
vi.mock("./SifreliYedekleme", () => ({ default: () => null }));
vi.mock("./YedektenGeriYukleme", () => ({ default: () => null }));
vi.mock("../../lib/download", () => ({ saveBlob: download.saveBlob }));

import GuvenlikAyarlari from "./GuvenlikAyarlari";

const PAROLASIZ = {
  password_set: false,
  locked: false,
  transition_pending: false,
  transition: "",
  protected_fields: ["ad", "soyad"],
};
const PAROLALI = { ...PAROLASIZ, password_set: true };

function ekranaBas() {
  return render(
    <SnackbarProvider>
      <GuvenlikAyarlari okulAdi="Deneme Anadolu Lisesi" />
    </SnackbarProvider>,
  );
}

describe("GuvenlikAyarlari", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    guvenlik.durum.mockResolvedValue(PAROLASIZ);
  });

  it("parolasız durumda dürüst kapsam metnini ve korunan alanları gösterir", async () => {
    ekranaBas();
    expect(await screen.findByText(/Kişisel veri alanları açık/)).toBeInTheDocument();
    expect(screen.getByText(/TAM DİSK ŞİFRELEME/)).toBeInTheDocument();
    expect(screen.getByText(/LUKS/)).toBeInTheDocument();
    expect(screen.getByText(/ad, soyad/)).toBeInTheDocument();
    // Şifrelenmeyen alanlar da açıkça söylenir.
    expect(screen.getByText(/Okul numarası, sınıf\/şube ve oturma düzeni/)).toBeInTheDocument();
  });

  it("parola koyar ve kurtarma anahtarını onay alınmadan kapatmaz", async () => {
    const kullanici = userEvent.setup();
    guvenlik.kur.mockResolvedValue({ ...PAROLALI, recovery_key: "AAAA-BBBB-CCCC-DDDD" });
    ekranaBas();

    await kullanici.click(await screen.findByRole("button", { name: "Parola koy" }));
    await kullanici.type(screen.getByLabelText(/^Yeni parola/), "Deneme-Parola-1");
    await kullanici.type(screen.getByLabelText(/tekrar/), "Deneme-Parola-1");
    await kullanici.click(screen.getByRole("button", { name: "Uygula" }));

    const diyalog = await screen.findByRole("dialog", { name: "Kurtarma anahtarınız" });
    expect(within(diyalog).getByTestId("kurtarma-anahtari")).toHaveTextContent(
      "AAAA-BBBB-CCCC-DDDD",
    );

    const kapat = within(diyalog).getByRole("button", { name: "Kapat" });
    expect(kapat).toBeDisabled();
    await kullanici.click(within(diyalog).getByRole("checkbox"));
    expect(kapat).toBeEnabled();
    await kullanici.click(kapat);
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "Kurtarma anahtarınız" })).toBeNull(),
    );
  });

  it("kurtarma anahtarı metin dosyası olarak indirilebilir", async () => {
    const kullanici = userEvent.setup();
    guvenlik.kur.mockResolvedValue({ ...PAROLALI, recovery_key: "AAAA-BBBB" });
    ekranaBas();

    await kullanici.click(await screen.findByRole("button", { name: "Parola koy" }));
    await kullanici.type(screen.getByLabelText(/^Yeni parola/), "Deneme-Parola-1");
    await kullanici.type(screen.getByLabelText(/tekrar/), "Deneme-Parola-1");
    await kullanici.click(screen.getByRole("button", { name: "Uygula" }));

    const diyalog = await screen.findByRole("dialog", { name: "Kurtarma anahtarınız" });
    await kullanici.click(
      within(diyalog).getByRole("button", { name: /Metin dosyası olarak kaydet/ }),
    );
    expect(download.saveBlob).toHaveBeenCalledWith(expect.any(Blob), "kurtarma-anahtari.txt");
  });

  it("eşleşmeyen parola tekrarında istek atmaz", async () => {
    const kullanici = userEvent.setup();
    ekranaBas();

    await kullanici.click(await screen.findByRole("button", { name: "Parola koy" }));
    await kullanici.type(screen.getByLabelText(/^Yeni parola/), "Deneme-Parola-1");
    await kullanici.type(screen.getByLabelText(/tekrar/), "baska-bir-sey");
    await kullanici.click(screen.getByRole("button", { name: "Uygula" }));

    expect(await screen.findByText("Parolalar eşleşmedi.")).toBeInTheDocument();
    expect(guvenlik.kur).not.toHaveBeenCalled();
  });

  it("parolalı durumda değiştirme/kilitleme/kaldırma eylemlerini sunar", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValue(PAROLALI);
    guvenlik.kaldir.mockResolvedValue(PAROLASIZ);
    ekranaBas();

    expect(await screen.findByText(/Kişisel veri alanları şifreli/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Parolayı değiştir" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Şimdi kilitle" })).toBeInTheDocument();

    await kullanici.click(screen.getByRole("button", { name: "Parolayı kaldır" }));
    expect(screen.getByText(/düz metne döner/)).toBeInTheDocument();
    await kullanici.type(screen.getByLabelText(/Mevcut parola/), "Deneme-Parola-1");
    await kullanici.click(screen.getByRole("button", { name: "Uygula" }));

    await waitFor(() => expect(guvenlik.kaldir).toHaveBeenCalledWith("Deneme-Parola-1"));
  });

  it("yanlış parolayla kaldırma denemesinde backend mesajını gösterir", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValue(PAROLALI);
    guvenlik.kaldir.mockRejectedValue(new Error("Parola hatalı."));
    ekranaBas();

    await kullanici.click(await screen.findByRole("button", { name: "Parolayı kaldır" }));
    await kullanici.type(screen.getByLabelText(/Mevcut parola/), "yanlis");
    await kullanici.click(screen.getByRole("button", { name: "Uygula" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Parola hatalı.");
  });
});
