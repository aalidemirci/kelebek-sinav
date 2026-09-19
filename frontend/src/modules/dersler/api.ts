// Ders havuzu API istemcisi — backend `apps/dersler/{urls,views,serializers}.py`
// ile birebir. Liste ucu ilk çağrıda MEB tohumunu tembelce koşar (K5).

import { api } from "../../lib/api";
import type { LevelPrograms, SchoolType, SchoolTypeOption } from "../okul/api";

export type CourseType = "COMMON" | "ELECTIVE";
export type CourseSource = "MEB_CATALOG" | "MANUAL";
/** Dersin sınav biçimi — backend `dersler.CourseExamMode` ile birebir. */
export type CourseExamMode = "WRITTEN" | "PRACTICE" | "NONE";

// `COMMON` kullanıcıya "Zorunlu" diye gösterilir: MEB dilinde "ortak sınav/ortak
// yazılı" okul geneli sınav demektir; ders türüne de "Ortak" demek iki kavramı
// karıştırıyordu (docs/sozluk.md, CLAUDE.md §2). Kod değeri değişmedi.
export const COURSE_TYPE_TR: Record<CourseType, string> = {
  COMMON: "Zorunlu",
  ELECTIVE: "Seçmeli",
};

// Takvim havuzunun "Dersleri ekle" yolu YALNIZ zorunlu + YAZILI dersleri
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

/** Bir dersin bir seviyedeki şube kapsamı (seçmeli dersler için). */
export interface CourseSectionOffering {
  level: number;
  section_ids: number[];
}

/** Tüm katalogun kapsam haritası — ders havuzu tablosunun "Şubeler" sütunu. */
export interface CourseSectionOfferingRow extends CourseSectionOffering {
  course: number;
}

// ---------------------------------------------------------------------------
// Seçmeli ders öğrenci listesi (19.09.2026) — "şubenin bir kısmı dersi alıyor".
// Kural ŞUBE BAZINDADIR: listesiz şubeyi dersi tamamen alır, listeli şubede
// yalnız listedekiler (backend `dersler.CourseEnrollment`).
// ---------------------------------------------------------------------------

/** (ders, şube) → listedeki öğrenci sayısı; listesiz şube satırda yoktur. */
export interface EnrollmentCountRow {
  course: number;
  section: number;
  count: number;
}

export interface CourseEnrollmentSection {
  section_id: number;
  student_ids: number[];
}

export interface SetSectionEnrollmentBody {
  section_id: number;
  /** Boş liste = şubenin tamamı dersi alır. */
  student_ids: number[];
  /** Verilirse şubenin listede OLMAYAN öğrencileri bu derse yazılır. */
  complement_course_id?: number;
}

export interface SetSectionEnrollmentResult {
  school_year: number;
  section_id: number;
  student_ids: number[];
  complement: { course_id: number; student_ids: number[] } | null;
}

/** e-Okul OOK10002R010 raporundaki bir ders grubunun eşleşme özeti. */
export interface ElectiveImportCourse {
  /** e-Okul başlığı ("SEÇMELİ KUR`AN-I KERİM"). */
  title: string;
  status: "matched" | "unmatched";
  course_id: number | null;
  course_name: string;
  note: string;
  report_rows: number;
  students: number;
  /** "9/A" etiketleri, Türk alfabesiyle sıralı. */
  sections: string[];
}

/** Satır sorunu — sayfa/satır konumu + okul no (ad YOK). */
export interface ElectiveImportIssue {
  page: number;
  line: number;
  issue: string;
  value: string;
}

export interface ElectiveImportReport {
  file_hash: string;
  file_name: string;
  school_year: string;
  pages: number;
  total_rows: number;
  processed: number;
  already_imported: boolean;
  dry_run: boolean;
  courses: ElectiveImportCourse[];
  /**
   * Raporun kapsadığı şube sayısı ve sınıf düzeyleri ("9. Sınıf"): listeler YALNIZ
   * bu şubelerde yenilenir — tek düzey/şube için alınmış rapor öbürlerini silmez.
   */
  covered_section_count: number;
  covered_levels: string[];
  /** Listesi olup bu raporda yer almayan dersler — dokunulmadı. */
  untouched_courses: string[];
  warnings: ElectiveImportIssue[];
  skipped: ElectiveImportIssue[];
  warnings_truncated: number;
  skipped_truncated: number;
}

function electiveImport(path: string, file: File): Promise<ElectiveImportReport> {
  const form = new FormData();
  form.append("file", file);
  return api.postForm<ElectiveImportReport>(path, form);
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
  /** Seçmeli derslerin şube kapsamı — sınav takvimi de bu kaynaktan beslenir. */
  sectionOfferings: (schoolYearId?: number) =>
    api.get<{ school_year: number; results: CourseSectionOfferingRow[] }>(
      `/courses/section-offerings/${schoolYearId ? `?school_year=${schoolYearId}` : ""}`,
    ),
  courseSections: (courseId: number, schoolYearId?: number) =>
    api.get<{ school_year: number; offerings: CourseSectionOffering[] }>(
      `/courses/${courseId}/sections/${schoolYearId ? `?school_year=${schoolYearId}` : ""}`,
    ),
  /** TAM DEĞİŞTİRME: gönderilmeyen seviyenin kapsamı silinir. */
  setCourseSections: (courseId: number, offerings: CourseSectionOffering[]) =>
    api.put<{ school_year: number; offerings: CourseSectionOffering[] }>(
      `/courses/${courseId}/sections/`,
      { offerings },
    ),

  /** Ders havuzu tablosu: (ders, şube) → listedeki öğrenci sayısı. */
  enrollmentCounts: () =>
    api.get<{ school_year: number; results: EnrollmentCountRow[] }>("/courses/enrollment-counts/"),
  /** Tek dersin listeli şubeleri ve öğrenci kimlikleri. */
  courseEnrollments: (courseId: number) =>
    api.get<{ school_year: number; sections: CourseEnrollmentSection[] }>(
      `/courses/${courseId}/enrollments/`,
    ),
  /** TEK ŞUBEYİ tamamen değiştirir; boş liste = şubenin tamamı. */
  setSectionEnrollment: (courseId: number, body: SetSectionEnrollmentBody) =>
    api.put<SetSectionEnrollmentResult>(`/courses/${courseId}/enrollments/`, body),
  /** e-Okul OOK10002R010 PDF'i — yazmadan önizleme. */
  previewEnrollmentImport: (file: File) =>
    electiveImport("/courses/enrollments/import/preview/", file),
  /** e-Okul OOK10002R010 PDF'i — rapordaki derslerin listelerini yazar. */
  commitEnrollmentImport: (file: File) =>
    electiveImport("/courses/enrollments/import/commit/", file),
};
