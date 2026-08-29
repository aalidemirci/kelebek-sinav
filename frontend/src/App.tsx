// Kelebek Sınav — kök route tanımı (F0 iskeleti).
// Route ağacı fazlarla büyür (tasarım §12): F1 kurulum/kişiler/ders havuzu,
// F2 salonlar, F3 oturumlar, F6 takvimler. DD kalıbındaki gibi rotalar
// `KurulumKapisi` içine alınır: kurulum tamamlanmadan sihirbaz dışına çıkılamaz.
// GuvenlikKapisi (uygulama parolası kilidi) şifreleme katmanıyla F1'de gelir —
// DD'deki yerleşimiyle KurulumKapisi'nın DIŞINA sarılacak.

import { Route, Routes } from "react-router-dom";

import AppShell from "./AppShell";
import KurulumKapisi from "./KurulumKapisi";
import HakkindaPage from "./modules/hakkinda/HakkindaPage";
import KurulumPage from "./modules/kurulum/KurulumPage";
import PanelPage from "./modules/panel/PanelPage";

export default function App() {
  return (
    <AppShell>
      <KurulumKapisi>
        <Routes>
          <Route path="/" element={<PanelPage />} />
          {/* Kurulum sihirbazı — kapının izin verdiği tek rota (bkz. KurulumKapisi). */}
          <Route path="/kurulum" element={<KurulumPage />} />
          <Route path="/hakkinda" element={<HakkindaPage />} />
        </Routes>
      </KurulumKapisi>
    </AppShell>
  );
}
