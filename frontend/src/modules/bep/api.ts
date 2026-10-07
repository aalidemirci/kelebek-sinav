// BEP kapsamındaki öğrenciler + bireysel soru dosyası API istemcisi (20.09.2026).
// Backend `apps/sinav/views_individual.py` ile BİREBİR.
//
// ÖZEL NİTELİKLİ VERİYE İŞARET (KVKK md. 6): liste YALNIZ üyelik tutar — tanı,
// rapor, açıklama ya da serbest metin alanı BİLİNÇLE YOKTUR ve EKLENMEZ
// (yerleştirme kuralındaki "yalnız kategori" kararının aynı gerekçesi).
//
// Yollardaki kimlik SATIR kimliğidir (opak): öğrenci pk'si yalnız istek
// GÖVDESİNDE gider. Backend 4xx yanıtını yoluyla günlüğe yazar; öğrenci kimliği
// yolda olsaydı "bu öğrencinin bireysel soru dosyası var" bilgisi günlüğe sızardı.
// Bu yüzden buraya öğrenci pk'siyle yol kuran bir uç EKLEMEYİN.

import { api } from "../../lib/api";
import type { RuleReason, ScoreModeCode, SeatPreference } from "../oturumlar/api";

// ---------------------------------------------------------------------------
// Kalıcı sınav tedbirleri (07.10.2026) — aynı satır BEP üyeliğini ve tedbirleri
// taşır. Gerekçe YALNIZ kategoridir; tedbirler seçenek/sayıdır, serbest metin
// YOKTUR. Tedbirin yer ayağı her oturumda yerleştirme kuralı olarak uygulanır;
// ek süre ve okuyucu/yazıcı desteği yalnız idare özetine basılır.
// ---------------------------------------------------------------------------

/** Yer tedbiri — backend `AccommodationPlacement` ile birebir. */
export type AccommodationPlacement = "NONE" | "HOME_CLASSROOM" | "SEPARATE_ROOM" | "FRONT_ROW";

export const PLACEMENT_TR: Record<AccommodationPlacement, string> = {
  NONE: "Yer kuralı yok",
  HOME_CLASSROOM: "Kendi sınıfında",
  SEPARATE_ROOM: "Ayrı salon",
  FRONT_ROW: "Ön sırada",
};

/** Ek süre üst sınırı (dakika) — backend `MAX_EXTRA_MINUTES`. */
export const MAX_EXTRA_MINUTES = 120;

/** Tedbir alanları — ekleme, düzenleme ve toplu ekleme AYNI gövdeyi gönderir. */
export interface AccommodationBody {
  reason_category: RuleReason;
  placement: AccommodationPlacement;
  /** Yalnız "Ayrı salon"da dolu. */
  target_room_id: number | null;
  seat_preference: SeatPreference;
  solo_desk: boolean;
  /** 0 = ek süre yok. */
  extra_minutes: number;
  reader: boolean;
  scribe: boolean;
}

/** `GET /iep-students/` satırı — sınıf/şube + okul no sırasıyla gelir. */
export interface IepStudent extends AccommodationBody {
  /** SATIR kimliği (silme/düzenleme bununla yapılır) — öğrenci pk'si DEĞİL. */
  id: number;
  student_id: number;
  student_number: string;
  full_name: string;
  class_label: string;
  reason_label: string;
  /** Tedbirlerin kullanıcı dilindeki özeti — backend üretir (kopya etiket yok). */
  measures: string[];
}

/** Toplu eklemenin sonucu — ad yok; "zaten listede" yalnız sayıdır. */
export interface BulkAddResult {
  added: number;
  already: number;
  /** Bu numarayla aktif öğrenci yok. */
  not_found: string[];
}

/** Oturuma giren tedbirli öğrenci (Yerleştirme Kuralları paneli). */
export interface SessionAccommodation {
  student_id: number;
  student_number: string;
  full_name: string;
  class_label: string;
  reason_label: string;
  measures: string[];
  /** Bu oturumda öğrencinin oturum kuralı var: tedbirin YER ayağı uygulanmaz. */
  overridden: boolean;
  /**
   * Yer tedbiri yerleşime yansıdı mı: null → yer tedbiri yok ya da dağıtılmadı;
   * false → dağıtım tedbirden önce yapılmış, oturum yeniden dağıtılmalı.
   */
  placement_applied: boolean | null;
  room_name: string;
  seat_no: number | null;
}

