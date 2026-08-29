// Kurulum sihirbazı testi (DD kalıbından KS'ye): üç adımın mutlu yolu + kapılar +
// hata durumu. `../okul/api` (kurulum + ders yılı uçlarının tek sınırı) vi.mock ile taklit
// edilir; yönlendirme GERÇEK router üzerinden doğrulanır (useNavigate mock'lanmaz —
// "/" rotası bir işaretle render edilir, sihirbaz oraya gidince işaret ekrana düşer).

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { SetupStatus } from "../okul/api";

const oapi = vi.hoisted(() => ({
  getSetupStatus: vi.fn(),
  getSchoolConfig: vi.fn(),
  updateSchoolConfig: vi.fn(),
  completeSetup: vi.fn(),
  listSchoolYears: vi.fn(),
  createSchoolYear: vi.fn(),
  configureSchoolTerms: vi.fn(),
  activateSchoolYear: vi.fn(),
}));

vi.mock("../okul/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../okul/api")>();
  return { ...actual, okulApi: oapi };
});

import KurulumPage from "./KurulumPage";

const BOS_DURUM: SetupStatus = {
  setup_completed: false,
  school_name: "",
  has_active_school_year: false,
  student_count: 0,
  personnel_count: 0,
  class_section_count: 0,
};

const BOS_CONFIG = {
  school_name: "",
  province: "",
  district: "",
  principal_name: "",
  school_type: "ANADOLU_LISESI" as const,
  has_prep_class: false,
  setup_completed: false,
};

/** `state` kapı yönlendirmesini taklit eder (KurulumKapisi'nin taşıdığı sebep). */
function renderPage(state?: unknown) {
  return render(
    <SnackbarProvider>
      <MemoryRouter initialEntries={[{ pathname: "/kurulum", state }]}>
        <Routes>
          <Route path="/kurulum" element={<KurulumPage />} />
          <Route path="/" element={<div>PANEL EKRANI</div>} />
        </Routes>
      </MemoryRouter>
    </SnackbarProvider>,
  );
}

