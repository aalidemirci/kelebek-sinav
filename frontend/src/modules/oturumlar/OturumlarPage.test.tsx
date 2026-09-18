// Sınav Oturumları listesi + yeni oturum diyaloğu testleri (F3).
// API mock'lanır; yönlendirme GERÇEK router üzerinden doğrulanır (useNavigate
// mock'lanmaz — KurulumPage test deseni). Ortak kurucu ./testFixtures'tan
// (test dosyaları birbirinden import ETMEZ — OYS Tur 232).

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
        makeSession({
          id: 8,
          name: "Geçen Yılın Sınavı",
          status: "ARCHIVED",
          exam_date: "2025-06-10",
        }),
      ]),
    );
    renderPage();

    expect(await screen.findByText("2. Ortak Sınav")).toBeInTheDocument();
    expect(screen.getByText("1. Deneme Sınavı")).toBeInTheDocument();
    // Durum adları aynı kipte: Taslak / Dağıtıldı / Onaylandı / Arşivlendi ("Arşiv" değil).
    expect(screen.getByText("Arşivlendi")).toBeInTheDocument();
    // Tarih Türkçe biçimde (lib/format.ts::formatDate) + saat + düzen etiketi.
    expect(screen.getByText(/15\.06\.2026 · 09:00 · Kelebek/)).toBeInTheDocument();
    expect(screen.getByText(/05\.01\.2026 · 09:00 · Kendi dersliğinde/)).toBeInTheDocument();
    // Durum rozetleri.
    expect(screen.getByText("Taslak")).toBeInTheDocument();
    expect(screen.getByText("Onaylandı")).toBeInTheDocument();
    // Gözetmen izi KS'de tamamen düştü.
    expect(screen.queryByText("Gözetmenli")).not.toBeInTheDocument();
  });

  it("boş listede EmptyState gösterir; içindeki düğme yeni oturum diyaloğunu açar", async () => {
    const user = userEvent.setup();
    exam.list.mockResolvedValue(paginated([]));
    renderPage();

    const baslik = await screen.findByRole("heading", { name: "Henüz sınav oturumu yok" });
    // Boş durumun kendi çıkışı vardır (sayfa başlığındaki düğmenin eşi).
    const kart = baslik.parentElement as HTMLElement;
    await user.click(within(kart).getByRole("button", { name: "Yeni sınav oturumu" }));
    expect(await screen.findByRole("dialog", { name: "Yeni sınav oturumu" })).toBeInTheDocument();
  });

  it("yükleme sırasında iskelet, hata durumunda role=alert gösterir", async () => {
    exam.list.mockRejectedValue(new Error("ağ koptu"));
    renderPage();

    // İlk çizimde sorgu beklemede → iskelet (düz "yükleniyor" metni değil).
    expect(screen.getByRole("status")).toHaveTextContent("Yükleniyor…");
    expect(await screen.findByRole("alert")).toHaveTextContent(/Oturumlar yüklenemedi/);
    expect(screen.queryByText("Henüz sınav oturumu yok")).not.toBeInTheDocument();
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
    exam.list.mockResolvedValue(paginated([makeSession()]));
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
    // Gözetmen anahtarı F7 ile diyaloğa geldi (U2 — varsayılan kapalı). Etiket evrak
    // kodu (R6) taşımaz — docs/sozluk.md §2.
    expect(screen.queryByText(/R6/)).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("checkbox", {
        name: "Gözetmen görevlendirmesi yapılacak (görevlendirme yazısı basılır)",
      }),
    );

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
