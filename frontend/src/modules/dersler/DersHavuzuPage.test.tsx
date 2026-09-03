// Ders havuzu testleri: "Sınav" sütunu (yazılı / uygulama / sınav yok) ve
// satırdan düzenleme yolu. Sınav biçimi takvim havuzunun neyi kendiliğinden
// çekeceğini belirler — sütun kayarsa idareci yanlış dersi siler.
// Liste useState + Promise.all ile, "Şubeler" sütununun kapsam haritası
// react-query ile gelir (03.09.2026) — sağlayıcı üçlüsü: QueryClient +
// Snackbar + Confirm. KVKK: ders adları kataloğa aittir, kişi verisi yok.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { Course, CourseSectionOffering, CourseSectionOfferingRow } from "./api";

const dersler = vi.hoisted(() => ({
  listCourses: vi.fn(),
  listDuplicates: vi.fn(() => Promise.resolve([])),
  createCourse: vi.fn(),
  updateCourse: vi.fn(),
  // Tipli varsayılan: `results: []` tek başına `never[]` çıkarır ve
  // mockResolvedValue kapsam satırlarını kabul etmez (tsc kapısı — emsal
  // TakvimHavuzPaneli.test.tsx şube mock'u).
  sectionOfferings: vi.fn(
    (): Promise<{ school_year: number; results: CourseSectionOfferingRow[] }> =>
      Promise.resolve({ school_year: 1, results: [] }),
  ),
  courseSections: vi.fn((): Promise<{ school_year: number; offerings: CourseSectionOffering[] }> =>
    Promise.resolve({ school_year: 1, offerings: [] }),
  ),
  setCourseSections: vi.fn(
    (): Promise<{ school_year: number; offerings: CourseSectionOffering[] }> =>
      Promise.resolve({ school_year: 1, offerings: [] }),
  ),
  getCatalogStatus: vi.fn(() =>
    Promise.resolve({
      year: 2026,
      year_label: "2026-2027",
      school_type: "ANADOLU_LISESI",
      school_type_label: "Anadolu Lisesi",
      has_prep_class: false,
      transitional: false,
      custom: false,
      synced: true,
      data_available: true,
      warnings: ["12. sınıf ortak dersleri için önceki çizelge bu sürümde yok."],
      levels: [
        {
          level: 9,
          label: "9. sınıf",
          explicit: false,
          programs: [
            {
              key: "anadolu-lisesi-2025",
              name: "Anadolu Lisesi Haftalık Ders Çizelgesi (TTK 09.05.2025/5)",
              source: "TTK 09.05.2025 tarihli ve 5 sayılı karar — https://ttkb.meb.gov.tr/x.pdf",
              role: "ortak+seçmeli",
            },
          ],
          default_program_keys: ["anadolu-lisesi-2025"],
          warnings: [],
        },
      ],
      programs: [],
      school_types: [],
    }),
  ),
  resyncCatalog: vi.fn(),
}));

