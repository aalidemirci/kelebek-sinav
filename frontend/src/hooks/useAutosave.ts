// Sunucu-taraflı oto-kayıt hook'u (Tur 147) — KVKK: localStorage YOK.
//
// useFormDraft'tan FARKI: taslak istemcide (localStorage) DEĞİL,
// değişen alanlar doğrudan SUNUCUYA yazılır (AuditLog'a düşer). EK-1 anlatısı
// (sağlık/aile ekonomik durumu/psikososyal özet) ÖZEL NİTELİKLİ KVKK verisidir
// (CLAUDE.md §5 — "TCKN gibi hassas alanlar hiç yazılmaz"); bu yüzden bu form
// için istemci-tarafı taslak yasak, sunucu-tarafı debounce'lu kayıt kullanılır.
//
// Davranış:
//   - notifyChange(changed) değişen alanları biriktirir (pending) ve debounce başlatır.
//   - Debounce dolunca pending alanlar tek POST ile yazılır; istek sürerken gelen
//     yeni değişiklikler korunur (uçuş sırasında değişmeyen alanlar temizlenir,
//     değişenler bir sonraki turda tekrar yazılır).
//   - Hata → status "error", pending KORUNUR; retry()/sonraki değişiklik tekrar dener.
//   - flush() bekleyeni hemen yazar (panel kapanışı); unmount'ta son pending
//     en iyi çabayla (fire-and-forget) yazılır.
//
// Kullanım:
//   const autosave = useAutosave<DecisionNarrativeBody>({
//     save: (changed) => oturumApi.updateNotes(sessionId, changed),
//   });
//   onChange → autosave.notifyChange({ health_status: value });
//   manuel tam kayıt sonrası → autosave.markSaved();
//   kapanışta → await autosave.flush();

import { useCallback, useEffect, useRef, useState } from "react";

export type AutosaveStatus = "idle" | "pending" | "saving" | "saved" | "error";

interface UseAutosaveOptions<T> {
  /** Değişen alanları sunucuya yazan fn. Reddederse status "error" olur. */
  save: (changed: Partial<T>) => Promise<unknown>;
  /** Son değişiklikten sonra yazıma kadar bekleme (ms). Varsayılan 1200. */
  delayMs?: number;
  /** false ise notifyChange yok sayılır (örn. yetki yok). Varsayılan true. */
  enabled?: boolean;
}

export interface UseAutosaveReturn<T> {
  status: AutosaveStatus;
  /** Son başarılı kayıt zamanı (gösterge için). */
  lastSavedAt: Date | null;
  /** Değişen alan(lar)ı biriktir + debounce başlat. */
  notifyChange: (changed: Partial<T>) => void;
  /** Bekleyeni hemen yaz; pending boşaldıysa (kayıt başarılı) true döner. */
  flush: () => Promise<boolean>;
  /** Hata sonrası bekleyeni yeniden yazmayı dener. */
  retry: () => void;
  /** Dışarıda yapılan tam kayıttan sonra: pending'i temizle, "saved" göster. */
  markSaved: () => void;
}

export function useAutosave<T>(opts: UseAutosaveOptions<T>): UseAutosaveReturn<T> {
  const { delayMs = 1200, enabled = true } = opts;

  const [status, setStatus] = useState<AutosaveStatus>("idle");
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);

  // Latest-ref desenleri: save/enabled her render'da değişebilir; notifyChange/flush
  // referans olarak stabil kalsın diye ref üzerinden okunur.
  const saveRef = useRef(opts.save);
  saveRef.current = opts.save;
  const enabledRef = useRef(enabled);
  enabledRef.current = enabled;

  const pendingRef = useRef<Record<string, unknown>>({});
  const timerRef = useRef<number | undefined>(undefined);
  const savingRef = useRef(false);
  const inflightRef = useRef<Promise<void> | null>(null);
  const mountedRef = useRef(true);

  // Bekleyen alanları boşalana (ya da hata) kadar drenajla yazar. Tek seferde bir
  // çalışma garantisi (savingRef); uçuş sırasında gelen değişiklikler döngüde alınır.
  const runSave = useCallback((): Promise<void> => {
    if (savingRef.current) return inflightRef.current ?? Promise.resolve();
    if (Object.keys(pendingRef.current).length === 0) return Promise.resolve();
    savingRef.current = true;
    const p = (async () => {
      let didSave = false;
      try {
        while (Object.keys(pendingRef.current).length > 0) {
          const payload = { ...pendingRef.current };
          const keys = Object.keys(payload);
          if (mountedRef.current) setStatus("saving");
          await saveRef.current(payload as Partial<T>);
          didSave = true;
          // Uçuş sırasında değişmeyen alanları pending'den düş; değişenler kalır.
          for (const k of keys) {
            if (pendingRef.current[k] === payload[k]) delete pendingRef.current[k];
          }
          if (mountedRef.current) setLastSavedAt(new Date());
        }
        if (didSave && mountedRef.current) setStatus("saved");
      } catch {
        if (mountedRef.current) setStatus("error"); // pending KORUNUR → retry
      } finally {
        savingRef.current = false;
        inflightRef.current = null;
      }
    })();
    inflightRef.current = p;
    return p;
  }, []);

  const notifyChange = useCallback(
    (changed: Partial<T>) => {
      if (!enabledRef.current) return;
      Object.assign(pendingRef.current, changed);
      if (mountedRef.current && !savingRef.current) setStatus("pending");
      window.clearTimeout(timerRef.current);
      timerRef.current = window.setTimeout(() => void runSave(), delayMs);
    },
    [delayMs, runSave],
  );

  const flush = useCallback(async (): Promise<boolean> => {
    window.clearTimeout(timerRef.current);
    if (savingRef.current && inflightRef.current) await inflightRef.current;
    await runSave();
    return Object.keys(pendingRef.current).length === 0;
  }, [runSave]);

  const retry = useCallback(() => void runSave(), [runSave]);

  const markSaved = useCallback(() => {
    window.clearTimeout(timerRef.current);
    pendingRef.current = {};
    if (mountedRef.current) {
      setLastSavedAt(new Date());
      setStatus("saved");
    }
  }, []);

  // Unmount: bekleyen son değişiklikleri en iyi çabayla yaz (state güncellemesi yok).
  useEffect(
    () => () => {
      mountedRef.current = false;
      window.clearTimeout(timerRef.current);
      const pend = pendingRef.current;
      if (!savingRef.current && Object.keys(pend).length > 0) {
        void saveRef.current({ ...pend } as Partial<T>);
      }
    },
    [],
  );

  return { status, lastSavedAt, notifyChange, flush, retry, markSaved };
}
