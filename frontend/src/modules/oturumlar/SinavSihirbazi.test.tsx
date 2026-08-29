// Sınav Sihirbazı testleri (F3): Adım 0 beyan kilidi, adım geçişleri,
// HOME_CLASSROOM'da salon adımının atlanması. API ağ çağrıları vi.mock'lanır;
// ortak oturum kurucusu testFixtures.ts'ten gelir (test dosyasından test
// dosyasına import YOK — OYS Tur 232).

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { ExamSession, ExamSessionCourseRow, ParticipantsResponse } from "./api";
import { makeSession } from "./testFixtures";

const sessionApi = vi.hoisted(() => ({
  preCheck: vi.fn(),
  confirmTransferCheck: vi.fn(),
  update: vi.fn(),
  participants: vi.fn(),
  addCourse: vi.fn(),
  removeCourse: vi.fn(),
  setRooms: vi.fn(),
  distribute: vi.fn(),
}));

const dersler = vi.hoisted(() => ({
  listCourses: vi.fn(() => Promise.resolve([])),
}));

const okul = vi.hoisted(() => ({
  listClassSections: vi.fn(() => Promise.resolve([])),
}));

const salonlar = vi.hoisted(() => ({
  list: vi.fn(() => Promise.resolve({ count: 0, next: null, previous: null, results: [] })),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, examSessionApi: { ...actual.examSessionApi, ...sessionApi } };
});
vi.mock("../dersler/api", async (importActual) => {
  const actual = await importActual<typeof import("../dersler/api")>();
  return { ...actual, derslerApi: { ...actual.derslerApi, ...dersler } };
});
vi.mock("../okul/api", async (importActual) => {
  const actual = await importActual<typeof import("../okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...okul } };
});
vi.mock("../salonlar/api", async (importActual) => {
  const actual = await importActual<typeof import("../salonlar/api")>();
  return { ...actual, examRoomApi: { ...actual.examRoomApi, ...salonlar } };
});

import SinavSihirbazi from "./SinavSihirbazi";

function makeCourseRow(overrides: Partial<ExamSessionCourseRow> = {}): ExamSessionCourseRow {
  return {
    id: 11,
    course_id: 3,
    course_name: "Coğrafya",
    participant_type: "LEVEL",
    level: 9,
    display_label: "Coğrafya — 9. Sınıf",
    section_ids: [],
    duration_minutes: null,
    shared_booklet: false,
    ...overrides,
  };
}

function makeParticipants(overrides: Partial<ParticipantsResponse> = {}): ParticipantsResponse {
  return {
    total_count: 30,
    has_blocking_conflicts: false,
    warnings: [],
    courses: [
      {
        session_course_id: 11,
        course_id: 3,
        course_name: "Coğrafya",
        count: 30,
        warnings: [],
        participants: [],
      },
    ],
    ...overrides,
  };
}

function renderWizard(session: ExamSession) {
  const onChanged = vi.fn();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <SinavSihirbazi session={session} onChanged={onChanged} />
      </SnackbarProvider>
    </QueryClientProvider>,
  );
  return { onChanged };
}

afterEach(() => vi.clearAllMocks());

describe("SinavSihirbazi — Adım 0 (Veri Ön Kontrolü)", () => {
  it("onaysız oturum Adım 0'da başlar; beyan işaretlenmeden ilerlenemez", async () => {
    const user = userEvent.setup();
    sessionApi.preCheck.mockResolvedValue({
      active_students_by_level: { "9": 120, "10": 96 },
      last_student_import: {
        file_name: "ogrenciler.xlsx",
        finished_at: "2026-06-01T09:00:00+03:00",
      },
    });
    sessionApi.confirmTransferCheck.mockResolvedValue(
      makeSession({ transfer_check_confirmed_at: "2026-06-14T10:00:00+03:00" }),
    );
    const { onChanged } = renderWizard(makeSession());

    expect(await screen.findByRole("heading", { name: "Veri Ön Kontrolü" })).toBeInTheDocument();
    // Yeni sözleşme: seviye sayıları + son aktarım dosyası görünür.
    expect(await screen.findByText("120")).toBeInTheDocument();
    expect(screen.getByText("ogrenciler.xlsx")).toBeInTheDocument();

    const onayla = screen.getByRole("button", { name: "Onayla ve devam et" });
    expect(onayla).toBeDisabled();
    await user.click(screen.getByRole("checkbox"));
    expect(onayla).toBeEnabled();

    await user.click(onayla);
    await waitFor(() => expect(sessionApi.confirmTransferCheck).toHaveBeenCalledWith(5));
    expect(onChanged).toHaveBeenCalled();
    // Onay sonrası Adım 1'e geçilir.
    expect(await screen.findByRole("heading", { name: "Oturum Bilgileri" })).toBeInTheDocument();
  });

  it("hiç öğrenci aktarımı yoksa uyarı gösterir", async () => {
    sessionApi.preCheck.mockResolvedValue({
      active_students_by_level: {},
      last_student_import: null,
    });
    renderWizard(makeSession());

    expect(await screen.findByText(/Henüz öğrenci aktarımı yapılmamış/)).toBeInTheDocument();
  });

  it("onaylı oturum Adım 1'den başlar; gözetmen anahtarı Adım 1'de (F7)", async () => {
    renderWizard(makeSession({ transfer_check_confirmed_at: "2026-06-10T10:00:00+03:00" }));

    expect(await screen.findByRole("heading", { name: "Oturum Bilgileri" })).toBeInTheDocument();
    expect(sessionApi.preCheck).not.toHaveBeenCalled();
    // Gözetmen anahtarı F7 ile Adım 1'e geldi (U2 — varsayılan kapalı).
    const kutu = screen.getByRole("checkbox", { name: /Gözetmen modülü açık/ });
    expect(kutu).not.toBeChecked();
  });
});

