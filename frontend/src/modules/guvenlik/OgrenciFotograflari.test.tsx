// Güvenlik sekmesindeki öğrenci fotoğrafları kartı (19.09.2026 — kullanıcı
// kararı: "Ayarlar'da 'tüm fotoğrafları sil' düğmesi olur"). Silme Kişiler
// ekranındakiyle AYNI bileşenden gelir; burada kablolama ve sayım sınanır.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { PhotoStats } from "../okul/api";

const okul = vi.hoisted(() => ({
  photoStats: vi.fn(),
  deleteAllPhotos: vi.fn(),
}));

vi.mock("../okul/api", async (importActual) => {
  const actual = await importActual<typeof import("../okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...okul } };
});

import OgrenciFotograflari from "./OgrenciFotograflari";

function renderKart(stats: PhotoStats) {
  okul.photoStats.mockResolvedValue(stats);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <ConfirmProvider>
          <OgrenciFotograflari />
        </ConfirmProvider>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("OgrenciFotograflari", () => {
  it("sayımı gösterir; onaydan sonra hepsini siler ve sayımı tazeler", async () => {
    const user = userEvent.setup();
    okul.deleteAllPhotos.mockResolvedValue({ deleted: 7 });
    renderKart({ with_photo: 7, active_students: 10, without_photo: 3 });

    expect(await screen.findByText("7 öğrencinin fotoğrafı kayıtlı.")).toBeInTheDocument();
    expect(screen.getByText(/yalnız bu bilgisayardaki veritabanında durur/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Tüm fotoğrafları sil" }));
    await user.click(await screen.findByRole("button", { name: "Sil" }));

    await waitFor(() => expect(okul.deleteAllPhotos).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("7 fotoğraf kalıcı olarak silindi.")).toBeInTheDocument();
    // Silmeden sonra sayım yeniden sorulur (ilk yükleme + tazeleme).
    await waitFor(() => expect(okul.photoStats).toHaveBeenCalledTimes(2));
  });

  it("fotoğraf yoksa silme düğmesi kapalıdır", async () => {
    renderKart({ with_photo: 0, active_students: 10, without_photo: 10 });

    expect(await screen.findByText("Kayıtlı fotoğraf yok.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tüm fotoğrafları sil" })).toBeDisabled();
  });
});
