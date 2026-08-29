// Panel (hub) — OYS SinavIslemleriHub'dan UYARLA (F3): modül kartları.
// Rapor/kitapçık ve sınav takvimi kartları kendi fazlarında (F4-F6) eklenir.

import HubFeatureCard from "../../ui/HubFeatureCard";

export default function PanelPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <header>
        <h1 className="text-headline-medium font-semibold tracking-tight text-on-surface">Panel</h1>
        <p className="mt-2 text-body-medium text-on-surface-variant">
          Ortak sınav planlama: oturum kur, dağıt, onayla; evrak ve kitapçık fazları (F4-F5) yolda.
        </p>
      </header>
      <div className="grid gap-4 sm:grid-cols-2">
        <HubFeatureCard
          to="/oturumlar"
          icon="event_seat"
          title="Sınav Oturumları"
          description="5 adımlı sihirbaz: nakil beyanı, dersler, salonlar, karışık dağıtım ve onay; yoklama takibi."
        />
        <HubFeatureCard
          to="/salonlar"
          icon="meeting_room"
          title="Salonlar"
          description="Salon şablonları ve 2B yerleşim editörü; şube dersliklerini tek tıkla üret."
        />
        <HubFeatureCard
          to="/kisiler"
          icon="group"
          title="Kişiler"
          description="Öğrenci ve öğretmen sicili; e-Okul listelerinden içe aktarma."
        />
        <HubFeatureCard
          to="/dersler"
          icon="menu_book"
          title="Ders Havuzu"
          description="MEB çizelgesinden tohumlanan ders havuzu; seviye ve alias yönetimi."
        />
      </div>
    </div>
  );
}
