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
});
