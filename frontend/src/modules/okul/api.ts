// `okul` modülü API istemcisi — kurum künyesi/kurulum, ders yılı + dönemler,
// kişi sicilleri (öğrenci + personel), şube kataloğu, toplu içe aktarma ve
// şablon indirme uçları. Backend `apps/okul/{urls,views,serializers}.py` ile
// BİREBİR. DD kalıbından KS'ye: TCKN/veli/tatil/sınıf-sorumlusu tipleri KALKTI
// (tasarım §5 — o veriler hiç toplanmaz); okul türü + şube kataloğu EKLENDİ.

import { api } from "../../lib/api";
import { getGradeLevels as fetchGradeLevels } from "../../lib/gradeLevels";
import type { GradeLevelOption, GradeLevelsResponse } from "../../lib/gradeLevels";
import { unwrap } from "../../lib/pagination";
import type { Paginated } from "../../lib/pagination";

export type { GradeLevelOption, GradeLevelsResponse, Paginated };

// ---------------------------------------------------------------------------
// Ders yılı
// ---------------------------------------------------------------------------

/** Ders yılı — SchoolYearSerializer ile birebir (`is_active` salt-okunur). */
export interface SchoolYear {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
}

export interface SchoolYearCreateBody {
  name: string;
  start_date: string;
  end_date: string;
}

export interface SchoolTerm {
  id: number;
  school_year: number;
  sequence: 1 | 2;
  name: string;
  start_date: string;
  end_date: string;
}

export interface SchoolTermConfigurationBody {
  first_term_end: string;
  second_term_start: string;
}

// ---------------------------------------------------------------------------
// Kurulum sihirbazı / kurum künyesi
// ---------------------------------------------------------------------------

/** `GET /setup/status/` — sihirbaz kapısı + sicil doluluk sayaçları. */
export interface SetupStatus {
  setup_completed: boolean;
  school_name: string;
  has_active_school_year: boolean;
  student_count: number;
  personnel_count: number;
  class_section_count: number;
}

/** Okul türü — seviye kümesi bundan türetilir (U4); v1'de tek tür. */
export type SchoolType = "ANADOLU_LISESI";

export const SCHOOL_TYPE_TR: Record<SchoolType, string> = {
  ANADOLU_LISESI: "Anadolu Lisesi",
};

/** Kurum künyesi — evrak antedi buradan çözülür (`setup_completed` salt-okunur). */
export interface SchoolConfig {
  school_name: string;
  province: string;
  district: string;
  principal_name: string;
  school_type: SchoolType;
  has_prep_class: boolean;
  setup_completed: boolean;
}

/** PUT gövdesi kısmi olabilir — backend MERGE semantiği uygular. */
export type SchoolConfigBody = Partial<Omit<SchoolConfig, "setup_completed">>;

// ---------------------------------------------------------------------------
// Kişi sicilleri
// ---------------------------------------------------------------------------

export type StudentStatus = "ACTIVE" | "LEFT";

export const STUDENT_STATUS_TR: Record<StudentStatus, string> = {
  ACTIVE: "Aktif",
  LEFT: "Ayrıldı",
};

/** Öğrenci sicili — StudentSerializer ile birebir (`full_name`/`class_label` türetilmiş). */
export interface Student {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  student_number: string;
  class_level: number | null;
  class_section: string;
  class_label: string;
  status: StudentStatus;
}

/** Öğrenci yazma gövdesi — türetilmiş alanlar (full_name/class_label) gönderilmez. */
export interface StudentWriteBody {
  first_name: string;
  last_name: string;
  student_number?: string;
  class_level?: number | null;
  class_section?: string;
  status?: StudentStatus;
}

/** Personel sicili — PersonnelSerializer ile birebir (`full_name` türetilmiş). */
export interface Personnel {
  id: number;
  first_name: string;
  last_name: string;
  title: string;
  branch: string;
  is_active: boolean;
  full_name: string;
}

