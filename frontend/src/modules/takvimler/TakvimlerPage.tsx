// Sınav Takvimi listesi (F6) — OYS TakvimlerPage'den UYARLA: rol/salt-okunur
// dalları düştü (tek kullanıcı idaredir — B2), rota kökü `/takvimler`, dönem
// seçici oturumlar modülünün `terms` ucundan. Ön tanımlı üretim + yeni takvim
// + durum/dönem filtreleri korunur. M3 token'ları — ham renk/px yok.

import { useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import DataTable from "../../ui/DataTable";
import Dialog from "../../ui/Dialog";
import EmptyState from "../../ui/EmptyState";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import TextField from "../../ui/TextField";
import { useConfirm } from "../../ui/ConfirmProvider";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { examSessionApi } from "../oturumlar/api";
import { formatDate } from "../oturumlar/oturumEtiket";
import type { ExamCalendar, ExamCalendarStatusCode } from "./api";
import { CALENDAR_STATUS_TR, examCalendarApi } from "./api";

const STATUS_BADGE: Record<ExamCalendarStatusCode, string> = {
  DRAFT: "bg-surface-container-high text-on-surface-variant",
  SUBMITTED: "bg-secondary-container text-on-secondary-container",
  APPROVED: "bg-primary-container text-on-primary-container",
};

export function CalendarStatusBadge({ status }: { status: ExamCalendarStatusCode }) {
  return (
    <span className={`rounded-full px-3 py-1 text-label-small ${STATUS_BADGE[status]}`}>
      {CALENDAR_STATUS_TR[status]}
    </span>
  );
}

export default function TakvimlerPage() {
  const navigate = useNavigate();
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const closeCreate = useCallback(() => setCreateOpen(false), []);
  const [statusFilter, setStatusFilter] = useState("");
  const [semesterFilter, setSemesterFilter] = useState("");

  const terms = useQuery({ queryKey: ["exam-terms"], queryFn: examSessionApi.terms });
  const calendarsQuery = useQuery({
    queryKey: ["exam-calendars", statusFilter, semesterFilter],
    queryFn: () =>
      examCalendarApi.list({
        status: statusFilter || undefined,
        semester: semesterFilter ? Number(semesterFilter) : undefined,
      }),
  });
  const invalidate = () => void queryClient.invalidateQueries({ queryKey: ["exam-calendars"] });

  const generateMutation = useMutation({
    mutationFn: () => examCalendarApi.generateDefaults(),
    onSuccess: (data) => {
      snackbar.success(`${data.created.length} ön tanımlı takvim üretildi.`);
      invalidate();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Takvimler üretilemedi."),
  });

  const handleGenerate = () => {
    void confirm({
      title: "Ön tanımlı takvimleri üret",
      message:
        "Aktif ders yılının dönemleri için mevzuat pencerelerine göre sınav takvimi " +
        "taslakları üretilecek ve havuzları ders kataloğundan doldurulacak. " +
        "Var olan takvimler atlanır.",
      confirmLabel: "Üret",
    }).then((ok) => ok && generateMutation.mutate());
  };

  const calendars = calendarsQuery.data?.results ?? [];

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <h1 className="text-headline-medium text-on-surface">Sınav Takvimi</h1>
        <span className="ml-auto" />
        <div className="w-56">
          <Select
            label="Dönem"
            options={[
              { value: "", label: "Tümü" },
              ...(terms.data?.terms ?? []).map((t) => ({
                value: String(t.id),
                label: t.label,
              })),
            ]}
            value={semesterFilter}
            onChange={(e) => setSemesterFilter(e.target.value)}
          />
        </div>
        <div className="w-44">
          <Select
            label="Durum"
            options={[
              { value: "", label: "Tümü" },
              { value: "DRAFT", label: "Taslak" },
              { value: "SUBMITTED", label: "Onaya Sunuldu" },
              { value: "APPROVED", label: "Onaylandı" },
            ]}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          />
        </div>
        <Button
          variant="tonal"
          icon="auto_awesome"
          disabled={generateMutation.isPending}
          onClick={handleGenerate}
        >
          Ön Tanımlı Takvimleri Üret
        </Button>
        <Button icon="add" onClick={() => setCreateOpen(true)}>
          Yeni takvim
        </Button>
      </div>

      {calendarsQuery.isPending ? (
        <SkeletonList rows={5} />
      ) : calendars.length === 0 ? (
        <EmptyState
          icon="event_note"
          title="Henüz sınav takvimi yok"
          description="Ön tanımlı takvimleri üretin veya yeni takvim ekleyin."
          action={
            <Button icon="auto_awesome" onClick={handleGenerate}>
              Ön Tanımlı Takvimleri Üret
            </Button>
          }
        />
      ) : (
        <DataTable
          rows={calendars}
          rowLabel={(c) => `${c.name} takvimi`}
          onRowClick={(c) => navigate(`/takvimler/${c.id}`)}
          columns={[
            { header: "Takvim", cell: (c) => c.name },
            { header: "Dönem", cell: (c) => c.semester_name },
            {
              header: "Tarih",
              cell: (c) => `${formatDate(c.start_date)} – ${formatDate(c.end_date)}`,
            },
            {
              header: "Durum",
              cell: (c: ExamCalendar) => <CalendarStatusBadge status={c.status} />,
            },
          ]}
        />
      )}

      {createOpen ? (
        <CreateDialog
          onClose={closeCreate}
          onCreated={(id) => {
            setCreateOpen(false);
            invalidate();
            navigate(`/takvimler/${id}`);
          }}
        />
      ) : null}
    </div>
  );
}

function CreateDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (id: number) => void;
}) {
  const snackbar = useSnackbar();
  const terms = useQuery({ queryKey: ["exam-terms"], queryFn: examSessionApi.terms });
  const [semester, setSemester] = useState("");
  const [round, setRound] = useState("1");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const createMutation = useMutation({
    mutationFn: () =>
      examCalendarApi.create({
        semester: Number(semester),
        round: Number(round),
        start_date: startDate,
        end_date: endDate,
      }),
    onSuccess: (cal) => onCreated(cal.id),
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Takvim oluşturulamadı."),
  });

  const semesterOptions = (terms.data?.terms ?? []).map((t) => ({
    value: String(t.id),
    label: t.label,
  }));

  return (
    <Dialog
      open
      onClose={onClose}
      title="Yeni Sınav Takvimi"
      actions={
        <>
          <Button variant="text" onClick={onClose}>
            Vazgeç
          </Button>
          <Button
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending || !semester || !startDate || !endDate}
          >
            Oluştur
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Select
          label="Dönem"
          placeholder="Dönem seçin…"
          options={semesterOptions}
          value={semester}
          onChange={(e) => setSemester(e.target.value)}
        />
        <Select
          label="Sınav turu"
          options={[
            { value: "1", label: "1. Sınav" },
            { value: "2", label: "2. Sınav" },
            { value: "3", label: "3. Sınav (haftalık ≥6 saat)" },
          ]}
          value={round}
          onChange={(e) => setRound(e.target.value)}
        />
        <TextField
          label="Başlangıç tarihi"
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
        />
        <TextField
          label="Bitiş tarihi"
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
        />
      </div>
    </Dialog>
  );
}
