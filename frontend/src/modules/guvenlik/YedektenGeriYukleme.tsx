// Yedekten geri yükleme kartı (Güvenlik sekmesi) — programın AÇILABİLDİĞİ
// senaryo: yanlış/eksik veri girişinden sonra eski bir güne dönüş. Program hiç
// açılmıyorsa (bozuk veritabanı) doğru araç masaüstü "--geri-yukle" kipidir
// (Başlat menüsü: "Yedekten Geri Yükle"); metin kullanıcıyı oraya yönlendirir.
//
// Akış: günlük yedek listesinden seçim YA DA elden getirilen .ksbak dosyası →
// (şifreliyse parola veya kurtarma anahtarı) → onay → POST /backups/restore/.
// Başarıda backend "yeniden başlat" kapısını kurar (tüm API 503 döner); kart
// olayı yayınlar ve YenidenBaslatEkrani arayüzü örter. Parola/kurtarma anahtarı
// yalnız istek gövdesinde taşınır, hiçbir yere yazılmaz.

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { yenidenBaslatGerekliYayinla } from "../../lib/restart";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import Icon from "../../ui/Icon";
import { SkeletonList } from "../../ui/Skeleton";
import TextField from "../../ui/TextField";
import { guvenlikApi } from "./api";
import type { YedekListesi } from "./api";

function boyutMetni(bayt: number): string {
  if (bayt >= 1024 * 1024) return `${(bayt / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bayt / 1024))} KB`;
}

