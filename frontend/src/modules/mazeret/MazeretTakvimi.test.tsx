// Mazeret Sınav Takvimi bileşeni testleri (20.09.2026): API ve saveBlob mock'lanır.
// KVKK: fixture'lardaki ad ve numaralar UYDURMADIR.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { MakeupPlan, MakeupPlanItem, MakeupPlanListResponse } from "./api";

const planApi = vi.hoisted(() => ({
  list: vi.fn(),
  get: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
  replace: vi.fn(),
  sync: vi.fn(),
  approve: vi.fn(),
  reopen: vi.fn(),
  createSessions: vi.fn(),
  pdfBlob: vi.fn(),
  moveItem: vi.fn(),
  pinItem: vi.fn(),
  removeItem: vi.fn(),
}));
const download = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, makeupPlanApi: planApi };
});
vi.mock("../../lib/download", async (importActual) => {
  const actual = await importActual<typeof import("../../lib/download")>();
  return { ...actual, ...download };
});

import MazeretTakvimi from "./MazeretTakvimi";

const PERIODS = [
  { no: 1, name: "1. Ders", start: "08:30" },
  { no: 2, name: "2. Ders", start: "09:20" },
  { no: 3, name: "3. Ders", start: "10:10" },
];

function kalem(overrides: Partial<MakeupPlanItem> = {}): MakeupPlanItem {
  return {
    id: 11,
    course_id: 3,
    level: 9,
    course_label: "Coğrafya — 9. Sınıf",
    source_date: "2026-11-16",
    external: false,
    placed_date: "2026-11-23",
    period_no: 2,
    is_pinned: false,
    note: "",
    student_count: 1,
    students: [
      { record_id: 1, student_number: "101", full_name: "Ayşe Yılmaz", class_label: "9/A" },
    ],
    session_id: null,
    session_name: "",
    session_status: null,
    ...overrides,
  };
}

function takvim(overrides: Partial<MakeupPlan> = {}): MakeupPlan {
  return {
    id: 4,
    name: "Kasım Mazeret Sınav Takvimi",
    semester_id: 3,
    semester_label: "2026-2027 · 1. dönem",
    status: "DRAFT",
    status_label: "Taslak",
    start_date: "2026-11-23",
    day_count: 2,
    max_per_day: 2,
    period_nos: [2, 3],
    strict_order: true,
    approved_by_name: "",
    approved_at: null,
    days: [
      { date: "2026-11-23", weekday_label: "Pazartesi" },
      { date: "2026-11-24", weekday_label: "Salı" },
    ],
    periods: PERIODS.slice(1),
    all_periods: PERIODS,
    items: [kalem()],
    errors: [],
    warnings: [],
    min_days: null,
    unsynced_count: 0,
    ...overrides,
  };
}

function liste(overrides: Partial<MakeupPlanListResponse> = {}): MakeupPlanListResponse {
  return {
    semester_id: 3,
    plans: [
      {
        id: 4,
        name: "Kasım Mazeret Sınav Takvimi",
        status: "DRAFT",
        status_label: "Taslak",
        start_date: "2026-11-23",
        day_count: 2,
      },
    ],
    all_periods: PERIODS,
    default_period_nos: [2, 3],
    eligible_count: 0,
    max_day_count: 20,
    ...overrides,
  };
}

