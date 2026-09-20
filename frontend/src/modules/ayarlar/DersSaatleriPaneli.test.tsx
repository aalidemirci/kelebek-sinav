// Ayarlar → Ders Saatleri testleri (20.09.2026).
// Sabitlenen: (1) saatleri BACKEND hesaplar — ön yüz kendi aritmetiğini yapmaz;
// (2) hesaplanan liste elle düzeltilebilir ve kaydedilen o düzeltilmiş listedir;
// (3) ikili eğitimde şube oturumu ve öğle çizelgesi görünür, tam günde gizli.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";

const okulApiMock = vi.hoisted(() => ({
  getSchoolConfig: vi.fn(),
  listClassSections: vi.fn(),
  previewBellSchedule: vi.fn(),
  updateSchoolConfig: vi.fn(),
  assignClassSectionShift: vi.fn(),
}));

vi.mock("../okul/api", async (importActual) => {
  const actual = await importActual<typeof import("../okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...okulApiMock } };
});

import DersSaatleriPaneli from "./DersSaatleriPaneli";

function config(overrides: Record<string, unknown> = {}) {
  return {
    school_name: "Test Lisesi",
    province: "İstanbul",
    district: "Sancaktepe",
    principal_name: "",
    school_type: "ANADOLU_LISESI",
    has_prep_class: false,
    level_programs: {},
    daily_period_count: 8,
    exam_period_nos: [],
    default_separation_mode: "NONE",
    education_model: "FULL_DAY",
    bell_schedule: [
      { no: 1, name: "1. Ders", start: "08:30" },
      { no: 2, name: "2. Ders", start: "09:20" },
    ],
    afternoon_bell_schedule: [],
    bell_flow: {},
    afternoon_bell_flow: {},
    setup_completed: true,
    ...overrides,
  };
}

function sube(id: number, label: string, shift = "") {
  return {
    id,
    school_year: 1,
    school_year_name: "2026-2027",
    class_level: Number(label.split("/")[0]),
    class_section: label.split("/")[1],
    class_label: label,
    group: null,
    group_name: "",
    shift,
  };
}

function renderPanel() {
  return render(
    <SnackbarProvider>
      <DersSaatleriPaneli />
    </SnackbarProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("DersSaatleriPaneli", () => {
  it("kayıtlı çizelgeyi düzenlenebilir alanlarda gösterir", async () => {
    okulApiMock.getSchoolConfig.mockResolvedValue(config());
    okulApiMock.listClassSections.mockResolvedValue([]);

    renderPanel();

    expect(await screen.findByLabelText("1. Ders")).toHaveValue("08:30");
    expect(screen.getByLabelText("2. Ders")).toHaveValue("09:20");
  });

  it("saatleri BACKEND hesaplar; ön yüz kendi aritmetiğini yapmaz", async () => {
    const user = userEvent.setup();
    okulApiMock.getSchoolConfig.mockResolvedValue(config({ bell_schedule: [] }));
    okulApiMock.listClassSections.mockResolvedValue([]);
    okulApiMock.previewBellSchedule.mockResolvedValue({
      periods: [
        { no: 1, name: "1. Ders", start: "09:00" },
        { no: 2, name: "2. Ders", start: "09:50" },
      ],
      end_time: "10:30",
      next_start: "10:50",
      flow: {},
    });

    renderPanel();
    await user.click(await screen.findByRole("button", { name: /Saatleri hesapla/ }));

    await waitFor(() => expect(okulApiMock.previewBellSchedule).toHaveBeenCalledTimes(1));
    expect(await screen.findByLabelText("1. Ders")).toHaveValue("09:00");
    expect(screen.getByText(/Son ders 10:30/)).toBeInTheDocument();
  });

  it("blok düzeni metni sayı listesine çevrilerek gönderilir", async () => {
    const user = userEvent.setup();
    okulApiMock.getSchoolConfig.mockResolvedValue(config({ bell_schedule: [] }));
    okulApiMock.listClassSections.mockResolvedValue([]);
    okulApiMock.previewBellSchedule.mockResolvedValue({
      periods: [],
      end_time: "14:25",
      next_start: "14:45",
      flow: {},
    });

    renderPanel();
    await user.type(await screen.findByLabelText(/Blok düzeni/), "2+2+2+2");
    await user.click(screen.getByRole("button", { name: /Saatleri hesapla/ }));

    await waitFor(() =>
      expect(okulApiMock.previewBellSchedule).toHaveBeenCalledWith(
        expect.objectContaining({ block_sizes: [2, 2, 2, 2] }),
      ),
    );
  });

  it("elle düzeltilen saat kaydedilir", async () => {
    const user = userEvent.setup();
    okulApiMock.getSchoolConfig.mockResolvedValue(config());
    okulApiMock.listClassSections.mockResolvedValue([]);
    okulApiMock.updateSchoolConfig.mockResolvedValue(config());

    renderPanel();
    const alan = await screen.findByLabelText("1. Ders");
    await user.clear(alan);
    await user.type(alan, "09:15");
    await user.click(screen.getByRole("button", { name: /Kaydet/ }));

    await waitFor(() =>
      expect(okulApiMock.updateSchoolConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          bell_schedule: [
            { no: 1, name: "1. Ders", start: "09:15" },
            { no: 2, name: "2. Ders", start: "09:20" },
          ],
        }),
      ),
    );
  });

  it("tam gün okulda şube oturumu bölümü GİZLİ", async () => {
    okulApiMock.getSchoolConfig.mockResolvedValue(config());
    okulApiMock.listClassSections.mockResolvedValue([sube(1, "9/A")]);

    renderPanel();

    await screen.findByLabelText("1. Ders");
    expect(screen.queryByText("Şube oturumları")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Öğleden sonra" })).not.toBeInTheDocument();
  });

  it("ikili eğitimde şube topluca öğle oturumuna işaretlenir", async () => {
    const user = userEvent.setup();
    okulApiMock.getSchoolConfig.mockResolvedValue(config({ education_model: "DUAL" }));
    okulApiMock.listClassSections.mockResolvedValue([sube(1, "9/A"), sube(2, "9/B", "AFTERNOON")]);
    okulApiMock.assignClassSectionShift.mockResolvedValue({ updated: 1 });

    renderPanel();

    expect(await screen.findByText("Şube oturumları")).toBeInTheDocument();
    // Kayıtlı işaret şubenin KENDİ satırında rozet olarak görünür ("Öğleden
    // sonra" metni sekme düğmesinde de geçtiği için satıra inilir).
    expect(screen.getByText("9/B").closest("label")).toHaveTextContent("Öğleden sonra");
    expect(screen.getByText("9/A").closest("label")).toHaveTextContent("—");

    await user.click(screen.getAllByRole("checkbox")[0]);
    await user.click(screen.getByRole("button", { name: "Öğleden sonra yap" }));

    await waitFor(() =>
      expect(okulApiMock.assignClassSectionShift).toHaveBeenCalledWith({
        section_ids: [1],
        shift: "AFTERNOON",
      }),
    );
  });

  it("şube çipleri sınıf düzeyine göre gruplanır; düzey etiketi tümünü seçer", async () => {
    const user = userEvent.setup();
    okulApiMock.getSchoolConfig.mockResolvedValue(config({ education_model: "DUAL" }));
    okulApiMock.listClassSections.mockResolvedValue([
      sube(1, "9/A"),
      sube(2, "9/B"),
      sube(3, "10/A"),
      sube(4, "10/B"),
    ]);
    okulApiMock.assignClassSectionShift.mockResolvedValue({ updated: 2 });

    renderPanel();

    // Düzey etiketi backend'le AYNI yazımda (docs/sozluk.md: "9. Sınıf").
    const dokuz = await screen.findByRole("button", { name: "9. Sınıf" });
    expect(screen.getByRole("button", { name: "10. Sınıf" })).toBeInTheDocument();
    // Her düzey kendi satırında: 9. Sınıf satırı yalnız 9/A ve 9/B taşır.
    const satir = dokuz.parentElement as HTMLElement;
    expect(satir).toHaveTextContent("9/A");
    expect(satir).toHaveTextContent("9/B");
    expect(satir).not.toHaveTextContent("10/A");

    // Etikete basmak o düzeyin TAMAMINI seçer — işaret düzey düzey verilir.
    await user.click(dokuz);
    await user.click(screen.getByRole("button", { name: "Sabah yap" }));

    await waitFor(() =>
      expect(okulApiMock.assignClassSectionShift).toHaveBeenCalledWith({
        section_ids: [1, 2],
        shift: "MORNING",
      }),
    );
  });

  it("düzey etiketine yeniden basmak seçimi kaldırır", async () => {
    const user = userEvent.setup();
    okulApiMock.getSchoolConfig.mockResolvedValue(config({ education_model: "DUAL" }));
    okulApiMock.listClassSections.mockResolvedValue([sube(1, "9/A"), sube(2, "9/B")]);

    renderPanel();

    const dokuz = await screen.findByRole("button", { name: "9. Sınıf" });
    await user.click(dokuz);
    expect(screen.getAllByRole("checkbox").every((c) => (c as HTMLInputElement).checked)).toBe(
      true,
    );

    await user.click(dokuz);
    expect(screen.getAllByRole("checkbox").some((c) => (c as HTMLInputElement).checked)).toBe(
      false,
    );
    expect(screen.getByRole("button", { name: "Sabah yap" })).toBeDisabled();
  });

  it("öğle oturumu sabahın bitişinden türetilir", async () => {
    const user = userEvent.setup();
    okulApiMock.getSchoolConfig.mockResolvedValue(config({ education_model: "DUAL" }));
    okulApiMock.listClassSections.mockResolvedValue([]);
    okulApiMock.previewBellSchedule
      .mockResolvedValueOnce({ periods: [], end_time: "14:25", next_start: "14:45", flow: {} })
      .mockResolvedValueOnce({
        periods: [{ no: 1, name: "1. Ders", start: "14:45" }],
        end_time: "20:00",
        next_start: "20:20",
        flow: {},
      });

    renderPanel();
    await user.click(await screen.findByRole("button", { name: "Öğleden sonra" }));
    await user.click(screen.getByRole("button", { name: "Sabaha göre hesapla" }));

    await waitFor(() => expect(okulApiMock.previewBellSchedule).toHaveBeenCalledTimes(2));
    // İkinci çağrı öğle akışını SABAHIN önerdiği saatle sorar.
    expect(okulApiMock.previewBellSchedule).toHaveBeenLastCalledWith(
      expect.objectContaining({ first_lesson: "14:45" }),
    );
    expect(await screen.findByLabelText("1. Ders")).toHaveValue("14:45");
  });
});
