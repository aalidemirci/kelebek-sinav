// Sorular ve Kitapçıklar paneli testleri (F5): API + saveBlob mock'lanır;
// soru dosyası yükleme/silme, kilit (onaylı/arşiv), Word şablonu indirme ve
// SENKRON kitapçık üretimi (polling yok — tek istekte tamamlanmış koşu)
// doğrulanır. Ortak kurucular testFixtures.ts'ten.
//
// 20.09.2026: panel BEP kapsamındaki öğrencilerin bireysel soru dosyaları
// bölümünü de barındırır (`bep/BireyselSorularBolumu` — ayrıntısı kendi test
// dosyasında). Burada uç sahtelenir; varsayılan yanıt BOŞTUR (bölüm çizilmez),
// böylece eski testler bölümden etkilenmez.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { IndividualQuestionRow } from "../bep/api";
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
const bireysel = vi.hoisted(() => ({ list: vi.fn() }));
const guvenlik = vi.hoisted(() => ({ durum: vi.fn() }));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, examSessionApi: { ...actual.examSessionApi, ...sessionApi } };
});
vi.mock("../bep/api", async (importActual) => {
  const actual = await importActual<typeof import("../bep/api")>();
  return { ...actual, individualQuestionApi: { ...actual.individualQuestionApi, ...bireysel } };
});
// Bireysel bölümün parola uyarısı güvenlik durumunu sorar (parola açık → bant yok).
vi.mock("../guvenlik/api", async (importActual) => {
  const actual = await importActual<typeof import("../guvenlik/api")>();
  return { ...actual, guvenlikApi: { ...actual.guvenlikApi, ...guvenlik } };
});
// Yalnız saveBlob sahtelenir; dosya adını kuran `dosyaAdi` GERÇEK kalır ki
// indirilen adın biçimi de sınansın.
vi.mock("../../lib/download", async (importActual) => {
  const actual = await importActual<typeof import("../../lib/download")>();
  return { ...actual, ...download };
});

import SorularPaneli from "./SorularPaneli";

function renderPanel(session: ExamSession) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <ConfirmProvider>
          <SorularPaneli session={session} />
        </ConfirmProvider>
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

/** Oturuma giren BEP kapsamındaki öğrenci — ad ve numara UYDURMADIR (KVKK). */
const BEP_SATIRI: IndividualQuestionRow = {
  student_id: 303,
  student_number: "103",
  full_name: "Zeynep Kaya",
  class_label: "10/C",
  room_name: "D-203",
  seat_no: 3,
  course_label: "Fizik — 10. Sınıf",
  on_iep_list: true,
  document: null,
};

