// Hub/landing sayfası özellik kartı (Tur 179). Öğrenci İşleri + Süreç Takip
// hub'larındaki yinelenen Link+Card+state-layer deseni tek bileşene alındı.
// Klavye focus'unda GÖRÜNÜR M3 halkası (focus-visible:ring) burada garanti edilir
// — WCAG 2.1 AA (2.4.7 Focus Visible) + CLAUDE.md §7.5. Yalnız M3 token kullanır;
// ikon dekoratiftir (görünür başlık etiket görevi görür → aria-hidden).

import { Link } from "react-router-dom";

import Card from "./Card";
import Icon from "./Icon";

interface HubFeatureCardProps {
  to: string;
  icon: string;
  title: string;
  description: string;
}

export default function HubFeatureCard({ to, icon, title, description }: HubFeatureCardProps) {
  return (
    <Link
      to={to}
      className="group relative block overflow-hidden rounded-shape-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
    >
      <Card elevation={0} className="ks-card-hover h-full p-5">
        <span aria-hidden="true" className="state-layer" />
        <div className="relative flex items-start gap-4">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-shape-lg bg-primary-container text-primary">
            <Icon name={icon} aria-hidden="true" />
          </span>
          <div>
            <p className="text-title-medium font-semibold text-on-surface">{title}</p>
            <p className="mt-1 text-body-medium text-on-surface-variant">{description}</p>
          </div>
        </div>
      </Card>
    </Link>
  );
}
