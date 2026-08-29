// Test fixture'ları (F3). Test DOSYASINDAN test dosyasına import YAPMA —
// import edilen dosyanın vi.mock kayıtları da yüklenir ve bu dosyanınkileri
// ezer (OYS Tur 232'de yaşandı); paylaşılan kurucular burada yaşar.

import type { Paginated } from "../../lib/pagination";
import type { ExamRoom } from "../salonlar/api";
import type {
  ExamAttendanceRecordRow,
  ExamSession,
  SeatAssignmentRow,
  SeatingResponse,
  ValidationReport,
} from "./api";

export function makeSession(overrides: Partial<ExamSession> = {}): ExamSession {
  return {
    id: 5,
    name: "2. Ortak Sınav",
    exam_date: "2026-06-15",
    start_time: "09:00:00",
    duration_minutes: 40,
    session_type: "SCHOOL",
    layout_mode: "BUTTERFLY",
    proctors_enabled: false,
    term_id: 3,
    term_label: "2025-2026 Ders Yılı 1. Dönem",
    status: "DRAFT",
    transfer_check_confirmed_by_name: "",
    transfer_check_confirmed_at: null,
    approved_by_name: "",
    approved_at: null,
    courses: [],
    rooms: [],
    ...overrides,
  };
}

/** DRF sayfalı liste sarmalayıcı — mock list yanıtları için. */
export function paginated<T>(results: T[]): Paginated<T> {
  return { count: results.length, next: null, previous: null, results };
}

export function makeReport(overrides: Partial<ValidationReport> = {}): ValidationReport {
  return {
    is_valid: true,
    hard_violations: [],
    first_ring_same_group_pairs: 0,
    min_same_group_distance: {},
    proximity_score: 0,
    cross_group_same_section_first_ring_pairs: 0,
    room_counts: {},
    ...overrides,
  };
}

// KVKK: fixture'lardaki tüm ad/numaralar UYDURMADIR (kullanıcı CLAUDE.md kuralı).
export function makeAssignment(overrides: Partial<SeatAssignmentRow> = {}): SeatAssignmentRow {
  return {
    id: 11,
    room_id: 1,
    seat_no: 1,
    desk_row: 0,
    desk_col: 0,
    slot: 0,
    student_id: 101,
    full_name: "Ayşe Yılmaz",
    student_number: "101",
    class_label: "9/A",
    conflict_group: "10:9",
    status: "NORMAL",
    ...overrides,
  };
}

/** Tek salon (D-204), ikili sırada iki öğrenci — takas testleri için yeterli. */
export function makeSeating(overrides: Partial<SeatingResponse> = {}): SeatingResponse {
  return {
    session_id: 5,
    status: "DISTRIBUTED",
    distribution_params: { seed: 1234, checkerboard: true },
    conflict_group_labels: { "10:9": "Matematik — 9. Sınıf" },
    rooms: [
      {
        room_id: 1,
        room_name: "D-204",
        assignments: [
          makeAssignment(),
          makeAssignment({
            id: 12,
            seat_no: 2,
            slot: 1,
            student_id: 102,
            full_name: "Mehmet Demir",
            student_number: "102",
            class_label: "9/B",
          }),
        ],
      },
    ],
    report: makeReport({ room_counts: { "1": 2 } }),
    occupancy: [{ room_id: 1, room_name: "D-204", capacity: 4, placed: 2, percent: 50 }],
    ...overrides,
  };
}

/** Kroki geometrisi: 1x2 ızgara — (0,0) ikili sıra, (0,1) öğretmen masası. */
export function makeRoomGeometry(overrides: Partial<ExamRoom> = {}): ExamRoom {
  return {
    id: 1,
    name: "D-204",
    block: "",
    linked_section_id: null,
    linked_section_label: "",
    layout_plan: {
      grid: { rows: 1, cols: 2 },
      desks: [{ row: 0, col: 0, type: "DOUBLE" }],
      furniture: [{ kind: "TEACHER_DESK", row: 0, col: 1 }],
    },
    numbering_scheme: "S_PATTERN",
    is_active: true,
    capacity: 4,
    ...overrides,
  };
}

export function makeAttendanceRecord(
  overrides: Partial<ExamAttendanceRecordRow> = {},
): ExamAttendanceRecordRow {
  return {
    id: 31,
    student_id: 101,
    full_name: "Ayşe Yılmaz",
    student_number: "101",
    class_label: "9/A",
    room_id: 1,
    room_name: "D-204",
    seat_no: 1,
    excuse_status: "PENDING",
    note: "",
    created_at: "2026-06-15T09:05:00Z",
    ...overrides,
  };
}