beforeEach(() => {
  // Varsayılan: oturuma giren BEP kapsamında öğrenci yok → bölüm hiç çizilmez.
  bireysel.list.mockResolvedValue({ rows: [] });
  guvenlik.durum.mockResolvedValue({
    password_set: true,
    locked: false,
    transition_pending: false,
    transition: "",
    protected_fields: [],
  });
});

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

  it("aynı kitapçık satırları tek satırda birleşir; dosya taşıyıcı satırdan okunur ve oraya yüklenir", async () => {
    const user = userEvent.setup();
    // Dosya 10. sınıf satırında (id 22) duruyor; 9. sınıf satırı (id 21) boş.
    sessionApi.question.mockImplementation((id: number) =>
      id === 22
        ? Promise.resolve(makeQuestionMeta())
        : Promise.reject(new ApiError(404, "not_found", "Soru dosyası yüklenmemiş.")),
    );
    sessionApi.bookletRuns.mockResolvedValue(paginated([]));
    sessionApi.uploadQuestion.mockResolvedValue(makeQuestionMeta());
    renderPanel(
      dagitilmisOturum({
        courses: [
          makeCourseRow({
            shared_booklet: true,
            display_label: "Matematik — 9. Sınıf (tüm seviyeler aynı kitapçık)",
          }),
          makeCourseRow({
            id: 22,
            level: 10,
            shared_booklet: true,
            display_label: "Matematik — 10. Sınıf (tüm seviyeler aynı kitapçık)",
          }),
        ],
      }),
    );

    expect(
      await screen.findByText("Matematik — 9. ve 10. Sınıf (aynı kitapçık)"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Matematik — 9\. Sınıf \(/)).not.toBeInTheDocument();
    expect(await screen.findByText(/2 sayfa · tek puan kutusu/)).toBeInTheDocument();
    // Tek satır, tek "Değiştir" — ikinci bir "Yükle" YOK (eski hata kaynağı).
    expect(screen.getAllByRole("button", { name: "Değiştir" })).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Yükle" })).not.toBeInTheDocument();
    expect(screen.queryByText("Soru dosyası yüklenmedi")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Değiştir" }));
    const dialog = await screen.findByRole("dialog");
    await user.upload(
      within(dialog).getByLabelText(/Soru PDF dosyası/),
      new File(["%PDF-"], "soru.pdf", { type: "application/pdf" }),
    );
    await user.click(within(dialog).getByRole("button", { name: "Yükle" }));
    await waitFor(() => expect(sessionApi.uploadQuestion).toHaveBeenCalledTimes(1));
    // Yükleme dosyanın durduğu (taşıyıcı) satıra gider — kardeşe değil.
    expect((sessionApi.uploadQuestion.mock.calls[0] as [number, FormData])[0]).toBe(22);
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

  it("yüklü soru PDF'ini 'Kaldır' onaydan geçer; onaylanınca dosyanın durduğu satırdan silinir", async () => {
    const user = userEvent.setup();
    sessionApi.question.mockResolvedValue(makeQuestionMeta());
    sessionApi.bookletRuns.mockResolvedValue(paginated([]));
    sessionApi.deleteQuestion.mockResolvedValue(undefined);
    renderPanel(dagitilmisOturum({ courses: [makeCourseRow()] }));

    await user.click(await screen.findByRole("button", { name: "Kaldır" }));
    // Tek tıkla silinmez: başlık soru, gövde sonuç (docs/sozluk.md §3).
    expect(sessionApi.deleteQuestion).not.toHaveBeenCalled();
    const dialog = await screen.findByRole("dialog", { name: "Soru dosyası kaldırılsın mı?" });
    expect(
      within(dialog).getByText(/Matematik — 9\. Sınıf için yüklenen soru PDF'i silinir/),
    ).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Kaldır" }));

    await waitFor(() => expect(sessionApi.deleteQuestion).toHaveBeenCalledWith(21));
    expect(await screen.findByText("Soru dosyası kaldırıldı.")).toBeInTheDocument();
  });

  it("'Kaldır' onayında 'Vazgeç' denirse dosya silinmez", async () => {
    const user = userEvent.setup();
    sessionApi.question.mockResolvedValue(makeQuestionMeta());
    sessionApi.bookletRuns.mockResolvedValue(paginated([]));
    renderPanel(dagitilmisOturum({ courses: [makeCourseRow()] }));

    await user.click(await screen.findByRole("button", { name: "Kaldır" }));
    const dialog = await screen.findByRole("dialog", { name: "Soru dosyası kaldırılsın mı?" });
    await user.click(within(dialog).getByRole("button", { name: "Vazgeç" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(sessionApi.deleteQuestion).not.toHaveBeenCalled();
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
    // Etiketlerde karar kodu (K5) ve rastgele büyük harf ("PUAN") yok.
    const puan = within(dialog).getByLabelText("Puan bölümü");
    expect(within(puan).getByRole("option", { name: "Tek puan kutusu" })).toBeInTheDocument();
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
    // Şablon oturuma özgü değildir → adında oturum adı/tarih yok.
    await waitFor(() => expect(download.saveBlob).toHaveBeenCalledWith(blob, "Soru-Şablonu.docx"));
  });

  it("GÜNCEL OLMAYAN kitapçık üretimi uyarıyla işaretlenir; güncel üretim işaretlenmez", async () => {
    sessionApi.question.mockRejectedValue(
      new ApiError(404, "not_found", "Soru dosyası yüklenmemiş."),
    );
    sessionApi.bookletRuns.mockResolvedValue(
      paginated([
        makeBookletRun({ id: 42, created_at: "2026-06-02T10:00:00+03:00", is_stale: false }),
        makeBookletRun({ id: 41, is_stale: true }),
      ]),
    );
    renderPanel(dagitilmisOturum());

    // Yalnız eski üretimin satırında uyarı var; ZIP yine indirilebilir (arşiv izi).
    // Metin iki nedeni de kapsar: yerleşim YA DA bir bireysel soru dosyası değişmiştir
    // (eski "Eski yerleşime göre" ikincisinde yanlış bilgi olurdu).
    const uyari = await screen.findByText("Güncel değil — yeniden üretin");
    expect(screen.getAllByText("Güncel değil — yeniden üretin")).toHaveLength(1);
    expect(screen.queryByText(/Eski yerleşime göre/)).not.toBeInTheDocument();
    expect(uyari.closest("li")).toHaveTextContent(/Üretim · 01\.06\.2026/);
    expect(screen.getAllByRole("button", { name: "ZIP indir" })).toHaveLength(2);
  });

  it("üretime giren bireysel soru dosyası sayısı satırda yalnız SAYI olarak görünür", async () => {
    sessionApi.question.mockRejectedValue(
      new ApiError(404, "not_found", "Soru dosyası yüklenmemiş."),
    );
    sessionApi.bookletRuns.mockResolvedValue(
      paginated([
        makeBookletRun({
          id: 42,
          created_at: "2026-06-02T10:00:00+03:00",
          manifest: { total_booklets: 8, total_pages: 16, individual_booklets: 2 },
        }),
        // Eski üretimin manifestinde alan yoktur; 0 da satır çizdirmez.
        makeBookletRun({ id: 41 }),
        makeBookletRun({ id: 40, manifest: { total_booklets: 8, individual_booklets: 0 } }),
      ]),
    );
    renderPanel(dagitilmisOturum());

    const bilgi = await screen.findByText("2 bireysel soru dosyası dahil");
    expect(bilgi.closest("li")).toHaveTextContent(/Üretim · 02\.06\.2026/);
    expect(screen.getAllByText(/bireysel soru dosyası dahil/)).toHaveLength(1);
  });

  it("oturuma giren BEP kapsamında öğrenci yoksa bireysel soru dosyaları bölümü çizilmez", async () => {
    sessionApi.question.mockRejectedValue(
      new ApiError(404, "not_found", "Soru dosyası yüklenmemiş."),
    );
    sessionApi.bookletRuns.mockResolvedValue(paginated([]));
    renderPanel(dagitilmisOturum());

    await waitFor(() => expect(bireysel.list).toHaveBeenCalledWith(5));
    expect(await screen.findByText("Matematik — 9. Sınıf")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /BEP kapsamındaki öğrenciler/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "İdare özeti (PDF)" })).toBeNull();
  });

  it("BEP kapsamında öğrenci varsa bölüm ders satırlarıyla kitapçık üretimi ARASINDA çizilir", async () => {
    sessionApi.question.mockRejectedValue(
      new ApiError(404, "not_found", "Soru dosyası yüklenmemiş."),
    );
    sessionApi.bookletRuns.mockResolvedValue(paginated([]));
    bireysel.list.mockResolvedValue({ rows: [BEP_SATIRI] });
    renderPanel(dagitilmisOturum());

    const baslik = await screen.findByRole("heading", {
      name: "BEP kapsamındaki öğrenciler — bireysel soru dosyaları",
    });
    const dersSatiri = screen.getByText("Matematik — 9. Sınıf");
    const uretim = screen.getByRole("heading", { name: "Kişiselleştirilmiş kitapçıklar" });
    // Belge sırası: ders satırı → bireysel bölüm → kitapçık üretim kutusu.
    const sonraGelir = (once: Node, sonra: Node) =>
      (once.compareDocumentPosition(sonra) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
    expect(sonraGelir(dersSatiri, baslik)).toBe(true);
    expect(sonraGelir(baslik, uretim)).toBe(true);
    // DAĞITILDI oturumda seçim açıktır.
    expect(
      screen.getByRole("button", { name: "Bireysel soru dosyası uygula" }),
    ).toBeInTheDocument();
  });

  it("onaylı oturumda bireysel soru dosyası seçimi de kilitlidir", async () => {
    sessionApi.question.mockResolvedValue(makeQuestionMeta());
    sessionApi.bookletRuns.mockResolvedValue(paginated([]));
    bireysel.list.mockResolvedValue({ rows: [BEP_SATIRI] });
    renderPanel(dagitilmisOturum({ status: "APPROVED" }));

    expect(await screen.findByText("Dersin soru dosyası")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Bireysel soru dosyası uygula" }),
    ).not.toBeInTheDocument();
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

    // Üretim kaydı kimlikle ("Koşu #41") değil üretim zamanıyla anılır.
    expect(await screen.findByText(/Üretim · 01\.06\.2026.*09:05/)).toBeInTheDocument();
    expect(screen.queryByText(/Koşu/)).not.toBeInTheDocument();
    // Başlık ve alan etiketlerinde evrak kodu (R10) yok.
    expect(
      screen.getByRole("heading", { name: "Kişiselleştirilmiş kitapçıklar" }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Her salon için isimsiz yedek kitapçık sayısı"),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "ZIP indir" }));
    // Dosya adı: belge adı + oturum adı + tarih (docs/sozluk.md §3).
    await waitFor(() =>
      expect(download.saveBlob).toHaveBeenCalledWith(
        zip,
        "Kitapçıklar_2-Ortak-Sınav_15.06.2026.zip",
      ),
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
