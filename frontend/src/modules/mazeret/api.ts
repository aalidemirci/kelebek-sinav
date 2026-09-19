// Mazeret takibi API istemcisi (19.09.2026) — backend `apps/sinav/views_makeup.py`.
// Kaynak gerçek `services_makeup.absence_rows`: ekran ve rapor AYNI satırı kullanır.
// Mazeret durumu/notu güncellemesi yoklama ucundan geçer (`attendanceApi.update`);
// burada kopyası tutulmaz.

import { api } from "../../lib/api";
import type {
  ExamSession,
  ExamSessionStatusCode,
  ExamSessionTypeCode,
  ExcuseStatusCode,
} from "../oturumlar/api";

/** Mazeret sınavının sonucu — kaynak kaydın satırında görünür. */
export type MakeupResultCode = "absent" | "attended" | "pending";

export interface AbsenceRow {
  record_id: number;
  session_id: number;
  session_name: string;
  exam_date: string; // ISO — görüntü lib/format.ts::formatDate
  /** Kayıt bir mazeret sınavından: ikinci mazeret sınavı açılmaz. */
  session_is_makeup: boolean;
  session_type: ExamSessionTypeCode;
  session_type_label: string;
  /** Ülke/il/ilçe geneli sınav — il/ilçe MEM'e bildirim bölümüne girer. */
  external: boolean;
  course_id: number | null;
  level: number | null;
  course_label: string;
  student_id: number | null;
  student_number: string;
  full_name: string;
  class_label: string;
  excuse_status: ExcuseStatusCode;
  excuse_label: string;
  note: string;
  notice_deadline: string; // ISO
  /** Karar bekleyen kayıtta 5 iş günü geçti — UYARIDIR, engel değil. */
  notice_overdue: boolean;
  makeup_session_id: number | null;
  makeup_session_name: string;
  makeup_session_status: ExamSessionStatusCode | null;
  makeup_date: string | null;
  makeup_result: MakeupResultCode | null;
  makeup_result_label: string;
  /** Mazeretli, henüz mazeret sınavına alınmamış ve dersi çözülebilmiş. */
  can_makeup: boolean;
}

export interface AbsenceSummary {
  total: number;
  pending: number;
  excused: number;
  unexcused: number;
  overdue: number;
  awaiting_makeup: number;
  in_makeup: number;
}

export interface SemesterOption {
  id: number;
  label: string;
  default: boolean;
}

export interface AbsencesResponse {
  semester_id: number | null;
  semesters: SemesterOption[];
  rows: AbsenceRow[];
  summary: AbsenceSummary;
  notice_business_days: number;
}

export interface MakeupSessionPayload {
  record_ids: number[];
  name?: string;
  exam_date: string;
  start_time: string;
  duration_minutes?: number;
}

export type MakeupReportKind = "pdf" | "xlsx";

export const makeupApi = {
  absences: (semesterId?: number) =>
    api.get<AbsencesResponse>(
      `/makeup/absences/${semesterId !== undefined ? `?semester=${semesterId}` : ""}`,
    ),
  /** Seçilen "Mazeretli" kayıtlarla TASLAK mazeret sınavı oturumu açar. */
  createSession: (payload: MakeupSessionPayload) =>
    api.post<ExamSession>("/makeup/sessions/", payload),
  /** Kayıtları mazeret sınavından çıkarır (yapılmış sınavda backend reddeder). */
  remove: (recordIds: number[]) =>
    api.post<{ removed: number }>("/makeup/remove/", { record_ids: recordIds }),
  /** `kind` — `?format=` DRF içerik müzakeresine ayrılmıştır. */
  reportBlob: (semesterId: number, kind: MakeupReportKind) =>
    api.getBlob(`/makeup/report/?semester=${semesterId}&kind=${kind}`),
};
