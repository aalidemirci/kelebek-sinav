// Sınav oturumları API istemcisi (backend apps/sinav — F3).
// OYS `sinav-islemleri/api.ts` oturum diliminden UYARLANMIŞTIR; kaynak gerçeği
// KS backend'idir (`apps/sinav/{serializers,views,urls}.py`):
// - `term_id`/`term_label` (OYS `semester_*` değil); dönem seçici `terms` ucu.
// - GROUPS katılımcı tipi ve `group_ids` YOK (TB7 — LEVEL + SECTIONS kaldı).
// - Gözetmen/soru dosyası/kitapçık/rapor/takvim uçları bu dilimde YOKTUR
//   (F3 kapsamı dışı — kasıtlı; rapor/evrak F4'te gelir).
// - PlacementRule uçları YENİdir (OYS FE'de hiç yoktu) — KVKK md. 6 notuna bak.
// Salon listesi için `examRoomApi` salonlar modülündedir (oradan import edilir,
// burada kopyası tutulmaz).

import { api } from "../../lib/api";
import type { Paginated } from "../../lib/pagination";

export type { Paginated };

// ---------------------------------------------------------------------------
// Kod birlikleri + Türkçe etiketler (backend TextChoices ile birebir)
// ---------------------------------------------------------------------------

export type LayoutModeCode = "BUTTERFLY" | "HOME_CLASSROOM";
export type ExamSessionStatusCode = "DRAFT" | "DISTRIBUTED" | "APPROVED" | "ARCHIVED";
export type ExamSessionTypeCode = "SCHOOL" | "DISTRICT" | "PROVINCE" | "NATIONAL";
export type ParticipantTypeCode = "LEVEL" | "SECTIONS";
export type SeatStatusCode = "NORMAL" | "PINNED" | "MANUAL";
export type ExcuseStatusCode = "PENDING" | "EXCUSED" | "UNEXCUSED";

export const LAYOUT_MODE_TR: Record<LayoutModeCode, string> = {
  BUTTERFLY: "Kelebek",
  HOME_CLASSROOM: "Kendi dersliğinde",
};

export const EXAM_SESSION_STATUS_TR: Record<ExamSessionStatusCode, string> = {
  DRAFT: "Taslak",
  DISTRIBUTED: "Dağıtıldı",
  APPROVED: "Onaylandı",
  ARCHIVED: "Arşiv",
};

export const EXAM_SESSION_TYPE_TR: Record<ExamSessionTypeCode, string> = {
  SCHOOL: "Okul",
  DISTRICT: "İlçe",
  PROVINCE: "İl",
  NATIONAL: "Ülke",
};

export const PARTICIPANT_TYPE_TR: Record<ParticipantTypeCode, string> = {
  LEVEL: "Seviye geneli",
  SECTIONS: "Şube şube",
};

export const EXCUSE_STATUS_TR: Record<ExcuseStatusCode, string> = {
  PENDING: "Beklemede",
  EXCUSED: "Özürlü",
  UNEXCUSED: "Özürsüz",
};

// ---------------------------------------------------------------------------
// Oturum tipleri (ExamSessionSerializer ile birebir)
// ---------------------------------------------------------------------------

/** Oturum dersi satırı — TEK seviyeli (Tur 241); `display_label` hazır gelir. */
export interface ExamSessionCourseRow {
  id: number;
  course_id: number;
  course_name: string;
  participant_type: ParticipantTypeCode;
  level: number | null;
  display_label: string;
  section_ids: number[];
  duration_minutes: number | null;
  shared_booklet: boolean;
}

export interface ExamSessionRoomRow {
  id: number;
  room_id: number;
  room_name: string;
  order: number;
  capacity_override: number | null;
}

