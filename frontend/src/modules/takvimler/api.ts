// Sınav takvimi API istemcisi (backend apps/sinav views_calendar — F6).
// OYS sinav-islemleri api.ts takvim bölümünden UYARLA: auth katmanı yok
// (X-KS-Token authsuz istemci), `school_year` alanı dönem üzerinden okunur,
// onay damgası approved_by_name olarak döner (B12). Kod birlikleri backend
// TextChoices ile birebir; grid hücre anahtarı "tarih|saat|seviye" sözleşmesi
// FE + PDF ortaktır (CLAUDE.md §3 emsali — değiştirme).

import { api } from "../../lib/api";
import type { Paginated } from "../../lib/pagination";

export type { Paginated };

export type ExamCalendarStatusCode = "DRAFT" | "SUBMITTED" | "APPROVED";
export type ExamKindCode = "WRITTEN" | "PRACTICE";
export type ExamTrackStatusCode = "DONE" | "NOT_APPLICABLE";

export const CALENDAR_STATUS_TR: Record<ExamCalendarStatusCode, string> = {
  DRAFT: "Taslak",
  SUBMITTED: "Onaya Sunuldu",
  APPROVED: "Onaylandı",
};

export interface ExamCalendar {
  id: number;
  school_year_name: string;
  semester: number;
  semester_name: string;
  round: number;
  name: string;
  start_date: string;
  end_date: string;
  status: ExamCalendarStatusCode;
  description_text: string;
  submitted_at: string | null;
  approved_by_name: string;
  approved_at: string | null;
}

export interface ExamCalendarEntryRow {
  id: number;
  calendar: number;
  course: number;
  course_name: string;
  level: number;
  exam_kind: ExamKindCode;
  is_butterfly: boolean;
  placed_date: string | null;
  period_no: number | null;
  session: number | null;
  note: string;
}

export interface CalendarGridLevel {
  value: number;
  label: string;
  /** Sütun başlığı için hazır görüntü etiketi ("9. Sınıf" / "Hazırlık"). */
  display_label: string;
  student_count: number;
}

export interface CalendarGridPeriod {
  no: number;
  name: string;
  start: string;
}

export interface CalendarGridCell {
  entry_id: number;
  course_id: number;
  course_name: string;
  level: number;
  exam_kind: ExamKindCode;
  is_butterfly: boolean;
  session_id: number | null;
  note: string;
}

export interface CalendarGridDay {
  date: string;
  is_weekend: boolean;
  weekday: number;
}

export interface CalendarGrid {
  calendar: {
    id: number;
    name: string;
    status: ExamCalendarStatusCode;
    start_date: string;
    end_date: string;
  };
  levels: CalendarGridLevel[];
  periods: CalendarGridPeriod[];
  days: CalendarGridDay[];
  cells: Record<string, CalendarGridCell[]>;
  unplaced: CalendarGridCell[];
  errors: string[];
  warnings: string[];
}

/** Havuzu katalogdan doldurma sonucu (etiket listeleri + toplam çift). */
export interface FillPoolResult {
  created: string[];
  existed: string[];
  skipped: string[];
  total_pairs: number;
}

export interface ExamTrackItemRow {
  id: number;
  name: string;
  description: string;
  order: number;
  is_active: boolean;
}

export interface ExamTrackCell {
  item_id: number;
  status: ExamTrackStatusCode | null;
  note?: string;
  marked_by_name?: string;
  marked_at?: string;
}

export interface ExamTrackRow {
  entry_id: number;
  course_name: string;
  level: number;
  exam_kind: ExamKindCode;
  cells: ExamTrackCell[];
}

export interface ExamTrackMatrix {
  items: { id: number; name: string; description: string; order: number }[];
  rows: ExamTrackRow[];
}