const okul = vi.hoisted(() => ({
  getGradeLevels: vi.fn(() =>
    Promise.resolve({
      levels: [
        { value: 9, label: "9" },
        { value: 10, label: "10" },
      ],
      prep_enabled: false,
    }),
  ),
  listClassSections: vi.fn(() =>
    Promise.resolve([
      { id: 1, class_level: 9, class_section: "A", class_label: "9/A", group: null },
      { id: 2, class_level: 9, class_section: "B", class_label: "9/B", group: null },
    ]),
  ),
  listClassSectionGroups: vi.fn(() => Promise.resolve([])),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, derslerApi: { ...actual.derslerApi, ...dersler } };
});
vi.mock("../okul/api", async (importActual) => {
  const actual = await importActual<typeof import("../okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...okul } };
});

import DersHavuzuPage from "./DersHavuzuPage";

function ders(overrides: Partial<Course> = {}): Course {
  return {
    id: 1,
    name: "Coğrafya",
    levels: [9],
    level_labels: ["9. Sınıf"],
    course_type: "COMMON",
    source: "MEB_CATALOG",
    exam_mode: "WRITTEN",
    exam_mode_label: "Yazılı",
    is_active: true,
    catalog_excluded: false,
    ...overrides,
  };
}

const BEDEN = ders({
  id: 2,
  name: "Beden Eğitimi ve Spor",
  levels: [9, 10],
  level_labels: ["9. Sınıf", "10. Sınıf"],
  exam_mode: "PRACTICE",
  exam_mode_label: "Uygulama",
});

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <ConfirmProvider>
          <DersHavuzuPage />
        </ConfirmProvider>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("DersHavuzuPage", () => {
  it("yürürlükteki çizelge panelini dayanağıyla basar; 'yeniden uygula' senkronu tetikler", async () => {
    const user = userEvent.setup();
    dersler.listCourses.mockResolvedValue([ders()]);
    dersler.resyncCatalog.mockResolvedValue({
      result: {
        created: 0,
        updated: 2,
        unchanged: 59,
        restored: 1,
        excluded: 0,
        errors: [],
        warnings: [],
      },
      status: {},
    });

    renderPage();

    expect(
      await screen.findByText(/Yürürlükteki çizelge — Anadolu Lisesi, 2026-2027/),
    ).toBeInTheDocument();
    expect(screen.getByText(/TTK 09\.05\.2025 tarihli ve 5 sayılı karar/)).toBeInTheDocument();
    expect(screen.getByText(/önceki çizelge bu sürümde yok/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Çizelgeyi yeniden uygula/ }));
    await waitFor(() => expect(dersler.resyncCatalog).toHaveBeenCalled());
    expect(await screen.findByText(/2 güncellenen, 1 geri açılan/)).toBeInTheDocument();
  });

  it("çizelge dışı kalan ders idari pasiften ayrı rozetlenir", async () => {
    dersler.listCourses.mockResolvedValue([
      ders({
        id: 5,
        name: "Hazırlık Sınıfı Türk Dili ve Edebiyatı",
        is_active: false,
        catalog_excluded: true,
      }),
      ders({ id: 6, name: "Girişimcilik", is_active: false }),
    ]);

    renderPage();

    const tablo = within(await screen.findByRole("table"));
    expect(tablo.getByText("Çizelge dışı")).toBeInTheDocument();
    expect(tablo.getByText("Pasif")).toBeInTheDocument();
  });

  it("listede Sınav sütunu dersin sınav biçimini basar", async () => {
    dersler.listCourses.mockResolvedValue([ders(), BEDEN]);

    renderPage();

    expect(await screen.findByRole("columnheader", { name: "Sınav" })).toBeInTheDocument();
    // Sayfa açıklaması da "Yazılı" diyor — sorgu TABLOYA daraltılır.
    const tablo = within(screen.getByRole("table"));
    expect(tablo.getByText("Yazılı")).toBeInTheDocument();
    expect(tablo.getByText("Uygulama")).toBeInTheDocument();
  });

  it("satırdan düzenleme sınav biçimini günceller", async () => {
    const user = userEvent.setup();
    dersler.listCourses.mockResolvedValue([ders(), BEDEN]);
    dersler.updateCourse.mockResolvedValue(BEDEN);

    renderPage();
    await user.click(
      await screen.findByRole("button", { name: "Beden Eğitimi ve Spor dersini düzenle" }),
    );

    const dialog = await screen.findByRole("dialog", {
      name: "Dersi düzenle: Beden Eğitimi ve Spor",
    });
    await user.selectOptions(within(dialog).getByRole("combobox", { name: "Sınav" }), "WRITTEN");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(dersler.updateCourse).toHaveBeenCalledWith(2, {
        name: "Beden Eğitimi ve Spor",
        levels: [9, 10],
        course_type: "COMMON",
        exam_mode: "WRITTEN",
      }),
    );
  });

  it("yeni ders eklerken seçilen sınav biçimi gönderilir", async () => {
    const user = userEvent.setup();
    dersler.listCourses.mockResolvedValue([ders()]);
    dersler.createCourse.mockResolvedValue(ders({ id: 3, name: "Görsel Sanatlar" }));

    renderPage();
    await user.click(await screen.findByRole("button", { name: "Ders ekle" }));

    const dialog = await screen.findByRole("dialog", { name: "Havuza ders ekle" });
    await user.type(within(dialog).getByLabelText(/Ders adı/), "Görsel Sanatlar");
    await user.click(within(dialog).getByRole("button", { name: "9" }));
    await user.selectOptions(within(dialog).getByRole("combobox", { name: "Sınav" }), "PRACTICE");
    await user.click(within(dialog).getByRole("button", { name: "Ekle" }));

    await waitFor(() =>
      expect(dersler.createCourse).toHaveBeenCalledWith({
        name: "Görsel Sanatlar",
        levels: [9],
        course_type: "COMMON",
        exam_mode: "PRACTICE",
      }),
    );
  });
  it("Şubeler sütunu: zorunlu derste 'Seviye geneli', seçmelide kapsam özeti", async () => {
    dersler.listCourses.mockResolvedValue([
      ders({ id: 1, name: "Matematik", course_type: "COMMON" }),
      ders({ id: 2, name: "Almanca", course_type: "ELECTIVE" }),
    ]);
    dersler.sectionOfferings.mockResolvedValue({
      school_year: 1,
      results: [{ course: 2, level: 9, section_ids: [1, 2] }],
    });

    renderPage();

    expect(await screen.findByRole("columnheader", { name: "Şubeler" })).toBeInTheDocument();
    // Zorunlu ders seviyenin tamamında okutulur; kapsam düğmesi çizilmez.
    expect(screen.getByText("Seviye geneli")).toBeInTheDocument();
    expect(
      await screen.findByRole("button", { name: "Almanca dersinin şubelerini düzenle" }),
    ).toHaveTextContent("9: A, B");
  });

  it("şubesi girilmemiş YAZILI seçmeli uyarı işaretiyle görünür", async () => {
    // Havuz doldurma onu atlayacak — sessiz düşmesin diye sütunda işaretlenir.
    dersler.listCourses.mockResolvedValue([
      ders({ id: 2, name: "Almanca", course_type: "ELECTIVE", exam_mode: "WRITTEN" }),
    ]);
    dersler.sectionOfferings.mockResolvedValue({ school_year: 1, results: [] });

    renderPage();

    expect(
      await screen.findByRole("button", { name: "Almanca dersinin şubelerini düzenle" }),
    ).toHaveTextContent("Girilmedi ⚠");
  });

  it("şube kapsamı diyaloğu seçimi seviye seviye kaydeder", async () => {
    const user = userEvent.setup();
    dersler.listCourses.mockResolvedValue([
      ders({ id: 2, name: "Almanca", course_type: "ELECTIVE", levels: [9] }),
    ]);
    dersler.sectionOfferings.mockResolvedValue({ school_year: 1, results: [] });
    dersler.courseSections.mockResolvedValue({ school_year: 1, offerings: [] });
    dersler.setCourseSections.mockResolvedValue({
      school_year: 1,
      offerings: [{ level: 9, section_ids: [1] }],
    });

    renderPage();
    await user.click(
      await screen.findByRole("button", { name: "Almanca dersinin şubelerini düzenle" }),
    );

    const dialog = await screen.findByRole("dialog", { name: "Almanca — şubeler" });
    await user.click(await within(dialog).findByLabelText("Almanca 9. sınıf: 9/A"));
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(dersler.setCourseSections).toHaveBeenCalledWith(2, [{ level: 9, section_ids: [1] }]),
    );
  });

  it("kayıtlı kapsam diyaloğa yüklenir", async () => {
    const user = userEvent.setup();
    dersler.listCourses.mockResolvedValue([
      ders({ id: 2, name: "Almanca", course_type: "ELECTIVE", levels: [9] }),
    ]);
    dersler.sectionOfferings.mockResolvedValue({
      school_year: 1,
      results: [{ course: 2, level: 9, section_ids: [2] }],
    });
    dersler.courseSections.mockResolvedValue({
      school_year: 1,
      offerings: [{ level: 9, section_ids: [2] }],
    });

    renderPage();
    await user.click(
      await screen.findByRole("button", { name: "Almanca dersinin şubelerini düzenle" }),
    );

    const dialog = await screen.findByRole("dialog", { name: "Almanca — şubeler" });
    expect(await within(dialog).findByLabelText("Almanca 9. sınıf: 9/B")).toBeChecked();
    expect(within(dialog).getByLabelText("Almanca 9. sınıf: 9/A")).not.toBeChecked();
  });
});
