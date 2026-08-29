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
vi.mock("../../lib/download", () => download);

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

    expect(await screen.findByText("Salon Oturma Planı (kroki)")).toBeInTheDocument();
    expect(screen.getByText("Dağıtım Doğrulama Raporu")).toBeInTheDocument();
    expect(screen.getByText("Toplu Dağıtım Çizelgesi (Excel)")).toBeInTheDocument();
    expect(screen.queryByText(/Gözetmen Görevlendirme/)).not.toBeInTheDocument();
  });

  it("R6 gözetmen ayarı açıkken listelenir", async () => {
    sessionApi.seating.mockResolvedValue(makeSeating());
    renderPanel(makeSession({ status: "DISTRIBUTED", proctors_enabled: true }));

    expect(await screen.findByText(/Gözetmen Görevlendirme/)).toBeInTheDocument();
  });

  it("tek rapor indirme: blob uca gider, dosya adı kodla kurulur (r5 → xlsx)", async () => {
    const user = userEvent.setup();
    sessionApi.seating.mockResolvedValue(makeSeating());
    const blob = new Blob(["excel"]);
    sessionApi.reportBlob.mockResolvedValue(blob);
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    const satir = (await screen.findByText("Toplu Dağıtım Çizelgesi (Excel)")).closest("li");
    expect(satir).not.toBeNull();
    await user.click(within(satir as HTMLElement).getByRole("button", { name: "İndir" }));

    await waitFor(() => expect(sessionApi.reportBlob).toHaveBeenCalledWith(5, "r5", undefined));
    expect(download.saveBlob).toHaveBeenCalledWith(blob, "r5_oturum_5.xlsx");
  });

  it("salon filtresi yalnız salon bazlı rapora uygulanır", async () => {
    const user = userEvent.setup();
    sessionApi.seating.mockResolvedValue(makeSeating());
    sessionApi.reportBlob.mockResolvedValue(new Blob(["pdf"]));
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    // Salon seçenekleri seating sorgusundan gelir — önce yüklenmesini bekle.
    await screen.findByRole("option", { name: "D-204" });
    await user.selectOptions(screen.getByLabelText(/Salon filtresi/), "1");

    const r1 = screen.getByText("Salon Oturma Planı (kroki)").closest("li");
    await user.click(within(r1 as HTMLElement).getByRole("button", { name: "İndir" }));
    await waitFor(() => expect(sessionApi.reportBlob).toHaveBeenCalledWith(5, "r1", 1));

    const r4 = screen.getByText("Şube Duyuru Listesi").closest("li");
    await user.click(within(r4 as HTMLElement).getByRole("button", { name: "İndir" }));
    await waitFor(() => expect(sessionApi.reportBlob).toHaveBeenCalledWith(5, "r4", undefined));
  });

  it("tümünü indir ZIP ucuna gider", async () => {
    const user = userEvent.setup();
    sessionApi.seating.mockResolvedValue(makeSeating());
    const blob = new Blob(["zip"]);
    sessionApi.reportsZipBlob.mockResolvedValue(blob);
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    await user.click(await screen.findByRole("button", { name: /Tümünü indir/ }));

    await waitFor(() => expect(sessionApi.reportsZipBlob).toHaveBeenCalledWith(5));
    expect(download.saveBlob).toHaveBeenCalledWith(blob, "sinav_evraki_oturum_5.zip");
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
