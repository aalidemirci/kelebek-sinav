// AyarlarPage testi (KS): ders yılları + şube kataloğu + okul bilgileri (okul
// türü dahil) + güvenlik sekmesinin varlığı. Güvenlik panelinin kendi davranışı
// modules/guvenlik testlerinde; burada yalnız sekme kablolaması doğrulanır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { ClassSection, SchoolYear } from "../okul/api";

const oapi = vi.hoisted(() => ({
  getSetupStatus: vi.fn(),
  getSchoolConfig: vi.fn(),
  updateSchoolConfig: vi.fn(),
  getGradeLevels: vi.fn(),
  listSchoolYears: vi.fn(),
  createSchoolYear: vi.fn(),
  activateSchoolYear: vi.fn(),
  listSchoolTerms: vi.fn(),
  configureSchoolTerms: vi.fn(),
  listClassSections: vi.fn(),
  createClassSection: vi.fn(),
  deleteClassSection: vi.fn(),
}));

vi.mock("../okul/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../okul/api")>();
  return { ...actual, okulApi: oapi };
});

// Güvenlik paneli kendi API'sine gider; bu testte içeriği önemsizdir.
vi.mock("../guvenlik/GuvenlikAyarlari", () => ({
  default: () => <div>GÜVENLİK PANELİ</div>,
}));

import AyarlarPage from "./AyarlarPage";

const AKTIF_YIL: SchoolYear = {
  id: 3,
  name: "2026-2027",
  start_date: "2026-09-01",
  end_date: "2027-06-30",
  is_active: true,
};

const PASIF_YIL: SchoolYear = {
  id: 4,
  name: "2027-2028",
  start_date: "2027-09-01",
  end_date: "2028-06-30",
  is_active: false,
};

const SUBE: ClassSection = {
  id: 11,
  school_year: 3,
  school_year_name: "2026-2027",
  class_level: 10,
  class_section: "A",
  class_label: "10/A",
};

function renderPage() {
  return render(
    <MemoryRouter>
      <SnackbarProvider>
        <ConfirmProvider>
          <AyarlarPage />
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  oapi.listSchoolYears.mockResolvedValue([AKTIF_YIL, PASIF_YIL]);
  oapi.getSchoolConfig.mockResolvedValue({
    school_name: "Örnek Anadolu Lisesi",
    province: "İstanbul",
    district: "Örnek",
    principal_name: "",
    school_type: "ANADOLU_LISESI",
    has_prep_class: false,
    setup_completed: true,
  });
  oapi.getGradeLevels.mockResolvedValue({
    levels: [
      { value: 9, label: "9" },
      { value: 10, label: "10" },
    ],
    prep_enabled: false,
  });
  oapi.listSchoolTerms.mockResolvedValue([]);
  oapi.listClassSections.mockResolvedValue([SUBE]);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("AyarlarPage — ders yılları", () => {
  it("yılları listeler, aktif olanı rozetler; pasif yıl aktifleştirilebilir", async () => {
    oapi.activateSchoolYear.mockResolvedValue(PASIF_YIL);
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("2026-2027")).toBeInTheDocument();
    expect(screen.getByText("Aktif")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Aktifleştir/ }));
    const onay = await screen.findByRole("dialog", { name: "Ders yılını aktifleştir" });
    await user.click(within(onay).getByRole("button", { name: "Aktifleştir" }));

    await waitFor(() => expect(oapi.activateSchoolYear).toHaveBeenCalledWith(4));
  });

  it("tatil sekmesi YOK (kelebek iş günü hesabı yapmaz)", async () => {
    renderPage();
    await screen.findByText("2026-2027");
    expect(screen.queryByRole("tab", { name: /Tatiller/ })).toBeNull();
  });
});

describe("AyarlarPage — şubeler", () => {
  it("şube kataloğunu listeler ve yeni şube ekler", async () => {
    oapi.createClassSection.mockResolvedValue({ ...SUBE, id: 12, class_section: "B" });
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("tab", { name: /Şubeler/ }));
    expect(await screen.findByText("10/A")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Şube"), "B");
    await user.click(screen.getByRole("button", { name: "Şube ekle" }));

    await waitFor(() =>
      expect(oapi.createClassSection).toHaveBeenCalledWith({
        school_year: 3,
        class_level: 9,
        class_section: "B",
      }),
    );
  });

  it("şube kaldırma onaydan geçer", async () => {
    oapi.deleteClassSection.mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("tab", { name: /Şubeler/ }));
    await screen.findByText("10/A");

    await user.click(screen.getByRole("button", { name: "10/A şubesini kaldır" }));
    const onay = await screen.findByRole("dialog", { name: "Şubeyi kaldır" });
    await user.click(within(onay).getByRole("button", { name: "Kaldır" }));

    await waitFor(() => expect(oapi.deleteClassSection).toHaveBeenCalledWith(11));
  });
});

describe("AyarlarPage — okul bilgileri", () => {
  it("künyeyi yükler ve kaydedince okul türü + hazırlık bayrağını da gönderir", async () => {
    oapi.updateSchoolConfig.mockResolvedValue({});
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("tab", { name: /Okul Bilgileri/ }));
    expect(await screen.findByLabelText(/Okul adı/)).toHaveValue("Örnek Anadolu Lisesi");

    await user.selectOptions(screen.getByLabelText("Hazırlık sınıfı"), "1");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(oapi.updateSchoolConfig).toHaveBeenCalledWith({
        school_name: "Örnek Anadolu Lisesi",
        province: "İstanbul",
        district: "Örnek",
        principal_name: "",
        school_type: "ANADOLU_LISESI",
        has_prep_class: true,
      }),
    );
  });

  it("kaydetme hatası bantta gösterilir", async () => {
    oapi.updateSchoolConfig.mockRejectedValue(
      new ApiError(500, "server_error", "Kayıt yazılamadı."),
    );
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("tab", { name: /Okul Bilgileri/ }));
    await screen.findByLabelText(/Okul adı/);
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    expect(await screen.findByText("Kayıt yazılamadı.")).toBeInTheDocument();
  });
});

describe("AyarlarPage — güvenlik", () => {
  it("güvenlik sekmesi paneli gösterir", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("tab", { name: /Güvenlik/ }));
    expect(await screen.findByText("GÜVENLİK PANELİ")).toBeInTheDocument();
  });
});
