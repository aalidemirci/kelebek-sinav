import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import ArsivBakimBanner from "./ArsivBakimBanner";

const mocks = vi.hoisted(() => ({ arsivAdaylari: vi.fn(), anonimlestir: vi.fn() }));

vi.mock("./api", () => ({
  bakimApi: { arsivAdaylari: mocks.arsivAdaylari, anonimlestir: mocks.anonimlestir },
}));

const LISTE = {
  retention_days: 730,
  candidates: [
    { id: 7, name: "1. Ortak Sınav", exam_date: "2024-06-03" },
    { id: 9, name: "2. Ortak Sınav", exam_date: "2024-06-10" },
  ],
};

function renderBanner() {
  return render(
    <SnackbarProvider>
      <ArsivBakimBanner />
    </SnackbarProvider>,
  );
}

describe("ArsivBakimBanner", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("adayları açılışta tespit eder; onay diyaloğu listeyi gösterip tetik atar", async () => {
    mocks.arsivAdaylari.mockResolvedValue(LISTE);
    mocks.anonimlestir.mockResolvedValue({ anonymized: [7, 9] });
    const user = userEvent.setup();
    renderBanner();

    expect(await screen.findByText(/2 arşiv oturumunun saklama süresi doldu/)).toBeInTheDocument();
    // 'İ' JS regex i-bayrağıyla katlanmaz (TR büyük İ) — ad birebir verilir.
    await user.click(screen.getByRole("button", { name: "İncele ve anonimleştir" }));

    // Onay diyaloğu aday listesini ve tarihleri (gg.aa.yyyy) gösterir (risk #9).
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("1. Ortak Sınav")).toBeInTheDocument();
    expect(screen.getByText("03.06.2024")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /geri dönüşsüz anonimleştir/i }));
    await waitFor(() => expect(mocks.anonimlestir).toHaveBeenCalledWith([7, 9]));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByText(/saklama süresi doldu/)).not.toBeInTheDocument();
  });

  it("aday yokken hiç görünmez", async () => {
    mocks.arsivAdaylari.mockResolvedValue({ retention_days: 730, candidates: [] });
    const { container } = renderBanner();
    await waitFor(() => expect(mocks.arsivAdaylari).toHaveBeenCalledTimes(1));
    expect(container.querySelector('[role="status"]')).not.toBeInTheDocument();
  });

  it("kilitli/çevrimdışı açılışta sessizce gizli kalır", async () => {
    mocks.arsivAdaylari.mockRejectedValue(new Error("423"));
    const { container } = renderBanner();
    await waitFor(() => expect(mocks.arsivAdaylari).toHaveBeenCalledTimes(1));
    expect(container.querySelector('[role="status"]')).not.toBeInTheDocument();
  });
});
