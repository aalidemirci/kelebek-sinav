// Sınav salonları API istemcisi (backend apps/sinav — F2).
// Numaralandırma iş kuralı BACKEND'dedir; editör her plan değişiminde
// preview-seats ucunu çağırır, istemcide hesap yapılmaz. Boş plan PDF'i
// (layout-pdf) F4'te evrak setiyle birlikte gelir.

import { api } from "../../lib/api";
import type { Paginated } from "../../lib/pagination";

export type { Paginated };

export type DeskTypeCode = "SINGLE" | "DOUBLE" | "TRIPLE";
export type FurnitureKindCode = "DOOR" | "BLACKBOARD" | "SMART_BOARD" | "TEACHER_DESK";
export type NumberingSchemeCode = "S_PATTERN" | "STRAIGHT";

export interface DeskCell {
  row: number;
  col: number;
  type: DeskTypeCode;
  disabled?: boolean;
}

export interface FurnitureCell {
  kind: FurnitureKindCode;
  row: number;
  col: number;
}

export interface LayoutPlan {
  grid: { rows: number; cols: number };
  desks: DeskCell[];
  furniture: FurnitureCell[];
}

export interface ExamRoom {
  id: number;
  name: string;
  block: string;
  linked_section_id: number | null;
  linked_section_label: string;
  layout_plan: LayoutPlan;
  numbering_scheme: NumberingSchemeCode;
  is_active: boolean;
  capacity: number;
}

export interface SeatPreview {
  desk_row: number;
  desk_col: number;
  desk_type: string;
  slot: number;
  seat_no: number;
  x: number;
  y: number;
}

export interface ExamRoomPayload {
  name?: string;
  block?: string;
  linked_section_id?: number | null;
  layout_plan?: LayoutPlan;
  numbering_scheme?: NumberingSchemeCode;
  is_active?: boolean;
}

export interface GenerateSectionRoomsResult {
  created: string[];
  skipped: string[];
  orphan_rooms: string[];
  sections_total: number;
}

export const examRoomApi = {
  // Okul salon sayısı küçüktür (≈30-60); tek sayfada tümü (limit=200).
  list: (includeInactive = false) =>
    api.get<Paginated<ExamRoom>>(
      `/exam-rooms/?limit=200${includeInactive ? "&include_inactive=true" : ""}`,
    ),
  create: (payload: ExamRoomPayload & { name: string }) =>
    api.post<ExamRoom>("/exam-rooms/", payload),
  update: (id: number, payload: ExamRoomPayload) =>
    api.patch<ExamRoom>(`/exam-rooms/${id}/`, payload),
  previewSeats: (layout_plan: LayoutPlan, numbering_scheme: NumberingSchemeCode) =>
    api.post<{ capacity: number; seats: SeatPreview[] }>("/exam-rooms/preview-seats/", {
      layout_plan,
      numbering_scheme,
    }),
  // Her aktif şube için 40 koltuklu derslik salonu üret (idempotent).
  generateSectionRooms: () =>
    api.post<GenerateSectionRoomsResult>("/exam-rooms/generate-section-rooms/", {}),
};
