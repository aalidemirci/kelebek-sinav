// "BEP ve tedbirler" listesi testleri (20.09.2026 BEP; tedbirler 07.10.2026): liste +
// boş durum, gerekçe ve tedbir sütunları (tedbir metni backend'den), ekleme/düzenleme
// penceresine giriş, çıkarma onayı (SATIR kimliğiyle siler; onay ve bildirim metninde
// öğrenci adı ve okul numarası YOK), "Tüm kayıtları sil" ve uygulama parolası uyarısı.
// Pencerenin ayrıntısı TedbirDialog.test.tsx'tedir. KVKK: ad ve numaralar UYDURMADIR.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { GuvenlikDurumu } from "../guvenlik/api";
import type { Student } from "../okul/api";
import type { IepStudent } from "./api";

const iep = vi.hoisted(() => ({
  list: vi.fn(),
  add: vi.fn(),
  update: vi.fn(),
  addByNumbers: vi.fn(),
  remove: vi.fn(),
  deleteAll: vi.fn(),
}));
const okulApiMock = vi.hoisted(() => ({ listStudents: vi.fn() }));
const guvenlik = vi.hoisted(() => ({ durum: vi.fn() }));
const salonApi = vi.hoisted(() => ({
  list: vi.fn(() => Promise.resolve({ count: 0, next: null, previous: null, results: [] })),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, iepApi: { ...actual.iepApi, ...iep } };
});
vi.mock("../okul/api", async (importActual) => {
  const actual = await importActual<typeof import("../okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...okulApiMock } };
});
vi.mock("../guvenlik/api", async (importActual) => {
  const actual = await importActual<typeof import("../guvenlik/api")>();
  return { ...actual, guvenlikApi: { ...actual.guvenlikApi, ...guvenlik } };
});
vi.mock("../salonlar/api", async (importActual) => {
  const actual = await importActual<typeof import("../salonlar/api")>();
  return { ...actual, examRoomApi: { ...actual.examRoomApi, ...salonApi } };
});

import BepListesiPaneli from "./BepListesiPaneli";

const TEDBIRSIZ: Omit<
  IepStudent,
  "id" | "student_id" | "student_number" | "full_name" | "class_label"
> = {
  reason_category: "IEP",
  reason_label: "BEP",
  placement: "NONE",
  target_room_id: null,
  seat_preference: "NONE",
  solo_desk: false,
  extra_minutes: 0,
  reader: false,
  scribe: false,
  measures: [],
};

// Satır kimliği (id) ile öğrenci pk'si (student_id) BİLEREK farklıdır: silme
// satır kimliğiyle yapılır; öğrenci pk'si yola hiç girmez.
const AYSE: IepStudent = {
  ...TEDBIRSIZ,
  id: 7,
  student_id: 301,
  student_number: "101",
  full_name: "Ayşe Yılmaz",
  class_label: "9/A",
};
const MEHMET: IepStudent = {
  ...TEDBIRSIZ,
  id: 8,
  student_id: 302,
  student_number: "102",
  full_name: "Mehmet Demir",
  class_label: "9/B",
  reason_category: "HEALTH",
  reason_label: "Sağlık",
  extra_minutes: 20,
  scribe: true,
  measures: ["Ek süre 20 dk", "Yazıcı desteği"],
};

const ZEYNEP: Student = {
  id: 303,
  first_name: "Zeynep",
  last_name: "Kaya",
  full_name: "Zeynep Kaya",
  student_number: "103",
  class_level: 10,
  class_section: "C",
  class_label: "10/C",
  gender: "",
  status: "ACTIVE",
};

function durum(passwordSet: boolean): GuvenlikDurumu {
  return {
    password_set: passwordSet,
    locked: false,
    security_file_missing: false,
    reset_available: false,
    transition_pending: false,
    transition: "",
    protected_fields: [],
  };
}

function ogrenciSayfasi(results: Student[]) {
  return { count: results.length, next: null, previous: null, results };
}

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={qc}>
        <SnackbarProvider>
          <ConfirmProvider>
            <BepListesiPaneli />
          </ConfirmProvider>
        </SnackbarProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  iep.list.mockResolvedValue({ results: [AYSE, MEHMET] });
  // Varsayılan: parola AÇIK → uyarı bandı yok (bant testleri kendi değerini verir).
  guvenlik.durum.mockResolvedValue(durum(true));
});

afterEach(() => vi.clearAllMocks());

