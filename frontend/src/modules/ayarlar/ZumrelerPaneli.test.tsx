// Ayarlar → Zümreler paneli testleri: zümre ekleme, başkanın PERSONEL
// listesinden seçilmesi (yalnız aktif personel) ve kaldırma onayı.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";

const okulApiMock = vi.hoisted(() => ({
  listSubjectDepartments: vi.fn(),
  createSubjectDepartment: vi.fn(),
  updateSubjectDepartment: vi.fn(),
  deleteSubjectDepartment: vi.fn(),
  listPersonnel: vi.fn(),
}));

vi.mock("../okul/api", async (importActual) => {
  const actual = await importActual<typeof import("../okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...okulApiMock } };
});

import ZumrelerPaneli from "./ZumrelerPaneli";

function personelSayfasi() {
  return {
    count: 2,
    next: null,
    previous: null,
    results: [
      {
        id: 8,
        first_name: "Ayşe",
        last_name: "ÇELİK",
        title: "Öğretmen",
        branch: "Coğrafya",
        is_active: true,
        full_name: "Ayşe ÇELİK",
      },
      {
        id: 9,
        first_name: "Bora",
        last_name: "ARSLAN",
        title: "Öğretmen",
        branch: "Matematik",
        is_active: true,
        full_name: "Bora ARSLAN",
      },
    ],
  };
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

afterEach(() => vi.clearAllMocks());

describe("ZumrelerPaneli", () => {
  it("başkan seçenekleri YALNIZ aktif personelden gelir", async () => {
    okulApiMock.listSubjectDepartments.mockResolvedValue([]);
    okulApiMock.listPersonnel.mockResolvedValue(personelSayfasi());
    renderPanel();

    await waitFor(() =>
      // limit=500 şart: DRF varsayılan sayfası 25, liste sessizce kesilmemeli.
      expect(okulApiMock.listPersonnel).toHaveBeenCalledWith({ onlyActive: true, limit: 500 }),
    );
    expect(await screen.findByText("Ayşe ÇELİK — Coğrafya")).toBeInTheDocument();
  });

  it("zümre adı ve başkanıyla eklenir", async () => {
    const user = userEvent.setup();
    okulApiMock.listSubjectDepartments.mockResolvedValue([]);
    okulApiMock.listPersonnel.mockResolvedValue(personelSayfasi());
    okulApiMock.createSubjectDepartment.mockResolvedValue({
      id: 3,
      name: "Sosyal Bilimler",
      head: 8,
      head_name: "Ayşe ÇELİK",
      is_board_member: true,
    });
    renderPanel();

    await user.type(await screen.findByLabelText("Zümre adı"), "Sosyal Bilimler");
    await user.selectOptions(screen.getByLabelText("Zümre başkanı"), "8");
    await user.click(screen.getByRole("button", { name: /Zümre ekle/ }));

    await waitFor(() =>
      expect(okulApiMock.createSubjectDepartment).toHaveBeenCalledWith({
        name: "Sosyal Bilimler",
        head: 8,
      }),
    );
  });

  it("kayıtlı zümre listelenir ve onaydan sonra kaldırılır", async () => {
    const user = userEvent.setup();
    okulApiMock.listSubjectDepartments.mockResolvedValue([
      { id: 3, name: "Sosyal Bilimler", head: 8, head_name: "Ayşe ÇELİK", is_board_member: true },
    ]);
    okulApiMock.listPersonnel.mockResolvedValue(personelSayfasi());
    okulApiMock.deleteSubjectDepartment.mockResolvedValue(undefined);
    renderPanel();

    await user.click(
      await screen.findByRole("button", { name: "Sosyal Bilimler zümresini kaldır" }),
    );
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Kaldır" }));

    await waitFor(() => expect(okulApiMock.deleteSubjectDepartment).toHaveBeenCalledWith(3));
  });
});
