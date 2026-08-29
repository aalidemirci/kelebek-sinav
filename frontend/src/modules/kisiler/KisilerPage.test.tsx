// Kişiler sayfası testi (F4-D4): iki sekmeli liste, KVKK gereği TCKN'nin listede
// GÖRÜNMEMESİ, gecikmeli arama, elle ekleme/düzenleme/silme akışı (alan hataları
// backend `fields`'tan), boş/hata durumları ve içe aktarma paneli (önizle → aktar,
// already_imported uyarısı, şablon indirme).

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { saveBlob } from "../../lib/download";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { Personnel, Student, StudentImportReport, StudentListParams } from "../okul/api";

const okulApiMock = vi.hoisted(() => ({
  getGradeLevels: vi.fn(),
  listStudents: vi.fn(),
  createStudent: vi.fn(),
  updateStudent: vi.fn(),
  deleteStudent: vi.fn(),
  listPersonnel: vi.fn(),
  createPersonnel: vi.fn(),
  updatePersonnel: vi.fn(),
  deletePersonnel: vi.fn(),
  previewStudentImport: vi.fn(),
  commitStudentImport: vi.fn(),
  previewPersonnelImport: vi.fn(),
  commitPersonnelImport: vi.fn(),
  studentTemplate: vi.fn(),
  personnelTemplate: vi.fn(),
}));

// Yalnız `okulApi` taklit edilir; etiket sabitleri + importCounts gerçek kalır
// (sayfa ile api katmanı arasındaki sözleşme sahte veriyle örtülmesin).
vi.mock("../okul/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../okul/api")>();
  return { ...actual, okulApi: okulApiMock };
});

vi.mock("../../lib/download", () => ({ saveBlob: vi.fn() }));

import KisilerPage from "./KisilerPage";

const STUDENT: Student = {
  id: 1,
  first_name: "Ayşe",
  last_name: "Yılmaz",
  full_name: "Ayşe Yılmaz",
  student_number: "123",
  class_level: 10,
  class_section: "A",
  class_label: "10/A",
  status: "ACTIVE",
};

const PERSONNEL: Personnel = {
  id: 5,
  first_name: "Mehmet",
  last_name: "Demirci",
  title: "Öğretmen",
  branch: "Coğrafya",
  is_active: true,
  full_name: "Mehmet Demirci",
};

const PREVIEW_REPORT: StudentImportReport = {
  file_hash: "abc",
  file_name: "",
  total_rows: 4,
  processed: 3,
  created_students: 2,
  updated_students: 1,
  unchanged_students: 0,
  already_imported: false,
  dry_run: true,
  warnings: [{ row_number: 3, field: "class", issue: "Sınıf/şube çözülemedi", raw_value: "8-A" }],
  skipped: [],
};

function page<T>(results: T[], count = results.length) {
  return { count, next: null, previous: null, results };
}

function renderPage() {
  return render(
    <SnackbarProvider>
      <ConfirmProvider>
        <KisilerPage />
      </ConfirmProvider>
    </SnackbarProvider>,
  );
}

beforeEach(() => {
  okulApiMock.getGradeLevels.mockResolvedValue({
    levels: [
      { value: 9, label: "9" },
      { value: 10, label: "10" },
    ],
    prep_enabled: false,
  });
  okulApiMock.listStudents.mockResolvedValue(page([STUDENT]));
  okulApiMock.listPersonnel.mockResolvedValue(page([PERSONNEL]));
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("KisilerPage — öğrenci listesi", () => {
  it("mutlu yol: liste yüklenir (yalnız ad + no + sınıf + durum — KVKK'da fazlası yok)", async () => {
    renderPage();
    expect(await screen.findByText("Ayşe Yılmaz")).toBeInTheDocument();
    expect(screen.getByText("10/A")).toBeInTheDocument();
    expect(screen.getByText("Aktif")).toBeInTheDocument();
    expect(okulApiMock.listStudents).toHaveBeenCalledWith({
      search: "",
      classLevel: null,
      classSection: "",
      limit: 25,
      offset: 0,
    });
  });

  it("arama gecikmeli olarak sorguya yansır", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.type(screen.getByLabelText("Ara"), "yılmaz");

    await waitFor(() =>
      expect(okulApiMock.listStudents).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: "yılmaz", offset: 0 }),
      ),
    );
  });

  it("boş liste: yönlendirici boş-durum kartı", async () => {
    okulApiMock.listStudents.mockResolvedValue(page<Student>([]));
    renderPage();
    expect(await screen.findByText("Gösterilecek öğrenci yok")).toBeInTheDocument();
  });

  it("hata: backend Türkçe mesajı hata bandında gösterilir", async () => {
    okulApiMock.listStudents.mockRejectedValue(
      new ApiError(500, "server_error", "Sicil okunamadı."),
    );
    renderPage();
    expect(await screen.findByText("Sicil okunamadı.")).toBeInTheDocument();
  });

  it("hata bandı canlı bölgedir — ekran okuyucuya duyurulur", async () => {
    okulApiMock.listStudents.mockRejectedValue(
      new ApiError(500, "server_error", "Sicil okunamadı."),
    );
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("Sicil okunamadı.");
  });
});

