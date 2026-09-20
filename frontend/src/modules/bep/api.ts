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
import type { ScoreModeCode } from "../oturumlar/api";

/** `GET /iep-students/` satırı — sınıf/şube + okul no sırasıyla gelir. */
export interface IepStudent {
  /** SATIR kimliği (silme bununla yapılır) — öğrenci pk'si DEĞİL. */
  id: number;
  student_id: number;
  student_number: string;
  full_name: string;
  class_label: string;
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
  add: (studentId: number) => api.post<{ id: number }>("/iep-students/", { student_id: studentId }),
  /** `id` SATIR kimliğidir (`IepStudent.id`). */
  remove: (id: number) => api.del<void>(`/iep-students/${id}/`),
  /** Geri alınamaz: bütün liste + bütün oturumlardaki bireysel soru dosyaları. */
  deleteAll: () => api.post<IepDeleteAllResult>("/iep-students/delete-all/"),
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
