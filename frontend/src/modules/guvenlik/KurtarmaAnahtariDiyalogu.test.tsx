// Kurtarma anahtarı diyaloğu testleri: anahtar bir daha gösterilmediği için
// "kaydettim" onayı olmadan kapanmaz; metin çıktısındaki tarih lib/format ile
// (gg.aa.yyyy, yerel gün) basılır. KVKK: anahtar ve okul adı uydurmadır.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

const indirme = vi.hoisted(() => ({ saveBlob: vi.fn() }));
vi.mock("../../lib/download", () => ({ saveBlob: indirme.saveBlob }));

import KurtarmaAnahtariDiyalogu from "./KurtarmaAnahtariDiyalogu";

/** jsdom Blob'unda `.text()` her sürümde yok — FileReader ile okunur. */
function blobMetni(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const okuyucu = new FileReader();
    okuyucu.onload = () => resolve(String(okuyucu.result));
    okuyucu.onerror = () => reject(okuyucu.error ?? new Error("okunamadı"));
    okuyucu.readAsText(blob);
  });
}

afterEach(() => {
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe("KurtarmaAnahtariDiyalogu", () => {
  it("“kaydettim” işaretlenmeden kapatılamaz", async () => {
    const user = userEvent.setup();
    const onKapat = vi.fn();
    render(<KurtarmaAnahtariDiyalogu open anahtar="A1B2-C3D4-E5F6" onKapat={onKapat} />);

    const kapat = screen.getByRole("button", { name: "Kapat" });
    expect(kapat).toBeDisabled();
    // ESC de kaçış değildir: anahtar kaybolurdu.
    await user.keyboard("{Escape}");
    expect(onKapat).not.toHaveBeenCalled();

    await user.click(screen.getByRole("checkbox", { name: /güvenli bir yere kaydettim/ }));
    await user.click(kapat);
    expect(onKapat).toHaveBeenCalledTimes(1);
  });

  it("metin çıktısı tarihi gg.aa.yyyy biçiminde ve yerel günle yazar", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 18, 0, 30, 0));
    const user = userEvent.setup();
    render(
      <KurtarmaAnahtariDiyalogu
        open
        anahtar="A1B2-C3D4-E5F6"
        okulAdi="Örnek Anadolu Lisesi"
        onKapat={() => {}}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Metin dosyası olarak kaydet" }));

    expect(indirme.saveBlob).toHaveBeenCalledWith(expect.any(Blob), "kurtarma-anahtari.txt");
    const metin = await blobMetni(indirme.saveBlob.mock.calls[0][0] as Blob);
    expect(metin).toContain("KELEBEK SINAV — KURTARMA ANAHTARI");
    expect(metin).toContain("Kurum: Örnek Anadolu Lisesi");
    expect(metin).toContain("Oluşturma tarihi: 18.09.2026");
    expect(metin).toContain("A1B2-C3D4-E5F6");
  });
});