export interface ExamSession {
  id: number;
  name: string;
  exam_date: string; // ISO yyyy-aa-gg (görüntü: lib/format.ts::formatDate)
  start_time: string; // "09:00:00"
  duration_minutes: number;
  session_type: ExamSessionTypeCode;
  layout_mode: LayoutModeCode;
  /** Gözetmen ayarı (K2) — R6 yalnız açıkken kataloglanır; atama F7'de. */
  proctors_enabled: boolean;
  term_id: number;
  term_label: string;
  status: ExamSessionStatusCode;
  transfer_check_confirmed_by_name: string;
  transfer_check_confirmed_at: string | null;
  approved_by_name: string;
  approved_at: string | null;
  courses: ExamSessionCourseRow[];
  rooms: ExamSessionRoomRow[];
}

export interface ExamSessionPayload {
  name?: string;
  exam_date?: string;
  start_time?: string;
  duration_minutes?: number;
  session_type?: ExamSessionTypeCode;
  layout_mode?: LayoutModeCode;
  term_id?: number;
}

/** `GET /exam-sessions/terms/` satırı — aktif ders yılının dönemleri. */
export interface TermOption {
  id: number;
  label: string;
}

/** Adım 0 verisi — sayılar + son öğrenci aktarımının tazeliği (PII yok).
 * OYS'deki e-Okul nakil hareket sorgusu KS'de YOK (B10 — beyan esaslı). */
export interface PreCheckSummary {
  active_students_by_level: Record<string, number>;
  last_student_import: { file_name: string; finished_at: string | null } | null;
}

export interface ParticipantRow {
  student_id: number;
  full_name: string;
  student_number: string;
  class_level: number;
  class_section: string;
  course_id: number;
  course_name: string;
  conflict_group: string;
}

export interface ParticipantsResponse {
  total_count: number;
  has_blocking_conflicts: boolean;
  warnings: string[];
  courses: {
    session_course_id: number;
    course_id: number;
    course_name: string;
    count: number;
    warnings: string[];
    participants: ParticipantRow[];
  }[];
}

// ---------------------------------------------------------------------------
// Yerleşim + doğrulama (views._report_payload ile birebir)
// ---------------------------------------------------------------------------

export interface ValidationReport {
  is_valid: boolean;
  hard_violations: string[];
  first_ring_same_group_pairs: number;
  min_same_group_distance: Record<string, number>;
  proximity_score: number;
  /** Aynı şubeden farklı-grup 1. halka komşu çifti (K1 gözlemlenebilirlik). */
  cross_group_same_section_first_ring_pairs: number;
  /** Salon id (string — JSON sözleşmesi) → yerleşen öğrenci sayısı. */
  room_counts: Record<string, number>;
}

/** Salon doluluk özeti (K1) — yerleşim paneli çipleri. */
export interface RoomOccupancyRow {
  room_id: number;
  room_name: string;
  capacity: number;
  placed: number;
  percent: number;
}

export interface SeatAssignmentRow {
  id: number;
  room_id: number;
  seat_no: number;
  desk_row: number;
  desk_col: number;
  slot: number;
  student_id: number | null; // F27: anonimleştirilmiş arşivde null
  full_name: string;
  student_number: string;
  class_label: string;
  conflict_group: string;
  status: SeatStatusCode;
}

export interface SeatingResponse {
  session_id: number;
  status: ExamSessionStatusCode;
  distribution_params: Record<string, unknown>;
  /** Grup anahtarı → insan-okur etiket ("Matematik — 9. Sınıf") — lejant. */
  conflict_group_labels: Record<string, string>;
  rooms: { room_id: number; room_name: string; assignments: SeatAssignmentRow[] }[];
  report: ValidationReport;
  occupancy: RoomOccupancyRow[];
}

export interface DistributeResult {
  status: ExamSessionStatusCode;
  seed: number;
  checkerboard: boolean;
  placed: number;
  warnings: string[];
  report: ValidationReport;
}

// --- Soru dosyası + kitapçık (F5) ---

