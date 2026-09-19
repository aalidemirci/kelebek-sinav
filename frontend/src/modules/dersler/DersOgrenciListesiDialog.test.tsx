// Seçmeli dersin şube öğrenci listesi (19.09.2026): kural şube bazındadır —
// "Şubenin tamamı" boş liste gönderir, "Yalnız işaretlenen" öğrenci kimliklerini;
// "İşaretlenmeyen öğrenciler" seçimi öbür seçmelinin listesini aynı adımda yazar.
// KVKK: adlar ve numaralar uydurmadır.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { Student } from "../okul/api";
import type { Course, SetSectionEnrollmentBody, SetSectionEnrollmentResult } from "./api";

const dersler = vi.hoisted(() => ({
  listCourses: vi.fn(),
  setSectionEnrollment: vi.fn(
    (_courseId: number, body: SetSectionEnrollmentBody): Promise<SetSectionEnrollmentResult> =>
      Promise.resolve({
        school_year: 1,
        section_id: body.section_id,
        student_ids: body.student_ids,
        complement: null,
      }),
  ),
}));

const okul = vi.hoisted(() => ({
  listStudents: vi.fn(),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, derslerApi: { ...actual.derslerApi, ...dersler } };
});
vi.mock("../okul/api", async (importActual) => {
  const actual = await importActual<typeof import("../okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...okul } };
});

import DersOgrenciListesiDialog from "./DersOgrenciListesiDialog";

function ders(overrides: Partial<Course> = {}): Course {
  return {
    id: 7,
    name: "Kur'an-ı Kerim",
    levels: [9],
    level_labels: ["9. Sınıf"],
    course_type: "ELECTIVE",
    source: "MEB_CATALOG",
    exam_mode: "WRITTEN",
    exam_mode_label: "Yazılı",
    is_active: true,
    catalog_excluded: false,
    ...overrides,
  };
}

const KURAN = ders();
const PEYGAMBER = ders({ id: 8, name: "Peygamberimizin Hayatı" });

function ogrenci(id: number, no: string, ad: string): Student {
  return {
    id,
    first_name: ad,
    last_name: "Deneme",
    full_name: `${ad} Deneme`,
    student_number: no,
    class_level: 9,
    class_section: "A",
    class_label: "9/A",
    status: "ACTIVE",
  };
}

// Numara sırası sayısaldır: "9" < "10" < "100" (metin sırası "10" < "100" < "9" derdi).
const SUBE = [ogrenci(3, "100", "Cem"), ogrenci(1, "10", "Ali"), ogrenci(2, "9", "Banu")];

function renderDialog(listedIds: number[] | null, onSaved = vi.fn(), onClose = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <DersOgrenciListesiDialog
          course={KURAN}
          section={{ id: 11, class_level: 9, class_section: "A", class_label: "9/A" }}
          listedIds={listedIds}
          onClose={onClose}
          onSaved={onSaved}
        />
      </SnackbarProvider>
    </QueryClientProvider>,
  );
  return { onSaved, onClose };
}

afterEach(() => vi.clearAllMocks());

