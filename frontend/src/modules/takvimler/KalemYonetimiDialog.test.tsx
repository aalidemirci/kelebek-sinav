// Süreç kalemi yönetimi testleri (18.09.2026): kalemin TEK durum eylemi vardır
// — "Pasifleştir" ↔ "Etkinleştir". Eskiden yan yana duran "Sil (kalem
// gizlenir)" düğmesi kalktı; DELETE ucu arayüzden çağrılmaz. Pasifleştirme
// başlıklı onay diyaloğundan geçer, etkinleştirme geçmez; her geçişin kendi
// snackbar cümlesi vardır.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { ExamTrackItemRow } from "./api";

const kalemApi = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, examTrackItemApi: { ...actual.examTrackItemApi, ...kalemApi } };
});

import KalemYonetimiDialog from "./KalemYonetimiDialog";

function kalem(overrides: Partial<ExamTrackItemRow> = {}): ExamTrackItemRow {
  return { id: 1, name: "Soru teslimi", description: "", order: 10, is_active: true, ...overrides };
}

function sayfa(results: ExamTrackItemRow[]) {
  return { count: results.length, next: null, previous: null, results };
}

function renderDialog(onChanged: () => void = () => {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <ConfirmProvider>
          <KalemYonetimiDialog open onClose={() => {}} onChanged={onChanged} />
        </ConfirmProvider>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("KalemYonetimiDialog", () => {
  it("kalemde tek durum eylemi vardır; silme düğmesi yoktur", async () => {
    kalemApi.list.mockResolvedValue(sayfa([kalem(), kalem({ id: 2, name: "Basım" })]));
    renderDialog();

    expect(
      await screen.findByRole("button", { name: "Soru teslimi kalemini pasifleştir" }),
    ).toHaveTextContent("Pasifleştir");
    expect(screen.queryByRole("button", { name: /kalemini sil/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Sil/ })).not.toBeInTheDocument();
    // Pasifler de listelensin diye katalog include_inactive ile okunur.
    expect(kalemApi.list).toHaveBeenCalledWith(true);
  });

  it("pasifleştirme başlıklı onaydan geçer ve is_active=false yollar", async () => {
    const user = userEvent.setup();
    const onChanged = vi.fn();
    kalemApi.list.mockResolvedValue(sayfa([kalem()]));
    kalemApi.update.mockResolvedValue(kalem({ is_active: false }));
    renderDialog(onChanged);

    await user.click(
      await screen.findByRole("button", { name: "Soru teslimi kalemini pasifleştir" }),
    );

    // Başlık SORU, gövde SONUÇ (docs/sozluk.md §3); başlıksız "Onay" kalmadı.
    const onay = await screen.findByRole("dialog", { name: "Kalem pasifleştirilsin mi?" });
    expect(within(onay).getByText(/bütün takvimlerin süreç takibinden kalkar/)).toBeInTheDocument();
    expect(within(onay).getByText(/işaretler silinmez/)).toBeInTheDocument();
    expect(kalemApi.update).not.toHaveBeenCalled();

    await user.click(within(onay).getByRole("button", { name: "Pasifleştir" }));

    await waitFor(() =>
      expect(kalemApi.update).toHaveBeenCalledWith(1, {
        name: undefined,
        description: undefined,
        is_active: false,
      }),
    );
    expect(kalemApi.remove).not.toHaveBeenCalled();
    expect(await screen.findByText("Kalem pasifleştirildi.")).toBeInTheDocument();
    expect(onChanged).toHaveBeenCalled();
  });

  it("onayda vazgeçilirse kalem değişmez", async () => {
    const user = userEvent.setup();
    kalemApi.list.mockResolvedValue(sayfa([kalem()]));
    renderDialog();

    await user.click(
      await screen.findByRole("button", { name: "Soru teslimi kalemini pasifleştir" }),
    );
    const onay = await screen.findByRole("dialog", { name: "Kalem pasifleştirilsin mi?" });
    await user.click(within(onay).getByRole("button", { name: "Vazgeç" }));

    expect(kalemApi.update).not.toHaveBeenCalled();
  });

  it("pasif kalem rozetle görünür ve onaysız etkinleştirilir", async () => {
    const user = userEvent.setup();
    kalemApi.list.mockResolvedValue(sayfa([kalem({ is_active: false })]));
    kalemApi.update.mockResolvedValue(kalem());
    renderDialog();

    const dugme = await screen.findByRole("button", {
      name: "Soru teslimi kalemini etkinleştir",
    });
    expect(dugme).toHaveTextContent("Etkinleştir");
    expect(screen.getByText("Pasif")).toBeInTheDocument();

    await user.click(dugme);

    await waitFor(() =>
      expect(kalemApi.update).toHaveBeenCalledWith(1, {
        name: undefined,
        description: undefined,
        is_active: true,
      }),
    );
    expect(screen.queryByRole("dialog", { name: /pasifleştirilsin/ })).not.toBeInTheDocument();
    expect(await screen.findByText("Kalem etkinleştirildi.")).toBeInTheDocument();
  });

  it("yeni kalem eklenir ve form temizlenir", async () => {
    const user = userEvent.setup();
    kalemApi.list.mockResolvedValue(sayfa([]));
    kalemApi.create.mockResolvedValue(kalem({ id: 5, name: "Puan girişi" }));
    renderDialog();

    expect(await screen.findByText("Henüz süreç kalemi yok.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Ad"), "Puan girişi");
    await user.click(screen.getByRole("button", { name: "Ekle" }));

    await waitFor(() =>
      expect(kalemApi.create).toHaveBeenCalledWith({ name: "Puan girişi", description: "" }),
    );
    expect(await screen.findByText("Kalem eklendi.")).toBeInTheDocument();
    expect(screen.getByLabelText("Ad")).toHaveValue("");
  });
});
