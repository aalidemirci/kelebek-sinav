// Öğrenci fotoğrafları paneli (19.09.2026): e-Okul OOG01001R080 Excel'i önce
// önizlenir, sonra aktarılır; kayıtlı fotoğrafı farklı öğrenciler için "koru /
// değiştir" seçimi aktarıma gider (kullanıcı kararı — mükerrer yüklemede sor);
// "Tüm fotoğrafları sil" onaydan geçer. KVKK: numaralar uydurmadır.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { PhotoImportReport, PhotoStats } from "../okul/api";

const okul = vi.hoisted(() => ({
  photoStats: vi.fn((): Promise<PhotoStats> =>
    Promise.resolve({ with_photo: 12, active_students: 40, without_photo: 28 }),
  ),
  previewPhotoImport: vi.fn(),
  commitPhotoImport: vi.fn(),
  deleteAllPhotos: vi.fn(),
}));

vi.mock("../okul/api", async (importActual) => {
  const actual = await importActual<typeof import("../okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...okul } };
});

import FotografPaneli from "./FotografPaneli";

function rapor(overrides: Partial<PhotoImportReport> = {}): PhotoImportReport {
  return {
    file_hash: "abc",
    file_name: "OOG01001R080.XLS",
    dry_run: true,
    already_imported: false,
    on_conflict: "keep",
    total: 30,
    placeholders: 2,
    matched: 27,
    created: 20,
    same: 4,
    conflicts: 3,
    replaced: 0,
    kept: 3,
    levels: ["9. Sınıf"],
    sections: ["9/A", "9/B"],
    missing_in_levels: 5,
    conflict_students: [
      { student_number: "101", class_label: "9/A" },
      { student_number: "102", class_label: "9/A" },
      { student_number: "201", class_label: "9/B" },
    ],
    conflicts_truncated: 0,
    skipped: [
      {
        location: "C8",
        issue:
          "Bu okul numarasıyla aktif öğrenci kaydı yok — önce öğrenci listesini e-Okul'dan güncelleyin.",
        value: "999",
      },
    ],
    skipped_truncated: 0,
    ...overrides,
  };
}

const XLS = new File(["sahte"], "OOG01001R080.XLS", { type: "application/vnd.ms-excel" });

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <ConfirmProvider>
          <FotografPaneli />
        </ConfirmProvider>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("FotografPaneli", () => {
  it("sayımı gösterir; önizleme düzeyi, yeni/aynı/farklı sayıları ve sorunları söyler", async () => {
    const user = userEvent.setup();
    okul.previewPhotoImport.mockResolvedValue(rapor());
    renderPanel();

    expect(
      await screen.findByText("12 öğrencinin fotoğrafı var · 28 öğrencinin yok"),
    ).toBeInTheDocument();
    expect(screen.getByText("OOG01001R080 - Fotoğraflı Öğrenci Listesi")).toBeInTheDocument();
    expect(screen.getByText(/sınıf düzeyi başına verir/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fotoğrafları aktar" })).toBeDisabled();

    await user.upload(screen.getByLabelText("e-Okul fotoğraflı öğrenci listesi (Excel)"), XLS);
    await user.click(screen.getByRole("button", { name: "Fotoğrafları önizle" }));

    await waitFor(() => expect(okul.previewPhotoImport).toHaveBeenCalledWith(XLS, "keep"));
    expect(
      await screen.findByText(
        /Önizleme — 9\. Sınıf · 2 şube · 30 fotoğraf: 20 yeni, 4 aynı, 3 farklı/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/2 öğrencinin e-Okul'da fotoğrafı yok/)).toBeInTheDocument();
    expect(screen.getByText(/101 · 9\/A, 102 · 9\/A, 201 · 9\/B/)).toBeInTheDocument();
    expect(screen.getByText("C8")).toBeInTheDocument();
    expect(screen.getByText("999")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fotoğrafları aktar" })).toBeEnabled();
  });

  it("mükerrer fotoğrafta seçilen “değiştir” aktarıma gider", async () => {
    const user = userEvent.setup();
    okul.previewPhotoImport.mockResolvedValue(rapor());
    okul.commitPhotoImport.mockResolvedValue(
      rapor({ dry_run: false, on_conflict: "replace", replaced: 3, kept: 0 }),
    );
    renderPanel();

    await user.upload(screen.getByLabelText("e-Okul fotoğraflı öğrenci listesi (Excel)"), XLS);
    await user.click(screen.getByRole("button", { name: "Fotoğrafları önizle" }));
    expect(await screen.findByText(/kayıtlı fotoğrafı bu/)).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Mevcut fotoğrafları koru" })).toBeChecked();
    await user.click(screen.getByRole("radio", { name: "Yenileriyle değiştir" }));
    await user.click(screen.getByRole("button", { name: "Fotoğrafları aktar" }));

    await waitFor(() => expect(okul.commitPhotoImport).toHaveBeenCalledWith(XLS, "replace"));
    expect(await screen.findByText("23 fotoğraf aktarıldı.")).toBeInTheDocument();
    expect(screen.getByText("3 fotoğraf yenisiyle değiştirildi.")).toBeInTheDocument();
  });

  it("okunamayan dosya gerekçesiyle role=alert basılır", async () => {
    const user = userEvent.setup();
    okul.previewPhotoImport.mockRejectedValue(
      new ApiError(400, "validation_error", "Dosya e-Okul Excel raporu olarak okunamadı."),
    );
    renderPanel();

    await user.upload(screen.getByLabelText("e-Okul fotoğraflı öğrenci listesi (Excel)"), XLS);
    await user.click(screen.getByRole("button", { name: "Fotoğrafları önizle" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Dosya e-Okul Excel raporu olarak okunamadı.",
    );
  });

  it("tüm fotoğrafları silme onaydan geçer", async () => {
    const user = userEvent.setup();
    okul.deleteAllPhotos.mockResolvedValue({ deleted: 12 });
    renderPanel();

    await user.click(await screen.findByRole("button", { name: "Tüm fotoğrafları sil" }));
    expect(
      await screen.findByRole("dialog", { name: "Bütün öğrenci fotoğrafları silinsin mi?" }),
    ).toBeInTheDocument();
    expect(okul.deleteAllPhotos).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Sil" }));

    await waitFor(() => expect(okul.deleteAllPhotos).toHaveBeenCalled());
    expect(await screen.findByText("12 fotoğraf kalıcı olarak silindi.")).toBeInTheDocument();
  });
});