describe("KisilerPage — öğrenci ekleme/düzenleme/silme", () => {
  it("zorunlu alan boşken istek atılmaz, hata alanın altında görünür", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Öğrenci ekle" }));
    const dialog = await screen.findByRole("dialog", { name: "Yeni öğrenci" });
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));

    expect(await within(dialog).findByText("Ad zorunludur.")).toBeInTheDocument();
    expect(within(dialog).getByText("Soyad zorunludur.")).toBeInTheDocument();
    expect(okulApiMock.createStudent).not.toHaveBeenCalled();
  });

  it("yeni öğrenci: boş sınıf alanı null olarak gönderilir", async () => {
    okulApiMock.createStudent.mockResolvedValue({ ...STUDENT, id: 2 });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Öğrenci ekle" }));
    const dialog = await screen.findByRole("dialog", { name: "Yeni öğrenci" });
    await user.type(within(dialog).getByLabelText(/^Ad \*$/), "Zeynep");
    await user.type(within(dialog).getByLabelText(/^Soyad \*$/), "Kaya");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(okulApiMock.createStudent).toHaveBeenCalledWith(
        expect.objectContaining({
          first_name: "Zeynep",
          last_name: "Kaya",
          class_level: null,
          status: "ACTIVE",
        }),
      ),
    );
  });

  it("backend alan hatası (fields) ilgili alanın altına yazılır", async () => {
    okulApiMock.createStudent.mockRejectedValue(
      new ApiError(400, "validation_error", "Girdiğiniz bilgileri kontrol edin.", {
        student_number: ["Bu okul numarası zaten kayıtlı."],
      }),
    );
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Öğrenci ekle" }));
    const dialog = await screen.findByRole("dialog", { name: "Yeni öğrenci" });
    await user.type(within(dialog).getByLabelText(/^Ad \*$/), "Zeynep");
    await user.type(within(dialog).getByLabelText(/^Soyad \*$/), "Kaya");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));

    expect(await within(dialog).findByText("Bu okul numarası zaten kayıtlı.")).toBeInTheDocument();
    expect(within(dialog).getByText("Girdiğiniz bilgileri kontrol edin.")).toBeInTheDocument();
  });

  it("satıra tıklama düzenleme formunu açar; alanlar dolu gelir", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Ayşe Yılmaz kaydını düzenle" }));
    const dialog = await screen.findByRole("dialog", { name: "Öğrenciyi düzenle" });
    expect(within(dialog).getByLabelText("Okul no")).toHaveValue("123");
  });

  it("son sayfadaki tek kayıt silinince önceki sayfaya düşer (boş sayfada kilitlenmez)", async () => {
    const SON_KAYIT: Student = {
      ...STUDENT,
      id: 9,
      first_name: "Zeynep",
      last_name: "Kaya",
      full_name: "Zeynep Kaya",
    };
    // İkinci sayfada tek kayıt var; silinince o sayfa boşalır (count 26 → 25).
    let silindi = false;
    okulApiMock.listStudents.mockImplementation((params: StudentListParams) =>
      Promise.resolve(
        (params.offset ?? 0) === 0
          ? page([STUDENT], silindi ? 25 : 26)
          : silindi
            ? page<Student>([], 25)
            : page([SON_KAYIT], 26),
      ),
    );
    okulApiMock.deleteStudent.mockImplementation(() => {
      silindi = true;
      return Promise.resolve(undefined);
    });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: /Sonraki/ }));
    await screen.findByText("Zeynep Kaya");

    await user.click(screen.getByRole("button", { name: "Zeynep Kaya kaydını düzenle" }));
    const dialog = await screen.findByRole("dialog", { name: "Öğrenciyi düzenle" });
    await user.click(within(dialog).getByRole("button", { name: "Sil" }));
    const confirmDialog = await screen.findByRole("dialog", { name: "Onay" });
    await user.click(within(confirmDialog).getByRole("button", { name: "Sil" }));

    // Önceki sayfa yeniden yüklenir: liste dolu ve sayfalama çubuğu yerinde.
    expect(await screen.findByText("Ayşe Yılmaz")).toBeInTheDocument();
    expect(screen.queryByText("Gösterilecek öğrenci yok")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Önceki/ })).toBeDisabled();
  });

  it("silme: onay dialogu onaylanınca API çağrılır", async () => {
    okulApiMock.deleteStudent.mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Ayşe Yılmaz kaydını düzenle" }));
    const dialog = await screen.findByRole("dialog", { name: "Öğrenciyi düzenle" });
    await user.click(within(dialog).getByRole("button", { name: "Sil" }));

    const confirmDialog = await screen.findByRole("dialog", { name: "Onay" });
    await user.click(within(confirmDialog).getByRole("button", { name: "Sil" }));

    await waitFor(() => expect(okulApiMock.deleteStudent).toHaveBeenCalledWith(1));
  });
});

