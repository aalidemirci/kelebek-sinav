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

  it("kayıtlı kural özetinde koltuk koordinatı ve tek başına görünür", async () => {
    ruleApi.list.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
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
        },
      ],
    });
    renderPanel();

    expect(await screen.findByText("Örnek ÖĞRENCİ")).toBeInTheDocument();
    expect(
      screen.getByText(/Belirli koltuk · D-101 · sıra 2-1, koltuk 0 · tek başına/),
    ).toBeInTheDocument();
    expect(screen.getByText("Engel durumu")).toBeInTheDocument();
  });
});
