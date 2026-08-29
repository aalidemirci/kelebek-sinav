// Modül içi alt sayfalardan modül ana sayfasına tek-tık dönüş başlığı.
// Geri-ok + modül adı (link) + sayfa başlığı + opsiyonel sağ eylemler.
// M3: yalnız token, dokunma ≥ 48px, görünür focus halkası, aria-label.

import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import Icon from "./Icon";

interface ModuleHeaderProps {
  /** Modül kökü rotası (ör. "/zumre"). */
  backTo: string;
  /** Modül adı (ör. "Zümre") — geri linkinde ve erişilebilir adda kullanılır. */
  moduleLabel: string;
  /** Sayfa başlığı (ör. "Takip Matrisi"). */
  title: string;
  /** Sağda opsiyonel eylemler (yıl seçici, "Yeni …" butonu vb.). */
  actions?: ReactNode;
}

export default function ModuleHeader({ backTo, moduleLabel, title, actions }: ModuleHeaderProps) {
  return (
    <div className="ks-page-header mb-5">
      <div className="flex items-center gap-2">
        <Link
          to={backTo}
          aria-label={`${moduleLabel} ana sayfasına dön`}
          className="flex min-h-12 items-center gap-1 rounded-shape-lg px-2 text-label-large text-primary hover:bg-primary/8 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <Icon name="arrow_back" />
          {moduleLabel}
        </Link>
        <span className="text-on-surface-variant" aria-hidden="true">
          /
        </span>
        <h1 className="ks-page-title">{title}</h1>
      </div>
      {actions ? <div className="flex items-end gap-3">{actions}</div> : null}
    </div>
  );
}
