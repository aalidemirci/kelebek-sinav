// Sınav Oturumları sayfası (F3): liste + yeni oturum diyaloğu (sihirbaz Adım 1
// bilgileri). OYS T11 OturumlarPage'den UYARLANDI:
// - dönem alanı `term_id` + `terms` ucu (OYS `semester_*` değil);
// - gözetmen anahtarı (`proctors_enabled`) F7 ile geldi (U2 — varsayılan
//   kapalı); yeni oturum diyaloğunda ve sihirbaz Adım 1'de açılabilir;
// - rota kökü `/oturumlar` (modül öneki yok — App.tsx route ağacı).
// Durum rozeti + tarih biçimi ./oturumEtiket'te (detay sayfasıyla ortak).
// M3 token'ları — ham renk/px yok.

import { useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Dialog from "../../ui/Dialog";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import TextField from "../../ui/TextField";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { LayoutModeCode } from "./api";
import { examSessionApi, LAYOUT_MODE_TR } from "./api";
import { formatDate, StatusBadge } from "./oturumEtiket";

export default function OturumlarPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const snackbar = useSnackbar();
  const [createOpen, setCreateOpen] = useState(false);
  // Dialog odak efekti onClose kimliğine bağlı — inline arrow her render'da
  // yenilenir ve yazarken odağı panele geri çalar; sabit referans şart.
  const closeCreate = useCallback(() => setCreateOpen(false), []);
  const [form, setForm] = useState({
    name: "",
    exam_date: "",
    start_time: "09:00",
    duration_minutes: "40",
    layout_mode: "BUTTERFLY" as LayoutModeCode,
    proctors_enabled: false,
    term_id: "",
  });

  const sessions = useQuery({ queryKey: ["exam-sessions"], queryFn: () => examSessionApi.list() });
  // Dönem seçici: aktif ders yılının dönemleri (backend terms ucu).
  const terms = useQuery({ queryKey: ["exam-terms"], queryFn: examSessionApi.terms });

  const create = useMutation({
    mutationFn: () =>
      examSessionApi.create({
        name: form.name.trim(),
        exam_date: form.exam_date,
        start_time: form.start_time,
        duration_minutes: Number(form.duration_minutes),
        layout_mode: form.layout_mode,
        proctors_enabled: form.proctors_enabled,
        term_id: Number(form.term_id),
      }),
    onSuccess: (session) => {
      void qc.invalidateQueries({ queryKey: ["exam-sessions"] });
      snackbar.success("Oturum oluşturuldu — sihirbazla planlamaya devam edin.");
      navigate(`/oturumlar/${session.id}`);
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Oturum oluşturulamadı."),
  });

  const canCreate =
    form.name.trim() !== "" &&
    form.exam_date !== "" &&
    form.start_time !== "" &&
    form.term_id !== "" &&
    Number(form.duration_minutes) > 0;

  const list = sessions.data?.results ?? [];

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="text-headline-medium text-on-surface">Sınav Oturumları</h1>
        <span className="ml-auto" />
        <Button icon="add" onClick={() => setCreateOpen(true)}>
          Yeni sınav oturumu
        </Button>
      </div>
      <p className="mb-4 text-body-medium text-on-surface-variant">
        Oturum, ortak sınavın planıdır: taslakta sihirbazla kurulur, dağıtım sonrası yerleşim
        incelenir, onayla kilitlenir ve arşivle kapanır.
      </p>

      {sessions.isPending && <SkeletonList rows={4} />}
      {sessions.isError && (
        <Card elevation={1} className="p-6">
          <p role="alert" className="text-body-medium text-error">
            Oturumlar yüklenemedi:{" "}
            {sessions.error instanceof ApiError ? sessions.error.message : "beklenmeyen hata."}
          </p>
        </Card>
      )}
      {sessions.isSuccess && list.length === 0 && (
        <Card elevation={1} className="p-6">
          <p className="text-body-medium text-on-surface-variant">
            Henüz sınav oturumu yok. &quot;Yeni sınav oturumu&quot; ile sihirbazı başlatın.
          </p>
        </Card>
      )}

      <ul className="flex flex-col gap-2">
        {list.map((session) => (
          <li key={session.id}>
            <button
              type="button"
              onClick={() => navigate(`/oturumlar/${session.id}`)}
              className="group relative block w-full overflow-hidden rounded-shape-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
            >
              <Card elevation={1} className="flex flex-wrap items-center gap-3 p-4">
                <span aria-hidden="true" className="state-layer" />
                <Icon name="quiz" aria-hidden="true" className="text-on-surface-variant" />
                <span className="text-title-medium text-on-surface">{session.name}</span>
                <span className="text-body-medium text-on-surface-variant">
                  {formatDate(session.exam_date)} · {session.start_time.slice(0, 5)} ·{" "}
                  {LAYOUT_MODE_TR[session.layout_mode]}
                </span>
                <span className="ml-auto flex items-center gap-2">
                  <StatusBadge status={session.status} />
                </span>
              </Card>
            </button>
          </li>
        ))}
      </ul>

      <Dialog
        open={createOpen}
        onClose={closeCreate}
        title="Yeni sınav oturumu"
        actions={
          <>
            <Button variant="text" onClick={closeCreate}>
              Vazgeç
            </Button>
            <Button onClick={() => create.mutate()} disabled={create.isPending || !canCreate}>
              Oluştur
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <TextField
            label="Oturum adı"
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            placeholder="Örn. 2. Dönem 1. Ortak Sınav"
            required
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
          <div className="grid grid-cols-2 gap-3">
            <TextField
              label="Süre (dk)"
              type="number"
              min={10}
              max={240}
              value={form.duration_minutes}
              onChange={(e) => setForm((f) => ({ ...f, duration_minutes: e.target.value }))}
              required
            />
            <Select
              label="Dönem"
              options={(terms.data?.terms ?? []).map((t) => ({
                value: String(t.id),
                label: t.label,
              }))}
              placeholder="Seçin"
              value={form.term_id}
              onChange={(e) => setForm((f) => ({ ...f, term_id: e.target.value }))}
              required
            />
          </div>
          <Select
            label="Düzen"
            options={[
              { value: "BUTTERFLY", label: "Kelebek (karışık dağıtım)" },
              { value: "HOME_CLASSROOM", label: "Kendi dersliğinde (klasik)" },
            ]}
            value={form.layout_mode}
            onChange={(e) =>
              setForm((f) => ({ ...f, layout_mode: e.target.value as LayoutModeCode }))
            }
          />
          <label className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
            <input
              type="checkbox"
              className="h-5 w-5 accent-primary"
              checked={form.proctors_enabled}
              onChange={(e) => setForm((f) => ({ ...f, proctors_enabled: e.target.checked }))}
            />
            Gözetmen modülü açık (görevlendirme + R6 belgesi)
          </label>
        </div>
      </Dialog>
    </div>
  );
}
