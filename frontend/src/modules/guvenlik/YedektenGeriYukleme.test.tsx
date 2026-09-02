// Yedekten geri yükleme kartı testleri: liste + kip etiketleri, şifreli yedekte
// sır zorunluluğu (istemci tarafı), onay akışı, FormData içeriği (kaynak ad YA
// DA dosya) ve başarıda "yeniden başlat" olayının yayınlanması. Backend hatası
// Türkçe mesajıyla kartta gösterilir.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { YENIDEN_BASLAT_OLAYI } from "../../lib/restart";
import { ConfirmProvider } from "../../ui/ConfirmProvider";

const guvenlik = vi.hoisted(() => ({
  yedekler: vi.fn(),
  geriYukle: vi.fn(),
}));

vi.mock("./api", () => ({ guvenlikApi: guvenlik }));

import YedektenGeriYukleme from "./YedektenGeriYukleme";

const LISTE = {
  backup_dir: "C:\\KelebekSinav\\backups",
  backups: [
    {
      name: "gunluk-2026-09-01.ksbak",
      size: 2 * 1024 * 1024,
      modified_at: "2026-09-01T08:00:00+03:00",
      encrypted: true,
    },
    {
      name: "gunluk-2026-08-31.ksbak",
      size: 4096,
      modified_at: "2026-08-31T08:00:00+03:00",
      encrypted: false,
    },
  ],
};

const SONUC = {
  encrypted: false,
  old_db_name: "db-onceki-2026-09-02-101010.sqlite3",
  state_written: false,
  restart_required: true,
};

function ekranaBas() {
  return render(
    <ConfirmProvider>
      <YedektenGeriYukleme />
    </ConfirmProvider>,
  );
}

/** Onay diyaloğundaki "Geri yükle" düğmesine basar (karttaki eş adlıdan ayrışır). */
async function onayla(kullanici: ReturnType<typeof userEvent.setup>) {
  const diyalog = await screen.findByRole("dialog", { name: "Yedekten geri yükle" });
  await kullanici.click(within(diyalog).getByRole("button", { name: "Geri yükle" }));
}

