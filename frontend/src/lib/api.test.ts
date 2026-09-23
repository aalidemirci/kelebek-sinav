// lib/api "yeniden başlat" sözleşmesi: backend restart_gate kapısındayken HANGİ
// uç çağrılırsa çağrılsın 503 `restart_required` döner; istemci ApiError fırlatır
// VE yeniden başlat olayını yayınlar (YenidenBaslatEkrani bunu dinler). Sıradan
// hatalar olayı yayınlamaz.

import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "./api";
import { KILIT_KAPISI_OLAYI } from "./kilit";
import { YENIDEN_BASLAT_OLAYI } from "./restart";

function sahteYanit(status: number, govde: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(govde),
    blob: () => Promise.resolve(new Blob()),
  };
}

describe("api — restart_required sözleşmesi", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("503 restart_required hem ApiError fırlatır hem olayı yayınlar", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        sahteYanit(503, {
          code: "restart_required",
          message: "Yedekten geri yükleme uygulandı.",
          fields: {},
        }),
      ),
    );
    const dinleyici = vi.fn();
    window.addEventListener(YENIDEN_BASLAT_OLAYI, dinleyici);
    try {
      await expect(api.get("/security/status/")).rejects.toMatchObject({
        code: "restart_required",
        status: 503,
      });
      expect(dinleyici).toHaveBeenCalledTimes(1);
    } finally {
      window.removeEventListener(YENIDEN_BASLAT_OLAYI, dinleyici);
    }
  });

  it("sıradan hata olayı yayınlamaz", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          sahteYanit(400, { code: "validation_error", message: "Hata.", fields: {} }),
        ),
    );
    const dinleyici = vi.fn();
    window.addEventListener(YENIDEN_BASLAT_OLAYI, dinleyici);
    try {
      await expect(api.get("/students/")).rejects.toBeInstanceOf(ApiError);
      expect(dinleyici).not.toHaveBeenCalled();
    } finally {
      window.removeEventListener(YENIDEN_BASLAT_OLAYI, dinleyici);
    }
  });
});

// Kilit kapısı: oturum ortasında 423 `locked` ya da `guvenlik_dosyasi_kayip`
// gelirse güvenlik kapısı durumu yeniden okusun diye olay yayınlanır.
describe("api — kilit kapısı (423) sözleşmesi", () => {
  afterEach(() => vi.unstubAllGlobals());

  it.each(["locked", "guvenlik_dosyasi_kayip"])("423 %s olayı yayınlar", async (kod) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(sahteYanit(423, { code: kod, message: "Kilitli.", fields: {} })),
    );
    const dinleyici = vi.fn();
    window.addEventListener(KILIT_KAPISI_OLAYI, dinleyici);
    try {
      await expect(api.get("/students/")).rejects.toMatchObject({ code: kod, status: 423 });
      await expect(api.getBlob("/templates/students/")).rejects.toMatchObject({ status: 423 });
      expect(dinleyici).toHaveBeenCalledTimes(2);
    } finally {
      window.removeEventListener(KILIT_KAPISI_OLAYI, dinleyici);
    }
  });

  it("başka 4xx kodu kilit olayı yayınlamaz", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          sahteYanit(400, { code: "validation_error", message: "Hata.", fields: {} }),
        ),
    );
    const dinleyici = vi.fn();
    window.addEventListener(KILIT_KAPISI_OLAYI, dinleyici);
    try {
      await expect(api.get("/students/")).rejects.toBeInstanceOf(ApiError);
      expect(dinleyici).not.toHaveBeenCalled();
    } finally {
      window.removeEventListener(KILIT_KAPISI_OLAYI, dinleyici);
    }
  });
});
