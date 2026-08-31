// Ayarlar → Şube Kümeleri testleri (Ö2).
// Sabitlenen: küme ekleme ve TOPLU atama (asıl seçim maliyetini düşüren yol);
// "— kümesiz —" seçimi group=null gönderir.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";

const okulApiMock = vi.hoisted(() => ({
  listClassSectionGroups: vi.fn(),
  listClassSections: vi.fn(),
  createClassSectionGroup: vi.fn(),
  deleteClassSectionGroup: vi.fn(),
  assignClassSectionGroup: vi.fn(),
}));

vi.mock("../okul/api", async (importActual) => {
  const actual = await importActual<typeof import("../okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...okulApiMock } };
});

import SubeKumeleriPaneli from "./SubeKumeleriPaneli";

function sube(id: number, label: string, group: number | null = null, groupName = "") {
  return {
    id,
    school_year: 1,
    school_year_name: "2026-2027",
    class_level: Number(label.split("/")[0]),
    class_section: label.split("/")[1],
    class_label: label,
    group,
    group_name: groupName,
  };
}

function renderPanel() {
  return render(
    <SnackbarProvider>
      <ConfirmProvider>
        <SubeKumeleriPaneli />
      </ConfirmProvider>
    </SnackbarProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("SubeKumeleriPaneli", () => {
  it("küme adıyla eklenir", async () => {
    const user = userEvent.setup();
    okulApiMock.listClassSectionGroups.mockResolvedValue([]);
    okulApiMock.listClassSections.mockResolvedValue([]);
    okulApiMock.createClassSectionGroup.mockResolvedValue({
      id: 1,
      name: "Sayısal",
      order: 0,
      section_count: 0,
    });
    renderPanel();

    await user.type(await screen.findByLabelText("Küme adı"), "Sayısal");
    await user.click(screen.getByRole("button", { name: /Küme ekle/ }));

    await waitFor(() =>
      expect(okulApiMock.createClassSectionGroup).toHaveBeenCalledWith({ name: "Sayısal" }),
    );
  });

  it("işaretlenen şubeler topluca kümeye atanır", async () => {
    const user = userEvent.setup();
    okulApiMock.listClassSectionGroups.mockResolvedValue([
      { id: 3, name: "Eşit Ağırlık", order: 0, section_count: 0 },
    ]);
    okulApiMock.listClassSections.mockResolvedValue([sube(11, "11/A"), sube(12, "11/B")]);
    okulApiMock.assignClassSectionGroup.mockResolvedValue({ updated: 2 });
    renderPanel();

    await user.click(await screen.findByRole("checkbox", { name: /11\/A/ }));
    await user.click(screen.getByRole("checkbox", { name: /11\/B/ }));
    await user.selectOptions(screen.getByLabelText("Küme"), "3");
    await user.click(screen.getByRole("button", { name: /^Ata \(/ }));

    await waitFor(() =>
      expect(okulApiMock.assignClassSectionGroup).toHaveBeenCalledWith({
        section_ids: [11, 12],
        group: 3,
      }),
    );
  });

  it("'— kümesiz —' seçilince group null gönderilir", async () => {
    const user = userEvent.setup();
    okulApiMock.listClassSectionGroups.mockResolvedValue([
      { id: 3, name: "Sayısal", order: 0, section_count: 1 },
    ]);
    okulApiMock.listClassSections.mockResolvedValue([sube(11, "11/A", 3, "Sayısal")]);
    okulApiMock.assignClassSectionGroup.mockResolvedValue({ updated: 1 });
    renderPanel();

    await user.click(await screen.findByRole("checkbox", { name: /11\/A/ }));
    await user.click(screen.getByRole("button", { name: /^Ata \(/ }));

    await waitFor(() =>
      expect(okulApiMock.assignClassSectionGroup).toHaveBeenCalledWith({
        section_ids: [11],
        group: null,
      }),
    );
  });
});