describe("YedektenGeriYukleme", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    guvenlik.yedekler.mockResolvedValue(LISTE);
  });

  it("yedekleri kip etiketleri ve yedek klasörüyle listeler", async () => {
    ekranaBas();

    expect(await screen.findByText("gunluk-2026-09-01.ksbak")).toBeInTheDocument();
    expect(screen.getByText(/şifreli/)).toBeInTheDocument();
    expect(screen.getByText(/düz/)).toBeInTheDocument();
    expect(screen.getByText("C:\\KelebekSinav\\backups")).toBeInTheDocument();
    // Kaynak seçilmeden geri yükleme düğmesi kapalıdır.
    expect(screen.getByRole("button", { name: "Geri yükle" })).toBeDisabled();
  });

  it("düz yedeği onayla geri yükler ve yeniden başlat olayını yayınlar", async () => {
    const kullanici = userEvent.setup();
    guvenlik.geriYukle.mockResolvedValue(SONUC);
    const dinleyici = vi.fn();
    window.addEventListener(YENIDEN_BASLAT_OLAYI, dinleyici);
    try {
      ekranaBas();

      await kullanici.click(await screen.findByRole("radio", { name: /gunluk-2026-08-31/ }));
      await kullanici.click(screen.getByRole("button", { name: "Geri yükle" }));
      // Onay metni kenara alma davranışını açıkça söyler.
      const diyalog = await screen.findByRole("dialog", { name: "Yedekten geri yükle" });
      expect(diyalog).toHaveTextContent("db-onceki-");
      await kullanici.click(within(diyalog).getByRole("button", { name: "Geri yükle" }));

      await waitFor(() => expect(guvenlik.geriYukle).toHaveBeenCalledTimes(1));
      const form = guvenlik.geriYukle.mock.calls[0][0] as FormData;
      expect(form.get("name")).toBe("gunluk-2026-08-31.ksbak");
      expect(form.get("file")).toBeNull();
      expect(form.get("password")).toBeNull();
      await waitFor(() => expect(dinleyici).toHaveBeenCalled());
    } finally {
      window.removeEventListener(YENIDEN_BASLAT_OLAYI, dinleyici);
    }
  });

  it("şifreli yedekte sır girilmeden istek atmaz", async () => {
    const kullanici = userEvent.setup();
    ekranaBas();

    await kullanici.click(await screen.findByRole("radio", { name: /gunluk-2026-09-01/ }));
    await kullanici.click(screen.getByRole("button", { name: "Geri yükle" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/şifreli/);
    expect(guvenlik.geriYukle).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("şifreli yedeği parolayla gönderir", async () => {
    const kullanici = userEvent.setup();
    guvenlik.geriYukle.mockResolvedValue({ ...SONUC, encrypted: true, state_written: true });
    ekranaBas();

    await kullanici.click(await screen.findByRole("radio", { name: /gunluk-2026-09-01/ }));
    await kullanici.type(screen.getByLabelText("Uygulama parolası"), "Deneme-Parola-1");
    await kullanici.click(screen.getByRole("button", { name: "Geri yükle" }));
    await onayla(kullanici);

    await waitFor(() => expect(guvenlik.geriYukle).toHaveBeenCalledTimes(1));
    const form = guvenlik.geriYukle.mock.calls[0][0] as FormData;
    expect(form.get("name")).toBe("gunluk-2026-09-01.ksbak");
    expect(form.get("password")).toBe("Deneme-Parola-1");
  });

  it("elden dosya yüklemesini FormData'ya koyar", async () => {
    const kullanici = userEvent.setup();
    guvenlik.geriYukle.mockResolvedValue(SONUC);
    ekranaBas();

    const dosya = new File([new Uint8Array([1, 2, 3])], "elden.ksbak");
    await kullanici.upload(await screen.findByLabelText(/elinizdeki yedek dosyası/), dosya);
    await kullanici.click(screen.getByRole("button", { name: "Geri yükle" }));
    await onayla(kullanici);

    await waitFor(() => expect(guvenlik.geriYukle).toHaveBeenCalledTimes(1));
    const form = guvenlik.geriYukle.mock.calls[0][0] as FormData;
    expect(form.get("name")).toBeNull();
    expect((form.get("file") as File).name).toBe("elden.ksbak");
  });

  it("onay reddedilirse istek atmaz", async () => {
    const kullanici = userEvent.setup();
    ekranaBas();

    await kullanici.click(await screen.findByRole("radio", { name: /gunluk-2026-08-31/ }));
    await kullanici.click(screen.getByRole("button", { name: "Geri yükle" }));
    const diyalog = await screen.findByRole("dialog", { name: "Yedekten geri yükle" });
    await kullanici.click(within(diyalog).getByRole("button", { name: "Vazgeç" }));

    expect(guvenlik.geriYukle).not.toHaveBeenCalled();
  });

  it("backend hatasını Türkçe mesajıyla gösterir", async () => {
    const kullanici = userEvent.setup();
    guvenlik.geriYukle.mockRejectedValue(
      new ApiError(400, "validation_error", "Yedek açılamadı: parola/kurtarma anahtarı hatalı."),
    );
    ekranaBas();

    await kullanici.click(await screen.findByRole("radio", { name: /gunluk-2026-08-31/ }));
    await kullanici.click(screen.getByRole("button", { name: "Geri yükle" }));
    await onayla(kullanici);

    expect(await screen.findByRole("alert")).toHaveTextContent("Yedek açılamadı");
  });

  it("yedek klasörü boşken dosya yükleme yolu açık kalır", async () => {
    guvenlik.yedekler.mockResolvedValue({ backup_dir: "C:\\x", backups: [] });
    ekranaBas();

    expect(await screen.findByText(/geri yüklenebilir dosya yok/)).toBeInTheDocument();
    expect(screen.getByLabelText(/elinizdeki yedek dosyası/)).toBeInTheDocument();
  });
});
