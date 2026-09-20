// Sorular ve Kitapçıklar → "BEP kapsamındaki öğrenciler — bireysel soru dosyaları"
// bölümü (20.09.2026). Program, oturumun YERLEŞİMİNDE bulunan BEP kapsamındaki
// öğrencileri (Kişiler → BEP listesi) hatırlatır; idareci hangisine ayrı sınav
// uygulanacağını SEÇER ve o öğrencinin soru PDF'ini yükler. Kitapçık üretiminde
// öğrencinin kitapçığı kendi PDF'inden, ADINA basılır.
//
// Satırın üç durumu (`IndividualQuestionRow.document`):
//   null                → seçim yok: öğrenci dersin soru dosyasını alır;
//   has_file === false  → seçildi, PDF bekleniyor (kitapçık üretimi reddedilir);
//   has_file === true   → PDF yüklü.
// `seat_no === null` yetim satırdır: öğrenci yeniden dağıtımda oturumdan düşmüş,
// seçimi kalmış — görünmez kalmasın diye listelenir, yalnız kaldırılabilir.
//
// GİZLİLİK (KVKK md. 6 — özel nitelikli veriye işaret): salon evrakında ve
// kitapçıkta öğrenciyi ayıran hiçbir işaret yoktur; basılı tek bilgi "İdare
// özeti"dir (salonlara dağıtılmaz, "Tümünü indir" paketine girmez). Bu ekranın
// onay, bildirim ve diyalog başlıklarında öğrenci adı ve okul numarası GEÇMEZ —
// satır zaten gösteriyor; diyaloglar satırı salon ve koltukla anar. Tanı ya da
// açıklama alanı YOKTUR ve EKLENMEZ.
//
// "Ortak kitapçık/ortak kâğıt" DENMEZ (MEB'de "ortak sınav" okul geneli
// sınavdır — docs/sozluk.md): bireysel soru dosyasının karşıtı "dersin soru
// dosyası"dır.

