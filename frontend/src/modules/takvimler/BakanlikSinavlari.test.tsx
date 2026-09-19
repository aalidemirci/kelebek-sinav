// Bakanlığın ülke geneli ortak yazılı sınavları bandı (19.09.2026): sınavlar
// gün adıyla listelenir, takvimdeki durumu yazar; "Takvime uygula" yalnız
// taslakta ve uygulanmamış sınav varken görünür, sonucu satır satır söyler.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { NationalExamRow } from "./api";

const calApi = vi.hoisted(() => ({
  nationalExams: vi.fn(),
  applyNationalExams: vi.fn(),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, examCalendarApi: { ...actual.examCalendarApi, ...calApi } };
});

import BakanlikSinavlari from "./BakanlikSinavlari";

const KAYNAK =
  "MEB Ölçme, Değerlendirme ve Sınav Hizmetleri Genel Müdürlüğünün 10.09.2026 tarihli ve " +
  "E-26614336-480.99-168561496 sayılı yazısı eki (Ülke Geneli Ortak Yazılı Sınav Takvimi)";

function satir(overrides: Partial<NationalExamRow> = {}): NationalExamRow {
  return {
    level: 10,
    level_label: "10. Sınıf",
    course_name: "Türk Dili ve Edebiyatı",
    date: "2026-11-12",
    weekday_label: "Perşembe",
    source: KAYNAK,
    course_id: 7,
    entry_id: 3,
    period_no: null,
    status: "pending",
    ...overrides,
  };
}

function renderBant(editable = true) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const onApplied = vi.fn();
  render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <BakanlikSinavlari calendarId={5} editable={editable} onApplied={onApplied} />
      </SnackbarProvider>
    </QueryClientProvider>,
  );
  return { onApplied };
}

afterEach(() => vi.clearAllMocks());

describe("BakanlikSinavlari", () => {
  it("sınavı gün adı ve dayanağıyla listeler; uygulayınca sonucu söyler", async () => {
    const user = userEvent.setup();
    calApi.nationalExams.mockResolvedValue({ exams: [satir()] });
    calApi.applyNationalExams.mockResolvedValue({
      result: {
        placed: ["10. Sınıf Türk Dili ve Edebiyatı (12.11.2026): 1. ders saati"],
        unchanged: [],
        skipped: [],
      },
      exams: [satir({ status: "placed", period_no: 1 })],
    });
    const { onApplied } = renderBant();

    expect(await screen.findByText("10. Sınıf Türk Dili ve Edebiyatı")).toBeInTheDocument();
    expect(screen.getByText(/12\.11\.2026 Perşembe · takvime uygulanmadı/)).toBeInTheDocument();
    expect(screen.getByText(/10\.09\.2026 tarihli/)).toBeInTheDocument();
    expect(
      screen.getByText(/ders saati Bakanlığın uygulama esaslarıyla kesinleşir/),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Takvime uygula" }));

    await waitFor(() => expect(calApi.applyNationalExams).toHaveBeenCalledWith(5));
    expect(await screen.findByText(/takvimde, 1\. ders saati/)).toBeInTheDocument();
    expect(
      screen.getByText(
        "Yerleştirildi: 10. Sınıf Türk Dili ve Edebiyatı (12.11.2026): 1. ders saati",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("1 Bakanlık sınavı takvime yerleştirildi.")).toBeInTheDocument();
    expect(onApplied).toHaveBeenCalled();
    // Hepsi yerleşince düğme kalkar.
    expect(screen.queryByRole("button", { name: "Takvime uygula" })).not.toBeInTheDocument();
  });

  it("onaylı takvimde düğme yok; eksik dersi nedeniyle yazar", async () => {
    calApi.nationalExams.mockResolvedValue({
      exams: [satir({ status: "missing_course", course_id: null, entry_id: null })],
    });
    renderBant(false);

    expect(await screen.findByText(/ders havuzunda bu adla ders yok/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Takvime uygula" })).not.toBeInTheDocument();
  });

  it("o turda Bakanlık sınavı yoksa hiçbir şey çizmez", async () => {
    calApi.nationalExams.mockResolvedValue({ exams: [] });
    renderBant();

    await waitFor(() => expect(calApi.nationalExams).toHaveBeenCalled());
    expect(screen.queryByRole("region", { name: "Bakanlık sınavları" })).not.toBeInTheDocument();
  });
});
