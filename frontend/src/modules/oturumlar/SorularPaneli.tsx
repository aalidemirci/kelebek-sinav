// Sorular ve Kitapçıklar paneli (F5) — OYS SorularPaneli'nden UYARLA: ders
// bazlı soru PDF'i yükleme (K5 puan bölümü), indirme + önizleme (blob URL),
// Word şablonu indirme ve R10 kitapçık üretimi. KS'de üretim SENKRONDUR
// (Celery yok): "Kitapçıkları üret" tek istekte tamamlanmış koşu döner —
// OYS'deki 4 sn'lik koşu polling'i kalktı. Soru dosyaları sınav öncesi
// gizlilik sınıfındadır; dosyalar yalnız yerel API'den (X-KS-Token) sunulur.
// Bant sabit 4 cm üst alana basılır (ölçekleme yok — OYS Tur 236).

import { useCallback, useMemo, useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import { dosyaAdi, saveBlob } from "../../lib/download";
import { formatDate, formatDateTime } from "../../lib/format";
import Button from "../../ui/Button";
import { useConfirm } from "../../ui/ConfirmProvider";
import Dialog from "../../ui/Dialog";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import TextField from "../../ui/TextField";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { ExamSession, ExamSessionCourseRow, ScoreModeCode } from "./api";
import { BOOKLETS_ZIP_FILE_TITLE, examSessionApi } from "./api";

/**
 * Soru dosyası satırı: olağan durumda bir oturum dersi satırı; "aynı kitapçık"
 * (shared_booklet) dersinde ise dersin TÜM seviye satırları tek gruptur —
 * backend o gruba tek dosya kabul eder (`upload_question_document`), panel de
 * tek satır gösterir. Eskiden satır başına "Yükle" çıkıyor, ikinci yükleme
 * "tek satıra yüklenir" hatasıyla dönüyordu (18.09.2026 TDE 9/10 vakası).
 */
interface QuestionGroup {
  key: string;
  label: string;
  rows: ExamSessionCourseRow[];
  shared: boolean;
}

/** "9. ve 10. Sınıf" / "9., 10. ve 11. Sınıf" / "Hazırlık ve 9. Sınıf". */
function levelsPhrase(levels: (number | null)[]): string {
  const parts = levels.map((lv) => (lv === null ? "—" : lv === 0 ? "Hazırlık" : `${lv}.`));
  const joined =
    parts.length > 1
      ? `${parts.slice(0, -1).join(", ")} ve ${parts[parts.length - 1]}`
      : (parts[0] ?? "");
  return levels.some((lv) => lv !== null && lv !== 0) ? `${joined} Sınıf` : joined;
}

export function groupQuestionRows(courses: ExamSessionCourseRow[]): QuestionGroup[] {
  const groups: QuestionGroup[] = [];
  const sharedByCourse = new Map<number, QuestionGroup>();
  for (const row of courses) {
    if (!row.shared_booklet) {
      groups.push({ key: `sc:${row.id}`, label: row.display_label, rows: [row], shared: false });
      continue;
    }
    const existing = sharedByCourse.get(row.course_id);
    if (existing) {
      existing.rows.push(row);
      continue;
    }
    const group: QuestionGroup = {
      key: `course:${row.course_id}`,
      label: "",
      rows: [row],
      shared: true,
    };
    sharedByCourse.set(row.course_id, group);
    groups.push(group);
  }
  for (const group of sharedByCourse.values()) {
    const levels = [...group.rows].sort((a, b) => (a.level ?? 0) - (b.level ?? 0));
    group.label = `${group.rows[0].course_name} — ${levelsPhrase(levels.map((r) => r.level))} (aynı kitapçık)`;
  }
  return groups;
}

function CourseQuestionRow({ group, locked }: { group: QuestionGroup; locked: boolean }) {
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const qc = useQueryClient();
  const [uploadOpen, setUploadOpen] = useState(false);
  const closeUpload = useCallback(() => setUploadOpen(false), []);
  const [file, setFile] = useState<File | null>(null);
  const [scoreMode, setScoreMode] = useState<ScoreModeCode>("SINGLE_BOX");
  const [questionCount, setQuestionCount] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  // Grubun her satırı sorgulanır; dosya hangi satırdaysa o satır "taşıyıcı"dır
  // (aynı kitapçıkta dosya kardeşlerden yalnız birinde durur). Dosya yoksa
  // yükleme ilk satıra gider.
  const questions = useQueries({
    queries: group.rows.map((row) => ({
      queryKey: ["exam-question", row.id],
      queryFn: () => examSessionApi.question(row.id),
      retry: false, // 404 = yüklenmemiş (olağan durum)
    })),
  });
  const carrierIndex = questions.findIndex((q) => q.data !== undefined);
  const meta = carrierIndex >= 0 ? questions[carrierIndex].data : undefined;
  const carrier = carrierIndex >= 0 ? group.rows[carrierIndex] : group.rows[0];
  const invalidateGroup = () => {
    for (const row of group.rows) {
      void qc.invalidateQueries({ queryKey: ["exam-question", row.id] });
    }
  };

  const upload = useMutation({
    mutationFn: () => {
      const form = new FormData();
      if (file) form.append("file", file);
      form.append("score_mode", scoreMode);
      if (scoreMode === "QUESTION_TABLE" && questionCount) {
        form.append("question_count", questionCount);
      }
      return examSessionApi.uploadQuestion(carrier.id, form);
    },
    onSuccess: () => {
      setUploadOpen(false);
      setFile(null);
      snackbar.success("Soru dosyası yüklendi.");
      invalidateGroup();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Yükleme başarısız."),
  });

  const remove = useMutation({
    mutationFn: () => examSessionApi.deleteQuestion(carrier.id),
    onSuccess: () => {
      snackbar.success("Soru dosyası kaldırıldı.");
      invalidateGroup();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Kaldırılamadı."),
  });

  const openPreview = async () => {
    try {
      const blob = await examSessionApi.questionBlob(carrier.id);
      setPreviewUrl(URL.createObjectURL(blob));
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Önizleme alınamadı.");
    }
  };
  const closePreview = useCallback(() => {
    setPreviewUrl((url) => {
      if (url) URL.revokeObjectURL(url);
      return null;
    });
  }, []);

  return (
    <li className="flex flex-wrap items-center gap-3 rounded-shape-md border border-outline-variant p-3">
      <span className="text-title-small text-on-surface">{group.label}</span>
      {group.shared && (
        <span className="text-body-small text-on-surface-variant">
          tek dosya — bu sınıf düzeylerinin tümü aynı kitapçığı alır
        </span>
      )}
      {meta ? (
        <span className="text-body-small text-on-surface-variant">
          {meta.page_count} sayfa ·{" "}
          {meta.score_mode === "SINGLE_BOX"
            ? "tek puan kutusu"
            : `${meta.question_count ?? "?"} soruluk puan tablosu`}
        </span>
      ) : (
        <span className="text-body-small text-error">Soru dosyası yüklenmedi</span>
      )}
      <span className="ml-auto" />
      {meta && (
        <>
          <Button variant="text" icon="visibility" onClick={() => void openPreview()}>
            Önizle
          </Button>
          {!locked && (
            <Button
              variant="text"
              icon="delete"
              // Yüklü dosya diskten de silinir (geri alınamaz) → onaydan geçer.
              onClick={() => {
                void confirm({
                  title: "Soru dosyası kaldırılsın mı?",
                  message: `${group.label} için yüklenen soru PDF'i silinir. Kitapçık üretebilmek için dosyayı yeniden yüklemeniz gerekir.`,
                  confirmLabel: "Kaldır",
                }).then((ok) => ok && remove.mutate());
              }}
              disabled={remove.isPending}
            >
              Kaldır
            </Button>
          )}
        </>
      )}
      {!locked && (
        <Button variant="tonal" icon="upload_file" onClick={() => setUploadOpen(true)}>
          {meta ? "Değiştir" : "Yükle"}
        </Button>
      )}

      <Dialog
        open={uploadOpen}
        onClose={closeUpload}
        title={`Soru PDF'i — ${group.label}`}
        actions={
          <>
            <Button variant="text" onClick={closeUpload}>
              Vazgeç
            </Button>
            <Button onClick={() => upload.mutate()} disabled={upload.isPending || !file}>
              {upload.isPending ? "Yükleniyor…" : "Yükle"}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-label-large text-on-surface-variant">
            Soru PDF dosyası
            <input
              type="file"
              accept="application/pdf"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="min-h-9 rounded-shape-xs border border-outline bg-surface px-3 py-1.5 text-body-medium text-on-surface file:mr-3 file:rounded-shape-sm file:border-0 file:bg-secondary-container file:px-3 file:py-1 file:text-label-large file:text-on-secondary-container"
            />
          </label>
          <Select
            label="Puan bölümü"
            options={[
              { value: "SINGLE_BOX", label: "Tek puan kutusu" },
              { value: "QUESTION_TABLE", label: "Soru bazlı puan tablosu" },
            ]}
            value={scoreMode}
            onChange={(e) => setScoreMode(e.target.value as ScoreModeCode)}
          />
          {scoreMode === "QUESTION_TABLE" && (
            <TextField
              label="Soru sayısı"
              type="number"
              min={1}
              max={60}
              value={questionCount}
              onChange={(e) => setQuestionCount(e.target.value)}
              required
            />
          )}
        </div>
      </Dialog>

      <Dialog
        open={previewUrl !== null}
        onClose={closePreview}
        title={`Önizleme — ${group.label}`}
        wide
        actions={
          <Button variant="text" onClick={closePreview}>
            Kapat
          </Button>
        }
      >
        {previewUrl && (
          <embed
            src={previewUrl}
            type="application/pdf"
            aria-label={`${group.label} soru dosyası önizlemesi`}
            className="h-[60vh] w-full rounded-shape-sm"
          />
        )}
      </Dialog>
    </li>
  );
}

const RUN_LABELS: Record<string, string> = {
  PENDING: "Bekliyor",
  IN_PROGRESS: "Üretiliyor",
  COMPLETED: "Tamamlandı",
  FAILED: "Başarısız",
};

export default function SorularPaneli({ session }: { session: ExamSession }) {
  const snackbar = useSnackbar();
  const qc = useQueryClient();
  const [backupCopies, setBackupCopies] = useState("0");
  const [templateDownloading, setTemplateDownloading] = useState(false);
  const locked = session.status !== "DISTRIBUTED"; // onaylı/arşivde dosya değişmez (T9 kilidi)
  const groups = useMemo(() => groupQuestionRows(session.courses), [session.courses]);

  const downloadTemplate = async () => {
    setTemplateDownloading(true);
    try {
      const blob = await examSessionApi.questionTemplateBlob();
      // Şablon oturuma özgü değildir → adında oturum/tarih yok.
      saveBlob(blob, dosyaAdi(["Soru Şablonu"], "docx"));
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Şablon indirilemedi.");
    } finally {
      setTemplateDownloading(false);
    }
  };

  // Senkron üretimde polling yok — liste yalnız üretim sonrası tazelenir.
  const runs = useQuery({
    queryKey: ["booklet-runs", session.id],
    queryFn: () => examSessionApi.bookletRuns(session.id),
  });

  const start = useMutation({
    mutationFn: () => examSessionApi.startBookletRun(session.id, Number(backupCopies) || 0),
    onSuccess: (run) => {
      if (run.status === "FAILED") {
        snackbar.error(
          `Kitapçık üretimi başarısız${run.error_message ? ` — ${run.error_message}` : "."}`,
        );
      } else {
        snackbar.success("Kitapçıklar üretildi.");
      }
      void qc.invalidateQueries({ queryKey: ["booklet-runs", session.id] });
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Üretim başlatılamadı."),
  });

  const downloadRun = async (runId: number) => {
    try {
      const blob = await examSessionApi.bookletRunZipBlob(runId);
      // Belge adı + oturum adı + tarih (docs/sozluk.md §3) — eski
      // `kitapciklar_oturum_12.zip` hangi sınava ait olduğunu söylemiyordu.
      saveBlob(
        blob,
        dosyaAdi([BOOKLETS_ZIP_FILE_TITLE, session.name, formatDate(session.exam_date)], "zip"),
      );
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "İndirilemedi.");
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {locked && (
        <p className="text-body-small text-on-surface-variant">
          Oturum {session.status === "APPROVED" ? "onaylı" : "arşivde"} — soru dosyaları
          değiştirilemez; kitapçık yeniden basılabilir.
        </p>
      )}
      {/* Şablon kuralları kartı — word_template._GUIDE_PARAGRAPHS ile AYNI
          6 madde (iki liste birlikte güncellenir — OYS Tur 646 sözleşmesi). */}
      <div className="rounded-shape-md bg-surface-container p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-title-small text-on-surface">Şablon Kuralları</h3>
          <span className="ml-auto" />
          <Button
            variant="text"
            icon="download"
            onClick={() => void downloadTemplate()}
            disabled={templateDownloading}
            aria-label="Word şablonunu indir"
          >
            Word şablonunu indir (üst boşluk 4 cm)
          </Button>
        </div>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-body-small text-on-surface-variant">
          <li>
            Sayfa A4 <span className="font-medium text-on-surface">dikey</span> kalır; üst kenar
            boşluğuna (4 cm) dokunmayın — yatay sayfa içeren PDF reddedilir.
          </li>
          <li>
            Yazı tipi Times New Roman / Arial / Calibri, PDF'e gömülü; gövde ≥ 11 punto, şıklar ≥ 10
            punto.
          </li>
          <li>Görseller ≥ 300 dpi ve salt siyah-beyaz — açık gri tonlar fotokopide kaybolur.</li>
          <li>Sayfa numarası eklemeyin; “Sayfa x / y” basım sırasında sistemce basılır.</li>
          <li>Yalnız PDF yüklenir (≤ 20 MB, tüm sayfalar A4 dikey).</li>
          <li>Yazmaya başlamadan önce şablondaki yönerge paragraflarını silin.</li>
        </ol>
      </div>
      <ul className="flex flex-col gap-2">
        {groups.map((group) => (
          <CourseQuestionRow key={group.key} group={group} locked={locked} />
        ))}
      </ul>

      <div className="flex flex-wrap items-end gap-3 rounded-shape-md border border-outline-variant p-3">
        <h3 className="w-full text-title-small text-on-surface">Kişiselleştirilmiş kitapçıklar</h3>
        <TextField
          label="Her salon için isimsiz yedek kitapçık sayısı"
          type="number"
          min={0}
          max={10}
          value={backupCopies}
          onChange={(e) => setBackupCopies(e.target.value)}
          className="w-80 max-w-full"
        />
        <Button icon="print" onClick={() => start.mutate()} disabled={start.isPending}>
          {start.isPending ? "Üretiliyor…" : "Kitapçıkları üret"}
        </Button>
        <ul className="w-full text-body-medium text-on-surface">
          {(runs.data?.results ?? []).map((run) => (
            <li
              key={run.id}
              className="flex items-center gap-3 border-b border-outline-variant py-1"
            >
              {/* Kayıt kimliği (#41) idareciye bir şey söylemez; ne zaman üretildiği söyler. */}
              <span>Üretim · {formatDateTime(run.created_at)}</span>
              <span className="text-body-small text-on-surface-variant">
                {RUN_LABELS[run.status] ?? run.status}
                {run.error_message && ` — ${run.error_message}`}
              </span>
              {/* Kitapçık salon/koltuk/ad taşır: yerleşim sonradan değiştiyse bu ZIP
                  basılırsa kitapçıklar yanlış koltuğa gider. */}
              {run.is_stale && (
                <span className="flex items-center gap-1 rounded-shape-sm bg-error-container px-2 py-0.5 text-body-small text-on-error-container">
                  <Icon name="warning" size="sm" />
                  Eski yerleşime göre — yeniden üretin
                </span>
              )}
              <span className="ml-auto" />
              {run.status === "COMPLETED" && (
                <Button variant="text" icon="download" onClick={() => void downloadRun(run.id)}>
                  ZIP indir
                </Button>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