import { useCallback, useId, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import { dosyaAdi, saveBlob } from "../../lib/download";
import { formatDate } from "../../lib/format";
import Button from "../../ui/Button";
import { useConfirm } from "../../ui/ConfirmProvider";
import Dialog from "../../ui/Dialog";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { ExamSession } from "../oturumlar/api";
import SoruYuklemeDialog from "../oturumlar/SoruYuklemeDialog";
import type { IndividualDocument, IndividualQuestionRow } from "./api";
import { individualQuestionApi } from "./api";
import BepParolaUyarisi from "./BepParolaUyarisi";

/** İndirilen idare özetinin dosya adındaki belge adı (docs/sozluk.md §3). */
export const IEP_SUMMARY_FILE_TITLE = "BEP İdare Özeti";

/** Satırın yeri — diyalog başlıkları da öğrenciyi adla değil BUNUNLA anar. */
function yerEtiketi(row: IndividualQuestionRow): string {
  return row.seat_no === null ? "yerleşimde yok" : `${row.room_name} · koltuk ${row.seat_no}`;
}

/** "2 sayfa · tek puan kutusu" — dersin soru dosyası satırıyla AYNI biçim. */
function dosyaOzeti(doc: IndividualDocument): string {
  const puan =
    doc.score_mode === "SINGLE_BOX"
      ? "tek puan kutusu"
      : `${doc.question_count ?? "?"} soruluk puan tablosu`;
  return `${doc.page_count ?? "?"} sayfa · ${puan}`;
}

function BireyselSatir({
  row,
  sessionId,
  locked,
  onChanged,
  onPreview,
}: {
  row: IndividualQuestionRow;
  sessionId: number;
  locked: boolean;
  onChanged: () => void;
  onPreview: (row: IndividualQuestionRow, doc: IndividualDocument) => void;
}) {
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const [uploadOpen, setUploadOpen] = useState(false);
  const closeUpload = useCallback(() => setUploadOpen(false), []);
  const doc = row.document;
  // Yetim satır: öğrenci artık yerleşimde yok — yükleme/seçim anlamsız, yalnız kaldırılır.
  const yetim = row.seat_no === null;

  const sec = useMutation({
    mutationFn: () => individualQuestionApi.select(sessionId, row.student_id),
    onSuccess: () => {
      snackbar.success("Bireysel soru dosyası seçildi; şimdi öğrencinin soru PDF'ini yükleyin.");
      onChanged();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Seçim yapılamadı."),
  });

  const yukle = useMutation({
    mutationFn: ({ documentId, form }: { documentId: number; form: FormData }) =>
      individualQuestionApi.uploadFile(documentId, form),
    onSuccess: () => {
      setUploadOpen(false);
      snackbar.success("Bireysel soru dosyası yüklendi.");
      onChanged();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Yükleme başarısız."),
  });

  const kaldir = useMutation({
    mutationFn: (documentId: number) => individualQuestionApi.remove(documentId),
    onSuccess: () => {
      snackbar.success("Bireysel soru dosyası kaldırıldı.");
      onChanged();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Kaldırılamadı."),
  });

  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-shape-md border border-outline-variant p-3">
      <span className="text-title-small text-on-surface">
        {row.student_number || "—"} · {row.full_name}
      </span>
      <span className="text-body-small text-on-surface-variant">
        {[row.class_label, yerEtiketi(row), row.course_label].filter(Boolean).join(" · ")}
      </span>
      {!row.on_iep_list && (
        // Listeden çıkarılan öğrencinin onaylı/arşiv oturumdaki dosyası yerinde kalır
        // (o sınavın yapıldığı hâlin parçasıdır) — satırın neden durduğu söylenir.
        // "BEP" sözcüğü bölüm başlığında kalır (docs/sozluk.md), satırda yinelenmez.
        <span className="text-body-small text-on-surface-variant">listeden çıkarılmış</span>
      )}
      {doc === null ? (
        <span className="text-body-small text-on-surface-variant">Dersin soru dosyası</span>
      ) : doc.has_file ? (
        <span className="text-body-small text-on-surface-variant">{dosyaOzeti(doc)}</span>
      ) : (
        <span className="text-body-small text-error">Dosya yüklenmedi</span>
      )}
      <span className="ml-auto" />

      {doc === null && !locked && !yetim && (
        <Button
          variant="tonal"
          icon="assignment_ind"
          onClick={() => sec.mutate()}
          disabled={sec.isPending}
        >
          Bireysel soru dosyası uygula
        </Button>
      )}
      {doc !== null && doc.has_file && (locked || !yetim) && (
        <Button variant="text" icon="visibility" onClick={() => onPreview(row, doc)}>
          Önizle
        </Button>
      )}
      {doc !== null && !locked && !yetim && (
        <Button variant="tonal" icon="upload_file" onClick={() => setUploadOpen(true)}>
          {doc.has_file ? "Değiştir" : "Yükle"}
        </Button>
      )}
      {doc !== null && !locked && (
        <Button
          variant="text"
          icon="delete"
          // Satır ve yüklü PDF KATI silinir (geri alınamaz) → onaydan geçer.
          // Başlık soru, gövde sonuç; öğrenci adı ve okul numarası geçmez.
          onClick={() => {
            void confirm({
              title: "Bireysel soru dosyası kaldırılsın mı?",
              message:
                "Bu öğrenci için yüklenen PDF silinir; öğrenci dersin soru dosyasından " +
                "basılan kitapçığı alır.",
              confirmLabel: "Kaldır",
            }).then((ok) => ok && kaldir.mutate(doc.id));
          }}
          disabled={kaldir.isPending}
        >
          Seçimi kaldır
        </Button>
      )}

      {uploadOpen && doc !== null && (
        <SoruYuklemeDialog
          title={`Bireysel soru PDF'i — ${yerEtiketi(row)}`}
          initialScoreMode={doc.has_file ? doc.score_mode : undefined}
          initialQuestionCount={doc.has_file ? doc.question_count : undefined}
          pending={yukle.isPending}
          onClose={closeUpload}
          onSubmit={(form) => yukle.mutate({ documentId: doc.id, form })}
        />
      )}
    </li>
  );
}

export default function BireyselSorularBolumu({
  session,
  locked,
}: {
  session: ExamSession;
  /** Oturum DAĞITILDI değilse (onaylı/arşiv) seçim ve dosya değişmez. */
  locked: boolean;
}) {
  const snackbar = useSnackbar();
  const qc = useQueryClient();
  const headingId = useId();
  const [summaryDownloading, setSummaryDownloading] = useState(false);
  const [preview, setPreview] = useState<{ url: string; label: string } | null>(null);

  const rows = useQuery({
    queryKey: ["individual-questions", session.id],
    queryFn: () => individualQuestionApi.list(session.id),
    // Satır salon ve koltuk taşır: Yerleşim sekmesindeki koltuk takasından sonra
    // bu sekmeye dönülünce (panel yeniden kurulur) güncel yer okunur.
    staleTime: 0,
  });
  const satirlar = rows.data?.rows ?? [];

  const tazele = useCallback(() => {
    void qc.invalidateQueries({ queryKey: ["individual-questions", session.id] });
    // Seçim/yükleme/kaldırma üretilmiş kitapçıkları "güncel değil"e çevirebilir.
    void qc.invalidateQueries({ queryKey: ["booklet-runs", session.id] });
  }, [qc, session.id]);

  const openPreview = async (row: IndividualQuestionRow, doc: IndividualDocument) => {
    try {
      const blob = await individualQuestionApi.fileBlob(doc.id);
      setPreview({ url: URL.createObjectURL(blob), label: yerEtiketi(row) });
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Önizleme alınamadı.");
    }
  };
  const closePreview = useCallback(() => {
    setPreview((current) => {
      if (current) URL.revokeObjectURL(current.url);
      return null;
    });
  }, []);

  const downloadSummary = async () => {
    setSummaryDownloading(true);
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
      setSummaryDownloading(false);
    }
  };

  // Liste HİÇ okunamadıysa sessiz kalınmaz: bölüm çizilmezse idareci bu oturumda
  // BEP kapsamında öğrenci olmadığını sanar ve öğrenci dersin kitapçığını alır.
  // (Tazeleme başarısız olduysa eldeki son liste gösterilmeye devam eder.)
  if (rows.isError && rows.data === undefined) {
    return (
      <p role="alert" className="text-body-small text-error">
        {rows.error instanceof ApiError
          ? rows.error.message
          : "BEP kapsamındaki öğrenciler okunamadı."}
      </p>
    );
  }

  // Oturuma giren BEP kapsamında öğrenci yoksa (ya da sorgu sürüyorsa) bölüm HİÇ çizilmez.
  if (satirlar.length === 0) return null;

  return (
    <section
      aria-labelledby={headingId}
      className="flex flex-col gap-3 rounded-shape-md border border-outline-variant p-3"
    >
      <h3 id={headingId} className="text-title-small text-on-surface">
        BEP kapsamındaki öğrenciler — bireysel soru dosyaları
      </h3>
      <p className="text-body-small text-on-surface-variant">
        Seçtiğiniz öğrencinin kitapçığı, dersin soru dosyası yerine buraya yüklediğiniz PDF'ten
        basılır. Kitapçık bandı, ders adı ve dağıtım sırası öteki öğrencilerle aynıdır; salon
        evrakında ve kitapçıkta öğrenciyi ayıran hiçbir işaret yoktur. PDF'in içine öğrencinin adını
        yazmayın; ad kitapçık bandına basılır. Fark edilmemesi için dersin soru dosyasıyla aynı
        sayfa sayısı ve tek puan kutusu önerilir.
      </p>
      <BepParolaUyarisi />

      <ul className="flex flex-col gap-2">
        {satirlar.map((row) => (
          <BireyselSatir
            key={row.student_id}
            row={row}
            sessionId={session.id}
            locked={locked}
            onChanged={tazele}
            onPreview={(r, doc) => void openPreview(r, doc)}
          />
        ))}
      </ul>

      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="outlined"
          icon="picture_as_pdf"
          onClick={() => void downloadSummary()}
          disabled={summaryDownloading}
        >
          İdare özeti (PDF)
        </Button>
        <span className="text-body-small text-on-surface-variant">
          Yalnız idare nüshasıdır; salonlara dağıtılmaz ve “Tümünü indir” paketine girmez.
        </span>
      </div>

      <Dialog
        open={preview !== null}
        onClose={closePreview}
        title={`Önizleme — ${preview?.label ?? ""}`}
        wide
        actions={
          <Button variant="text" onClick={closePreview}>
            Kapat
          </Button>
        }
      >
        {preview && (
          <embed
            src={preview.url}
            type="application/pdf"
            aria-label="Bireysel soru dosyası önizlemesi"
            className="h-[60vh] w-full rounded-shape-sm"
          />
        )}
      </Dialog>
    </section>
  );
}
