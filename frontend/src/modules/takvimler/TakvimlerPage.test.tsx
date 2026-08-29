// Takvim listesi testleri (F6): liste + filtre + ön tanımlı üretim (confirm'li)
// + yeni takvim akışı. API vi.mock ile ezilir; router gerçek (MemoryRouter).

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { makeCalendar, paginated } from "./testFixtures";

const calApi = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  generateDefaults: vi.fn(),
}));
const sessionApi = vi.hoisted(() => ({
  terms: vi.fn(() =>
    Promise.resolve({ terms: [{ id: 3, label: "2026-2027 Ders Yılı 1. Dönem" }] }),
  ),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, examCalendarApi: { ...actual.examCalendarApi, ...calApi } };
});
vi.mock("../oturumlar/api", async (importActual) => {
  const actual = await importActual<typeof import("../oturumlar/api")>();
  return { ...actual, examSessionApi: { ...actual.examSessionApi, ...sessionApi } };
});

import TakvimlerPage from "./TakvimlerPage";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <ConfirmProvider>
          <MemoryRouter initialEntries={["/takvimler"]}>
            <Routes>
              <Route path="/takvimler" element={<TakvimlerPage />} />
              <Route path="/takvimler/:id" element={<div>TAKVİM DETAY</div>} />
            </Routes>
          </MemoryRouter>
        </ConfirmProvider>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("TakvimlerPage", () => {
  it("takvimleri durum rozeti ve tarih aralığıyla listeler; satır detaya gider", async () => {
    const user = userEvent.setup();
    calApi.list.mockResolvedValue(
      paginated([
        makeCalendar(),
        makeCalendar({
          id: 8,
          round: 2,
          status: "APPROVED",
          name: "1. Dönem 2. Sınav Takvimi",
        }),
      ]),
    );
    renderPage();

    // Rozet metinleri filtre <option>'larıyla çakışır — satır içinde aranır.
    const satir1 = await screen.findByRole("button", {
      name: "1. Dönem 1. Sınav Takvimi takvimi",
    });
    expect(within(satir1).getByText("Taslak")).toBeInTheDocument();
    const satir2 = screen.getByRole("button", { name: "1. Dönem 2. Sınav Takvimi takvimi" });
    expect(within(satir2).getByText("Onaylandı")).toBeInTheDocument();
    expect(screen.getAllByText("26.10.2026 – 06.11.2026").length).toBe(2);

    await user.click(satir1);
    expect(await screen.findByText("TAKVİM DETAY")).toBeInTheDocument();
  });

  it("ön tanımlı üretim confirm'den geçer ve sonucu bildirir", async () => {
    const user = userEvent.setup();
    calApi.list.mockResolvedValue(paginated([]));
    calApi.generateDefaults.mockResolvedValue({ created: [makeCalendar()] });
    renderPage();

    const butonlar = await screen.findAllByRole("button", {
      name: "Ön Tanımlı Takvimleri Üret",
    });
    await user.click(butonlar[0]);
    const dialog = await screen.findByRole("dialog", { name: "Ön tanımlı takvimleri üret" });
    await user.click(within(dialog).getByRole("button", { name: "Üret" }));

    await waitFor(() => expect(calApi.generateDefaults).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("1 ön tanımlı takvim üretildi.")).toBeInTheDocument();
  });

  it("yeni takvim: dönem + tur + tarihlerle create çağrılır ve detaya gidilir", async () => {
    const user = userEvent.setup();
    calApi.list.mockResolvedValue(paginated([]));
    calApi.create.mockResolvedValue(makeCalendar({ id: 9, round: 3 }));
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Yeni takvim" }));
    const dialog = await screen.findByRole("dialog", { name: "Yeni Sınav Takvimi" });
    await user.selectOptions(within(dialog).getByLabelText("Dönem"), "3");
    await user.selectOptions(within(dialog).getByLabelText("Sınav turu"), "3");
    await user.type(within(dialog).getByLabelText("Başlangıç tarihi"), "2027-01-02");
    await user.type(within(dialog).getByLabelText("Bitiş tarihi"), "2027-01-15");
    await user.click(within(dialog).getByRole("button", { name: "Oluştur" }));

    await waitFor(() =>
      expect(calApi.create).toHaveBeenCalledWith({
        semester: 3,
        round: 3,
        start_date: "2027-01-02",
        end_date: "2027-01-15",
      }),
    );
    expect(await screen.findByText("TAKVİM DETAY")).toBeInTheDocument();
  });
});
