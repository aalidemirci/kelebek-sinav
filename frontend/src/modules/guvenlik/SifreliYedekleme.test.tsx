import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";

const mocks = vi.hoisted(() => ({
  postBlob: vi.fn(),
  saveBlob: vi.fn(),
}));

vi.mock("../../lib/api", () => ({ api: { postBlob: mocks.postBlob } }));
vi.mock("../../lib/download", () => ({ saveBlob: mocks.saveBlob }));

import SifreliYedekleme from "./SifreliYedekleme";

beforeEach(() => vi.clearAllMocks());

it("parola yokken şifreli yedek indirmesini kapalı tutar", () => {
  render(
    <SnackbarProvider>
      <SifreliYedekleme parolaKurulu={false} />
    </SnackbarProvider>,
  );

  expect(screen.getByRole("button", { name: /Şifreli yedeği indir/ })).toBeDisabled();
  expect(screen.getByText(/önce uygulama parolası kurmalısınız/)).toBeInTheDocument();
});

it("yalnız şifreli ddbak dosyasını kullanıcıya indirir", async () => {
  const blob = new Blob(["DDBAK-encrypted"]);
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
      expect.stringMatching(/^disiplin-defteri-yedek-.+\.ddbak$/),
    );
  });
});
