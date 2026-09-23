// "Kurtarma anahtarını yenile" kartı — görev devri. Kurtarma anahtarını elinde
// tutan kişi görevden ayrıldıysa ya da kâğıt kaybolduysa yenisi üretilir.
// Parola değişimi kurtarma anahtarını geçersiz KILMAZ (backend yalnız parola
// sarmalını yeniler); bunun için bu ayrı işlem gerekir.
//
// Onay diyaloğu uygulama parolasını ister (başlık soru, gövde sonuç —
// docs/sozluk.md §3); backend parolayı bellekteki anahtara karşı doğrular,
// aynı veri anahtarını YENİ kurtarma anahtarıyla sarmalar, önceki güvenlik
// dosyasını "guvenlik-arsiv" adıyla saklar ve yeni anahtarı BİR KEZ döndürür.
// Anahtar kurulumdaki diyalogla (KurtarmaAnahtariDiyalogu) gösterilir: yazdırma
// ya da kaydetme onaylanmadan kapanmaz. Metinler dürüsttür: eski yedeklerin eski
// anahtarla açılmaya devam ettiğini ve yenilemenin tam bir iptal olmadığını söyler.

import { useState } from "react";
import type { FormEvent } from "react";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Dialog from "../../ui/Dialog";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import KurtarmaAnahtariDiyalogu from "./KurtarmaAnahtariDiyalogu";
import { guvenlikApi } from "./api";
import {
  ELE_GECMIS_ANAHTAR_METNI,
  ESKI_YEDEK_METNI,
  YENILEME_METNI,
  YENILEME_SONUCU_METNI,
} from "./metinler";

interface KurtarmaAnahtariniYenileKartiProps {
  /** Kurtarma anahtarı çıktısında görünsün diye. */
  okulAdi?: string;
}

export default function KurtarmaAnahtariniYenileKarti({
  okulAdi = "",
}: KurtarmaAnahtariniYenileKartiProps) {
  const snackbar = useSnackbar();
  const [acik, setAcik] = useState(false);
  const [parola, setParola] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [calisiyor, setCalisiyor] = useState(false);
  const [yeniAnahtar, setYeniAnahtar] = useState<string | null>(null);

  function kapat() {
    setAcik(false);
    setParola("");
    setHata(null);
  }

  async function yenile(e: FormEvent) {
    e.preventDefault();
    setHata(null);
    setCalisiyor(true);
    try {
      const sonuc = await guvenlikApi.kurtarmaAnahtariniYenile(parola);
      kapat();
      setYeniAnahtar(sonuc.recovery_key);
      snackbar.success("Yeni kurtarma anahtarı üretildi. Yazdırıp saklayın.");
    } catch (err) {
      setHata(err instanceof ApiError ? err.message : "Kurtarma anahtarı yenilenemedi.");
    } finally {
      setCalisiyor(false);
    }
  }

  return (
    <Card className="p-6">
      <div className="mb-2 flex items-center gap-3">
        <Icon name="autorenew" className="text-primary" />
        <h2 className="text-title-large text-on-surface">Kurtarma anahtarını yenile</h2>
      </div>
      <p className="text-body-medium text-on-surface-variant">{YENILEME_METNI}</p>
      <div className="mt-4">
        <Button variant="tonal" icon="autorenew" onClick={() => setAcik(true)}>
          Kurtarma anahtarını yenile
        </Button>
      </div>

      <Dialog open={acik} onClose={kapat} title="Kurtarma anahtarı yenilensin mi?">
        <form onSubmit={yenile} className="flex flex-col gap-4">
          <p className="text-body-medium text-on-surface">{YENILEME_SONUCU_METNI}</p>
          <p className="text-body-medium text-on-surface-variant">{ESKI_YEDEK_METNI}</p>
          <p className="text-body-small text-on-surface-variant">{ELE_GECMIS_ANAHTAR_METNI}</p>
          <TextField
            label="Uygulama parolası"
            type="password"
            value={parola}
            onChange={(e) => setParola(e.target.value)}
            autoComplete="current-password"
            error={hata ?? undefined}
            required
          />
          <div className="flex justify-end gap-2">
            <Button variant="text" type="button" onClick={kapat}>
              Vazgeç
            </Button>
            <Button type="submit" icon="autorenew" disabled={calisiyor || !parola}>
              {calisiyor ? "Üretiliyor…" : "Yeni anahtar üret"}
            </Button>
          </div>
        </form>
      </Dialog>

      <KurtarmaAnahtariDiyalogu
        open={yeniAnahtar !== null}
        anahtar={yeniAnahtar ?? ""}
        okulAdi={okulAdi}
        baslik="Yeni kurtarma anahtarınız"
        ekMetin={ESKI_YEDEK_METNI}
        onKapat={() => setYeniAnahtar(null)}
      />
    </Card>
  );
}
