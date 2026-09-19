// e-Okul "Seçmeli Ders Öğrencileri" (OOK10002R010) PDF aktarımı (19.09.2026).
//
// e-Okul yolu: Öğrenci Seçmeli Derslerini Belirle ekranı → Raporlar → OOK10002R010 -
// Seçmeli Ders Öğrencileri → PDF. Aynı raporun Excel ihracı ders adlarını
// DÜŞÜRDÜĞÜ için yalnız PDF kabul edilir (backend `dersler.enrollment_import`).
//
// Akış öğrenci içe aktarmasıyla aynı: önce "Önizle" (hiçbir şey yazmaz), rapor
// incelenir, sonra "Aktar". Raporun KAPSADIĞI şubelerde (raporda satırı geçen)
// her dersin o yılki öğrenci listesi ve şube kapsamı yenilenir; raporda olmayan
// derslere ve şubelere dokunulmaz — rapor tek düzey/şube için alınmış olabilir.

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import { gradeLevelLabel } from "../../lib/gradeLevels";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { ElectiveImportIssue, ElectiveImportReport } from "./api";
import { derslerApi } from "./api";

export default function SecmeliOgrenciAktarDialog({
  onClose,
  onImported,
}: {
  onClose: () => void;
  onImported: () => void;
}) {
  const snackbar = useSnackbar();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ElectiveImportReport | null>(null);
  const [busy, setBusy] = useState<"preview" | "commit" | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Havuzda karşılığı olmayan ve "Havuza ekle" işaretli e-Okul başlıkları
  // (19.09.2026, kullanıcı kararı: yeni seçmeli onayla eklenir). Önizleme her
  // eklenebilir başlığı İŞARETLİ getirir; idareci kutuyu kaldırabilir.
  const [eklenecek, setEklenecek] = useState<Set<string>>(new Set());

  const run = (mode: "preview" | "commit") => {
    if (!file) return;
    setBusy(mode);
    setError(null);
    const istek =
      mode === "preview"
        ? derslerApi.previewEnrollmentImport(file)
        : derslerApi.commitEnrollmentImport(file, [...eklenecek]);
    istek
      .then((r) => {
        setReport(r);
        if (mode === "preview") {
          setEklenecek(new Set(r.courses.filter((c) => c.addable).map((c) => c.title)));
        } else {
          const dersler = r.courses.filter((c) => c.status === "matched").length;
          snackbar.success(
            `${dersler} dersin öğrenci listesi aktarıldı (${r.processed} öğrenci-ders kaydı).`,
          );
          for (const key of [
            ["course-enrollments"],
            ["course-enrollment-counts"],
            ["course-section-offerings"],
            ["course-sections"],
            ["courses"],
          ]) {
            void queryClient.invalidateQueries({ queryKey: key });
          }
          onImported();
        }
      })
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Rapor okunamadı."))
      .finally(() => setBusy(null));
  };

  const onizlendi = report?.dry_run === true;
  const aktarildi = report !== null && !report.dry_run;

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title="e-Okul'dan seçmeli ders öğrencilerini aktar"
      actions={
        <>
          <Button variant="text" onClick={onClose} disabled={busy !== null}>
            {aktarildi ? "Kapat" : "Vazgeç"}
          </Button>
          <Button
            variant="tonal"
            icon="visibility"
            onClick={() => run("preview")}
            disabled={!file || busy !== null || aktarildi}
          >
            {busy === "preview" ? "Okunuyor…" : "Önizle"}
          </Button>
          <Button
            icon="upload"
            onClick={() => run("commit")}
            disabled={!file || !onizlendi || busy !== null}
          >
            {busy === "commit" ? "Aktarılıyor…" : "Aktar"}
          </Button>
        </>
      }
    >
      <p className="mb-3 text-body-small text-on-surface-variant">
        e-Okul'da <strong>Öğrenci Seçmeli Derslerini Belirle</strong> ekranının{" "}
        <strong>Raporlar</strong> menüsünden{" "}
        <strong>OOK10002R010 - Seçmeli Ders Öğrencileri</strong> raporunu <strong>PDF</strong>{" "}
        olarak kaydedin (Excel ihracı ders adlarını içermez). Raporun kapsadığı şubelerde her dersin
        bu yılki öğrenci listesi ve şubeleri yenilenir; raporda olmayan derslere ve şubelere
        dokunulmaz. Öğrenciler okul numarasıyla eşleşir — önce öğrenci listesini güncel tutun.
      </p>
      <label className="flex flex-wrap items-center gap-3 text-body-medium text-on-surface">
        <span className="text-label-large">Rapor dosyası (PDF)</span>
        <input
          type="file"
          accept=".pdf,application/pdf"
          aria-label="e-Okul OOK10002R010 raporu (PDF)"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setReport(null);
            setError(null);
          }}
        />
      </label>

      {error && (
        <p
          role="alert"
          className="mt-3 flex items-start gap-2 rounded-shape-sm bg-error-container px-3 py-2 text-body-medium text-on-error-container"
        >
          <Icon name="error" size="lg" />
          <span>{error}</span>
        </p>
      )}

      {report && (
        <RaporGorunumu
          report={report}
          eklenecek={eklenecek}
          onToggle={
            onizlendi
              ? (title) =>
                  setEklenecek((prev) => {
                    const yeni = new Set(prev);
                    if (yeni.has(title)) yeni.delete(title);
                    else yeni.add(title);
                    return yeni;
                  })
              : undefined
          }
        />
      )}
    </Dialog>
  );
}

