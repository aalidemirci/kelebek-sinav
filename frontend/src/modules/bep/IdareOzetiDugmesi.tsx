// "İdare özeti (PDF)" düğmesi — Sorular ve Kitapçıklar'daki BEP bölümü ile
// Yerleştirme Kuralları'ndaki tedbir bölümü AYNI belgeyi indirir (07.10.2026).
//
// Belge yalnız idare nüshasıdır: salonlara dağıtılmaz, "Tümünü indir" paketine
// girmez. Ek süre ve okuyucu/yazıcı desteği YALNIZ bu belgede basılır (kullanıcı
// kararı — salon evrakına öğrenci notu konmaz, gözetmene idare bildirir).

import { useState } from "react";

import { ApiError } from "../../lib/api";
import { dosyaAdi, saveBlob } from "../../lib/download";
import { formatDate } from "../../lib/format";
import Button from "../../ui/Button";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { individualQuestionApi } from "./api";

/** İndirilen idare özetinin dosya adındaki belge adı (docs/sozluk.md §3). */
export const IEP_SUMMARY_FILE_TITLE = "Sınav Tedbirleri ve BEP İdare Özeti";

export default function IdareOzetiDugmesi({
  session,
}: {
  session: { id: number; name: string; exam_date: string };
}) {
  const snackbar = useSnackbar();
  const [indiriliyor, setIndiriliyor] = useState(false);

  const indir = async () => {
    setIndiriliyor(true);
    try {
      const blob = await individualQuestionApi.summaryBlob(session.id);
      // Belge adı + oturum adı + tarih (docs/sozluk.md §3).
      saveBlob(
        blob,
        dosyaAdi([IEP_SUMMARY_FILE_TITLE, session.name, formatDate(session.exam_date)], "pdf"),
      );
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "İdare özeti indirilemedi.");
    } finally {
      setIndiriliyor(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button
        variant="outlined"
        icon="picture_as_pdf"
        onClick={() => void indir()}
        disabled={indiriliyor}
      >
        İdare özeti (PDF)
      </Button>
      <span className="text-body-small text-on-surface-variant">
        Yalnız idare nüshasıdır; salonlara dağıtılmaz ve “Tümünü indir” paketine girmez.
      </span>
    </div>
  );
}
