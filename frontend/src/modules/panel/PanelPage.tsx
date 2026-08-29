// Panel (hub) — OYS SinavIslemleriHub'dan UYARLA (F3): modül kartları.

import HubFeatureCard from "../../ui/HubFeatureCard";

export default function PanelPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <header>
        <h1 className="text-headline-medium font-semibold tracking-tight text-on-surface">Panel</h1>
        <p className="mt-2 text-body-medium text-on-surface-variant">
          Ortak sınav planlama: takvimle, oturum kur, dağıt, onayla; evrakı ve kitapçıkları bas.
        </p>
      </header>
      <div className="grid gap-4 sm:grid-cols-2">
        <HubFeatureCard
          to="/takvimler"
          icon="calendar_month"
          title="Sınav Takvimi"
          description="Mevzuat pencereli dönem takvimleri; ders havuzu, yerleştirme ızgarası, süreç takibi ve resmî PDF."
        />
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