export default function YedektenGeriYukleme() {
  const confirm = useConfirm();
  const [liste, setListe] = useState<YedekListesi | null>(null);
  const [listeHata, setListeHata] = useState<string | null>(null);
  const [secili, setSecili] = useState("");
  const [dosya, setDosya] = useState<File | null>(null);
  const dosyaRef = useRef<HTMLInputElement>(null);
  const [parola, setParola] = useState("");
  const [anahtar, setAnahtar] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [calisiyor, setCalisiyor] = useState(false);

  const yukle = useCallback(() => {
    guvenlikApi
      .yedekler()
      .then((veri) => {
        setListe(veri);
        setListeHata(null);
      })
      .catch((err: unknown) =>
        setListeHata(err instanceof ApiError ? err.message : "Yedek listesi okunamadı."),
      );
  }, []);
  useEffect(yukle, [yukle]);

  const seciliYedek = liste?.backups.find((yedek) => yedek.name === secili) ?? null;
  // Elden yüklenen dosyanın şifreli olup olmadığı istemcide bilinmez; alanlar
  // gösterilir, zorunluluk denetimini backend yapar (Türkçe mesajla).
  const sifreAlanlariGorunur = dosya !== null || (seciliYedek?.encrypted ?? false);

  function dosyaSecimineGec(yeni: File | null) {
    setDosya(yeni);
    setHata(null);
    if (yeni !== null) setSecili("");
  }

  function listedenSec(ad: string) {
    setSecili(ad);
    setDosya(null);
    setHata(null);
    if (dosyaRef.current) dosyaRef.current.value = "";
  }

  async function geriYukle() {
    setHata(null);
    const kaynakAdi = dosya ? dosya.name : secili;
    if (!kaynakAdi) return;
    if (seciliYedek?.encrypted && !parola && !anahtar) {
      setHata("Bu yedek şifreli; uygulama parolasını ya da kurtarma anahtarını girin.");
      return;
    }
    const onay = await confirm({
      title: "Yedekten geri yükle",
      message:
        `'${kaynakAdi}' yedeği mevcut veritabanının yerine konacak. Mevcut veritabanı ` +
        "silinmez; veri klasöründe 'db-onceki-…' adıyla saklanır. İşlem sonrası program " +
        "kapatılıp yeniden açılmalıdır. Devam edilsin mi?",
      confirmLabel: "Geri yükle",
    });
    if (!onay) return;
    setCalisiyor(true);
    try {
      const form = new FormData();
      if (dosya) form.append("file", dosya);
      else form.append("name", secili);
      if (parola) form.append("password", parola);
      if (anahtar) form.append("recovery_key", anahtar);
      await guvenlikApi.geriYukle(form);
      // Backend kapıyı kurdu; ekran örtülür — sırları bellekte tutmaya gerek yok.
      setParola("");
      setAnahtar("");
      yenidenBaslatGerekliYayinla();
    } catch (err) {
      setHata(err instanceof ApiError ? err.message : "Geri yükleme uygulanamadı.");
    } finally {
      setCalisiyor(false);
    }
  }

  return (
    <Card className="p-6">
      <div className="flex items-start gap-3">
        <Icon name="settings_backup_restore" className="mt-0.5 text-primary" />
        <div className="min-w-0 flex-1">
          <h2 className="text-title-large text-on-surface">Yedekten geri yükle</h2>
          <p className="mt-2 text-body-medium text-on-surface-variant">
            Yanlış veri girişinden sonra eski bir güne dönmek için günlük yedeklerden birini seçin
            ya da elinizdeki <span className="font-mono">.ksbak</span> dosyasını yükleyin. Mevcut
            veritabanı silinmez; veri klasöründe <span className="font-mono">db-onceki-…</span>{" "}
            adıyla kenara alınır. Geri yükleme uygulandıktan sonra program kapatılıp yeniden
            açılmalıdır.
          </p>
          <p className="mt-2 text-body-small text-on-surface-variant">
            Program hiç açılmıyorsa (bozuk veritabanı) bu ekrana ulaşamazsınız; o durumda Başlat
            menüsündeki &quot;Yedekten Geri Yükle&quot; kısayolunu kullanın.
          </p>

          {liste === null && listeHata === null ? (
            <SkeletonList rows={2} className="mt-4" />
          ) : listeHata !== null ? (
            <p role="alert" className="mt-4 text-body-small text-error">
              {listeHata}
            </p>
          ) : liste !== null && liste.backups.length === 0 ? (
            <p className="mt-4 text-body-medium text-on-surface-variant">
              Yedek klasöründe geri yüklenebilir dosya yok. Program her açılışta günlük yedek alır;
              elinizde bir yedek varsa aşağıdan dosya olarak yükleyebilirsiniz.
            </p>
          ) : (
            liste !== null && (
              <fieldset className="mt-4">
                <legend className="text-label-large text-on-surface-variant">
                  Günlük yedekler (en yeniden eskiye)
                </legend>
                <ul className="mt-2 max-h-56 space-y-1 overflow-y-auto pr-1">
                  {liste.backups.map((yedek) => (
                    <li key={yedek.name}>
                      <label className="flex cursor-pointer items-center gap-3 rounded-shape-sm px-3 py-2 hover:bg-surface-container">
                        <input
                          type="radio"
                          name="geri-yukleme-yedegi"
                          checked={secili === yedek.name}
                          onChange={() => listedenSec(yedek.name)}
                          className="h-5 w-5 accent-primary"
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-mono text-body-medium text-on-surface">
                            {yedek.name}
                          </span>
                          <span className="block text-label-small text-on-surface-variant">
                            {formatDateTime(yedek.modified_at)} · {boyutMetni(yedek.size)} ·{" "}
                            {yedek.encrypted ? "şifreli" : "düz"}
                          </span>
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </fieldset>
            )
          )}

          {liste !== null && (
            <p className="mt-2 text-label-small text-on-surface-variant">
              Yedek klasörü: <span className="font-mono">{liste.backup_dir}</span>
            </p>
          )}

          <div className="mt-4">
            <label
              htmlFor="geri-yukleme-dosyasi"
              className="mb-1 block text-label-large text-on-surface-variant"
            >
              Ya da elinizdeki yedek dosyası (.ksbak)
            </label>
            <input
              id="geri-yukleme-dosyasi"
              ref={dosyaRef}
              type="file"
              accept=".ksbak"
              onChange={(e) => dosyaSecimineGec(e.target.files?.[0] ?? null)}
              className="block min-h-[var(--ks-field-height)] w-full rounded-shape-sm border border-outline bg-surface-container-lowest px-3 py-2 text-body-medium text-on-surface file:mr-3 file:rounded-shape-sm file:border-0 file:bg-secondary-container file:px-3 file:py-1.5 file:text-label-large file:text-on-secondary-container focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            />
          </div>

          {sifreAlanlariGorunur && (
            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <TextField
                label="Uygulama parolası"
                type="password"
                value={parola}
                onChange={(e) => setParola(e.target.value)}
                autoComplete="current-password"
                helperText="Şifreli yedek için ikisinden birini girin."
              />
              <TextField
                label="Kurtarma anahtarı"
                value={anahtar}
                onChange={(e) => setAnahtar(e.target.value)}
                autoComplete="off"
                helperText="Parola bilinmiyorsa yazdırdığınız anahtar."
              />
            </div>
          )}

          {hata && (
            <p role="alert" className="mt-3 text-body-small text-error">
              {hata}
            </p>
          )}

          <div className="mt-5 flex flex-wrap gap-2">
            <Button
              icon="settings_backup_restore"
              onClick={() => void geriYukle()}
              disabled={calisiyor || (!secili && dosya === null)}
            >
              {calisiyor ? "Geri yükleniyor…" : "Geri yükle"}
            </Button>
            <Button variant="text" icon="refresh" onClick={yukle} disabled={calisiyor}>
              Listeyi yenile
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}
