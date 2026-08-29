// Sınav Oturumları listesi + yeni oturum diyaloğu testleri (F3).
// API mock'lanır; yönlendirme GERÇEK router üzerinden doğrulanır (useNavigate
// mock'lanmaz — KurulumPage test deseni). Ortak kurucu ./testFixtures'tan
// (test dosyaları birbirinden import ETMEZ — OYS Tur 232).

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { ExamSession } from "./api";
import { makeSession } from "./testFixtures";

const exam = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  terms: vi.fn(() =>
    Promise.resolve({ terms: [{ id: 3, label: "2025-2026 Ders Yılı 1. Dönem" }] }),
  ),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, examSessionApi: { ...actual.examSessionApi, ...exam } };
});

import OturumlarPage from "./OturumlarPage";

function paginated(rows: ExamSession[]) {
  return { count: rows.length, next: null, previous: null, results: rows };
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <MemoryRouter initialEntries={["/oturumlar"]}>
          <Routes>
            <Route path="/oturumlar" element={<OturumlarPage />} />
            <Route path="/oturumlar/:id" element={<div>DETAY EKRANI</div>} />
          </Routes>
        </MemoryRouter>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("OturumlarPage", () => {
  it("oturumları gg.aa.yyyy tarih + durum rozetiyle listeler; 'Gözetmenli' rozeti YOK", async () => {
    exam.list.mockResolvedValue(
      paginated([
        makeSession(),
        makeSession({
          id: 6,
          name: "1. Deneme Sınavı",
          status: "APPROVED",
          exam_date: "2026-01-05",
          layout_mode: "HOME_CLASSROOM",
        }),
      ]),
    );
    renderPage();

    expect(await screen.findByText("2. Ortak Sınav")).toBeInTheDocument();
    expect(screen.getByText("1. Deneme Sınavı")).toBeInTheDocument();
    // Tarih Türkçe biçimde (lib/format.ts::formatDate) + saat + düzen etiketi.
    expect(screen.getByText(/15\.06\.2026 · 09:00 · Kelebek/)).toBeInTheDocument();
    expect(screen.getByText(/05\.01\.2026 · 09:00 · Kendi dersliğinde/)).toBeInTheDocument();
    // Durum rozetleri.
    expect(screen.getByText("Taslak")).toBeInTheDocument();
    expect(screen.getByText("Onaylandı")).toBeInTheDocument();
    // Gözetmen izi KS'de tamamen düştü.
    expect(screen.queryByText("Gözetmenli")).not.toBeInTheDocument();
  });

  it("boş listede yönlendirici boş durum metni gösterir", async () => {
    exam.list.mockResolvedValue(paginated([]));
    renderPage();

    expect(await screen.findByText(/Henüz sınav oturumu yok/)).toBeInTheDocument();
  });

  it("satıra tıklayınca oturum detayına gider", async () => {
    const user = userEvent.setup();
    exam.list.mockResolvedValue(paginated([makeSession()]));
    renderPage();

    await user.click(await screen.findByRole("button", { name: /2\. Ortak Sınav/ }));
    expect(await screen.findByText("DETAY EKRANI")).toBeInTheDocument();
  });

  it("yeni oturum: form doğru gövdeyle (term_id + proctors_enabled) gönderilir ve detaya gidilir", async () => {
    const user = userEvent.setup();
    exam.list.mockResolvedValue(paginated([]));
    exam.create.mockResolvedValue(makeSession({ id: 7, name: "3. Ortak Sınav" }));
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Yeni sınav oturumu" }));
    await user.type(screen.getByLabelText(/Oturum adı/), "3. Ortak Sınav");
    // Tarih alanı jsdom'da change olayıyla doldurulur (type="date").
    fireEvent.change(screen.getByLabelText(/Sınav tarihi/), {
      target: { value: "2026-06-15" },
    });
    // Dönem seçeneği terms ucundan (mock) gelir — yüklenmesini bekle.
    await user.selectOptions(
      screen.getByLabelText(/Dönem/),
      await screen.findByRole("option", { name: "2025-2026 Ders Yılı 1. Dönem" }),
    );
    // Gözetmen anahtarı F7 ile diyaloğa geldi (U2 — varsayılan kapalı).
    await user.click(screen.getByRole("checkbox", { name: /Gözetmen modülü açık/ }));

    await user.click(screen.getByRole("button", { name: "Oluştur" }));

    await waitFor(() =>
      expect(exam.create).toHaveBeenCalledWith({
        name: "3. Ortak Sınav",
        exam_date: "2026-06-15",
        start_time: "09:00",
        duration_minutes: 40,
        layout_mode: "BUTTERFLY",
        proctors_enabled: true,
        term_id: 3,
      }),
    );
    expect(await screen.findByText("DETAY EKRANI")).toBeInTheDocument();
  });
});
