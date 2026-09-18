// Genel Bakış (hub) — OYS SinavIslemleriHub'dan UYARLA (F3): modül kartları.
// Sayfanın TEK adı "Genel Bakış"tır (gezinme + üst çubuk + h1 — docs/sozluk.md
// §4); kart başlıkları gittikleri sayfanın h1'iyle aynıdır.

import HubFeatureCard from "../../ui/HubFeatureCard";

export default function PanelPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <header>
        <h1 className="text-headline-medium font-semibold tracking-tight text-on-surface">
          Genel Bakış
        </h1>
        <p className="mt-2 text-body-medium text-on-surface-variant">
          Ortak sınav planlama: takvimi kur, oturum aç, dağıt, onayla; evrakı ve kitapçıkları bas.
        </p>
      </header>
      <div className="grid gap-4 sm:grid-cols-2">
        <HubFeatureCard
          to="/takvimler"
          icon="calendar_month"
          title="Sınav Takvimleri"
          description="Mevzuat pencereli dönem takvimleri; ders havuzu, yerleştirme çizelgesi, süreç takibi ve resmî PDF."
        />
        <HubFeatureCard
          to="/oturumlar"
          icon="event_seat"
          title="Sınav Oturumları"
          description="Adım adım sihirbaz: dersler, salonlar, karışık dağıtım ve onay; evrak, kitapçık ve yoklama takibi."
        />
        <HubFeatureCard
          to="/salonlar"
          icon="meeting_room"
          title="Sınav Salonları"
          description="Salon planları ve oturma düzeni editörü; şube dersliklerini tek tıkla oluştur."
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
          description="MEB haftalık ders çizelgesinden türetilen ders havuzu; sınıf düzeyi ve takma ad yönetimi."
        />
      </div>
    </div>
  );
}
