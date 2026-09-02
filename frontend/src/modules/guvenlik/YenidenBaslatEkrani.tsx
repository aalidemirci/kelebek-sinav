// Tam ekran "programı kapatıp yeniden açın" yönlendirmesi — backend
// `restart_gate` kapısının arayüz ayağı. Geri yükleme uygulandıktan sonra
// süreç içi durum (bellekteki anahtar, bekleyen şema göçleri) diskteki veriyi
// artık tarif etmez; backend tüm API'yi 503 `restart_required` ile keser ve
// `lib/api.ts` olayı yayınlar. Ekran BİLEREK kapatılamaz: kapatma düğmesi
// koymak kullanıcıyı bayat oturumda çalışmaya davet ederdi — tek çıkış
// pencereyi kapatıp programı yeniden açmaktır.

import { useEffect, useState } from "react";

import { YENIDEN_BASLAT_OLAYI } from "../../lib/restart";
import Icon from "../../ui/Icon";

export default function YenidenBaslatEkrani() {
  const [aktif, setAktif] = useState(false);

  useEffect(() => {
    const dinleyici = () => setAktif(true);
    window.addEventListener(YENIDEN_BASLAT_OLAYI, dinleyici);
    return () => window.removeEventListener(YENIDEN_BASLAT_OLAYI, dinleyici);
  }, []);

  if (!aktif) return null;

  return (
    <div
      // z-[60]: ui/Dialog z-50 kullanır; bu ekran her diyaloğun üstünde kalmalı.
      className="fixed inset-0 z-[60] flex items-center justify-center bg-scrim/[0.6] p-4"
      role="alertdialog"
      aria-modal="true"
      aria-label="Programı yeniden başlatın"
    >
      <div className="w-full max-w-lg rounded-shape-lg border border-outline-variant bg-surface-container-lowest p-8 text-center shadow-elevation-3">
        <Icon name="restart_alt" size="5xl" className="text-primary" />
        <h2 className="mt-3 text-headline-small text-on-surface">Programı kapatıp yeniden açın</h2>
        <p className="mt-3 text-body-medium text-on-surface-variant">
          Yedekten geri yükleme uygulandı. Geri yüklenen kayıtlarla çalışmaya devam edebilmek için
          programın yeniden başlatılması gerekir: pencereyi kapatın ve programı yeniden açın.
        </p>
        <p className="mt-3 text-body-small text-on-surface-variant">
          Önceki veritabanı silinmedi; veri klasöründe{" "}
          <span className="font-mono">db-onceki-…</span> adıyla saklanıyor.
        </p>
      </div>
    </div>
  );
}
