// Yerleşim krokisi testleri (F3): API mock'lanır; kroki çizimi (rapor, doluluk
// çipleri, seed, rozet, lejant), tıkla-takas akışı ve takas KİLİDİ (yalnız
// DAĞITILDI) doğrulanır. Ortak kurucular testFixtures.ts'ten — test dosyası
// test dosyasından import ETMEZ (OYS Tur 232).

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { ExamSession } from "./api";
import { makeReport, makeRoomGeometry, makeSeating, makeSession, paginated } from "./testFixtures";

const sessionApi = vi.hoisted(() => ({
  seating: vi.fn(),
  swapSeats: vi.fn(),
}));
const roomApi = vi.hoisted(() => ({ list: vi.fn() }));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, examSessionApi: { ...actual.examSessionApi, ...sessionApi } };
});
vi.mock("../salonlar/api", async (importActual) => {
  const actual = await importActual<typeof import("../salonlar/api")>();
  return { ...actual, examRoomApi: { ...actual.examRoomApi, ...roomApi } };
});

import YerlesimPaneli from "./YerlesimPaneli";

function renderPanel(session: ExamSession) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <YerlesimPaneli session={session} />
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("YerlesimPaneli", () => {
  it("krokiyi rapor, doluluk çipi, seed, rozet ve lejantla çizer", async () => {
    const seating = makeSeating();
    seating.rooms[0].assignments[0].status = "PINNED";
    seating.rooms[0].assignments[1].status = "MANUAL";
    sessionApi.seating.mockResolvedValue(seating);
    roomApi.list.mockResolvedValue(paginated([makeRoomGeometry()]));
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    // Doğrulayıcı raporu + doluluk çipi + seed.
    expect(await screen.findByText("Sert kısıt ihlali yok (İHLAL = 0).")).toBeInTheDocument();
    expect(screen.getByText("D-204: 2/4 (%50)")).toBeInTheDocument();
    expect(screen.getByText("1234")).toBeInTheDocument();
    // Salon sekmesi + koltuklar (grid kimliğinden) + mobilya.
    expect(screen.getByRole("tab", { name: "D-204" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Ayşe Yılmaz/ })).toBeInTheDocument();
    expect(screen.getByText("Öğrt. Masası")).toBeInTheDocument();
    // PINNED/MANUAL rozetleri (class_label ile aynı span'da).
    expect(screen.getByText("9/A · Sabit")).toBeInTheDocument();
    expect(screen.getByText("9/B · Elle")).toBeInTheDocument();
    // Grup lejantı insan-okur etiketle.
    expect(screen.getByText("Matematik — 9. Sınıf")).toBeInTheDocument();
  });

  it("DAĞITILDI: iki koltuğa tıklayınca swap-seats çağrılır, ihlalsiz sonuç yeşil", async () => {
    const user = userEvent.setup();
    sessionApi.seating.mockResolvedValue(makeSeating());
    roomApi.list.mockResolvedValue(paginated([makeRoomGeometry()]));
    sessionApi.swapSeats.mockResolvedValue({ swapped: [], report: makeReport() });
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    await user.click(await screen.findByRole("button", { name: /Ayşe Yılmaz/ }));
    // İlk seçim vurgulanır (aria-pressed + etiket eki).
    expect(screen.getByRole("button", { name: /Ayşe Yılmaz.*takas için seçili/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await user.click(screen.getByRole("button", { name: /Mehmet Demir/ }));

    await waitFor(() => expect(sessionApi.swapSeats).toHaveBeenCalledWith(5, 11, 12));
    expect(await screen.findByText("Takas yapıldı — ihlal yok.")).toBeInTheDocument();
  });

  it("takas sonrası sert ihlal kırmızı snackbar'la duyurulur", async () => {
    const user = userEvent.setup();
    sessionApi.seating.mockResolvedValue(makeSeating());
    roomApi.list.mockResolvedValue(paginated([makeRoomGeometry()]));
    sessionApi.swapSeats.mockResolvedValue({
      swapped: [],
      report: makeReport({
        is_valid: false,
        hard_violations: ["101 ile 102 aynı grupta yan yana."],
      }),
    });
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    await user.click(await screen.findByRole("button", { name: /Ayşe Yılmaz/ }));
    await user.click(screen.getByRole("button", { name: /Mehmet Demir/ }));

    expect(await screen.findByText("Takas yapıldı ama 1 sert ihlal oluştu!")).toBeInTheDocument();
  });

  it("ONAYLI oturumda takas kilitli: koltuklar disabled, uç çağrılmaz", async () => {
    const user = userEvent.setup();
    sessionApi.seating.mockResolvedValue(makeSeating({ status: "APPROVED" }));
    roomApi.list.mockResolvedValue(paginated([makeRoomGeometry()]));
    renderPanel(makeSession({ status: "APPROVED" }));

    const seatA = await screen.findByRole("button", { name: /Ayşe Yılmaz/ });
    expect(seatA).toBeDisabled();
    // Takas yönergesi de gösterilmez.
    expect(screen.queryByText(/Takas: bir öğrenciye tıklayın/)).not.toBeInTheDocument();
    await user.click(seatA);
    await user.click(screen.getByRole("button", { name: /Mehmet Demir/ }));
    expect(sessionApi.swapSeats).not.toHaveBeenCalled();
  });
});
