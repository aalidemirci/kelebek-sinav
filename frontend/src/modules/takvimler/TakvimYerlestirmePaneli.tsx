// Sınav Takvimi — Yerleştirme paneli (F6) — OYS'den UYARLA. Izgara: satır =
// (gün, ders saati), sütun = seviye. Boş hücre → o seviyenin havuz girdileri
// dialog'da (tıkla-yerleştir, DnD yok); dolu hücre çipi + kaldır. Onaylı
// takvimde satırda "Oturum Üret". Uyarı üç-kanalı: grid.errors bandı /
// grid.warnings bandı / placeEntry warnings snackbar'ı — kural hesabı
// backend'dedir, FE yalnız sunar. Okul dışı makam (Bakanlık/İl MEM/İlçe MEM)
// sınavları çipte AYRI rozetle görünür — rozet ders adı span'ının DIŞINDADIR
// (ders adının tam metin eşleşmesi bozulmasın). M3 token'ları.

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import Icon from "../../ui/Icon";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { formatDate } from "../oturumlar/oturumEtiket";
import type { CalendarGrid, ExamCalendarStatusCode } from "./api";
import { EXAM_AUTHORITY_SHORT_TR, EXAM_AUTHORITY_TR, examCalendarApi } from "./api";

interface SlotTarget {
  date: string;
  periodNo: number;
  level: number;
}

