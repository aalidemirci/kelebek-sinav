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
  /** Mazeretli ve henüz bir mazeret OTURUMUNA alınmamış (takvimde olsa da bekliyor). */
  awaiting_makeup: boolean;
  /** Mazeret TAKVİMİNE alınmışsa takvim bilgisi; oturumu takvimden üretilir. */
  plan_id: number | null;
  plan_name: string;
  plan_date: string | null;
  plan_period_no: number | null;
  /** Elle mazeret sınavına SEÇİLEBİLİR: bekliyor ve hiçbir takvime alınmamış. */
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

// ---------------------------------------------------------------------------
// Mazeret sınav takvimi (20.09.2026) — backend `views_makeup_plan.py`
// ---------------------------------------------------------------------------

export type MakeupPlanStatusCode = "DRAFT" | "APPROVED";

export interface PlanPeriod {
  no: number;
  name: string;
  start: string;
}

export interface MakeupPlanSummary {
  id: number;
  name: string;
  status: MakeupPlanStatusCode;
  status_label: string;
  start_date: string;
  day_count: number;
}

export interface MakeupPlanListResponse {
  semester_id: number | null;
  plans: MakeupPlanSummary[];
  all_periods: PlanPeriod[];
  default_period_nos: number[];
  /** Takvime alınmayı bekleyen "Mazeretli" kayıt sayısı. */
  eligible_count: number;
  max_day_count: number;
}

export interface MakeupPlanStudent {
  record_id: number;
  student_number: string;
  full_name: string;
  class_label: string;
}

export interface MakeupPlanItem {
  id: number;
  course_id: number;
  level: number;
  course_label: string;
  /** Asıl sınavın tarihi — takvim sırası bundan türer. */
  source_date: string;
  /** Ülke/il/ilçe geneli sınav: otomatik yerleşmez, elle sabitlenir. */
  external: boolean;
  placed_date: string | null;
  period_no: number | null;
  is_pinned: boolean;
  /** Yerleşemediyse gerekçesi (okul numarasıyla; ad yazılmaz). */
  note: string;
  student_count: number;
  students: MakeupPlanStudent[];
  session_id: number | null;
  session_name: string;
  session_status: ExamSessionStatusCode | null;
}

export interface MakeupPlan {
  id: number;
  name: string;
  semester_id: number;
  semester_label: string;
  status: MakeupPlanStatusCode;
  status_label: string;
  start_date: string;
  day_count: number;
  max_per_day: number;
  /** Boş = okulun sınav saatleri. */
  period_nos: number[];
  strict_order: boolean;
  approved_by_name: string;
  approved_at: string | null;
  days: { date: string; weekday_label: string }[];
  periods: PlanPeriod[];
  all_periods: PlanPeriod[];
  items: MakeupPlanItem[];
  /** ONAYI ENGELLER: aynı saatte iki sınava düşen öğrenci. */
  errors: string[];
  warnings: string[];
  /** Sığmayan sınav varsa: bu kurallarla gereken en az gün sayısı. */
  min_days: number | null;
  /** Takvimden sonra "Mazeretli" olan, takvime alınmamış kayıt sayısı. */
  unsynced_count: number;
}

export interface MakeupPlanParams {
  name?: string;
  start_date?: string;
  day_count?: number;
  max_per_day?: number;
  period_nos?: number[];
  strict_order?: boolean;
}

export type MakeupPlanPdfKind = "ilan" | "liste";

/** İşlem uçları takvimin güncel hâlini + işlemin kendi sonucunu döner. */
export type MakeupPlanResult<T> = MakeupPlan & { result: T };

export const makeupPlanApi = {
  list: (semesterId?: number) =>
    api.get<MakeupPlanListResponse>(
      `/makeup-plans/${semesterId !== undefined ? `?semester=${semesterId}` : ""}`,
    ),
  get: (id: number) => api.get<MakeupPlan>(`/makeup-plans/${id}/`),
  create: (
    payload: MakeupPlanParams & { semester_id: number; start_date: string; day_count: number },
  ) => api.post<MakeupPlan>("/makeup-plans/", payload),
  /** Parametreleri değiştirir ve sabit olmayan sınavları yeniden yerleştirir. */
  update: (id: number, payload: MakeupPlanParams) =>
    api.patch<MakeupPlan>(`/makeup-plans/${id}/`, payload),
  remove: (id: number) => api.del<void>(`/makeup-plans/${id}/`),
  replace: (id: number) =>
    api.post<MakeupPlanResult<{ placed: number; unplaced: number }>>(
      `/makeup-plans/${id}/replace/`,
    ),
  sync: (id: number) => api.post<MakeupPlanResult<{ added: number }>>(`/makeup-plans/${id}/sync/`),
  approve: (id: number, approvedByName: string) =>
    api.post<MakeupPlanResult<null>>(`/makeup-plans/${id}/approve/`, {
      approved_by_name: approvedByName,
    }),
  reopen: (id: number) => api.post<MakeupPlanResult<null>>(`/makeup-plans/${id}/reopen/`),
  createSessions: (id: number) =>
    api.post<MakeupPlanResult<{ created: string[]; skipped: string[] }>>(
      `/makeup-plans/${id}/sessions/`,
    ),
  pdfBlob: (id: number, kind: MakeupPlanPdfKind, names: boolean) =>
    api.getBlob(`/makeup-plans/${id}/pdf/?kind=${kind}&names=${names ? 1 : 0}`),
  /** `placed_date`/`period_no` null = takvim dışına al. */
  moveItem: (
    itemId: number,
    payload: { placed_date: string | null; period_no: number | null; is_pinned?: boolean },
  ) =>
    api.patch<MakeupPlanResult<{ warnings: string[] }>>(`/makeup-plan-items/${itemId}/`, payload),
  pinItem: (itemId: number, isPinned: boolean) =>
    api.patch<MakeupPlanResult<{ warnings: string[] }>>(`/makeup-plan-items/${itemId}/`, {
      is_pinned: isPinned,
    }),
  removeItem: (itemId: number) => api.del<MakeupPlan>(`/makeup-plan-items/${itemId}/`),
};
