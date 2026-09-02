// lib/api "yeniden başlat" sözleşmesi: backend restart_gate kapısındayken HANGİ
// uç çağrılırsa çağrılsın 503 `restart_required` döner; istemci ApiError fırlatır
// VE yeniden başlat olayını yayınlar (YenidenBaslatEkrani bunu dinler). Sıradan
// hatalar olayı yayınlamaz.

import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "./api";
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
