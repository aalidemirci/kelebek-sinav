// Sınav yoklaması testleri (F3): API mock'lanır; girmedi işaretleme akışı,
// mazeret durumu (anında) / not (onBlur) güncellemesi — ARŞİVDE DE — ve
// confirm'li işaret kaldırma doğrulanır. Ortak kurucular testFixtures.ts'ten.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { Paginated } from "../../lib/pagination";
import type { ExamRoom } from "../salonlar/api";
import type { ExamSession } from "./api";
import {
  makeAssignment,
  makeAttendanceRecord,
  makeRoomGeometry,
  makeSeating,
  makeSession,
  paginated,
} from "./testFixtures";

const sessionApi = vi.hoisted(() => ({
  seating: vi.fn(),
  // Varsayılan: fotoğraf yok (eski liste testleri planı hiç görmez).
  seatingPhotos: vi.fn(() => Promise.resolve({ photos: {} as Record<string, string> })),
}));
const attendance = vi.hoisted(() => ({
  list: vi.fn(),
  mark: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
}));
// Salon planı gelmezse panel liste görünümüne düşer — eski testler bunu sınar.
const rooms = vi.hoisted(() => ({
  list: vi.fn((): Promise<Paginated<ExamRoom>> => Promise.reject(new Error("plan yok"))),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return {
    ...actual,
    examSessionApi: { ...actual.examSessionApi, ...sessionApi },
    attendanceApi: attendance,
  };
});
vi.mock("../salonlar/api", async (importActual) => {
  const actual = await importActual<typeof import("../salonlar/api")>();
  return { ...actual, examRoomApi: { ...actual.examRoomApi, ...rooms } };
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

    // Mazeret durumu seçenekleri mevzuatın diliyle: Beklemede / Mazeretli / Mazeretsiz
    // ("Özürlü/Özürsüz" engellilik çağrışımı taşıyordu — docs/sozluk.md §1).
    const durum = screen.getByLabelText("Ayşe Yılmaz mazeret durumu");
    expect(
      within(durum)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["Beklemede", "Mazeretli", "Mazeretsiz"]);
    expect(screen.queryByText(/Özür/)).not.toBeInTheDocument();

    // Mazeret durumu: seçim anında update çağırır (arşivde de açık).
    await user.selectOptions(durum, "EXCUSED");
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

// ---------------------------------------------------------------------------
// Fotoğraflı yoklama planı (19.09.2026, kullanıcı kararı: "yoklama/imza doğrudan
// plan üzerinde") — salon planı + fotoğraflar gelince liste yerine plan çizilir.
// KVKK: fotoğraf 1×1 piksellik uydurma data URI'dir.
// ---------------------------------------------------------------------------

const FOTO = "data:image/jpeg;base64,/9j/sahte";

describe("YoklamaPaneli — fotoğraflı plan", () => {
  it("salon planında kartlar çizilir; fotoğrafı olanda resim, olmayanda baş harfler", async () => {
    sessionApi.seating.mockResolvedValue(makeSeating({ status: "APPROVED" }));
    sessionApi.seatingPhotos.mockResolvedValue({ photos: { "101": FOTO } });
    rooms.list.mockResolvedValue(paginated([makeRoomGeometry()]));
    attendance.list.mockResolvedValue(paginated([]));
    renderPanel(makeSession({ status: "APPROVED" }));

    const plan = await screen.findByRole("group", { name: "D-204 yoklama planı" });
    const ayse = within(plan).getByRole("button", { name: /1\. koltuk, Ayşe Yılmaz, 101/ });
    expect(ayse.querySelector("img")?.getAttribute("src")).toBe(FOTO);
    const mehmet = within(plan).getByRole("button", { name: /2\. koltuk, Mehmet Demir/ });
    expect(mehmet.querySelector("img")).toBeNull();
    expect(mehmet).toHaveTextContent("MD");
    // Öğretmen masası planda yerinde; liste görünümü çizilmez.
    expect(within(plan).getByText("Öğretmen masası")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Girmedi işaretle/ })).not.toBeInTheDocument();
  });

  it("karta basmak girmedi işaretler; işaretli karta basmak onayla kaldırır", async () => {
    const user = userEvent.setup();
    sessionApi.seating.mockResolvedValue(makeSeating({ status: "APPROVED" }));
    sessionApi.seatingPhotos.mockResolvedValue({ photos: {} });
    rooms.list.mockResolvedValue(paginated([makeRoomGeometry()]));
    attendance.list.mockResolvedValue(paginated([makeAttendanceRecord()]));
    attendance.mark.mockResolvedValue(makeAttendanceRecord({ id: 32, student_id: 102 }));
    attendance.remove.mockResolvedValue(undefined);
    renderPanel(makeSession({ status: "APPROVED" }));

    const plan = await screen.findByRole("group", { name: "D-204 yoklama planı" });
    const ayse = within(plan).getByRole("button", { name: /Ayşe Yılmaz/ });
    expect(ayse).toHaveAttribute("aria-pressed", "true");
    expect(ayse).toHaveTextContent("Girmedi");

    await user.click(within(plan).getByRole("button", { name: /Mehmet Demir/ }));
    await waitFor(() =>
      expect(attendance.mark).toHaveBeenCalledWith({ session_id: 5, seat_assignment_id: 12 }),
    );

    await user.click(ayse);
    expect(await screen.findByText("İşaret kaldırılsın mı?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Kaldır" }));
    await waitFor(() => expect(attendance.remove).toHaveBeenCalledWith(31));
  });

  it("koltuğu planda olmayan öğrenci kaybolmaz — planın altında uyarıyla gösterilir", async () => {
    sessionApi.seating.mockResolvedValue(
      makeSeating({
        rooms: [
          {
            room_id: 1,
            room_name: "D-204",
            assignments: [
              makeAssignment(),
              makeAssignment({ id: 13, seat_no: 9, desk_row: 5, student_id: 109 }),
            ],
          },
        ],
      }),
    );
    sessionApi.seatingPhotos.mockResolvedValue({ photos: {} });
    rooms.list.mockResolvedValue(paginated([makeRoomGeometry()]));
    attendance.list.mockResolvedValue(paginated([]));
    renderPanel(makeSession({ status: "APPROVED" }));

    expect(
      await screen.findByText(/1 öğrencinin koltuğu güncel salon planında yok/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /9\. koltuk/ })).toBeInTheDocument();
  });
});
