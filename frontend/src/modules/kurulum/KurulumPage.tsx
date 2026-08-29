// Kurulum sihirbazı — F0 yer tutucusu. F1'de DD kalıbındaki gerçek sihirbaz
// gelir: okul künyesi → ders yılı → kişiler (e-Okul içe aktarma) → ders havuzu.
// Başlık metni App.test.tsx kurulum kapısı testlerinin çapasıdır.

import EmptyState from "../../ui/EmptyState";

export default function KurulumPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <header>
        <h1 className="text-headline-medium font-semibold tracking-tight text-on-surface">
          Kurulum sihirbazı
        </h1>
        <p className="mt-2 text-body-medium text-on-surface-variant">
          Programı kullanmaya başlamadan önce okul künyesi, ders yılı ve kişi listeleri buradan
          girilecek.
        </p>
      </header>
      <EmptyState
        icon="handyman"
        title="Sihirbaz F1'de geliyor"
        description="Bu iskelet sürümde kurulum adımları henüz yok; okul künyesi, ders yılı, e-Okul içe aktarma ve MEB ders havuzu tohumu F1 fazında eklenecek."
      />
    </div>
  );
}
