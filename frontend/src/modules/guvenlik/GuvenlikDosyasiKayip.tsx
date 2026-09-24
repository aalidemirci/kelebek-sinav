// Güvenlik dosyası kayıp ekranı — uygulama parolası kuruluyken guvenlik.json
// silinir, yeniden adlandırılır ya da içi boşaltılır/bozulursa backend ikisini
// aynı `security_file_missing` durumuyla bildirir. Program "parolasız"a DÖNMEZ:
// backend veri uçlarını 423 `guvenlik_dosyasi_kayip` ile keser ve yalnız durum
// uçlarını, sıfırlamayı, yedek listesini ve yedekten geri yüklemeyi açık bırakır.
//
// Ekran çıkış yollarını anlaşılır dille söyler:
// 1. Dosyanın kopyasını veri klasörüne geri koymak → "Yeniden denetle" (backend
//    her istekte diske baktığı için dosya döndüğü anda olağan kilit ekranına
//    geçilir).
// 2. Yedekten geri yüklemek → geri yükleme guvenlik.json'u yedeğin kurtarma
//    başlığından yeniden yazar; ardından "yeniden başlat" ekranı gelir.
// 3. YALNIZ korunan kayıt yokken (backend `reset_available`: dosya okunamıyor
//    ve kayıtların anahtarı veritabanına işlenmemiş) "Güvenlik dosyasını
//    sıfırla": okunamayan dosya arşivlenir (silinmez), program parolasız kipe
//    döner. Koşul sağlanmıyorsa kart hiç görünmez, backend de 409 döner.

import { useState } from "react";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import Icon from "../../ui/Icon";
import YedektenGeriYukleme from "./YedektenGeriYukleme";
import { guvenlikApi } from "./api";
import {
  DOSYA_KAYIP_BASLIGI,
  DOSYA_KAYIP_GERI_KOY,
  DOSYA_KAYIP_METNI,
  DOSYA_KAYIP_SIFIRLA_METNI,
  DOSYA_KAYIP_YEDEKTEN,
} from "./metinler";

interface GuvenlikDosyasiKayipProps {
  /** Güvenlik durumunu yeniden okur (dosya geri konduysa kilit ekranına geçilir). */
  onYenidenDenetle: () => void;
  /** Backend `reset_available`: "güvenlik dosyasını sıfırla" yolu açık mı? */
  sifirlanabilir?: boolean;
}

/** Üçüncü çıkış yolu — yalnız korunan kayıt yokken görünür (dosya başı notu). */
function SifirlamaKarti({ onSifirlandi }: { onSifirlandi: () => void }) {
  const confirm = useConfirm();
  const [calisiyor, setCalisiyor] = useState(false);
  const [hata, setHata] = useState<string | null>(null);

  async function sifirla() {
    // Başlık soru, gövde sonuç (docs/sozluk.md §3).
    const onay = await confirm({
      title: "Güvenlik dosyası sıfırlansın mı?",
      message:
        "Okunamayan dosya veri klasöründe “guvenlik-arsiv” adıyla saklanır ve program " +
        "parolasız çalışmaya döner. İsterseniz sonra Ayarlar → Güvenlik’ten yeniden parola " +
        "koyarsınız.",
      confirmLabel: "Sıfırla",
    });
    if (!onay) return;
    setCalisiyor(true);
    setHata(null);
    try {
      await guvenlikApi.sifirla();
      onSifirlandi();
    } catch (err) {
      setHata(err instanceof ApiError ? err.message : "Güvenlik dosyası sıfırlanamadı.");
    } finally {
      setCalisiyor(false);
    }
  }

  return (
    <Card elevation={1} className="p-6">
      <h2 className="text-title-medium text-on-surface">Güvenlik dosyasını sıfırlama</h2>
      <p className="mt-2 text-body-medium text-on-surface-variant">{DOSYA_KAYIP_SIFIRLA_METNI}</p>
      {hata && (
        <p role="alert" className="mt-2 text-body-small text-error">
          {hata}
        </p>
      )}
      <div className="mt-4">
        <Button icon="restart_alt" onClick={() => void sifirla()} disabled={calisiyor}>
          Güvenlik dosyasını sıfırla
        </Button>
      </div>
    </Card>
  );
}

export default function GuvenlikDosyasiKayip({
  onYenidenDenetle,
  sifirlanabilir = false,
}: GuvenlikDosyasiKayipProps) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 p-4">
      <Card elevation={1} className="p-6">
        <div className="mb-4 flex items-center gap-3">
          <Icon name="gpp_maybe" size="lg" className="text-error" />
          <h1 className="text-headline-small text-on-surface">{DOSYA_KAYIP_BASLIGI}</h1>
        </div>
        <p className="text-body-medium text-on-surface-variant">{DOSYA_KAYIP_METNI}</p>
        <h2 className="mt-4 text-title-medium text-on-surface">Ne yapmalı?</h2>
        <ol className="mt-2 list-decimal space-y-2 pl-5 text-body-medium text-on-surface-variant">
          <li>{DOSYA_KAYIP_GERI_KOY}</li>
          <li>{DOSYA_KAYIP_YEDEKTEN}</li>
        </ol>
        <div className="mt-5">
          <Button variant="tonal" icon="refresh" onClick={onYenidenDenetle}>
            Yeniden denetle
          </Button>
        </div>
      </Card>

      {sifirlanabilir && <SifirlamaKarti onSifirlandi={onYenidenDenetle} />}

      <YedektenGeriYukleme kayipKipi />
    </div>
  );
}