describe("BepListesiPaneli", () => {
  it("listeyi gerekçe ve tedbirleriyle gösterir; tanı tutulmadığını söyler", async () => {
    renderPanel();

    const ayse = (await screen.findByText("Ayşe Yılmaz")).closest("tr") as HTMLElement;
    expect(within(ayse).getByText("101")).toBeInTheDocument();
    expect(within(ayse).getByText("BEP")).toBeInTheDocument();
    expect(within(ayse).getByText("Tedbir yok")).toBeInTheDocument();
    const mehmet = screen.getByText("Mehmet Demir").closest("tr") as HTMLElement;
    expect(within(mehmet).getByText("Sağlık")).toBeInTheDocument();
    expect(within(mehmet).getByText("Ek süre 20 dk · Yazıcı desteği")).toBeInTheDocument();
    expect(screen.getByText("2 öğrenci")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Tedbirler" })).toBeInTheDocument();
    // KVKK md. 6: tanı/rapor/açıklama kaydedilmez; evrak ve kitapçıkta işaret yok.
    expect(screen.getByText("tanı, rapor ya da açıklama kaydedilmez")).toBeInTheDocument();
    expect(screen.getByText(/öğrenciyi ayıran hiçbir işaret\s+basılmaz/)).toBeInTheDocument();
  });

  it("boş listede boş durum gösterilir", async () => {
    iep.list.mockResolvedValue({ results: [] });
    renderPanel();

    expect(await screen.findByText("Listede öğrenci yok")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("liste okunamazsa backend gerekçesi role=alert ile basılır", async () => {
    iep.list.mockRejectedValue(new ApiError(500, "server_error", "BEP listesi okunamadı."));
    renderPanel();

    expect(await screen.findByRole("alert")).toHaveTextContent("BEP listesi okunamadı.");
    expect(screen.queryByText("Listede öğrenci yok")).not.toBeInTheDocument();
  });

  it("öğrenci ekleme penceresi: aramadan seçilir, tedbirsiz BEP üyeliği gönderilir", async () => {
    const user = userEvent.setup();
    okulApiMock.listStudents.mockResolvedValue(ogrenciSayfasi([ZEYNEP]));
    iep.add.mockResolvedValue({ id: 9 });
    renderPanel();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Öğrenci ekle" }));
    const dialog = await screen.findByRole("dialog", { name: "Öğrenci ekle" });
    // Seçim yokken kayıt kapalıdır.
    expect(within(dialog).getByRole("button", { name: "Kaydet" })).toBeDisabled();
    await user.type(within(dialog).getByLabelText(/^Öğrenci/), "Zey");
    await user.click(within(await screen.findByRole("listbox")).getAllByRole("option")[0]);

    const cagriOncesi = iep.list.mock.calls.length;
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(iep.add).toHaveBeenCalledWith(303, {
        reason_category: "IEP",
        placement: "NONE",
        target_room_id: null,
        seat_preference: "NONE",
        solo_desk: false,
        extra_minutes: 0,
        reader: false,
        scribe: false,
      }),
    );
    // Bildirimde öğrenci adı ve okul numarası geçmez.
    expect(await screen.findByText("Öğrenci listeye eklendi.")).toBeInTheDocument();
    await waitFor(() => expect(iep.list.mock.calls.length).toBeGreaterThan(cagriOncesi));
    expect(screen.queryByRole("dialog", { name: "Öğrenci ekle" })).not.toBeInTheDocument();
  });

  it("zaten listedeki öğrenci aramada görünür ama seçilemez", async () => {
    const user = userEvent.setup();
    okulApiMock.listStudents.mockResolvedValue(
      ogrenciSayfasi([{ ...ZEYNEP, id: 301, full_name: "Ayşe Yılmaz", student_number: "101" }]),
    );
    renderPanel();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Öğrenci ekle" }));
    const dialog = await screen.findByRole("dialog", { name: "Öğrenci ekle" });
    await user.type(within(dialog).getByLabelText(/^Öğrenci/), "Ayş");
    const secenek = within(await screen.findByRole("listbox")).getAllByRole("option")[0];
    expect(secenek).toHaveAttribute("aria-disabled", "true");
    expect(secenek).toHaveTextContent("zaten listede");
  });

  it("Düzenle satırın tedbirleriyle açılır ve SATIR kimliğiyle kaydeder", async () => {
    const user = userEvent.setup();
    iep.update.mockResolvedValue({ id: 8 });
    renderPanel();

    const satir = (await screen.findByText("Mehmet Demir")).closest("tr") as HTMLElement;
    await user.click(within(satir).getByRole("button", { name: "Düzenle" }));
    const dialog = await screen.findByRole("dialog", { name: "Tedbirleri düzenle" });
    expect(within(dialog).getByLabelText("Ek süre (dakika)")).toHaveValue(20);
    expect(within(dialog).getByRole("checkbox", { name: "Yazıcı desteği" })).toBeChecked();
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(iep.update).toHaveBeenCalledWith(8, expect.objectContaining({ extra_minutes: 20 })),
    );
    expect(await screen.findByText("Tedbirler kaydedildi.")).toBeInTheDocument();
  });

  it("çıkarma onayı: başlık soru, gövde sonuç — metinde öğrenci adı ve okul numarası yok", async () => {
    const user = userEvent.setup();
    iep.remove.mockResolvedValue(undefined);
    renderPanel();

    const satir = (await screen.findByText("Ayşe Yılmaz")).closest("tr") as HTMLElement;
    await user.click(within(satir).getByRole("button", { name: "Çıkar" }));

    // Tek tıkla çıkarılmaz (tedbirler ve bireysel soru dosyaları da silinir).
    expect(iep.remove).not.toHaveBeenCalled();
    const dialog = await screen.findByRole("dialog", { name: "Öğrenci listeden çıkarılsın mı?" });
    expect(dialog).toHaveTextContent(
      "Bu öğrencinin tedbirleri silinir ve öğrenci BEP kapsamındaki öğrenciler listesinden çıkar; onaylanmamış oturumlardaki bireysel soru dosyaları da silinir.",
    );
    expect(dialog).not.toHaveTextContent("Ayşe Yılmaz");
    expect(dialog).not.toHaveTextContent("101");
    await user.click(within(dialog).getByRole("button", { name: "Çıkar" }));

    // Silme SATIR kimliğiyle yapılır (7) — öğrenci pk'siyle (301) değil.
    await waitFor(() => expect(iep.remove).toHaveBeenCalledWith(7));
    const bildirim = await screen.findByText("Öğrenci listeden çıkarıldı.");
    expect(bildirim).not.toHaveTextContent("Ayşe");
  });

  it("çıkarma onayında “Vazgeç” denirse kayıt silinmez", async () => {
    const user = userEvent.setup();
    renderPanel();

    const satir = (await screen.findByText("Mehmet Demir")).closest("tr") as HTMLElement;
    await user.click(within(satir).getByRole("button", { name: "Çıkar" }));
    const dialog = await screen.findByRole("dialog", { name: "Öğrenci listeden çıkarılsın mı?" });
    await user.click(within(dialog).getByRole("button", { name: "Vazgeç" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(iep.remove).not.toHaveBeenCalled();
  });

  it("“Tüm kayıtları sil” onaydan geçer ve geri alınamayacağını söyler", async () => {
    const user = userEvent.setup();
    iep.deleteAll.mockResolvedValue({ students: 2, documents: 3 });
    renderPanel();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Tüm kayıtları sil" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Tüm BEP ve tedbir kayıtları silinsin mi?",
    });
    expect(dialog).toHaveTextContent(
      "Listedeki bütün öğrenciler, tedbirleri ve bütün oturumlardaki bireysel soru dosyaları kalıcı olarak silinir. Bu işlem geri alınamaz.",
    );
    expect(iep.deleteAll).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole("button", { name: "Sil" }));

    await waitFor(() => expect(iep.deleteAll).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("BEP ve tedbir kayıtları silindi.")).toBeInTheDocument();
  });

  it("silme başarısız olursa hata bildirilir", async () => {
    const user = userEvent.setup();
    iep.deleteAll.mockRejectedValue(new Error("ağ koptu"));
    renderPanel();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Tüm kayıtları sil" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Tüm BEP ve tedbir kayıtları silinsin mi?",
    });
    await user.click(within(dialog).getByRole("button", { name: "Sil" }));

    expect(await screen.findByText("Kayıtlar silinemedi.")).toBeInTheDocument();
  });
});

