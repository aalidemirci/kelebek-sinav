// M3 Snackbar (CLAUDE.md §7.5 / .claude/rules/frontend-m3.md): geçici bildirim;
// inverse-surface zemin + inverse-on-surface metin, shape-xs köşe, elevation-3,
// tek satır body-medium + opsiyonel eylem (inverse-primary etiket) + kapat ikonu.
// Erişilebilirlik: varsayılan role=status (polite); hata için role=alert (assertive).
// Eylem/kapat butonları 48px dokunma hedefi + görünür focus halkası. Token-only.
//
// Bu bileşen YALNIZ sunumdur — kuyruk/otomatik-kapanma/`useSnackbar` mantığı
// SnackbarProvider'dadır.

import { useEffect, useState } from "react";

import Icon from "./Icon";

export interface SnackbarAction {
  label: string;
  onClick: () => void;
}

interface SnackbarProps {
  message: string;
  /** Sağda tek opsiyonel eylem (örn. "Geri al"). */
  action?: SnackbarAction;
  /** Verilirse kapat (×) ikonu gösterilir. */
  onDismiss?: () => void;
  /** Hata bildirimi: ekran okuyucuya assertive duyurulur (role=alert). */
  assertive?: boolean;
}

export default function Snackbar({ message, action, onDismiss, assertive = false }: SnackbarProps) {
  // Görünüm geçişi: monte olunca yukarı-kayarak belirir. prefers-reduced-motion
  // index.css'te global olarak süreyi sıfırlar → hareket hassas kullanıcıda anında.
  const [shown, setShown] = useState(false);
  useEffect(() => setShown(true), []);

  return (
    <div
      role={assertive ? "alert" : "status"}
      className={`pointer-events-auto flex min-h-12 w-full max-w-md items-center gap-1 rounded-shape-xs bg-inverse-surface pl-4 text-inverse-on-surface shadow-elevation-3 transition duration-medium-2 ease-emphasized-decelerate ${
        action || onDismiss ? "pr-1" : "pr-4"
      } ${shown ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0"}`}
    >
      <span className="flex-1 py-3 text-body-medium">{message}</span>

      {action && (
        <button
          type="button"
          onClick={action.onClick}
          className="group relative inline-flex min-h-12 items-center justify-center overflow-hidden rounded-shape-xs px-3 text-label-large text-inverse-primary transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inverse-primary"
        >
          <span aria-hidden="true" className="state-layer" />
          <span className="relative z-10">{action.label}</span>
        </button>
      )}

      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Kapat"
          className="group relative inline-flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-full transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inverse-primary"
        >
          <span aria-hidden="true" className="state-layer" />
          <Icon name="close" size="lg" className="relative z-10" />
        </button>
      )}
    </div>
  );
}