export type ScoreModeCode = "SINGLE_BOX" | "QUESTION_TABLE";
export type BookletRunStatusCode = "PENDING" | "IN_PROGRESS" | "COMPLETED" | "FAILED";

export interface QuestionDocumentMeta {
  id: number;
  course_name: string;
  page_count: number;
  sha256: string;
  score_mode: ScoreModeCode;
  question_count: number | null;
  created_at: string;
}

export interface BookletRun {
  id: number;
  status: BookletRunStatusCode;
  backup_copies: number;
  manifest: Record<string, unknown>;
  error_message: string;
  created_at: string;
  completed_at: string | null;
}

/** Evrak paneli katalog satırı — kodlar backend REPORT_CODES ile birebir (OYS AYNEN). */
export const REPORT_CATALOG: { code: string; title: string; roomScoped: boolean }[] = [
  { code: "r1", title: "Salon Oturma Planı (kroki)", roomScoped: true },
  { code: "r2", title: "Salon Yoklama / İmza Listesi", roomScoped: true },
  { code: "r2k", title: "Şube Yoklama Listesi", roomScoped: false },
  { code: "r3", title: "Salon Kapı Listesi", roomScoped: true },
  { code: "r4", title: "Şube Duyuru Listesi", roomScoped: false },
  { code: "r5", title: "Toplu Dağıtım Çizelgesi (Excel)", roomScoped: false },
  { code: "r6", title: "Gözetmen Görevlendirme / Tebliğ-Tebellüğ", roomScoped: false },
  { code: "r7", title: "Sınav Evrak Zarfı Kapağı / Salon Tutanağı", roomScoped: true },
  { code: "r8", title: "Dağıtım Doğrulama Raporu", roomScoped: false },
  { code: "r9", title: "Evrak Teslim / Teslim Alma Tutanağı", roomScoped: false },
];

