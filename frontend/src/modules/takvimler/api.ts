// Sınav takvimi API istemcisi (backend apps/sinav views_calendar — F6).
// OYS sinav-islemleri api.ts takvim bölümünden UYARLA: auth katmanı yok
// (X-KS-Token authsuz istemci), `school_year` alanı dönem üzerinden okunur,
// onay damgası approved_by_name olarak döner (B12). Kod birlikleri backend
// TextChoices ile birebir; grid hücre anahtarı "tarih|saat|seviye" sözleşmesi
// FE + PDF ortaktır (CLAUDE.md §3 emsali — değiştirme).

import { api } from "../../lib/api";
import type { Paginated } from "../../lib/pagination";
// Katılımcı tipi oturum modülünün kod birliğidir (LEVEL | SECTIONS — TB7);
// takvim girdisi AYNI birliği kullanır, ikinci bir tanım açılmaz.
import type { ParticipantTypeCode } from "../oturumlar/api";

export type { Paginated, ParticipantTypeCode };

export type ExamCalendarStatusCode = "DRAFT" | "SUBMITTED" | "APPROVED";
export type ExamKindCode = "WRITTEN" | "PRACTICE";
export type ExamTrackStatusCode = "DONE" | "NOT_APPLICABLE";
/** Sınavı hazırlayan/yapan makam — backend ExamAuthority ile birebir. */
export type ExamAuthorityCode = "SCHOOL" | "MINISTRY" | "PROVINCIAL" | "DISTRICT";

export const CALENDAR_STATUS_TR: Record<ExamCalendarStatusCode, string> = {
  DRAFT: "Taslak",
  SUBMITTED: "Onaya Sunuldu",
  APPROVED: "Onaylandı",
};

export const EXAM_AUTHORITY_TR: Record<ExamAuthorityCode, string> = {
  SCHOOL: "Okul",
  MINISTRY: "Bakanlık",
  PROVINCIAL: "İl MEM",
  DISTRICT: "İlçe MEM",
};

/** Izgara hücresi dar — rozet kısaltması ("Okul" rozeti hiç basılmaz). */
export const EXAM_AUTHORITY_SHORT_TR: Record<ExamAuthorityCode, string> = {
  SCHOOL: "",
  MINISTRY: "BAK",
  PROVINCIAL: "İL",
  DISTRICT: "İLÇE",
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
  footnote_text: string;
  signatory_departments: number[];
  signatory_department_names: string[];
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
  authority: ExamAuthorityCode;
  /** Katılımcı kapsamı: seviye geneli mi, seçilen şubeler mi (CLAUDE.md §3). */
  participant_type: ParticipantTypeCode;
  /** SECTIONS kapsamında somut şube pk'leri — küme kimliği ASLA yazılmaz. */
  section_ids: number[];
  /** Backend'in hazır kapsam etiketi ("Seviye geneli" / "3 şube"). */
  participant_label: string;
  /** Kapsam ders havuzundaki tanımdan farklı mı (bilinçli istisna rozeti). */
  scope_differs_from_catalog: boolean;
  placed_date: string | null;
  period_no: number | null;
  /** Sabitlenmiş girdiyi otomatik yerleştirme yerinden oynatmaz. */
  is_pinned: boolean;
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
  /** Ayarlarda sınava açık işaretlenmiş saat mi (otomatik yerleştirme buraya bakar). */
  is_exam_period: boolean;
}

