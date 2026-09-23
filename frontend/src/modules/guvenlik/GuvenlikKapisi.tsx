// Güvenlik kapısı (F5-D5) — uygulama parolası kuruluysa ve kilit açık değilse
// içerik yerine kilit ekranını; güvenlik dosyası kayıpsa (guvenlik.json silinmiş,
// yeniden adlandırılmış ya da içi bozuk) ayrı bir "güvenlik dosyası kayıp"
// ekranını gösterir. `KurulumKapisi` ile aynı desendedir, üç farkla:
//
// 1. Durum bir KEZ değil, kilit her kapandığında yeniden okunur; "kilitle"
//    eylemi (Ayarlar) `guvenlikKilitlendi` olayını yayınlar, kapı dinler. Oturum
//    ortasında bir istek 423 alırsa (başka yoldan kilit ya da güvenlik dosyası
//    kaybı) `lib/api.ts` `lib/kilit.ts` olayını yayınlar; kapı durumu sunucudan
//    yeniden okur.
// 2. Parola isteğe bağlıdır: kurulu değilse kapı içeriği gösterir. Ama "kurulu
//    değil" kararını BACKEND verir (dosya yok VE veritabanında anahtar izi yok);
//    dosyanın kaybolması programı parolasız kipe döndürmez.
// 3. FAIL-OPEN'dır: durum ucu okunamazsa içeri alır. Gerçek kapı BACKEND'dedir
//    (`apps.okul.lock_middleware` → 423 `locked` / `guvenlik_dosyasi_kayip`) —
//    burada ikinci kez kilitlemek, uç hatasında kullanıcıyı kilit ekranına
//    hapsedip parolayı doğrulatamamak demek olurdu.

import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { KILIT_KAPISI_OLAYI } from "../../lib/kilit";
import { SkeletonList } from "../../ui/Skeleton";
import GuvenlikDosyasiKayip from "./GuvenlikDosyasiKayip";
import KilitEkrani from "./KilitEkrani";
import { guvenlikApi } from "./api";
import type { GuvenlikDurumu } from "./api";

/** Ayarlar ekranı "Şimdi kilitle" dediğinde bu olay yayınlanır. */
export const KILIT_OLAYI = "guvenlik:kilitlendi";

export function kilitOlayiYayinla(): void {
  window.dispatchEvent(new CustomEvent(KILIT_OLAYI));
}

/** Durum ucu okunamadığında kullanılan açık durum (fail-open — dosya başı notu). */
const OKUNAMADI: GuvenlikDurumu = {
  password_set: false,
  locked: false,
  security_file_missing: false,
  reset_available: false,
  transition_pending: false,
  transition: "",
  protected_fields: [],
};

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
        if (!iptal) setDurum(OKUNAMADI);
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

  // 423: hangi kilidin kapandığını (olağan kilit ya da kayıp dosya) sunucu söyler.
  useEffect(() => {
    const dinleyici = () => void oku();
    window.addEventListener(KILIT_KAPISI_OLAYI, dinleyici);
    return () => window.removeEventListener(KILIT_KAPISI_OLAYI, dinleyici);
  }, [oku]);

  if (durum === null) return <SkeletonList rows={3} className="mx-auto max-w-3xl" />;

  // Kayıp dosya kilit ekranından ÖNCE gelir: dosya yokken parola sarmalı da
  // yoktur, kilit ekranındaki parola hiçbir zaman kabul edilmezdi.
  if (durum.security_file_missing) {
    return (
      <GuvenlikDosyasiKayip
        sifirlanabilir={durum.reset_available}
        onYenidenDenetle={() => void oku()}
      />
    );
  }

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
