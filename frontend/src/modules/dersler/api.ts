// Ders havuzu API istemcisi — backend `apps/dersler/{urls,views,serializers}.py`
// ile birebir. Liste ucu ilk çağrıda MEB tohumunu tembelce koşar (K5).

import { api } from "../../lib/api";

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

  mergeCourses: (duplicate: number, canonical: number): Promise<MergeResult> =>
    api.post<MergeResult>("/courses/merge/", { duplicate, canonical }),
};