export interface CalendarGridCell {
  entry_id: number;
  course_id: number;
  course_name: string;
  level: number;
  exam_kind: ExamKindCode;
  is_butterfly: boolean;
  authority: ExamAuthorityCode;
  // Hücre anahtarı biçimi sabittir, sözlüğe alan eklenebilir (CLAUDE.md §3):
  // kapsam bilgisi havuz tablosu ile ızgarada AYNI kaynaktan okunur.
  participant_type: ParticipantTypeCode;
  section_ids: number[];
  participant_label: string;
  session_id: number | null;
  note: string;
  is_pinned: boolean;
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

/** Otomatik yerleştirme kipi: yalnız boşları doldur / sabitler hariç yeniden dağıt. */
export type AutoPlaceMode = "FILL" | "REDISTRIBUTE";

export interface AutoPlacedRow {
  entry_id: number;
  course_name: string;
  level: number;
  date: string;
  period_no: number;
}

export interface AutoSkippedRow {
  entry_id: number;
  course_name: string;
  level: number;
  reason: string;
}

/** Otomatik yerleştirme raporu — yerleşenler, atlananlar (gerekçeli), uyarılar. */
export interface AutoPlaceResult {
  placed: AutoPlacedRow[];
  skipped: AutoSkippedRow[];
  warnings: string[];
  /** REDISTRIBUTE kipinde havuza geri alınan sabitlenmemiş girdi sayısı. */
  cleared: number;
}

/** Havuzu katalogdan doldurma sonucu (etiket listeleri + toplam çift). */
export interface FillPoolResult {
  created: string[];
  existed: string[];
  skipped: string[];
  total_pairs: number;
}

/**
 * Toplu havuz girdisi kalemi — seçmeli ders dialog'unun tek yazma birimi.
 * Ders alanı `course_id`'dir (tekil `addEntry` gövdesindeki `course` DEĞİL —
 * ikisi ayrı backend yüzeyi, karıştırma).
 */
export interface BulkEntryItem {
  course_id: number;
  level: number;
  participant_type: ParticipantTypeCode;
  section_ids: number[];
  exam_kind?: ExamKindCode;
  is_butterfly?: boolean;
  authority?: ExamAuthorityCode;
}

/** Toplu ekleme sonucu — fill-pool ile aynı şekil, `total_pairs` yok. */
export interface BulkEntriesResult {
  created: string[];
  existed: string[];
  skipped: string[];
}

export interface ElectivePoolCourse {
  id: number;
  name: string;
  /** O takvimde canlı YAZILI girdisi var mı (işaretli + kilitli gösterilir). */
  in_pool: boolean;
  /**
   * Ders havuzunda girilmiş şube kapsamı — diyalog kutuları bununla ÖN DOLAR
   * (kaynak Ders Havuzu ekranıdır, 03.09.2026). Boşsa kapsam tanımsızdır.
   */
  default_section_ids: number[];
}

/** Seviye başına seçilebilir seçmeli dersler (ders adları backend'de TR sıralı). */
export interface ElectivePoolLevel {
  value: number;
  /** Izgara sütun başlığıyla aynı etiket ("9. Sınıf" / "Hazırlık"). */
  display_label: string;
  courses: ElectivePoolCourse[];
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
      footnote_text: string;
      signatory_departments: number[];
    }>,
  ) => api.patch<ExamCalendar>(`/exam-calendars/${id}/`, payload),
  remove: (id: number) => api.del<void>(`/exam-calendars/${id}/`),
  generateDefaults: (schoolYearId?: number) =>
    api.post<{ created: ExamCalendar[] }>("/exam-calendars/generate-defaults/", {
      school_year_id: schoolYearId,
    }),
  defaultDescription: () => api.get<{ text: string }>("/exam-calendars/default-description/"),
  defaultFootnote: () => api.get<{ text: string }>("/exam-calendars/default-footnote/"),
  fillPool: (id: number) => api.post<FillPoolResult>(`/exam-calendars/${id}/fill-pool/`, {}),
  entries: (id: number) =>
    api.get<{ results: ExamCalendarEntryRow[] }>(`/exam-calendars/${id}/entries/`),
  addEntry: (
    id: number,
    payload: {
      course: number;
      level: number;
      exam_kind?: ExamKindCode;
      is_butterfly?: boolean;
      authority?: ExamAuthorityCode;
      participant_type?: ParticipantTypeCode;
      section_ids?: number[];
    },
  ) => api.post<ExamCalendarEntryRow>(`/exam-calendars/${id}/entries/`, payload),
  /** Seçmeli ders seçimi TEK istekle yazılır (kalem başına savepoint backend'de). */
  bulkEntries: (id: number, items: BulkEntryItem[]) =>
    api.post<BulkEntriesResult>(`/exam-calendars/${id}/bulk-entries/`, { items }),
  // Uç `{"results": [...]}` zarfıyla döner (havuz listesiyle aynı kalıp);
  // tüketiciler düz dizi görür.
  electiveOptions: async (id: number): Promise<ElectivePoolLevel[]> => {
    const data = await api.get<{ results: ElectivePoolLevel[] }>(
      `/exam-calendars/${id}/elective-options/`,
    );
    return data.results ?? [];
  },
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
    payload: Partial<{
      is_butterfly: boolean;
      exam_kind: ExamKindCode;
      authority: ExamAuthorityCode;
      note: string;
      participant_type: ParticipantTypeCode;
      section_ids: number[];
    }>,
  ) => api.patch<ExamCalendarEntryRow>(`/exam-calendar-entries/${entryId}/`, payload),
  removeEntry: (entryId: number) => api.del<void>(`/exam-calendar-entries/${entryId}/`),
  placeEntry: (entryId: number, payload: { date: string; period_no: number }) =>
    api.post<{ entry: ExamCalendarEntryRow; warnings: string[] }>(
      `/exam-calendar-entries/${entryId}/place/`,
      payload,
    ),
  unplaceEntry: (entryId: number) =>
    api.post<ExamCalendarEntryRow>(`/exam-calendar-entries/${entryId}/unplace/`, {}),
  pinEntry: (entryId: number, isPinned: boolean) =>
    api.post<ExamCalendarEntryRow>(`/exam-calendar-entries/${entryId}/pin/`, {
      is_pinned: isPinned,
    }),
  /** Havuzda bekleyenleri kurallara uyarak ızgaraya dağıtır (F6 eki-2). */
  autoPlace: (id: number, mode: AutoPlaceMode) =>
    api.post<AutoPlaceResult>(`/exam-calendars/${id}/auto-place/`, { mode }),
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
