// BEP kapsamındaki öğrenciler listesi testleri (20.09.2026): liste + boş durum,
// Autocomplete ile ekleme, çıkarma onayı (SATIR kimliğiyle siler; onay ve
// bildirim metninde öğrenci adı ve okul numarası YOK), "Tüm BEP kayıtlarını sil"
// ve uygulama parolası uyarısı (kapalıyken görünür, açıkken/okunamazsa gizli).
// KVKK: fixture'lardaki ad ve numaralar UYDURMADIR.

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
  remove: vi.fn(),
  deleteAll: vi.fn(),
}));
const okulApiMock = vi.hoisted(() => ({ listStudents: vi.fn() }));
const guvenlik = vi.hoisted(() => ({ durum: vi.fn() }));

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

import BepListesiPaneli from "./BepListesiPaneli";

// Satır kimliği (id) ile öğrenci pk'si (student_id) BİLEREK farklıdır: silme
// satır kimliğiyle yapılır; öğrenci pk'si yola hiç girmez.
const AYSE: IepStudent = {
  id: 7,
  student_id: 301,
  student_number: "101",
  full_name: "Ayşe Yılmaz",
  class_label: "9/A",
};
const MEHMET: IepStudent = {
  id: 8,
  student_id: 302,
  student_number: "102",
  full_name: "Mehmet Demir",
  class_label: "9/B",
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
  status: "ACTIVE",
};

