// Öğrenci fotoğrafları (19.09.2026) — e-Okul fotoğraflı öğrenci listesi
// (OOG01001R080) Excel ihracından aktarım + sayım + KVKK silme düğmesi.
//
// e-Okul bu raporu SINIF DÜZEYİ başına ayrı verir; her dosya ayrı aktarılır.
// Eşleşme okul numarasıyla (şube öğrenci kaydından). Akış öğrenci aktarımıyla
// aynı: önce "Önizle" (hiçbir şey yazmaz), rapor okunur, sonra "Aktar".
// MÜKERRER YÜKLEME (kullanıcı kararı): aynı fotoğraf sessizce geçilir; kayıtlı
// fotoğrafı yenisinden FARKLI öğrenciler için idareci "koru" ya da "değiştir"
// seçer. Fotoğraflar salon evrakının fotoğraflı oturma planında ve yoklama
// ekranında kullanılır.

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import { formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { PhotoConflictChoice, PhotoImportReport } from "../okul/api";
import { okulApi } from "../okul/api";
import FotograflariSilDugmesi from "./FotograflariSilDugmesi";

export default function FotografPaneli() {
  const snackbar = useSnackbar();
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<PhotoImportReport | null>(null);
  const [secim, setSecim] = useState<PhotoConflictChoice>("keep");
  const [busy, setBusy] = useState<"preview" | "commit" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const stats = useQuery({
    queryKey: ["student-photo-stats"],
    queryFn: () => okulApi.photoStats(),
    retry: false,
  });

  const run = (mode: "preview" | "commit") => {
    if (!file) return;
    setBusy(mode);
    setError(null);
    const istek =
      mode === "preview"
        ? okulApi.previewPhotoImport(file, secim)
        : okulApi.commitPhotoImport(file, secim);
    istek
      .then((r) => {
        setReport(r);
        if (mode === "commit") {
          snackbar.success(
            `${formatNumber(r.created + r.replaced)} fotoğraf aktarıldı` +
              (r.kept ? `; ${formatNumber(r.kept)} öğrencinin mevcut fotoğrafı korundu.` : "."),
          );
          void qc.invalidateQueries({ queryKey: ["student-photo-stats"] });
          void qc.invalidateQueries({ queryKey: ["exam-seating-photos"] });
        }
      })
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Dosya okunamadı."))
      .finally(() => setBusy(null));
  };

  const onizlendi = report?.dry_run === true;
  const aktarildi = report !== null && !report.dry_run;

  return (
    <Card elevation={1} className="flex flex-col gap-3 p-[var(--ks-panel-padding)]">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-title-medium text-on-surface">Öğrenci fotoğrafları</p>
          {stats.data && (
            <p className="text-body-small text-on-surface-variant">
              {formatNumber(stats.data.with_photo)} öğrencinin fotoğrafı var ·{" "}
              {formatNumber(stats.data.without_photo)} öğrencinin yok
            </p>
          )}
        </div>
        <FotograflariSilDugmesi
          disabled={!stats.data?.with_photo}
          onDeleted={() => setReport(null)}
        />
      </div>
      <p className="text-body-small text-on-surface-variant">
        e-Okul'daki <strong>OOG01001R080</strong> fotoğraflı öğrenci listesi raporunu{" "}
        <strong>Excel</strong> olarak indirip olduğu gibi yükleyin. e-Okul bu raporu sınıf düzeyi
        başına verir: her düzeyin dosyasını ayrı ayrı aktarın. Fotoğraflar okul numarasıyla eşleşir
        ve salon evrakındaki fotoğraflı oturma planında ve yoklama ekranında kullanılır. Uygulama
        parolası açıksa şifreli saklanır; ayrılan öğrencinin fotoğrafı silinir.
      </p>
      <label className="flex flex-wrap items-center gap-3 text-body-medium text-on-surface">
        <span className="text-label-large">Rapor dosyası (Excel)</span>
        <input
          type="file"
          accept=".xls,application/vnd.ms-excel"
          aria-label="e-Okul fotoğraflı öğrenci listesi (Excel)"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setReport(null);
            setError(null);
            setSecim("keep");
          }}
        />
      </label>

      {error && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-shape-sm bg-error-container px-3 py-2 text-body-medium text-on-error-container"
        >
          <Icon name="error" size="lg" />
          <span>{error}</span>
        </p>
      )}

      {report && (
        <FotoRaporu report={report} secim={secim} onSecim={onizlendi ? setSecim : undefined} />
      )}

      <div className="flex flex-wrap justify-end gap-2">
        <Button
          variant="tonal"
          icon="visibility"
          onClick={() => run("preview")}
          disabled={!file || busy !== null || aktarildi}
        >
          {busy === "preview" ? "Okunuyor…" : "Fotoğrafları önizle"}
        </Button>
        <Button
          icon="upload"
          onClick={() => run("commit")}
          disabled={!file || !onizlendi || busy !== null}
        >
          {busy === "commit" ? "Aktarılıyor…" : "Fotoğrafları aktar"}
        </Button>
      </div>
    </Card>
  );
}

