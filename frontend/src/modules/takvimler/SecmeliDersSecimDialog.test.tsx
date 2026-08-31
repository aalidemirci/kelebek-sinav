// Seçmeli ders seçim dialog'u testleri (F6 sadeleştirmesi): seviye sekmesi
// değişimi, havuzdaki dersin kilitli gelmesi, şube kümesi çipinin şubeleri
// seçime EKLEMESİ, kaydetmenin TEK bulkEntries çağrısı yapması ve atlanan
// derslerin sessizce düşmemesi. okulApi'nin İKİ ucu da mock'lanır — kümeler
// mock'lanmazsa çip hiç çizilmez (SinavSihirbazi.test.tsx'teki tuzak).

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { ClassSection, ClassSectionGroup } from "../okul/api";
import { makeBulkResult, makeElectiveOptions } from "./testFixtures";

const calApi = vi.hoisted(() => ({
  electiveOptions: vi.fn(),
  bulkEntries: vi.fn(),
}));

const okul = vi.hoisted(() => ({
  listClassSections: vi.fn(),
  listClassSectionGroups: vi.fn(),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, examCalendarApi: { ...actual.examCalendarApi, ...calApi } };
});
vi.mock("../okul/api", async (importActual) => {
  const actual = await importActual<typeof import("../okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...okul } };
});

import SecmeliDersSecimDialog from "./SecmeliDersSecimDialog";

// KVKK: şube adları uydurmadır; öğrenci verisi hiç kullanılmaz.
function sube(overrides: Partial<ClassSection> = {}): ClassSection {
  return {
    id: 101,
    school_year: 1,
    school_year_name: "2026-2027",
    class_level: 9,
    class_section: "A",
    class_label: "9/A",
    group: 1,
    group_name: "Sayısal",
    ...overrides,
  };
}

function kume(overrides: Partial<ClassSectionGroup> = {}): ClassSectionGroup {
  return { id: 1, name: "Sayısal", order: 1, section_count: 2, ...overrides };
}

const SUBELER: ClassSection[] = [
  sube(),
  sube({ id: 102, class_section: "B", class_label: "9/B" }),
  sube({ id: 103, class_section: "C", class_label: "9/C", group: null, group_name: "" }),
  sube({ id: 111, class_level: 10, class_section: "A", class_label: "10/A" }),
];

function renderDialog(onSaved: () => void = () => {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <SecmeliDersSecimDialog calendarId={7} onClose={() => {}} onSaved={onSaved} />
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("SecmeliDersSecimDialog", () => {
  it("seviye sekmesi değişince o seviyenin seçmelileri listelenir", async () => {
    const user = userEvent.setup();
    calApi.electiveOptions.mockResolvedValue(makeElectiveOptions());
    okul.listClassSections.mockResolvedValue(SUBELER);
    okul.listClassSectionGroups.mockResolvedValue([kume()]);

    renderDialog();
    expect(
      await screen.findByRole("checkbox", { name: /Çağdaş Türk ve Dünya Tarihi/ }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "10. Sınıf" }));

    expect(
      await screen.findByRole("checkbox", { name: /Astronomi ve Uzay Bilimleri/ }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("checkbox", { name: /Çağdaş Türk ve Dünya Tarihi/ }),
    ).not.toBeInTheDocument();
  });

  it("havuzda olan ders işaretli ve kilitli gelir", async () => {
    calApi.electiveOptions.mockResolvedValue(makeElectiveOptions());
    okul.listClassSections.mockResolvedValue(SUBELER);
    okul.listClassSectionGroups.mockResolvedValue([kume()]);

    renderDialog();

    const havuzdaki = await screen.findByRole("checkbox", { name: /Almanca/ });
    expect(havuzdaki).toBeChecked();
    expect(havuzdaki).toBeDisabled();
  });

  it("şube kümesi çipi kümedeki şubeleri seçime EKLER (ayrı durum tutmaz)", async () => {
    const user = userEvent.setup();
    calApi.electiveOptions.mockResolvedValue(makeElectiveOptions());
    okul.listClassSections.mockResolvedValue(SUBELER);
    okul.listClassSectionGroups.mockResolvedValue([kume()]);

    renderDialog();
    await user.click(await screen.findByRole("checkbox", { name: /Çağdaş Türk ve Dünya Tarihi/ }));
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Çağdaş Türk ve Dünya Tarihi katılımcı kapsamı" }),
      "SECTIONS",
    );

    await user.click(
      await screen.findByRole("button", {
        name: "Çağdaş Türk ve Dünya Tarihi: Sayısal kümesini ekle",
      }),
    );

    // Küme yalnız 9/A ve 9/B'yi kapsar; 9/C kümesizdir, 10/A başka seviyededir.
    expect(screen.getByRole("checkbox", { name: /9\/A/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /9\/B/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /9\/C/ })).not.toBeChecked();
    expect(screen.queryByRole("checkbox", { name: /10\/A/ })).not.toBeInTheDocument();

    // Çip EKLER: elle işaretlenen şube kümeden gelenlerin yanına yazılır.
    await user.click(screen.getByRole("checkbox", { name: /9\/C/ }));
    expect(screen.getByRole("checkbox", { name: /9\/A/ })).toBeChecked();
  });

  it("kaydetme seçilen dersleri TEK bulkEntries çağrısında yollar", async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    calApi.electiveOptions.mockResolvedValue(makeElectiveOptions());
    calApi.bulkEntries.mockResolvedValue(
      makeBulkResult({ created: ["Çağdaş Türk ve Dünya Tarihi — 9. Sınıf"] }),
    );
    okul.listClassSections.mockResolvedValue(SUBELER);
    okul.listClassSectionGroups.mockResolvedValue([kume()]);

    renderDialog(onSaved);
    await user.click(await screen.findByRole("checkbox", { name: /Çağdaş Türk ve Dünya Tarihi/ }));
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Çağdaş Türk ve Dünya Tarihi katılımcı kapsamı" }),
      "SECTIONS",
    );
    await user.click(await screen.findByRole("checkbox", { name: /9\/B/ }));

    // İkinci seviyeden bir ders daha: kalemler seviye başına ayrı satırdır.
    await user.click(screen.getByRole("tab", { name: "10. Sınıf" }));
    await user.click(await screen.findByRole("checkbox", { name: /Astronomi ve Uzay Bilimleri/ }));

    await user.click(screen.getByRole("button", { name: /Havuza ekle/ }));

    await waitFor(() => expect(calApi.bulkEntries).toHaveBeenCalledTimes(1));
    expect(calApi.bulkEntries).toHaveBeenCalledWith(7, [
      { course_id: 21, level: 9, participant_type: "SECTIONS", section_ids: [102] },
      { course_id: 23, level: 10, participant_type: "LEVEL", section_ids: [] },
    ]);
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it("atlanan dersler uyarı olarak gösterilir (sessizce düşmez)", async () => {
    const user = userEvent.setup();
    calApi.electiveOptions.mockResolvedValue(makeElectiveOptions());
    calApi.bulkEntries.mockResolvedValue(
      makeBulkResult({ skipped: ["Çağdaş Türk ve Dünya Tarihi — 9. Sınıf (ders pasif)"] }),
    );
    okul.listClassSections.mockResolvedValue(SUBELER);
    okul.listClassSectionGroups.mockResolvedValue([kume()]);

    renderDialog();
    await user.click(await screen.findByRole("checkbox", { name: /Çağdaş Türk ve Dünya Tarihi/ }));
    await user.click(screen.getByRole("button", { name: /Havuza ekle/ }));

    expect(await screen.findByText(/1 ders atlandı/)).toBeInTheDocument();
    expect(screen.getByText(/ders pasif/)).toBeInTheDocument();
  });

  it("şube seçilmemiş “Şube seç” satırı kaydetmeyi kapatır", async () => {
    const user = userEvent.setup();
    calApi.electiveOptions.mockResolvedValue(makeElectiveOptions());
    okul.listClassSections.mockResolvedValue(SUBELER);
    okul.listClassSectionGroups.mockResolvedValue([kume()]);

    renderDialog();
    await user.click(await screen.findByRole("checkbox", { name: /Çağdaş Türk ve Dünya Tarihi/ }));
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Çağdaş Türk ve Dünya Tarihi katılımcı kapsamı" }),
      "SECTIONS",
    );

    expect(screen.getByRole("button", { name: /Havuza ekle/ })).toBeDisabled();
    expect(await screen.findByRole("alert")).toHaveTextContent(/Şube seçilmemiş ders var/);
  });

  it("toplu kapsam kısayolu aktif seviyedeki seçili derslere uygulanır", async () => {
    const user = userEvent.setup();
    calApi.electiveOptions.mockResolvedValue(makeElectiveOptions());
    calApi.bulkEntries.mockResolvedValue(makeBulkResult({ created: ["Çağdaş Türk — 9. Sınıf"] }));
    okul.listClassSections.mockResolvedValue(SUBELER);
    okul.listClassSectionGroups.mockResolvedValue([kume()]);

    renderDialog();
    await user.click(await screen.findByRole("checkbox", { name: /Çağdaş Türk ve Dünya Tarihi/ }));

    await user.selectOptions(screen.getByRole("combobox", { name: "Kapsam" }), "SECTIONS");
    await user.click(await screen.findByRole("checkbox", { name: "Toplu: 9/A" }));
    await user.click(screen.getByRole("button", { name: /Seçili 1 derse uygula/ }));

    await user.click(screen.getByRole("button", { name: /Havuza ekle/ }));
    await waitFor(() =>
      expect(calApi.bulkEntries).toHaveBeenCalledWith(7, [
        { course_id: 21, level: 9, participant_type: "SECTIONS", section_ids: [101] },
      ]),
    );
  });
});