describe("DersOgrenciListesiDialog", () => {
  it("listesiz şube “Şubenin tamamı” açılır ve kaydetme boş liste gönderir", async () => {
    const user = userEvent.setup();
    okul.listStudents.mockResolvedValue({ count: 3, results: SUBE });
    dersler.listCourses.mockResolvedValue([KURAN, PEYGAMBER]);
    const { onSaved } = renderDialog(null);

    expect(
      screen.getByRole("dialog", { name: "Kur'an-ı Kerim — 9/A öğrencileri" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Şubenin tamamı bu dersi alıyor" })).toBeChecked();
    // Tamamı kipinde öğrenci kutuları çizilmez.
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();

    await waitFor(() => expect(screen.getByRole("button", { name: "Kaydet" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(dersler.setSectionEnrollment).toHaveBeenCalledWith(7, {
        section_id: 11,
        student_ids: [],
      }),
    );
    expect(onSaved).toHaveBeenCalled();
    expect(
      await screen.findByText("9/A şubesinin “Kur'an-ı Kerim” listesi kaydedildi."),
    ).toBeInTheDocument();
    // Sorgu sınıf düzeyi + şubeyle, yalnız aktif öğrencilerle yapılır.
    expect(okul.listStudents).toHaveBeenCalledWith({
      classLevel: 9,
      classSection: "A",
      onlyActive: true,
      limit: 500,
    });
  });

  it("işaretlenen öğrenciler ve kalanların yazılacağı ders birlikte gönderilir", async () => {
    const user = userEvent.setup();
    okul.listStudents.mockResolvedValue({ count: 3, results: SUBE });
    dersler.listCourses.mockResolvedValue([KURAN, PEYGAMBER]);
    renderDialog(null);

    await user.click(screen.getByRole("radio", { name: "Yalnız işaretlenen öğrenciler alıyor" }));
    const kutular = await screen.findAllByRole("checkbox");
    // Okul numarası sayı gibi sıralanır.
    expect(kutular.map((k) => k.getAttribute("aria-label"))).toEqual([
      "9 Banu Deneme",
      "10 Ali Deneme",
      "100 Cem Deneme",
    ]);
    // Hiç işaret yokken kaydetme kapalı ve gerekçe söylenir.
    expect(screen.getByRole("button", { name: "Kaydet" })).toBeDisabled();
    expect(screen.getByText(/En az bir öğrenci işaretleyin/)).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "9 Banu Deneme" }));
    await user.click(screen.getByRole("checkbox", { name: "100 Cem Deneme" }));
    expect(screen.getByText("2 / 3 öğrenci işaretli")).toBeInTheDocument();

    // Kalanlar için yalnız öbür seçmeliler listelenir (dersin kendisi değil).
    const kalan = screen.getByRole("combobox", { name: "İşaretlenmeyen öğrenciler" });
    expect(
      screen.queryByRole("option", { name: "Kur'an-ı Kerim dersine yaz" }),
    ).not.toBeInTheDocument();
    await user.selectOptions(kalan, "8");
    expect(
      screen.getByText("1 öğrenci seçilen dersin bu şubedeki listesi olur (eski listesi değişir)."),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(dersler.setSectionEnrollment).toHaveBeenCalled());
    const [dersId, govde] = dersler.setSectionEnrollment.mock.calls[0];
    expect(dersId).toBe(7);
    expect(govde.section_id).toBe(11);
    expect([...govde.student_ids].sort()).toEqual([2, 3]);
    expect(govde.complement_course_id).toBe(8);
  });

  it("kayıtlı liste işaretli açılır; şubeden ayrılan öğrenci sayılmaz", async () => {
    const user = userEvent.setup();
    okul.listStudents.mockResolvedValue({ count: 3, results: SUBE });
    dersler.listCourses.mockResolvedValue([KURAN]);
    // 99 artık bu şubede değil (nakil / şube değişikliği).
    renderDialog([1, 99]);

    expect(
      screen.getByRole("radio", { name: "Yalnız işaretlenen öğrenciler alıyor" }),
    ).toBeChecked();
    expect(await screen.findByRole("checkbox", { name: "10 Ali Deneme" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "9 Banu Deneme" })).not.toBeChecked();
    expect(screen.getByText("1 / 3 öğrenci işaretli")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Tümünü işaretle" }));
    expect(screen.getByText("3 / 3 öğrenci işaretli")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "İşaretleri kaldır" }));
    expect(screen.getByText("0 / 3 öğrenci işaretli")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kaydet" })).toBeDisabled();
  });

  it("servis reddi gerekçesiyle gösterilir; diyalog açık kalır", async () => {
    const user = userEvent.setup();
    okul.listStudents.mockResolvedValue({ count: 3, results: SUBE });
    dersler.listCourses.mockResolvedValue([KURAN]);
    dersler.setSectionEnrollment.mockRejectedValueOnce(
      new ApiError(400, "validation_error", "1 öğrenci bu şubenin aktif öğrencisi değil."),
    );
    const { onSaved } = renderDialog([1]);

    await screen.findByRole("checkbox", { name: "10 Ali Deneme" });
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    expect(
      await screen.findByText("1 öğrenci bu şubenin aktif öğrencisi değil."),
    ).toBeInTheDocument();
    expect(onSaved).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: /9\/A öğrencileri/ })).toBeInTheDocument();
  });

  it("şubede aktif öğrenci yoksa bunu söyler", async () => {
    const user = userEvent.setup();
    okul.listStudents.mockResolvedValueOnce({ count: 0, results: [] });
    dersler.listCourses.mockResolvedValue([KURAN]);
    renderDialog(null);
    await user.click(screen.getByRole("radio", { name: "Yalnız işaretlenen öğrenciler alıyor" }));
    expect(await screen.findByText("Bu şubede kayıtlı aktif öğrenci yok.")).toBeInTheDocument();
  });

  it("öğrenci listesi okunamazsa gerekçe role=alert ile basılır", async () => {
    const user = userEvent.setup();
    okul.listStudents.mockRejectedValue(new ApiError(500, "server_error", "Veritabanı kilitli."));
    dersler.listCourses.mockResolvedValue([KURAN]);
    renderDialog(null);
    await user.click(screen.getByRole("radio", { name: "Yalnız işaretlenen öğrenciler alıyor" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Öğrenciler yüklenemedi: Veritabanı kilitli.",
    );
  });
});
