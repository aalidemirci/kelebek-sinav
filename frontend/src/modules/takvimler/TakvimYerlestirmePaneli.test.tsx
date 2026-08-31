// Yerleştirme ızgarası testleri (F6): tıkla-yerleştir akışı + uyarı snackbar'ı
// (uyarıyla yerleşir, sert reddi backend verir), hücre anahtarı sözleşmesi,
// boş hafta sonunun gizlenmesi, onaylı takvimde "Oturum Üret".

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { makeCell, makeEntry, makeGrid } from "./testFixtures";

const calApi = vi.hoisted(() => ({
  grid: vi.fn(),
  placeEntry: vi.fn(),
  unplaceEntry: vi.fn(),
  createSession: vi.fn(),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, examCalendarApi: { ...actual.examCalendarApi, ...calApi } };
});

import TakvimYerlestirmePaneli from "./TakvimYerlestirmePaneli";

function renderPanel(status: "DRAFT" | "SUBMITTED" | "APPROVED" = "DRAFT") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <MemoryRouter>
          <TakvimYerlestirmePaneli calendarId={7} status={status} onChanged={() => {}} />
        </MemoryRouter>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("TakvimYerlestirmePaneli", () => {
  it("ızgara başlıkları seviye + öğrenci sayısı; boş hafta sonu satırı gizli", async () => {
    calApi.grid.mockResolvedValue(makeGrid());
    renderPanel();

    expect(await screen.findByText("9. Sınıf (84)")).toBeInTheDocument();
    expect(screen.getByText("27.10.2026")).toBeInTheDocument();
    // 31 Ekim hafta sonu ve hücresi boş → satır üretilmez (kompakt ızgara).
    expect(screen.queryByText(/31\.10\.2026/)).not.toBeInTheDocument();
  });

  it("tıkla-yerleştir: dialog'dan girdi seçilir; backend uyarısı snackbar'da", async () => {
    const user = userEvent.setup();
    calApi.grid.mockResolvedValue(makeGrid());
    calApi.placeEntry.mockResolvedValue({
      entry: makeEntry({ placed_date: "2026-10-27", period_no: 1 }),
      warnings: ["Bu seviyede aynı gün 3. sınav — OKY md. 45."],
    });
    renderPanel();

    await user.click(
      await screen.findByRole("button", {
        name: "27.10.2026 1. Ders 9. Sınıf sınav yerleştir",
      }),
    );
    const dialog = await screen.findByRole("dialog", { name: "Sınav yerleştir" });
    await user.click(within(dialog).getByRole("button", { name: /Coğrafya/ }));

    await waitFor(() =>
      expect(calApi.placeEntry).toHaveBeenCalledWith(41, { date: "2026-10-27", period_no: 1 }),
    );
    // Uyarı yerleşimi ENGELLEMEZ — snackbar'da gösterilir.
    expect(await screen.findByText(/OKY md\. 45/)).toBeInTheDocument();
  });

  it("onaylı takvimde oturumsuz kelebek satırında 'Oturum Üret' görünür ve çağrılır", async () => {
    const user = userEvent.setup();
    calApi.grid.mockResolvedValue(
      makeGrid({
        calendar: { ...makeGrid().calendar, status: "APPROVED" },
        cells: { "2026-10-27|1|9": [makeCell()] },
        unplaced: [],
      }),
    );
    calApi.createSession.mockResolvedValue({ session_id: 12, name: "Takvim — 1. Ders" });
    renderPanel("APPROVED");

    await user.click(await screen.findByRole("button", { name: "Oturum Üret" }));
    await waitFor(() =>
      expect(calApi.createSession).toHaveBeenCalledWith(7, {
        date: "2026-10-27",
        period_no: 1,
      }),
    );
    expect(await screen.findByText(/Oturum üretildi/)).toBeInTheDocument();
  });

  it("okul dışı makam sınavı ders adını bozmadan AYRI rozetle görünür", async () => {
    calApi.grid.mockResolvedValue(
      makeGrid({
        cells: { "2026-10-27|1|9": [makeCell({ authority: "MINISTRY" })] },
        unplaced: [],
      }),
    );
    renderPanel();

    // Ders adı tam metin eşleşmesini korur (rozet ayrı <span>).
    expect(await screen.findByText("Coğrafya")).toBeInTheDocument();
    expect(screen.getByText("BAK")).toBeInTheDocument();
  });

  it("okul sınavında makam rozeti basılmaz", async () => {
    calApi.grid.mockResolvedValue(
      makeGrid({ cells: { "2026-10-27|1|9": [makeCell()] }, unplaced: [] }),
    );
    renderPanel();

    expect(await screen.findByText("Coğrafya")).toBeInTheDocument();
    expect(screen.queryByText("BAK")).not.toBeInTheDocument();
    expect(screen.queryByText("İL")).not.toBeInTheDocument();
  });

  it("onaylı takvimde yerleştirme/kaldırma denetimleri çizilmez", async () => {
    calApi.grid.mockResolvedValue(
      makeGrid({
        calendar: { ...makeGrid().calendar, status: "APPROVED" },
        cells: { "2026-10-27|1|9": [makeCell({ session_id: 12 })] },
        unplaced: [],
      }),
    );
    renderPanel("APPROVED");

    expect(await screen.findByText("Coğrafya")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /sınav yerleştir/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /yerleşimini kaldır/ })).not.toBeInTheDocument();
    // Oturumlu hücrede oturuma gitme bağlantısı var; hepsi oturumluysa üretim yok.
    expect(screen.getByRole("button", { name: "Üretilen oturuma git" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Oturum Üret" })).not.toBeInTheDocument();
  });
});
