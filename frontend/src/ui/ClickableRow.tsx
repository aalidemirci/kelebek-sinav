// Tıklanabilir tablo satırı — M3 erişilebilirlik standardı (C-row1, Tur 400).
// Tek doğruluk kaynağı: role="button" + tabIndex + Enter/Space + görünür focus
// halkası + h-12 (48px dokunma hedefi — tablo düzeninde height, min-height gibi
// davranır: içerik büyürse satır uzar) + ROW_HOVER state layer (%8 on-surface).
// Sütun sınırı/zebra gibi tabloya özgü sınıflar `className` ile eklenir.

import type { KeyboardEvent, ReactNode } from "react";

import { ROW_HOVER } from "./listStyles";

export default function ClickableRow({
  onActivate,
  ariaLabel,
  className = "",
  children,
}: {
  /** Tıklama ve Enter/Space aynı eylemi tetikler. */
  onActivate: () => void;
  /** Ekran okuyucu için satırın eylem etiketi (örn. "X kaydını aç"). */
  ariaLabel: string;
  className?: string;
  children: ReactNode;
}) {
  const onKeyDown = (e: KeyboardEvent<HTMLTableRowElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onActivate();
    }
  };
  return (
    <tr
      role="button"
      tabIndex={0}
      aria-label={ariaLabel}
      onClick={onActivate}
      onKeyDown={onKeyDown}
      className={`h-[var(--ks-row-height)] cursor-pointer ${ROW_HOVER} focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary ${className}`}
    >
      {children}
    </tr>
  );
}
