// Takvim detay sayfası testleri (18.09.2026): tek "Onayla" akışı (taslakta
// submit + approve art arda; eski ONAYA SUNULDU verisinde yalnız approve),
// onaylı takvimi taslağa almanın onay diyaloğu, durum geçişlerinin kendi
// snackbar cümleleri, "bulunamadı"nın YALNIZ 404'te görünmesi ve PDF dosya adı.
// Sekme panelleri bu dosyanın konusu değildir — yer tutucuyla değiştirilir
// (her birinin kendi testi var).

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { makeCalendar } from "./testFixtures";

const calApi = vi.hoisted(() => ({
  get: vi.fn(),
  update: vi.fn(),
  submit: vi.fn(),
  approve: vi.fn(),
  reopen: vi.fn(),
  remove: vi.fn(),
  pdfBlob: vi.fn(),
}));
const indirme = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, examCalendarApi: { ...actual.examCalendarApi, ...calApi } };
});
vi.mock("../../lib/download", async (importActual) => {
  const actual = await importActual<typeof import("../../lib/download")>();
  return { ...actual, saveBlob: indirme.saveBlob };
});
vi.mock("./TakvimHavuzPaneli", () => ({ default: () => <div>HAVUZ PANELİ</div> }));
vi.mock("./TakvimYerlestirmePaneli", () => ({ default: () => <div>YERLEŞTİRME PANELİ</div> }));
vi.mock("./TakvimTakipPaneli", () => ({ default: () => <div>TAKİP PANELİ</div> }));
vi.mock("./TakvimOnizlemePaneli", () => ({ default: () => <div>ÖNİZLEME PANELİ</div> }));
// Bakanlık sınavı bandının kendi testi var (BakanlikSinavlari.test.tsx).
vi.mock("./BakanlikSinavlari", () => ({ default: () => null }));