describe("BepListesiPaneli — uygulama parolası uyarısı", () => {
  it("parola kapalıyken uyarı bandı görünür ve Ayarlar → Güvenlik'e bağlanır", async () => {
    guvenlik.durum.mockResolvedValue(durum(false));
    renderPanel();

    const bant = await screen.findByRole("status", { name: "Uygulama parolası kapalı" });
    expect(within(bant).getByRole("link", { name: "Ayarlar → Güvenlik" })).toHaveAttribute(
      "href",
      "/ayarlar?tab=guvenlik",
    );
  });

  it("parola açıkken uyarı bandı çizilmez", async () => {
    renderPanel();
    await screen.findByText("Ayşe Yılmaz");

    await waitFor(() => expect(guvenlik.durum).toHaveBeenCalled());
    expect(
      screen.queryByRole("status", { name: "Uygulama parolası kapalı" }),
    ).not.toBeInTheDocument();
  });

  it("güvenlik durumu okunamazsa sessiz kalır (bant da hata da yok)", async () => {
    guvenlik.durum.mockRejectedValue(new ApiError(500, "server_error", "Durum okunamadı."));
    renderPanel();
    await screen.findByText("Ayşe Yılmaz");

    await waitFor(() => expect(guvenlik.durum).toHaveBeenCalled());
    expect(
      screen.queryByRole("status", { name: "Uygulama parolası kapalı" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Durum okunamadı.")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
