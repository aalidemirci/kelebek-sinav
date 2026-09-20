// Mazeret Takibi ekranı testleri (19.09.2026): API ve saveBlob mock'lanır; yönlendirme
// GERÇEK router üzerinden doğrulanır. KVKK: fixture'lardaki ad ve numaralar UYDURMADIR.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { AbsenceRow, AbsencesResponse } from "./api";

const makeup = vi.hoisted(() => ({
  absences: vi.fn(),
  createSession: vi.fn(),
  remove: vi.fn(),
  reportBlob: vi.fn(),
}));
const attendance = vi.hoisted(() => ({ update: vi.fn() }));
const download = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, makeupApi: makeup };
});
vi.mock("../oturumlar/api", async (importActual) => {
  const actual = await importActual<typeof import("../oturumlar/api")>();
  return { ...actual, attendanceApi: { ...actual.attendanceApi, ...attendance } };
});
// Yalnız saveBlob sahtelenir; dosya adını kuran `dosyaAdi` GERÇEK kalır.
vi.mock("../../lib/download", async (importActual) => {
  const actual = await importActual<typeof import("../../lib/download")>();
  return { ...actual, ...download };
});

import MazeretTakibiPage from "./MazeretTakibiPage";

function satir(overrides: Partial<AbsenceRow> = {}): AbsenceRow {
  return {
    record_id: 1,
    session_id: 5,
    session_name: "1. Ortak Sınav",
    exam_date: "2026-11-16",
    session_is_makeup: false,
    session_type: "SCHOOL",
    session_type_label: "Okul",
    external: false,
    course_id: 3,
    level: 9,
    course_label: "Coğrafya — 9. Sınıf",
    student_id: 101,
    student_number: "101",
    full_name: "Ayşe Yılmaz",
    class_label: "9/A",
    excuse_status: "PENDING",
    excuse_label: "Beklemede",
    note: "",
    notice_deadline: "2026-11-23",
    notice_overdue: false,
    makeup_session_id: null,
    makeup_session_name: "",
    makeup_session_status: null,
    makeup_date: null,
    makeup_result: null,
    makeup_result_label: "",
    awaiting_makeup: overrides.can_makeup ?? false,
    plan_id: null,
    plan_name: "",
    plan_date: null,
    plan_period_no: null,
    can_makeup: false,
    ...overrides,
  };
}

const BEKLEYEN = satir();
const MAZERETLI = satir({
  record_id: 2,
  student_id: 102,
  student_number: "102",
  full_name: "Mehmet Demir",
  excuse_status: "EXCUSED",
  excuse_label: "Mazeretli",
  note: "Rapor no 12, 16.11.2026",
  can_makeup: true,
});
const ULKE = satir({
  record_id: 3,
  session_id: 6,
  session_name: "Ülke Geneli Sınav",
  exam_date: "2026-11-11",
  session_type: "NATIONAL",
  session_type_label: "Ülke",
  external: true,
  course_label: "Türk Dili ve Edebiyatı — 10. Sınıf",
  student_id: 201,
  student_number: "201",
  full_name: "Zeynep Kaya",
  class_label: "10/B",
  excuse_status: "EXCUSED",
  excuse_label: "Mazeretli",
  notice_deadline: "2026-11-18",
  can_makeup: true,
});

