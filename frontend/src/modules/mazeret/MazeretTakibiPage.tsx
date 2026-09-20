// Mazeret Takibi (19.09.2026, kullanıcı isteği) — dönemin sınavlarına girmeyen
// öğrenciler tek ekranda: mazeret durumu ve belge notu burada da güncellenir,
// mazereti kabul edilenler ("Mazeretli") seçilip TOPLU mazeret sınavı açılır, takip
// raporu PDF (resmî, imzalı) ve Excel (e-Okul'a işleme kopyası) olarak alınır.
//
// Kurallar backend'dedir (`services_makeup`): mazeret sınavına yalnız "Mazeretli"
// girer, bir defaya mahsustur (mazeret sınavında da girmeyene ikincisi açılmaz),
// dönem içinde açılır; 5 iş günü bildirim süresi UYARIDIR — karar idarenindir.
// Ekran kuralları yalnız görünür kılar (seçim kutusu, rozet); son söz backend'in.

import { useCallback, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { useTabParam } from "../../hooks/useTabParam";
import { ApiError } from "../../lib/api";
import { dosyaAdi, saveBlob } from "../../lib/download";
import { formatDate } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import Dialog from "../../ui/Dialog";
import EmptyState from "../../ui/EmptyState";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import Tabs, { tabPanelProps } from "../../ui/Tabs";
import TextField from "../../ui/TextField";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { ExcuseStatusCode } from "../oturumlar/api";
import { attendanceApi, EXCUSE_STATUS_TR } from "../oturumlar/api";
import type { AbsenceRow, AbsenceSummary, MakeupReportKind } from "./api";
import { makeupApi } from "./api";
import MazeretTakvimi from "./MazeretTakvimi";

/** İndirilen raporun belge adı (docs/sozluk.md §3 — belge adı + dönem). */
export const REPORT_FILE_TITLE = "Mazeret Takip Çizelgesi";
const DEFAULT_MAKEUP_NAME = "Mazeret Sınavı";

const TABS = ["kayitlar", "takvim"] as const;
type TabKey = (typeof TABS)[number];

type Filtre = "ALL" | "PENDING" | "AWAITING" | "UNEXCUSED";

const FILTRE_TR: Record<Filtre, string> = {
  ALL: "Tümü",
  PENDING: "Karar bekleyenler",
  AWAITING: "Mazeret sınavı bekleyenler",
  UNEXCUSED: "Mazeretsizler (e-Okul'a “G”)",
};

const FILTRE_UYGUN: Record<Filtre, (r: AbsenceRow) => boolean> = {
  ALL: () => true,
  PENDING: (r) => r.excuse_status === "PENDING",
  AWAITING: (r) => r.can_makeup,
  UNEXCUSED: (r) => r.excuse_status === "UNEXCUSED",
};

/** Mazeret durumu → tonal çip (Yoklama paneliyle aynı tonlar; ham renk yok). */
const EXCUSE_TONES: Record<ExcuseStatusCode, string> = {
  PENDING: "bg-surface-container-high text-on-surface",
  EXCUSED: "bg-primary-container text-on-primary-container",
  UNEXCUSED: "bg-error-container text-on-error-container",
};

interface SinavGrubu {
  key: string;
  examDate: string;
  courseLabel: string;
  sessionName: string;
  sessionId: number;
  external: boolean;
  typeLabel: string;
  isMakeup: boolean;
  rows: AbsenceRow[];
}

/** Satırlar sınav (oturum + ders) başına gruplanır — sıra backend'den (tarih, ders, no). */
function gruplaSinavlar(rows: AbsenceRow[]): SinavGrubu[] {
  const gruplar = new Map<string, SinavGrubu>();
  for (const r of rows) {
    const key = `${r.session_id}|${r.course_label}`;
    let grup = gruplar.get(key);
    if (!grup) {
      grup = {
        key,
        examDate: r.exam_date,
        courseLabel: r.course_label,
        sessionName: r.session_name,
        sessionId: r.session_id,
        external: r.external,
        typeLabel: r.session_type_label,
        isMakeup: r.session_is_makeup,
        rows: [],
      };
      gruplar.set(key, grup);
    }
    grup.rows.push(r);
  }
  return [...gruplar.values()];
}

function OzetCipleri({ summary }: { summary: AbsenceSummary }) {
  const ogeler: { label: string; value: number; tone: string }[] = [
    { label: "Sınava girmeyen", value: summary.total, tone: "bg-surface-container-high" },
    { label: "Karar bekleyen", value: summary.pending, tone: "bg-surface-container-high" },
    { label: "Mazeretli", value: summary.excused, tone: "bg-primary-container" },
    { label: "Mazeretsiz", value: summary.unexcused, tone: "bg-error-container" },
    {
      label: "Bildirim süresi geçmiş",
      value: summary.overdue,
      tone: summary.overdue > 0 ? "bg-error-container" : "bg-surface-container-high",
    },
    {
      label: "Mazeret sınavı bekleyen",
      value: summary.awaiting_makeup,
      tone: "bg-secondary-container",
    },
    { label: "Mazeret sınavına alınan", value: summary.in_makeup, tone: "bg-secondary-container" },
  ];
  return (
    <ul aria-label="Özet" className="flex flex-wrap gap-2">
      {ogeler.map((o) => (
        <li
          key={o.label}
          className={`flex items-baseline gap-2 rounded-shape-md px-3 py-2 text-on-surface ${o.tone}`}
        >
          <span className="text-title-medium">{o.value}</span>
          <span className="text-body-small">{o.label}</span>
        </li>
      ))}
    </ul>
  );
}

function MazeretSinaviBilgisi({
  row,
  onRemove,
  busy,
}: {
  row: AbsenceRow;
  onRemove: (row: AbsenceRow) => void;
  busy: boolean;
}) {
  if (row.session_is_makeup) {
    return (
      <span className="text-body-small text-on-surface-variant">
        Mazeret sınavında girmedi — ikinci mazeret sınavı yapılmaz
      </span>
    );
  }
  if (row.makeup_session_id !== null) {
    // Yapılmış (onaylı/arşiv) mazeret sınavından öğrenci çıkarılamaz — backend de reddeder.
    const cikarilabilir =
      row.makeup_session_status === "DRAFT" || row.makeup_session_status === "DISTRIBUTED";
    return (
      <span className="flex flex-wrap items-center gap-2 text-body-small">
        <Link to={`/oturumlar/${row.makeup_session_id}`} className="text-primary underline">
          {row.makeup_session_name} · {formatDate(row.makeup_date)}
        </Link>
        <span className="rounded-full bg-surface-container-high px-2 py-0.5 text-label-small text-on-surface">
          {row.makeup_result_label}
        </span>
        {cikarilabilir && (
          <Button variant="text" icon="person_remove" onClick={() => onRemove(row)} disabled={busy}>
            Çıkar
          </Button>
        )}
      </span>
    );
  }
  if (row.excuse_status === "UNEXCUSED") {
    return <span className="text-body-small text-error">{"e-Okul'a “G” işlenir"}</span>;
  }
  if (row.plan_id !== null) {
    // Takvime alınmış kayıt elle seçilemez: oturumu mazeret takviminden üretilir.
    return (
      <span className="text-body-small text-on-surface-variant">
        Mazeret takviminde: {row.plan_name}
        {row.plan_date !== null &&
          ` · ${formatDate(row.plan_date)} · ${row.plan_period_no}. ders saati`}
      </span>
    );
  }
  if (row.can_makeup) {
    return <span className="text-body-small text-on-surface-variant">Mazeret sınavı bekliyor</span>;
  }
  return null;
}

function KayitSatiri({
  row,
  selected,
  onToggle,
  onChanged,
  onRemove,
  removeBusy,
}: {
  row: AbsenceRow;
  selected: boolean;
  onToggle: (row: AbsenceRow) => void;
  onChanged: (row: AbsenceRow) => void;
  onRemove: (row: AbsenceRow) => void;
  removeBusy: boolean;
}) {
  const snackbar = useSnackbar();
  const [note, setNote] = useState(row.note);
  const update = useMutation({
    mutationFn: (payload: { excuse_status?: ExcuseStatusCode; note?: string }) =>
      attendanceApi.update(row.record_id, payload),
    onSuccess: () => {
      onChanged(row);
      snackbar.success("Mazeret kaydı güncellendi.");
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Güncellenemedi."),
  });

  return (
    <li className="flex flex-wrap items-center gap-3 rounded-shape-md border border-outline-variant p-3">
      <input
        type="checkbox"
        className="h-5 w-5 accent-primary"
        aria-label={`${row.student_number} mazeret sınavına seç`}
        checked={selected}
        disabled={!row.can_makeup}
        onChange={() => onToggle(row)}
      />
      <span className="w-16 text-label-large text-on-surface-variant">{row.student_number}</span>
      <span className="min-w-40 text-title-small text-on-surface">{row.full_name}</span>
      <span className="text-body-small text-on-surface-variant">{row.class_label}</span>
      <span
        className={`rounded-full px-3 py-1 text-label-small ${EXCUSE_TONES[row.excuse_status]}`}
      >
        {EXCUSE_STATUS_TR[row.excuse_status]}
      </span>
      <span
        className={`text-body-small ${row.notice_overdue ? "font-semibold text-error" : "text-on-surface-variant"}`}
      >
        Son gün {formatDate(row.notice_deadline)}
        {row.notice_overdue && " — süre geçti"}
      </span>
      <span className="ml-auto" />
      <Select
        label=""
        aria-label={`${row.student_number} mazeret durumu`}
        options={Object.entries(EXCUSE_STATUS_TR).map(([value, label]) => ({ value, label }))}
        value={row.excuse_status}
        onChange={(e) => update.mutate({ excuse_status: e.target.value as ExcuseStatusCode })}
        disabled={update.isPending}
        className="w-40"
      />
      <div className="w-72">
        <TextField
          label=""
          aria-label={`${row.student_number} belge notu`}
          placeholder="Belge no/tarih (örn. Rapor no 123, 10.06.2026)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          onBlur={() => note !== row.note && update.mutate({ note })}
        />
      </div>
      <div className="w-full pl-8">
        <MazeretSinaviBilgisi row={row} onRemove={onRemove} busy={removeBusy} />
      </div>
    </li>
  );
}

/** Seçimde aynı öğrenci iki kez varsa (iki sınavın mazereti) — backend de reddeder. */
function ciftOgrenci(rows: AbsenceRow[]): string | null {
  const gorulen = new Set<number>();
  for (const r of rows) {
    if (r.student_id === null) continue;
    if (gorulen.has(r.student_id)) return r.student_number;
    gorulen.add(r.student_id);
  }
  return null;
}

function MazeretSinaviDialog({
  open,
  onClose,
  selectedRows,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  selectedRows: AbsenceRow[];
  onCreated: (sessionId: number) => void;
}) {
  const snackbar = useSnackbar();
  const [form, setForm] = useState({
    name: DEFAULT_MAKEUP_NAME,
    exam_date: "",
    start_time: "09:00",
    duration_minutes: "40",
  });
  const create = useMutation({
    mutationFn: () =>
      makeupApi.createSession({
        record_ids: selectedRows.map((r) => r.record_id),
        name: form.name.trim(),
        exam_date: form.exam_date,
        start_time: form.start_time,
        duration_minutes: Number(form.duration_minutes),
      }),
    onSuccess: (session) => onCreated(session.id),
    onError: (e) =>
      snackbar.error(e instanceof ApiError ? e.message : "Mazeret sınavı oluşturulamadı."),
  });

  const dersler = useMemo(() => {
    const sayim = new Map<string, number>();
    for (const r of selectedRows) sayim.set(r.course_label, (sayim.get(r.course_label) ?? 0) + 1);
    return [...sayim.entries()];
  }, [selectedRows]);
  const cift = ciftOgrenci(selectedRows);
  const disari = selectedRows.some((r) => r.external);
  const canCreate =
    form.exam_date !== "" &&
    form.start_time !== "" &&
    Number(form.duration_minutes) > 0 &&
    cift === null;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Mazeret sınavı oluştur"
      actions={
        <>
          <Button variant="text" onClick={onClose}>
            Vazgeç
          </Button>
          <Button onClick={() => create.mutate()} disabled={create.isPending || !canCreate}>
            {create.isPending ? "Oluşturuluyor…" : "Oluştur"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-body-medium text-on-surface">
          {selectedRows.length} öğrenci, {dersler.length} ders. Oturum taslak olarak açılır; salon,
          dağıtım, evrak ve yoklama normal sınav gibi yürür.
        </p>
        <ul className="flex flex-col gap-0.5 text-body-small text-on-surface-variant">
          {dersler.map(([ders, adet]) => (
            <li key={ders}>
              {ders}: {adet} öğrenci
            </li>
          ))}
        </ul>
        {cift !== null && (
          <p role="alert" className="text-body-small text-error">
            Okul No {cift} iki sınavın mazeretine birden seçildi; bir oturumda tek sınava girilir —
            bu dersleri ayrı mazeret sınavlarına alın.
          </p>
        )}
        {disari && (
          <p className="flex items-start gap-2 rounded-shape-sm bg-tertiary-container p-2 text-body-small text-on-tertiary-container">
            <Icon name="info" size="sm" className="mt-0.5 shrink-0" />
            Seçilenlerde ülke/il geneli sınav var: bu sınavların mazeret sınavı tarihi il millî
            eğitim müdürlüğünce ilan edilir; tarihi o ilana göre seçin.
          </p>
        )}
        <TextField
          label="Oturum adı"
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
        />
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label="Sınav tarihi"
            type="date"
            value={form.exam_date}
            onChange={(e) => setForm((f) => ({ ...f, exam_date: e.target.value }))}
            required
          />
          <TextField
            label="Başlangıç saati"
            type="time"
            value={form.start_time}
            onChange={(e) => setForm((f) => ({ ...f, start_time: e.target.value }))}
            required
          />
        </div>
        <TextField
          label="Süre (dk)"
          type="number"
          min={10}
          max={240}
          value={form.duration_minutes}
          onChange={(e) => setForm((f) => ({ ...f, duration_minutes: e.target.value }))}
          required
        />
      </div>
    </Dialog>
  );
}

export default function MazeretTakibiPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const [semester, setSemester] = useState<number | undefined>(undefined);
  const [filtre, setFiltre] = useState<Filtre>("ALL");
  const [secili, setSecili] = useState<Set<number>>(new Set());
  // Sekme adreste durur (`/mazeret?tab=takvim`): kılavuz ve oturum sayfası doğrudan bağlanır.
  const [tab, setTab] = useTabParam<TabKey>("tab", TABS, "kayitlar");
  const [dialogOpen, setDialogOpen] = useState(false);
  // Dialog odak efekti onClose kimliğine bağlı — inline arrow her render'da yenilenir
  // ve yazarken odağı geri çalar; sabit referans şart (OturumlarPage emsali).
  const closeDialog = useCallback(() => setDialogOpen(false), []);
  const [busy, setBusy] = useState<MakeupReportKind | null>(null);

  const absences = useQuery({
    queryKey: ["makeup-absences", semester ?? "varsayilan"],
    queryFn: () => makeupApi.absences(semester),
  });
  const data = absences.data;
  const rows = useMemo(() => data?.rows ?? [], [data]);
  const donemId = semester ?? data?.semester_id ?? undefined;
  const donemEtiketi = data?.semesters.find((s) => s.id === donemId)?.label ?? "";

  // Seçim yalnız hâlâ seçilebilir satırlardan oluşur (durum değişince kendiliğinden düşer).
  const seciliSatirlar = useMemo(
    () => rows.filter((r) => r.can_makeup && secili.has(r.record_id)),
    [rows, secili],
  );
  const gruplar = useMemo(() => gruplaSinavlar(rows.filter(FILTRE_UYGUN[filtre])), [rows, filtre]);

  const yenile = (row?: AbsenceRow) => {
    void qc.invalidateQueries({ queryKey: ["makeup-absences"] });
    if (row) void qc.invalidateQueries({ queryKey: ["exam-attendance", row.session_id] });
  };

  const remove = useMutation({
    mutationFn: (row: AbsenceRow) => makeupApi.remove([row.record_id]),
    onSuccess: (_sonuc, row) => {
      yenile();
      if (row.makeup_session_id !== null) {
        void qc.invalidateQueries({ queryKey: ["exam-participants", row.makeup_session_id] });
      }
      snackbar.success("Öğrenci mazeret sınavından çıkarıldı.");
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Çıkarılamadı."),
  });

  const toggle = (row: AbsenceRow) =>
    setSecili((prev) => {
      const next = new Set(prev);
      if (next.has(row.record_id)) next.delete(row.record_id);
      else next.add(row.record_id);
      return next;
    });

  // Süzgeç açıkken GÖRÜNMEYEN kayıt seçilmez (ekranda olmayan seçim şaşırtır).
  const bekleyenleriSec = () =>
    setSecili(
      new Set(
        gruplar
          .flatMap((g) => g.rows)
          .filter((r) => r.can_makeup)
          .map((r) => r.record_id),
      ),
    );

  const indir = async (kind: MakeupReportKind) => {
    if (donemId === undefined) return;
    setBusy(kind);
    try {
      const blob = await makeupApi.reportBlob(donemId, kind);
      saveBlob(blob, dosyaAdi([REPORT_FILE_TITLE, donemEtiketi.replace("·", "")], kind));
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Rapor üretilemedi.");
    } finally {
      setBusy(null);
    }
  };

  // Kayıtlar sekmesinin içeriği (takvim sekmesi ayrı bileşendir: MazeretTakvimi).
  const kayitlar = (
    <>
      <Select
        label="Göster"
        options={(Object.keys(FILTRE_TR) as Filtre[]).map((value) => ({
          value,
          label: FILTRE_TR[value],
        }))}
        value={filtre}
        onChange={(e) => setFiltre(e.target.value as Filtre)}
        className="w-72"
      />

      {absences.isPending && <SkeletonList rows={4} />}
      {absences.isError && (
        <Card elevation={1} className="p-6">
          <p role="alert" className="text-body-medium text-error">
            Mazeret listesi yüklenemedi:{" "}
            {absences.error instanceof ApiError ? absences.error.message : "beklenmeyen hata."}
          </p>
        </Card>
      )}

      {data && <OzetCipleri summary={data.summary} />}

      {rows.some((r) => r.can_makeup) && (
        <Card
          elevation={1}
          className="sticky top-20 z-20 flex flex-wrap items-center gap-3 bg-surface-container-lowest p-3"
        >
          <span className="text-body-medium text-on-surface">
            {seciliSatirlar.length} öğrenci seçildi
          </span>
          <Button variant="text" icon="done_all" onClick={bekleyenleriSec}>
            Bekleyenlerin tümünü seç
          </Button>
          {seciliSatirlar.length > 0 && (
            <Button variant="text" onClick={() => setSecili(new Set())}>
              Seçimi temizle
            </Button>
          )}
          <span className="ml-auto" />
          <Button
            icon="event_available"
            onClick={() => setDialogOpen(true)}
            disabled={seciliSatirlar.length === 0}
          >
            Mazeret sınavı oluştur
          </Button>
        </Card>
      )}

      {data && rows.length === 0 && (
        <EmptyState
          icon="event_busy"
          title="Bu dönemde sınava girmeyen öğrenci yok"
          description="Kayıtlar onaylanmış oturumların Yoklama sekmesinde işaretlenir; burada dönemin tamamı toplanır."
        />
      )}
      {data && rows.length > 0 && gruplar.length === 0 && (
        <p className="text-body-medium text-on-surface-variant">Bu süzgece uyan kayıt yok.</p>
      )}

      {gruplar.map((g) => (
        <Card key={g.key} elevation={1} className="flex flex-col gap-3 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-title-medium text-on-surface">
              {formatDate(g.examDate)} · {g.courseLabel}
            </h2>
            <Link
              to={`/oturumlar/${g.sessionId}`}
              className="text-body-small text-primary underline"
            >
              {g.sessionName}
            </Link>
            {g.external && (
              <span className="rounded-full bg-tertiary-container px-2 py-0.5 text-label-small text-on-tertiary-container">
                {g.typeLabel} geneli
              </span>
            )}
            {g.isMakeup && (
              <span className="rounded-full bg-tertiary-container px-2 py-0.5 text-label-small text-on-tertiary-container">
                Mazeret sınavı
              </span>
            )}
          </div>
          <ul className="flex flex-col gap-2">
            {g.rows.map((r) => (
              <KayitSatiri
                key={r.record_id}
                row={r}
                selected={secili.has(r.record_id)}
                onToggle={toggle}
                onChanged={yenile}
                onRemove={(row) => {
                  void confirm({
                    title: "Mazeret sınavından çıkarılsın mı?",
                    message:
                      "Öğrenci yeniden “mazeret sınavı bekleyen” olur. Dağıtılmış oturumda yerleşim kendiliğinden değişmez; oturum sayfası yeniden dağıtmanızı ister.",
                    confirmLabel: "Çıkar",
                  }).then((ok) => ok && remove.mutate(row));
                }}
                removeBusy={remove.isPending}
              />
            ))}
          </ul>
        </Card>
      ))}

      {dialogOpen && (
        <MazeretSinaviDialog
          open={dialogOpen}
          onClose={closeDialog}
          selectedRows={seciliSatirlar}
          onCreated={(sessionId) => {
            setDialogOpen(false);
            setSecili(new Set());
            yenile();
            void qc.invalidateQueries({ queryKey: ["exam-sessions"] });
            snackbar.success(
              "Mazeret sınavı oluşturuldu — sihirbazla salon ve dağıtımı tamamlayın.",
            );
            navigate(`/oturumlar/${sessionId}`);
          }}
        />
      )}
    </>
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-headline-medium text-on-surface">Mazeret Takibi</h1>
        <span className="ml-auto" />
        <Button
          variant="tonal"
          icon="picture_as_pdf"
          onClick={() => void indir("pdf")}
          disabled={busy !== null || donemId === undefined}
        >
          {busy === "pdf" ? "Hazırlanıyor…" : "Rapor (PDF)"}
        </Button>
        <Button
          variant="tonal"
          icon="table_view"
          onClick={() => void indir("xlsx")}
          disabled={busy !== null || donemId === undefined}
        >
          {busy === "xlsx" ? "Hazırlanıyor…" : "Rapor (Excel)"}
        </Button>
      </div>
      <p className="text-body-medium text-on-surface-variant">
        Dönemin sınavlarına girmeyen öğrenciler (oturumların Yoklama sekmesinde işaretlenenler).
        Mazeret belgesi sınav tarihinden itibaren en geç {data?.notice_business_days ?? 5} iş günü
        içinde okul müdürlüğüne bildirilir; süresi geçmiş kararsız kayıtlar işaretlenir — karar okul
        müdürlüğünündür. Mazereti kabul edilenleri seçip mazeret sınavı oluşturun ya da hepsi için
        “Mazeret Takvimi” sekmesinden takvim kurun; mazeret sınavı bir defaya mahsus yapılır.
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <Select
          label="Dönem"
          options={(data?.semesters ?? []).map((s) => ({ value: String(s.id), label: s.label }))}
          value={donemId === undefined ? "" : String(donemId)}
          onChange={(e) => {
            setSemester(Number(e.target.value));
            setSecili(new Set());
          }}
          className="w-64"
        />
      </div>

      <Tabs
        items={[
          { key: "kayitlar", label: "Kayıtlar", icon: "person_off" },
          { key: "takvim", label: "Mazeret Takvimi", icon: "event_note" },
        ]}
        active={tab}
        onChange={(key) => setTab(key as TabKey)}
        idBase="mazeret"
        ariaLabel="Mazeret takibi bölümleri"
      />
      <div {...tabPanelProps("mazeret", tab)} className="flex flex-col gap-4">
        {tab === "takvim" ? <MazeretTakvimi semesterId={donemId} /> : kayitlar}
      </div>
    </div>
  );
}
