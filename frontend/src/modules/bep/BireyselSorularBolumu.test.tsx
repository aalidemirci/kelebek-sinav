// Bireysel soru dosyaları bölümü testleri (20.09.2026): oturuma giren BEP
// kapsamında öğrenci yoksa bölüm HİÇ çizilmez; satırın üç durumu (seçim yok /
// dosya bekleniyor / dosya yüklü) doğru düğmeleri gösterir; seçim, yükleme ve
// kaldırma hem bu bölümü hem kitapçık üretim listesini tazeler; kilitli oturumda
// yalnız durum + Önizle kalır; idare özeti belge adıyla indirilir.
// KVKK: onay/bildirim/diyalog metinlerinde öğrenci adı ve okul numarası YOKTUR;
// fixture'lardaki ad ve numaralar UYDURMADIR.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { makeSession } from "../oturumlar/testFixtures";
import type { IndividualDocument, IndividualQuestionRow } from "./api";

const individual = vi.hoisted(() => ({
  list: vi.fn(),
  select: vi.fn(),
  remove: vi.fn(),
  uploadFile: vi.fn(),
  fileBlob: vi.fn(),
  summaryBlob: vi.fn(),
}));
const guvenlik = vi.hoisted(() => ({ durum: vi.fn() }));
const download = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return {
    ...actual,
    individualQuestionApi: { ...actual.individualQuestionApi, ...individual },
  };
});
vi.mock("../guvenlik/api", async (importActual) => {
  const actual = await importActual<typeof import("../guvenlik/api")>();
  return { ...actual, guvenlikApi: { ...actual.guvenlikApi, ...guvenlik } };
});
// Yalnız saveBlob sahtelenir; dosya adını kuran `dosyaAdi` GERÇEK kalır.
vi.mock("../../lib/download", async (importActual) => {
  const actual = await importActual<typeof import("../../lib/download")>();
  return { ...actual, ...download };
});

import BireyselSorularBolumu from "./BireyselSorularBolumu";

function makeDoc(overrides: Partial<IndividualDocument> = {}): IndividualDocument {
  return {
    id: 71,
    has_file: true,
    page_count: 2,
    score_mode: "SINGLE_BOX",
    question_count: null,
    ...overrides,
  };
}

function makeRow(overrides: Partial<IndividualQuestionRow> = {}): IndividualQuestionRow {
  return {
    student_id: 301,
    student_number: "101",
    full_name: "Ayşe Yılmaz",
    class_label: "9/A",
    room_name: "D-201",
    seat_no: 5,
    course_label: "Matematik — 9. Sınıf",
    on_iep_list: true,
    document: null,
    ...overrides,
  };
}

/** Üç durum: seçim yok · seçildi, dosya bekleniyor · dosya yüklü (puan tablosu). */
const SECIMSIZ = makeRow();
const DOSYA_BEKLEYEN = makeRow({
  student_id: 302,
  student_number: "102",
  full_name: "Mehmet Demir",
  class_label: "9/B",
  room_name: "D-202",
  seat_no: 12,
  document: makeDoc({ id: 72, has_file: false, page_count: null }),
});
const DOSYASI_YUKLU = makeRow({
  student_id: 303,
  student_number: "103",
  full_name: "Zeynep Kaya",
  class_label: "10/C",
  room_name: "D-203",
  seat_no: 3,
  course_label: "Fizik — 10. Sınıf",
  document: makeDoc({ id: 73, page_count: 4, score_mode: "QUESTION_TABLE", question_count: 8 }),
});

const BASLIK = "BEP kapsamındaki öğrenciler — bireysel soru dosyaları";

