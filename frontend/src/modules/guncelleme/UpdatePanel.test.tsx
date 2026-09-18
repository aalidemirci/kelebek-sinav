// Güncelleme paneli testleri: kullanıcı dili ("yayımlanan son sürüm", "kurulum
// dosyası" — GitHub/Release/kurucu/SHA jargonu yok), elle denetim, doğrulanmış
// indirme ve çevrimdışı hata bandı.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";

const mocks = vi.hoisted(() => ({ check: vi.fn(), downloadInstaller: vi.fn(), saveBlob: vi.fn() }));

vi.mock("./api", () => ({
  updateApi: { check: mocks.check, downloadInstaller: mocks.downloadInstaller },
}));
vi.mock("../../lib/download", () => ({ saveBlob: mocks.saveBlob }));

import UpdatePanel from "./UpdatePanel";

const GUNCEL = {
  current_version: "2026.9.0",
  latest_version: "2026.9.0",
  update_available: false,
  release_name: "Eylül sürümü",
  published_at: "2026-09-01T12:00:00Z",
  release_url: "https://example.invalid/kelebek-sinav/v2026.9.0",
  can_download: false,
  installer_name: "",
  installer_size: 0,
};

const YENI_SURUM = {
  ...GUNCEL,
  latest_version: "2026.10.0",
  update_available: true,
  can_download: true,
  installer_name: "kelebek-sinav-2026.10.0-win64-setup.exe",
  installer_size: 43_515_904,
};

function renderPanel() {
  return render(
    <SnackbarProvider>
      <UpdatePanel />
    </SnackbarProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("UpdatePanel", () => {
  it("sürümleri kullanıcı diliyle gösterir — GitHub/Release/kurucu/SHA jargonu yok", async () => {
    mocks.check.mockResolvedValue(GUNCEL);
    renderPanel();

    expect(await screen.findByText("Uygulama güncel.")).toBeInTheDocument();
    expect(screen.getByText("Kurulu sürüm")).toBeInTheDocument();
    expect(screen.getByText("Yayımlanan son sürüm")).toBeInTheDocument();
    expect(screen.getByText(/bütünlüğü doğrulanmadan indirmeye sunulmaz/)).toBeInTheDocument();
    expect(screen.queryByText(/GitHub|Release|kurucu|SHA-256/)).not.toBeInTheDocument();
  });

  it("“Şimdi denetle” sunucuyu zorla yeniden sorar", async () => {
    const user = userEvent.setup();
    mocks.check.mockResolvedValue(GUNCEL);
    renderPanel();
    await screen.findByText("Uygulama güncel.");

    await user.click(screen.getByRole("button", { name: "Şimdi denetle" }));

    await waitFor(() => expect(mocks.check).toHaveBeenLastCalledWith(true));
  });

  it("yeni sürümde kurulum dosyası doğrulanarak indirilir", async () => {
    const user = userEvent.setup();
    const blob = new Blob(["kurulum"]);
    mocks.check.mockResolvedValue(YENI_SURUM);
    mocks.downloadInstaller.mockResolvedValue(blob);
    renderPanel();

    expect(await screen.findByText("Yeni sürüm hazır: 2026.10.0")).toBeInTheDocument();
    // 41,5 MB — Türkçe sayı biçimi (ondalık virgül).
    expect(screen.getByText("Windows kurulum dosyası: 41,5 MB")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Doğrula ve indir" }));

    await waitFor(() =>
      expect(mocks.saveBlob).toHaveBeenCalledWith(blob, YENI_SURUM.installer_name),
    );
    expect(await screen.findByText("Kurulum dosyası doğrulanarak indirildi.")).toBeInTheDocument();
  });

  it("indirilecek dosya yoksa bunu “kurulum dosyası” diye söyler", async () => {
    mocks.check.mockResolvedValue({ ...YENI_SURUM, can_download: false });
    renderPanel();

    expect(
      await screen.findByText("Bu sürümde Windows kurulum dosyası bulunmuyor."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Doğrula ve indir" })).toBeDisabled();
  });

  it("Pardus/Linux’ta Windows kurulum dosyası önermez, paketle güncellemeye yönlendirir", async () => {
    mocks.check.mockResolvedValue({
      ...YENI_SURUM,
      platform: "linux",
      can_download: false,
      installer_name: "",
      installer_size: 0,
    });
    renderPanel();

    expect(await screen.findByText("Yeni sürüm hazır: 2026.10.0")).toBeInTheDocument();
    expect(screen.getByText(/güncelleme paketle yapılır/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Doğrula ve indir" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Windows kurulum dosyası/)).not.toBeInTheDocument();
  });

  it("denetim başarısızsa hata canlı bölgede gösterilir", async () => {
    mocks.check.mockRejectedValue(new Error("ağ yok"));
    renderPanel();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Güncelleme denetlenemedi. İnternet bağlantısını kontrol edin.",
    );
  });
});