export const examCalendarApi = {
  list: (params: { school_year?: number; semester?: number; status?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.school_year) qs.set("school_year", String(params.school_year));
    if (params.semester) qs.set("semester", String(params.semester));
    if (params.status) qs.set("status", params.status);
    const s = qs.toString();
    return api.get<Paginated<ExamCalendar>>(`/exam-calendars/${s ? `?${s}` : ""}`);
  },
  get: (id: number) => api.get<ExamCalendar>(`/exam-calendars/${id}/`),
  create: (payload: {
    semester: number;
    round: number;
    start_date: string;
    end_date: string;
    name?: string;
  }) => api.post<ExamCalendar>("/exam-calendars/", payload),
  update: (
    id: number,
    payload: Partial<{
      name: string;
      start_date: string;
      end_date: string;
      description_text: string;
    }>,
  ) => api.patch<ExamCalendar>(`/exam-calendars/${id}/`, payload),
  remove: (id: number) => api.del<void>(`/exam-calendars/${id}/`),
  generateDefaults: (schoolYearId?: number) =>
    api.post<{ created: ExamCalendar[] }>("/exam-calendars/generate-defaults/", {
      school_year_id: schoolYearId,
    }),
  defaultDescription: () => api.get<{ text: string }>("/exam-calendars/default-description/"),
  fillPool: (id: number) => api.post<FillPoolResult>(`/exam-calendars/${id}/fill-pool/`, {}),
  entries: (id: number) =>
    api.get<{ results: ExamCalendarEntryRow[] }>(`/exam-calendars/${id}/entries/`),
  addEntry: (
    id: number,
    payload: { course: number; level: number; exam_kind?: ExamKindCode; is_butterfly?: boolean },
  ) => api.post<ExamCalendarEntryRow>(`/exam-calendars/${id}/entries/`, payload),
  grid: (id: number) => api.get<CalendarGrid>(`/exam-calendars/${id}/grid/`),
  participantPreview: (id: number) =>
    api.get<Record<string, { student_count: number; whole: boolean; groups: string[] }>>(
      `/exam-calendars/${id}/participant-preview/`,
    ),
  submit: (id: number) => api.post<ExamCalendar>(`/exam-calendars/${id}/submit/`, {}),
  approve: (id: number) => api.post<ExamCalendar>(`/exam-calendars/${id}/approve/`, {}),
  reopen: (id: number) => api.post<ExamCalendar>(`/exam-calendars/${id}/reopen/`, {}),
  pdfBlob: (id: number) => api.getBlob(`/exam-calendars/${id}/pdf/`),
  createSession: (id: number, payload: { date: string; period_no: number }) =>
    api.post<{ session_id: number; name: string }>(
      `/exam-calendars/${id}/create-session/`,
      payload,
    ),
  track: (id: number) => api.get<ExamTrackMatrix>(`/exam-calendars/${id}/track/`),
  setTrackMark: (
    id: number,
    payload: {
      entry_id: number;
      item_id: number;
      status: ExamTrackStatusCode | null;
      note?: string;
    },
  ) => api.post<{ cell: ExamTrackCell }>(`/exam-calendars/${id}/track/mark/`, payload),
  patchEntry: (
    entryId: number,
    payload: Partial<{ is_butterfly: boolean; exam_kind: ExamKindCode; note: string }>,
  ) => api.patch<ExamCalendarEntryRow>(`/exam-calendar-entries/${entryId}/`, payload),
  removeEntry: (entryId: number) => api.del<void>(`/exam-calendar-entries/${entryId}/`),
  placeEntry: (entryId: number, payload: { date: string; period_no: number }) =>
    api.post<{ entry: ExamCalendarEntryRow; warnings: string[] }>(
      `/exam-calendar-entries/${entryId}/place/`,
      payload,
    ),
  unplaceEntry: (entryId: number) =>
    api.post<ExamCalendarEntryRow>(`/exam-calendar-entries/${entryId}/unplace/`, {}),
};

export const examTrackItemApi = {
  list: (includeInactive = false) =>
    api.get<Paginated<ExamTrackItemRow>>(
      `/exam-track-items/?limit=200${includeInactive ? "&include_inactive=true" : ""}`,
    ),
  create: (payload: { name: string; description?: string }) =>
    api.post<ExamTrackItemRow>("/exam-track-items/", payload),
  update: (
    id: number,
    payload: Partial<{ name: string; description: string; is_active: boolean }>,
  ) => api.patch<ExamTrackItemRow>(`/exam-track-items/${id}/`, payload),
  remove: (id: number) => api.del<void>(`/exam-track-items/${id}/`),
};
