// Kelebek Sınav — kök route tanımı. Route ağacı fazlarla büyür (tasarım §12):
// F1 kurulum/kişiler/ders havuzu/ayarlar + güvenlik kapısı; F2 salonlar; F3
// oturumlar; F6 takvimler. DD kalıbı: kilit ekranı (GuvenlikKapisi) kurulum
// kapısından ÖNCE — parola kuruluysa hiçbir veri ekranı (sihirbaz dahil)
// açılmadan kilit çözülmelidir.

import { Route, Routes } from "react-router-dom";

import AppShell from "./AppShell";
import KurulumKapisi from "./KurulumKapisi";
import AyarlarPage from "./modules/ayarlar/AyarlarPage";
import DersHavuzuPage from "./modules/dersler/DersHavuzuPage";
import GuvenlikKapisi from "./modules/guvenlik/GuvenlikKapisi";
import HakkindaPage from "./modules/hakkinda/HakkindaPage";
import KisilerPage from "./modules/kisiler/KisilerPage";
import KurulumPage from "./modules/kurulum/KurulumPage";
import OturumDetayPage from "./modules/oturumlar/OturumDetayPage";
import OturumlarPage from "./modules/oturumlar/OturumlarPage";
import PanelPage from "./modules/panel/PanelPage";
import SalonlarPage from "./modules/salonlar/SalonlarPage";

export default function App() {
  return (
    <AppShell>
      <GuvenlikKapisi>
        <KurulumKapisi>
          <Routes>
            <Route path="/" element={<PanelPage />} />
            {/* Kurulum sihirbazı — kapının izin verdiği tek rota (bkz. KurulumKapisi). */}
            <Route path="/kurulum" element={<KurulumPage />} />
            {/* Öğrenci + öğretmen sicili ve e-Okul içe aktarma. */}
            <Route path="/kisiler" element={<KisilerPage />} />
            {/* MEB çizelgesinden tohumlanan ders havuzu (K5/U4). */}
            <Route path="/dersler" element={<DersHavuzuPage />} />
            {/* Salon şablonları + 2D yerleşim editörü (F2). */}
            <Route path="/salonlar" element={<SalonlarPage />} />
            {/* Sınav oturumları: sihirbaz + dağıtım + yoklama (F3). */}
            <Route path="/oturumlar" element={<OturumlarPage />} />
            <Route path="/oturumlar/:id" element={<OturumDetayPage />} />
            {/* Ders yılı, şubeler, okul künyesi, güvenlik. */}
            <Route path="/ayarlar" element={<AyarlarPage />} />
            <Route path="/hakkinda" element={<HakkindaPage />} />
          </Routes>
        </KurulumKapisi>
      </GuvenlikKapisi>
    </AppShell>
  );
}
