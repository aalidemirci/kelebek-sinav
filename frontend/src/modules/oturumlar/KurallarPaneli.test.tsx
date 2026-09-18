// Yerleştirme kuralları paneli testleri (Ö4).
// Çekirdek iddia: yer seçilmezse VARSAYILAN kural "kendi dersliğinde + arka
// sıra + tek başına"dır (kullanıcı isteği 31.08.2026). Koltuk seçilirse
// BELIRLI_KOLTUK koordinat üçlüsüyle gönderilir — seat_no ile DEĞİL.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";

const ruleApi = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn(), remove: vi.fn() }));
const okulApiMock = vi.hoisted(() => ({ listStudents: vi.fn() }));
const roomApi = vi.hoisted(() => ({ list: vi.fn(), seats: vi.fn() }));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, placementRuleApi: { ...actual.placementRuleApi, ...ruleApi } };
});
vi.mock("../okul/api", async (importActual) => {
  const actual = await importActual<typeof import("../okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...okulApiMock } };
});
vi.mock("../salonlar/api", async (importActual) => {
  const actual = await importActual<typeof import("../salonlar/api")>();
  return { ...actual, examRoomApi: { ...actual.examRoomApi, ...roomApi } };
});

import KurallarPaneli from "./KurallarPaneli";

const OGRENCI = {
  id: 42,
  first_name: "Örnek",
  last_name: "ÖĞRENCİ",
  full_name: "Örnek ÖĞRENCİ",
  student_number: "101",
  class_level: 9,
  class_section: "A",
  class_label: "9/A",
  status: "ACTIVE" as const,
};

/** "Belirli koltuk" kuralı — koordinat ızgara kimliğidir (0 tabanlı; satır 0 = ön cephe). */
const SABIT_KOLTUK_KURALI = {
  id: 3,
  student_id: 42,
  student_name: "Örnek ÖĞRENCİ",
  scope: "SESSION",
  session_id: 7,
  rule_type: "FIXED_SEAT",
  target_room_id: 2,
  target_room_name: "D-101",
  target_desk_row: 2,
  target_desk_col: 1,
  target_slot: 0,
  seat_preference: "NONE",
  solo_desk: true,
  reason_category: "DISABILITY",
};

/** D-101 koltuk ucu: (2, 1) hücresindeki ikili sıranın iki koltuğu. */
const D101_KOLTUKLARI = {
  room_id: 2,
  numbering_scheme: "S_PATTERN",
  capacity: 40,
  seats: [
    { desk_row: 2, desk_col: 1, desk_type: "DOUBLE", slot: 0, seat_no: 11, x: 1, y: 2 },
    { desk_row: 2, desk_col: 1, desk_type: "DOUBLE", slot: 1, seat_no: 12, x: 1.5, y: 2 },
  ],
};

function kuralListesi(results: unknown[]) {
  return { count: results.length, next: null, previous: null, results };
}

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <ConfirmProvider>
          <KurallarPaneli sessionId={7} />
        </ConfirmProvider>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("KurallarPaneli", () => {
  it("kural yokken boş durum gösterir", async () => {
    ruleApi.list.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    renderPanel();
    expect(await screen.findByText("Kural yok")).toBeInTheDocument();
  });

  it("yer seçilmezse varsayılan kural kendi dersliğinde + arka sıra + tek başına", async () => {
    const user = userEvent.setup();
    ruleApi.list.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    okulApiMock.listStudents.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [OGRENCI],
    });
    ruleApi.create.mockResolvedValue({ id: 1 });
    renderPanel();

    await user.click(await screen.findByRole("button", { name: /Kural ekle/ }));
    const alan = await screen.findByLabelText(/Öğrenci/);
    await user.type(alan, "Örnek");
    // Autocomplete etiketi `highlight()` ile parçalara bölünür → metinle değil
    // ROL ile seçilir. Arama LISTBOX'ına sınırlanır: yerel <select> öğelerinin
    // <option>'ları da role="option" taşır ve aksi hâlde onlar yakalanır.
    const listbox = await screen.findByRole("listbox");
    await user.click(within(listbox).getAllByRole("option")[0]);
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(ruleApi.create).toHaveBeenCalledWith(
        expect.objectContaining({
          student_id: 42,
          rule_type: "HOME_CLASSROOM",
          seat_preference: "BACK",
          solo_desk: true,
          scope: "SESSION",
          session_id: 7,
        }),
      ),
    );
  });

  it("kayıtlı kural özetinde koltuk SÖZLE ve 1 tabanlı yazılır; koltuk no salondan okunur", async () => {
    ruleApi.list.mockResolvedValue(kuralListesi([SABIT_KOLTUK_KURALI]));
    roomApi.seats.mockResolvedValue(D101_KOLTUKLARI);
    renderPanel();

    expect(await screen.findByText("Örnek ÖĞRENCİ")).toBeInTheDocument();
    // Izgara (2, 1, 0) → 2. sıra (ön cephe bandı sayılmaz), 2. sütun, sol koltuk.
    expect(
      await screen.findByText(
        "Belirli koltuk · D-101 · 2. sıra, 2. sütun, sol koltuk (koltuk no 11) · tek başına",
      ),
    ).toBeInTheDocument();
    expect(roomApi.seats).toHaveBeenCalledWith(2);
    // Eski 0 tabanlı ham koordinat gösterimi kalmadı.
    expect(screen.queryByText(/sıra 2-1, koltuk 0/)).not.toBeInTheDocument();
    expect(screen.getByText("Engel durumu")).toBeInTheDocument();
  });

  it("salon koltuk ucu gelmezse konum yine sözle yazılır; yalnız koltuk no ve sol/sağ düşer", async () => {
    ruleApi.list.mockResolvedValue(kuralListesi([SABIT_KOLTUK_KURALI]));
    roomApi.seats.mockRejectedValue(new Error("ağ koptu"));
    renderPanel();

    // Sıra tipi bilinmeden "sol/orta/sağ" tahmin edilmez → soldan sayılır.
    expect(
      await screen.findByText(
        "Belirli koltuk · D-101 · 2. sıra, 2. sütun, soldan 1. koltuk · tek başına",
      ),
    ).toBeInTheDocument();
  });

  it("koltuk seçici seçenekleri sözle gösterir; kayıt yine KOORDİNATLA gider", async () => {
    const user = userEvent.setup();
    ruleApi.list.mockResolvedValue(kuralListesi([]));
    okulApiMock.listStudents.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [OGRENCI],
    });
    roomApi.list.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [{ id: 2, name: "D-101", group_name: "" }],
    });
    roomApi.seats.mockResolvedValue(D101_KOLTUKLARI);
    ruleApi.create.mockResolvedValue({ id: 1 });
    renderPanel();

    await user.click(await screen.findByRole("button", { name: /Kural ekle/ }));
    await user.type(await screen.findByLabelText(/Öğrenci/), "Örnek");
    await user.click(within(await screen.findByRole("listbox")).getAllByRole("option")[0]);
    await user.click(screen.getByRole("checkbox", { name: "Yerini ben seçeyim" }));

    // Seçici yer tutucusu tek biçim: "Seçin" (docs/sozluk.md §3).
    const salon = screen.getByLabelText("Salon");
    expect(within(salon).getByRole("option", { name: "Seçin" })).toBeInTheDocument();
    await user.selectOptions(salon, "2");

    const koltuk = screen.getByLabelText("Koltuk");
    const secenek = await within(koltuk).findByRole("option", {
      name: "2. sıra, 2. sütun, sağ koltuk (koltuk no 12)",
    });
    await user.selectOptions(koltuk, secenek);
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(ruleApi.create).toHaveBeenCalledWith(
        expect.objectContaining({
          rule_type: "FIXED_SEAT",
          target_room_id: 2,
          target_desk_row: 2,
          target_desk_col: 1,
          target_slot: 1,
        }),
      ),
    );
  });

  it("kural kaldırma onayı: başlık soru, gövde sonuç — gövdede öğrenci adı geçmez", async () => {
    const user = userEvent.setup();
    ruleApi.list.mockResolvedValue(kuralListesi([SABIT_KOLTUK_KURALI]));
    roomApi.seats.mockResolvedValue(D101_KOLTUKLARI);
    ruleApi.remove.mockResolvedValue(undefined);
    renderPanel();

    await user.click(await screen.findByRole("button", { name: "Örnek ÖĞRENCİ kuralını kaldır" }));
    const dialog = await screen.findByRole("dialog", { name: "Kural kaldırılsın mı?" });
    expect(dialog).not.toHaveTextContent("Örnek ÖĞRENCİ");
    await user.click(within(dialog).getByRole("button", { name: "Kaldır" }));

    await waitFor(() => expect(ruleApi.remove).toHaveBeenCalledWith(3));
  });
});
