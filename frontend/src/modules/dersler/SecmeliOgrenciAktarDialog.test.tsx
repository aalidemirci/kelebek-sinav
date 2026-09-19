// e-Okul OOK10002R010 (Seçmeli Ders Öğrencileri) PDF aktarımı: önce "Önizle"
// (hiçbir şey yazmaz), sonra "Aktar". Aktar önizlemesiz açılmaz; rapor her e-Okul
// dersinin havuzdaki karşılığını ve satır sorunlarını KONUMLA (sayfa/satır + okul
// no, ad YOK) gösterir. KVKK: numaralar uydurmadır, dosya içeriği sahte baytlardır.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { ElectiveImportReport } from "./api";

const dersler = vi.hoisted(() => ({
  previewEnrollmentImport: vi.fn(),
  commitEnrollmentImport: vi.fn(),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, derslerApi: { ...actual.derslerApi, ...dersler } };
});

import SecmeliOgrenciAktarDialog from "./SecmeliOgrenciAktarDialog";

function rapor(overrides: Partial<ElectiveImportReport> = {}): ElectiveImportReport {
  return {
    file_hash: "abc",
    file_name: "secmeli.pdf",
    school_year: "2026-2027",
    pages: 3,
    total_rows: 5,
    processed: 4,
    already_imported: false,
    dry_run: true,
    covered_section_count: 3,
    covered_levels: ["9. Sınıf", "10. Sınıf"],
    courses: [
      {
        title: "SEÇMELİ KUR`AN-I KERİM",
        status: "matched",
        course_id: 7,
        course_name: "Kur'an-ı Kerim",
        note: "",
        report_rows: 3,
        students: 3,
        sections: ["9/A", "9/B"],
      },
      {
        title: "SEÇMELİ ASTRONOMİ",
        status: "unmatched",
        course_id: null,
        course_name: "",
        note: "Ders Havuzu'nda bu adla seçmeli ders yok.",
        report_rows: 1,
        students: 0,
        sections: ["10/A"],
      },
    ],
    untouched_courses: ["Peygamberimizin Hayatı"],
    warnings: [
      {
        page: 2,
        line: 14,
        issue: "Rapordaki şube (9/B) öğrenci kaydındaki şubeden (9/A) farklı.",
        value: "1234",
      },
    ],
    skipped: [{ page: 3, line: 5, issue: "Okul numarası öğrenci listesinde yok.", value: "9999" }],
    warnings_truncated: 0,
    skipped_truncated: 2,
    ...overrides,
  };
}

function renderDialog() {
  const onClose = vi.fn();
  const onImported = vi.fn();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <SecmeliOgrenciAktarDialog onClose={onClose} onImported={onImported} />
      </SnackbarProvider>
    </QueryClientProvider>,
  );
  return { onClose, onImported };
}

const PDF = new File(["%PDF-1.4 sahte"], "secmeli.pdf", { type: "application/pdf" });

afterEach(() => vi.clearAllMocks());

