// Şifreli yedek kartı testleri: parola kapısı, yalnız .ksbak indirmesi, dosya
// adında YEREL tarih (UTC `toISOString` değil) ve kripto jargonsuz metin.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";

const mocks = vi.hoisted(() => ({
  postBlob: vi.fn(),
  saveBlob: vi.fn(),
}));

vi.mock("../../lib/api", () => ({ api: { postBlob: mocks.postBlob } }));
vi.mock("../../lib/download", () => ({ saveBlob: mocks.saveBlob }));

import SifreliYedekleme from "./SifreliYedekleme";

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.useRealTimers());

it("parola yokken şifreli yedek indirmesini kapalı tutar", () => {
  render(
    <SnackbarProvider>
      <SifreliYedekleme parolaKurulu={false} />
    </SnackbarProvider>,
  );

  expect(screen.getByRole("button", { name: /Şifreli yedeği indir/ })).toBeDisabled();
  expect(screen.getByText(/önce uygulama parolası kurmalısınız/)).toBeInTheDocument();
});

it("yalnız şifreli ksbak dosyasını kullanıcıya indirir", async () => {
  const blob = new Blob(["KSBAK-encrypted"]);
  mocks.postBlob.mockResolvedValue(blob);
  render(
    <SnackbarProvider>
      <SifreliYedekleme parolaKurulu />
    </SnackbarProvider>,
  );

  await userEvent.click(screen.getByRole("button", { name: /Şifreli yedeği indir/ }));

  await waitFor(() => {
    expect(mocks.postBlob).toHaveBeenCalledWith("/backups/encrypted/");
    expect(mocks.saveBlob).toHaveBeenCalledWith(
      blob,
      expect.stringMatching(/^kelebek-sinav-yedek-\d{4}-\d{2}-\d{2}\.ksbak$/),
    );
  });
});

it("dosya adındaki tarih YEREL tarihtir (UTC'den türetilmez)", async () => {
  // Yerel 18 Eylül 00:30: UTC+3'te `toISOString()` hâlâ 17 Eylül der. Sahte saat
  // yalnız Date'i dondurur (zamanlayıcılar gerçek kalır — waitFor çalışsın).
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 8, 18, 0, 30, 0));
  mocks.postBlob.mockResolvedValue(new Blob(["x"]));
  render(
    <SnackbarProvider>
      <SifreliYedekleme parolaKurulu />
    </SnackbarProvider>,
  );

  await userEvent.click(screen.getByRole("button", { name: /Şifreli yedeği indir/ }));

  await waitFor(() =>
    expect(mocks.saveBlob).toHaveBeenCalledWith(
      expect.anything(),
      "kelebek-sinav-yedek-2026-09-18.ksbak",
    ),
  );
});

it("metin kripto jargonu kullanmaz (teknik adlar yalnız Hakkında sayfasında)", () => {
  render(
    <SnackbarProvider>
      <SifreliYedekleme parolaKurulu />
    </SnackbarProvider>,
  );

  expect(screen.getByText(/güçlü şifrelemeyle\s+korunur/)).toBeInTheDocument();
  expect(screen.getByText(/ağ diskine/)).toBeInTheDocument();
  expect(screen.queryByText(/X25519|AES-256|NAS/)).not.toBeInTheDocument();
});