export const examSessionApi = {
  // Okul ölçeğinde oturum sayısı küçüktür; tek sayfada tümü (limit=100).
  list: (status?: ExamSessionStatusCode) =>
    api.get<Paginated<ExamSession>>(
      `/exam-sessions/?limit=100${status ? `&status=${status}` : ""}`,
    ),
  get: (id: number) => api.get<ExamSession>(`/exam-sessions/${id}/`),
  create: (
    payload: ExamSessionPayload & {
      name: string;
      exam_date: string;
      start_time: string;
      term_id: number;
    },
  ) => api.post<ExamSession>("/exam-sessions/", payload),
  update: (id: number, payload: ExamSessionPayload) =>
    api.patch<ExamSession>(`/exam-sessions/${id}/`, payload),
  remove: (id: number) => api.del<void>(`/exam-sessions/${id}/`),

  // --- Sihirbaz uçları ---
  terms: () => api.get<{ terms: TermOption[] }>("/exam-sessions/terms/"),
  preCheck: () => api.get<PreCheckSummary>("/exam-sessions/pre-check/"),
  /** Adım 0 beyan kutusu — kim/ne zaman oturuma yazılır (B10). */
  confirmTransferCheck: (id: number, payload: { confirmed_by_name?: string } = {}) =>
    api.post<ExamSession>(`/exam-sessions/${id}/confirm-transfer-check/`, payload),

  addCourse: (
    id: number,
    payload: {
      course_id: number;
      participant_type: ParticipantTypeCode;
      level?: number; // LEVEL tipinde zorunlu; SECTIONS'ta backend türetir
      section_ids?: number[];
      duration_minutes?: number | null;
      shared_booklet?: boolean;
    },
  ) => api.post<ExamSessionCourseRow>(`/exam-sessions/${id}/courses/`, payload),
  /** Ders satırı güncelleme — `course_id` değiştirilemez (çıkar + yeniden ekle). */
  updateCourse: (
    sessionCourseId: number,
    payload: {
      participant_type?: ParticipantTypeCode;
      level?: number | null;
      section_ids?: number[];
      duration_minutes?: number | null;
      shared_booklet?: boolean;
    },
  ) => api.patch<ExamSessionCourseRow>(`/exam-session-courses/${sessionCourseId}/`, payload),
  removeCourse: (sessionCourseId: number) =>
    api.del<void>(`/exam-session-courses/${sessionCourseId}/`),
  setRooms: (id: number, rooms: { room_id: number; capacity_override?: number | null }[]) =>
    api.put<{ rooms: ExamSessionRoomRow[] }>(`/exam-sessions/${id}/rooms/`, { rooms }),

  participants: (id: number) => api.get<ParticipantsResponse>(`/exam-sessions/${id}/participants/`),
  distribute: (id: number, payload: { seed?: number; strict?: boolean } = {}) =>
    api.post<DistributeResult>(`/exam-sessions/${id}/distribute/`, payload),
  seating: (id: number) => api.get<SeatingResponse>(`/exam-sessions/${id}/seating/`),
  swapSeats: (id: number, assignmentA: number, assignmentB: number) =>
    api.post<{ swapped: SeatAssignmentRow[]; report: ValidationReport }>(
      `/exam-sessions/${id}/swap-seats/`,
      { assignment_a: assignmentA, assignment_b: assignmentB },
    ),

  // --- Durum makinesi ---
  approve: (id: number, payload: { approved_by_name?: string } = {}) =>
    api.post<ExamSession>(`/exam-sessions/${id}/approve/`, payload),
  reopen: (id: number) => api.post<ExamSession>(`/exam-sessions/${id}/reopen/`),
  archive: (id: number) => api.post<ExamSession>(`/exam-sessions/${id}/archive/`),

  // --- Evrak (F4) — blob indirme; dosya adı panelde kurulur ---
  reportBlob: (id: number, code: string, roomId?: number) =>
    api.getBlob(`/exam-sessions/${id}/reports/${code}/${roomId ? `?room_id=${roomId}` : ""}`),
  reportsZipBlob: (id: number) => api.getBlob(`/exam-sessions/${id}/reports/zip/`),

  // --- Soru dosyası + kitapçık (F5) — üretim SENKRON (Celery yok) ---
  question: (sessionCourseId: number) =>
    api.get<QuestionDocumentMeta>(`/exam-session-courses/${sessionCourseId}/question/`),
  uploadQuestion: (sessionCourseId: number, form: FormData) =>
    api.postForm<QuestionDocumentMeta>(`/exam-session-courses/${sessionCourseId}/question/`, form),
  deleteQuestion: (sessionCourseId: number) =>
    api.del<void>(`/exam-session-courses/${sessionCourseId}/question/`),
  questionBlob: (sessionCourseId: number) =>
    api.getBlob(`/exam-session-courses/${sessionCourseId}/question/download/`),
  questionTemplateBlob: () => api.getBlob("/exam-sessions/question-template/"),
  startBookletRun: (id: number, backupCopies: number) =>
    api.post<BookletRun>(`/exam-sessions/${id}/booklets/`, { backup_copies: backupCopies }),
  bookletRuns: (id: number) =>
    api.get<Paginated<BookletRun>>(`/booklet-runs/?session=${id}&limit=10`),
  bookletRunZipBlob: (runId: number) => api.getBlob(`/booklet-runs/${runId}/download/`),
};

// ---------------------------------------------------------------------------
// Yerleştirme kuralları (OYS FE'de yoktu — PlacementRuleViewSet F3)
// ---------------------------------------------------------------------------
// ÖZEL NİTELİKLİ VERİYE İŞARET (KVKK md. 6): gerekçe YALNIZ kategoridir,
// serbest metin alanı BİLİNÇLE YOKTUR. Güncelleme ucu yok — kaldır + yeniden
// ekle (tarihsel iz). Oturum kuralı kalıcı kuralı ezer; kural sahibi öğrenci
// dağıtımda PINNED yerleşir.