function renderBolum({ locked = false }: { locked?: boolean } = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(qc, "invalidateQueries");
  const session = makeSession({ status: locked ? "APPROVED" : "DISTRIBUTED" });
  const view = render(
    <MemoryRouter>
      <QueryClientProvider client={qc}>
        <SnackbarProvider>
          <ConfirmProvider>
            <BireyselSorularBolumu session={session} locked={locked} />
          </ConfirmProvider>
        </SnackbarProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
  return { ...view, invalidate };
}

/** Öğrencinin satırı (li) — aynı düğme adları her satırda yinelendiği için kapsam şart. */
async function satir(fullName: RegExp): Promise<HTMLElement> {
  return (await screen.findByText(fullName)).closest("li") as HTMLElement;
}

beforeEach(() => {
  individual.list.mockResolvedValue({ rows: [SECIMSIZ, DOSYA_BEKLEYEN, DOSYASI_YUKLU] });
  // Varsayılan: parola AÇIK → uyarı bandı yok.
  guvenlik.durum.mockResolvedValue({
    password_set: true,
    locked: false,
    transition_pending: false,
    transition: "",
    protected_fields: [],
  });
  // jsdom bu ikisini sağlamaz; önizleme blob'u nesne adresine çevirir.
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    writable: true,
    value: vi.fn(() => "blob:onizleme"),
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    writable: true,
    value: vi.fn(),
  });
});

afterEach(() => vi.clearAllMocks());

describe("BireyselSorularBolumu — görünürlük", () => {
  it("oturuma giren BEP kapsamında öğrenci yoksa bölüm hiç çizilmez", async () => {
    individual.list.mockResolvedValue({ rows: [] });
    const { container } = renderBolum();

    await waitFor(() => expect(individual.list).toHaveBeenCalledWith(5));
    expect(screen.queryByRole("heading", { name: BASLIK })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "İdare özeti (PDF)" })).not.toBeInTheDocument();
    expect(container).toBeEmptyDOMElement();
    // Bölüm çizilmediğinde parola durumu da sorulmaz.
    expect(guvenlik.durum).not.toHaveBeenCalled();
  });

  it("sorgu sürerken de çizilmez", () => {
    individual.list.mockReturnValue(new Promise(() => {}));
    const { container } = renderBolum();

    expect(container).toBeEmptyDOMElement();
  });

  it("liste okunamazsa sessiz kalmaz: gerekçe role=alert ile basılır", async () => {
    individual.list.mockRejectedValue(new ApiError(500, "server_error", "Liste okunamadı."));
    renderBolum();

    expect(await screen.findByRole("alert")).toHaveTextContent("Liste okunamadı.");
    expect(screen.queryByRole("heading", { name: BASLIK })).not.toBeInTheDocument();
  });

  it("başlık, açıklama ve idare özeti notu çizilir; “ortak kitapçık” denmez", async () => {
    const { container } = renderBolum();

    expect(await screen.findByRole("heading", { name: BASLIK })).toBeInTheDocument();
    expect(
      screen.getByText(/salon\s+evrakında ve kitapçıkta öğrenciyi ayıran hiçbir işaret yoktur/),
    ).toBeInTheDocument();
    expect(screen.getByText(/PDF'in içine öğrencinin adını\s+yazmayın/)).toBeInTheDocument();
    expect(
      screen.getByText(
        "Yalnız idare nüshasıdır; salonlara dağıtılmaz ve “Tümünü indir” paketine girmez.",
      ),
    ).toBeInTheDocument();
    // "Ortak" yalnız MEB anlamında kullanılır — karşıt terim "dersin soru dosyası"dır.
    expect(container.textContent ?? "").not.toMatch(/ortak/i);
  });

  it("parola kapalıyken bölümde uyarı bandı görünür", async () => {
    guvenlik.durum.mockResolvedValue({
      password_set: false,
      locked: false,
      transition_pending: false,
      transition: "",
      protected_fields: [],
    });
    renderBolum();

    expect(
      await screen.findByRole("status", { name: "Uygulama parolası kapalı" }),
    ).toHaveTextContent(/BEP bilgisi bu bilgisayarda ve yedeklerde şifresiz saklanıyor/);
  });
});