export default function TakvimYerlestirmePaneli({
  calendarId,
  status,
  onChanged,
}: {
  calendarId: number;
  status: ExamCalendarStatusCode;
  onChanged: () => void;
}) {
  const snackbar = useSnackbar();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [pickSlot, setPickSlot] = useState<SlotTarget | null>(null);
  const editable = status === "DRAFT";
  const approved = status === "APPROVED";

  const gridQuery = useQuery({
    queryKey: ["exam-calendar-grid", calendarId],
    queryFn: () => examCalendarApi.grid(calendarId),
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["exam-calendar-grid", calendarId] });
    void queryClient.invalidateQueries({ queryKey: ["exam-calendar-entries", calendarId] });
    onChanged();
  };

  const placeMutation = useMutation({
    mutationFn: (p: { entryId: number; date: string; periodNo: number }) =>
      examCalendarApi.placeEntry(p.entryId, { date: p.date, period_no: p.periodNo }),
    onSuccess: (data) => {
      // Uyarıyla yerleşir — sert reddi backend 400 ile döndürür (onError).
      data.warnings.forEach((w) => snackbar.error(w));
      setPickSlot(null);
      invalidate();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Yerleştirilemedi."),
  });

  const unplaceMutation = useMutation({
    mutationFn: (entryId: number) => examCalendarApi.unplaceEntry(entryId),
    onSuccess: invalidate,
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Kaldırılamadı."),
  });

  const createSessionMutation = useMutation({
    mutationFn: (p: { date: string; periodNo: number }) =>
      examCalendarApi.createSession(calendarId, { date: p.date, period_no: p.periodNo }),
    onSuccess: (data) => {
      snackbar.success(`Oturum üretildi: ${data.name}`);
      invalidate();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Oturum üretilemedi."),
  });

  const grid = gridQuery.data;
  const rows = useMemo(() => buildRows(grid), [grid]);

  if (gridQuery.isPending) return <SkeletonList rows={6} />;
  if (!grid) return <p className="text-on-surface-variant">Izgara yüklenemedi.</p>;
  // KS'de ders saati listesi boşsa varsayılan devreye girer (B6) — bu dal
  // yalnız yapılandırma bozulursa görünür.
  if (grid.periods.length === 0) {
    return (
      <p role="alert" className="text-body-medium text-on-surface-variant">
        Ders saati listesi boş — yerleştirme ızgarası oluşturulamıyor. Kurum yapılandırmasındaki
        ders saati listesini kontrol edin.
      </p>
    );
  }

  const unplacedByLevel = (level: number) => grid.unplaced.filter((c) => c.level === level);

  return (
    <div>
      {grid.errors.length > 0 ? (
        <div className="mb-3 rounded-shape-sm bg-error-container p-3 text-body-small text-on-error-container">
          {grid.errors.map((e, i) => (
            <div key={i}>⚠ {e}</div>
          ))}
        </div>
      ) : null}
      {grid.warnings.length > 0 ? (
        <div className="mb-3 rounded-shape-sm bg-secondary-container p-3 text-body-small text-on-secondary-container">
          {grid.warnings.map((w, i) => (
            <div key={i}>{w}</div>
          ))}
        </div>
      ) : null}

      <div className="overflow-x-auto rounded-shape-lg bg-surface-container-low shadow-elevation-1">
        <table className="w-full border-collapse text-body-small">
          <caption className="sr-only">Sınav takvimi yerleştirme ızgarası</caption>
          <thead>
            <tr className="border-b border-outline-variant">
              <th className="sticky left-0 z-10 bg-surface-container-low px-3 py-2 text-left text-label-medium text-on-surface-variant">
                Tarih / Ders Saati
              </th>
              {grid.levels.map((l) => (
                <th
                  key={l.value}
                  className="px-2 py-2 text-center text-label-small text-on-surface-variant"
                >
                  {l.display_label} ({l.student_count})
                </th>
              ))}
              {approved ? <th className="px-2 py-2" /> : null}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.date}|${row.periodNo}`} className="border-b border-outline-variant">
                <th
                  scope="row"
                  className="sticky left-0 z-10 bg-surface-container-low px-3 py-2 text-left font-normal"
                >
                  {row.firstOfDay ? (
                    <span className="block text-body-medium text-on-surface">{row.dayLabel}</span>
                  ) : null}
                  <span className="block text-body-small text-on-surface-variant">
                    {row.periodName}
                  </span>
                </th>
                {grid.levels.map((l) => {
                  const key = `${row.date}|${row.periodNo}|${l.value}`;
                  const cells = grid.cells[key] ?? [];
                  return (
                    <td key={l.value} className="px-1 py-1 text-center align-top">
                      {cells.map((c) => (
                        <div
                          key={c.entry_id}
                          className="mb-1 inline-flex items-center gap-1 rounded-shape-sm bg-secondary-container px-2 py-1 text-label-small text-on-secondary-container"
                        >
                          <span>
                            {c.course_name}
                            {c.exam_kind === "PRACTICE" ? " [U]" : ""}
                            {!c.is_butterfly ? " (KD)" : ""}
                          </span>
                          {c.authority !== "SCHOOL" ? (
                            <span
                              title={`${EXAM_AUTHORITY_TR[c.authority]} sınavı`}
                              className="rounded-full bg-tertiary-container px-1.5 text-label-small text-on-tertiary-container"
                            >
                              {EXAM_AUTHORITY_SHORT_TR[c.authority]}
                            </span>
                          ) : null}
                          {editable ? (
                            <button
                              type="button"
                              aria-label={`${c.course_name} yerleşimini kaldır`}
                              className="-my-2 -mr-1 flex min-h-8 min-w-8 shrink-0 items-center justify-center rounded-shape-sm hover:bg-on-secondary-container/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                              onClick={() => unplaceMutation.mutate(c.entry_id)}
                            >
                              <Icon name="close" size="sm" />
                            </button>
                          ) : null}
                          {c.session_id ? (
                            <button
                              type="button"
                              aria-label="Üretilen oturuma git"
                              className="-my-2 -mr-1 flex min-h-8 min-w-8 shrink-0 items-center justify-center rounded-shape-sm hover:bg-on-secondary-container/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                              onClick={() => navigate(`/oturumlar/${c.session_id}`)}
                            >
                              <Icon name="open_in_new" size="sm" />
                            </button>
                          ) : null}
                        </div>
                      ))}
                      {editable ? (
                        <button
                          type="button"
                          aria-label={`${row.dayLabel} ${row.periodName} ${l.display_label} sınav yerleştir`}
                          className="inline-flex min-h-8 min-w-8 items-center justify-center rounded-shape-sm text-outline outline-offset-2 hover:bg-on-surface/5 focus-visible:bg-on-surface/8 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                          onClick={() =>
                            setPickSlot({ date: row.date, periodNo: row.periodNo, level: l.value })
                          }
                        >
                          <Icon name="add" size="sm" />
                        </button>
                      ) : null}
                    </td>
                  );
                })}
                {approved ? (
                  <td className="px-2 py-1 text-center">
                    {rowHasButterfly(grid, row) ? (
                      <Button
                        variant="tonal"
                        icon="auto_awesome"
                        disabled={createSessionMutation.isPending}
                        onClick={() =>
                          createSessionMutation.mutate({ date: row.date, periodNo: row.periodNo })
                        }
                      >
                        Oturum Üret
                      </Button>
                    ) : null}
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-2 text-body-small text-on-surface-variant">
        BAK / İL / İLÇE rozetli sınavlar Bakanlık ya da İl/İlçe Millî Eğitim Müdürlüğünce yapılır;
        tarih ve saatleri ilgili makamın kılavuzuna göredir ve o günlerde okul geneli ayrıca sınav
        yapılmaz.
      </p>

      {pickSlot ? (
        <Dialog
          open
          onClose={() => setPickSlot(null)}
          title="Sınav yerleştir"
          actions={
            <Button variant="text" onClick={() => setPickSlot(null)}>
              Kapat
            </Button>
          }
        >
          <div className="flex flex-col gap-2">
            {unplacedByLevel(pickSlot.level).length === 0 ? (
              <p className="text-body-small text-on-surface-variant">
                Bu seviyede havuzda yerleştirilecek ders yok.
              </p>
            ) : (
              unplacedByLevel(pickSlot.level).map((c) => (
                <button
                  key={c.entry_id}
                  type="button"
                  className="flex min-h-9 items-center justify-between rounded-shape-sm border border-outline-variant px-3 text-left text-body-medium text-on-surface hover:bg-on-surface/5"
                  onClick={() =>
                    placeMutation.mutate({
                      entryId: c.entry_id,
                      date: pickSlot.date,
                      periodNo: pickSlot.periodNo,
                    })
                  }
                >
                  <span>
                    {c.course_name}
                    {c.exam_kind === "PRACTICE" ? " [Uygulama]" : ""}
                    {c.authority !== "SCHOOL" ? ` — ${EXAM_AUTHORITY_TR[c.authority]}` : ""}
                  </span>
                  <Icon name="add_circle" />
                </button>
              ))
            )}
          </div>
        </Dialog>
      ) : null}
    </div>
  );
}

interface GridRow {
  date: string;
  periodNo: number;
  periodName: string;
  dayLabel: string;
  firstOfDay: boolean;
}

function buildRows(grid: CalendarGrid | undefined): GridRow[] {
  if (!grid) return [];
  const rows: GridRow[] = [];
  for (const day of grid.days) {
    // Hafta sonu günleri tamamen atlanmaz — backend hafta sonuna UYARIYLA
    // yerleştirmeye izin verir; yerleştirilmiş girdisi olan hafta sonu günü
    // ızgarada görünür (boş hafta sonları gizli — kompakt ızgara).
    if (day.is_weekend && !dayHasCells(grid, day.date)) continue;
    grid.periods.forEach((p, idx) => {
      rows.push({
        date: day.date,
        periodNo: p.no,
        periodName: p.name,
        dayLabel: day.is_weekend ? `${formatDate(day.date)} (Hafta sonu)` : formatDate(day.date),
        firstOfDay: idx === 0,
      });
    });
  }
  return rows;
}

function dayHasCells(grid: CalendarGrid, date: string): boolean {
  return grid.periods.some((p) =>
    grid.levels.some((l) => (grid.cells[`${date}|${p.no}|${l.value}`] ?? []).length > 0),
  );
}

function rowHasButterfly(grid: CalendarGrid, row: GridRow): boolean {
  return grid.levels.some((l) => {
    const cells = grid.cells[`${row.date}|${row.periodNo}|${l.value}`] ?? [];
    return cells.some((c) => c.is_butterfly && !c.session_id);
  });
}
