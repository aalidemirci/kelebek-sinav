// Seçmeli ders seçimi bekleyen öğrenciler (07.10.2026): şubesi değişen ya da nakil
// gelen öğrencinin yeni şubesi seçmeliyi bölünerek okutuyorsa idareci hangi dersleri
// aldığını seçer. Eski şubesinde aldığı ders işaretli gelir (öneri); boş kayıt
// "hiçbirini almıyor" demektir. KVKK: adlar ve numaralar uydurmadır.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { PendingElectiveChoice, ResolveElectiveChoiceResult } from "./api";

const dersler = vi.hoisted(() => ({
  pendingElectiveChoices: vi.fn(
    (): Promise<{ school_year: number; results: PendingElectiveChoice[] }> =>
      Promise.resolve({ school_year: 1, results: [] }),
  ),
  resolveElectiveChoice: vi.fn(
    (studentId: number, courseIds: number[]): Promise<ResolveElectiveChoiceResult> =>
      Promise.resolve({
        school_year: 1,
        student_id: studentId,
        section_id: 4,
        course_ids: courseIds,
      }),
  ),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, derslerApi: { ...actual.derslerApi, ...dersler } };
});

import SecimBekleyenlerDialog, { SecimBekleyenBandi } from "./SecimBekleyenler";

function bekleyen(overrides: Partial<PendingElectiveChoice> = {}): PendingElectiveChoice {
  return {
    student_id: 31,
    student_number: "512",
    full_name: "Deniz Deneme",
    class_level: 9,
    class_label: "9/B",
    section_id: 4,
    courses: [
      { course_id: 7, course_name: "Almanca", listed_count: 14, enrolled: false, suggested: true },
      {
        course_id: 8,
        course_name: "Fransızca",
        listed_count: 12,
        enrolled: false,
        suggested: false,
      },
    ],
    ...overrides,
  };
}

function sarmala(children: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <MemoryRouter>{children}</MemoryRouter>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
  // clearAllMocks uygulamayı SIFIRLAMAZ: her test "bekleyen yok" varsayımıyla başlasın.
  dersler.pendingElectiveChoices.mockResolvedValue({ school_year: 1, results: [] });
});

describe("SecimBekleyenBandi", () => {
  it("bekleyen yoksa hiçbir şey basmaz", async () => {
    sarmala(<SecimBekleyenBandi onOpen={vi.fn()} />);
    await waitFor(() => expect(dersler.pendingElectiveChoices).toHaveBeenCalled());
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("sayıyı söyler ve pencereyi açar", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    dersler.pendingElectiveChoices.mockResolvedValue({
      school_year: 1,
      results: [bekleyen(), bekleyen({ student_id: 32, student_number: "513" })],
    });

    sarmala(<SecimBekleyenBandi onOpen={onOpen} />);

    expect(
      await screen.findByText(/2 öğrencinin seçmeli ders seçimi bekliyor/),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Seçimleri yap" }));
    expect(onOpen).toHaveBeenCalled();
  });

  it("pencere yoksa Ders Havuzu'na bağlantı verir", async () => {
    dersler.pendingElectiveChoices.mockResolvedValue({ school_year: 1, results: [bekleyen()] });

    sarmala(<SecimBekleyenBandi />);

    expect(
      await screen.findByRole("link", { name: "Ders Havuzu → Seçimleri yap" }),
    ).toHaveAttribute("href", "/dersler?secim=bekleyen");
  });
});

describe("SecimBekleyenlerDialog", () => {
  it("eski şubedeki ders işaretli gelir; seçilen dersler kaydedilir", async () => {
    const user = userEvent.setup();
    dersler.pendingElectiveChoices.mockResolvedValue({ school_year: 1, results: [bekleyen()] });

    sarmala(<SecimBekleyenlerDialog onClose={vi.fn()} />);

    const almanca = await screen.findByRole("checkbox", { name: /Almanca/ });
    expect(almanca).toBeChecked();
    expect(screen.getByText(/eski şubesinde alıyordu/)).toBeInTheDocument();
    const fransizca = screen.getByRole("checkbox", { name: /Fransızca/ });
    expect(fransizca).not.toBeChecked();

    await user.click(almanca);
    await user.click(fransizca);
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(dersler.resolveElectiveChoice).toHaveBeenCalledWith(31, [8]));
    expect(await screen.findByText("Öğrencinin seçmeli dersleri kaydedildi.")).toBeInTheDocument();
  });

  it("işaretsiz kayıt 'hiçbirini almıyor' demektir", async () => {
    const user = userEvent.setup();
    dersler.pendingElectiveChoices.mockResolvedValue({
      school_year: 1,
      results: [
        bekleyen({
          courses: [
            {
              course_id: 7,
              course_name: "Almanca",
              listed_count: 14,
              enrolled: false,
              suggested: false,
            },
          ],
        }),
      ],
    });

    sarmala(<SecimBekleyenlerDialog onClose={vi.fn()} />);

    await user.click(await screen.findByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(dersler.resolveElectiveChoice).toHaveBeenCalledWith(31, []));
    expect(await screen.findByText(/derslerin hiçbirini almıyor/)).toBeInTheDocument();
  });

  it("listede zaten olan ders işaretli gelir; ret metni bildirimde görünür", async () => {
    const user = userEvent.setup();
    dersler.pendingElectiveChoices.mockResolvedValue({
      school_year: 1,
      results: [
        bekleyen({
          courses: [
            {
              course_id: 8,
              course_name: "Fransızca",
              listed_count: 12,
              enrolled: true,
              suggested: false,
            },
          ],
        }),
      ],
    });
    dersler.resolveElectiveChoice.mockRejectedValueOnce(
      new ApiError(
        400,
        "validation_error",
        "Öğrencinin şubesi seçim beklerken değişti; listeyi yenileyin.",
      ),
    );

    sarmala(<SecimBekleyenlerDialog onClose={vi.fn()} />);

    expect(await screen.findByRole("checkbox", { name: /Fransızca/ })).toBeChecked();
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(
      await screen.findByText("Öğrencinin şubesi seçim beklerken değişti; listeyi yenileyin."),
    ).toBeInTheDocument();
  });

  it("bekleyen yoksa boş durum gösterir; Kapat pencereyi kapatır", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    sarmala(<SecimBekleyenlerDialog onClose={onClose} />);

    expect(await screen.findByText("Seçim bekleyen öğrenci yok")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Kapat" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("liste yüklenemezse hatayı söyler", async () => {
    dersler.pendingElectiveChoices.mockRejectedValue(
      new ApiError(
        400,
        "validation_error",
        "Aktif ders yılı yok — Ayarlar → Ders Yılları'ndan bir yıl açın.",
      ),
    );

    sarmala(<SecimBekleyenlerDialog onClose={vi.fn()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Aktif ders yılı yok");
  });
});
