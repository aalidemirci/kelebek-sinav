// Güvenlik ayarları bölümü (F5-D5) — Ayarlar sayfasına bir sekme/kart olarak
// takılır (rota ve menü bağlama iş sahibinindir; bkz. teslim raporu).
//
// Üç eylem: parola koy / parola değiştir / parolayı kaldır (+ "şimdi kilitle").
// Metinler `metinler.ts`'ten gelir ve DÜRÜSTTÜR: bu koruma alan şifrelemesidir,
// tam disk şifrelemesi değildir.

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Dialog from "../../ui/Dialog";
import Icon from "../../ui/Icon";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import KurtarmaAnahtariDiyalogu from "./KurtarmaAnahtariDiyalogu";
import SifreliYedekleme from "./SifreliYedekleme";
import { guvenlikApi } from "./api";
import type { GuvenlikDurumu } from "./api";
import { kilitOlayiYayinla } from "./GuvenlikKapisi";
import {
  KALDIRMA_UYARISI,
  KAPSAM_DISI_METNI,
  KAPSAM_METNI,
  KURMA_UYARISI,
  YARIM_GECIS_METNI,
} from "./metinler";

type Kip = "yok" | "kur" | "degistir" | "kaldir";

function hataMesaji(err: unknown, varsayilan: string): string {
  return err instanceof Error && err.message ? err.message : varsayilan;
}

interface GuvenlikAyarlariProps {
  /** Kurtarma anahtarı çıktısında görünsün diye (Ayarlar sayfası zaten okur). */
  okulAdi?: string;
}