function yanit(rows: AbsenceRow[], overrides: Partial<AbsencesResponse> = {}): AbsencesResponse {
  return {
    semester_id: 3,
    semesters: [
      { id: 3, label: "2026-2027 · 1. dönem", default: true },
      { id: 4, label: "2026-2027 · 2. dönem", default: false },
    ],
    rows,
    summary: {
      total: rows.length,
      pending: rows.filter((r) => r.excuse_status === "PENDING").length,
      excused: rows.filter((r) => r.excuse_status === "EXCUSED").length,
      unexcused: rows.filter((r) => r.excuse_status === "UNEXCUSED").length,
      overdue: rows.filter((r) => r.notice_overdue).length,
      awaiting_makeup: rows.filter((r) => r.can_makeup).length,
      in_makeup: rows.filter((r) => r.makeup_session_id !== null).length,
    },
    notice_business_days: 5,
    ...overrides,
  };
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <ConfirmProvider>
          <MemoryRouter initialEntries={["/mazeret"]}>
            <Routes>
              <Route path="/mazeret" element={<MazeretTakibiPage />} />
              <Route path="/oturumlar/:id" element={<div>OTURUM EKRANI</div>} />
            </Routes>
          </MemoryRouter>
        </ConfirmProvider>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("MazeretTakibiPage", () => {
  it("dönemin girmeyenlerini sınav başına gruplar; seçim yalnız mazeret sınavı bekleyende açık", async () => {
    makeup.absences.mockResolvedValue(yanit([BEKLEYEN, MAZERETLI, ULKE]));
    renderPage();

    expect(
      await screen.findByRole("heading", { name: "16.11.2026 · Coğrafya — 9. Sınıf" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Mazeret Takibi" })).toBeVisible();
    expect(makeup.absences).toHaveBeenCalledWith(undefined); // varsayılan dönem backend'den
    expect(screen.getByText("Ülke geneli")).toBeInTheDocument();
    const ozet = screen.getByRole("list", { name: "Özet" });
    expect(within(ozet).getByText("Mazeret sınavı bekleyen").previousSibling).toHaveTextContent(
      "2",
    );

    expect(screen.getByRole("checkbox", { name: "101 mazeret sınavına seç" })).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: "102 mazeret sınavına seç" })).toBeEnabled();
    expect(screen.getByText("Son gün 18.11.2026")).toBeInTheDocument();
  });

  it("karar bekleyen kayıtta süre geçtiyse işaretlenir (uyarı — engel değil)", async () => {
    makeup.absences.mockResolvedValue(yanit([satir({ notice_overdue: true })]));
    renderPage();

    expect(await screen.findByText("Son gün 23.11.2026 — süre geçti")).toBeInTheDocument();
  });

  it("mazeret durumu anında, belge notu alan bırakılınca kaydedilir", async () => {
    const user = userEvent.setup();
    makeup.absences.mockResolvedValue(yanit([BEKLEYEN]));
    attendance.update.mockResolvedValue({});
    renderPage();

    await user.selectOptions(await screen.findByLabelText("101 mazeret durumu"), "EXCUSED");
    await waitFor(() =>
      expect(attendance.update).toHaveBeenCalledWith(1, { excuse_status: "EXCUSED" }),
    );
    const not = screen.getByLabelText("101 belge notu");
    await user.type(not, "Veli dilekçesi 17.11.2026");
    fireEvent.blur(not);
    await waitFor(() =>
      expect(attendance.update).toHaveBeenLastCalledWith(1, { note: "Veli dilekçesi 17.11.2026" }),
    );
  });

  it("seçilenlerle mazeret sınavı oluşturulur ve oturuma gidilir", async () => {
    const user = userEvent.setup();
    makeup.absences.mockResolvedValue(yanit([BEKLEYEN, MAZERETLI, ULKE]));
    makeup.createSession.mockResolvedValue({ id: 9 });
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Bekleyenlerin tümünü seç" }));
    expect(screen.getByText("2 öğrenci seçildi")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Mazeret sınavı oluştur" }));

    const dialog = await screen.findByRole("dialog", { name: "Mazeret sınavı oluştur" });
    expect(within(dialog).getByText("2 öğrenci, 2 ders.", { exact: false })).toBeInTheDocument();
    // Ülke geneli sınavın mazeret tarihi il MEM'ce ilan edilir (Yönerge md. 5/1-aa).
    expect(within(dialog).getByText(/il millî eğitim müdürlüğünce ilan edilir/)).toBeVisible();
    const olustur = within(dialog).getByRole("button", { name: "Oluştur" });
    expect(olustur).toBeDisabled(); // tarih girilmedi
    fireEvent.change(within(dialog).getByLabelText(/Sınav tarihi/), {
      target: { value: "2026-11-23" },
    });
    await user.click(olustur);

    await waitFor(() =>
      expect(makeup.createSession).toHaveBeenCalledWith({
        record_ids: [2, 3],
        name: "Mazeret Sınavı",
        exam_date: "2026-11-23",
        start_time: "09:00",
        duration_minutes: 40,
      }),
    );
    expect(await screen.findByText("OTURUM EKRANI")).toBeInTheDocument();
  });

  it("aynı öğrenci iki sınavın mazeretine seçilirse oluşturma kapanır", async () => {
    const user = userEvent.setup();
    const ikinci = satir({
      ...MAZERETLI,
      record_id: 4,
      session_id: 7,
      session_name: "2. Ortak Sınav",
      exam_date: "2026-11-17",
      course_label: "Fizik — 9. Sınıf",
    });
    makeup.absences.mockResolvedValue(yanit([MAZERETLI, ikinci]));
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Bekleyenlerin tümünü seç" }));
    await user.click(screen.getByRole("button", { name: "Mazeret sınavı oluştur" }));
    const dialog = await screen.findByRole("dialog", { name: "Mazeret sınavı oluştur" });
    expect(within(dialog).getByRole("alert")).toHaveTextContent(
      "Okul No 102 iki sınavın mazeretine birden seçildi",
    );
    fireEvent.change(within(dialog).getByLabelText(/Sınav tarihi/), {
      target: { value: "2026-11-23" },
    });
    expect(within(dialog).getByRole("button", { name: "Oluştur" })).toBeDisabled();
  });

  it("alınmış öğrenci mazeret sınavından onayla çıkarılır; ikinci mazeret sınavı yok notu", async () => {
    const user = userEvent.setup();
    const alinmis = satir({
      ...MAZERETLI,
      can_makeup: false,
      makeup_session_id: 9,
      makeup_session_name: "Kasım Mazeret",
      makeup_session_status: "DRAFT",
      makeup_date: "2026-11-23",
      makeup_result: "pending",
      makeup_result_label: "Yapılmadı",
    });
    const tekrar = satir({
      record_id: 7,
      session_id: 9,
      session_name: "Kasım Mazeret",
      session_is_makeup: true,
      student_id: 103,
      student_number: "103",
      full_name: "Can Öztürk",
    });
    makeup.absences.mockResolvedValue(yanit([alinmis, tekrar]));
    makeup.remove.mockResolvedValue({ removed: 1 });
    renderPage();

    expect(await screen.findByRole("link", { name: "Kasım Mazeret · 23.11.2026" })).toHaveAttribute(
      "href",
      "/oturumlar/9",
    );
    expect(
      screen.getByText("Mazeret sınavında girmedi — ikinci mazeret sınavı yapılmaz"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Çıkar" }));
    expect(await screen.findByText("Mazeret sınavından çıkarılsın mı?")).toBeInTheDocument();
    expect(makeup.remove).not.toHaveBeenCalled();
    const onay = await screen.findByRole("dialog", { name: "Mazeret sınavından çıkarılsın mı?" });
    await user.click(within(onay).getByRole("button", { name: "Çıkar" }));
    await waitFor(() => expect(makeup.remove).toHaveBeenCalledWith([2]));
  });

  it("yapılmış mazeret sınavında 'Çıkar' düğmesi yok", async () => {
    makeup.absences.mockResolvedValue(
      yanit([
        satir({
          ...MAZERETLI,
          can_makeup: false,
          makeup_session_id: 9,
          makeup_session_name: "Kasım Mazeret",
          makeup_session_status: "APPROVED",
          makeup_date: "2026-11-23",
          makeup_result: "attended",
          makeup_result_label: "Girdi",
        }),
      ]),
    );
    renderPage();

    expect(await screen.findByText("Girdi")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Çıkar" })).not.toBeInTheDocument();
  });

  it("süzgeç mazeretsizleri gösterir; rapor PDF ve Excel dönem adıyla indirilir", async () => {
    const user = userEvent.setup();
    const blob = new Blob(["%PDF"]);
    makeup.absences.mockResolvedValue(
      yanit([
        MAZERETLI,
        satir({
          record_id: 5,
          student_id: 103,
          student_number: "103",
          full_name: "Can Öztürk",
          excuse_status: "UNEXCUSED",
          excuse_label: "Mazeretsiz",
        }),
      ]),
    );
    makeup.reportBlob.mockResolvedValue(blob);
    renderPage();

    await user.selectOptions(await screen.findByLabelText("Göster"), "UNEXCUSED");
    expect(screen.queryByText("Mehmet Demir")).not.toBeInTheDocument();
    expect(screen.getByText("Can Öztürk")).toBeInTheDocument();
    expect(screen.getByText("e-Okul'a “G” işlenir")).toBeInTheDocument();
    // Süzgeç açıkken "tümünü seç" yalnız GÖRÜNEN kayıtları alır (burada seçilebilir yok).
    await user.click(screen.getByRole("button", { name: "Bekleyenlerin tümünü seç" }));
    expect(screen.getByText("0 öğrenci seçildi")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Rapor (PDF)" }));
    await waitFor(() => expect(makeup.reportBlob).toHaveBeenCalledWith(3, "pdf"));
    expect(download.saveBlob).toHaveBeenCalledWith(
      blob,
      "Mazeret-Takip-Çizelgesi_2026-2027-1-dönem.pdf",
    );
    await user.click(screen.getByRole("button", { name: "Rapor (Excel)" }));
    await waitFor(() => expect(makeup.reportBlob).toHaveBeenLastCalledWith(3, "xlsx"));
  });

  it("takvime alınmış kayıt elle seçilemez; takvimdeki yeri satırda yazar", async () => {
    makeup.absences.mockResolvedValue(
      yanit([
        satir({
          ...MAZERETLI,
          can_makeup: false,
          awaiting_makeup: true,
          plan_id: 4,
          plan_name: "Kasım Mazeret Takvimi",
          plan_date: "2026-11-23",
          plan_period_no: 2,
        }),
      ]),
    );
    renderPage();

    expect(
      await screen.findByText(
        "Mazeret takviminde: Kasım Mazeret Takvimi · 23.11.2026 · 2. ders saati",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "102 mazeret sınavına seç" })).toBeDisabled();
    // Seçilebilir kayıt yok → toplu seçim çubuğu hiç çizilmez.
    expect(
      screen.queryByRole("button", { name: "Mazeret sınavı oluştur" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Mazeret Takvimi" })).toBeInTheDocument();
  });

  it("dönem değişince o dönemin listesi istenir", async () => {
    const user = userEvent.setup();
    makeup.absences.mockResolvedValue(yanit([]));
    renderPage();

    expect(
      await screen.findByRole("heading", { name: "Bu dönemde sınava girmeyen öğrenci yok" }),
    ).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Dönem"), "4");
    await waitFor(() => expect(makeup.absences).toHaveBeenLastCalledWith(4));
  });
});