describe("KisilerPage — öğretmen sekmesi", () => {
  it("sekmeye geçince öğretmen listesi yüklenir", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("tab", { name: /Öğretmenler/ }));

    expect(await screen.findByText("Mehmet Demirci")).toBeInTheDocument();
    expect(screen.getByText("Coğrafya")).toBeInTheDocument();
    expect(okulApiMock.listPersonnel).toHaveBeenCalledWith({
      search: "",
      limit: 25,
      offset: 0,
    });
  });
});

describe("KisilerPage — içe aktarma paneli", () => {
  it("yapıştırılan metin: önizleme raporu gösterilir, Aktar önizlemeden önce kapalıdır", async () => {
    okulApiMock.previewStudentImport.mockResolvedValue(PREVIEW_REPORT);
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    expect(screen.getByRole("button", { name: "Aktar" })).toBeDisabled();

    await user.type(screen.getByLabelText("Ya da tabloyu yapıştırın"), "ad\tsoyad");
    await user.click(screen.getByRole("button", { name: /Önizle/ }));

    await waitFor(() =>
      expect(okulApiMock.previewStudentImport).toHaveBeenCalledWith({ text: "ad\tsoyad" }),
    );
    expect(await screen.findByText("Önizleme — hiçbir kayıt yazılmadı")).toBeInTheDocument();
    expect(screen.getByText("Uyarılar (1)")).toBeInTheDocument();
    expect(screen.getByText("Sınıf/şube çözülemedi")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aktar" })).toBeEnabled();
  });

  it("aktar: commit sonrası liste tazelenir ve already_imported uyarısı görünür", async () => {
    okulApiMock.previewStudentImport.mockResolvedValue(PREVIEW_REPORT);
    okulApiMock.commitStudentImport.mockResolvedValue({
      ...PREVIEW_REPORT,
      dry_run: false,
      already_imported: true,
      warnings: [],
    });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.type(screen.getByLabelText("Ya da tabloyu yapıştırın"), "ad\tsoyad");
    await user.click(screen.getByRole("button", { name: /Önizle/ }));
    await screen.findByText("Önizleme — hiçbir kayıt yazılmadı");

    const callsBefore = okulApiMock.listStudents.mock.calls.length;
    await user.click(screen.getByRole("button", { name: "Aktar" }));

    await waitFor(() =>
      expect(okulApiMock.commitStudentImport).toHaveBeenCalledWith({ text: "ad\tsoyad" }),
    );
    expect(await screen.findByText(/daha önce aktarılmış/)).toBeInTheDocument();
    await waitFor(() =>
      expect(okulApiMock.listStudents.mock.calls.length).toBeGreaterThan(callsBefore),
    );
  });

  it("önizleme hatası: backend mesajı bantta görünür, Aktar kapalı kalır", async () => {
    okulApiMock.previewStudentImport.mockRejectedValue(
      new ApiError(
        400,
        "validation_error",
        "Dosya (file) veya metin (text) alanlarından biri gerekli.",
      ),
    );
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.type(screen.getByLabelText("Ya da tabloyu yapıştırın"), "x");
    await user.click(screen.getByRole("button", { name: /Önizle/ }));

    expect(
      await screen.findByText("Dosya (file) veya metin (text) alanlarından biri gerekli."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aktar" })).toBeDisabled();
  });

  it("dosya seçimi kaldırılınca yapıştırma alanı yeniden etkinleşir", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    const dosyaAlani = screen.getByLabelText("Dosya (.xlsx)") as HTMLInputElement;
    await user.upload(dosyaAlani, new File(["x"], "ogrenci.xlsx"));
    expect(screen.getByLabelText("Ya da tabloyu yapıştırın")).toBeDisabled();

    await user.click(screen.getByRole("button", { name: /Dosyayı kaldır/ }));

    expect(screen.getByLabelText("Ya da tabloyu yapıştırın")).toBeEnabled();
    expect(dosyaAlani.files?.length ?? 0).toBe(0);
  });

  it("şablon indir: blob dosya olarak kaydedilir", async () => {
    const blob = new Blob(["x"]);
    okulApiMock.studentTemplate.mockResolvedValue(blob);
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Şablon indir" }));

    await waitFor(() => expect(saveBlob).toHaveBeenCalledWith(blob, "sablon-ogrenci.xlsx"));
  });
});
