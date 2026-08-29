// Kurtarma anahtarı diyaloğu (F5-D5) — anahtar SUNUCUDA SAKLANMAZ, bu ekran
// onu gösteren TEK yerdir. O yüzden diyalog "kaydettim" onayı verilmeden
// kapanmaz ve kullanıcıya iki kalıcı kopya yolu sunar: yazdırma ve metin dosyası.
//
// Yazdırma notu: program bir masaüstü penceresi (pywebview) içinde koştuğu için
// `window.print()` tüm uygulama kabuğunu basardı. Diyalog açıkken devreye giren
// küçük bir YAZDIRMA stili sayfadaki her şeyi gizleyip yalnız anahtar kartını
// bırakır. Stil bilinçli olarak bu bileşenin içindedir (ortak `index.css`'e
// dokunmamak için) ve renk/ölçü içermez — yalnız görünürlük anahtarlar.

import { useState } from "react";

import { saveBlob } from "../../lib/download";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import { KURTARMA_UYARISI } from "./metinler";

const YAZDIRMA_ALANI_ID = "kurtarma-anahtari-yazdirma-alani";

// Kural `@media print { … }` bloğunun İÇİNDEDİR, `<style media="print">`
// niteliğiyle DEĞİL: jsdom nitelik biçimini yok sayıp kuralı ekrana da uygular,
// o zaman `visibility: hidden` tüm sayfayı erişilebilirlik ağacından düşürür
// (testlerde "rol bulunamadı" olarak patladı — gerçek tarayıcıda görünmez bir
// tuzak olurdu).
const YAZDIRMA_STILI = `
  @media print {
    body * { visibility: hidden !important; }
    #${YAZDIRMA_ALANI_ID}, #${YAZDIRMA_ALANI_ID} * { visibility: visible !important; }
    #${YAZDIRMA_ALANI_ID} { position: absolute; left: 0; top: 0; width: 100%; }
  }
`;

interface KurtarmaAnahtariDiyaloguProps {
  open: boolean;
  /** Sunucunun bir daha üretemeyeceği anahtar (ör. "A1B2-C3D4-…"). */
  anahtar: string;
  /** Okul adı — çıktının hangi kuruma ait olduğu belli olsun. */
  okulAdi?: string;
  onKapat: () => void;
}

function metinCiktisi(anahtar: string, okulAdi: string): string {
  const tarih = new Date().toLocaleDateString("tr-TR");
  return [
    "DİSİPLİN DEFTERİ — KURTARMA ANAHTARI",
    okulAdi ? `Kurum: ${okulAdi}` : "",
    `Oluşturma tarihi: ${tarih}`,
    "",
    anahtar,
    "",
    "Bu anahtar, uygulama parolası unutulduğunda kayıtlara erişmenin tek yoludur.",
    "Yazıcı çıktısını kilitli bir dolapta saklayın; bilgisayarda tutmayın.",
  ]
    .filter(Boolean)
    .join("\n");
}

export default function KurtarmaAnahtariDiyalogu({
  open,
  anahtar,
  okulAdi = "",
  onKapat,
}: KurtarmaAnahtariDiyaloguProps) {
  const [kaydettim, setKaydettim] = useState(false);

  function yazdir() {
    // jsdom/bazı gömülü motorlarda `print` bulunmayabilir — sessizce atlanır.
    if (typeof window.print === "function") window.print();
  }

  function indir() {
    saveBlob(
      new Blob([metinCiktisi(anahtar, okulAdi)], { type: "text/plain;charset=utf-8" }),
      "kurtarma-anahtari.txt",
    );
  }

  return (
    <Dialog
      open={open}
      // Kapatma yalnız onay kutusundan sonra: ESC/scrim ile kaçış anahtarı kaybettirirdi.
      onClose={() => {
        if (kaydettim) onKapat();
      }}
      title="Kurtarma anahtarınız"
      actions={
        <Button
          onClick={() => {
            setKaydettim(false);
            onKapat();
          }}
          disabled={!kaydettim}
        >
          Kapat
        </Button>
      }
    >
      <style>{YAZDIRMA_STILI}</style>

      <div id={YAZDIRMA_ALANI_ID} className="mb-4">
        <p className="text-label-large text-on-surface-variant">
          Kelebek Sınav kurtarma anahtarı{okulAdi ? ` — ${okulAdi}` : ""}
        </p>
        <p
          // `select-all` + tek boşluklu font: elle yazarken karakter karışmasın.
          className="mt-2 select-all break-all rounded-shape-md bg-surface-container-high p-4 font-mono text-title-medium tracking-widest text-on-surface"
          data-testid="kurtarma-anahtari"
        >
          {anahtar}
        </p>
      </div>

      <p className="mb-4 text-body-small text-error">{KURTARMA_UYARISI}</p>

      <div className="mb-4 flex flex-wrap gap-2">
        <Button variant="tonal" icon="print" type="button" onClick={yazdir}>
          Yazdır
        </Button>
        <Button variant="outlined" icon="download" type="button" onClick={indir}>
          Metin dosyası olarak kaydet
        </Button>
      </div>

      <label className="flex min-h-12 items-center gap-3 text-body-medium text-on-surface">
        <input
          type="checkbox"
          checked={kaydettim}
          onChange={(e) => setKaydettim(e.target.checked)}
          className="size-5 accent-primary"
        />
        Kurtarma anahtarını yazdırdım / güvenli bir yere kaydettim.
      </label>
    </Dialog>
  );
}
