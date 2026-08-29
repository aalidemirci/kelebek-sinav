// M3 boş-durum bileşeni (Faz 1a): merkezî ikon + başlık + destek metni + opsiyonel
// birincil eylem. Ölü-alanlı tek-satır boş kartların (frontend-m3.md C2) yerine geçer;
// `compact` varyantı satır-içi "kayıt yok" metinleri içindir. Yalnız M3 token'ları.

import type { ReactNode } from "react";

import Card from "./Card";
import Icon from "./Icon";

interface EmptyStateProps {
  /** Material Symbols adı — bağlamı çağrıştıran ikon (varsayılan "inbox"). */
  icon?: string;
  title: string;
  description?: string;
  /** Opsiyonel birincil eylem (ör. "Ekle" Button) — M3: her boş ekranın çıkışı olur. */
  action?: ReactNode;
  /** Satır-içi kompakt varyant (kart yerine tek satır). */
  compact?: boolean;
}

export default function EmptyState({
  icon = "inbox",
  title,
  description,
  action,
  compact = false,
}: EmptyStateProps) {
  if (compact) {
    return (
      <div className="flex items-center gap-2 py-3 text-body-small text-on-surface-variant">
        <Icon name={icon} size="sm" aria-hidden="true" />
        <span>{title}</span>
      </div>
    );
  }
  return (
    <Card
      elevation={0}
      className="flex flex-col items-center gap-3 border-dashed px-6 py-12 text-center"
    >
      <span className="flex h-14 w-14 items-center justify-center rounded-shape-lg bg-primary-container text-primary">
        <Icon name={icon} size="2xl" aria-hidden="true" />
      </span>
      <h3 className="text-title-medium text-on-surface">{title}</h3>
      {description && (
        <p className="max-w-md text-body-medium text-on-surface-variant">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </Card>
  );
}
