// Ayarlar → Zümreler paneli testleri: zümre ekleme, başkanın PERSONEL
// listesinden seçilmesi (yalnız aktif personel) ve kaldırma onayı.
// 20.09.2026: branşlardan zümre üretimi, branş düzenleme ve başkan adaylarının
// zümrenin branşlarına göre süzülmesi. Fixture'lardaki adlar UYDURMADIR.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";

const okulApiMock = vi.hoisted(() => ({
  listSubjectDepartments: vi.fn(),
  createSubjectDepartment: vi.fn(),
  updateSubjectDepartment: vi.fn(),
  deleteSubjectDepartment: vi.fn(),
  listPersonnel: vi.fn(),
  listBranchCandidates: vi.fn(),
  generateDepartments: vi.fn(),
}));

vi.mock("../okul/api", async (importActual) => {
  const actual = await importActual<typeof import("../okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...okulApiMock } };
});

import ZumrelerPaneli from "./ZumrelerPaneli";

function personelSayfasi() {
  return {
    count: 3,
    next: null,
    previous: null,
    results: [
      {
        id: 8,
        first_name: "Ayşe",
        last_name: "ÇELİK",
        title: "Öğretmen",
        branch: "Coğrafya",
        branch_key: "cografya",
        is_active: true,
        full_name: "Ayşe ÇELİK",
      },
      {
        id: 9,
        first_name: "Bora",
        last_name: "ARSLAN",
        title: "Öğretmen",
        branch: "Matematik",
        branch_key: "matematik",
        is_active: true,
        full_name: "Bora ARSLAN",
      },
      {
        id: 10,
        first_name: "Cem",
        last_name: "KAYA",
        title: "Öğretmen",
        branch: "COĞRAFYA", // yazım farklı, ANAHTAR aynı → aynı branş
        branch_key: "cografya",
        is_active: true,
        full_name: "Cem KAYA",
      },
    ],
  };
}

function zumre(overrides: Record<string, unknown> = {}) {
  return {
    id: 3,
    name: "Sosyal Bilimler",
    head: 8,
    head_name: "Ayşe ÇELİK",
    is_board_member: true,
    branches: [],
    branch_keys: [],
    ...overrides,
  };
}

function adaylar() {
  return [
    {
      key: "cografya",
      name: "Coğrafya",
      teacher_count: 2,
      status: "COVERED",
      department_id: 3,
      department_name: "Sosyal Bilimler",
    },
    {
      key: "matematik",
      name: "Matematik",
      teacher_count: 1,
      status: "NEW",
      department_id: null,
      department_name: "",
    },
    {
      key: "fizik",
      name: "Fizik",
      teacher_count: 2,
      status: "LINKABLE",
      department_id: 5,
      department_name: "Fizik",
    },
  ];
}

function renderPanel() {
  return render(
    <SnackbarProvider>
      <ConfirmProvider>
        <ZumrelerPaneli />
      </ConfirmProvider>
    </SnackbarProvider>,
  );
}

beforeEach(() => {
  okulApiMock.listSubjectDepartments.mockResolvedValue([]);
  okulApiMock.listPersonnel.mockResolvedValue(personelSayfasi());
  okulApiMock.listBranchCandidates.mockResolvedValue([]);
});
afterEach(() => vi.clearAllMocks());

describe("ZumrelerPaneli", () => {
  it("başkan seçenekleri YALNIZ aktif personelden gelir", async () => {
    renderPanel();

    await waitFor(() =>
      // limit=500 şart: DRF varsayılan sayfası 25, liste sessizce kesilmemeli.
      expect(okulApiMock.listPersonnel).toHaveBeenCalledWith({ onlyActive: true, limit: 500 }),
    );
    expect(await screen.findByText("Ayşe ÇELİK — Coğrafya")).toBeInTheDocument();
  });

  it("zümre adı ve başkanıyla eklenir", async () => {
    const user = userEvent.setup();
    okulApiMock.createSubjectDepartment.mockResolvedValue(zumre());
    renderPanel();

    await user.type(await screen.findByLabelText("Zümre adı"), "Sosyal Bilimler");
    await user.selectOptions(screen.getByLabelText("Zümre başkanı"), "8");
    await user.click(screen.getByRole("button", { name: /Zümre ekle/ }));

    await waitFor(() =>
      // Branş seçilmediyse gövdede `branches` anahtarı HİÇ yoktur.
      expect(okulApiMock.createSubjectDepartment).toHaveBeenCalledWith({
        name: "Sosyal Bilimler",
        head: 8,
      }),
    );
  });

  it("eklerken branş seçilirse başkan adayları o branşa iner ve branş kaydedilir", async () => {
    const user = userEvent.setup();
    okulApiMock.listBranchCandidates.mockResolvedValue(adaylar());
    okulApiMock.createSubjectDepartment.mockResolvedValue(zumre());
    renderPanel();

    await user.type(await screen.findByLabelText("Zümre adı"), "Matematik");
    const brans = screen.getByLabelText("Branş");
    // Branşı zaten bir zümrede olan aday (Coğrafya) seçenek DEĞİLDİR.
    await within(brans).findByRole("option", { name: "Matematik" });
    expect(within(brans).queryByRole("option", { name: "Coğrafya" })).toBeNull();
    await user.selectOptions(brans, "matematik");

    const baskan = screen.getByLabelText("Zümre başkanı");
    expect(within(baskan).getByRole("option", { name: "Bora ARSLAN — Matematik" })).toBeDefined();
    expect(within(baskan).queryByRole("option", { name: "Ayşe ÇELİK — Coğrafya" })).toBeNull();
    await user.selectOptions(baskan, "9");
    await user.click(screen.getByRole("button", { name: /Zümre ekle/ }));

    await waitFor(() =>
      expect(okulApiMock.createSubjectDepartment).toHaveBeenCalledWith({
        name: "Matematik",
        head: 9,
        branches: ["Matematik"],
      }),
    );
  });

  it("kayıtlı zümre listelenir ve onaydan sonra kaldırılır", async () => {
    const user = userEvent.setup();
    okulApiMock.listSubjectDepartments.mockResolvedValue([zumre()]);
    okulApiMock.deleteSubjectDepartment.mockResolvedValue(undefined);
    renderPanel();

    await user.click(
      await screen.findByRole("button", { name: "Sosyal Bilimler zümresini kaldır" }),
    );
    // Başlık soru, gövde sonuç; "personel" değil "öğretmen" (docs/sozluk.md).
    const dialog = await screen.findByRole("dialog", { name: "Zümre kaldırılsın mı?" });
    expect(within(dialog).getByText(/Öğretmen kayıtları etkilenmez/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Kaldır" }));

    await waitFor(() => expect(okulApiMock.deleteSubjectDepartment).toHaveBeenCalledWith(3));
  });

  it("satırdan başkan değişimi sessiz geçmez — kaydedildiği bildirilir", async () => {
    const user = userEvent.setup();
    okulApiMock.listSubjectDepartments.mockResolvedValue([zumre()]);
    okulApiMock.updateSubjectDepartment.mockResolvedValue({});
    renderPanel();

    const secici = await screen.findByRole("combobox", { name: "Sosyal Bilimler zümre başkanı" });
    // Boş seçenek tek biçimdir ("— seçilmedi —" kalktı).
    expect(within(secici).getByRole("option", { name: "— yok —" })).toBeDefined();
    // Öğretmen listesi zümrelerden ayrı yüklenir — seçenek gelene dek beklenir.
    // Branşı tanımsız zümrede aday BÜTÜN öğretmenlerdir (eski davranış).
    await within(secici).findByRole("option", { name: "Bora ARSLAN — Matematik" });
    await user.selectOptions(secici, "9");

    await waitFor(() =>
      expect(okulApiMock.updateSubjectDepartment).toHaveBeenCalledWith(3, { head: 9 }),
    );
    expect(
      await screen.findByText("“Sosyal Bilimler” zümresinin başkanı güncellendi."),
    ).toBeInTheDocument();
  });

  it("başkan “— yok —” yapılınca kaldırıldığı bildirilir", async () => {
    const user = userEvent.setup();
    okulApiMock.listSubjectDepartments.mockResolvedValue([zumre()]);
    okulApiMock.updateSubjectDepartment.mockResolvedValue({});
    renderPanel();

    await user.selectOptions(
      await screen.findByRole("combobox", { name: "Sosyal Bilimler zümre başkanı" }),
      "",
    );

    await waitFor(() =>
      expect(okulApiMock.updateSubjectDepartment).toHaveBeenCalledWith(3, { head: null }),
    );
    expect(
      await screen.findByText("“Sosyal Bilimler” zümresinin başkanı kaldırıldı."),
    ).toBeInTheDocument();
  });

  it("başkan adayları zümrenin branşındaki öğretmenlerdir; istenirse hepsi gösterilir", async () => {
    const user = userEvent.setup();
    okulApiMock.listSubjectDepartments.mockResolvedValue([
      zumre({
        name: "Coğrafya",
        head: null,
        head_name: "",
        branches: ["Coğrafya"],
        branch_keys: ["cografya"],
      }),
    ]);
    renderPanel();

    const secici = await screen.findByRole("combobox", { name: "Coğrafya zümre başkanı" });
    // Yazımı farklı ("COĞRAFYA") öğretmen de aynı branştır — eşleşme anahtar üzerinden.
    await within(secici).findByRole("option", { name: "Cem KAYA — COĞRAFYA" });
    expect(within(secici).getByRole("option", { name: "Ayşe ÇELİK — Coğrafya" })).toBeDefined();
    expect(within(secici).queryByRole("option", { name: "Bora ARSLAN — Matematik" })).toBeNull();
    expect(screen.getByText("Branş: Coğrafya")).toBeInTheDocument();

    await user.click(screen.getByLabelText("Başkan adaylarında tüm öğretmenleri göster"));
    expect(within(secici).getByRole("option", { name: "Bora ARSLAN — Matematik" })).toBeDefined();
  });

  it("kayıtlı başkan başka branştansa seçenek olarak korunur ve etiketlenir", async () => {
    okulApiMock.listSubjectDepartments.mockResolvedValue([
      zumre({
        name: "Coğrafya",
        head: 9,
        head_name: "Bora ARSLAN",
        branch_keys: ["cografya"],
        branches: ["Coğrafya"],
      }),
      zumre({
        id: 4,
        name: "Fizik",
        head: 77,
        head_name: "Eski BAŞKAN",
        branch_keys: ["fizik"],
        branches: ["Fizik"],
      }),
    ]);
    renderPanel();

    const cografya = await screen.findByRole("combobox", { name: "Coğrafya zümre başkanı" });
    await within(cografya).findByRole("option", { name: "Bora ARSLAN — Matematik (başka branş)" });
    expect(cografya).toHaveValue("9");
    // Sicilde artık olmayan (pasif/silinmiş) başkan ayrı etiket alır.
    const fizik = screen.getByRole("combobox", { name: "Fizik zümre başkanı" });
    expect(within(fizik).getByRole("option", { name: "Eski BAŞKAN (listede yok)" })).toBeDefined();
  });

  it("branşlardan üretim: adaylar durumlarıyla listelenir, seçilenler üretilir", async () => {
    const user = userEvent.setup();
    okulApiMock.listBranchCandidates.mockResolvedValue(adaylar());
    okulApiMock.generateDepartments.mockResolvedValue({
      created: ["Matematik"],
      linked: ["Fizik"],
      skipped: [],
    });
    renderPanel();

    // Düğme kaç YENİ aday olduğunu söyler (branşı zaten zümrede olan sayılmaz).
    await user.click(
      await screen.findByRole("button", { name: "Branşlardan zümre üret (2 yeni)" }),
    );
    const dialog = await screen.findByRole("dialog", { name: "Branşlardan zümre üret" });
    const kapsanmis = within(dialog).getByRole("checkbox", { name: /Coğrafya/ });
    expect(kapsanmis).toBeDisabled();
    expect(kapsanmis).not.toBeChecked();
    expect(within(dialog).getByText(/“Sosyal Bilimler” zümresinde/)).toBeInTheDocument();
    expect(within(dialog).getByRole("checkbox", { name: /Matematik/ })).toBeChecked();
    expect(within(dialog).getByText(/zümresi var — branşı ona bağlanır/)).toBeInTheDocument();

    // İstenmeyen branşın işareti kaldırılır → yalnız kalanlar gönderilir.
    await user.click(within(dialog).getByRole("checkbox", { name: /Fizik/ }));
    await user.click(within(dialog).getByRole("button", { name: "Seçilenleri üret (1)" }));

    await waitFor(() =>
      expect(okulApiMock.generateDepartments).toHaveBeenCalledWith(["matematik"]),
    );
    expect(
      await screen.findByText("1 zümre oluşturuldu, 1 zümreye branşı bağlandı."),
    ).toBeInTheDocument();
    // Liste ve adaylar üretimden sonra yeniden okunur.
    await waitFor(() => expect(okulApiMock.listSubjectDepartments).toHaveBeenCalledTimes(2));
  });

  it("öğretmen listesinde branş yoksa üretim düğmesi kapalıdır ve nedeni yazar", async () => {
    renderPanel();
    expect(await screen.findByRole("button", { name: "Branşlardan zümre üret" })).toBeDisabled();
    expect(await screen.findByText(/Öğretmen listesinde branş bilgisi yok/)).toBeInTheDocument();
  });

  it("üretim hatası bildirilir ve pencere açık kalır", async () => {
    const user = userEvent.setup();
    okulApiMock.listBranchCandidates.mockResolvedValue(adaylar());
    okulApiMock.generateDepartments.mockRejectedValue(new Error("ağ"));
    renderPanel();

    await user.click(await screen.findByRole("button", { name: /Branşlardan zümre üret/ }));
    const dialog = await screen.findByRole("dialog", { name: "Branşlardan zümre üret" });
    await user.click(within(dialog).getByRole("button", { name: /Seçilenleri üret/ }));

    expect(await screen.findByText("Zümreler üretilemedi.")).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "Branşlardan zümre üret" })).toBeInTheDocument();
  });

  it("branş düzenleme: başka zümrenin branşı kilitli, seçim ADLARIYLA kaydedilir", async () => {
    const user = userEvent.setup();
    okulApiMock.listSubjectDepartments.mockResolvedValue([
      zumre({
        id: 7,
        name: "Fen Bilimleri",
        head: null,
        head_name: "",
        branches: ["Kimya"],
        branch_keys: ["kimya"],
      }),
    ]);
    okulApiMock.listBranchCandidates.mockResolvedValue(adaylar());
    okulApiMock.updateSubjectDepartment.mockResolvedValue({});
    renderPanel();

    await user.click(
      await screen.findByRole("button", { name: "Fen Bilimleri zümresinin branşlarını düzenle" }),
    );
    const dialog = await screen.findByRole("dialog", { name: "Branşlar — Fen Bilimleri" });
    // Başka zümredeki branş seçilemez; zümrenin sicilde olmayan kendi branşı listede KALIR.
    expect(within(dialog).getByRole("checkbox", { name: /Coğrafya/ })).toBeDisabled();
    const kimya = within(dialog).getByRole("checkbox", { name: /Kimya/ });
    expect(kimya).toBeChecked();
    expect(within(dialog).getByText("öğretmen listesinde yok")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("checkbox", { name: /Fizik/ }));
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(okulApiMock.updateSubjectDepartment).toHaveBeenCalledWith(7, {
        branches: ["Fizik", "Kimya"],
      }),
    );
    expect(
      await screen.findByText("“Fen Bilimleri” zümresinin branşları güncellendi."),
    ).toBeInTheDocument();
  });
});