export type RuleScope = "SESSION" | "PERMANENT";
export type RuleType = "HOME_CLASSROOM" | "FIXED_ROOM" | "FRONT_ROW" | "SEPARATE_ROOM";
export type RuleReason = "DISABILITY" | "IEP" | "HEALTH" | "OTHER";

export const RULE_SCOPE_TR: Record<RuleScope, string> = {
  SESSION: "Oturum",
  PERMANENT: "Kalıcı",
};

export const RULE_TYPE_TR: Record<RuleType, string> = {
  HOME_CLASSROOM: "Kendi dersliğinde",
  FIXED_ROOM: "Belirli salon",
  FRONT_ROW: "Ön sıra",
  SEPARATE_ROOM: "Ayrı salon",
};

export const RULE_REASON_TR: Record<RuleReason, string> = {
  DISABILITY: "Engel durumu",
  IEP: "BEP",
  HEALTH: "Sağlık",
  OTHER: "Diğer",
};

export interface PlacementRule {
  id: number;
  student_id: number | null; // F27: anonimleştirilmiş arşiv kuralında null
  student_name: string; // anonimleştirilmişte "—"
  scope: RuleScope;
  session_id: number | null; // PERMANENT kapsamda null
  rule_type: RuleType;
  target_room_id: number | null;
  target_room_name: string;
  reason_category: RuleReason;
}

export interface PlacementRulePayload {
  student_id: number;
  rule_type: RuleType;
  scope?: RuleScope; // varsayılan PERMANENT
  session_id?: number | null; // SESSION kapsamında zorunlu
  target_room_id?: number | null; // FIXED_ROOM için hedef salon
  reason_category?: RuleReason; // varsayılan OTHER
}

export const placementRuleApi = {
  // Kural sayısı küçüktür; tek sayfada tümü. `session` verilirse o oturumun
  // kuralları (oturum + geçerli kalıcılar — süzme selector'da).
  list: ({ session }: { session?: number } = {}) =>
    api.get<Paginated<PlacementRule>>(
      `/placement-rules/?limit=500${session ? `&session=${session}` : ""}`,
    ),
  create: (payload: PlacementRulePayload) => api.post<PlacementRule>("/placement-rules/", payload),
  remove: (id: number) => api.del<void>(`/placement-rules/${id}/`),
};

// ---------------------------------------------------------------------------
// Sınav yoklama kayıtları (girmedi + mazeret durumu)
// ---------------------------------------------------------------------------

export interface ExamAttendanceRecordRow {
  id: number;
  student_id: number | null; // F27: anonimleştirilmiş arşivde null
  full_name: string;
  student_number: string;
  class_label: string;
  room_id: number;
  room_name: string;
  seat_no: number;
  excuse_status: ExcuseStatusCode;
  note: string;
  created_at: string;
}

export const attendanceApi = {
  list: (sessionId: number) =>
    api.get<Paginated<ExamAttendanceRecordRow>>(
      `/exam-attendance-records/?session=${sessionId}&limit=500`,
    ),
  /** Girmedi işaretleme — referans SeatAssignment'tır; yalnız ONAYLI/ARŞİV oturumda. */
  mark: (payload: {
    session_id: number;
    seat_assignment_id: number;
    excuse_status?: ExcuseStatusCode;
    note?: string;
  }) => api.post<ExamAttendanceRecordRow>("/exam-attendance-records/", payload),
  /** Mazeret durumu/notu ARŞİVDE DE güncellenebilir (belge sonradan gelir). */
  update: (id: number, payload: { excuse_status?: ExcuseStatusCode; note?: string }) =>
    api.patch<ExamAttendanceRecordRow>(`/exam-attendance-records/${id}/`, payload),
  remove: (id: number) => api.del<void>(`/exam-attendance-records/${id}/`),
};