describe("SinavSihirbazi — adım geçişleri", () => {
  it("Adım 1 kaydedilince update çağrılır ve Adım 2'ye geçilir", async () => {
    const user = userEvent.setup();
    const session = makeSession({ transfer_check_confirmed_at: "2026-06-10T10:00:00+03:00" });
    sessionApi.update.mockResolvedValue(session);
    const { onChanged } = renderWizard(session);

    await user.click(await screen.findByRole("button", { name: "Kaydet ve devam et" }));

    await waitFor(() =>
      expect(sessionApi.update).toHaveBeenCalledWith(
        5,
        expect.objectContaining({ name: "2. Ortak Sınav", layout_mode: "BUTTERFLY" }),
      ),
    );
    expect(onChanged).toHaveBeenCalled();
    expect(
      await screen.findByRole("heading", { name: "Ders ve Katılımcılar" }),
    ).toBeInTheDocument();
    // Ders yokken ilerlenemez.
    expect(screen.getByRole("button", { name: "Devam" })).toBeDisabled();
  });

  it("çakışma kilidi: has_blocking_conflicts Devam düğmesini kilitler", async () => {
    const user = userEvent.setup();
    const session = makeSession({
      transfer_check_confirmed_at: "2026-06-10T10:00:00+03:00",
      courses: [makeCourseRow()],
    });
    sessionApi.update.mockResolvedValue(session);
    sessionApi.participants.mockResolvedValue(
      makeParticipants({
        has_blocking_conflicts: true,
        warnings: ["Öğrenci 154 iki derse düşüyor."],
      }),
    );
    renderWizard(session);

    await user.click(await screen.findByRole("button", { name: "Kaydet ve devam et" }));
    expect(await screen.findByText(/dağıtım engellenecek/)).toBeInTheDocument();
    expect(screen.getByText(/Öğrenci 154 iki derse düşüyor\./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Devam" })).toBeDisabled();
  });

  it("HOME_CLASSROOM: salon adımı atlanır (2→4) ve dağıtım koşar", async () => {
    const user = userEvent.setup();
    const session = makeSession({
      layout_mode: "HOME_CLASSROOM",
      transfer_check_confirmed_at: "2026-06-10T10:00:00+03:00",
      courses: [makeCourseRow()],
    });
    sessionApi.update.mockResolvedValue(session);
    sessionApi.participants.mockResolvedValue(makeParticipants());
    sessionApi.distribute.mockResolvedValue({
      status: "DISTRIBUTED",
      seed: 42,
      checkerboard: false,
      placed: 30,
      warnings: [],
      report: {
        is_valid: true,
        hard_violations: [],
        first_ring_same_group_pairs: 0,
        min_same_group_distance: {},
        proximity_score: 0,
        cross_group_same_section_first_ring_pairs: 0,
        room_counts: {},
      },
    });
    const { onChanged } = renderWizard(session);

    // Stepper salon adımını baştan "atlandı" işaretler.
    expect(await screen.findByText("atlandı")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Kaydet ve devam et" }));
    await user.click(await screen.findByRole("button", { name: "Devam" }));

    // Salon adımı görülmeden Dağıt & Önizle'ye ulaşılır; salon ucu hiç çağrılmaz.
    expect(await screen.findByRole("heading", { name: "Dağıt & Önizle" })).toBeInTheDocument();
    expect(salonlar.list).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Dağıt" }));
    await waitFor(() =>
      expect(sessionApi.distribute).toHaveBeenCalledWith(5, { seed: undefined, strict: false }),
    );
    expect(await screen.findByText(/30 öğrenci yerleşti \(seed 42\)/)).toBeInTheDocument();
    expect(onChanged).toHaveBeenCalled();
  });
});
