// Güvenlik kapısı (F5-D5) — uygulama parolası kuruluysa ve kilit açık değilse
// içerik yerine kilit ekranını gösterir. `KurulumKapisi` ile aynı desendedir,
// iki farkla:
//
// 1. Durum bir KEZ değil, kilit her kapandığında yeniden okunur; "kilitle"
//    eylemi (Ayarlar) `guvenlikKilitlendi` olayını yayınlar, kapı dinler.
// 2. FAIL-OPEN'dır: durum ucu okunamazsa içeri alır. Gerçek kapı BACKEND'dedir
//    (`apps.okul.lock_middleware` → 423) — burada ikinci kez kilitlemek, uç
//    hatasında kullanıcıyı kilit ekranına hapsedip parolayı doğrulatamamak
//    demek olurdu.

import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { SkeletonList } from "../../ui/Skeleton";
import KilitEkrani from "./KilitEkrani";
import { guvenlikApi } from "./api";
import type { GuvenlikDurumu } from "./api";

/** Ayarlar ekranı "Şimdi kilitle" dediğinde bu olay yayınlanır. */
export const KILIT_OLAYI = "guvenlik:kilitlendi";

export function kilitOlayiYayinla(): void {
  window.dispatchEvent(new CustomEvent(KILIT_OLAYI));
}

export default function GuvenlikKapisi({ children }: { children: ReactNode }) {
  const [durum, setDurum] = useState<GuvenlikDurumu | null>(null);

  const oku = useCallback(() => {
    let iptal = false;
    guvenlikApi
      .durum()
      .then((d) => {
        if (!iptal) setDurum(d);
      })
      .catch(() => {
        // Fail-open (dosya başı notu).
        if (!iptal)
          setDurum({
            password_set: false,
            locked: false,
            transition_pending: false,
            transition: "",
            protected_fields: [],
          });
      });
    return () => {
      iptal = true;
    };
  }, []);

  useEffect(() => oku(), [oku]);

  useEffect(() => {
    const dinleyici = () => setDurum((onceki) => (onceki ? { ...onceki, locked: true } : onceki));
    window.addEventListener(KILIT_OLAYI, dinleyici);
    return () => window.removeEventListener(KILIT_OLAYI, dinleyici);
  }, []);

  if (durum === null) return <SkeletonList rows={3} className="mx-auto max-w-3xl" />;

  if (durum.locked) {
    return (
      <KilitEkrani
        yarimGecis={durum.transition_pending}
        onAcildi={() => setDurum({ ...durum, locked: false, transition_pending: false })}
      />
    );
  }

  return <>{children}</>;
}
