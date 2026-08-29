// Oturum detayı testleri (F3-F7): TASLAK'ta sihirbaz; sonrasında sekmeler
// (Yerleşim + Gözetmenler + Sorular + Evrak + koşullu Yoklama) +
// yaşam döngüsü eylemleri. Paneller ayrı dosyalarda paralel geliştirilir →
// vi.mock ile yerine geçirilir; test panel içeriğine değil props sözleşmesine
// (session) bakar. Ortak kurucu ./testFixtures'tan (test dosyaları birbirinden
// import ETMEZ — OYS Tur 232).

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { ExamSession } from "./api";
import { makeSession } from "./testFixtures";

const exam = vi.hoisted(() => ({
  get: vi.fn(),
  approve: vi.fn(),
  reopen: vi.fn(),
  archive: vi.fn(),
  remove: vi.fn(),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, examSessionApi: { ...actual.examSessionApi, ...exam } };
});
vi.mock("./SinavSihirbazi", () => ({
  default: ({ session }: { session: ExamSession }) => <div>SİHİRBAZ PANELİ {session.id}</div>,
}));
vi.mock("./YerlesimPaneli", () => ({
  default: ({ session }: { session: ExamSession }) => <div>YERLEŞİM PANELİ {session.id}</div>,
}));
vi.mock("./YoklamaPaneli", () => ({
  default: ({ session }: { session: ExamSession }) => <div>YOKLAMA PANELİ {session.id}</div>,
}));
vi.mock("./EvrakPaneli", () => ({
  default: ({ session }: { session: ExamSession }) => <div>EVRAK PANELİ {session.id}</div>,
}));
vi.mock("./SorularPaneli", () => ({
  default: ({ session }: { session: ExamSession }) => <div>SORULAR PANELİ {session.id}</div>,
}));
vi.mock("./GozetmenlerPaneli", () => ({
  default: ({ session }: { session: ExamSession }) => <div>GÖZETMEN PANELİ {session.id}</div>,
}));

import OturumDetayPage from "./OturumDetayPage";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <ConfirmProvider>
          <MemoryRouter initialEntries={["/oturumlar/5"]}>
            <Routes>
              <Route path="/oturumlar/:id" element={<OturumDetayPage />} />
              <Route path="/oturumlar" element={<div>OTURUM LİSTESİ</div>} />
            </Routes>
          </MemoryRouter>
        </ConfirmProvider>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("OturumDetayPage", () => {
  it("TASLAK oturumda sihirbaz açılır; sekme yok, 'Taslağı sil' var, 'Onayla' yok", async () => {
    exam.get.mockResolvedValue(makeSession());
    renderPage();

    expect(await screen.findByText("SİHİRBAZ PANELİ 5")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "2. Ortak Sınav" })).toBeInTheDocument();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Taslağı sil/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Onayla" })).not.toBeInTheDocument();
  });

  it("taslak silme onaylanınca remove çağrılır ve listeye dönülür", async () => {
    const user = userEvent.setup();
    exam.get.mockResolvedValue(makeSession());
    exam.remove.mockResolvedValue(undefined);
    renderPage();

    await user.click(await screen.findByRole("button", { name: /Taslağı sil/ }));
    const dialog = await screen.findByRole("dialog", { name: "Taslak silinsin mi?" });
    await user.click(within(dialog).getByRole("button", { name: "Sil" }));

    await waitFor(() => expect(exam.remove).toHaveBeenCalledWith(5));
    expect(await screen.findByText("OTURUM LİSTESİ")).toBeInTheDocument();
  });

  it("DAĞITILDI: Yerleşim + Gözetmenler + Sorular + Evrak sekmeleri (Yoklama yok); Onayla approve çağırır", async () => {
    const user = userEvent.setup();
    exam.get.mockResolvedValue(makeSession({ status: "DISTRIBUTED" }));
    exam.approve.mockResolvedValue(makeSession({ status: "APPROVED" }));
    renderPage();

    expect(await screen.findByText("YERLEŞİM PANELİ 5")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Yerleşim/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Sorular ve Kitapçıklar/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Evrak/ })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /Yoklama/ })).not.toBeInTheDocument();
    // Gözetmenler sekmesi F7 ile geldi (koşulsuz — kapalıysa panel mesajı).
    expect(screen.getByRole("tab", { name: /Gözetmenler/ })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Onayla" }));
    await waitFor(() => expect(exam.approve).toHaveBeenCalledWith(5));
    expect(await screen.findByText("Oturum onaylandı — yerleşim kilitlendi.")).toBeInTheDocument();
  });

  it("DAĞITILDI: Sorular ve Evrak sekmeleri panellerini açar", async () => {
    const user = userEvent.setup();
    exam.get.mockResolvedValue(makeSession({ status: "DISTRIBUTED" }));
    renderPage();

    await user.click(await screen.findByRole("tab", { name: /Gözetmenler/ }));
    expect(await screen.findByText("GÖZETMEN PANELİ 5")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /Sorular ve Kitapçıklar/ }));
    expect(await screen.findByText("SORULAR PANELİ 5")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /Evrak/ }));
    expect(await screen.findByText("EVRAK PANELİ 5")).toBeInTheDocument();
  });

  it("ARŞİV: Evrak sekmesi görünür kalır (yeniden basım açık)", async () => {
    exam.get.mockResolvedValue(makeSession({ status: "ARCHIVED" }));
    renderPage();

    expect(await screen.findByRole("tab", { name: /Evrak/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Yoklama/ })).toBeInTheDocument();
  });

  it("ONAYLI: Yoklama sekmesi açılır, panel oturumu alır; 'Yeniden aç' reopen çağırır", async () => {
    const user = userEvent.setup();
    exam.get.mockResolvedValue(makeSession({ status: "APPROVED" }));
    exam.reopen.mockResolvedValue(makeSession({ status: "DISTRIBUTED" }));
    renderPage();

    expect(await screen.findByText("YERLEŞİM PANELİ 5")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /Yoklama/ }));
    expect(await screen.findByText("YOKLAMA PANELİ 5")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Yeniden aç/ }));
    await waitFor(() => expect(exam.reopen).toHaveBeenCalledWith(5));
    expect(await screen.findByText(/Onay geri alındı/)).toBeInTheDocument();
  });

  it("ONAYLI: arşivleme onay diyaloğundan geçer ve archive çağrılır", async () => {
    const user = userEvent.setup();
    exam.get.mockResolvedValue(makeSession({ status: "APPROVED" }));
    exam.archive.mockResolvedValue(makeSession({ status: "ARCHIVED" }));
    renderPage();

    await user.click(await screen.findByRole("button", { name: /Arşivle/ }));
    // Sayfadaki buton ile onay butonu aynı adı taşır → diyalog içinde ara.
    const dialog = await screen.findByRole("dialog", { name: "Arşivlensin mi?" });
    await user.click(within(dialog).getByRole("button", { name: "Arşivle" }));

    await waitFor(() => expect(exam.archive).toHaveBeenCalledWith(5));
    expect(await screen.findByText(/Oturum arşivlendi/)).toBeInTheDocument();
  });
});
