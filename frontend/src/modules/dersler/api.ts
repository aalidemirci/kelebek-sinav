// Ders havuzu API istemcisi — backend `apps/dersler/{urls,views,serializers}.py`
// ile birebir. Liste ucu ilk çağrıda MEB tohumunu tembelce koşar (K5).

import { api } from "../../lib/api";
import type { LevelPrograms, SchoolType, SchoolTypeOption } from "../okul/api";

export type CourseType = "COMMON" | "ELECTIVE";
export type CourseSource = "MEB_CATALOG" | "MANUAL";
/** Dersin sınav biçimi — backend `dersler.CourseExamMode` ile birebir. */
export type CourseExamMode = "WRITTEN" | "PRACTICE" | "NONE";

export const COURSE_TYPE_TR: Record<CourseType, string> = {
  COMMON: "Ortak",
  ELECTIVE: "Seçmeli",
};

// Takvim havuzunun "Zorunlu dersleri ekle" yolu YALNIZ ortak + YAZILI dersleri
// çeker; uygulama sınavı yapılan (Beden/Görsel/Müzik) ya da hiç sınavı olmayan
// (Rehberlik) ders idarecinin tek tek silmesi gereken satır olmaktan çıksın.
export const COURSE_EXAM_MODE_TR: Record<CourseExamMode, string> = {
  WRITTEN: "Yazılı",
  PRACTICE: "Uygulama",
  NONE: "Sınav yok",
};

export const COURSE_SOURCE_TR: Record<CourseSource, string> = {
  MEB_CATALOG: "MEB çizelgesi",
  MANUAL: "Elle giriş",
};

export interface Course {
  id: number;
  name: string;
  levels: number[];
  level_labels: string[];
  course_type: CourseType;
  source: CourseSource;
  exam_mode: CourseExamMode;
  /** Backend'in hazır Türkçe etiketi — sözlükle çelişirse kaynak gerçek budur. */
  exam_mode_label: string;
  is_active: boolean;
  /** Okulun yürürlükteki çizelgesinde yok; katalog senkronu pasifleştirdi (idari pasif DEĞİL). */
  catalog_excluded: boolean;
}

// ---------------------------------------------------------------------------
// Yürürlükteki çizelge planı (`GET /courses/catalog-status/`, tasarım §7.2)
// ---------------------------------------------------------------------------

/** Bir çizelge program dosyası (data/ders-cizelgeleri/<key>.md). */
export interface CatalogProgram {
  key: string;
  name: string;
  school_type: SchoolType;
  school_type_label: string;
  has_prep: boolean;
  /** Bölüm/varyant etiketi (GSL: "Müzik"); boş = tek bölüm. */
  department: string;
  /** Dayanak: TTK karar tarih/sayı + bağlantı. */
  source: string;
  start_year: number | null;
  phased: boolean;
  /** false: yalnız matristen seçilir (Tematik Spor, AİHL program/proje dersleri). */
  default_included: boolean;
  course_count: number;
}

export interface CatalogLevelProgram {
  key: string;
  name: string;
  source: string;
  /** "ortak+seçmeli" / "ortak" / "seçmeli" — programın bu seviyede verdiği satırlar. */
  role: string;
}

export interface CatalogLevelStatus {
  level: number;
  label: string;
  /** Seviye `level_programs` ile mi belirlendi (varsayılan değil). */
  explicit: boolean;
  programs: CatalogLevelProgram[];
  /** Varsayılan atamanın bu seviyedeki program anahtarları (matris "sıfırla" başvurusu). */
  default_program_keys: string[];
  warnings: string[];
}