function durum(passwordSet: boolean): GuvenlikDurumu {
  return {
    password_set: passwordSet,
    locked: false,
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
  it("listeyi okul no, ad soyad ve şubeyle gösterir; yalnız üyelik tutulduğunu söyler", async () => {
    renderPanel();

    const satir = (await screen.findByText("Ayşe Yılmaz")).closest("tr") as HTMLElement;
    expect(within(satir).getByText("101")).toBeInTheDocument();
    expect(within(satir).getByText("9/A")).toBeInTheDocument();
    expect(screen.getByText("Mehmet Demir")).toBeInTheDocument();
    expect(screen.getByText("2 öğrenci")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Şube" })).toBeInTheDocument();
    // KVKK md. 6: tanı/rapor/açıklama kaydedilmez; evrak ve kitapçıkta işaret yok.
    expect(screen.getByText("tanı, rapor ya da açıklama kaydedilmez")).toBeInTheDocument();
    expect(
      screen.getByText(/kitapçıklarda öğrenciyi ayıran hiçbir işaret\s+basılmaz/),
    ).toBeInTheDocument();
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

  it("öğrenci ekleme: aramadan seçilir, student_id ile gönderilir ve liste tazelenir", async () => {
    const user = userEvent.setup();
    okulApiMock.listStudents.mockResolvedValue(ogrenciSayfasi([ZEYNEP]));
    iep.add.mockResolvedValue({ id: 9 });
    renderPanel();
    await screen.findByText("Ayşe Yılmaz");

    // Seçim yokken ekleme kapalıdır.
    expect(screen.getByRole("button", { name: "Listeye ekle" })).toBeDisabled();
    await user.type(screen.getByLabelText("Öğrenci ekle"), "Zey");
    // Autocomplete etiketi vurguyla parçalara bölünür → metinle değil ROL ile seçilir.
    const listbox = await screen.findByRole("listbox");
    await user.click(within(listbox).getAllByRole("option")[0]);
    expect(okulApiMock.listStudents).toHaveBeenCalledWith({
      search: "Zey",
      onlyActive: true,
      limit: 20,
    });

    const cagriOncesi = iep.list.mock.calls.length;
    await user.click(screen.getByRole("button", { name: "Listeye ekle" }));

    await waitFor(() => expect(iep.add).toHaveBeenCalledWith(303));
    // Bildirimde öğrenci adı ve okul numarası geçmez.
    expect(await screen.findByText("Öğrenci listeye eklendi.")).toBeInTheDocument();
    await waitFor(() => expect(iep.list.mock.calls.length).toBeGreaterThan(cagriOncesi));
    // Arama kutusu boşalır: aynı öğrenci yeniden aranmaz, düğme yeniden kapanır.
    expect(screen.getByLabelText("Öğrenci ekle")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Listeye ekle" })).toBeDisabled();
  });

  it("zaten listedeki öğrenci aramada görünür ama seçilemez", async () => {
    const user = userEvent.setup();
    okulApiMock.listStudents.mockResolvedValue(
      ogrenciSayfasi([{ ...ZEYNEP, id: 301, full_name: "Ayşe Yılmaz", student_number: "101" }]),
    );
    renderPanel();
    await screen.findByText("Ayşe Yılmaz");

    await user.type(screen.getByLabelText("Öğrenci ekle"), "Ayş");
    const secenek = within(await screen.findByRole("listbox")).getAllByRole("option")[0];
    expect(secenek).toHaveAttribute("aria-disabled", "true");
    expect(secenek).toHaveTextContent("zaten listede");
    await user.click(secenek);

    expect(screen.getByRole("button", { name: "Listeye ekle" })).toBeDisabled();
    expect(iep.add).not.toHaveBeenCalled();
  });

  it("ekleme reddedilirse backend gerekçesi bildirilir", async () => {
    const user = userEvent.setup();
    okulApiMock.listStudents.mockResolvedValue(ogrenciSayfasi([ZEYNEP]));
    iep.add.mockRejectedValue(new ApiError(400, "validation_error", "Bu öğrenci zaten listede."));
    renderPanel();
    await screen.findByText("Ayşe Yılmaz");

    await user.type(screen.getByLabelText("Öğrenci ekle"), "Zey");
    await user.click(within(await screen.findByRole("listbox")).getAllByRole("option")[0]);
    await user.click(screen.getByRole("button", { name: "Listeye ekle" }));

    expect(await screen.findByText("Bu öğrenci zaten listede.")).toBeInTheDocument();
  });

  it("çıkarma onayı: başlık soru, gövde sonuç — metinde öğrenci adı ve okul numarası yok", async () => {
    const user = userEvent.setup();
    iep.remove.mockResolvedValue(undefined);
    renderPanel();

    const satir = (await screen.findByText("Ayşe Yılmaz")).closest("tr") as HTMLElement;
    await user.click(within(satir).getByRole("button", { name: "Çıkar" }));

    // Tek tıkla çıkarılmaz (bireysel soru dosyaları da silinir).
    expect(iep.remove).not.toHaveBeenCalled();
    const dialog = await screen.findByRole("dialog", { name: "Öğrenci listeden çıkarılsın mı?" });
    expect(dialog).toHaveTextContent(
      "Bu öğrenci BEP kapsamındaki öğrenciler listesinden çıkarılır; onaylanmamış oturumlardaki bireysel soru dosyaları da silinir.",
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

  it("“Tüm BEP kayıtlarını sil” onaydan geçer ve geri alınamayacağını söyler", async () => {
    const user = userEvent.setup();
    iep.deleteAll.mockResolvedValue({ students: 2, documents: 3 });
    renderPanel();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Tüm BEP kayıtlarını sil" }));
    const dialog = await screen.findByRole("dialog", { name: "Tüm BEP kayıtları silinsin mi?" });
    expect(dialog).toHaveTextContent(
      "Listedeki bütün öğrenciler ve bütün oturumlardaki bireysel soru dosyaları kalıcı olarak silinir. Bu işlem geri alınamaz.",
    );
    expect(iep.deleteAll).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole("button", { name: "Sil" }));

    await waitFor(() => expect(iep.deleteAll).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("BEP kayıtları silindi.")).toBeInTheDocument();
  });

  it("silme başarısız olursa hata bildirilir", async () => {
    const user = userEvent.setup();
    iep.deleteAll.mockRejectedValue(new Error("ağ koptu"));
    renderPanel();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Tüm BEP kayıtlarını sil" }));
    const dialog = await screen.findByRole("dialog", { name: "Tüm BEP kayıtları silinsin mi?" });
    await user.click(within(dialog).getByRole("button", { name: "Sil" }));

    expect(await screen.findByText("BEP kayıtları silinemedi.")).toBeInTheDocument();
  });
});

describe("BepListesiPaneli — uygulama parolası uyarısı", () => {
  it("parola kapalıyken uyarı bandı görünür ve Ayarlar → Güvenlik'e bağlanır", async () => {
    guvenlik.durum.mockResolvedValue(durum(false));
    renderPanel();

    const bant = await screen.findByRole("status", { name: "Uygulama parolası kapalı" });
    expect(bant).toHaveTextContent(
      "Uygulama parolası kapalı: BEP bilgisi bu bilgisayarda ve yedeklerde şifresiz saklanıyor. Bu bilgi özel nitelikli kişisel veridir (KVKK md. 6); Ayarlar → Güvenlik bölümünden parola koymanız önerilir.",
    );
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
