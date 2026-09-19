// Sınav Takvimi detay (F6) — OYS TakvimDetayPage'den UYARLA: rol dalları
// düştü (tek kullanıcı hem hazırlar hem onaylar — B12). Havuz + yerleştirme +
// takip + önizleme sekmeleri + onay akışı + PDF indir.
//
// Onay akışı (18.09.2026, değerlendirme K2): tek kullanıcıda "Onaya sun →
// Onayla" iki tıklık bir ritüeldi — sunan da onaylayan da aynı kişi. Arayüzde
// TEK birincil düğme kaldı: "Onayla". Backend durum makinesi DEĞİŞMEDİ
// (TASLAK → ONAYA SUNULDU → ONAYLANDI); düğme taslakta `submit` + `approve`
// uçlarını art arda çağırır, damgalar (sunum/onay zamanı, onaylayan) eskisi gibi
// yazılır. Eski veride ONAYA SUNULDU durumunda kalmış takvimde de aynı düğme
// görünür ve yalnız `approve` çağırır.

import { useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../../lib/api";
import { saveBlob } from "../../lib/download";
import { formatDate } from "../../lib/format";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import EmptyState from "../../ui/EmptyState";
import Icon from "../../ui/Icon";
import { SkeletonList } from "../../ui/Skeleton";
import Tabs from "../../ui/Tabs";
import TextField from "../../ui/TextField";
import { useConfirm } from "../../ui/ConfirmProvider";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { DefaultWindow, ExamCalendarStatusCode } from "./api";
import { calendarPdfFileName, examCalendarApi } from "./api";
import BakanlikSinavlari from "./BakanlikSinavlari";
import PencereOnerisi from "./PencereOnerisi";
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
    void queryClient.invalidateQueries({ queryKey: ["exam-calendars"] });
  };

  // Tek "Onayla": taslakta önce sunulur, sonra onaylanır (dosya başı notu).
  const approveMutation = useMutation({
    mutationFn: async (status: ExamCalendarStatusCode) => {
      if (status === "DRAFT") await examCalendarApi.submit(calendarId);
      return examCalendarApi.approve(calendarId);
    },
    onSuccess: () => {
      snackbar.success("Takvim onaylandı.");
      invalidate();
    },
    onError: (e) => {
      snackbar.error(e instanceof ApiError ? e.message : "Takvim onaylanamadı.");
      // Sunum geçip onay takıldıysa takvim ONAYA SUNULDU'da kalmıştır — ekran
      // gerçek durumu göstersin ("Onayla" yine oradadır, yeniden denenir).
      invalidate();
    },
  });

  const reopenMutation = useMutation({
    mutationFn: () => examCalendarApi.reopen(calendarId),
    onSuccess: () => {
      snackbar.success("Takvim taslağa alındı.");
      invalidate();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Takvim taslağa alınamadı."),
  });

  const removeMutation = useMutation({
    mutationFn: () => examCalendarApi.remove(calendarId),
    onSuccess: () => {
      snackbar.success("Takvim silindi.");
      void queryClient.invalidateQueries({ queryKey: ["exam-calendars"] });
      navigate("/takvimler");
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Takvim silinemedi."),
  });

  if (calendarQuery.isPending) {
    return <SkeletonList rows={6} />;
  }
  const calendar = calendarQuery.data;
  if (calendarQuery.isError || !calendar) {
    const hata = calendarQuery.error;
    // "Bulunamadı" YALNIZ 404'tür; kilitli kayıt, sunucu hatası ya da bağlantı
    // kopması "takvim yok" diye sunulmaz — gerçek mesaj gösterilir.
    if (hata instanceof ApiError && hata.status === 404) {
      return (
        <EmptyState
          icon="event_busy"
          title="Takvim bulunamadı."
          description="Bu takvim silinmiş ya da bağlantı eski olabilir."
          action={
            <Button icon="arrow_back" onClick={() => navigate("/takvimler")}>
              Takvimlere dön
            </Button>
          }
        />
      );
    }
    return (
      <div role="alert" className="flex flex-col items-start gap-3">
        <p className="flex items-start gap-2 rounded-shape-sm bg-error-container px-4 py-3 text-body-medium text-on-error-container">
          <Icon name="error" size="lg" />
          <span>
            Takvim yüklenemedi: {hata instanceof ApiError ? hata.message : "beklenmeyen bir hata."}
          </span>
        </p>
        <Button variant="tonal" icon="refresh" onClick={() => void calendarQuery.refetch()}>
          Yeniden dene
        </Button>
      </div>
    );
  }
  const isDraft = calendar.status === "DRAFT";
  const isApproved = calendar.status === "APPROVED";
  const lifecycleBusy = approveMutation.isPending || reopenMutation.isPending;

  const downloadPdf = async () => {
    try {
      const blob = await examCalendarApi.pdfBlob(calendarId);
      saveBlob(blob, calendarPdfFileName(calendar));
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "PDF indirilemedi.");
    }
  };

  // Onaylı takvimde taslağa almak onayı DÜŞÜRÜR (PDF yeniden "TASLAK" filigranlı
  // basılır) → onay diyaloğu. Eski veride ONAYA SUNULDU'dan dönüşte düşecek bir
  // onay yoktur; doğrudan alınır.
  const handleReopen = () => {
    if (!isApproved) {
      reopenMutation.mutate();
      return;
    }
    void confirm({
      title: "Onaylı takvim taslağa alınsın mı?",
      message:
        "Takvimin onayı kalkar: havuz, yerleştirme ve açıklamalar yeniden düzenlenebilir olur, " +
        "PDF yeniden “TASLAK” filigranıyla basılır. Bu takvimden üretilmiş oturumlar " +
        "etkilenmez. Duyurmadan önce takvimi yeniden onaylamanız gerekir.",
      confirmLabel: "Taslağa al",
    }).then((ok) => ok && reopenMutation.mutate());
  };

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
            Tarihleri düzenle
          </Button>
        ) : null}
        <span className="ml-auto" />
        <Button variant="outlined" icon="picture_as_pdf" onClick={() => void downloadPdf()}>
          PDF
        </Button>
        {isDraft ? (
          <Button
            variant="text"
            icon="delete"
            disabled={removeMutation.isPending}
            onClick={() =>
              void confirm({
                title: "Takvim silinsin mi?",
                message:
                  `“${calendar.name}” havuzu, yerleştirmesi ve süreç takip işaretleriyle ` +
                  "birlikte silinir.",
                confirmLabel: "Sil",
              }).then((ok) => ok && removeMutation.mutate())
            }
          >
            Sil
          </Button>
        ) : null}
        {!isDraft ? (
          <Button variant="text" icon="undo" disabled={lifecycleBusy} onClick={handleReopen}>
            Taslağa al
          </Button>
        ) : null}
        {!isApproved ? (
          <Button
            icon="check_circle"
            disabled={lifecycleBusy}
            onClick={() => approveMutation.mutate(calendar.status)}
          >
            {approveMutation.isPending ? "Onaylanıyor…" : "Onayla"}
          </Button>
        ) : null}
      </div>

      {!isDraft ? (
        <p className="mb-3 inline-flex items-center gap-1 text-body-small text-on-surface-variant">
          <Icon name="lock" size="sm" /> Havuz ve yerleştirme yalnız taslak durumda düzenlenebilir.
        </p>
      ) : null}

      {/* Bakanlığın ilan ettiği haftalardan farklı taslak: yalnız ÖNERİ (kısıt değil). */}
      {isDraft &&
      calendar.default_window?.official &&
      (calendar.default_window.start_date !== calendar.start_date ||
        calendar.default_window.end_date !== calendar.end_date) ? (
        <p
          role="status"
          className="mb-3 flex flex-wrap items-center gap-2 rounded-shape-sm bg-secondary-container px-3 py-2 text-body-small text-on-secondary-container"
        >
          <Icon name="info" size="sm" />
          <span>
            Bu takvimin tarihleri Bakanlığın ilan ettiği sınav haftalarından farklı (
            {formatDate(calendar.default_window.start_date)} –{" "}
            {formatDate(calendar.default_window.end_date)}). İsterseniz tarihleri
            güncelleyebilirsiniz; yerleştirme bundan etkilenmez.
          </span>
          <Button variant="text" icon="edit_calendar" onClick={() => setDateEditOpen(true)}>
            Tarihleri düzenle
          </Button>
        </p>
      ) : null}

      <BakanlikSinavlari calendarId={calendarId} editable={isDraft} onApplied={invalidate} />

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
          oneri={calendar.default_window}
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
  oneri,
  onClose,
  onSaved,
}: {
  calendarId: number;
  startDate: string;
  endDate: string;
  /** Önerilen haftalar (Bakanlık ilanı / Yönetmelik) — "Bu tarihleri kullan". */
  oneri: DefaultWindow | null;
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
        {oneri ? (
          <PencereOnerisi
            pencere={oneri}
            onApply={() => {
              setStart(oneri.start_date);
              setEnd(oneri.end_date);
            }}
          />
        ) : null}
      </div>
    </Dialog>
  );
}
