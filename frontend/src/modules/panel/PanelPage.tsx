// Panel (hub) — F0 iskeleti. F3'ten itibaren OYS sinav-islemleri hub'ının
// uyarlaması gelir: oturum listesi, yaklaşan sınavlar, hızlı eylemler.

import EmptyState from "../../ui/EmptyState";

export default function PanelPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <header>
        <h1 className="text-headline-medium font-semibold tracking-tight text-on-surface">Panel</h1>
        <p className="mt-2 text-body-medium text-on-surface-variant">
          Sınav planlama modülleri fazlar hâlinde geliyor (tasarım belgesi §12).
        </p>
      </header>
      <EmptyState
        icon="grid_on"
        title="Henüz modül yok"
        description="F1: kurulum + kişiler + ders havuzu · F2: salonlar · F3: sınav oturumları · F4-F5: evrak ve kitapçık · F6: sınav takvimi."
      />
    </div>
  );
}
