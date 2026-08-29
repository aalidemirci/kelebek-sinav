// Sınav Takvimi — Süreç Takip paneli (F6) — OYS'den UYARLA: rol dalları düştü
// (tek kullanıcı idaredir — hep düzenlenebilir). Excel "Sınav Takip"in
// karşılığı: satır=takvim girdisi (ders+seviye), sütun=aktif süreç kalemi;
// hücre tıkla-döngü boş→Yapıldı→Kapsam dışı→boş; not modu açıkken tıklama
// not penceresi açar. M3 token'ları.

import { useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import { gradeLevelLabel } from "../../lib/gradeLevels";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import EmptyState from "../../ui/EmptyState";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import TextField from "../../ui/TextField";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { ExamTrackCell, ExamTrackStatusCode } from "./api";
import { examCalendarApi } from "./api";
import KalemYonetimiDialog from "./KalemYonetimiDialog";

const NEXT_STATUS: Record<string, ExamTrackStatusCode | null> = {
  EMPTY: "DONE",
  DONE: "NOT_APPLICABLE",
  NOT_APPLICABLE: null,
};

const STATUS_VIEW: Record<ExamTrackStatusCode, { icon: string; label: string; tone: string }> = {
  DONE: { icon: "check_circle", label: "Yapıldı", tone: "text-primary" },
  NOT_APPLICABLE: {
    icon: "remove_circle_outline",
    label: "Kapsam dışı",
    tone: "text-on-surface-variant",
  },
};

function cellTitle(cell: ExamTrackCell): string {
  if (!cell.status) return "İşaretsiz";
  const parts = [STATUS_VIEW[cell.status].label];
  if (cell.marked_by_name) parts.push(cell.marked_by_name);
  if (cell.marked_at) parts.push(new Date(cell.marked_at).toLocaleDateString("tr-TR"));
  if (cell.note) parts.push(cell.note); // not tooltip'te görünür
  return parts.join(" · ");
}

/** Not düzenleme hedefi. */
interface NoteTarget {
  entryId: number;
  itemId: number;
  label: string;
  status: ExamTrackStatusCode | null;
  note: string;
}

export default function TakvimTakipPaneli({ calendarId }: { calendarId: number }) {
  const snackbar = useSnackbar();
  const queryClient = useQueryClient();
  const [manageOpen, setManageOpen] = useState(false);
  const [noteMode, setNoteMode] = useState(false);
  const [noteTarget, setNoteTarget] = useState<NoteTarget | null>(null);
  // Sabit kimlik ŞART: Dialog'un focus-trap effect'i [open, onClose]'a bağlı —
  // her render'da değişen handler yazma sırasında odağı panele çalar.
  const closeNoteDialog = useCallback(() => setNoteTarget(null), []);
  const closeManage = useCallback(() => setManageOpen(false), []);

  const trackQuery = useQuery({
    queryKey: ["exam-calendar-track", calendarId],
    queryFn: () => examCalendarApi.track(calendarId),
  });

  const invalidateTrack = () =>
    void queryClient.invalidateQueries({ queryKey: ["exam-calendar-track", calendarId] });

  const manageDialog = (
    <KalemYonetimiDialog open={manageOpen} onClose={closeManage} onChanged={invalidateTrack} />
  );

  const markMutation = useMutation({
    // note alanı opsiyonel — gönderilmezse backend mevcut notu korur.
    mutationFn: (p: {
      entryId: number;
      itemId: number;
      status: ExamTrackStatusCode | null;
      note?: string;
    }) =>
      examCalendarApi.setTrackMark(calendarId, {
        entry_id: p.entryId,
        item_id: p.itemId,
        status: p.status,
        ...(p.note !== undefined ? { note: p.note } : {}),
      }),
    onSuccess: () => {
      setNoteTarget(null);
      invalidateTrack();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "İşaret kaydedilemedi."),
  });

  if (trackQuery.isPending) return <SkeletonList rows={5} />;
  const matrix = trackQuery.data;
  if (!matrix || matrix.items.length === 0) {
    return (
      <>
        <EmptyState
          icon="checklist"
          title="Süreç kalemi yok"
          description="Takip matrisi için süreç kalemi kataloğuna kalem ekleyin."
          action={
            <Button icon="tune" onClick={() => setManageOpen(true)}>
              Kalem Yönetimi
            </Button>
          }
        />
        {manageDialog}
      </>
    );
  }
  if (matrix.rows.length === 0) {
    return (
      <EmptyState
        icon="event_note"
        title="Takip edilecek ders yok"
        description="Havuza ders ekleyip yerleştirdiğinizde burada görünür."
      />
    );
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {/* Not modu — açıkken hücre tıklaması durum döngüsü yerine not
            penceresi açar (kim/ne zaman tooltip + not). */}
        <Button
          variant={noteMode ? "tonal" : "text"}
          icon="edit_note"
          className="ml-auto"
          aria-pressed={noteMode}
          onClick={() => setNoteMode((v) => !v)}
        >
          Not modu
        </Button>
        <Button variant="text" icon="tune" onClick={() => setManageOpen(true)}>
          Kalem Yönetimi
        </Button>
      </div>
      {noteMode ? (
        <p className="mb-2 text-body-small text-on-surface-variant">
          Not modu açık — bir hücreye tıklayınca durum değişmez, not düzenleme penceresi açılır.
        </p>
      ) : null}
      <div className="overflow-x-auto rounded-shape-lg bg-surface-container-low shadow-elevation-1">
        <table className="w-full border-collapse text-body-small">
          <caption className="sr-only">Sınav süreç takip matrisi</caption>
          <thead>
            <tr className="border-b border-outline-variant">
              <th className="sticky left-0 z-10 bg-surface-container-low px-3 py-2 text-left text-label-medium text-on-surface-variant">
                Ders / Seviye
              </th>
              {matrix.items.map((item) => (
                <th
                  key={item.id}
                  title={item.description || item.name}
                  className="px-2 py-2 text-center align-bottom text-label-small text-on-surface-variant"
                >
                  <span className="inline-block max-w-32 whitespace-normal">{item.name}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.rows.map((row) => (
              <tr key={row.entry_id} className="border-b border-outline-variant last:border-b-0">
                <th
                  scope="row"
                  className="sticky left-0 z-10 bg-surface-container-low px-3 py-2 text-left font-normal"
                >
                  <span className="block text-on-surface">{row.course_name}</span>
                  <span className="block text-body-small text-on-surface-variant">
                    {gradeLevelLabel(row.level)}
                    {row.exam_kind === "PRACTICE" ? " · Uygulama" : ""}
                  </span>
                </th>
                {row.cells.map((cell) => {
                  const view = cell.status ? STATUS_VIEW[cell.status] : null;
                  const itemName = matrix.items.find((i) => i.id === cell.item_id)?.name ?? "";
                  return (
                    <td key={cell.item_id} className="px-1 py-1 text-center">
                      <button
                        type="button"
                        disabled={markMutation.isPending}
                        aria-label={`${row.course_name} — ${itemName}: ${view ? view.label : "işaretsiz"}`}
                        title={cellTitle(cell)}
                        onClick={() =>
                          noteMode
                            ? setNoteTarget({
                                entryId: row.entry_id,
                                itemId: cell.item_id,
                                label: `${row.course_name} — ${itemName}`,
                                status: cell.status ?? null,
                                note: cell.note ?? "",
                              })
                            : markMutation.mutate({
                                entryId: row.entry_id,
                                itemId: cell.item_id,
                                status: NEXT_STATUS[cell.status ?? "EMPTY"] ?? null,
                              })
                        }
                        className={`inline-flex h-8 w-8 items-center justify-center rounded-shape-sm outline-offset-2 hover:bg-on-surface/5 focus-visible:bg-on-surface/8 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                          view ? view.tone : "text-outline"
                        }`}
                      >
                        <Icon name={view ? view.icon : "radio_button_unchecked"} />
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex flex-wrap gap-4 text-body-small text-on-surface-variant">
        <span className="inline-flex items-center gap-1">
          <Icon name="check_circle" className="text-primary" /> Yapıldı
        </span>
        <span className="inline-flex items-center gap-1">
          <Icon name="remove_circle_outline" /> Kapsam dışı
        </span>
        <span className="inline-flex items-center gap-1">
          <Icon name="radio_button_unchecked" className="text-outline" /> İşaretsiz
        </span>
      </div>
      {noteTarget ? (
        <Dialog
          open
          onClose={closeNoteDialog}
          title={`Not — ${noteTarget.label}`}
          actions={
            <>
              <Button variant="text" onClick={closeNoteDialog}>
                Vazgeç
              </Button>
              <Button
                disabled={markMutation.isPending}
                onClick={() =>
                  markMutation.mutate({
                    entryId: noteTarget.entryId,
                    itemId: noteTarget.itemId,
                    status: noteTarget.status ?? "DONE",
                    note: noteTarget.note,
                  })
                }
              >
                Kaydet
              </Button>
            </>
          }
        >
          <div className="flex flex-col gap-3">
            <Select
              label="Durum"
              options={[
                { value: "DONE", label: "Yapıldı" },
                { value: "NOT_APPLICABLE", label: "Kapsam dışı" },
              ]}
              value={noteTarget.status ?? "DONE"}
              onChange={(e) =>
                setNoteTarget((p) =>
                  p ? { ...p, status: e.target.value as ExamTrackStatusCode } : p,
                )
              }
            />
            <TextField
              label="Not"
              value={noteTarget.note}
              onChange={(e) => setNoteTarget((p) => (p ? { ...p, note: e.target.value } : p))}
            />
          </div>
        </Dialog>
      ) : null}
      {manageDialog}
    </div>
  );
}