export default function GuvenlikAyarlari({ okulAdi = "" }: GuvenlikAyarlariProps) {
  const snackbar = useSnackbar();
  const [durum, setDurum] = useState<GuvenlikDurumu | null>(null);
  const [kip, setKip] = useState<Kip>("yok");
  const [parola, setParola] = useState("");
  const [parolaTekrar, setParolaTekrar] = useState("");
  const [yeniParola, setYeniParola] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [calisiyor, setCalisiyor] = useState(false);
  const [kurtarmaAnahtari, setKurtarmaAnahtari] = useState<string | null>(null);

  const oku = useCallback(() => {
    guvenlikApi
      .durum()
      .then(setDurum)
      .catch(() => snackbar.error("Güvenlik durumu okunamadı."));
  }, [snackbar]);

  useEffect(() => oku(), [oku]);

  function kapat() {
    setKip("yok");
    setParola("");
    setParolaTekrar("");
    setYeniParola("");
    setHata(null);
  }

  async function gonder(e: FormEvent) {
    e.preventDefault();
    setHata(null);
    if (kip !== "kaldir" && parolaTekrar !== (kip === "kur" ? parola : yeniParola)) {
      setHata("Parolalar eşleşmedi.");
      return;
    }
    setCalisiyor(true);
    try {
      if (kip === "kur") {
        const sonuc = await guvenlikApi.kur(parola);
        setKurtarmaAnahtari(sonuc.recovery_key);
        snackbar.success("Parola kuruldu; kişisel veri alanları şifrelendi.");
      } else if (kip === "degistir") {
        await guvenlikApi.parolaDegistir(parola, yeniParola);
        snackbar.success("Parola değiştirildi.");
      } else {
        await guvenlikApi.kaldir(parola);
        snackbar.success("Parola kaldırıldı; alanlar düz metne döndürüldü.");
      }
      kapat();
      oku();
    } catch (err) {
      setHata(hataMesaji(err, "İşlem tamamlanamadı."));
    } finally {
      setCalisiyor(false);
    }
  }

  async function kilitle() {
    try {
      await guvenlikApi.kilitle();
      kilitOlayiYayinla();
    } catch (err) {
      snackbar.error(hataMesaji(err, "Kilitlenemedi."));
    }
  }

  if (durum === null) return <SkeletonList rows={2} />;

  const baslikIkonu = durum.password_set ? "lock" : "lock_open";
  const dialogBasligi =
    kip === "kur"
      ? "Uygulama parolası koy"
      : kip === "degistir"
        ? "Parolayı değiştir"
        : "Parolayı kaldır";

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-6">
        <div className="mb-2 flex items-center gap-3">
          <Icon name={baslikIkonu} className="text-primary" />
          <h2 className="text-title-large text-on-surface">
            {durum.password_set ? "Kişisel veri alanları şifreli" : "Kişisel veri alanları açık"}
          </h2>
        </div>

        <p className="text-body-medium text-on-surface-variant">{KAPSAM_METNI}</p>
        <p className="mt-2 text-body-small text-on-surface-variant">{KAPSAM_DISI_METNI}</p>

        {durum.protected_fields.length > 0 && (
          <p className="mt-3 text-body-small text-on-surface-variant">
            <span className="text-label-large">Şifrelenen alanlar: </span>
            {durum.protected_fields.join(", ")}
          </p>
        )}

        {durum.transition_pending && (
          <p className="mt-3 rounded-shape-md bg-tertiary-container p-3 text-body-small text-on-tertiary-container">
            {YARIM_GECIS_METNI}
          </p>
        )}

        <div className="mt-6 flex flex-wrap gap-2">
          {durum.password_set ? (
            <>
              <Button variant="tonal" icon="key" onClick={() => setKip("degistir")}>
                Parolayı değiştir
              </Button>
              <Button variant="outlined" icon="lock" onClick={kilitle}>
                Şimdi kilitle
              </Button>
              <Button variant="text" icon="lock_open" onClick={() => setKip("kaldir")}>
                Parolayı kaldır
              </Button>
            </>
          ) : (
            <Button icon="lock" onClick={() => setKip("kur")}>
              Parola koy
            </Button>
          )}
        </div>
      </Card>

      <SifreliYedekleme parolaKurulu={durum.password_set} />

      <Dialog open={kip !== "yok"} onClose={kapat} title={dialogBasligi}>
        <form onSubmit={gonder} className="flex flex-col gap-4">
          <p className="text-body-small text-on-surface-variant">
            {kip === "kur" ? KURMA_UYARISI : kip === "kaldir" ? KALDIRMA_UYARISI : ""}
          </p>

          <TextField
            label={kip === "kur" ? "Yeni parola" : "Mevcut parola"}
            type="password"
            value={parola}
            onChange={(e) => setParola(e.target.value)}
            autoComplete={kip === "kur" ? "new-password" : "current-password"}
            helperText={kip === "kur" ? "En az 8 karakter." : undefined}
            required
          />

          {kip === "degistir" && (
            <TextField
              label="Yeni parola"
              type="password"
              value={yeniParola}
              onChange={(e) => setYeniParola(e.target.value)}
              autoComplete="new-password"
              helperText="En az 8 karakter."
              required
            />
          )}

          {kip !== "kaldir" && (
            <TextField
              // Etiket "Yeni parola (tekrar)" DEĞİL: iki alanın adı aynı ön ekle
              // başladığında hem ekran okuyucuda hem testte ayrışmıyor.
              label="Parola (tekrar)"
              type="password"
              value={parolaTekrar}
              onChange={(e) => setParolaTekrar(e.target.value)}
              autoComplete="new-password"
              error={hata ?? undefined}
              required
            />
          )}

          {kip === "kaldir" && hata && (
            <p role="alert" className="text-body-small text-error">
              {hata}
            </p>
          )}

          <div className="flex justify-end gap-2">
            <Button variant="text" type="button" onClick={kapat}>
              Vazgeç
            </Button>
            <Button type="submit" disabled={calisiyor}>
              {calisiyor ? "Uygulanıyor…" : "Uygula"}
            </Button>
          </div>
        </form>
      </Dialog>

      <KurtarmaAnahtariDiyalogu
        open={kurtarmaAnahtari !== null}
        anahtar={kurtarmaAnahtari ?? ""}
        okulAdi={okulAdi}
        onKapat={() => setKurtarmaAnahtari(null)}
      />
    </div>
  );
}
