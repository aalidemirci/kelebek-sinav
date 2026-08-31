// "Başka oturumdan kopyala" diyaloğu testleri (Ö5).
// Sabitlenen: kaynak oturum + iki onay kutusu gövdeye doğru geçer; atlananlar
// SESSİZ düşmez, kullanıcıya listelenir.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { makeSession } from "./testFixtures";

const sessionApi = vi.hoisted(() => ({ list: vi.fn(), copyPlan: vi.fn() }));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, examSessionApi: { ...actual.examSessionApi, ...sessionApi } };
});

import OturumKopyalaDialog from "./OturumKopyalaDialog";

function renderDialog() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <OturumKopyalaDialog sessionId={7} onClose={() => {}} onCopied={() => {}} />
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("OturumKopyalaDialog", () => {
  it("kaynak seçilip kopyalanır; hedef oturum listede görünmez", async () => {
    const user = userEvent.setup();
    sessionApi.list.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [makeSession({ id: 7, name: "Hedef" }), makeSession({ id: 9, name: "Kaynak" })],
    });
    sessionApi.copyPlan.mockResolvedValue({
      session: makeSession({ id: 7 }),
      report: {
        courses_created: ["Coğrafya — 9. Sınıf"],
        courses_skipped: [],
        rooms_created: ["D-101"],
        rooms_skipped: ["D-102 (pasif salon)"],
        warnings: [],
      },
    });
    renderDialog();

    const secici = await screen.findByLabelText("Kaynak oturum");
    // Hedef oturum kendi listesinde OLMAMALI (kendinden kopyalanamaz).
    expect(secici).not.toHaveTextContent("Hedef");
    await user.selectOptions(secici, "9");
    await user.click(screen.getByRole("button", { name: /Kopyala/ }));

    await waitFor(() =>
      expect(sessionApi.copyPlan).toHaveBeenCalledWith(7, {
        source_id: 9,
        courses: true,
        rooms: true,
      }),
    );
    // Atlananlar kullanıcıya gösterilir.
    expect(await screen.findByText(/D-102 \(pasif salon\)/)).toBeInTheDocument();
  });

  it("yalnız salon kopyalanabilir", async () => {
    const user = userEvent.setup();
    sessionApi.list.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [makeSession({ id: 9, name: "Kaynak" })],
    });
    sessionApi.copyPlan.mockResolvedValue({
      session: makeSession({ id: 7 }),
      report: {
        courses_created: [],
        courses_skipped: [],
        rooms_created: ["D-101"],
        rooms_skipped: [],
        warnings: [],
      },
    });
    renderDialog();

    await user.selectOptions(await screen.findByLabelText("Kaynak oturum"), "9");
    await user.click(screen.getByRole("checkbox", { name: /Dersler ve katılacak şubeler/ }));
    await user.click(screen.getByRole("button", { name: /Kopyala/ }));

    await waitFor(() =>
      expect(sessionApi.copyPlan).toHaveBeenCalledWith(7, {
        source_id: 9,
        courses: false,
        rooms: true,
      }),
    );
  });
});
