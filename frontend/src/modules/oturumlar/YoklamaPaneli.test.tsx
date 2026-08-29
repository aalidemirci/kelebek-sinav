// Sınav yoklaması testleri (F3): API mock'lanır; girmedi işaretleme akışı,
// mazeret durumu (anında) / not (onBlur) güncellemesi — ARŞİVDE DE — ve
// confirm'li işaret kaldırma doğrulanır. Ortak kurucular testFixtures.ts'ten.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { ExamSession } from "./api";
import { makeAttendanceRecord, makeSeating, makeSession, paginated } from "./testFixtures";

const sessionApi = vi.hoisted(() => ({ seating: vi.fn() }));
const attendance = vi.hoisted(() => ({
  list: vi.fn(),
  mark: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return {
    ...actual,
    examSessionApi: { ...actual.examSessionApi, ...sessionApi },
    attendanceApi: attendance,
  };
});

import YoklamaPaneli from "./YoklamaPaneli";

function renderPanel(session: ExamSession) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <ConfirmProvider>
          <YoklamaPaneli session={session} />
        </ConfirmProvider>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("YoklamaPaneli", () => {
  it("salon listesinden girmedi işaretler (varsayılan mazeret beklemede)", async () => {
    const user = userEvent.setup();
    sessionApi.seating.mockResolvedValue(makeSeating({ status: "APPROVED" }));
    attendance.list.mockResolvedValue(paginated([]));
    attendance.mark.mockResolvedValue(makeAttendanceRecord());
    renderPanel(makeSession({ status: "APPROVED" }));

    expect(await screen.findByText("Sınava girmeyenler (0)")).toBeInTheDocument();
    // İlk öğrencinin satırındaki "Girmedi işaretle" butonu (iki satırdan ilki).
    const buttons = screen.getAllByRole("button", { name: /Girmedi işaretle/ });
    expect(buttons).toHaveLength(2);
    await user.click(buttons[0]);

    // mark yalnız kimliklerle çağrılır — mazeret backend varsayılanı PENDING.
    await waitFor(() =>
      expect(attendance.mark).toHaveBeenCalledWith({ session_id: 5, seat_assignment_id: 11 }),
    );
    expect(
      await screen.findByText("Girmedi olarak işaretlendi — mazeret durumu beklemede."),
    ).toBeInTheDocument();
  });

  it("işaretli öğrenci listelenir; ARŞİVDE mazeret anında, not onBlur'da güncellenir", async () => {
    const user = userEvent.setup();
    sessionApi.seating.mockResolvedValue(makeSeating({ status: "ARCHIVED" }));
    attendance.list.mockResolvedValue(paginated([makeAttendanceRecord()]));
    attendance.update.mockResolvedValue(makeAttendanceRecord({ excuse_status: "EXCUSED" }));
    renderPanel(makeSession({ status: "ARCHIVED" }));

    // İşaretli öğrenci kartta; salon satırında buton yerine "Girmedi" görünür.
    expect(await screen.findByText("Sınava girmeyenler (1)")).toBeInTheDocument();
    expect(screen.getByText("Girmedi")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Girmedi işaretle/ })).toHaveLength(1); // yalnız 102

    // Mazeret durumu: seçim anında update çağırır (arşivde de açık).
    await user.selectOptions(screen.getByLabelText("Ayşe Yılmaz mazeret durumu"), "EXCUSED");
    await waitFor(() =>
      expect(attendance.update).toHaveBeenCalledWith(31, { excuse_status: "EXCUSED" }),
    );
    expect(await screen.findByText("Mazeret kaydı güncellendi.")).toBeInTheDocument();

    // Not: yazarken istek YOK; blur'da tek istek.
    attendance.update.mockClear();
    await user.type(screen.getByLabelText("Ayşe Yılmaz mazeret notu"), "Rapor no 123");
    expect(attendance.update).not.toHaveBeenCalled();
    await user.tab();
    await waitFor(() =>
      expect(attendance.update).toHaveBeenCalledWith(31, { note: "Rapor no 123" }),
    );
  });

  it("işaret kaldırma confirm ister; onaylanınca kaydı siler", async () => {
    const user = userEvent.setup();
    sessionApi.seating.mockResolvedValue(makeSeating({ status: "APPROVED" }));
    attendance.list.mockResolvedValue(paginated([makeAttendanceRecord()]));
    attendance.remove.mockResolvedValue(undefined);
    renderPanel(makeSession({ status: "APPROVED" }));

    await user.click(await screen.findByRole("button", { name: /İşareti kaldır/ }));
    expect(await screen.findByText("İşaret kaldırılsın mı?")).toBeInTheDocument();
    expect(attendance.remove).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Kaldır" }));
    await waitFor(() => expect(attendance.remove).toHaveBeenCalledWith(31));
    expect(await screen.findByText("İşaret kaldırıldı.")).toBeInTheDocument();
  });
});