import TakvimDetayPage from "./TakvimDetayPage";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <ConfirmProvider>
          <MemoryRouter initialEntries={["/takvimler/7"]}>
            <Routes>
              <Route path="/takvimler/:id" element={<TakvimDetayPage />} />
              <Route path="/takvimler" element={<div>TAKVİM LİSTESİ</div>} />
            </Routes>
          </MemoryRouter>
        </ConfirmProvider>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("TakvimDetayPage — onay akışı", () => {
  it("taslakta tek birincil düğme “Onayla”dır; sırayla submit ve approve çağırır", async () => {
    const user = userEvent.setup();
    calApi.get.mockResolvedValue(makeCalendar());
    calApi.submit.mockResolvedValue(makeCalendar({ status: "SUBMITTED" }));
    calApi.approve.mockResolvedValue(makeCalendar({ status: "APPROVED" }));
    renderPage();

    const onayla = await screen.findByRole("button", { name: "Onayla" });
    // Tek kullanıcıda "onaya sun" ritüeli yok; taslakta taslağa alma da yok.
    expect(screen.queryByRole("button", { name: /Onaya sun/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Taslağa al" })).not.toBeInTheDocument();

    await user.click(onayla);

    await waitFor(() => expect(calApi.approve).toHaveBeenCalledWith(7));
    expect(calApi.submit).toHaveBeenCalledWith(7);
    // Backend durum makinesi değişmedi: önce sunum, SONRA onay.
    expect(calApi.submit.mock.invocationCallOrder[0]).toBeLessThan(
      calApi.approve.mock.invocationCallOrder[0],
    );
    expect(await screen.findByText("Takvim onaylandı.")).toBeInTheDocument();
  });

  it("eski veride ONAYA SUNULDU takvimde “Onayla” yalnız approve çağırır", async () => {
    const user = userEvent.setup();
    calApi.get.mockResolvedValue(makeCalendar({ status: "SUBMITTED" }));
    calApi.approve.mockResolvedValue(makeCalendar({ status: "APPROVED" }));
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Onayla" }));

    await waitFor(() => expect(calApi.approve).toHaveBeenCalledWith(7));
    expect(calApi.submit).not.toHaveBeenCalled();
    expect(await screen.findByText("Takvim onaylandı.")).toBeInTheDocument();
  });

  it("sunum geçip onay takılırsa backend'in gerekçesi gösterilir", async () => {
    const user = userEvent.setup();
    calApi.get.mockResolvedValue(makeCalendar());
    calApi.submit.mockResolvedValue(makeCalendar({ status: "SUBMITTED" }));
    calApi.approve.mockRejectedValue(
      new ApiError(400, "validation_error", "Yerleştirilmemiş sınav var."),
    );
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Onayla" }));

    expect(await screen.findByText("Yerleştirilmemiş sınav var.")).toBeInTheDocument();
    expect(screen.queryByText("Takvim onaylandı.")).not.toBeInTheDocument();
  });

  it("onaylı takvimi taslağa almak onay diyaloğundan geçer (onay düşer)", async () => {
    const user = userEvent.setup();
    calApi.get.mockResolvedValue(makeCalendar({ status: "APPROVED" }));
    calApi.reopen.mockResolvedValue(makeCalendar());
    renderPage();

    // Onaylı takvimde yeniden "Onayla" sunulmaz.
    await user.click(await screen.findByRole("button", { name: "Taslağa al" }));
    expect(screen.queryByRole("button", { name: "Onayla" })).not.toBeInTheDocument();

    // Başlık SORU, gövde SONUÇ — ikisi aynı cümle değil (docs/sozluk.md §3).
    const onay = await screen.findByRole("dialog", { name: "Onaylı takvim taslağa alınsın mı?" });
    expect(within(onay).getByText(/Takvimin onayı kalkar/)).toBeInTheDocument();
    expect(within(onay).getByText(/oturumlar etkilenmez/)).toBeInTheDocument();

    // Vazgeçilirse hiçbir şey olmaz.
    await user.click(within(onay).getByRole("button", { name: "Vazgeç" }));
    expect(calApi.reopen).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Taslağa al" }));
    const onay2 = await screen.findByRole("dialog", { name: "Onaylı takvim taslağa alınsın mı?" });
    await user.click(within(onay2).getByRole("button", { name: "Taslağa al" }));

    await waitFor(() => expect(calApi.reopen).toHaveBeenCalledWith(7));
    expect(await screen.findByText("Takvim taslağa alındı.")).toBeInTheDocument();
  });

  it("ONAYA SUNULDU'dan taslağa dönüşte düşecek onay yoktur — diyalog açılmaz", async () => {
    const user = userEvent.setup();
    calApi.get.mockResolvedValue(makeCalendar({ status: "SUBMITTED" }));
    calApi.reopen.mockResolvedValue(makeCalendar());
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Taslağa al" }));

    await waitFor(() => expect(calApi.reopen).toHaveBeenCalledWith(7));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(await screen.findByText("Takvim taslağa alındı.")).toBeInTheDocument();
  });

  it("taslak takvim silme onayında başlık ile gövde ayrı cümlelerdir", async () => {
    const user = userEvent.setup();
    calApi.get.mockResolvedValue(makeCalendar());
    calApi.remove.mockResolvedValue(undefined);
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Sil" }));
    const onay = await screen.findByRole("dialog", { name: "Takvim silinsin mi?" });
    expect(within(onay).getByText(/birlikte silinir/)).toBeInTheDocument();
    await user.click(within(onay).getByRole("button", { name: "Sil" }));

    await waitFor(() => expect(calApi.remove).toHaveBeenCalledWith(7));
    expect(await screen.findByText("TAKVİM LİSTESİ")).toBeInTheDocument();
  });
});

describe("TakvimDetayPage — hata ve indirme", () => {
  it("404'te “Takvim bulunamadı.” ve listeye dönüş düğmesi görünür", async () => {
    const user = userEvent.setup();
    calApi.get.mockRejectedValue(new ApiError(404, "not_found", "Bulunamadı."));
    renderPage();

    expect(await screen.findByText("Takvim bulunamadı.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Takvimlere dön" }));
    expect(await screen.findByText("TAKVİM LİSTESİ")).toBeInTheDocument();
  });

  it("404 dışındaki hatada gerçek mesaj gösterilir — “bulunamadı” DENMEZ", async () => {
    calApi.get.mockRejectedValue(new ApiError(500, "server_error", "Veritabanı kilitli."));
    renderPage();

    const uyari = await screen.findByRole("alert");
    expect(uyari).toHaveTextContent("Takvim yüklenemedi: Veritabanı kilitli.");
    expect(screen.queryByText("Takvim bulunamadı.")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yeniden dene" })).toBeInTheDocument();
  });

  it("PDF takvim adı ve sınav haftası tarihiyle indirilir (kimlik numaralı ad yok)", async () => {
    const user = userEvent.setup();
    const blob = new Blob(["pdf"]);
    calApi.get.mockResolvedValue(makeCalendar());
    calApi.pdfBlob.mockResolvedValue(blob);
    renderPage();

    await user.click(await screen.findByRole("button", { name: "PDF" }));

    await waitFor(() =>
      expect(indirme.saveBlob).toHaveBeenCalledWith(blob, "1-Dönem-1-Sınav-Takvimi_26.10.2026.pdf"),
    );
  });
});

describe("TakvimDetayPage — Bakanlık sınav haftaları önerisi (kısıt değil)", () => {
  const ILAN = {
    start_date: "2026-11-02",
    end_date: "2026-11-13",
    source: "MEB ÖDSHGM 10.09.2026 tarihli yazı",
    official: true,
  };

  it("ilandan farklı taslakta bant görünür; “Bu tarihleri kullan” alanları doldurur", async () => {
    const user = userEvent.setup();
    calApi.get.mockResolvedValue(makeCalendar({ default_window: ILAN }));
    calApi.update.mockResolvedValue(
      makeCalendar({ start_date: "2026-11-02", end_date: "2026-11-13", default_window: ILAN }),
    );
    renderPage();

    // Yüklenirken iskelet de role=status taşır — bant metninden bulunur.
    const metin = await screen.findByText(/Bakanlığın ilan ettiği sınav haftalarından farklı/);
    const bant = metin.closest<HTMLElement>("[role='status']");
    if (bant === null) throw new Error("öneri bandı role=status taşımıyor");
    expect(bant).toHaveTextContent("02.11.2026");
    await user.click(within(bant).getByRole("button", { name: "Tarihleri düzenle" }));

    const dialog = await screen.findByRole("dialog", { name: "Takvim tarihlerini düzenle" });
    await user.click(within(dialog).getByRole("button", { name: "Bu tarihleri kullan" }));
    expect(within(dialog).getByLabelText("Başlangıç tarihi")).toHaveValue("2026-11-02");
    expect(within(dialog).getByLabelText("Bitiş tarihi")).toHaveValue("2026-11-13");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(calApi.update).toHaveBeenCalledWith(7, {
        start_date: "2026-11-02",
        end_date: "2026-11-13",
      }),
    );
  });

  it("tarihler ilanla aynıysa, öneri Yönetmelik kuralıysa ya da takvim onaylıysa bant yok", async () => {
    calApi.get.mockResolvedValue(
      makeCalendar({ start_date: "2026-11-02", end_date: "2026-11-13", default_window: ILAN }),
    );
    const { unmount } = renderPage();
    await screen.findByRole("button", { name: "Onayla" });
    expect(screen.queryByText(/haftalarından farklı/)).not.toBeInTheDocument();
    unmount();

    calApi.get.mockResolvedValue(makeCalendar({ default_window: { ...ILAN, official: false } }));
    const ikinci = renderPage();
    await screen.findByRole("button", { name: "Onayla" });
    expect(screen.queryByText(/haftalarından farklı/)).not.toBeInTheDocument();
    ikinci.unmount();

    calApi.get.mockResolvedValue(makeCalendar({ status: "APPROVED", default_window: ILAN }));
    renderPage();
    await screen.findByRole("button", { name: "Taslağa al" });
    expect(screen.queryByText(/haftalarından farklı/)).not.toBeInTheDocument();
  });
});
