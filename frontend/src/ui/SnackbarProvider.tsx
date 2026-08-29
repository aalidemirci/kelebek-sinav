// Snackbar altyapısı (CLAUDE.md §7.5): uygulama kökünde tek host + `useSnackbar`
// hook'u. Geçici işlem geri bildirimi için (kaydedildi / silindi / hata). Kalıcı
// durumlar (sayfa-yükleme hatası, form doğrulama) inline error kartı olarak kalır;
// Snackbar yalnız GEÇİCİ bildirimdir (M3).
//
// Davranış: aynı anda tek snackbar görünür (M3); fazlası FIFO kuyrukta bekler.
// Otomatik kapanma — varsayılan 4 sn, eylemli/hata 6 sn, `duration: null` = elle
// kapatılana dek kalıcı. `error()` assertive (ekran okuyucu role=alert) + 6 sn.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";

import Snackbar, { type SnackbarAction } from "./Snackbar";

const DEFAULT_DURATION = 4000;
const LONG_DURATION = 6000;

export interface SnackbarOptions {
  /** Sağda tek opsiyonel eylem (örn. "Geri al"). */
  action?: SnackbarAction;
  /** Görünme süresi (ms). Verilmezse eylemli/uzun=6 sn, sade=4 sn. `null` = kalıcı. */
  duration?: number | null;
  /** Ekran okuyucuya assertive duyur (hata). `error()` bunu otomatik açar. */
  assertive?: boolean;
}

interface SnackbarItem extends SnackbarOptions {
  id: number;
  message: string;
}

export interface SnackbarApi {
  /** Mesajı kuyruğa ekler. */
  show: (message: string, opts?: SnackbarOptions) => void;
  /** Olumlu geri bildirim (sade gösterim). */
  success: (message: string, opts?: SnackbarOptions) => void;
  /** Hata geri bildirimi (assertive + uzun süre). */
  error: (message: string, opts?: SnackbarOptions) => void;
  /** Görünen snackbar'ı kapatır, kuyruktaki bir sonrakine geçer. */
  dismiss: () => void;
}

const SnackbarContext = createContext<SnackbarApi | null>(null);

export function useSnackbar(): SnackbarApi {
  const ctx = useContext(SnackbarContext);
  if (!ctx) throw new Error("useSnackbar yalnız SnackbarProvider içinde kullanılabilir.");
  return ctx;
}

export function SnackbarProvider({ children }: { children: ReactNode }) {
  const [queue, setQueue] = useState<SnackbarItem[]>([]);
  const nextId = useRef(0);
  const current = queue[0] ?? null;

  const dismiss = useCallback(() => setQueue((q) => q.slice(1)), []);

  const show = useCallback((message: string, opts: SnackbarOptions = {}) => {
    const id = nextId.current++;
    setQueue((q) => [...q, { id, message, ...opts }]);
  }, []);

  const api = useMemo<SnackbarApi>(
    () => ({
      show,
      success: (message, opts) => show(message, opts),
      error: (message, opts) =>
        show(message, { assertive: true, duration: LONG_DURATION, ...opts }),
      dismiss,
    }),
    [show, dismiss],
  );

  // Görünen öğe için otomatik kapanma zamanlayıcısı (duration:null → kalıcı).
  useEffect(() => {
    if (!current) return;
    if (current.duration === null) return;
    const ms = current.duration ?? (current.action ? LONG_DURATION : DEFAULT_DURATION);
    const timer = setTimeout(dismiss, ms);
    return () => clearTimeout(timer);
  }, [current, dismiss]);

  return (
    <SnackbarContext.Provider value={api}>
      {children}
      {current && (
        <div className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex justify-center p-4 sm:justify-start">
          <Snackbar
            key={current.id}
            message={current.message}
            action={current.action}
            assertive={current.assertive}
            onDismiss={dismiss}
          />
        </div>
      )}
    </SnackbarContext.Provider>
  );
}
