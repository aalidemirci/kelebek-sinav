// F27/F8 (K14): açılışta aday tespiti + kullanıcı onaylı GERİ DÖNÜŞSÜZ tetik.
// Banner her açılışta yeniden görünür ("Daha sonra" yalnız bu oturumu susturur —
// KVKK saklama süresi hatırlatması kalıcı olarak kapatılamaz, risk #9).
// Onay diyaloğu aday listesini GÖSTERMEDEN tetik atmaz; backend de listedeki
// id'leri aday filtresinden yeniden geçirir (çift kapı).

import { useEffect, useState } from "react";

import { ApiError } from "../../lib/api";
import { formatDate } from "../../lib/format";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { bakimApi } from "./api";
import type { ArsivAdayi } from "./api";

export default function ArsivBakimBanner() {
  const [adaylar, setAdaylar] = useState<ArsivAdayi[]>([]);
  const [dialogAcik, setDialogAcik] = useState(false);
  const [calisiyor, setCalisiyor] = useState(false);
  const [hata, setHata] = useState<string | null>(null);
  const snackbar = useSnackbar();

  useEffect(() => {
    let iptal = false;
    bakimApi
      .arsivAdaylari()
      .then((liste) => {
        if (!iptal) setAdaylar(liste.candidates);
      })
      // Kilitli/kurulumsuz açılışta 423/4xx gelebilir — banner sessizce gizli kalır.
      .catch(() => undefined);
    return () => {
      iptal = true;
    };
  }, []);

  if (adaylar.length === 0) return null;

  const anonimlestir = async () => {
    setCalisiyor(true);
    setHata(null);
    try {
      const sonuc = await bakimApi.anonimlestir(adaylar.map((aday) => aday.id));
      snackbar.success(
        `${sonuc.anonymized.length} arşiv oturumu anonimleştirildi; evrak yeniden basımı açık.`,
      );
      setAdaylar([]);
      setDialogAcik(false);
    } catch (e) {
      setHata(e instanceof ApiError ? e.message : "Anonimleştirme tamamlanamadı.");
    } finally {
      setCalisiyor(false);
    }
  };

  return (
    <>
      <div
        role="status"
        className="mb-4 flex flex-wrap items-center gap-3 rounded-shape-md border border-tertiary/30 bg-tertiary-container px-4 py-3 text-on-tertiary-container"
      >
        <Icon name="auto_delete" className="shrink-0" />
        <p className="min-w-48 flex-1 text-body-medium">
          <span className="font-medium">
            {adaylar.length} arşiv oturumunun saklama süresi doldu (2 ders yılı).
          </span>{" "}
          KVKK veri minimizasyonu gereği kişisel veriler anonimleştirilmelidir.
        </p>
        <div className="flex flex-wrap gap-1">
          <Button variant="tonal" icon="visibility" onClick={() => setDialogAcik(true)}>
            İncele ve anonimleştir
          </Button>
          <Button variant="text" onClick={() => setAdaylar([])}>
            Daha sonra
          </Button>
        </div>
      </div>

      <Dialog
        open={dialogAcik}
        onClose={() => setDialogAcik(false)}
        title="Arşiv anonimleştirme"
        actions={
          <>
            <Button variant="text" onClick={() => setDialogAcik(false)} disabled={calisiyor}>
              Vazgeç
            </Button>
            <Button icon="auto_delete" onClick={() => void anonimlestir()} disabled={calisiyor}>
              {calisiyor ? "Anonimleştiriliyor…" : "Geri dönüşsüz anonimleştir"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <p>
            Aşağıdaki arşiv oturumlarında sınav tarihinin üzerinden 2 ders yılı (730 gün) geçti.
            Anonimleştirme <span className="font-medium">GERİ DÖNÜŞSÜZDÜR</span>: öğrenci ve
            öğretmen adları ile okul numaraları silinir, yoklama notları temizlenir, kitapçık ve
            soru dosyaları kaldırılır. Salon/koltuk düzeni ve sayımlar istatistik arşivi olarak
            kalır; evrak yeniden basımı çalışmaya devam eder (adlar "—" basılır).
          </p>
          <ul className="space-y-1">
            {adaylar.map((aday) => (
              <li
                key={aday.id}
                className="flex items-center justify-between gap-3 rounded-shape-sm bg-surface-container px-3 py-2"
              >
                <span className="text-on-surface">{aday.name}</span>
                <span className="shrink-0 text-body-small">{formatDate(aday.exam_date)}</span>
              </li>
            ))}
          </ul>
          {hata && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-shape-sm bg-error-container px-4 py-3 text-on-error-container"
            >
              <Icon name="error" />
              <span>{hata}</span>
            </div>
          )}
        </div>
      </Dialog>
    </>
  );
}