describe("BireyselSorularBolumu — satır durumları", () => {
  it("seçim yok: “Dersin soru dosyası” + uygula düğmesi; yükleme/kaldırma yok", async () => {
    renderBolum();
    const li = await satir(/Ayşe Yılmaz/);

    expect(li).toHaveTextContent("101 · Ayşe Yılmaz");
    expect(li).toHaveTextContent("9/A · D-201 · koltuk 5 · Matematik — 9. Sınıf");
    expect(within(li).getByText("Dersin soru dosyası")).toBeInTheDocument();
    expect(
      within(li).getByRole("button", { name: "Bireysel soru dosyası uygula" }),
    ).toBeInTheDocument();
    expect(within(li).queryByRole("button", { name: "Yükle" })).not.toBeInTheDocument();
    expect(within(li).queryByRole("button", { name: "Önizle" })).not.toBeInTheDocument();
    expect(within(li).queryByRole("button", { name: "Seçimi kaldır" })).not.toBeInTheDocument();
  });

  it("seçildi, dosya bekleniyor: hata tonunda “Dosya yüklenmedi” + Yükle + Seçimi kaldır", async () => {
    renderBolum();
    const li = await satir(/Mehmet Demir/);

    expect(within(li).getByText("Dosya yüklenmedi")).toHaveClass("text-error");
    expect(within(li).getByRole("button", { name: "Yükle" })).toBeInTheDocument();
    expect(within(li).getByRole("button", { name: "Seçimi kaldır" })).toBeInTheDocument();
    expect(within(li).queryByRole("button", { name: "Önizle" })).not.toBeInTheDocument();
    expect(within(li).queryByRole("button", { name: "Değiştir" })).not.toBeInTheDocument();
    expect(
      within(li).queryByRole("button", { name: "Bireysel soru dosyası uygula" }),
    ).not.toBeInTheDocument();
  });

  it("dosya yüklü: sayfa + puan bölümü özeti, Önizle + Değiştir + Seçimi kaldır", async () => {
    renderBolum();
    const li = await satir(/Zeynep Kaya/);

    expect(within(li).getByText("4 sayfa · 8 soruluk puan tablosu")).toBeInTheDocument();
    expect(within(li).getByRole("button", { name: "Önizle" })).toBeInTheDocument();
    expect(within(li).getByRole("button", { name: "Değiştir" })).toBeInTheDocument();
    expect(within(li).getByRole("button", { name: "Seçimi kaldır" })).toBeInTheDocument();
    expect(within(li).queryByRole("button", { name: "Yükle" })).not.toBeInTheDocument();
  });

  it("tek puan kutulu dosyanın özeti dersin soru dosyasıyla aynı biçimdedir", async () => {
    individual.list.mockResolvedValue({ rows: [makeRow({ document: makeDoc() })] });
    renderBolum();

    expect(await screen.findByText("2 sayfa · tek puan kutusu")).toBeInTheDocument();
  });

  it("yetim satır (yerleşimde yok): yalnız “Seçimi kaldır” gösterilir", async () => {
    individual.list.mockResolvedValue({
      rows: [
        makeRow({ room_name: "", seat_no: null, course_label: "", document: makeDoc({ id: 74 }) }),
      ],
    });
    renderBolum();
    const li = await satir(/Ayşe Yılmaz/);

    expect(li).toHaveTextContent("9/A · yerleşimde yok");
    expect(within(li).getByRole("button", { name: "Seçimi kaldır" })).toBeInTheDocument();
    expect(within(li).getAllByRole("button")).toHaveLength(1);
  });

  it("listeden çıkarılmış öğrencinin kalan satırı bunu söyler", async () => {
    individual.list.mockResolvedValue({
      rows: [makeRow({ on_iep_list: false, document: makeDoc() })],
    });
    renderBolum({ locked: true });

    expect(await screen.findByText("listeden çıkarılmış")).toBeInTheDocument();
  });

  it("kilitli oturumda düğmeler yok: yalnız durum + Önizle kalır", async () => {
    renderBolum({ locked: true });
    await screen.findByRole("heading", { name: BASLIK });

    // Durum metinleri yerinde.
    expect(screen.getByText("Dersin soru dosyası")).toBeInTheDocument();
    expect(screen.getByText("Dosya yüklenmedi")).toBeInTheDocument();
    expect(screen.getByText("4 sayfa · 8 soruluk puan tablosu")).toBeInTheDocument();
    // Yalnız dosyası yüklü satırda Önizle; seçim/yükleme/kaldırma hiçbir satırda yok.
    expect(screen.getAllByRole("button", { name: "Önizle" })).toHaveLength(1);
    expect(
      screen.queryByRole("button", { name: /Bireysel soru dosyası uygula|Yükle|Değiştir/ }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Seçimi kaldır" })).not.toBeInTheDocument();
    // İdare özeti kilitli oturumda da alınır.
    expect(screen.getByRole("button", { name: "İdare özeti (PDF)" })).toBeEnabled();
  });
});

describe("BireyselSorularBolumu — işlemler", () => {
  it("seçim: oturum ve öğrenci GÖVDEDE gider; bölüm ve kitapçık üretim listesi tazelenir", async () => {
    const user = userEvent.setup();
    individual.select.mockResolvedValue(makeDoc({ id: 75, has_file: false, page_count: null }));
    const { invalidate } = renderBolum();
    const li = await satir(/Ayşe Yılmaz/);

    await user.click(within(li).getByRole("button", { name: "Bireysel soru dosyası uygula" }));

    await waitFor(() => expect(individual.select).toHaveBeenCalledWith(5, 301));
    const bildirim = await screen.findByText(
      "Bireysel soru dosyası seçildi; şimdi öğrencinin soru PDF'ini yükleyin.",
    );
    // Bildirimde öğrenci adı ve okul numarası geçmez.
    expect(bildirim).not.toHaveTextContent(/Ayşe|101/);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["individual-questions", 5] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["booklet-runs", 5] });
  });

  it("seçim reddedilirse backend gerekçesi bildirilir", async () => {
    const user = userEvent.setup();
    individual.select.mockRejectedValue(
      new ApiError(
        400,
        "validation_error",
        "Onaylı/arşiv oturumda bireysel soru dosyası değiştirilemez.",
      ),
    );
    renderBolum();
    const li = await satir(/Ayşe Yılmaz/);

    await user.click(within(li).getByRole("button", { name: "Bireysel soru dosyası uygula" }));

    expect(
      await screen.findByText("Onaylı/arşiv oturumda bireysel soru dosyası değiştirilemez."),
    ).toBeInTheDocument();
  });

  it("yükleme: dosya + puan bölümü belge kimliğiyle gider; diyalog başlığı öğrenciyi adla anmaz", async () => {
    const user = userEvent.setup();
    individual.uploadFile.mockResolvedValue(makeDoc({ id: 72 }));
    const { invalidate } = renderBolum();
    const li = await satir(/Mehmet Demir/);

    await user.click(within(li).getByRole("button", { name: "Yükle" }));
    // Başlık satırı salon ve koltukla anar — ad/okul no yok.
    const dialog = await screen.findByRole("dialog", {
      name: "Bireysel soru PDF'i — D-202 · koltuk 12",
    });
    expect(dialog).not.toHaveTextContent(/Mehmet|102/);
    // Alanlar dersin soru dosyası diyaloğuyla AYNI.
    const puan = within(dialog).getByLabelText("Puan bölümü");
    expect(within(puan).getByRole("option", { name: "Tek puan kutusu" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Yükle" })).toBeDisabled();
    await user.upload(
      within(dialog).getByLabelText(/Soru PDF dosyası/),
      new File(["%PDF-"], "bireysel.pdf", { type: "application/pdf" }),
    );
    await user.click(within(dialog).getByRole("button", { name: "Yükle" }));

    await waitFor(() => expect(individual.uploadFile).toHaveBeenCalledTimes(1));
    const [documentId, form] = individual.uploadFile.mock.calls[0] as [number, FormData];
    expect(documentId).toBe(72);
    expect((form.get("file") as File).name).toBe("bireysel.pdf");
    expect(form.get("score_mode")).toBe("SINGLE_BOX");
    expect(form.get("question_count")).toBeNull();
    expect(await screen.findByText("Bireysel soru dosyası yüklendi.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["booklet-runs", 5] });
  });

  it("“Değiştir” yüklü dosyanın puan bölümüyle açılır; soru sayısı forma girer", async () => {
    const user = userEvent.setup();
    individual.uploadFile.mockResolvedValue(makeDoc({ id: 73 }));
    renderBolum();
    const li = await satir(/Zeynep Kaya/);

    await user.click(within(li).getByRole("button", { name: "Değiştir" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Bireysel soru PDF'i — D-203 · koltuk 3",
    });
    expect(within(dialog).getByLabelText("Puan bölümü")).toHaveValue("QUESTION_TABLE");
    expect(within(dialog).getByLabelText(/Soru sayısı/)).toHaveValue(8);
    await user.upload(
      within(dialog).getByLabelText(/Soru PDF dosyası/),
      new File(["%PDF-"], "yeni.pdf", { type: "application/pdf" }),
    );
    await user.click(within(dialog).getByRole("button", { name: "Yükle" }));

    await waitFor(() => expect(individual.uploadFile).toHaveBeenCalledTimes(1));
    const [documentId, form] = individual.uploadFile.mock.calls[0] as [number, FormData];
    expect(documentId).toBe(73);
    expect(form.get("score_mode")).toBe("QUESTION_TABLE");
    expect(form.get("question_count")).toBe("8");
  });

  it("yükleme reddedilirse gerekçe bildirilir ve diyalog açık kalır", async () => {
    const user = userEvent.setup();
    individual.uploadFile.mockRejectedValue(
      new ApiError(400, "validation_error", "Yatay sayfa içeren PDF kabul edilmez."),
    );
    renderBolum();
    const li = await satir(/Mehmet Demir/);

    await user.click(within(li).getByRole("button", { name: "Yükle" }));
    const dialog = await screen.findByRole("dialog");
    await user.upload(
      within(dialog).getByLabelText(/Soru PDF dosyası/),
      new File(["%PDF-"], "yatay.pdf", { type: "application/pdf" }),
    );
    await user.click(within(dialog).getByRole("button", { name: "Yükle" }));

    expect(await screen.findByText("Yatay sayfa içeren PDF kabul edilmez.")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("“Seçimi kaldır” onaydan geçer; onay metninde öğrenci adı ve okul numarası yok", async () => {
    const user = userEvent.setup();
    individual.remove.mockResolvedValue(undefined);
    const { invalidate } = renderBolum();
    const li = await satir(/Zeynep Kaya/);

    await user.click(within(li).getByRole("button", { name: "Seçimi kaldır" }));
    // Tek tıkla silinmez: başlık soru, gövde sonuç (docs/sozluk.md §3).
    expect(individual.remove).not.toHaveBeenCalled();
    const dialog = await screen.findByRole("dialog", {
      name: "Bireysel soru dosyası kaldırılsın mı?",
    });
    expect(dialog).toHaveTextContent(
      "Bu öğrenci için yüklenen PDF silinir; öğrenci dersin soru dosyasından basılan kitapçığı alır.",
    );
    expect(dialog).not.toHaveTextContent(/Zeynep|103/);
    await user.click(within(dialog).getByRole("button", { name: "Kaldır" }));

    await waitFor(() => expect(individual.remove).toHaveBeenCalledWith(73));
    expect(await screen.findByText("Bireysel soru dosyası kaldırıldı.")).toBeInTheDocument();
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["individual-questions", 5] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["booklet-runs", 5] });
  });

  it("kaldırma onayında “Vazgeç” denirse seçim yerinde kalır", async () => {
    const user = userEvent.setup();
    renderBolum();
    const li = await satir(/Mehmet Demir/);

    await user.click(within(li).getByRole("button", { name: "Seçimi kaldır" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Bireysel soru dosyası kaldırılsın mı?",
    });
    await user.click(within(dialog).getByRole("button", { name: "Vazgeç" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(individual.remove).not.toHaveBeenCalled();
  });

  it("önizleme: PDF belge kimliğiyle alınır ve diyalogda gösterilir; kapatınca adres bırakılır", async () => {
    const user = userEvent.setup();
    const blob = new Blob(["%PDF-"], { type: "application/pdf" });
    individual.fileBlob.mockResolvedValue(blob);
    renderBolum();
    const li = await satir(/Zeynep Kaya/);

    await user.click(within(li).getByRole("button", { name: "Önizle" }));

    const dialog = await screen.findByRole("dialog", { name: "Önizleme — D-203 · koltuk 3" });
    expect(individual.fileBlob).toHaveBeenCalledWith(73);
    expect(URL.createObjectURL).toHaveBeenCalledWith(blob);
    expect(within(dialog).getByLabelText("Bireysel soru dosyası önizlemesi")).toHaveAttribute(
      "src",
      "blob:onizleme",
    );
    expect(dialog).not.toHaveTextContent(/Zeynep|103/);

    await user.click(within(dialog).getByRole("button", { name: "Kapat" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:onizleme");
  });

  it("önizleme alınamazsa gerekçe bildirilir", async () => {
    const user = userEvent.setup();
    individual.fileBlob.mockRejectedValue(
      new ApiError(404, "media_missing", "Bireysel soru dosyası bu bilgisayarda bulunamadı."),
    );
    renderBolum();
    const li = await satir(/Zeynep Kaya/);

    await user.click(within(li).getByRole("button", { name: "Önizle" }));

    expect(
      await screen.findByText("Bireysel soru dosyası bu bilgisayarda bulunamadı."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("idare özeti: PDF oturum kimliğiyle alınır, belge adı + oturum adı + tarihle kaydedilir", async () => {
    const user = userEvent.setup();
    const blob = new Blob(["%PDF-"], { type: "application/pdf" });
    individual.summaryBlob.mockResolvedValue(blob);
    renderBolum();

    await user.click(await screen.findByRole("button", { name: "İdare özeti (PDF)" }));

    await waitFor(() => expect(individual.summaryBlob).toHaveBeenCalledWith(5));
    await waitFor(() =>
      expect(download.saveBlob).toHaveBeenCalledWith(
        blob,
        "BEP-İdare-Özeti_2-Ortak-Sınav_15.06.2026.pdf",
      ),
    );
  });

  it("idare özeti üretilemezse backend gerekçesi bildirilir; dosya kaydedilmez", async () => {
    const user = userEvent.setup();
    individual.summaryBlob.mockRejectedValue(
      new ApiError(400, "validation_error", "Bu oturumda BEP kapsamında yerleşmiş öğrenci yok."),
    );
    renderBolum();

    await user.click(await screen.findByRole("button", { name: "İdare özeti (PDF)" }));

    expect(
      await screen.findByText("Bu oturumda BEP kapsamında yerleşmiş öğrenci yok."),
    ).toBeInTheDocument();
    expect(download.saveBlob).not.toHaveBeenCalled();
    // İndirme bitince düğme yeniden açılır.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "İdare özeti (PDF)" })).toBeEnabled(),
    );
  });
});