function FotoRaporu({
  report,
  secim,
  onSecim,
}: {
  report: PhotoImportReport;
  secim: PhotoConflictChoice;
  /** Yalnız önizlemede: mükerrer fotoğraf seçimi. */
  onSecim?: (secim: PhotoConflictChoice) => void;
}) {
  return (
    <div className="flex flex-col gap-2 text-body-small">
      <p className="text-body-medium text-on-surface">
        {report.dry_run ? "Önizleme" : "Aktarım"}
        {report.levels.length > 0 ? ` — ${report.levels.join(", ")}` : ""}
        {report.sections.length > 0 ? ` · ${report.sections.length} şube` : ""} ·{" "}
        {formatNumber(report.total)} fotoğraf: {formatNumber(report.created)} yeni,{" "}
        {formatNumber(report.same)} aynı
        {report.conflicts ? `, ${formatNumber(report.conflicts)} farklı` : ""}
        {report.dry_run ? "" : `, ${formatNumber(report.replaced)} değiştirildi`}.
      </p>
      {report.already_imported && (
        <p className="rounded-shape-sm bg-secondary-container px-3 py-2 text-on-secondary-container">
          Bu dosya daha önce aktarılmış; yeniden aktarım aynı fotoğrafları değiştirmez.
        </p>
      )}
      {report.placeholders > 0 && (
        <p className="text-on-surface-variant">
          {formatNumber(report.placeholders)} öğrencinin e-Okul'da fotoğrafı yok (kayıtlı fotoğrafı
          varsa korunur).
        </p>
      )}
      {report.conflicts > 0 && (
        <fieldset className="flex flex-col gap-1 rounded-shape-sm bg-tertiary-container px-3 py-2 text-on-tertiary-container">
          <legend className="sr-only">Mükerrer fotoğraf seçimi</legend>
          <p>
            <strong>{formatNumber(report.conflicts)} öğrencinin</strong> kayıtlı fotoğrafı bu
            dosyadakinden farklı. Hangisi korunsun?
          </p>
          {onSecim ? (
            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="foto-cakisma"
                  className="h-4 w-4 accent-primary"
                  checked={secim === "keep"}
                  onChange={() => onSecim("keep")}
                />
                Mevcut fotoğrafları koru
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="foto-cakisma"
                  className="h-4 w-4 accent-primary"
                  checked={secim === "replace"}
                  onChange={() => onSecim("replace")}
                />
                Yenileriyle değiştir
              </label>
            </div>
          ) : (
            <p>
              {report.replaced > 0
                ? `${formatNumber(report.replaced)} fotoğraf yenisiyle değiştirildi.`
                : `${formatNumber(report.kept)} öğrencinin mevcut fotoğrafı korundu.`}
            </p>
          )}
          <details>
            <summary className="cursor-pointer">Öğrenciler (okul no · şube)</summary>
            <p className="mt-1">
              {report.conflict_students
                .map((s) => `${s.student_number} · ${s.class_label}`)
                .join(", ")}
              {report.conflicts_truncated > 0
                ? ` … ve ${report.conflicts_truncated} öğrenci daha`
                : ""}
            </p>
          </details>
        </fieldset>
      )}
      {report.missing_in_levels > 0 && (
        <p className="text-on-surface-variant">
          Bu sınıf düzeylerinde aktarımdan sonra {formatNumber(report.missing_in_levels)} öğrencinin
          fotoğrafı yok.
        </p>
      )}
      {report.skipped.length > 0 && (
        <details className="rounded-shape-sm border border-outline-variant px-3 py-2">
          <summary className="cursor-pointer text-label-large text-on-surface">
            Aktarılmayan satırlar ({report.skipped.length + report.skipped_truncated})
          </summary>
          <table className="mt-2 w-full text-left">
            <thead>
              <tr className="text-label-medium text-on-surface-variant">
                <th className="py-1 pr-3">Konum</th>
                <th className="py-1 pr-3">Okul no</th>
                <th className="py-1">Sorun</th>
              </tr>
            </thead>
            <tbody>
              {report.skipped.map((s, i) => (
                <tr key={`${s.location}-${i}`}>
                  <td className="py-1 pr-3 text-on-surface-variant">{s.location}</td>
                  <td className="py-1 pr-3">{s.value || "—"}</td>
                  <td className="py-1">{s.issue}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {report.skipped_truncated > 0 && (
            <p className="mt-1 text-on-surface-variant">
              … ve {report.skipped_truncated} satır daha (liste kısaltıldı).
            </p>
          )}
        </details>
      )}
    </div>
  );
}