export interface PersonnelWriteBody {
  first_name: string;
  last_name: string;
  title?: string;
  branch?: string;
  is_active?: boolean;
}

/**
 * Zümre — okul zümre başkanları kurulunu oluşturan sınıf/alan zümreleri.
 * Sınav takvimi PDF'inin imza bloğu bu katalogdan seçilir (SubjectDepartmentSerializer).
 */
export interface SubjectDepartment {
  id: number;
  name: string;
  head: number | null;
  /** Başkanın ad-soyadı — backend şifreli alandan çözer (yazma tarafı yalnız `head`). */
  head_name: string;
  is_board_member: boolean;
}

export interface SubjectDepartmentWriteBody {
  name: string;
  head?: number | null;
  is_board_member?: boolean;
}

/** Şube kataloğu satırı — salon-şube eşlemesi (F2) ve R2k bu katalogdan okur. */
export interface ClassSection {
  id: number;
  school_year: number;
  school_year_name: string;
  class_level: number;
  class_section: string;
  class_label: string;
}

export interface ClassSectionWriteBody {
  school_year: number;
  class_level: number;
  class_section: string;
}

export interface StudentListParams {
  search?: string;
  classLevel?: number | null;
  classSection?: string;
  onlyActive?: boolean;
  limit?: number;
  offset?: number;
}

export interface PersonnelListParams {
  search?: string;
  onlyActive?: boolean;
  limit?: number;
  offset?: number;
}

// ---------------------------------------------------------------------------
// İçe aktarma (Excel dosyası — e-Okul .xls ya da şablon .xlsx — VEYA pano metni)
// ---------------------------------------------------------------------------

/** Rapordaki tek satır sorunu (uyarı veya atlanan satır). */
export interface ImportIssue {
  row_number: number;
  field: string;
  issue: string;
  raw_value: string;
}

interface ImportReportBase {
  file_hash: string;
  file_name: string;
  total_rows: number;
  processed: number;
  /** Aynı içerik daha önce aktarılmış — UYARIDIR, engel değil. */
  already_imported: boolean;
  /** Önizleme (true) hiçbir şey yazmaz; commit false döner. */
  dry_run: boolean;
  warnings: ImportIssue[];
  skipped: ImportIssue[];
}

export interface StudentImportReport extends ImportReportBase {
  created_students: number;
  updated_students: number;
  unchanged_students: number;
}

export interface PersonnelImportReport extends ImportReportBase {
  created_personnel: number;
  updated_personnel: number;
  unchanged_personnel: number;
}

export type ImportReport = StudentImportReport | PersonnelImportReport;

/** İçe aktarma girdisi — dosya yolu (multipart) veya pano metni (JSON). */
export type ImportInput = { file: File } | { text: string };

/**
 * Öğrenci/personel raporlarının farklı adlandırılmış sayaçlarını (created_students
 * ↔ created_personnel) tek şekle indirger — rapor bileşeni türden bağımsız kalır.
 */
export function importCounts(report: ImportReport): {
  created: number;
  updated: number;
  unchanged: number;
} {
  if ("created_students" in report) {
    return {
      created: report.created_students,
      updated: report.updated_students,
      unchanged: report.unchanged_students,
    };
  }
  return {
    created: report.created_personnel,
    updated: report.updated_personnel,
    unchanged: report.unchanged_personnel,
  };
}

/** Şablon dosya adları — indirme sırasında tarayıcıya verilir (backend ile aynı). */
export const STUDENT_TEMPLATE_FILENAME = "sablon-ogrenci.xlsx";
export const PERSONNEL_TEMPLATE_FILENAME = "sablon-personel.xlsx";

// ---------------------------------------------------------------------------
// Yardımcılar
// ---------------------------------------------------------------------------

/** Parça yoksa yolu olduğu gibi bırakır (gereksiz "?" üretmez). */
function withQuery(path: string, parts: string[]): string {
  return parts.length > 0 ? `${path}?${parts.join("&")}` : path;
}

