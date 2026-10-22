// Bakanlık takvimleri bandı: ülke geneli sınavlar (19.09.2026) gün adıyla
// listelenir, takvimdeki durumu yazar; OYSS uygulama takvimi (22.10.2026) gün +
// ders saatiyle, düzeyleri birleştirerek listelenir, açıklama satırları sunucudan
// gelir. "Takvime uygula" yalnız taslakta ve uygulanmamış sınav varken görünür,
// ikisini birlikte uygular ve sonucu satır satır söyler.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { NationalExamRow, OyssExamRow, OyssInfo } from "./api";

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

const OYSS_BILGI: OyssInfo = {
  source:
    "Okul Geneli Ortak Yazılı Sınav Uygulama Takvimi (Ortak Yazılı Sınav Sistemi, " +
    "2026-2027 1. dönem 1. yazılı sınavlar; ÖDSHGM, Ekim 2026)",
  duration_minutes: 40,
  makeup_start: "2026-11-23",
  makeup_end: "2026-11-27",
  notes: [
    "Günde tek sınav 2. ders saatinde, iki sınav 2. ve 4. ders saatlerinde uygulanır; süre 40 dakikadır.",
    "Mazeret sınavları 23.11.2026 – 27.11.2026 arasında, okul müdürlüğünün planlamasıyla OYSS üzerinden yapılır.",
  ],
};

const BOS_SONUC = { placed: [], unchanged: [], skipped: [] };

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