export interface CatalogStatus {
  year: number;
  year_label: string;
  school_type: SchoolType;
  school_type_label: string;
  has_prep_class: boolean;
  /** Seviyeler arasında farklı program kümeleri var (kademeli dönüşüm). */
  transitional: boolean;
  /** En az bir seviye açık atamayla belirlenmiş. */
  custom: boolean;
  /** Katalog bu planla senkron (önizlemede daima false). */
  synced: boolean;
  /** Okul türü için çizelge verisi var. */
  data_available: boolean;
  warnings: string[];
  levels: CatalogLevelStatus[];
  programs: CatalogProgram[];
  school_types: SchoolTypeOption[];
}

export interface CatalogStatusParams {
  schoolType?: SchoolType;
  hasPrepClass?: boolean;
  levelPrograms?: LevelPrograms;
}

export interface CatalogResyncResult {
  result: {
    created: number;
    updated: number;
    unchanged: number;
    restored: number;
    excluded: number;
    errors: string[];
    warnings: string[];
  } | null;
  status: CatalogStatus;
}

export interface CourseWriteBody {
  name: string;
  levels: number[];
  course_type?: CourseType;
  exam_mode?: CourseExamMode;
}

export interface CourseListParams {
  level?: number | null;
  courseType?: CourseType | null;
  includeInactive?: boolean;
  q?: string;
}

/** Mükerrer aday kümesindeki tek ders satırı. */
export interface DuplicateMember {
  id: number;
  name: string;
  course_type: CourseType;
  levels: number[];
  course_source: CourseSource;
  has_prefix: boolean;
  exam_count: number;
}

export interface DuplicateCluster {
  canon_key: string;
  suggested_canonical_id: number;
  courses: DuplicateMember[];
}

export interface MergeResult {
  aliases: number;
  exams: number;
  dropped_exams: number;
}

export const derslerApi = {
  listCourses: (params: CourseListParams = {}): Promise<Course[]> => {
    const parts: string[] = [];
    if (params.level !== undefined && params.level !== null) parts.push(`level=${params.level}`);
    if (params.courseType) parts.push(`course_type=${params.courseType}`);
    if (params.includeInactive) parts.push("include_inactive=true");
    if (params.q?.trim()) parts.push(`q=${encodeURIComponent(params.q.trim())}`);
    const query = parts.length > 0 ? `?${parts.join("&")}` : "";
    return api.get<Course[]>(`/courses/${query}`);
  },

  createCourse: (body: CourseWriteBody): Promise<Course> => api.post<Course>("/courses/", body),

  updateCourse: (
    id: number,
    body: Partial<CourseWriteBody> & { is_active?: boolean },
  ): Promise<Course> => api.patch<Course>(`/courses/${id}/`, body),

  listDuplicates: (): Promise<DuplicateCluster[]> =>
    api.get<DuplicateCluster[]>("/courses/duplicates/"),

  /**
   * Yürürlükteki çizelge planı. Parametre verilirse KAYDEDİLMEMİŞ seçimin
   * önizlemesi döner (kurulum/ayar matrisi); verilmezse kayıtlı yapılandırma.
   */
  getCatalogStatus: (params: CatalogStatusParams = {}): Promise<CatalogStatus> => {
    const parts: string[] = [];
    if (params.schoolType) parts.push(`school_type=${params.schoolType}`);
    if (params.hasPrepClass !== undefined) {
      parts.push(`has_prep_class=${params.hasPrepClass ? "1" : "0"}`);
    }
    if (params.levelPrograms) {
      parts.push(`level_programs=${encodeURIComponent(JSON.stringify(params.levelPrograms))}`);
    }
    const query = parts.length > 0 ? `?${parts.join("&")}` : "";
    return api.get<CatalogStatus>(`/courses/catalog-status/${query}`);
  },

  /** Kataloğu çizelgeye zorla yeniden çeker ("Çizelgeyi yeniden uygula"). */
  resyncCatalog: (): Promise<CatalogResyncResult> =>
    api.post<CatalogResyncResult>("/courses/resync/"),

  mergeCourses: (duplicate: number, canonical: number): Promise<MergeResult> =>
    api.post<MergeResult>("/courses/merge/", { duplicate, canonical }),
};
