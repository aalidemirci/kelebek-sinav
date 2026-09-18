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

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { ExamSession } from "./api";
import { makeReport, makeSession } from "./testFixtures";

const exam = vi.hoisted(() => ({
  get: vi.fn(),
  approve: vi.fn(),
  reopen: vi.fn(),
  archive: vi.fn(),
  revertToDraft: vi.fn(),
  remove: vi.fn(),
  distribute: vi.fn(),
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

  it("yüklenirken iskelet gösterir; uç hatasında role=alert ve listeye dönüş yolu", async () => {
    exam.get.mockRejectedValue(new Error("ağ koptu"));
    renderPage();

    // İlk çizimde sorgu beklemede → iskelet (düz "yükleniyor" metni değil).
    expect(screen.getByRole("status")).toHaveTextContent("Yükleniyor…");
    expect(await screen.findByRole("alert")).toHaveTextContent(/Oturum yüklenemedi/);
    expect(screen.getByRole("button", { name: "Oturum listesine dön" })).toBeInTheDocument();
  });

  it("DAĞITILDI: Yerleşim + Gözetmenler + Sorular + Evrak sekmeleri (Yoklama yok)", async () => {
    exam.get.mockResolvedValue(makeSession({ status: "DISTRIBUTED" }));
    renderPage();

    expect(await screen.findByText("YERLEŞİM PANELİ 5")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Yerleşim/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Sorular ve Kitapçıklar/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Evrak/ })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /Yoklama/ })).not.toBeInTheDocument();
    // Gözetmenler sekmesi F7 ile geldi (koşulsuz — kapalıysa panel mesajı).
    expect(screen.getByRole("tab", { name: /Gözetmenler/ })).toBeInTheDocument();
    // Üç eylem: Taslağa al · Yeniden dağıt · Onayla.
    expect(screen.getByRole("button", { name: "Taslağa al" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yeniden dağıt" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Onayla" })).toBeInTheDocument();
  });

  it("DAĞITILDI: 'Onayla' diyalogdan geçer; ad boşsa boş gönderilir (backend okul müdürünü yazar)", async () => {
    const user = userEvent.setup();
    exam.get.mockResolvedValue(makeSession({ status: "DISTRIBUTED" }));
    exam.approve.mockResolvedValue(makeSession({ status: "APPROVED" }));
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Onayla" }));
    // Tek tıkla onay YOK — önce sonuç söylenir (kilit + ihlalde ret).
    expect(exam.approve).not.toHaveBeenCalled();
    const dialog = await screen.findByRole("dialog", { name: "Oturum onaylansın mı?" });
    expect(
      within(dialog).getByText(
        "Onay yerleşimi kilitler; yerleşimde kural ihlali varsa reddedilir.",
      ),
    ).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Onayla" }));
    await waitFor(() => expect(exam.approve).toHaveBeenCalledWith(5, { approved_by_name: "" }));
    expect(await screen.findByText("Oturum onaylandı — yerleşim kilitlendi.")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.queryByRole("dialog", { name: "Oturum onaylansın mı?" }),
      ).not.toBeInTheDocument(),
    );
  });

  it("DAĞITILDI: onaylayan adı girilirse kırpılarak approved_by_name olarak gider", async () => {
    const user = userEvent.setup();
    exam.get.mockResolvedValue(makeSession({ status: "DISTRIBUTED" }));
    exam.approve.mockResolvedValue(makeSession({ status: "APPROVED" }));
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Onayla" }));
    const dialog = await screen.findByRole("dialog", { name: "Oturum onaylansın mı?" });
    // KVKK: ad uydurmadır.
    await user.type(
      within(dialog).getByLabelText("Onaylayan (boş bırakılırsa okul müdürü)"),
      " Zeynep Arslan ",
    );
    await user.click(within(dialog).getByRole("button", { name: "Onayla" }));

    await waitFor(() =>
      expect(exam.approve).toHaveBeenCalledWith(5, { approved_by_name: "Zeynep Arslan" }),
    );
  });

  it("DAĞITILDI: onay reddedilirse gerekçe gösterilir ve diyalog açık kalır", async () => {
    const user = userEvent.setup();
    exam.get.mockResolvedValue(makeSession({ status: "DISTRIBUTED" }));
    exam.approve.mockRejectedValue(
      new ApiError(400, "invalid", "Onay reddedildi: yerleşimde 2 kural ihlali var."),
    );
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Onayla" }));
    const dialog = await screen.findByRole("dialog", { name: "Oturum onaylansın mı?" });
    await user.click(within(dialog).getByRole("button", { name: "Onayla" }));

    expect(
      await screen.findByText("Onay reddedildi: yerleşimde 2 kural ihlali var."),
    ).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "Oturum onaylansın mı?" })).toBeInTheDocument();
  });

  it("DAĞITILDI: 'Yeniden dağıt' sonuçları uyarır, numara + katı dağıtımı gönderir, uyarıları gösterir", async () => {
    const user = userEvent.setup();
    exam.get.mockResolvedValue(makeSession({ status: "DISTRIBUTED" }));
    exam.distribute.mockResolvedValue({
      status: "DISTRIBUTED",
      seed: 77,
      checkerboard: true,
      placed: 120,
      warnings: ["Gözetmen görevlendirmeleri yeni dağıtım nedeniyle sıfırlandı; yeniden atayın."],
      report: makeReport(),
    });
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Yeniden dağıt" }));
    const dialog = await screen.findByRole("dialog", { name: "Yeniden dağıtılsın mı?" });
    expect(
      within(dialog).getByText(
        /Elle yapılan koltuk takasları ve gözetmen görevlendirmeleri sıfırlanır\./,
      ),
    ).toBeInTheDocument();
    expect(exam.distribute).not.toHaveBeenCalled();

    await user.type(
      within(dialog).getByLabelText("Dağıtım numarası (boş bırakılırsa yeni rastgele)"),
      "77",
    );
    await user.click(within(dialog).getByRole("checkbox", { name: /Katı dağıtım/ }));
    const ilkGetSayisi = exam.get.mock.calls.length;
    await user.click(within(dialog).getByRole("button", { name: "Yeniden dağıt" }));

    await waitFor(() =>
      expect(exam.distribute).toHaveBeenCalledWith(5, { seed: 77, strict: true }),
    );
    // Sonuç + backend uyarıları diyalogda kalır (snackbar'da akıp gitmez).
    const sonuc = await screen.findByRole("dialog", { name: "Yeniden dağıtım sonucu" });
    expect(within(sonuc).getByText(/120 öğrenci yerleşti/)).toBeInTheDocument();
    expect(within(sonuc).getByText("Kural ihlali yok — oturum onaylanabilir.")).toBeInTheDocument();
    expect(within(sonuc).getByText(/Gözetmen görevlendirmeleri yeni dağıtım/)).toBeInTheDocument();
    // Oturum sorgusu tazelenir.
    await waitFor(() => expect(exam.get.mock.calls.length).toBeGreaterThan(ilkGetSayisi));

    await user.click(within(sonuc).getByRole("button", { name: "Kapat" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("DAĞITILDI: yeniden dağıtım ihlalli dönerse sonuç 'onaylanamaz' der", async () => {
    const user = userEvent.setup();
    exam.get.mockResolvedValue(makeSession({ status: "DISTRIBUTED" }));
    exam.distribute.mockResolvedValue({
      status: "DISTRIBUTED",
      seed: 9,
      checkerboard: false,
      placed: 40,
      warnings: [],
      report: makeReport({ is_valid: false, hard_violations: ["a", "b"] }),
    });
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Yeniden dağıt" }));
    const dialog = await screen.findByRole("dialog", { name: "Yeniden dağıtılsın mı?" });
    await user.click(within(dialog).getByRole("button", { name: "Yeniden dağıt" }));

    // Numara boş → gövdede seed yok (backend yeni rastgele numara seçer).
    await waitFor(() =>
      expect(exam.distribute).toHaveBeenCalledWith(5, { seed: undefined, strict: false }),
    );
    const sonuc = await screen.findByRole("dialog", { name: "Yeniden dağıtım sonucu" });
    expect(within(sonuc).getByRole("alert")).toHaveTextContent(/2 kural ihlali var — onaylanamaz/);
  });

  it("'Kendi dersliğinde' düzeninde yeniden dağıtım numara/katı dağıtım sormaz, sonuçta numara yazmaz", async () => {
    const user = userEvent.setup();
    exam.get.mockResolvedValue(
      makeSession({ status: "DISTRIBUTED", layout_mode: "HOME_CLASSROOM" }),
    );
    // Klasik düzende backend numarayı hep 0 döndürür (karıştırma yok).
    exam.distribute.mockResolvedValue({
      status: "DISTRIBUTED",
      seed: 0,
      checkerboard: false,
      placed: 64,
      warnings: [],
      report: makeReport(),
    });
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Yeniden dağıt" }));
    const dialog = await screen.findByRole("dialog", { name: "Yeniden dağıtılsın mı?" });
    expect(within(dialog).queryByLabelText(/Dağıtım numarası/)).not.toBeInTheDocument();
    expect(within(dialog).queryByRole("checkbox")).not.toBeInTheDocument();
    expect(
      within(dialog).getByText(/okul numarası sırasıyla yeniden yerleştirilir/),
    ).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Yeniden dağıt" }));
    const sonuc = await screen.findByRole("dialog", { name: "Yeniden dağıtım sonucu" });
    expect(within(sonuc).getByText(/64 öğrenci yerleşti/)).toBeInTheDocument();
    expect(within(sonuc).queryByText(/Dağıtım numarası/)).not.toBeInTheDocument();
    expect(await screen.findByText("Yeniden dağıtıldı: 64 öğrenci yerleşti.")).toBeInTheDocument();
  });

  it("'Yeniden dağıt' yalnız DAĞITILDI durumunda vardır", async () => {
    exam.get.mockResolvedValue(makeSession({ status: "APPROVED" }));
    renderPage();

    expect(await screen.findByText("YERLEŞİM PANELİ 5")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Yeniden dağıt" })).not.toBeInTheDocument();
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

  it("DAĞITILDI: 'Taslağa al' onay diyaloğundan geçer ve revertToDraft çağrılır", async () => {
    const user = userEvent.setup();
    exam.get.mockResolvedValue(makeSession({ status: "DISTRIBUTED" }));
    exam.revertToDraft.mockResolvedValue(makeSession({ status: "DRAFT" }));
    renderPage();

    await user.click(await screen.findByRole("button", { name: /Taslağa al/ }));
    // Sayfadaki buton ile onay butonu aynı adı taşır → diyalog içinde ara.
    const dialog = await screen.findByRole("dialog", { name: "Taslağa alınsın mı?" });
    expect(within(dialog).getByText(/soru dosyaları korunur/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Taslağa al" }));

    await waitFor(() => expect(exam.revertToDraft).toHaveBeenCalledWith(5));
    expect(await screen.findByText(/Oturum taslağa alındı/)).toBeInTheDocument();
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
