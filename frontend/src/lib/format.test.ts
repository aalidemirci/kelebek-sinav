// Tur 43 — format yardımcılarının testi. CLAUDE.md §2'deki Türkçe görüntü
// kuralları (gg.aa.yyyy, 1.234,56) doğrulanır.

import { describe, expect, it } from "vitest";

import { formatDate, formatDateTime, formatNumber, formatPercent, todayIso } from "./format";

describe("formatDate", () => {
  it("ISO 8601 tarihini gg.aa.yyyy biçimine çevirir", () => {
    expect(formatDate("2026-05-28")).toBe("28.05.2026");
  });

  it("ISO datetime'ı da tarih kısmından alır", () => {
    expect(formatDate("2026-12-31T23:59:00Z")).toBe("31.12.2026");
  });

  it("null/undefined için tire döner", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate(undefined)).toBe("—");
    expect(formatDate("")).toBe("—");
  });

  it("geçersiz tarihi olduğu gibi döndürür", () => {
    expect(formatDate("not-a-date")).toBe("not-a-date");
  });
});

describe("formatNumber", () => {
  it("binlik nokta + ondalık virgül kullanır", () => {
    expect(formatNumber(1234)).toBe("1.234");
    expect(formatNumber(1234567)).toBe("1.234.567");
  });

  it("ondalıklı sayıyı virgülle gösterir", () => {
    expect(formatNumber(1234.56)).toBe("1.234,56");
  });

  it("null/undefined için tire döner", () => {
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber(undefined)).toBe("—");
  });

  it("sıfırı düz '0' olarak gösterir", () => {
    expect(formatNumber(0)).toBe("0");
  });
});

describe("formatPercent", () => {
  it("pozitif değere + işareti ekler", () => {
    expect(formatPercent(12.5)).toBe("+12,5%");
  });

  it("negatif değere işaret eklemez (zaten - var)", () => {
    expect(formatPercent(-3)).toBe("-3%");
  });

  it("sıfır için işaretsiz", () => {
    expect(formatPercent(0)).toBe("0%");
  });

  it("null için tire", () => {
    expect(formatPercent(null)).toBe("—");
  });
});

describe("formatDateTime", () => {
  it("geçersiz ISO için string'i geri verir", () => {
    expect(formatDateTime("not-a-date")).toBe("not-a-date");
  });

  it("null için tire", () => {
    expect(formatDateTime(null)).toBe("—");
  });

  // Saat dilimi testi içinde belirli string beklemek yerine içerik kontrolü;
  // CI'da TZ tutarsızlığını önler.
  it("geçerli ISO için Türkçe tarih-saat üretir", () => {
    const result = formatDateTime("2026-05-28T10:30:00Z");
    expect(result).toMatch(/28\.05\.2026/);
  });
});

describe("todayIso", () => {
  it("yyyy-mm-dd biçiminde 10 karakterlik string döner", () => {
    const t = todayIso();
    expect(t).toHaveLength(10);
    expect(t).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

// Kaynak taraması — kural değil MEKANİZMA: `new Date().toISOString()` UTC verir,
// Türkiye (UTC+3) gece 00:00-02:59 arasında bir GÜN GERİYE kayar; o saatte açılan
// formun tarih varsayılanı dünü gösterir ve resmî belgeye yanlış tarih basılır.
// Doğru yol `todayIso()` (yerel saat). Bu test yeni bir sızıntıyı derlemede değil,
// testte yakalar.
describe("tarih disiplini", () => {
  it("kaynak ağacında UTC'den tarih türeten kullanım yok", async () => {
    const { readdirSync, readFileSync } = await import("node:fs");
    const { join } = await import("node:path");

    const suclular: string[] = [];
    const tara = (dizin: string): void => {
      for (const girdi of readdirSync(dizin, { withFileTypes: true })) {
        const yol = join(dizin, girdi.name);
        if (girdi.isDirectory()) {
          tara(yol);
        } else if (/\.tsx?$/.test(girdi.name) && !girdi.name.includes(".test.")) {
          const metin = readFileSync(yol, "utf8");
          if (/toISOString\(\)\s*\.\s*(slice|split)\(/.test(metin)) suclular.push(yol);
        }
      }
    };
    tara(join(__dirname, ".."));

    expect(suclular).toEqual([]);
  });
});
