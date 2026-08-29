// Sınav Yoklaması (F3) — OYS Tur 245 panelinden UYARLANDI: ONAYLI/ARŞİV
// oturumda sınava GİRMEYEN öğrenciler işaretlenir; mazeret durumu
// (Beklemede/Özürlü/Özürsüz) + belge notu (no/tarih — dosya yüklenmez) izlenir.
// Mazeret güncellemesi ARŞİVDE DE açıktır (belge sınavdan sonra 5 iş günü
// içinde veliden gelir — MEB yazılı/uygulamalı sınavlar yönergesi). Durum
// kapısı backend'dedir; panel yalnız sunar.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import TextField from "../../ui/TextField";
import { useConfirm } from "../../ui/ConfirmProvider";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { ExamAttendanceRecordRow, ExamSession, ExcuseStatusCode } from "./api";
import { attendanceApi, examSessionApi, EXCUSE_STATUS_TR } from "./api";

/** Mazeret durumu → tonal çip rengi (M3 token — ham renk yok). */
const EXCUSE_TONES: Record<ExcuseStatusCode, string> = {
  PENDING: "bg-surface-container-high text-on-surface",
  EXCUSED: "bg-primary-container text-on-primary-container",
  UNEXCUSED: "bg-error-container text-on-error-container",
};

function AbsentRecordRow({
  record,
  onChanged,
}: {
  record: ExamAttendanceRecordRow;
  onChanged: () => void;
}) {
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const [note, setNote] = useState(record.note);

  const update = useMutation({
    mutationFn: (payload: { excuse_status?: ExcuseStatusCode; note?: string }) =>
      attendanceApi.update(record.id, payload),
    onSuccess: () => {
      onChanged();
      snackbar.success("Mazeret kaydı güncellendi.");
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Güncellenemedi."),
  });
  const remove = useMutation({
    mutationFn: () => attendanceApi.remove(record.id),
    onSuccess: () => {
      onChanged();
      snackbar.success("İşaret kaldırıldı.");
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Kaldırılamadı."),
  });

  return (
    <li className="flex flex-wrap items-center gap-3 rounded-shape-md border border-outline-variant p-3">
      <span className="text-title-small text-on-surface">{record.full_name}</span>
      <span className="text-body-small text-on-surface-variant">
        {record.student_number} · {record.class_label} · {record.room_name} #{record.seat_no}
      </span>
      <span
        className={`rounded-full px-3 py-1 text-label-small ${EXCUSE_TONES[record.excuse_status]}`}
      >
        {EXCUSE_STATUS_TR[record.excuse_status]}
      </span>
      <span className="ml-auto" />
      <Select
        label=""
        aria-label={`${record.full_name} mazeret durumu`}
        options={Object.entries(EXCUSE_STATUS_TR).map(([value, label]) => ({ value, label }))}
        value={record.excuse_status}
        onChange={(e) => update.mutate({ excuse_status: e.target.value as ExcuseStatusCode })}
        className="w-40"
      />
      <div className="w-72">
        <TextField
          label=""
          aria-label={`${record.full_name} mazeret notu`}
          placeholder="Belge no/tarih (örn. Rapor no 123, 10.06.2026)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          onBlur={() => note !== record.note && update.mutate({ note })}
        />
      </div>
      <Button
        variant="text"
        icon="undo"
        onClick={() => {
          void confirm({
            title: "İşaret kaldırılsın mı?",
            message: "Öğrenci sınava girmiş sayılacak; yoklama kaydı kaldırılır.",
            confirmLabel: "Kaldır",
          }).then((ok) => ok && remove.mutate());
        }}
        disabled={remove.isPending}
      >
        İşareti kaldır
      </Button>
    </li>
  );
}

export default function YoklamaPaneli({ session }: { session: ExamSession }) {
  const snackbar = useSnackbar();
  const qc = useQueryClient();

  const seating = useQuery({
    queryKey: ["exam-seating", session.id],
    queryFn: () => examSessionApi.seating(session.id),
  });
  const records = useQuery({
    queryKey: ["exam-attendance", session.id],
    queryFn: () => attendanceApi.list(session.id),
  });

  const refresh = () => void qc.invalidateQueries({ queryKey: ["exam-attendance", session.id] });

  const mark = useMutation({
    mutationFn: (seatAssignmentId: number) =>
      attendanceApi.mark({ session_id: session.id, seat_assignment_id: seatAssignmentId }),
    onSuccess: () => {
      refresh();
      snackbar.success("Girmedi olarak işaretlendi — mazeret durumu beklemede.");
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "İşaretlenemedi."),
  });

  if (seating.isPending || records.isPending) {
    return <SkeletonList rows={3} />;
  }
  if (seating.isError || records.isError) {
    return (
      <p role="alert" className="text-body-medium text-error">
        Yoklama yüklenemedi.
      </p>
    );
  }

  const recordRows = records.data?.results ?? [];
  const absentStudentIds = new Set(recordRows.map((r) => r.student_id));
  const rooms = seating.data?.rooms ?? [];

  return (
    <div className="flex flex-col gap-4">
      <p className="text-body-small text-on-surface-variant">
        Sınava girmeyen öğrenciyi salon listesinden işaretleyin. Mazeret belgesi (veli yazısı,
        rapor) sınav tarihinden itibaren en geç 5 iş günü içinde okul müdürlüğüne bildirilir — belge
        no/tarihi nota yazın; durum arşivde de güncellenebilir.
      </p>

      <Card elevation={1} className="flex flex-col gap-3 p-4">
        <h3 className="text-title-medium text-on-surface">
          Sınava girmeyenler ({recordRows.length})
        </h3>
        {recordRows.length === 0 ? (
          <p className="text-body-medium text-on-surface-variant">
            İşaretli öğrenci yok — tüm katılımcılar sınava girmiş görünüyor.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {recordRows.map((r) => (
              <AbsentRecordRow key={r.id} record={r} onChanged={refresh} />
            ))}
          </ul>
        )}
      </Card>

      {rooms.map((room) => (
        <Card key={room.room_id} elevation={1} className="flex flex-col gap-2 p-4">
          <h3 className="text-title-small text-on-surface">{room.room_name}</h3>
          <ul className="flex flex-col gap-1">
            {room.assignments.map((a) => {
              // F27 anonim arşivde student_id null'dur — null asla eşleşmesin
              // (aksi hâlde tüm satırlar "Girmedi" görünürdü).
              const absent = a.student_id !== null && absentStudentIds.has(a.student_id);
              return (
                <li
                  key={a.id}
                  className={`flex flex-wrap items-center gap-3 rounded-shape-sm px-3 py-1 ${
                    absent ? "bg-error-container/40" : ""
                  }`}
                >
                  <span className="w-10 text-label-large text-on-surface-variant">
                    #{a.seat_no}
                  </span>
                  <span className="text-body-medium text-on-surface">{a.full_name}</span>
                  <span className="text-body-small text-on-surface-variant">
                    {a.student_number} · {a.class_label}
                  </span>
                  <span className="ml-auto" />
                  {absent ? (
                    <span className="text-label-small text-error">Girmedi</span>
                  ) : (
                    <Button
                      variant="text"
                      icon="person_off"
                      onClick={() => mark.mutate(a.id)}
                      disabled={mark.isPending}
                    >
                      Girmedi işaretle
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        </Card>
      ))}
    </div>
  );
}
