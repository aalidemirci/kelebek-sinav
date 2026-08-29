// Sorular ve Kitapçıklar paneli testleri (F5): API + saveBlob mock'lanır;
// soru dosyası yükleme/silme, kilit (onaylı/arşiv), Word şablonu indirme ve
// SENKRON kitapçık üretimi (polling yok — tek istekte tamamlanmış koşu)
// doğrulanır. Ortak kurucular testFixtures.ts'ten.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { ExamSession } from "./api";
import {
  makeBookletRun,
  makeCourseRow,
  makeQuestionMeta,
  makeSession,
  paginated,
} from "./testFixtures";

const sessionApi = vi.hoisted(() => ({
  question: vi.fn(),
  uploadQuestion: vi.fn(),
  deleteQuestion: vi.fn(),
  questionBlob: vi.fn(),
  questionTemplateBlob: vi.fn(),
  startBookletRun: vi.fn(),
  bookletRuns: vi.fn(),
  bookletRunZipBlob: vi.fn(),
}));
const download = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, examSessionApi: { ...actual.examSessionApi, ...sessionApi } };
});
vi.mock("../../lib/download", () => download);

import SorularPaneli from "./SorularPaneli";

function renderPanel(session: ExamSession) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <SorularPaneli session={session} />
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

function dagitilmisOturum(overrides: Partial<ExamSession> = {}): ExamSession {
  return makeSession({
    status: "DISTRIBUTED",
    courses: [
      makeCourseRow(),
      makeCourseRow({ id: 22, level: 10, display_label: "Matematik — 10. Sınıf" }),
    ],
    ...overrides,
  });
}

afterEach(() => vi.clearAllMocks());

describe("SorularPaneli", () => {
  it("ders satırları listelenir; yüklü/yüklenmedi üst verisi gösterilir", async () => {
    sessionApi.question.mockImplementation((id: number) =>
      id === 21
        ? Promise.resolve(makeQuestionMeta())
        : Promise.reject(new ApiError(404, "not_found", "Soru dosyası yüklenmemiş.")),
    );
    sessionApi.bookletRuns.mockResolvedValue(paginated([]));
    renderPanel(dagitilmisOturum());

    expect(await screen.findByText("Matematik — 9. Sınıf")).toBeInTheDocument();
    expect(await screen.findByText(/2 sayfa · tek puan kutusu/)).toBeInTheDocument();
    expect(await screen.findByText("Soru dosyası yüklenmedi")).toBeInTheDocument();
    // Kilitsiz (DAĞITILDI): yüklü satırda Değiştir, boş satırda Yükle.
    expect(screen.getByRole("button", { name: "Değiştir" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yükle" })).toBeInTheDocument();
  });

  it("onaylı oturumda yükleme kilitli — yalnız önizleme kalır", async () => {
    sessionApi.question.mockResolvedValue(makeQuestionMeta());
    sessionApi.bookletRuns.mockResolvedValue(paginated([]));
    renderPanel(dagitilmisOturum({ status: "APPROVED" }));

    expect(await screen.findByText(/onaylı — soru dosyaları/)).toBeInTheDocument();
    // Üst veri sorguları çözülene dek bekle — Önizle ancak meta gelince çizilir.
    expect((await screen.findAllByRole("button", { name: "Önizle" })).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /Yükle|Değiştir/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Kaldır" })).not.toBeInTheDocument();
  });

  it("yükleme dialogu: dosya + puan bölümü FormData ile gönderilir", async () => {
    const user = userEvent.setup();
    sessionApi.question.mockRejectedValue(
      new ApiError(404, "not_found", "Soru dosyası yüklenmemiş."),
    );
    sessionApi.bookletRuns.mockResolvedValue(paginated([]));
    sessionApi.uploadQuestion.mockResolvedValue(makeQuestionMeta());
    renderPanel(dagitilmisOturum({ courses: [makeCourseRow()] }));

    await user.click(await screen.findByRole("button", { name: "Yükle" }));
    const dialog = await screen.findByRole("dialog");
    const input = within(dialog).getByLabelText(/Soru PDF dosyası/);
    await user.upload(input, new File(["%PDF-"], "soru.pdf", { type: "application/pdf" }));
    await user.click(within(dialog).getByRole("button", { name: "Yükle" }));

    await waitFor(() => expect(sessionApi.uploadQuestion).toHaveBeenCalledTimes(1));
    const [id, form] = sessionApi.uploadQuestion.mock.calls[0] as [number, FormData];
    expect(id).toBe(21);
    expect((form.get("file") as File).name).toBe("soru.pdf");
    expect(form.get("score_mode")).toBe("SINGLE_BOX");
    expect(await screen.findByText("Soru dosyası yüklendi.")).toBeInTheDocument();
  });

  it("Word şablonu indirilir (üst boşluk 4 cm)", async () => {
    const user = userEvent.setup();
    sessionApi.question.mockRejectedValue(
      new ApiError(404, "not_found", "Soru dosyası yüklenmemiş."),
    );
    sessionApi.bookletRuns.mockResolvedValue(paginated([]));
    const blob = new Blob(["docx"]);
    sessionApi.questionTemplateBlob.mockResolvedValue(blob);
    renderPanel(dagitilmisOturum());

    await user.click(await screen.findByRole("button", { name: "Word şablonunu indir" }));
    await waitFor(() => expect(download.saveBlob).toHaveBeenCalledWith(blob, "soru_sablonu.docx"));
  });

  it("kitapçık üretimi SENKRON: başarıda 'üretildi' + liste tazelenir, ZIP indirilebilir", async () => {
    const user = userEvent.setup();
    sessionApi.question.mockRejectedValue(
      new ApiError(404, "not_found", "Soru dosyası yüklenmemiş."),
    );
    sessionApi.bookletRuns.mockResolvedValue(paginated([makeBookletRun()]));
    sessionApi.startBookletRun.mockResolvedValue(makeBookletRun());
    const zip = new Blob(["zip"]);
    sessionApi.bookletRunZipBlob.mockResolvedValue(zip);
    renderPanel(dagitilmisOturum());

    await user.click(await screen.findByRole("button", { name: "Kitapçıkları üret" }));
    await waitFor(() => expect(sessionApi.startBookletRun).toHaveBeenCalledWith(5, 0));
    expect(await screen.findByText("Kitapçıklar üretildi.")).toBeInTheDocument();

    expect(await screen.findByText("Koşu #41")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "ZIP indir" }));
    await waitFor(() =>
      expect(download.saveBlob).toHaveBeenCalledWith(zip, "kitapciklar_oturum_5.zip"),
    );
  });

  it("üretim FAILED dönerse hata snackbar'ı koşunun mesajını taşır", async () => {
    const user = userEvent.setup();
    sessionApi.question.mockRejectedValue(
      new ApiError(404, "not_found", "Soru dosyası yüklenmemiş."),
    );
    sessionApi.bookletRuns.mockResolvedValue(paginated([]));
    sessionApi.startBookletRun.mockResolvedValue(
      makeBookletRun({ status: "FAILED", error_message: "ValueError: bozuk", completed_at: null }),
    );
    renderPanel(dagitilmisOturum());

    await user.click(await screen.findByRole("button", { name: "Kitapçıkları üret" }));
    expect(await screen.findByText(/Kitapçık üretimi başarısız — ValueError/)).toBeInTheDocument();
  });
});