/** Düz dizi dönen uçları da sayfalama zarfına indirger (tek tüketim şekli). */
function asPage<T>(data: Paginated<T> | T[]): Paginated<T> {
  return Array.isArray(data)
    ? { count: data.length, next: null, previous: null, results: data }
    : data;
}

/** Dosya yolu multipart (`file`), metin yolu JSON (`text`) — backend tam olarak birini bekler. */
function importRequest<R>(path: string, input: ImportInput): Promise<R> {
  if ("file" in input) {
    const form = new FormData();
    form.append("file", input.file);
    return api.postForm<R>(path, form);
  }
  return api.post<R>(path, { text: input.text });
}

export const okulApi = {
  // --- Kurulum sihirbazı ---

  getSetupStatus: (): Promise<SetupStatus> => api.get<SetupStatus>("/setup/status/"),

  getSchoolConfig: (): Promise<SchoolConfig> => api.get<SchoolConfig>("/setup/school-config/"),

  /** Kısmi gövde gönderilebilir — backend MERGE eder (verilmeyen alan korunur). */
  updateSchoolConfig: (body: SchoolConfigBody): Promise<SchoolConfig> =>
    api.put<SchoolConfig>("/setup/school-config/", body),

  completeSetup: (): Promise<{ setup_completed: boolean }> =>
    api.post<{ setup_completed: boolean }>("/setup/complete/"),

  /** Öğrenim seviyeleri — okul türünden türetilir (U4). */
  getGradeLevels: (): Promise<GradeLevelsResponse> => fetchGradeLevels(),

  // --- Ders yılları ---

  /** Ders yıllarını listeler (DRF sayfalı yanıt → düz dizi). */
  listSchoolYears: async (): Promise<SchoolYear[]> => {
    const data = await api.get<Paginated<SchoolYear>>("/school-years/?limit=200");
    return unwrap(data);
  },

  /** Yeni ders yılı oluşturur (pasif doğar; aktivasyon ayrı uçtan). */
  createSchoolYear: (body: SchoolYearCreateBody): Promise<SchoolYear> =>
    api.post<SchoolYear>("/school-years/", body),

  /** Ders yılını aktifleştirir — backend diğerlerini pasifler. */
  activateSchoolYear: (id: number): Promise<SchoolYear> =>
    api.post<SchoolYear>(`/school-years/${id}/activate/`),

  listSchoolTerms: (schoolYearId: number): Promise<SchoolTerm[]> =>
    api.get<SchoolTerm[]>(`/school-years/${schoolYearId}/terms/`),

  configureSchoolTerms: (
    schoolYearId: number,
    body: SchoolTermConfigurationBody,
  ): Promise<SchoolTerm[]> => api.put<SchoolTerm[]>(`/school-years/${schoolYearId}/terms/`, body),

  // --- Öğrenciler ---

  listStudents: async (params: StudentListParams = {}): Promise<Paginated<Student>> => {
    const parts: string[] = [];
    if (params.search?.trim()) parts.push(`search=${encodeURIComponent(params.search.trim())}`);
    if (params.classLevel !== undefined && params.classLevel !== null) {
      parts.push(`class_level=${params.classLevel}`);
    }
    if (params.classSection?.trim()) {
      parts.push(`class_section=${encodeURIComponent(params.classSection.trim())}`);
    }
    if (params.onlyActive) parts.push("only_active=true");
    if (params.limit !== undefined) parts.push(`limit=${params.limit}`);
    if (params.offset) parts.push(`offset=${params.offset}`);
    const data = await api.get<Paginated<Student> | Student[]>(withQuery("/students/", parts));
    return asPage(data);
  },

  getStudent: (id: number): Promise<Student> => api.get<Student>(`/students/${id}/`),

  createStudent: (body: StudentWriteBody): Promise<Student> =>
    api.post<Student>("/students/", body),

  updateStudent: (id: number, body: Partial<StudentWriteBody>): Promise<Student> =>
    api.patch<Student>(`/students/${id}/`, body),

  deleteStudent: (id: number): Promise<void> => api.del<void>(`/students/${id}/`),

  // --- Personel ---

  listPersonnel: async (params: PersonnelListParams = {}): Promise<Paginated<Personnel>> => {
    const parts: string[] = [];
    if (params.search?.trim()) parts.push(`search=${encodeURIComponent(params.search.trim())}`);
    if (params.onlyActive) parts.push("only_active=true");
    if (params.limit !== undefined) parts.push(`limit=${params.limit}`);
    if (params.offset) parts.push(`offset=${params.offset}`);
    const data = await api.get<Paginated<Personnel> | Personnel[]>(withQuery("/personnel/", parts));
    return asPage(data);
  },

  getPersonnel: (id: number): Promise<Personnel> => api.get<Personnel>(`/personnel/${id}/`),

  createPersonnel: (body: PersonnelWriteBody): Promise<Personnel> =>
    api.post<Personnel>("/personnel/", body),

  updatePersonnel: (id: number, body: Partial<PersonnelWriteBody>): Promise<Personnel> =>
    api.patch<Personnel>(`/personnel/${id}/`, body),

  deletePersonnel: (id: number): Promise<void> => api.del<void>(`/personnel/${id}/`),

  // --- Şube kataloğu ---

  listClassSections: async (schoolYear?: number): Promise<ClassSection[]> => {
    const path =
      schoolYear === undefined
        ? "/class-sections/?limit=500"
        : `/class-sections/?school_year=${schoolYear}&limit=500`;
    const data = await api.get<Paginated<ClassSection> | ClassSection[]>(path);
    return unwrap(data);
  },

  createClassSection: (body: ClassSectionWriteBody): Promise<ClassSection> =>
    api.post<ClassSection>("/class-sections/", body),

  deleteClassSection: (id: number): Promise<void> => api.del<void>(`/class-sections/${id}/`),

  // --- Zümreler (takvim imza bloğunun kaynağı) ---

  /** `limit=500`: DRF varsayılan sayfası 25'tir, zümre listesi sessizce kesilmesin. */
  listSubjectDepartments: async (boardOnly = false): Promise<SubjectDepartment[]> => {
    const path = boardOnly
      ? "/subject-departments/?board_only=true&limit=500"
      : "/subject-departments/?limit=500";
    const data = await api.get<Paginated<SubjectDepartment> | SubjectDepartment[]>(path);
    return unwrap(data);
  },

  createSubjectDepartment: (body: SubjectDepartmentWriteBody): Promise<SubjectDepartment> =>
    api.post<SubjectDepartment>("/subject-departments/", body),

  updateSubjectDepartment: (
    id: number,
    body: Partial<SubjectDepartmentWriteBody>,
  ): Promise<SubjectDepartment> =>
    api.patch<SubjectDepartment>(`/subject-departments/${id}/`, body),

  deleteSubjectDepartment: (id: number): Promise<void> =>
    api.del<void>(`/subject-departments/${id}/`),

  // --- İçe aktarma (önizleme hiçbir şey yazmaz; commit gerçek yazar) ---

  previewStudentImport: (input: ImportInput): Promise<StudentImportReport> =>
    importRequest<StudentImportReport>("/imports/students/preview/", input),

  commitStudentImport: (input: ImportInput): Promise<StudentImportReport> =>
    importRequest<StudentImportReport>("/imports/students/commit/", input),

  previewPersonnelImport: (input: ImportInput): Promise<PersonnelImportReport> =>
    importRequest<PersonnelImportReport>("/imports/personnel/preview/", input),

  commitPersonnelImport: (input: ImportInput): Promise<PersonnelImportReport> =>
    importRequest<PersonnelImportReport>("/imports/personnel/commit/", input),

  // --- Şablon indirme (xlsx blob) ---

  studentTemplate: (): Promise<Blob> => api.getBlob("/templates/students/"),

  personnelTemplate: (): Promise<Blob> => api.getBlob("/templates/personnel/"),
};
