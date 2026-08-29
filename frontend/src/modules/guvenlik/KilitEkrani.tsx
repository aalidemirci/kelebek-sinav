// Kilit ekranı (F5-D5) — uygulama parolası kuruluyken programın ilk yüzü.
// OYS'de karşılığı YOK (orada Google/JWT girişi vardır); bu ekran authsuz tek
// kullanıcılı programın TEK kapısıdır: kimlik doğrulamaz, yalnız kayıtların
// şifresini çözecek anahtarı belleğe aldırır.
//
// İki yol sunar: parola VE (parola unutulduysa) kurtarma anahtarı. İkincisi
// yeni parola belirlemeyi de zorunlu kılar — kurtarma bir kerelik giriş değil,
// parola sıfırlamadır (backend `unlock_with_recovery`).

import { useState } from "react";
import type { FormEvent } from "react";

import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import TextField from "../../ui/TextField";
import { guvenlikApi } from "./api";
import { KAPSAM_METNI, YARIM_GECIS_METNI } from "./metinler";

interface KilitEkraniProps {
  /** Kilit açıldığında çağrılır (kapı içeriği göstermeye geçer). */
  onAcildi: () => void;
  /** Yarım kalan geçiş uyarısı gösterilsin mi? */
  yarimGecis?: boolean;
}

function hataMesaji(err: unknown, varsayilan: string): string {
  return err instanceof Error && err.message ? err.message : varsayilan;
}

export default function KilitEkrani({ onAcildi, yarimGecis = false }: KilitEkraniProps) {
  const [kurtarmaKipi, setKurtarmaKipi] = useState(false);
  const [parola, setParola] = useState("");
  const [kurtarmaAnahtari, setKurtarmaAnahtari] = useState("");
  const [yeniParola, setYeniParola] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [calisiyor, setCalisiyor] = useState(false);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    setHata(null);
    setCalisiyor(true);
    try {
      if (kurtarmaKipi) {
        await guvenlikApi.kurtar(kurtarmaAnahtari, yeniParola);
      } else {
        await guvenlikApi.ac(parola);
      }
      setParola("");
      setKurtarmaAnahtari("");
      setYeniParola("");
      onAcildi();
    } catch (err) {
      setHata(hataMesaji(err, "Kilit açılamadı."));
    } finally {
      setCalisiyor(false);
    }
  }

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-4">
      <Card elevation={1} className="w-full max-w-md p-6">
        <div className="mb-4 flex items-center gap-3">
          <Icon name="lock" size="lg" className="text-primary" />
          <h1 className="text-headline-small text-on-surface">Kayıtlar kilitli</h1>
        </div>

        {yarimGecis && (
          <p className="mb-4 rounded-shape-md bg-tertiary-container p-3 text-body-small text-on-tertiary-container">
            {YARIM_GECIS_METNI}
          </p>
        )}

        <form onSubmit={gonder} className="flex flex-col gap-4">
          {kurtarmaKipi ? (
            <>
              <TextField
                label="Kurtarma anahtarı"
                value={kurtarmaAnahtari}
                onChange={(e) => setKurtarmaAnahtari(e.target.value)}
                autoComplete="off"
                spellCheck={false}
                placeholder="ABCD-EFGH-..."
                required
              />
              <TextField
                label="Yeni parola"
                type="password"
                value={yeniParola}
                onChange={(e) => setYeniParola(e.target.value)}
                autoComplete="new-password"
                helperText="En az 8 karakter. Kurtarma anahtarı bundan sonra da geçerli kalır."
                required
              />
            </>
          ) : (
            <TextField
              label="Uygulama parolası"
              type="password"
              value={parola}
              onChange={(e) => setParola(e.target.value)}
              autoComplete="current-password"
              autoFocus
              error={hata ?? undefined}
              required
            />
          )}

          {kurtarmaKipi && hata && (
            <p role="alert" className="text-body-small text-error">
              {hata}
            </p>
          )}

          <Button type="submit" disabled={calisiyor} block>
            {calisiyor ? "Açılıyor…" : kurtarmaKipi ? "Kurtar ve aç" : "Aç"}
          </Button>
        </form>

        <div className="mt-4 flex justify-center">
          <Button
            variant="text"
            type="button"
            onClick={() => {
              setKurtarmaKipi((onceki) => !onceki);
              setHata(null);
            }}
          >
            {kurtarmaKipi ? "Parolayla açmaya dön" : "Parolamı unuttum"}
          </Button>
        </div>

        <p className="mt-4 border-t border-outline-variant pt-4 text-body-small text-on-surface-variant">
          {KAPSAM_METNI}
        </p>
      </Card>
    </div>
  );
}
