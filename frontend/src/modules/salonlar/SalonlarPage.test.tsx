// Sınav Salonları sayfası + Salon Editörü entegrasyon testleri (T10 — Tur 231).
// API ağ çağrıları mock'lanır; tıkla-yerleştir akışı, canlı kapasite sayacı,
// backend numara önizlemesi ve kaydetme gövdesi doğrulanır.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { ExamRoom } from "./api";

const exam = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  previewSeats: vi.fn(),
  generateSectionRooms: vi.fn(),
  layoutPdfBlob: vi.fn(),
}));
const download = vi.hoisted(() => ({ saveBlob: vi.fn() }));

const sections = vi.hoisted(() => ({
  listClassSections: vi.fn(() =>
    Promise.resolve([
      {
        id: 7,
        school_year: 1,
        school_year_name: "2026-2027",
        class_level: 9,
        class_section: "A",
        class_label: "9/A",
      },
    ]),
  ),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, examRoomApi: exam };
});
vi.mock("../../lib/download", () => download);
vi.mock("../okul/api", async (importActual) => {
  const actual = await importActual<typeof import("../okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...sections } };
});

import SalonlarPage from "./SalonlarPage";

function makeRoom(overrides: Partial<ExamRoom> = {}): ExamRoom {
  return {
    id: 1,
    name: "D-204",
    block: "A Blok",
    linked_section_id: null,
    linked_section_label: "",
    layout_plan: { grid: { rows: 2, cols: 2 }, desks: [], furniture: [] },
    numbering_scheme: "S_PATTERN",
    is_active: true,
    capacity: 0,
    ...overrides,
  };
}

function paginated(rooms: ExamRoom[]) {
  return { count: rooms.length, next: null, previous: null, results: rooms };
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <ConfirmProvider>
          <SalonlarPage />
        </ConfirmProvider>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("SalonlarPage", () => {
  it("salon kartlarını kapasite + pasif rozetiyle listeler", async () => {
    exam.list.mockResolvedValue(
      paginated([makeRoom(), makeRoom({ id: 2, name: "Lab", is_active: false, capacity: 12 })]),
    );
    renderPage();

    expect(await screen.findByText("D-204")).toBeInTheDocument();
    expect(screen.getByText("Lab")).toBeInTheDocument();
    expect(screen.getByText("Pasif")).toBeInTheDocument();
    expect(screen.getByText("12 koltuk")).toBeInTheDocument();
  });

  it("yeni salon boş planla oluşturulur ve editör açılır", async () => {
    const user = userEvent.setup();
    exam.list.mockResolvedValue(paginated([]));
    exam.create.mockResolvedValue(makeRoom({ id: 9, name: "Yeni-1" }));
    exam.previewSeats.mockResolvedValue({ capacity: 0, seats: [] });
    renderPage();

    await user.click(await screen.findByRole("button", { name: /yeni salon/i }));
    await user.type(screen.getByLabelText(/salon adı/i), "Yeni-1");
    await user.click(screen.getByRole("button", { name: "Oluştur" }));

    await waitFor(() =>
      expect(exam.create).toHaveBeenCalledWith({
        name: "Yeni-1",
        block: "",
        layout_plan: { grid: { rows: 5, cols: 4 }, desks: [], furniture: [] },
      }),
    );
  });

  it("tıkla-yerleştir: sıra eklenir, kapasite sayacı backend önizlemesinden gelir", async () => {
    const user = userEvent.setup();
    exam.list.mockResolvedValue(paginated([makeRoom()]));
    // İlk çağrı (boş plan) 0; sıra yerleştirilince 2 koltuk + numaralar.
    exam.previewSeats.mockImplementation((plan: { desks: unknown[] }) =>
      Promise.resolve(
        plan.desks.length === 0
          ? { capacity: 0, seats: [] }
          : {
              capacity: 2,
              seats: [
                { desk_row: 0, desk_col: 0, desk_type: "DOUBLE", slot: 0, seat_no: 1, x: 0, y: 0 },
                {
                  desk_row: 0,
                  desk_col: 0,
                  desk_type: "DOUBLE",
                  slot: 1,
                  seat_no: 2,
                  x: 0.25,
                  y: 0,
                },
              ],
            },
      ),
    );
    renderPage();

    await user.click(await screen.findByRole("button", { name: /D-204/ }));
    expect(await screen.findByText("Kapasite: 0")).toBeInTheDocument();

    // Varsayılan araç ikili sıra; sol-üst hücreye yerleştir.
    await user.click(screen.getByRole("button", { name: "Satır 1, sütun 1 — boş" }));
    expect(
      await screen.findByRole("button", { name: "Satır 1, sütun 1 — İkili sıra" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Kapasite: 2")).toBeInTheDocument();
    // Backend'den gelen koltuk numaraları hücrede görünür.
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("araç paletinden mobilya seçilip yerleştirilir; silgi temizler", async () => {
    const user = userEvent.setup();
    exam.list.mockResolvedValue(paginated([makeRoom()]));
    exam.previewSeats.mockResolvedValue({ capacity: 0, seats: [] });
    renderPage();

    await user.click(await screen.findByRole("button", { name: /D-204/ }));
    await user.click(await screen.findByRole("radio", { name: "Öğretmen masası" }));
    await user.click(screen.getByRole("button", { name: "Satır 1, sütun 2 — boş" }));
    expect(
      screen.getByRole("button", { name: "Satır 1, sütun 2 — Öğretmen masası" }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "Sil" }));
    await user.click(screen.getByRole("button", { name: "Satır 1, sütun 2 — Öğretmen masası" }));
    expect(screen.getByRole("button", { name: "Satır 1, sütun 2 — boş" })).toBeInTheDocument();
  });

  it("kaydet: planı + şube eşlemesini doğru gövdeyle gönderir", async () => {
    const user = userEvent.setup();
    const room = makeRoom();
    exam.list.mockResolvedValue(paginated([room]));
    exam.previewSeats.mockResolvedValue({ capacity: 0, seats: [] });
    exam.update.mockResolvedValue(makeRoom({ capacity: 2 }));
    renderPage();

    await user.click(await screen.findByRole("button", { name: /D-204/ }));
    await user.click(screen.getByRole("button", { name: "Satır 2, sütun 1 — boş" }));
    await user.selectOptions(screen.getByLabelText(/bağlı şube/i), "7");
    await user.click(screen.getByRole("button", { name: /kaydet/i }));

    await waitFor(() => expect(exam.update).toHaveBeenCalledTimes(1));
    const [id, payload] = exam.update.mock.calls[0];
    expect(id).toBe(1);
    expect(payload.linked_section_id).toBe(7);
    expect(payload.layout_plan.desks).toEqual([{ row: 1, col: 0, type: "DOUBLE" }]);
    expect(await screen.findByText("Salon kaydedildi.")).toBeInTheDocument();
  });

  it("'Yerleşim planı (PDF)' kaydedilmiş planı indirir (F4 layout-pdf)", async () => {
    const user = userEvent.setup();
    exam.list.mockResolvedValue(paginated([makeRoom()]));
    exam.previewSeats.mockResolvedValue({ capacity: 0, seats: [] });
    const blob = new Blob(["pdf"]);
    exam.layoutPdfBlob.mockResolvedValue(blob);
    renderPage();

    await user.click(await screen.findByRole("button", { name: /D-204/ }));
    await user.click(await screen.findByRole("button", { name: /Yerleşim planı \(PDF\)/ }));

    await waitFor(() => expect(exam.layoutPdfBlob).toHaveBeenCalledWith(1));
    expect(download.saveBlob).toHaveBeenCalledWith(blob, "salon_yerlesim_plani_1.pdf");
  });

  it("önizleme kapatılınca sayaç yerel toplama düşer ve uç çağrılmaz", async () => {
    const user = userEvent.setup();
    exam.list.mockResolvedValue(paginated([makeRoom()]));
    exam.previewSeats.mockResolvedValue({ capacity: 0, seats: [] });
    renderPage();

    await user.click(await screen.findByRole("button", { name: /D-204/ }));
    await user.click(screen.getByLabelText(/koltuk numarası önizlemesi/i));
    exam.previewSeats.mockClear();

    await user.click(screen.getByRole("button", { name: "Satır 1, sütun 1 — boş" }));
    expect(await screen.findByText("Kapasite: 2")).toBeInTheDocument(); // yerel toplam (ikili)
    expect(exam.previewSeats).not.toHaveBeenCalled();
  });

  it("'Şube dersliklerini oluştur' onaylanınca üretim ucunu çağırır (Tur 637)", async () => {
    const user = userEvent.setup();
    exam.list.mockResolvedValue(paginated([]));
    exam.generateSectionRooms.mockResolvedValue({
      created: ["9/A Dersliği", "9/B Dersliği"],
      skipped: [],
      orphan_rooms: [],
      sections_total: 2,
    });
    renderPage();

    await user.click(await screen.findByRole("button", { name: /Şube dersliklerini oluştur/ }));
    // Onay dialogu → "Oluştur"
    await user.click(await screen.findByRole("button", { name: "Oluştur" }));
    await waitFor(() => expect(exam.generateSectionRooms).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/2 salon oluşturuldu/)).toBeInTheDocument();
  });
});
