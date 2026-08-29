// M3 Dialog (CLAUDE.md §7.5 / .claude/rules/frontend-m3.md): scrim %32 siyah,
// surface-container-high, shape-xl, elevation-3, başlık headline-small. ESC + scrim
// tıklaması kapatır; açılışta ilk odak panele alınır, Tab odak TUZAĞI panel
// içinde döner (F29, Tur 247 — WCAG 2.1 klavye tuzağı deseni: Tab son öğeden
// ilkine, Shift+Tab ilkinden sonuncuya sarar). İçerik token tüketir; ham renk/px yok.

import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

/** Panel içindeki klavyeyle odaklanabilir öğeler (F29 odak tuzağı).
 *
 * Görünürlük için `hidden` attribute'una bakılır; `offsetParent` KULLANILMAZ
 * (jsdom'da hep null — test ortamı tuzağı). Dialog içeriğinde display:none
 * odaklanabilir öğe pratikte bulunmaz.
 */
function focusables(panel: HTMLElement): HTMLElement[] {
  const selector =
    'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
  return [...panel.querySelectorAll<HTMLElement>(selector)].filter((el) => !el.hidden);
}

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  /** Alt eylem çubuğu (butonlar). Sağa hizalanır. */
  actions?: ReactNode;
  /** Geniş içerik (tablo vb.) için ferah genişlik. */
  wide?: boolean;
  /** Tam-genişliğe yakın panel (haftalık ızgara gibi büyük tablolar — Tur 671). */
  full?: boolean;
}

export default function Dialog({
  open,
  onClose,
  title,
  children,
  actions,
  wide = false,
  full = false,
}: DialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const aciciRef = useRef<HTMLElement | null>(null);

  // Açılışta odağı panele al — YALNIZ open geçişinde (Tur 650). Bu efekt
  // onClose'a bağlanırsa her ebeveyn render'ında yeniden koşar ve panel.focus()
  // dialog içindeki input'tan odağı çalar (yazı yazarken karakter kaybı).
  //
  // Kapanışta odak, dialogu AÇAN öğeye geri verilir (WCAG 2.4.3; B6). Aksi
  // halde odak <body>'ye düşer ve klavye kullanıcısı sekmeye sayfanın başından
  // başlar. Açan öğe, panel odaklanmadan ÖNCE okunur.
  useEffect(() => {
    if (!open) return;
    const aktif = document.activeElement;
    aciciRef.current = aktif instanceof HTMLElement ? aktif : null;
    panelRef.current?.focus();
    return () => {
      const acici = aciciRef.current;
      aciciRef.current = null;
      // Açan öğe bu arada DOM'dan kalkmış olabilir (silinen satırın butonu);
      // o durumda odak tarayıcının varsayılanına bırakılır.
      if (acici !== null && acici.isConnected) acici.focus();
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      // F29: Tab odak tuzağı — odak dialog dışına çıkamaz, uçlarda sarar.
      if (e.key !== "Tab") return;
      const panel = panelRef.current;
      if (panel === null) return;
      const items = focusables(panel);
      if (items.length === 0) {
        e.preventDefault();
        panel.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || active === panel)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      } else if (active !== null && !panel.contains(active)) {
        // Odak bir şekilde dışarıdaysa (örn. tarayıcı çubuğundan dönüş) içeri al.
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex animate-scrim-in items-center justify-center bg-scrim/[0.32] p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={`flex max-h-[90vh] w-full animate-dialog-in flex-col overflow-hidden rounded-shape-lg border border-outline-variant bg-surface-container-lowest text-on-surface shadow-elevation-3 outline-none ${
          full ? "max-w-6xl" : wide ? "max-w-3xl" : "max-w-md"
        }`}
      >
        <div className="border-b border-outline-variant/70 px-6 py-5">
          <h2 className="text-title-large font-semibold">{title}</h2>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5 text-body-medium text-on-surface-variant scrollbar-thin">
          {children}
        </div>
        {actions && (
          <div className="flex justify-end gap-2 border-t border-outline-variant bg-surface-container-low px-6 py-4">
            {actions}
          </div>
        )}
      </div>
    </div>
  );
}
