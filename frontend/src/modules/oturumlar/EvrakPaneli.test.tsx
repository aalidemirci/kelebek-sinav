// Evrak paneli testleri (F4): API blob uçları + saveBlob mock'lanır; katalog
// listesi, R6'nın gözetmen ayarına bağlı gizlenmesi, salon filtresi ve dosya
// adı kurulumu (pdf/xlsx/zip) doğrulanır. Ortak kurucular testFixtures.ts'ten.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { ExamSession } from "./api";
import { makeSeating, makeSession } from "./testFixtures";

const sessionApi = vi.hoisted(() => ({
  seating: vi.fn(),
  reportBlob: vi.fn(),
  reportsZipBlob: vi.fn(),
}));
const download = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, examSessionApi: { ...actual.examSessionApi, ...sessionApi } };
});
// Yalnız saveBlob sahtelenir; dosya adını kuran `dosyaAdi` GERÇEK kalır ki
// indirilen adın biçimi de sınansın.
vi.mock("../../lib/download", async (importActual) => {
  const actual = await importActual<typeof import("../../lib/download")>();
  return { ...actual, ...download };
});

import EvrakPaneli from "./EvrakPaneli";

function renderPanel(session: ExamSession) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <EvrakPaneli session={session} />
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("EvrakPaneli", () => {
  it("katalog listelenir; R6 gözetmen ayarı kapalıyken gizli", async () => {
    sessionApi.seating.mockResolvedValue(makeSeating());
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    expect(await screen.findByText("Salon Sınav Evrakı")).toBeInTheDocument();
    expect(screen.getByText("Şube Sınav Duyurusu")).toBeInTheDocument();
    expect(screen.getByText("Sınav İhlal ve Kopya Tutanağı")).toBeInTheDocument();
    expect(screen.getByText("Dağıtım Doğrulama Raporu")).toBeInTheDocument();
    expect(screen.getByText("Toplu Dağıtım Çizelgesi (Excel)")).toBeInTheDocument();
    expect(screen.queryByText(/Gözetmen Görevlendirme/)).not.toBeInTheDocument();
    // 30.08.2026 sadeleştirmesinde kaldırılan belgeler katalogda kalmamalı.
    for (const kalkan of ["Salon Yoklama", "Şube Yoklama", "Kapı Listesi", "Teslim Alma"]) {
      expect(screen.queryByText(new RegExp(kalkan))).not.toBeInTheDocument();
    }
  });

  it("R6 gözetmen ayarı açıkken sözlükteki adıyla listelenir", async () => {
    sessionApi.seating.mockResolvedValue(makeSeating());
    renderPanel(makeSession({ status: "DISTRIBUTED", proctors_enabled: true }));

    expect(await screen.findByText("Gözetmen Görevlendirme Yazısı")).toBeInTheDocument();
  });

  it("panel metinlerinde evrak kodu ve 'seed' geçmez (docs/sozluk.md §2)", async () => {
    sessionApi.seating.mockResolvedValue(makeSeating());
    const { container } = renderPanel(
      makeSession({ status: "DISTRIBUTED", proctors_enabled: true }),
    );

    await screen.findByText("Salon Sınav Evrakı");
    expect(container.textContent).not.toMatch(/\bR(1|4|5|6|7|8|10)\b/);
    expect(container.textContent).not.toMatch(/seed/i);
    expect(screen.getByText(/“Sorular ve Kitapçıklar” sekmesinden/)).toBeInTheDocument();
  });

  it("tek belge indirme: dosya adı belge adı + oturum adı + tarih taşır (Excel → xlsx)", async () => {
    const user = userEvent.setup();
    sessionApi.seating.mockResolvedValue(makeSeating());
    const blob = new Blob(["excel"]);
    sessionApi.reportBlob.mockResolvedValue(blob);
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    const satir = (await screen.findByText("Toplu Dağıtım Çizelgesi (Excel)")).closest("li");
    expect(satir).not.toBeNull();
    await user.click(within(satir as HTMLElement).getByRole("button", { name: "İndir" }));

    await waitFor(() => expect(sessionApi.reportBlob).toHaveBeenCalledWith(5, "r5", undefined));
    // Eski ad `r5_oturum_5.xlsx` idi: kod + kimlik, hangi sınav olduğu belirsiz.
    expect(download.saveBlob).toHaveBeenCalledWith(
      blob,
      "Toplu-Dağıtım-Çizelgesi_2-Ortak-Sınav_15.06.2026.xlsx",
    );
  });

  it("salon filtresi yalnız salon bazlı rapora uygulanır", async () => {
    const user = userEvent.setup();
    sessionApi.seating.mockResolvedValue(makeSeating());
    sessionApi.reportBlob.mockResolvedValue(new Blob(["pdf"]));
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    // Salon seçenekleri seating sorgusundan gelir — önce yüklenmesini bekle.
    await screen.findByRole("option", { name: "D-204" });
    await user.selectOptions(screen.getByLabelText(/Salon filtresi/), "1");

    const r1 = screen.getByText("Salon Sınav Evrakı").closest("li");
    await user.click(within(r1 as HTMLElement).getByRole("button", { name: "İndir" }));
    await waitFor(() => expect(sessionApi.reportBlob).toHaveBeenCalledWith(5, "r1", 1));
    // Salon filtreli indirme salon adını da taşır — tüm salonlarınkiyle karışmaz.
    await waitFor(() =>
      expect(download.saveBlob).toHaveBeenLastCalledWith(
        expect.anything(),
        "Salon-Sınav-Evrakı_D-204_2-Ortak-Sınav_15.06.2026.pdf",
      ),
    );

    const r4 = screen.getByText("Şube Sınav Duyurusu").closest("li");
    await user.click(within(r4 as HTMLElement).getByRole("button", { name: "İndir" }));
    await waitFor(() => expect(sessionApi.reportBlob).toHaveBeenCalledWith(5, "r4", undefined));
    // Salon bazlı olmayan belgenin adına salon girmez.
    await waitFor(() =>
      expect(download.saveBlob).toHaveBeenLastCalledWith(
        expect.anything(),
        "Şube-Sınav-Duyurusu_2-Ortak-Sınav_15.06.2026.pdf",
      ),
    );
  });

  it("tümünü indir ZIP ucuna gider", async () => {
    const user = userEvent.setup();
    sessionApi.seating.mockResolvedValue(makeSeating());
    const blob = new Blob(["zip"]);
    sessionApi.reportsZipBlob.mockResolvedValue(blob);
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    await user.click(await screen.findByRole("button", { name: /Tümünü indir/ }));

    await waitFor(() => expect(sessionApi.reportsZipBlob).toHaveBeenCalledWith(5));
    expect(download.saveBlob).toHaveBeenCalledWith(
      blob,
      "Sınav-Evrakı_2-Ortak-Sınav_15.06.2026.zip",
    );
  });

  it("uç hatasında snackbar gösterilir, indirme yapılmaz", async () => {
    const user = userEvent.setup();
    sessionApi.seating.mockResolvedValue(makeSeating());
    sessionApi.reportsZipBlob.mockRejectedValue(new Error("ağ koptu"));
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    await user.click(await screen.findByRole("button", { name: /Tümünü indir/ }));

    expect(await screen.findByText("Evrak üretilemedi.")).toBeInTheDocument();
    expect(download.saveBlob).not.toHaveBeenCalled();
  });
});
