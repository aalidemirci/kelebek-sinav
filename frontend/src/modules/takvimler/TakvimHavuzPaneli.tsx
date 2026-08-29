// Sınav Takvimi — Havuz paneli (F6) — OYS TakvimHavuzPaneli'nden UYARLA.
// Havuz "Katalogdan Doldur" ile otomatik dolar (KS sapması B6/B8: program
// verisi yok — kaynak aktif ders kataloğu × öğrencisi olan seviyeler); elle
// ekleme formu kenar durumlar için kalır. Katılımcı sayısı/kapsam dipnotu
// önizleme. Yalnız taslakta düzenlenebilir; round 3 havuzu ELLE doldurulur.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import { gradeLevelLabel } from "../../lib/gradeLevels";
import Autocomplete from "../../ui/Autocomplete";
import Button from "../../ui/Button";
import DataTable from "../../ui/DataTable";
import EmptyState from "../../ui/EmptyState";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useConfirm } from "../../ui/ConfirmProvider";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { Course } from "../dersler/api";
import { derslerApi } from "../dersler/api";
import type { ExamCalendarEntryRow, ExamKindCode } from "./api";
import { examCalendarApi } from "./api";

export default function TakvimHavuzPaneli({
  calendarId,
  round,
  editable,
  onChanged,
}: {
  calendarId: number;
  round: number;
  editable: boolean;
  onChanged: () => void;
}) {
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [course, setCourse] = useState<Course | null>(null);
  const [level, setLevel] = useState("9");
  const [kind, setKind] = useState<ExamKindCode>("WRITTEN");
  const [butterfly, setButterfly] = useState(true);

  const entriesQuery = useQuery({
    queryKey: ["exam-calendar-entries", calendarId],
    queryFn: () => examCalendarApi.entries(calendarId),
  });
  const previewQuery = useQuery({
    queryKey: ["exam-calendar-preview", calendarId],
    queryFn: () => examCalendarApi.participantPreview(calendarId),
  });
  // Seviye seçenekleri ızgaranın dinamik seviye listesinden (Hazırlık opt-in
  // okulda 0 dahil). Aynı queryKey Yerleştirme paneliyle paylaşılır.
  const gridQuery = useQuery({
    queryKey: ["exam-calendar-grid", calendarId],
    queryFn: () => examCalendarApi.grid(calendarId),
    enabled: editable,
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["exam-calendar-entries", calendarId] });
    void queryClient.invalidateQueries({ queryKey: ["exam-calendar-preview", calendarId] });
    onChanged();
  };

  const addMutation = useMutation({
    mutationFn: () =>
      examCalendarApi.addEntry(calendarId, {
        course: (course as Course).id,
        level: Number(level),
        exam_kind: kind,
        is_butterfly: butterfly,
      }),
    onSuccess: () => {
      snackbar.success("Ders havuza eklendi.");
      setCourse(null);
      invalidate();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Ders eklenemedi."),
  });

  const removeMutation = useMutation({
    mutationFn: (entryId: number) => examCalendarApi.removeEntry(entryId),
    onSuccess: invalidate,
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Kaldırılamadı."),
  });

  // Havuzu katalogdan doldur — idempotent (var olan atlanır); skipped sessiz
  // düşmez, uyarıyla raporlanır.
  const fillMutation = useMutation({
    mutationFn: () => examCalendarApi.fillPool(calendarId),
    onSuccess: (result) => {
      const base = `${result.created.length} ders eklendi, ${result.existed.length} zaten vardı.`;
      if (result.skipped.length > 0) {
        // Tek birleşik mesaj (snackbar kuyruklu — iki mesaj sırayla beklerdi).
        snackbar.error(
          `${base} ${result.skipped.length} ders atlandı: ${result.skipped
            .slice(0, 3)
            .join("; ")}${result.skipped.length > 3 ? "…" : ""}`,
        );
      } else {
        snackbar.success(base);
      }
      invalidate();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Havuz doldurulamadı."),
  });

  const canFill = editable && round !== 3;
  const handleFill = () => {
    void confirm({
      title: "Havuzu katalogdan doldur",
      message:
        "Aktif ders kataloğundaki dersler, öğrencisi olan seviyeler bazında havuza " +
        "eklenecek; var olan girdiler atlanır. Tür varsayılanı Yazılı — gerekirse " +
        "taslakta düzenleyin.",
      confirmLabel: "Doldur",
    }).then((ok) => ok && fillMutation.mutate());
  };

  const searchCourses = (q: string): Promise<Course[]> => derslerApi.listCourses({ q });

  const entries = entriesQuery.data?.results ?? [];
  const preview = previewQuery.data ?? {};

  return (
    <div>
      {canFill ? (
        <div className="mb-3 flex justify-end">
          <Button
            variant="tonal"
            icon="auto_awesome"
            disabled={fillMutation.isPending}
            onClick={handleFill}
          >
            Katalogdan Doldur
          </Button>
        </div>
      ) : null}
      {editable ? (
        <div className="mb-4 flex flex-wrap items-end gap-3 rounded-shape-lg bg-surface-container p-4">
          <div className="min-w-56 grow">
            <Autocomplete<Course>
              label="Ders"
              placeholder="Ders ara…"
              selected={course}
              search={searchCourses}
              onSelect={setCourse}
              onClear={() => setCourse(null)}
              getLabel={(c) => c.name}
              getKey={(c) => c.id}
            />
          </div>
          <div className="w-36">
            <Select
              label="Seviye"
              options={
                gridQuery.data?.levels.map((l) => ({
                  value: String(l.value),
                  label: l.display_label,
                })) ?? [9, 10, 11, 12].map((l) => ({ value: String(l), label: gradeLevelLabel(l) }))
              }
              value={level}
              onChange={(e) => setLevel(e.target.value)}
            />
          </div>
          <div className="w-36">
            <Select
              label="Tür"
              options={[
                { value: "WRITTEN", label: "Yazılı" },
                { value: "PRACTICE", label: "Uygulama" },
              ]}
              value={kind}
              onChange={(e) => setKind(e.target.value as ExamKindCode)}
            />
          </div>
          <label className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
            <input
              type="checkbox"
              className="h-5 w-5 accent-primary"
              checked={!butterfly}
              onChange={(e) => setButterfly(!e.target.checked)}
            />
            Kelebek değil
          </label>
          <Button
            icon="add"
            disabled={!course || addMutation.isPending}
            onClick={() => addMutation.mutate()}
          >
            Havuza ekle
          </Button>
        </div>
      ) : null}

      {entriesQuery.isPending ? (
        <SkeletonList rows={4} />
      ) : entriesQuery.isError ? (
        // Hata durumu "Havuz boş" gibi sunulmaz — mesaj gösterilir.
        <p role="alert" className="text-body-medium text-error">
          Havuz listesi yüklenemedi:{" "}
          {entriesQuery.error instanceof ApiError
            ? entriesQuery.error.message
            : "beklenmeyen hata."}
        </p>
      ) : entries.length === 0 ? (
        <EmptyState
          icon="playlist_add"
          title="Havuz boş"
          description={
            canFill
              ? "Katalogdaki dersleri tek tıkla çekin veya yukarıdan elle ekleyin."
              : editable
                ? "Yukarıdan ders ekleyin."
                : "Bu takvime ders eklenmemiş."
          }
          action={
            canFill ? (
              <Button icon="auto_awesome" disabled={fillMutation.isPending} onClick={handleFill}>
                Katalogdan Doldur
              </Button>
            ) : undefined
          }
        />
      ) : (
        <DataTable
          rows={entries}
          columns={[
            {
              header: "Ders",
              cell: (e: ExamCalendarEntryRow) => (
                <span>
                  {e.course_name}
                  {e.exam_kind === "PRACTICE" ? " [Uygulama]" : ""}
                  {!e.is_butterfly ? (
                    <span className="ml-2 rounded-full bg-surface-container-high px-2 py-0.5 text-label-small text-on-surface-variant">
                      Kelebek değil
                    </span>
                  ) : null}
                </span>
              ),
            },
            { header: "Seviye", cell: (e) => gradeLevelLabel(e.level) },
            {
              header: "Katılımcı",
              cell: (e) => {
                const p = preview[String(e.id)];
                if (!p) return "—";
                const foot = p.whole ? "" : ` (${p.groups.join(", ")})`;
                return `${p.student_count}${foot}`;
              },
            },
            {
              header: "Durum",
              cell: (e) =>
                e.placed_date ? (
                  <span className="inline-flex items-center gap-1 text-primary">
                    <Icon name="event_available" size="sm" /> Yerleştirildi
                  </span>
                ) : (
                  <span className="text-on-surface-variant">Havuzda</span>
                ),
            },
            ...(editable
              ? [
                  {
                    header: "",
                    align: "right" as const,
                    cell: (e: ExamCalendarEntryRow) => (
                      <Button
                        variant="text"
                        icon="delete"
                        aria-label={`${e.course_name} girdisini kaldır`}
                        disabled={e.placed_date !== null || removeMutation.isPending}
                        onClick={() => removeMutation.mutate(e.id)}
                      >
                        Kaldır
                      </Button>
                    ),
                  },
                ]
              : []),
          ]}
        />
      )}
    </div>
  );
}
