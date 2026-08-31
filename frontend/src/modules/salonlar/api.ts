// Sınav salonları API istemcisi (backend apps/sinav — F2 + F4 layout-pdf).
// Numaralandırma iş kuralı BACKEND'dedir; editör her plan değişiminde
// preview-seats ucunu çağırır, istemcide hesap yapılmaz.

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

/**
 * Derslik kümesi (Sabah/Öğle gibi) — YALNIZ seçim kolaylığı etiketi.
 * `block` ile karıştırılmaz: blok resmî salon evrakına basılır, küme basılmaz.
 */
export interface ExamRoomGroup {
  id: number;
  name: string;
  order: number;
  room_count: number;
}

export interface ExamRoom {
  id: number;
  name: string;
  block: string;
  group_id: number | null;
  group_name: string;
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
  group_id?: number | null;
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

export const examRoomGroupApi = {
  list: () => api.get<Paginated<ExamRoomGroup>>("/exam-room-groups/?limit=200"),

  create: (payload: { name: string; order?: number }) =>
    api.post<ExamRoomGroup>("/exam-room-groups/", payload),

  update: (id: number, payload: Partial<{ name: string; order: number }>) =>
    api.patch<ExamRoomGroup>(`/exam-room-groups/${id}/`, payload),

  remove: (id: number) => api.del<void>(`/exam-room-groups/${id}/`),

  /** Toplu atama — ikili eğitimde asıl seçim maliyetini düşüren uç. */
  assign: (payload: { room_ids: number[]; group: number | null }) =>
    api.post<{ updated: number }>("/exam-room-groups/assign/", payload),
};

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
  // Boş yerleşim planı PDF'i (F4) — oturumdan bağımsız, kişisel veri yok.
  /** Kayıtlı salonun numaralandırılmış koltukları (koltuk seçici + kroki). */
  seats: (id: number) =>
    api.get<{
      room_id: number;
      numbering_scheme: NumberingSchemeCode;
      capacity: number;
      seats: SeatPreview[];
    }>(`/exam-rooms/${id}/seats/`),

  layoutPdfBlob: (id: number) => api.getBlob(`/exam-rooms/${id}/layout-pdf/`),
};
