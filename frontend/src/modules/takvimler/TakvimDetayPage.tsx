// Sınav Takvimi detay (F6) — OYS TakvimDetayPage'den UYARLA: rol dalları
// düştü (tek kullanıcı hem hazırlar hem onaylar — B12; SUBMITTED tek tıkla
// geçilir, APPROVED kilidi ve damgalar kalır), rota kökü `/takvimler`.
// Havuz + yerleştirme + takip + önizleme sekmeleri + onay akışı + PDF indir.

import { useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../../lib/api";
import { saveBlob } from "../../lib/download";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import Icon from "../../ui/Icon";
import { SkeletonList } from "../../ui/Skeleton";
import Tabs from "../../ui/Tabs";
import TextField from "../../ui/TextField";
import { useConfirm } from "../../ui/ConfirmProvider";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { formatDate } from "../oturumlar/oturumEtiket";
import { examCalendarApi } from "./api";
import { CalendarStatusBadge } from "./TakvimlerPage";
import TakvimHavuzPaneli from "./TakvimHavuzPaneli";
import TakvimOnizlemePaneli from "./TakvimOnizlemePaneli";
import TakvimTakipPaneli from "./TakvimTakipPaneli";
import TakvimYerlestirmePaneli from "./TakvimYerlestirmePaneli";

export default function TakvimDetayPage() {
  const { id } = useParams<{ id: string }>();
  const calendarId = Number(id);
  const navigate = useNavigate();
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState("havuz");
  const [dateEditOpen, setDateEditOpen] = useState(false);
  const closeDateEdit = useCallback(() => setDateEditOpen(false), []);

  const calendarQuery = useQuery({
    queryKey: ["exam-calendar", calendarId],
    queryFn: () => examCalendarApi.get(calendarId),
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["exam-calendar", calendarId] });
    void queryClient.invalidateQueries({ queryKey: ["exam-calendar-grid", calendarId] });
  };

  const lifecycle = useMutation({
    mutationFn: (action: "submit" | "approve" | "reopen") => examCalendarApi[action](calendarId),
    onSuccess: () => {
      snackbar.success("Takvim durumu güncellendi.");
      invalidate();
    },
    onError: (e) =>
      snackbar.error(e instanceof ApiError ? e.message : "İşlem gerçekleştirilemedi."),
  });

  const removeMutation = useMutation({
    mutationFn: () => examCalendarApi.remove(calendarId),
    onSuccess: () => {
      snackbar.success("Takvim silindi.");
      void queryClient.invalidateQueries({ queryKey: ["exam-calendars"] });
      navigate("/takvimler");
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Silinemedi."),
  });

  const downloadPdf = async () => {
    try {
      const blob = await examCalendarApi.pdfBlob(calendarId);
      saveBlob(blob, `sinav_takvimi_${calendarId}.pdf`);
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "PDF indirilemedi.");
    }
  };

  if (calendarQuery.isPending) {
    return <SkeletonList rows={6} />;
  }
  const calendar = calendarQuery.data;
  if (!calendar) {
    return <div className="text-on-surface-variant">Takvim bulunamadı.</div>;
  }
  const isDraft = calendar.status === "DRAFT";
  const isSubmitted = calendar.status === "SUBMITTED";

  const tabs = [
    { key: "havuz", label: "Havuz", icon: "playlist_add" },
    { key: "yerlestirme", label: "Yerleştirme", icon: "grid_on" },
    { key: "takip", label: "Süreç Takip", icon: "checklist" },
    { key: "onizleme", label: "Önizleme", icon: "description" },
  ];

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Button variant="text" icon="arrow_back" onClick={() => navigate("/takvimler")}>
          Takvimler
        </Button>
        <h1 className="text-headline-medium text-on-surface">{calendar.name}</h1>
        <CalendarStatusBadge status={calendar.status} />
        <span className="text-body-medium text-on-surface-variant">
          {formatDate(calendar.start_date)} – {formatDate(calendar.end_date)}
        </span>
        {isDraft ? (
          <Button
            variant="text"
            icon="edit_calendar"
            aria-label="Takvim tarihlerini düzenle"
            onClick={() => setDateEditOpen(true)}
          >
            Tarihleri Düzenle
          </Button>
        ) : null}
        <span className="ml-auto" />
        <Button variant="outlined" icon="picture_as_pdf" onClick={() => void downloadPdf()}>
          PDF
        </Button>
        {isDraft ? (
          <>
            <Button
              variant="tonal"
              icon="send"
              disabled={lifecycle.isPending}
              onClick={() => lifecycle.mutate("submit")}
            >
              Onaya Sun
            </Button>
            <Button
              variant="text"
              icon="delete"
              disabled={removeMutation.isPending}
              onClick={() =>
                void confirm({
                  title: "Takvim silinsin mi?",
                  message: `'${calendar.name}' silinsin mi?`,
                  confirmLabel: "Sil",
                }).then((ok) => ok && removeMutation.mutate())
              }
            >
              Sil
            </Button>
          </>
        ) : null}
        {isSubmitted ? (
          <Button
            icon="check_circle"
            disabled={lifecycle.isPending}
            onClick={() => lifecycle.mutate("approve")}
          >
            Onayla
          </Button>
        ) : null}
        {!isDraft ? (
          <Button
            variant="text"
            icon="undo"
            disabled={lifecycle.isPending}
            onClick={() => lifecycle.mutate("reopen")}
          >
            Taslağa Al
          </Button>
        ) : null}
      </div>

      {!isDraft ? (
        <p className="mb-3 inline-flex items-center gap-1 text-body-small text-on-surface-variant">
          <Icon name="lock" size="sm" /> Havuz ve yerleştirme yalnız taslak durumda düzenlenebilir.
        </p>
      ) : null}

      <Tabs items={tabs} active={tab} onChange={setTab} idBase="takvim-detay" />

      <div className="mt-4">
        {tab === "havuz" ? (
          <TakvimHavuzPaneli
            calendarId={calendarId}
            round={calendar.round}
            editable={isDraft}
            onChanged={invalidate}
          />
        ) : tab === "yerlestirme" ? (
          <TakvimYerlestirmePaneli
            calendarId={calendarId}
            status={calendar.status}
            onChanged={invalidate}
          />
        ) : tab === "takip" ? (
          <TakvimTakipPaneli calendarId={calendarId} />
        ) : (
          <TakvimOnizlemePaneli calendar={calendar} editable={isDraft} onSaved={invalidate} />
        )}
      </div>

      {dateEditOpen ? (
        <DateEditDialog
          calendarId={calendarId}
          startDate={calendar.start_date}
          endDate={calendar.end_date}
          onClose={closeDateEdit}
          onSaved={() => {
            setDateEditOpen(false);
            invalidate();
          }}
        />
      ) : null}
    </div>
  );
}