describe("SecmeliOgrenciAktarDialog", () => {
  it("e-Okul yolunu söyler; dosya seçilmeden önizleme, önizlemeden aktarım açılmaz", async () => {
    const user = userEvent.setup();
    dersler.previewEnrollmentImport.mockResolvedValue(rapor());
    renderDialog();

    const dialog = screen.getByRole("dialog", {
      name: "e-Okul'dan seçmeli ders öğrencilerini aktar",
    });
    expect(within(dialog).getByText("Öğrenci Seçmeli Derslerini Belirle")).toBeInTheDocument();
    expect(within(dialog).getByText("OOK10002R010 - Seçmeli Ders Öğrencileri")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Önizle" })).toBeDisabled();
    expect(within(dialog).getByRole("button", { name: "Aktar" })).toBeDisabled();

    await user.upload(within(dialog).getByLabelText("e-Okul OOK10002R010 raporu (PDF)"), PDF);
    expect(within(dialog).getByRole("button", { name: "Önizle" })).toBeEnabled();
    expect(within(dialog).getByRole("button", { name: "Aktar" })).toBeDisabled();

    await user.click(within(dialog).getByRole("button", { name: "Önizle" }));
    await waitFor(() => expect(dersler.previewEnrollmentImport).toHaveBeenCalledWith(PDF));
    expect(dersler.commitEnrollmentImport).not.toHaveBeenCalled();

    expect(
      await within(dialog).findByText(/Önizleme — 2026-2027 ders yılı · 3/),
    ).toBeInTheDocument();
    const tablo = within(within(dialog).getAllByRole("table")[0]);
    expect(tablo.getByText("SEÇMELİ KUR`AN-I KERİM")).toBeInTheDocument();
    expect(tablo.getByText("Kur'an-ı Kerim")).toBeInTheDocument();
    expect(tablo.getByText("9/A, 9/B")).toBeInTheDocument();
    expect(tablo.getByText("Eşleşmedi")).toBeInTheDocument();
    expect(tablo.getByText("Ders Havuzu'nda bu adla seçmeli ders yok.")).toBeInTheDocument();
    expect(within(dialog).getByText(/1 ders Ders Havuzu'nda eşleşmedi/)).toBeInTheDocument();
    // Kapsam söylenir: süzülmüş rapor öbür şubelerin listesini silmez.
    expect(
      within(dialog).getByText(
        /Rapor 9\. Sınıf, 10\. Sınıf düzeylerinden 3 şubeyi kapsıyor; .*öbür şubelere dokunulmaz/,
      ),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText(/listesine dokunulmayan dersler: Peygamberimizin Hayatı/),
    ).toBeInTheDocument();
    // Sorunlar konumla + okul numarasıyla; kısaltılan satırlar sayıya eklenir.
    expect(within(dialog).getByText("Uyarılar (1)")).toBeInTheDocument();
    expect(within(dialog).getByText("Aktarılmayan satırlar (3)")).toBeInTheDocument();
    expect(within(dialog).getByText("2 / 14")).toBeInTheDocument();
    expect(within(dialog).getByText("9999")).toBeInTheDocument();
    expect(within(dialog).getByText(/ve 2 satır daha/)).toBeInTheDocument();

    expect(within(dialog).getByRole("button", { name: "Aktar" })).toBeEnabled();
  });

  it("önizlemeden sonra Aktar yazar, sorguları tazeler ve düğme Kapat olur", async () => {
    const user = userEvent.setup();
    dersler.previewEnrollmentImport.mockResolvedValue(rapor());
    dersler.commitEnrollmentImport.mockResolvedValue(rapor({ dry_run: false }));
    const { onImported } = renderDialog();

    await user.upload(screen.getByLabelText("e-Okul OOK10002R010 raporu (PDF)"), PDF);
    await user.click(screen.getByRole("button", { name: "Önizle" }));
    await screen.findByText(/Önizleme — 2026-2027/);
    await user.click(screen.getByRole("button", { name: "Aktar" }));

    await waitFor(() => expect(dersler.commitEnrollmentImport).toHaveBeenCalledWith(PDF));
    expect(
      await screen.findByText("1 dersin öğrenci listesi aktarıldı (4 öğrenci-ders kaydı)."),
    ).toBeInTheDocument();
    expect(onImported).toHaveBeenCalled();
    // Bildirim de kendi "Kapat" düğmesini taşır — sorgu pencereyle sınırlanır.
    const dialog = within(
      screen.getByRole("dialog", { name: "e-Okul'dan seçmeli ders öğrencilerini aktar" }),
    );
    expect(dialog.getByText(/Aktarım — 2026-2027 ders yılı/)).toBeInTheDocument();
    expect(dialog.getByRole("button", { name: "Kapat" })).toBeInTheDocument();
    // Yazılmış raporda yeniden önizleme/aktarım yok: yeni dosya seçmek gerekir.
    expect(dialog.getByRole("button", { name: "Önizle" })).toBeDisabled();
    expect(dialog.getByRole("button", { name: "Aktar" })).toBeDisabled();
  });

  it("daha önce aktarılmış dosya belirtilir; tek düzeyli kapsam tekil söylenir", async () => {
    const user = userEvent.setup();
    dersler.previewEnrollmentImport.mockResolvedValue(
      rapor({ already_imported: true, covered_section_count: 1, covered_levels: ["9. Sınıf"] }),
    );
    renderDialog();

    await user.upload(screen.getByLabelText("e-Okul OOK10002R010 raporu (PDF)"), PDF);
    await user.click(screen.getByRole("button", { name: "Önizle" }));
    expect(await screen.findByText(/Bu dosya daha önce aktarılmış/)).toBeInTheDocument();
    expect(screen.getByText(/Rapor 9\. Sınıf düzeyinden 1 şubeyi kapsıyor/)).toBeInTheDocument();
  });

  it("okunamayan rapor gerekçesiyle role=alert basılır; aktarım açılmaz", async () => {
    const user = userEvent.setup();
    dersler.previewEnrollmentImport.mockRejectedValue(
      new ApiError(400, "parse_error", "Dosya PDF değil — e-Okul raporunu PDF olarak kaydedin."),
    );
    renderDialog();

    await user.upload(screen.getByLabelText("e-Okul OOK10002R010 raporu (PDF)"), PDF);
    await user.click(screen.getByRole("button", { name: "Önizle" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Dosya PDF değil — e-Okul raporunu PDF olarak kaydedin.",
    );
    expect(screen.getByRole("button", { name: "Aktar" })).toBeDisabled();
  });
});
