// Türkçe görüntü biçimlendirme (CLAUDE.md §2): tarih gg.aa.yyyy, sayı binlik nokta /
// ondalık virgül. Depolama/giriş ISO 8601 (yyyy-aa-gg) kalır — yalnızca GÖRÜNTÜ.

/** ISO tarihi (yyyy-mm-dd) → gg.aa.yyyy. Geçersizse olduğu gibi döner. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${m[3]}.${m[2]}.${m[1]}`;
}

const nf = new Intl.NumberFormat("tr-TR");

/** Tam sayı/ondalık → Türkçe biçim (1.234,56). null → "—". */
export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return nf.format(value);
}

/** Yüzde değişim → "+12,5%" / "-3%". null → "—". */
export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${nf.format(value)}%`;
}

const dtf = new Intl.DateTimeFormat("tr-TR", {
  dateStyle: "short",
  timeStyle: "short",
  timeZone: "Europe/Istanbul",
});

/** ISO tarih-saat → gg.aa.yyyy SS:dd (Europe/Istanbul). Geçersizse olduğu gibi döner. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return dtf.format(d);
}

/** Bugünü ISO yyyy-mm-dd olarak (yerel saat) — tarih input varsayılanı için. */
export function todayIso(): string {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}