/** Takvim aralığı düzenleme (pencere tamamı düzenlenebilir — kılavuz varsayılanı). */
function DateEditDialog({
  calendarId,
  startDate,
  endDate,
  onClose,
  onSaved,
}: {
  calendarId: number;
  startDate: string;
  endDate: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const snackbar = useSnackbar();
  const [start, setStart] = useState(startDate);
  const [end, setEnd] = useState(endDate);

  const saveMutation = useMutation({
    mutationFn: () => examCalendarApi.update(calendarId, { start_date: start, end_date: end }),
    onSuccess: () => {
      snackbar.success("Takvim tarihleri güncellendi.");
      onSaved();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Tarihler güncellenemedi."),
  });

  return (
    <Dialog
      open
      onClose={onClose}
      title="Takvim tarihlerini düzenle"
      actions={
        <>
          <Button variant="text" onClick={onClose}>
            Vazgeç
          </Button>
          <Button
            disabled={saveMutation.isPending || !start || !end}
            onClick={() => saveMutation.mutate()}
          >
            Kaydet
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <TextField
          label="Başlangıç tarihi"
          type="date"
          value={start}
          onChange={(e) => setStart(e.target.value)}
        />
        <TextField
          label="Bitiş tarihi"
          type="date"
          value={end}
          onChange={(e) => setEnd(e.target.value)}
        />
      </div>
    </Dialog>
  );
}
