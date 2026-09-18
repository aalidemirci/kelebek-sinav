// Önizleme paneli testleri (F6 eki): düzenlenebilir DİPNOT alanı ve imza
// bloğuna girecek zümrelerin seçimi. Onaylı takvimde ikisi de kilitlidir
// (backend `_ensure_draft` ile aynı kural — FE yalnız sunar).

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { makeCalendar } from "./testFixtures";

const calApi = vi.hoisted(() => ({
  update: vi.fn(),
  defaultFootnote: vi.fn(),
  defaultDescription: vi.fn(),
  pdfBlob: vi.fn(),
}));

const okulApiMock = vi.hoisted(() => ({ listSubjectDepartments: vi.fn() }));
const indirme = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("../../lib/download", async (importActual) => {
  const actual = await importActual<typeof import("../../lib/download")>();
  return { ...actual, saveBlob: indirme.saveBlob };
});

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, examCalendarApi: { ...actual.examCalendarApi, ...calApi } };
});

vi.mock("../okul/api", async (importActual) => {
  const actual = await importActual<typeof import("../okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...okulApiMock } };
});

import type { ExamCalendar } from "./api";
import TakvimOnizlemePaneli from "./TakvimOnizlemePaneli";

function renderPanel(calendar: ExamCalendar, editable = true) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <MemoryRouter>
          <TakvimOnizlemePaneli calendar={calendar} editable={editable} onSaved={() => {}} />
        </MemoryRouter>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("TakvimOnizlemePaneli", () => {
  it("dipnot düzenlenip kaydedilir", async () => {
    const user = userEvent.setup();
    okulApiMock.listSubjectDepartments.mockResolvedValue([]);
    calApi.update.mockResolvedValue(makeCalendar());
    renderPanel(makeCalendar());

    const alan = screen.getByLabelText("Takvim dipnotu");
    await user.clear(alan);
    await user.type(alan, "Mazeret sınavları 12 Kasım'da.");
    await user.click(screen.getByRole("button", { name: /Dipnotu kaydet/ }));

    await waitFor(() =>
      expect(calApi.update).toHaveBeenCalledWith(7, {
        footnote_text: "Mazeret sınavları 12 Kasım'da.",
      }),
    );
  });

  it("varsayılan dipnota dönülür (kaydetmeden metni yükler)", async () => {
    const user = userEvent.setup();
    okulApiMock.listSubjectDepartments.mockResolvedValue([]);
    calApi.defaultFootnote.mockResolvedValue({ text: "Varsayılan dipnot metni." });
    renderPanel(makeCalendar());

    await user.click(screen.getByRole("button", { name: /Varsayılan dipnota dön/ }));
    await waitFor(() =>
      expect(screen.getByLabelText("Takvim dipnotu")).toHaveValue("Varsayılan dipnot metni."),
    );
    expect(calApi.update).not.toHaveBeenCalled();
  });

  it("imza zümresi işaretlenince takvime kaydedilir", async () => {
    const user = userEvent.setup();
    okulApiMock.listSubjectDepartments.mockResolvedValue([
      { id: 3, name: "Sosyal Bilimler", head: 8, head_name: "Ayşe ÇELİK", is_board_member: true },
      { id: 4, name: "Matematik", head: null, head_name: "", is_board_member: true },
    ]);
    calApi.update.mockResolvedValue(makeCalendar({ signatory_departments: [3] }));
    renderPanel(makeCalendar());

    const kutu = await screen.findByRole("checkbox", { name: /Sosyal Bilimler/ });
    await user.click(kutu);

    await waitFor(() =>
      expect(calApi.update).toHaveBeenCalledWith(7, { signatory_departments: [3] }),
    );
    // Başkan adı seçenekte görünür (şifreli alandan backend çözer).
    expect(screen.getByText(/Ayşe ÇELİK/)).toBeInTheDocument();
  });

  it("onaylı takvimde dipnot ve zümre seçimi kilitli", async () => {
    okulApiMock.listSubjectDepartments.mockResolvedValue([
      { id: 3, name: "Sosyal Bilimler", head: null, head_name: "", is_board_member: true },
    ]);
    renderPanel(makeCalendar({ status: "APPROVED" }), false);

    expect(screen.getByLabelText("Takvim dipnotu")).toHaveAttribute("readonly");
    expect(screen.queryByRole("button", { name: /Dipnotu kaydet/ })).not.toBeInTheDocument();
    expect(await screen.findByRole("checkbox", { name: /Sosyal Bilimler/ })).toBeDisabled();
  });

  it("onay bilgisi onaylı takvimde damgayı İstanbul saatiyle gösterir", async () => {
    okulApiMock.listSubjectDepartments.mockResolvedValue([]);
    renderPanel(
      makeCalendar({
        status: "APPROVED",
        approved_by_name: "Ayşe ÇELİK",
        // 21:30 UTC = ertesi gün 00:30 İstanbul (lib/format saat dilimi sabit).
        approved_at: "2026-10-20T21:30:00Z",
      }),
      false,
    );

    expect(screen.getByText("Ayşe ÇELİK")).toBeInTheDocument();
    expect(screen.getByText("21.10.2026 00:30")).toBeInTheDocument();
    // Tek "Onayla" akışında ayrı "Onaya sunuldu" satırı yoktur.
    expect(screen.queryByText("Onaya sunuldu")).not.toBeInTheDocument();
  });

  it("taslağa alınmış takvimde eski onay damgası gösterilmez", async () => {
    okulApiMock.listSubjectDepartments.mockResolvedValue([]);
    // Backend damgayı tarihçe olarak saklar; ekran taslağı onaylı göstermemeli.
    renderPanel(
      makeCalendar({
        status: "DRAFT",
        approved_by_name: "Ayşe ÇELİK",
        approved_at: "2026-10-20T21:30:00Z",
      }),
    );

    expect(screen.queryByText("Ayşe ÇELİK")).not.toBeInTheDocument();
    expect(screen.queryByText("21.10.2026 00:30")).not.toBeInTheDocument();
  });

  it("açıklama yardım metni kısaltma kullanmaz ve “resmî” yazar", async () => {
    okulApiMock.listSubjectDepartments.mockResolvedValue([]);
    renderPanel(makeCalendar());

    expect(screen.getByText(/resmî sınav takvimi PDF'inin/)).toBeInTheDocument();
    expect(screen.getByText(/konu soru\s+dağılım tablosu/)).toBeInTheDocument();
    expect(screen.queryByText(/KSD/)).not.toBeInTheDocument();
  });

  it("PDF takvim adı ve tarihle indirilir", async () => {
    const user = userEvent.setup();
    const blob = new Blob(["pdf"]);
    okulApiMock.listSubjectDepartments.mockResolvedValue([]);
    calApi.pdfBlob.mockResolvedValue(blob);
    renderPanel(makeCalendar({ name: "Kasım Ortak Sınavları" }));

    await user.click(screen.getByRole("button", { name: "PDF indir" }));

    // Takvim adı belge adını taşımıyorsa "Sınav Takvimi" öne eklenir.
    await waitFor(() =>
      expect(indirme.saveBlob).toHaveBeenCalledWith(
        blob,
        "Sınav-Takvimi_Kasım-Ortak-Sınavları_26.10.2026.pdf",
      ),
    );
  });
});