/** Bireysel soru dosyası satırının özeti — öğrenci kimliği taşımaz. */
export interface IndividualDocument {
  id: number;
  /** false → öğrenci seçildi ama PDF bekleniyor; kitapçık üretimi reddedilir. */
  has_file: boolean;
  page_count: number | null;
  score_mode: ScoreModeCode;
  question_count: number | null;
}

/** Oturum paneli satırı: o oturuma giren BEP kapsamındaki öğrenci. */
export interface IndividualQuestionRow {
  student_id: number;
  student_number: string;
  full_name: string;
  class_label: string;
  room_name: string;
  /** null → öğrenci artık yerleşimde yok (yetim satır; yalnız kaldırılabilir). */
  seat_no: number | null;
  course_label: string;
  /** false → öğrenci listeden çıkarılmış ama bu oturumdaki dosyası duruyor. */
  on_iep_list: boolean;
  /** null → seçim yok: öğrenci dersin soru dosyasını alır. */
  document: IndividualDocument | null;
}

/** KVKK düğmesinin sonucu — kaç liste kaydı ve kaç bireysel dosya silindi. */
export interface IepDeleteAllResult {
  students: number;
  documents: number;
}

export const iepApi = {
  list: () => api.get<{ results: IepStudent[] }>("/iep-students/"),
  /** Tedbir verilmezse yalnız BEP üyeliğidir (20.09.2026 davranışı). */
  add: (studentId: number, measures?: AccommodationBody) =>
    api.post<{ id: number }>("/iep-students/", { student_id: studentId, ...measures }),
  /** Gerekçe ve tedbirleri TAMAMEN değiştirir; `id` SATIR kimliğidir. */
  update: (id: number, measures: AccommodationBody) =>
    api.put<{ id: number }>(`/iep-students/${id}/`, measures),
  /** Okul numaralarıyla toplu ekleme — numaralar boşluk, virgül ya da satırla ayrılır. */
  addByNumbers: (numbers: string, measures: AccommodationBody) =>
    api.post<BulkAddResult>("/iep-students/bulk/", { student_numbers: numbers, ...measures }),
  /** `id` SATIR kimliğidir (`IepStudent.id`). */
  remove: (id: number) => api.del<void>(`/iep-students/${id}/`),
  /** Geri alınamaz: bütün liste + bütün oturumlardaki bireysel soru dosyaları. */
  deleteAll: () => api.post<IepDeleteAllResult>("/iep-students/delete-all/"),
  /** Oturuma giren tedbirli öğrenciler (Yerleştirme Kuralları paneli). */
  session: (sessionId: number) =>
    api.get<{ rows: SessionAccommodation[] }>(`/iep-students/session/?session=${sessionId}`),
};

export const individualQuestionApi = {
  list: (sessionId: number) =>
    api.get<{ rows: IndividualQuestionRow[] }>(`/individual-questions/?session=${sessionId}`),
  /** Seçim: öğrenciye bu oturumda bireysel soru dosyası uygulanacak (dosya ayrıca yüklenir). */
  select: (sessionId: number, studentId: number) =>
    api.post<IndividualDocument>("/individual-questions/", {
      session_id: sessionId,
      student_id: studentId,
    }),
  /** Seçimi kaldırır: satır + yüklü PDF silinir. */
  remove: (documentId: number) => api.del<void>(`/individual-questions/${documentId}/`),
  /** Yükle/değiştir — gövde dersin soru dosyasıyla AYNI alanlar (file, score_mode, question_count). */
  uploadFile: (documentId: number, form: FormData) =>
    api.postForm<IndividualDocument>(`/individual-questions/${documentId}/file/`, form),
  fileBlob: (documentId: number) => api.getBlob(`/individual-questions/${documentId}/file/`),
  /** İdare özeti (PDF) — salonlara dağıtılmaz, "Tümünü indir" paketine girmez. */
  summaryBlob: (sessionId: number) =>
    api.getBlob(`/individual-questions/summary/?session=${sessionId}`),
};
