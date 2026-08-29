// Kontrollü (useState tabanlı) formlar için alan-bazlı doğrulama + hata gösterimi
// (Tur 191, Talep 1f). OYS form mimarisi standardı: form değerleri bileşenin kendi
// state'inde kalır; bu hook yalnız `alan → hata mesajı` haritasını yönetir ve onu
// iki kaynaktan doldurur:
//   1) İSTEMCİ: `validate(zodSchema, values)` — boş/geçersiz zorunlu alanlar.
//   2) SUNUCU: `applyApiError(err)` — backend `{fields}` hatası (CLAUDE.md §7).
// Bileşen her alana `error={errors.<alan>}` geçer → TextField/Select/Autocomplete
// kırmızı çerçeve + hata metni gösterir. RHF zorunluluğu yoktur (mevcut kontrollü
// bileşen ekosistemiyle düşük-sürtünme; bkz. Tur 191 mimari kararı).

import { useCallback, useState } from "react";
import type { ZodType } from "zod";

import { parseApiFieldErrors } from "../lib/formErrors";

export interface UseFormErrors<K extends string = string> {
  /** Geçerli alan-bazlı hatalar (`alan → mesaj`). Boş alan = hata yok. */
  errors: Partial<Record<K, string>>;
  /** Tek bir alanın hatasını elle ayarla (özel doğrulamalar için). */
  setFieldError: (field: K, message: string) => void;
  /** Tüm hataları temizle (yeni submit denemesinin başında). */
  clearErrors: () => void;
  /**
   * `values`'ı zod şemasıyla doğrular. Geçerliyse hataları temizler ve `true` döner;
   * geçersizse her alanın İLK hata mesajını `errors`'a yazar ve `false` döner.
   */
  validate: (schema: ZodType, values: unknown) => boolean;
  /**
   * Backend `{fields}` hatasını alan-bazlı `errors`'a yansıtır. İlk hatalı alanın
   * adını döner (odak/uyarı için) — `ApiError` değilse `null`.
   */
  applyApiError: (err: unknown) => K | null;
}

export function useFormErrors<K extends string = string>(): UseFormErrors<K> {
  const [errors, setErrors] = useState<Partial<Record<K, string>>>({});

  const clearErrors = useCallback(() => setErrors({}), []);

  const setFieldError = useCallback((field: K, message: string) => {
    setErrors((prev) => ({ ...prev, [field]: message }));
  }, []);

  const validate = useCallback((schema: ZodType, values: unknown): boolean => {
    const result = schema.safeParse(values);
    if (result.success) {
      setErrors({});
      return true;
    }
    const next: Partial<Record<K, string>> = {};
    for (const issue of result.error.issues) {
      const key = issue.path[0];
      if (typeof key === "string" && next[key as K] === undefined) {
        next[key as K] = issue.message;
      }
    }
    setErrors(next);
    return false;
  }, []);

  const applyApiError = useCallback((err: unknown): K | null => {
    const fields = parseApiFieldErrors(err);
    if (!fields) return null;
    let first: K | null = null;
    setErrors((prev) => ({ ...prev, ...(fields as Partial<Record<K, string>>) }));
    for (const key of Object.keys(fields)) {
      first = key as K;
      break;
    }
    return first;
  }, []);

  return { errors, setFieldError, clearErrors, validate, applyApiError };
}
