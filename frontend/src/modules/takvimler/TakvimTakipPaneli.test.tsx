// Süreç takip paneli testleri: hücre tıkla-döngüsü, işaret ipucundaki tarihin
// lib/format ile (Europe/Istanbul) basılması, "Kalem yönetimi" düğmesinin
// cümle düzeni ve yükleme hatasının "kalem yok" boş durumuyla karışmaması.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { makeTrackMatrix } from "./testFixtures";

const calApi = vi.hoisted(() => ({ track: vi.fn(), setTrackMark: vi.fn() }));
const kalemApi = vi.hoisted(() => ({
  list: vi.fn(() => Promise.resolve({ count: 0, next: null, previous: null, results: [] })),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return {
    ...actual,
    examCalendarApi: { ...actual.examCalendarApi, ...calApi },
    examTrackItemApi: { ...actual.examTrackItemApi, ...kalemApi },
  };
});

import TakvimTakipPaneli from "./TakvimTakipPaneli";

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <ConfirmProvider>
          <TakvimTakipPaneli calendarId={7} />
        </ConfirmProvider>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("TakvimTakipPaneli", () => {
  it("işaretsiz hücreye tıklamak “Yapıldı” işaretini yollar", async () => {
    const user = userEvent.setup();
    calApi.track.mockResolvedValue(makeTrackMatrix());
    calApi.setTrackMark.mockResolvedValue({ cell: { item_id: 1, status: "DONE" } });
    renderPanel();

    expect(
      await screen.findByRole("columnheader", { name: "Ders / Sınıf düzeyi" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Coğrafya — Soru teslimi: işaretsiz" }));

    await waitFor(() =>
      expect(calApi.setTrackMark).toHaveBeenCalledWith(7, {
        entry_id: 41,
        item_id: 1,
        status: "DONE",
      }),
    );
  });

  it("işaret ipucu tarihi gg.aa.yyyy ve İstanbul saatiyle basar", async () => {
    calApi.track.mockResolvedValue(
      makeTrackMatrix({
        rows: [
          {
            entry_id: 41,
            course_name: "Coğrafya",
            level: 9,
            exam_kind: "WRITTEN",
            cells: [
              {
                item_id: 1,
                status: "DONE",
                marked_by_name: "Ayşe ÇELİK",
                // 21:30 UTC = ertesi gün 00:30 İstanbul: UTC'den gün türetmek
                // (eski toLocaleDateString, UTC makinede) tarihi bir gün geri atardı.
                marked_at: "2026-10-27T21:30:00Z",
              },
            ],
          },
        ],
      }),
    );
    renderPanel();

    const hucre = await screen.findByRole("button", { name: "Coğrafya — Soru teslimi: Yapıldı" });
    expect(hucre).toHaveAttribute("title", "Yapıldı · Ayşe ÇELİK · 28.10.2026 00:30");
  });

  it("“Kalem yönetimi” düğmesi cümle düzenindedir ve yönetim diyaloğunu açar", async () => {
    const user = userEvent.setup();
    calApi.track.mockResolvedValue(makeTrackMatrix());
    renderPanel();

    await user.click(await screen.findByRole("button", { name: "Kalem yönetimi" }));

    expect(
      await screen.findByRole("dialog", { name: "Süreç kalemi yönetimi" }),
    ).toBeInTheDocument();
  });

  it("yükleme hatası “kalem yok” diye sunulmaz — gerçek mesaj gösterilir", async () => {
    calApi.track.mockRejectedValue(new ApiError(500, "server_error", "Veritabanı kilitli."));
    renderPanel();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Süreç takibi yüklenemedi: Veritabanı kilitli.",
    );
    expect(screen.queryByText("Süreç kalemi yok")).not.toBeInTheDocument();
  });
});
