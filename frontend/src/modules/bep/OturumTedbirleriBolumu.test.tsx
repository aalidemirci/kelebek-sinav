// Yerleştirme Kuralları → "Kalıcı sınav tedbirleri" bölümü (07.10.2026): oturuma giren
// tedbirli öğrenciler, oturum kuralının tedbiri ezdiği satırın rozeti ve idare özeti
// düğmesi. Tedbirli öğrenci yoksa bölüm hiç çizilmez. KVKK: veriler uydurmadır.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { SessionAccommodation } from "./api";

const iep = vi.hoisted(() => ({ session: vi.fn() }));
const bireysel = vi.hoisted(() => ({
  summaryBlob: vi.fn(() => Promise.resolve(new Blob(["%PDF"]))),
}));
const indirme = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return {
    ...actual,
    iepApi: { ...actual.iepApi, ...iep },
    individualQuestionApi: { ...actual.individualQuestionApi, ...bireysel },
  };
});
vi.mock("../../lib/download", async (importActual) => {
  const actual = await importActual<typeof import("../../lib/download")>();
  return { ...actual, saveBlob: indirme.saveBlob };
});

import OturumTedbirleriBolumu from "./OturumTedbirleriBolumu";

const SATIR: SessionAccommodation = {
  student_id: 31,
  student_number: "512",
  full_name: "Deniz Deneme",
  class_label: "9/B",
  reason_label: "Engel durumu",
  measures: ["Ayrı salon (Rehberlik)", "Ek süre 20 dk"],
  overridden: false,
  placement_applied: true,
  room_name: "Rehberlik",
  seat_no: 1,
};

const OTURUM = { id: 4, name: "1. Ortak Sınav", exam_date: "2026-11-16" };

function renderBolum() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <MemoryRouter>
          <OturumTedbirleriBolumu session={OTURUM} />
        </MemoryRouter>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("OturumTedbirleriBolumu", () => {
  it("tedbirli öğrenciyi yeri ve tedbirleriyle gösterir; idare özeti indirilir", async () => {
    const user = userEvent.setup();
    iep.session.mockResolvedValue({
      rows: [SATIR, { ...SATIR, student_id: 32, student_number: "513", overridden: true }],
    });
    renderBolum();

    expect(await screen.findByRole("heading", { name: "Kalıcı sınav tedbirleri" })).toBeVisible();
    expect(screen.getAllByText("Ayrı salon (Rehberlik) · Ek süre 20 dk")).toHaveLength(2);
    expect(screen.getAllByText("Rehberlik · koltuk 1")).toHaveLength(2);
    expect(screen.getByText("bu oturumda kural geçerli")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Kişiler → BEP ve tedbirler" })).toHaveAttribute(
      "href",
      "/kisiler?tab=bep",
    );

    await user.click(screen.getByRole("button", { name: "İdare özeti (PDF)" }));
    await waitFor(() => expect(bireysel.summaryBlob).toHaveBeenCalledWith(4));
    expect(indirme.saveBlob).toHaveBeenCalledWith(
      expect.any(Blob),
      "Sınav-Tedbirleri-ve-BEP-İdare-Özeti_1-Ortak-Sınav_16.11.2026.pdf",
    );
  });

  it("dağıtılmamış oturumda yer 'henüz dağıtılmadı' der", async () => {
    iep.session.mockResolvedValue({
      rows: [{ ...SATIR, room_name: "", seat_no: null, placement_applied: null }],
    });
    renderBolum();

    expect(await screen.findByText("henüz dağıtılmadı")).toBeInTheDocument();
    expect(screen.queryByText(/uygulanmadı/)).not.toBeInTheDocument();
  });

  it("tedbir dağıtımdan sonra girildiyse yeniden dağıtılması gerektiğini söyler", async () => {
    iep.session.mockResolvedValue({ rows: [{ ...SATIR, placement_applied: false }] });
    renderBolum();

    expect(
      await screen.findByText("yer tedbiri bu dağıtımda uygulanmadı — oturumu yeniden dağıtın"),
    ).toBeInTheDocument();
  });

  it("tedbirli öğrenci yoksa bölüm çizilmez", async () => {
    iep.session.mockResolvedValue({ rows: [] });
    renderBolum();

    await waitFor(() => expect(iep.session).toHaveBeenCalledWith(4));
    expect(
      screen.queryByRole("heading", { name: "Kalıcı sınav tedbirleri" }),
    ).not.toBeInTheDocument();
  });

  it("liste okunamazsa sessiz kalınmaz", async () => {
    iep.session.mockRejectedValue(new ApiError(500, "server_error", "Kasa kilitli."));
    renderBolum();

    expect(await screen.findByRole("alert")).toHaveTextContent("Kasa kilitli.");
  });
});