function renderTakvim() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <ConfirmProvider>
          <MemoryRouter>
            <MazeretTakvimi semesterId={3} />
          </MemoryRouter>
        </ConfirmProvider>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("MazeretTakvimi", () => {
  it("takvim yokken bekleyen kayıtlarla yeni takvim kurulur", async () => {
    const user = userEvent.setup();
    planApi.list.mockResolvedValue(liste({ plans: [], eligible_count: 5 }));
    planApi.create.mockResolvedValue(takvim());
    renderTakvim();

    expect(
      await screen.findByRole("heading", { name: "Henüz mazeret takvimi yok" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Takvime alınmayı bekleyen 5 mazeretli kayıt var.")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Yeni mazeret takvimi" }));

    const dialog = await screen.findByRole("dialog", { name: "Yeni mazeret takvimi" });
    // Okulun sınav saatleri işaretli gelir; günlük sınırın varsayılanı 2'dir.
    expect(within(dialog).getByRole("checkbox", { name: /2\. Ders/ })).toBeChecked();
    expect(within(dialog).getByRole("checkbox", { name: /1\. Ders/ })).not.toBeChecked();
    expect(within(dialog).getByLabelText("Bir öğrenci bir günde en çok")).toHaveValue("2");
    expect(
      within(dialog).getByRole("checkbox", { name: /Asıl takvim sırasını kesin koru/ }),
    ).toBeChecked();
    const olustur = within(dialog).getByRole("button", { name: "Takvimi oluştur" });
    expect(olustur).toBeDisabled(); // başlangıç günü girilmedi
    fireEvent.change(within(dialog).getByLabelText(/İlk mazeret sınavı günü/), {
      target: { value: "2026-11-23" },
    });
    await user.clear(within(dialog).getByLabelText(/Kaç güne sığsın/));
    await user.type(within(dialog).getByLabelText(/Kaç güne sığsın/), "2");
    await user.click(olustur);

    await waitFor(() =>
      expect(planApi.create).toHaveBeenCalledWith({
        semester_id: 3,
        name: "Mazeret Sınav Takvimi",
        start_date: "2026-11-23",
        day_count: 2,
        max_per_day: 2,
        period_nos: [2, 3],
        strict_order: true,
      }),
    );
    expect(
      await screen.findByRole("heading", { name: "Kasım Mazeret Sınav Takvimi" }),
    ).toBeVisible();
  });

  it("bekleyen kayıt yoksa yeni takvim düğmesi kapalıdır", async () => {
    planApi.list.mockResolvedValue(liste({ plans: [], eligible_count: 0 }));
    renderTakvim();

    expect(await screen.findByRole("button", { name: "Yeni mazeret takvimi" })).toBeDisabled();
  });

  it("çizelge sınavları gün ve saate göre gösterir; sığmayanı gerekçesi ve en az günle söyler", async () => {
    planApi.list.mockResolvedValue(liste());
    planApi.get.mockResolvedValue(
      takvim({
        items: [
          kalem(),
          kalem({
            id: 12,
            course_label: "Tarih — 9. Sınıf",
            placed_date: null,
            period_no: null,
            note: "Belirlenen günlere sığmadı: Okul No 101 için uygun saat kalmadı.",
          }),
        ],
        min_days: 3,
        warnings: ["1 kaydın mazeret kararı hâlâ “Beklemede”."],
      }),
    );
    renderTakvim();

    const cizelge = await screen.findByRole("table", {
      name: "Mazeret sınavları yerleştirme çizelgesi",
    });
    const pazartesi = within(cizelge).getByRole("row", { name: /23\.11\.2026/ });
    expect(within(pazartesi).getByText("Coğrafya — 9. Sınıf")).toBeInTheDocument();
    expect(within(pazartesi).getByText("1 öğrenci · asıl sınav 16.11.2026")).toBeInTheDocument();
    expect(screen.getByText(/asıl takvim sırası kesin korunur/)).toBeInTheDocument();

    expect(screen.getByRole("heading", { name: "Takvime konmamış sınavlar (1)" })).toBeVisible();
    expect(screen.getByText(/Okul No 101 için uygun saat kalmadı/)).toBeInTheDocument();
    expect(screen.getByText("3 gün")).toBeInTheDocument();
    expect(screen.getByText("1 kaydın mazeret kararı hâlâ “Beklemede”.")).toBeInTheDocument();
  });

  it("öğrenci çakışması varken onay kapalıdır", async () => {
    planApi.list.mockResolvedValue(liste());
    planApi.get.mockResolvedValue(
      takvim({ errors: ["Okul No 101 aynı saatte hem “Coğrafya” hem “Matematik” sınavında."] }),
    );
    renderTakvim();

    expect(await screen.findByRole("alert")).toHaveTextContent("Okul No 101 aynı saatte");
    expect(screen.getByRole("button", { name: "Onayla" })).toBeDisabled();
  });

  it("sınav elle taşınır; taşımanın uyarıları ekranda kalır", async () => {
    const user = userEvent.setup();
    planApi.list.mockResolvedValue(liste());
    planApi.get.mockResolvedValue(takvim());
    planApi.moveItem.mockResolvedValue({
      ...takvim({ items: [kalem({ placed_date: "2026-11-24", period_no: 3, is_pinned: true })] }),
      result: { warnings: ["Okul No 101: 24 Kasım 2026 Salı günü 3 mazeret sınavı var."] },
    });
    renderTakvim();

    await user.click(
      await screen.findByRole("button", { name: "Coğrafya — 9. Sınıf sınavını taşı" }),
    );
    const dialog = await screen.findByRole("dialog", { name: "Sınavı taşı" });
    fireEvent.change(within(dialog).getByLabelText(/Mazeret sınavı tarihi/), {
      target: { value: "2026-11-24" },
    });
    await user.selectOptions(within(dialog).getByLabelText("Ders saati"), "3");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(planApi.moveItem).toHaveBeenCalledWith(11, {
        placed_date: "2026-11-24",
        period_no: 3,
        is_pinned: true,
      }),
    );
    const bant = await screen.findByRole("status", { name: "Bu taşımanın doğurduğu uyarılar" });
    expect(bant).toHaveTextContent("3 mazeret sınavı var");
    expect(screen.getByLabelText("Sabit")).toBeInTheDocument();
  });

  it("taşıma penceresinden sınav takvimden çıkarılır (onayla)", async () => {
    const user = userEvent.setup();
    planApi.list.mockResolvedValue(liste());
    planApi.get.mockResolvedValue(takvim());
    planApi.removeItem.mockResolvedValue(takvim({ items: [] }));
    renderTakvim();

    await user.click(
      await screen.findByRole("button", { name: "Coğrafya — 9. Sınıf sınavını taşı" }),
    );
    await user.click(await screen.findByRole("button", { name: "Takvimden çıkar" }));
    const onay = await screen.findByRole("dialog", { name: "Sınav takvimden çıkarılsın mı?" });
    expect(planApi.removeItem).not.toHaveBeenCalled();
    await user.click(within(onay).getByRole("button", { name: "Çıkar" }));
    await waitFor(() => expect(planApi.removeItem).toHaveBeenCalledWith(11));
  });

  it("yeniden yerleştirir, yeni kayıtları ekler ve parametreleri değiştirir", async () => {
    const user = userEvent.setup();
    planApi.list.mockResolvedValue(liste());
    planApi.get.mockResolvedValue(takvim({ unsynced_count: 2 }));
    planApi.replace.mockResolvedValue({
      ...takvim({ unsynced_count: 2 }),
      result: { placed: 1, unplaced: 0 },
    });
    planApi.sync.mockResolvedValue({ ...takvim(), result: { added: 2 } });
    planApi.update.mockResolvedValue(takvim({ day_count: 4, strict_order: false }));
    renderTakvim();

    await user.click(await screen.findByRole("button", { name: "Yeniden yerleştir" }));
    await waitFor(() => expect(planApi.replace).toHaveBeenCalledWith(4));
    await user.click(await screen.findByRole("button", { name: "Kayıtları güncelle (2)" }));
    await waitFor(() => expect(planApi.sync).toHaveBeenCalledWith(4));
    // Eklenen kayıtlardan sonra düğme kaybolur (snackbar kuyrukludur; metni beklenmez).
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /Kayıtları güncelle/ })).not.toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: "Parametreler" }));
    const dialog = await screen.findByRole("dialog", { name: "Takvim parametreleri" });
    await user.click(
      within(dialog).getByRole("checkbox", { name: /Asıl takvim sırasını kesin koru/ }),
    );
    await user.click(within(dialog).getByRole("button", { name: "Kaydet ve yeniden yerleştir" }));
    await waitFor(() =>
      expect(planApi.update).toHaveBeenCalledWith(4, {
        name: "Kasım Mazeret Sınav Takvimi",
        start_date: "2026-11-23",
        day_count: 2,
        max_per_day: 2,
        period_nos: [2, 3],
        strict_order: false,
      }),
    );
    expect(await screen.findByText(/sınavlar boş saatlere öne çekilir/)).toBeInTheDocument();
  });

  it("onaylanır, oturumlar tek tıkla üretilir ve oturuma bağlantı çıkar", async () => {
    const user = userEvent.setup();
    const onayli = takvim({ status: "APPROVED", status_label: "Onaylandı" });
    planApi.list.mockResolvedValue(liste());
    planApi.get.mockResolvedValue(takvim());
    planApi.approve.mockResolvedValue({ ...onayli, result: null });
    planApi.createSessions.mockResolvedValue({
      ...takvim({
        status: "APPROVED",
        status_label: "Onaylandı",
        items: [kalem({ session_id: 9, session_name: "Kasım Mazeret", session_status: "DRAFT" })],
      }),
      result: { created: ["Kasım Mazeret — 23.11.2026 2. Ders"], skipped: [] },
    });
    renderTakvim();

    await user.click(await screen.findByRole("button", { name: "Onayla" }));
    const dialog = await screen.findByRole("dialog", { name: "Mazeret takvimi onaylansın mı?" });
    await user.type(within(dialog).getByLabelText("Onaylayan"), " Ali VELİ ");
    await user.click(within(dialog).getByRole("button", { name: "Onayla" }));
    await waitFor(() => expect(planApi.approve).toHaveBeenCalledWith(4, "Ali VELİ"));

    // Onaylı takvimde düzenleme düğmeleri yok; oturum üretimi açık.
    expect(await screen.findByText("Onaylandı")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Yeniden yerleştir" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /sınavını taşı/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Oturumları oluştur" }));
    await waitFor(() => expect(planApi.createSessions).toHaveBeenCalledWith(4));
    expect(await screen.findByRole("link", { name: "Oturuma git" })).toHaveAttribute(
      "href",
      "/oturumlar/9",
    );
    expect(screen.getByRole("button", { name: "Oturumları oluştur" })).toBeDisabled();
  });

  it("ilan nüshası adsız iner; öğrenci listesi istenirse okul numarasıyla alınır", async () => {
    const user = userEvent.setup();
    const blob = new Blob(["%PDF"]);
    planApi.list.mockResolvedValue(liste());
    planApi.get.mockResolvedValue(takvim());
    planApi.pdfBlob.mockResolvedValue(blob);
    renderTakvim();

    await user.click(await screen.findByRole("button", { name: "Takvim (PDF)" }));
    await waitFor(() => expect(planApi.pdfBlob).toHaveBeenCalledWith(4, "ilan", false));
    expect(download.saveBlob).toHaveBeenLastCalledWith(blob, "Kasım-Mazeret-Sınav-Takvimi.pdf");

    await user.click(screen.getByRole("button", { name: "Öğrenci listesi (PDF)" }));
    await waitFor(() => expect(planApi.pdfBlob).toHaveBeenLastCalledWith(4, "liste", true));
    expect(download.saveBlob).toHaveBeenLastCalledWith(
      blob,
      "Kasım-Mazeret-Sınav-Takvimi_Öğrenci-Listesi.pdf",
    );

    await user.click(screen.getByRole("checkbox", { name: /adları gizle/ }));
    await user.click(screen.getByRole("button", { name: "Öğrenci listesi (PDF)" }));
    await waitFor(() => expect(planApi.pdfBlob).toHaveBeenLastCalledWith(4, "liste", false));
    expect(download.saveBlob).toHaveBeenLastCalledWith(
      blob,
      "Kasım-Mazeret-Sınav-Takvimi_Öğrenci-Listesi-(okul-numarasıyla).pdf",
    );
  });

  it("taslak takvim onayla silinir", async () => {
    const user = userEvent.setup();
    planApi.list.mockResolvedValue(liste());
    planApi.get.mockResolvedValue(takvim());
    planApi.remove.mockResolvedValue(undefined);
    renderTakvim();

    await user.click(await screen.findByRole("button", { name: "Takvimi sil" }));
    const onay = await screen.findByRole("dialog", { name: "Mazeret takvimi silinsin mi?" });
    await user.click(within(onay).getByRole("button", { name: "Sil" }));
    await waitFor(() => expect(planApi.remove).toHaveBeenCalledWith(4));
  });
});
