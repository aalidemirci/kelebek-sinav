// Ders havuzu testleri: "Sınav" sütunu (yazılı / uygulama / sınav yok) ve
// satırdan düzenleme yolu. Sınav biçimi takvim havuzunun neyi kendiliğinden
// çekeceğini belirler — sütun kayarsa idareci yanlış dersi siler.
// Sayfa react-query kullanmaz (useState + Promise.all); sağlayıcı olarak
// Snackbar + Confirm yeter. KVKK: ders adları kataloğa aittir, kişi verisi yok.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { Course } from "./api";

const dersler = vi.hoisted(() => ({
  listCourses: vi.fn(),
  listDuplicates: vi.fn(() => Promise.resolve([])),
  createCourse: vi.fn(),
  updateCourse: vi.fn(),
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
  return render(
    <SnackbarProvider>
      <ConfirmProvider>
        <DersHavuzuPage />
      </ConfirmProvider>
    </SnackbarProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("DersHavuzuPage", () => {
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
});