beforeEach(() => {
  oapi.getSetupStatus.mockResolvedValue(BOS_DURUM);
  oapi.getSchoolConfig.mockResolvedValue(BOS_CONFIG);
  oapi.listSchoolYears.mockResolvedValue([]);
  oapi.configureSchoolTerms.mockResolvedValue([]);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("KurulumPage", () => {
  it("boş kurulumda 1. adımdan başlar; okul bilgileri kaydedilince 2. adıma geçer", async () => {
    oapi.updateSchoolConfig.mockResolvedValue({ ...BOS_CONFIG, school_name: "Deneme Lisesi" });
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("1. Okul bilgileri")).toBeInTheDocument();
    await user.type(screen.getByLabelText(/Okul adı/), "Deneme Lisesi");
    await user.type(screen.getByLabelText("İl"), "Ankara");
    await user.click(screen.getByRole("button", { name: /Kaydet ve devam/ }));

    await waitFor(() =>
      expect(oapi.updateSchoolConfig).toHaveBeenCalledWith({
        school_name: "Deneme Lisesi",
        province: "Ankara",
        district: "",
        principal_name: "",
        school_type: "ANADOLU_LISESI",
        has_prep_class: false,
      }),
    );
    expect(await screen.findByText("2. Ders yılı")).toBeInTheDocument();
  });

  it("okul adı boşken 'Kaydet ve devam' pasiftir", async () => {
    renderPage();
    expect(await screen.findByText("1. Okul bilgileri")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Kaydet ve devam/ })).toBeDisabled();
  });

  it("kayıt hatasında Türkçe hata bandı + alan hatası gösterilir", async () => {
    oapi.updateSchoolConfig.mockRejectedValue(
      new ApiError(400, "validation_error", "Okul adı çok uzun.", { school_name: ["Çok uzun."] }),
    );
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("1. Okul bilgileri");
    await user.type(screen.getByLabelText(/Okul adı/), "X");
    await user.click(screen.getByRole("button", { name: /Kaydet ve devam/ }));

    expect(await screen.findByText("Okul adı çok uzun.")).toBeInTheDocument();
    // Alan hatası backend {fields} sözleşmesinden okunur.
    expect(await screen.findByText("Çok uzun.")).toBeInTheDocument();
    // Hata varken adım değişmez.
    expect(screen.getByText("1. Okul bilgileri")).toBeInTheDocument();
  });

  it("aktif ders yılı yokken İleri kapalıdır; oluşturulan yıl aktifleştirilir", async () => {
    oapi.getSetupStatus
      .mockResolvedValueOnce({ ...BOS_DURUM, school_name: "Deneme Lisesi" }) // ilk yükleme
      .mockResolvedValue({
        ...BOS_DURUM,
        school_name: "Deneme Lisesi",
        has_active_school_year: true,
      });
    oapi.getSchoolConfig.mockResolvedValue({ ...BOS_CONFIG, school_name: "Deneme Lisesi" });
    oapi.createSchoolYear.mockResolvedValue({
      id: 5,
      name: "2026-2027",
      start_date: "2026-09-01",
      end_date: "2027-06-30",
      is_active: false,
    });
    oapi.activateSchoolYear.mockResolvedValue({});
    const user = userEvent.setup();
    renderPage();

    // Okul adı dolu + aktif yıl yok → sihirbaz 2. adımdan açılır, İleri kapalı.
    expect(await screen.findByText("2. Ders yılı")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /İleri/ })).toBeDisabled();
    expect(screen.getByText(/Devam etmek için bir ders yılını aktifleştirin/)).toBeInTheDocument();

    await user.clear(screen.getByLabelText(/^Ad/));
    await user.type(screen.getByLabelText(/^Ad/), "2026-2027");
    fireEvent.change(screen.getByLabelText(/Başlangıç/), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText(/Bitiş/), { target: { value: "2027-06-30" } });
    await user.click(screen.getByRole("button", { name: /Ders yılını kaydet ve aktifleştir/ }));

    await waitFor(() =>
      expect(oapi.createSchoolYear).toHaveBeenCalledWith({
        name: "2026-2027",
        start_date: "2026-09-01",
        end_date: "2027-06-30",
      }),
    );
    await waitFor(() =>
      expect(oapi.configureSchoolTerms).toHaveBeenCalledWith(5, {
        first_term_end: "2027-01-16",
        second_term_start: "2027-02-02",
      }),
    );
    await waitFor(() => expect(oapi.activateSchoolYear).toHaveBeenCalledWith(5));
    // Durum tazelendi → kapı açılır.
    await waitFor(() => expect(screen.getByRole("button", { name: /İleri/ })).toBeEnabled());
  });

  it("son adım: sayımlar görünür, kurulum tamamlanınca panele yönlendirilir", async () => {
    oapi.getSetupStatus.mockResolvedValue({
      setup_completed: false,
      school_name: "Deneme Lisesi",
      has_active_school_year: true,
      student_count: 612,
      personnel_count: 48,
      class_section_count: 21,
    });
    oapi.getSchoolConfig.mockResolvedValue({ ...BOS_CONFIG, school_name: "Deneme Lisesi" });
    oapi.completeSetup.mockResolvedValue({ setup_completed: true });
    const user = userEvent.setup();
    renderPage();

    // Tüm ölçütler tamam → sihirbaz son adımdan açılır.
    expect(await screen.findByText("3. Kişiler")).toBeInTheDocument();
    expect(screen.getByText("612")).toBeInTheDocument();
    expect(screen.getByText("48")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Kurulumu tamamla/ }));
    await waitFor(() => expect(oapi.completeSetup).toHaveBeenCalled());
    expect(await screen.findByText("PANEL EKRANI")).toBeInTheDocument();
  });

  it("kapı yönlendirmesinde neden sihirbaza getirildiği yazılı olarak söylenir", async () => {
    renderPage({ kapiYonlendirdi: "/kisiler" });
    expect(
      await screen.findByText(/Kurulum tamamlanmadan diğer ekranlar açılmaz/),
    ).toBeInTheDocument();
  });

  it("doğrudan açılışta kapı açıklaması gösterilmez", async () => {
    renderPage();
    await screen.findByText("1. Okul bilgileri");
    expect(screen.queryByText(/Kurulum tamamlanmadan diğer ekranlar açılmaz/)).toBeNull();
  });

  it("3. adım sicil aktarımının kurulumdan SONRA yapıldığını söyler", async () => {
    oapi.getSetupStatus.mockResolvedValue({
      ...BOS_DURUM,
      school_name: "Deneme Lisesi",
      has_active_school_year: true,
    });
    oapi.getSchoolConfig.mockResolvedValue({ ...BOS_CONFIG, school_name: "Deneme Lisesi" });
    renderPage();

    expect(await screen.findByText("3. Kişiler")).toBeInTheDocument();
    // "Kişiler" vurgulu span içinde olduğundan metin düğüm düğüm eşleşir.
    expect(screen.getByText(/kurulum tamamlandıktan sonra/)).toBeInTheDocument();
  });

  it("durum yüklenemezse hata bandı gösterilir, adım içeriği render edilmez", async () => {
    oapi.getSetupStatus.mockRejectedValue(
      new ApiError(500, "server_error", "Sunucuya ulaşılamadı."),
    );
    renderPage();

    expect(await screen.findByText("Sunucuya ulaşılamadı.")).toBeInTheDocument();
    expect(screen.queryByText("1. Okul bilgileri")).not.toBeInTheDocument();
  });
});
