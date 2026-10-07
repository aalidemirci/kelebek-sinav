// Tedbir penceresi (07.10.2026): okul numaralarıyla toplu ekleme, yer tedbirinin
// alanları (ayrı salon → salon zorunlu; salon içi tercih; tek başına), okuyucu/yazıcı
// için ayrı salon önerisi, BEP dışı gerekçede en az bir tedbir şartı ve düzenleme.
// KVKK: ad ve numaralar uydurmadır; bildirimlerde öğrenci adı geçmez.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { IepStudent } from "./api";

const iep = vi.hoisted(() => ({
  add: vi.fn(() => Promise.resolve({ id: 1 })),
  update: vi.fn(() => Promise.resolve({ id: 1 })),
  addByNumbers: vi.fn(() => Promise.resolve({ added: 2, already: 1, not_found: ["999"] })),
}));
const salonApi = vi.hoisted(() => ({
  list: vi.fn(() =>
    Promise.resolve({
      count: 1,
      next: null,
      previous: null,
      results: [{ id: 5, name: "Rehberlik", group_name: "" }],
    }),
  ),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, iepApi: { ...actual.iepApi, ...iep } };
});
vi.mock("../salonlar/api", async (importActual) => {
  const actual = await importActual<typeof import("../salonlar/api")>();
  return { ...actual, examRoomApi: { ...actual.examRoomApi, ...salonApi } };
});

import TedbirDialog from "./TedbirDialog";

const SATIR: IepStudent = {
  id: 8,
  student_id: 302,
  student_number: "102",
  full_name: "Mehmet Demir",
  class_label: "9/B",
  reason_category: "DISABILITY",
  reason_label: "Engel durumu",
  placement: "HOME_CLASSROOM",
  target_room_id: null,
  seat_preference: "BACK",
  solo_desk: true,
  extra_minutes: 0,
  reader: false,
  scribe: false,
  measures: ["Kendi sınıfında", "arka sıra", "sırada tek başına"],
};

function renderDialog(row: IepStudent | null = null, onSaved = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <TedbirDialog row={row} onClose={vi.fn()} onSaved={onSaved} />
      </SnackbarProvider>
    </QueryClientProvider>,
  );
  return { onSaved };
}

afterEach(() => vi.clearAllMocks());

describe("TedbirDialog", () => {
  it("okul numaralarıyla toplu ekler; sonuç sayıyla ve bulunamayan numarayla söylenir", async () => {
    const user = userEvent.setup();
    const { onSaved } = renderDialog();

    await user.click(screen.getByRole("radio", { name: "Okul numaralarıyla toplu" }));
    await user.type(screen.getByRole("textbox", { name: "Okul numaraları" }), "101 102, 999");
    await user.selectOptions(screen.getByLabelText("Gerekçe"), "HEALTH");
    // Sağlık gerekçesinde tedbir yokken kayıt kapalıdır.
    expect(screen.getByText(/en az bir tedbir seçin/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kaydet" })).toBeDisabled();
    await user.clear(screen.getByLabelText("Ek süre (dakika)"));
    await user.type(screen.getByLabelText("Ek süre (dakika)"), "15");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(iep.addByNumbers).toHaveBeenCalledWith("101 102, 999", {
        reason_category: "HEALTH",
        placement: "NONE",
        target_room_id: null,
        seat_preference: "NONE",
        solo_desk: false,
        extra_minutes: 15,
        reader: false,
        scribe: false,
      }),
    );
    expect(
      await screen.findByText(
        "2 öğrenci eklendi; 1 öğrenci zaten listedeydi; bu numaralarla aktif öğrenci yok: 999.",
      ),
    ).toBeInTheDocument();
    expect(onSaved).toHaveBeenCalled();
  });

  it("ayrı salon salon ister; salon içi tercih ve tek başına seçilebilir", async () => {
    const user = userEvent.setup();
    renderDialog(SATIR);

    await user.selectOptions(screen.getByLabelText("Sınava nerede girsin?"), "SEPARATE_ROOM");
    expect(screen.getByText("“Ayrı salon” için salon seçin.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kaydet" })).toBeDisabled();
    await waitFor(() => expect(salonApi.list).toHaveBeenCalled());
    await user.selectOptions(await screen.findByLabelText("Salon"), "5");
    expect(screen.getByLabelText("Salon içinde")).toHaveValue("BACK");
    expect(screen.getByRole("checkbox", { name: "Sırada tek başına otursun" })).toBeChecked();
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(iep.update).toHaveBeenCalledWith(
        8,
        expect.objectContaining({ placement: "SEPARATE_ROOM", target_room_id: 5, solo_desk: true }),
      ),
    );
  });

  it("yer kaldırılınca salon içi tercih ve tek başına sıfırlanır", async () => {
    const user = userEvent.setup();
    renderDialog(SATIR);

    await user.selectOptions(screen.getByLabelText("Sınava nerede girsin?"), "NONE");
    expect(screen.queryByLabelText("Salon içinde")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("checkbox", { name: "Sırada tek başına otursun" }),
    ).not.toBeInTheDocument();
    // Engel durumu gerekçesinde yer de kalmayınca en az bir tedbir istenir.
    expect(screen.getByRole("button", { name: "Kaydet" })).toBeDisabled();
  });

  it("okuyucu/yazıcı desteğinde ayrı salon önerilir ve tek tıkla seçilir", async () => {
    const user = userEvent.setup();
    renderDialog();

    await user.click(screen.getByRole("checkbox", { name: "Okuyucu desteği" }));
    const oneri = screen.getByText(/“Ayrı salon” önerilir/).closest("p") as HTMLElement;
    await user.click(within(oneri).getByRole("button", { name: "Ayrı salon seç" }));

    expect(screen.getByLabelText("Sınava nerede girsin?")).toHaveValue("SEPARATE_ROOM");
    expect(screen.queryByText(/“Ayrı salon” önerilir/)).not.toBeInTheDocument();
  });

  it("ek süre aralık dışındaysa kayıt kapalıdır", async () => {
    const user = userEvent.setup();
    renderDialog(SATIR);

    await user.clear(screen.getByLabelText("Ek süre (dakika)"));
    await user.type(screen.getByLabelText("Ek süre (dakika)"), "200");

    expect(screen.getByText("Ek süre 0 ile 120 dakika arasında olmalı.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kaydet" })).toBeDisabled();
  });

  it("düzenleme başlığı öğrenciyi gösterir; ret metni bildirime düşer", async () => {
    const user = userEvent.setup();
    iep.update.mockRejectedValueOnce(
      new ApiError(400, "validation_error", "Seçilen salon bulunamadı ya da pasif."),
    );
    renderDialog(SATIR);

    expect(screen.getByRole("dialog", { name: "Tedbirleri düzenle" })).toHaveTextContent(
      "102 Mehmet Demir — 9/B",
    );
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    expect(await screen.findByText("Seçilen salon bulunamadı ya da pasif.")).toBeInTheDocument();
  });
});
