// saveBlob DOM akışı testi (Tur 535): createObjectURL → <a download> → revoke.

import { afterEach, describe, expect, it, vi } from "vitest";

import { dosyaAdi, saveBlob } from "./download";

describe("dosyaAdi", () => {
  it("belge + oturum adı + tarihten okunur dosya adı kurar (Türkçe harf korunur)", () => {
    expect(dosyaAdi(["Salon Sınav Evrakı", "1. Ortak Sınav", "16.11.2026"], "pdf")).toBe(
      "Salon-Sınav-Evrakı_1-Ortak-Sınav_16.11.2026.pdf",
    );
  });

  it("dosya sisteminin yasakladığı karakterleri atar, boş parçayı düşürür", () => {
    expect(dosyaAdi(['9/A: "Deneme" <1>', "", null, "Takvim?"], ".zip")).toBe(
      "9A-Deneme-1_Takvim.zip",
    );
    expect(dosyaAdi([], "pdf")).toBe("belge.pdf");
    // Ters bölü Windows'ta yol ayracıdır; salon adında geçerse dosya adını böler.
    expect(dosyaAdi(["Salon Sınav Evrakı", "B\\Blok 101"], "pdf")).toBe(
      "Salon-Sınav-Evrakı_BBlok-101.pdf",
    );
  });
});

describe("saveBlob", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("blob için geçici URL açar, bağlantıyı tıklar ve URL'yi gecikmeli bırakır", () => {
    vi.useFakeTimers();
    const createObjectURL = vi.fn(() => "blob:test-url");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL,
      revokeObjectURL,
    });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    saveBlob(new Blob(["test"]), "dosya.xlsx");

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(click).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).not.toHaveBeenCalled();
    // Bağlantı DOM'da bırakılmadı.
    expect(document.querySelector("a[download]")).toBeNull();

    vi.advanceTimersByTime(1_000);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:test-url");
  });
});