function oyssSatir(overrides: Partial<OyssExamRow> = {}): OyssExamRow {
  return {
    level: 9,
    level_label: "9. Sınıf",
    course_name: "Biyoloji",
    pool_course_name: "Biyoloji",
    date: "2026-11-03",
    weekday_label: "Salı",
    period_no: 2,
    course_id: 11,
    entry_id: 21,
    entry_date: "2026-11-03",
    entry_period_no: 2,
    status: "placed",
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
    calApi.nationalExams.mockResolvedValue({ exams: [satir()], oyss: [], oyss_info: null });
    calApi.applyNationalExams.mockResolvedValue({
      result: {
        placed: ["10. Sınıf Türk Dili ve Edebiyatı (12.11.2026): 1. ders saati"],
        unchanged: [],
        skipped: [],
      },
      oyss_result: BOS_SONUC,
      exams: [satir({ status: "placed", period_no: 1 })],
      oyss: [],
      oyss_info: null,
    });
    const { onApplied } = renderBant();

    expect(await screen.findByText("10. Sınıf Türk Dili ve Edebiyatı")).toBeInTheDocument();
    expect(screen.getByText(/12\.11\.2026 Perşembe · takvime uygulanmadı/)).toBeInTheDocument();
    expect(screen.getByText(/10\.09\.2026 tarihli/)).toBeInTheDocument();
    expect(
      screen.getByText(/ders saati Bakanlığın uygulama esaslarıyla kesinleşir/),
    ).toBeInTheDocument();
    // OYSS takvimi yoksa OYSS bölümü çizilmez.
    expect(screen.queryByText(/Ortak Yazılı Sınav Sistemi/)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Takvime uygula" }));

    await waitFor(() => expect(calApi.applyNationalExams).toHaveBeenCalledWith(5));
    expect(await screen.findByText(/takvimde, 1\. ders saati/)).toBeInTheDocument();
    expect(
      screen.getByText(
        "Yerleştirildi: 10. Sınıf Türk Dili ve Edebiyatı (12.11.2026): 1. ders saati",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("1 sınav Bakanlık takvimine göre yerleştirildi.")).toBeInTheDocument();
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

  it("OYSS sınavlarını düzeyleri birleştirerek gün ve ders saatiyle listeler", async () => {
    calApi.nationalExams.mockResolvedValue({
      exams: [],
      oyss: [
        oyssSatir(),
        oyssSatir({ level: 10, level_label: "10. Sınıf", entry_id: 22 }),
        oyssSatir({
          level: 9,
          course_name: "Kimya",
          pool_course_name: "Kimya",
          date: "2026-11-04",
          weekday_label: "Çarşamba",
          entry_date: "2026-11-04",
          entry_period_no: 3,
        }),
        oyssSatir({
          level: 11,
          level_label: "11. Sınıf",
          course_name: "Matematik",
          pool_course_name: "Seçmeli Matematik",
          date: "2026-11-05",
          weekday_label: "Perşembe",
          entry_id: null,
          entry_date: null,
          entry_period_no: null,
          status: "needs_pool",
        }),
        oyssSatir({
          course_name: "Coğrafya",
          pool_course_name: "Coğrafya",
          date: "2026-11-10",
          weekday_label: "Salı",
          period_no: 4,
          entry_date: "2026-11-05",
          entry_period_no: 1,
          status: "pending",
        }),
        oyssSatir({
          course_name: "Felsefe",
          pool_course_name: "",
          date: "2026-11-06",
          weekday_label: "Cuma",
          period_no: null,
          course_id: null,
          entry_id: null,
          entry_date: null,
          entry_period_no: null,
          status: "missing_course",
        }),
      ],
      oyss_info: OYSS_BILGI,
    });
    renderBant();

    expect(
      await screen.findByText("Ortak Yazılı Sınav Sistemi (OYSS) uygulama takvimi"),
    ).toBeInTheDocument();
    const biyoloji = screen.getByText("Biyoloji — 9. ve 10. Sınıf").closest("li");
    expect(biyoloji).toHaveTextContent("03.11.2026 Salı · 2. ders saati · takvimde");
    // İdareci saati değiştirmiş: takvimdeki saat söylenir.
    expect(screen.getByText("Kimya — 9. Sınıf").closest("li")).toHaveTextContent(
      "04.11.2026 Çarşamba · 2. ders saati · takvimde, 3. ders saati",
    );
    const matematik = screen.getByText("Matematik — 11. Sınıf").closest("li");
    expect(matematik).toHaveTextContent("(havuzdaki ders: Seçmeli Matematik)");
    expect(matematik).toHaveTextContent("seçmeli ders takvim havuzunda yok");
    expect(screen.getByText("Coğrafya — 9. Sınıf").closest("li")).toHaveTextContent(
      "10.11.2026 Salı · 4. ders saati · takvimde başka günde (05.11.2026)",
    );
    // Karşılığı olmayan satırlar tek özet satırında.
    expect(
      screen.getByText(/Ders havuzunda karşılığı olmayanlar: 9\. Sınıf Felsefe/),
    ).toBeInTheDocument();
    expect(screen.queryByText("Felsefe — 9. Sınıf")).not.toBeInTheDocument();
    // Dayanak ve açıklama satırları sunucudan.
    expect(
      screen.getByText(/Dayanak: Okul Geneli Ortak Yazılı Sınav Uygulama/),
    ).toBeInTheDocument();
    expect(screen.getByText(/^Günde tek sınav 2\. ders saatinde/)).toBeInTheDocument();
    expect(screen.getByText(/^Mazeret sınavları 23\.11\.2026/)).toBeInTheDocument();
    // Bekleyen OYSS sınavı varken düğme görünür.
    expect(screen.getByRole("button", { name: "Takvime uygula" })).toBeInTheDocument();
  });

  it("uygulama iki takvimin sonucunu birlikte söyler", async () => {
    const user = userEvent.setup();
    const bekleyen = oyssSatir({ entry_date: null, entry_period_no: null, status: "pending" });
    calApi.nationalExams.mockResolvedValue({
      exams: [],
      oyss: [bekleyen],
      oyss_info: OYSS_BILGI,
    });
    calApi.applyNationalExams.mockResolvedValue({
      result: BOS_SONUC,
      oyss_result: {
        placed: ["9. Sınıf Biyoloji (03.11.2026): 2. ders saati"],
        unchanged: [],
        skipped: ["9 OYSS sınavının ders havuzunda o sınıf düzeyinde karşılığı yok"],
      },
      exams: [],
      oyss: [oyssSatir()],
      oyss_info: OYSS_BILGI,
    });
    renderBant();

    await user.click(await screen.findByRole("button", { name: "Takvime uygula" }));

    expect(
      await screen.findByText("Yerleştirildi: 9. Sınıf Biyoloji (03.11.2026): 2. ders saati"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Uygulanamadı: 9 OYSS sınavının ders havuzunda o sınıf düzeyinde karşılığı yok",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("1 sınav Bakanlık takvimine göre yerleştirildi.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Takvime uygula" })).not.toBeInTheDocument();
  });
});
