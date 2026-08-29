// Onay (confirm) altyapısı (CLAUDE.md §7.5): uygulama kökünde tek M3 Dialog host'u
// + `useConfirm` hook'u. Native `window.confirm()` yerine erişilebilir ui/Dialog
// (scrim + klavye tuzağı + ESC + odak yönetimi). KVKK: onay metni (dosya/kişi adı)
// tarayıcı-native dialog yerine uygulama içinde, kontrollü bileşende gösterilir.
//
// Kullanım — native confirm'in eşdeğeri:
//   const confirm = useConfirm();
//   if (!(await confirm({ message: "'X' silinsin mi?", confirmLabel: "Sil" }))) return;
// Onayla → Promise true; Vazgeç / ESC / scrim → false.

import { createContext, useCallback, useContext, useRef, useState } from "react";
import type { ReactNode } from "react";

import Button from "./Button";
import Dialog from "./Dialog";

export interface ConfirmOptions {
  /** Gövde metni (zorunlu). */
  message: string;
  /** Başlık (varsayılan "Onay"). */
  title?: string;
  /** Onay butonu etiketi — eylemi tarif etmeli, örn. "Sil"/"Çıkar" (varsayılan "Onayla"). */
  confirmLabel?: string;
  /** İptal butonu etiketi (varsayılan "Vazgeç"). */
  cancelLabel?: string;
}

type ConfirmFn = (options: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<ConfirmFn | null>(null);

export function useConfirm(): ConfirmFn {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm yalnız ConfirmProvider içinde kullanılabilir.");
  return ctx;
}

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [options, setOptions] = useState<ConfirmOptions | null>(null);
  // Bekleyen Promise'in resolve'u — StrictMode state-updater'ı iki kez çağırdığı
  // için resolve'u updater İÇİNDE değil, olay işleyicide ref üzerinden çağırırız
  // (aksi halde Promise iki kez resolve olur).
  const resolveRef = useRef<((ok: boolean) => void) | null>(null);

  const confirm = useCallback<ConfirmFn>((opts) => {
    return new Promise<boolean>((resolve) => {
      // Bekleyen önceki onay varsa iptal say (üst üste çağrıya karşı güvenlik).
      resolveRef.current?.(false);
      resolveRef.current = resolve;
      setOptions(opts);
    });
  }, []);

  const close = useCallback((ok: boolean) => {
    setOptions(null);
    const resolve = resolveRef.current;
    resolveRef.current = null;
    resolve?.(ok);
  }, []);

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <Dialog
        open={options !== null}
        onClose={() => close(false)}
        title={options?.title ?? "Onay"}
        actions={
          <>
            <Button variant="text" onClick={() => close(false)}>
              {options?.cancelLabel ?? "Vazgeç"}
            </Button>
            <Button variant="filled" onClick={() => close(true)}>
              {options?.confirmLabel ?? "Onayla"}
            </Button>
          </>
        }
      >
        {options?.message}
      </Dialog>
    </ConfirmContext.Provider>
  );
}
