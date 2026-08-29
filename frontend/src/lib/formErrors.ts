// Backend hata sözleşmesini (CLAUDE.md §7: `{code, message, fields}`) alan-bazlı
// hata haritasına çeviren paylaşılan yardımcı. Kontrollü-form `useFormErrors` ve
// RHF resolver'ları bunu kullanır (tek doğruluk kaynağı, DRY).

import { ApiError } from "./api";

/**
 * Backend `{fields}` hatasından `alan → mesaj` haritası çıkarır. `fields` değeri
 * dizi (DRF çoğul mesaj) ya da tek string olabilir; çoğul mesajlar boşlukla birleşir.
 * `err` bir `ApiError` değilse `null` döner (çağıran genel mesaja düşer).
 */
export function parseApiFieldErrors(err: unknown): Record<string, string> | null {
  if (!(err instanceof ApiError)) return null;
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(err.fields ?? {})) {
    const messages = Array.isArray(value) ? value : [value];
    const msg = messages
      .map((m) => String(m))
      .filter(Boolean)
      .join(" ");
    if (msg) out[key] = msg;
  }
  return out;
}
