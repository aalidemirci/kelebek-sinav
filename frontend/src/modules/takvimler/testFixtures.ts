// Takvim test fixture'ları (F6). Test DOSYASINDAN test dosyasına import YAPMA
// (OYS Tur 232 — vi.mock sızıntısı); paylaşılan kurucular burada yaşar.
// KVKK: adlar/sayılar uydurmadır.

import type { Paginated } from "../../lib/pagination";
import type {
  CalendarGrid,
  CalendarGridCell,
  ExamCalendar,
  ExamCalendarEntryRow,
  ExamTrackMatrix,
} from "./api";

export function paginated<T>(results: T[]): Paginated<T> {
  return { count: results.length, next: null, previous: null, results };
}

export function makeCalendar(overrides: Partial<ExamCalendar> = {}): ExamCalendar {
  return {
    id: 7,
    school_year_name: "2026-2027",
    semester: 3,
    semester_name: "1. Dönem",
    round: 1,
    name: "1. Dönem 1. Sınav Takvimi",
    start_date: "2026-10-26",
    end_date: "2026-11-06",
    status: "DRAFT",
    description_text: "AÇIKLAMALAR\n1. Örnek madde.",
    footnote_text: "Mazeret sınavları izleyen hafta yapılır.",
    signatory_departments: [],
    signatory_department_names: [],
    submitted_at: null,
    approved_by_name: "",
    approved_at: null,
    ...overrides,
  };
}

export function makeEntry(overrides: Partial<ExamCalendarEntryRow> = {}): ExamCalendarEntryRow {
  return {
    id: 41,
    calendar: 7,
    course: 10,
    course_name: "Coğrafya",
    level: 9,
    exam_kind: "WRITTEN",
    is_butterfly: true,
    authority: "SCHOOL",
    placed_date: null,
    period_no: null,
    session: null,
    note: "",
    ...overrides,
  };
}

export function makeCell(overrides: Partial<CalendarGridCell> = {}): CalendarGridCell {
  return {
    entry_id: 41,
    course_id: 10,
    course_name: "Coğrafya",
    level: 9,
    exam_kind: "WRITTEN",
    is_butterfly: true,
    authority: "SCHOOL",
    session_id: null,
    note: "",
    ...overrides,
  };
}

/** 2 günlük mini ızgara: 27 Ekim Salı + 31 Ekim Cumartesi (boş hafta sonu gizlenir). */
export function makeGrid(overrides: Partial<CalendarGrid> = {}): CalendarGrid {
  return {
    calendar: {
      id: 7,
      name: "1. Dönem 1. Sınav Takvimi",
      status: "DRAFT",
      start_date: "2026-10-26",
      end_date: "2026-11-06",
    },
    levels: [
      { value: 9, label: "9", display_label: "9. Sınıf", student_count: 84 },
      { value: 10, label: "10", display_label: "10. Sınıf", student_count: 78 },
    ],
    periods: [
      { no: 1, name: "1. Ders", start: "08:30" },
      { no: 2, name: "2. Ders", start: "09:20" },
    ],
    days: [
      { date: "2026-10-27", is_weekend: false, weekday: 1 },
      { date: "2026-10-31", is_weekend: true, weekday: 5 },
    ],
    cells: {},
    unplaced: [makeCell()],
    errors: [],
    warnings: [],
    ...overrides,
  };
}

export function makeTrackMatrix(overrides: Partial<ExamTrackMatrix> = {}): ExamTrackMatrix {
  return {
    items: [{ id: 1, name: "Soru teslimi", description: "", order: 10 }],
    rows: [
      {
        entry_id: 41,
        course_name: "Coğrafya",
        level: 9,
        exam_kind: "WRITTEN",
        cells: [{ item_id: 1, status: null }],
      },
    ],
    ...overrides,
  };
}
