// Gözetmenler paneli testleri (F7): kapalı modül mesajı, salon başına
// tıkla-ata akışı (Autocomplete), uygun-olmayan adayın seçilememesi,
// tebellüğ işleme ve muafiyet ekleme. Oto-öneri düğmesi OLMAMALI (U2/TB4).

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { ExamSession, ProctorAssignmentRow, ProctorCandidate } from "./api";
import { makeSeating, makeSession, paginated } from "./testFixtures";

const sessionApi = vi.hoisted(() => ({
  proctors: vi.fn(),
  assignProctor: vi.fn(),
  proctorCandidates: vi.fn(),
  removeProctor: vi.fn(),
  acknowledgeProctor: vi.fn(),
  seating: vi.fn(),
}));
const exemptionApi = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  remove: vi.fn(),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return {
    ...actual,
    examSessionApi: { ...actual.examSessionApi, ...sessionApi },
    proctorExemptionApi: exemptionApi,
  };
});

import GozetmenlerPaneli from "./GozetmenlerPaneli";

function makeCandidate(overrides: Partial<ProctorCandidate> = {}): ProctorCandidate {
  return {
    teacher_id: 51,
    teacher_name: "Ayşe ÖĞRETMEN",
    is_exempt: false,
    is_busy: false,
    is_assigned: false,
    ...overrides,
  };
}

function makeAssignmentRow(overrides: Partial<ProctorAssignmentRow> = {}): ProctorAssignmentRow {
  return {
    id: 61,
    session_id: 5,
    teacher_id: 51,
    teacher_name: "Ayşe ÖĞRETMEN",
    role: "PROCTOR",
    room_id: 1,
    room_name: "D-204",
    acknowledged: false,
    acknowledged_at: null,
    ...overrides,
  };
}

function renderPanel(session: ExamSession) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <ConfirmProvider>
          <GozetmenlerPaneli session={session} />
        </ConfirmProvider>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

function dagitilmisGozetmenli(overrides: Partial<ExamSession> = {}): ExamSession {
  return makeSession({ status: "DISTRIBUTED", proctors_enabled: true, ...overrides });
}

function mockVarsayilanlar(
  assignments: ProctorAssignmentRow[] = [],
  candidates: ProctorCandidate[] = [makeCandidate()],
) {
  sessionApi.proctors.mockResolvedValue({ proctors_enabled: true, assignments });
  sessionApi.proctorCandidates.mockResolvedValue({ candidates });
  sessionApi.seating.mockResolvedValue(makeSeating());
  exemptionApi.list.mockResolvedValue(paginated([]));
}

afterEach(() => vi.clearAllMocks());

describe("GozetmenlerPaneli", () => {
  it("modül kapalıyken bilgi mesajı basar; hiçbir uç çağrılmaz gerekmez", async () => {
    sessionApi.proctors.mockResolvedValue({ proctors_enabled: false, assignments: [] });
    renderPanel(makeSession({ status: "DISTRIBUTED", proctors_enabled: false }));

    expect(await screen.findByText(/Gözetmen modülü bu oturumda kapalı/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Otomatik/ })).not.toBeInTheDocument();
  });

  it("salon satırından aday seçilince atama yapılır; oto-öneri düğmesi YOK", async () => {
    const user = userEvent.setup();
    mockVarsayilanlar();
    sessionApi.assignProctor.mockResolvedValue(makeAssignmentRow());
    renderPanel(dagitilmisGozetmenli());

    expect(await screen.findByText("D-204")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Otomatik Öner/ })).not.toBeInTheDocument();

    const picker = screen.getByLabelText("D-204 için gözetmen ata");
    await user.type(picker, "Ay");
    await user.click(await screen.findByRole("option", { name: /ÖĞRETMEN/ }, { timeout: 3000 }));

    await waitFor(() =>
      expect(sessionApi.assignProctor).toHaveBeenCalledWith(5, {
        teacher_id: 51,
        role: "PROCTOR",
        room_id: 1,
      }),
    );
    expect(await screen.findByText("Görevlendirme eklendi.")).toBeInTheDocument();
  });

  it("muaf aday listede görünür ama seçilemez (neden etiketiyle)", async () => {
    const user = userEvent.setup();
    mockVarsayilanlar([], [makeCandidate({ is_exempt: true })]);
    renderPanel(dagitilmisGozetmenli());

    const picker = await screen.findByLabelText("D-204 için gözetmen ata");
    await user.type(picker, "Ay");
    const secenek = await screen.findByRole("option", { name: /ÖĞRETMEN/ }, { timeout: 3000 });
    expect(secenek).toHaveAttribute("aria-disabled", "true");
    expect(within(secenek).getByText(/muaf/)).toBeInTheDocument();
    await user.click(secenek);
    expect(sessionApi.assignProctor).not.toHaveBeenCalled();
  });

  it("tebellüğ chip'ten işlenir; onaylı oturumda liste salt-okunur ama tebellüğ açık", async () => {
    const user = userEvent.setup();
    sessionApi.proctors.mockResolvedValue({
      proctors_enabled: true,
      assignments: [makeAssignmentRow()],
    });
    sessionApi.seating.mockResolvedValue(makeSeating());
    sessionApi.acknowledgeProctor.mockResolvedValue(
      makeAssignmentRow({ acknowledged: true, acknowledged_at: "2026-06-15T10:00:00+03:00" }),
    );
    renderPanel(dagitilmisGozetmenli({ status: "APPROVED" }));

    expect(await screen.findByText("Ayşe ÖĞRETMEN")).toBeInTheDocument();
    expect(screen.getByText(/görevlendirme kilitli/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Tebellüğ işle" }));
    await waitFor(() => expect(sessionApi.acknowledgeProctor).toHaveBeenCalledWith(61));
    expect(await screen.findByText("Tebellüğ işlendi.")).toBeInTheDocument();
  });

  it("muafiyet bölümü: kalıcı muafiyet eklenir", async () => {
    const user = userEvent.setup();
    mockVarsayilanlar();
    exemptionApi.create.mockResolvedValue({
      id: 71,
      teacher_id: 51,
      teacher_name: "Ayşe ÖĞRETMEN",
      scope: "PERMANENT",
      session_id: null,
      reason_category: "DUTY",
    });
    renderPanel(dagitilmisGozetmenli());

    const bolum = (await screen.findByText("Muaf personel")).closest("section");
    expect(bolum).not.toBeNull();
    await user.selectOptions(within(bolum as HTMLElement).getByLabelText("Gerekçe"), "DUTY");
    await user.type(within(bolum as HTMLElement).getByLabelText("Öğretmen"), "Ay");
    await user.click(await screen.findByRole("option", { name: /ÖĞRETMEN/ }, { timeout: 3000 }));

    await waitFor(() =>
      expect(exemptionApi.create).toHaveBeenCalledWith({
        teacher_id: 51,
        scope: "PERMANENT",
        session_id: null,
        reason_category: "DUTY",
      }),
    );
    expect(await screen.findByText("Muafiyet eklendi.")).toBeInTheDocument();
  });
});
