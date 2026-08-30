import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import UpdateBanner from "./UpdateBanner";

const mocks = vi.hoisted(() => ({ check: vi.fn(), downloadInstaller: vi.fn(), saveBlob: vi.fn() }));

vi.mock("./api", () => ({
  updateApi: { check: mocks.check, downloadInstaller: mocks.downloadInstaller },
}));
vi.mock("../../lib/download", () => ({ saveBlob: mocks.saveBlob }));

const STATUS = {
  current_version: "2026.9.0",
  latest_version: "2026.10.0",
  update_available: true,
  release_name: "Ekim sürümü",
  published_at: "2026-10-01T12:00:00Z",
  release_url: "https://github.com/aalidemirci/kelebek-sinav/releases/tag/v2026.10.0",
  can_download: true,
  installer_name: "kelebek-sinav-2026.10.0-win64-setup.exe",
  installer_size: 42,
};

function renderBanner() {
  return render(
    <SnackbarProvider>
      <UpdateBanner />
    </SnackbarProvider>,
  );
}

describe("UpdateBanner", () => {
  afterEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("yeni sürümü otomatik denetler ve doğrulanmış kurucuyu indirir", async () => {
    const blob = new Blob(["kurucu"]);
    mocks.check.mockResolvedValue(STATUS);
    mocks.downloadInstaller.mockResolvedValue(blob);
    const user = userEvent.setup();
    renderBanner();
    expect(await screen.findByText(/Kelebek Sınav 2026.10.0 hazır/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /güncellemeyi indir/i }));
    await waitFor(() => expect(mocks.downloadInstaller).toHaveBeenCalledTimes(1));
    expect(mocks.saveBlob).toHaveBeenCalledWith(blob, STATUS.installer_name);
  });

  it("kullanıcının ertelediği sürümü yeniden göstermez", async () => {
    window.localStorage.setItem("kelebek-sinav-dismissed-update", STATUS.latest_version);
    mocks.check.mockResolvedValue(STATUS);
    renderBanner();
    await waitFor(() => expect(mocks.check).toHaveBeenCalledTimes(1));
    expect(screen.queryByText(/Kelebek Sınav 2026.10.0 hazır/)).not.toBeInTheDocument();
  });

  it("çevrimdışıyken sessizce gizli kalır (DD'de test edilmeyen boşluk)", async () => {
    mocks.check.mockRejectedValue(new Error("ağ yok"));
    const { container } = renderBanner();
    await waitFor(() => expect(mocks.check).toHaveBeenCalledTimes(1));
    expect(container.querySelector('[role="status"]')).not.toBeInTheDocument();
  });
});