function RaporGorunumu({
  report,
  eklenecek,
  onToggle,
}: {
  report: ElectiveImportReport;
  eklenecek: Set<string>;
  /** Yalnız önizlemede: "Havuza ekle" kutusu. */
  onToggle?: (title: string) => void;
}) {
  const eslesmeyen = report.courses.filter((c) => c.status === "unmatched");
  const eklenecekler = onToggle
    ? eslesmeyen.filter((c) => c.addable && eklenecek.has(c.title))
    : [];
  const aktarilmayacak = eslesmeyen.length - eklenecekler.length;
  return (
    <div className="mt-4 space-y-3">
      <p className="text-body-medium text-on-surface">
        {report.dry_run ? "Önizleme" : "Aktarım"} — {report.school_year} ders yılı · {report.pages}{" "}
        sayfa · {report.total_rows} satır · {report.processed} öğrenci-ders kaydı
        {report.dry_run ? " yazılacak" : " yazıldı"}.
      </p>
      {report.covered_section_count > 0 && (
        <p className="text-body-small text-on-surface-variant">
          Rapor {report.covered_levels.join(", ")}{" "}
          {report.covered_levels.length > 1 ? "düzeylerinden" : "düzeyinden"}{" "}
          {report.covered_section_count} şubeyi kapsıyor; listeler yalnız bu şubelerde yenilenir,
          öbür şubelere dokunulmaz.
        </p>
      )}
      {report.already_imported && (
        <p className="rounded-shape-sm bg-secondary-container px-3 py-2 text-body-small text-on-secondary-container">
          Bu dosya daha önce aktarılmış; yeniden aktarım listeleri aynı içerikle yeniler.
        </p>
      )}
      {eklenecekler.length > 0 && (
        <p className="flex items-start gap-2 rounded-shape-sm bg-secondary-container px-3 py-2 text-body-small text-on-secondary-container">
          <Icon name="add_circle" size="sm" />
          <span>
            {eklenecekler.length} seçmeli Ders Havuzu'nda yok; aktarımda seçmeli ders olarak havuza
            eklenecek (aşağıda işaretli — istemediğinizin işaretini kaldırın).
          </span>
        </p>
      )}
      {aktarilmayacak > 0 && (
        <p className="flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-3 py-2 text-body-small text-on-tertiary-container">
          <Icon name="warning" size="sm" />
          <span>
            {aktarilmayacak} ders Ders Havuzu'nda eşleşmedi ve aktarılmayacak — aşağıdaki tabloda
            gerekçesi var.
          </span>
        </p>
      )}
      <div className="max-h-72 overflow-auto rounded-shape-sm border border-outline-variant">
        <table className="w-full text-left text-body-small">
          <thead>
            <tr className="border-b border-outline-variant text-label-medium text-on-surface-variant">
              <th className="px-3 py-2">e-Okul'daki ad</th>
              <th className="px-3 py-2">Ders Havuzu'ndaki ders</th>
              <th className="px-3 py-2 text-right">Öğrenci</th>
              <th className="px-3 py-2">Şubeler</th>
            </tr>
          </thead>
          <tbody>
            {report.courses.map((c) => (
              <tr key={c.title} className="border-b border-outline-variant/50 last:border-b-0">
                <td className="px-3 py-2 text-on-surface-variant">{c.title}</td>
                <td className="px-3 py-2">
                  {c.status === "matched" ? (
                    <span className="text-on-surface">{c.course_name}</span>
                  ) : (
                    <span className="text-error">Eşleşmedi</span>
                  )}
                  {c.note && (
                    <span className="block text-label-small text-on-surface-variant">{c.note}</span>
                  )}
                  {onToggle && c.status === "unmatched" && c.addable && (
                    <label className="mt-1 flex items-center gap-2 text-on-surface">
                      <input
                        type="checkbox"
                        className="h-4 w-4 accent-primary"
                        checked={eklenecek.has(c.title)}
                        onChange={() => onToggle(c.title)}
                        aria-label={`${c.proposed_name} dersini Ders Havuzu'na ekle`}
                      />
                      <span>
                        Havuza ekle: <strong>{c.proposed_name}</strong>
                        {c.proposed_levels.length > 0
                          ? ` (${c.proposed_levels.map((l) => gradeLevelLabel(l)).join(", ")})`
                          : ""}
                      </span>
                    </label>
                  )}
                </td>
                <td className="px-3 py-2 text-right">
                  {c.status === "matched" ? c.students : c.report_rows}
                </td>
                <td className="px-3 py-2 text-on-surface-variant">{c.sections.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {report.untouched_courses.length > 0 && (
        <p className="text-body-small text-on-surface-variant">
          Bu raporda olmadığı için listesine dokunulmayan dersler:{" "}
          {report.untouched_courses.join(", ")}.
        </p>
      )}
      <SorunTablosu
        baslik="Uyarılar"
        satirlar={report.warnings}
        kesilen={report.warnings_truncated}
      />
      <SorunTablosu
        baslik="Aktarılmayan satırlar"
        satirlar={report.skipped}
        kesilen={report.skipped_truncated}
      />
    </div>
  );
}

function SorunTablosu({
  baslik,
  satirlar,
  kesilen,
}: {
  baslik: string;
  satirlar: ElectiveImportIssue[];
  kesilen: number;
}) {
  if (satirlar.length === 0) return null;
  return (
    <details className="rounded-shape-sm border border-outline-variant px-3 py-2">
      <summary className="cursor-pointer text-label-large text-on-surface">
        {baslik} ({satirlar.length + kesilen})
      </summary>
      <table className="mt-2 w-full text-left text-body-small">
        <thead>
          <tr className="text-label-medium text-on-surface-variant">
            <th className="py-1 pr-3">Sayfa / satır</th>
            <th className="py-1 pr-3">Okul no</th>
            <th className="py-1">Sorun</th>
          </tr>
        </thead>
        <tbody>
          {satirlar.map((s, i) => (
            <tr key={`${s.page}-${s.line}-${i}`}>
              <td className="py-1 pr-3 text-on-surface-variant">
                {s.page > 0 ? `${s.page} / ${s.line}` : "—"}
              </td>
              <td className="py-1 pr-3">{s.value || "—"}</td>
              <td className="py-1">{s.issue}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {kesilen > 0 && (
        <p className="mt-1 text-body-small text-on-surface-variant">
          … ve {kesilen} satır daha (liste kısaltıldı).
        </p>
      )}
    </details>
  );
}
