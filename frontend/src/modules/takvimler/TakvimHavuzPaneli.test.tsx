// Takvim havuz paneli testleri (F6 sadeleştirmesi): "Dersleri ekle"
// onay + fill-pool çağrısı, "Seçmeli ders seç" dialog'unun açılması, havuz
// tablosundaki "Katılımcılar" sütunu ve o sütundan kapsamın DÜZELTİLMESİ.
// 18.09.2026 sözlük turu: "Düzen" seçim alanı (eski "Kelebek değil" kutusu),
// tür/düzen rozetleri, girdi kaldırmanın bildirimi. Panel useConfirm kullanır →
// ConfirmProvider ZORUNLU; onay dialog'una basılmadan mutasyon koşmaz.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import type { Course } from "../dersler/api";
import type { ClassSection, ClassSectionGroup } from "../okul/api";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { makeElectiveOptions, makeEntry, makeGrid } from "./testFixtures";

const calApi = vi.hoisted(() => ({
  entries: vi.fn(),
  participantPreview: vi.fn(),
  grid: vi.fn(),
  fillPool: vi.fn(),
  electiveOptions: vi.fn(),
  bulkEntries: vi.fn(),
  patchEntry: vi.fn(),
  addEntry: vi.fn(),
  removeEntry: vi.fn(),
}));

// Tipli varsayılan: `Promise.resolve([])` tek başına `never[]` çıkarır ve
// mockResolvedValue ders listesini kabul etmez (tsc kapısı).
const dersler = vi.hoisted(() => ({
  listCourses: vi.fn((): Promise<Course[]> => Promise.resolve([])),
}));

// Seçmeli dialog şube kataloğunu okur — mock'lanmazsa sorgu sessizce reddedilir
// ve çipler hiç çizilmez (bu dosyada dialog yalnız "açıldı mı" diye sınanıyor).
// Tipli varsayılan: `Promise.resolve([])` tek başına `never[]` çıkarır ve
// mockResolvedValue şube listesini kabul etmez (tsc kapısı).
const okul = vi.hoisted(() => ({
  listClassSections: vi.fn((): Promise<ClassSection[]> => Promise.resolve([])),
  listClassSectionGroups: vi.fn((): Promise<ClassSectionGroup[]> => Promise.resolve([])),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, examCalendarApi: { ...actual.examCalendarApi, ...calApi } };
});
vi.mock("../dersler/api", async (importActual) => {
  const actual = await importActual<typeof import("../dersler/api")>();
  return { ...actual, derslerApi: { ...actual.derslerApi, ...dersler } };
});
vi.mock("../okul/api", async (importActual) => {
  const actual = await importActual<typeof import("../okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...okul } };
});

import TakvimHavuzPaneli from "./TakvimHavuzPaneli";

function renderPanel(round = 1, editable = true) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <ConfirmProvider>
          <TakvimHavuzPaneli
            calendarId={7}
            round={round}
            editable={editable}
            onChanged={() => {}}
          />
        </ConfirmProvider>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("TakvimHavuzPaneli", () => {
  it("“Dersleri ekle” onaydan sonra fill-pool ucunu çağırır ve sonucu özetler", async () => {
    const user = userEvent.setup();
    calApi.entries.mockResolvedValue({ results: [makeEntry()] });
    calApi.participantPreview.mockResolvedValue({});
    calApi.grid.mockResolvedValue(makeGrid());
    calApi.fillPool.mockResolvedValue({
      created: ["Coğrafya — 9. Sınıf"],
      existed: [],
      skipped: [],
      total_pairs: 1,
    });

    renderPanel();
    await user.click(await screen.findByRole("button", { name: "Dersleri ekle" }));

    // Onay metni sözleşmeyi anlatır: zorunlu + yazılı dersler ve ŞUBESİ TANIMLI
    // seçmeliler; şubesi girilmemiş seçmeli atlanır (03.09.2026 genişlemesi).
    // Başlık sorudur; ders türü "zorunlu"dur — "ortak" yalnız MEB'in okul
    // geneli sınav anlamında kullanılır (docs/sozluk.md).
    const onay = await screen.findByRole("dialog", { name: "Dersler havuza eklensin mi?" });
    expect(within(onay).getByText(/ZORUNLU ve sınavı YAZILI dersler/)).toBeInTheDocument();
    expect(within(onay).queryByText(/ortak/i)).not.toBeInTheDocument();
    expect(within(onay).getByText(/şubesi girilmemiş seçmeli atlanır/)).toBeInTheDocument();
    await user.click(within(onay).getByRole("button", { name: "Ekle" }));

    await waitFor(() => expect(calApi.fillPool).toHaveBeenCalledWith(7));
    expect(await screen.findByText(/1 ders eklendi/)).toBeInTheDocument();
  });

  it("“Seçmeli ders seç” dialog'u seviye sekmeleriyle açılır", async () => {
    const user = userEvent.setup();
    calApi.entries.mockResolvedValue({ results: [makeEntry()] });
    calApi.participantPreview.mockResolvedValue({});
    calApi.grid.mockResolvedValue(makeGrid());
    calApi.electiveOptions.mockResolvedValue(makeElectiveOptions());

    renderPanel();
    await user.click(await screen.findByRole("button", { name: "Seçmeli ders seç" }));

    const dialog = await screen.findByRole("dialog", { name: "Seçmeli ders seç" });
    expect(calApi.electiveOptions).toHaveBeenCalledWith(7);
    expect(within(dialog).getByRole("tab", { name: "9. Sınıf" })).toBeInTheDocument();
    expect(
      await within(dialog).findByRole("checkbox", { name: /Çağdaş Türk ve Dünya Tarihi/ }),
    ).toBeInTheDocument();
  });

  it("havuz tablosu katılımcıları sözlük sözcükleriyle basar (backend etiketiyle değil)", async () => {
    calApi.entries.mockResolvedValue({
      results: [
        // Fixture'daki backend etiketi "Seviye geneli"dir — arayüz onu BASMAZ.
        makeEntry(),
        makeEntry({
          id: 42,
          course: 11,
          course_name: "Almanca",
          participant_type: "SECTIONS",
          section_ids: [3, 4],
          participant_label: "",
        }),
      ],
    });
    calApi.participantPreview.mockResolvedValue({
      "41": { student_count: 84, whole: true, groups: [] },
    });
    calApi.grid.mockResolvedValue(makeGrid());

    renderPanel();

    expect(await screen.findByRole("columnheader", { name: "Katılımcılar" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Sınıf düzeyi" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Öğrenci sayısı" })).toBeInTheDocument();
    expect(screen.getByText("Sınıf düzeyinin tamamı")).toBeInTheDocument();
    expect(screen.getByText("2 şube")).toBeInTheDocument();
    expect(screen.queryByText("Seviye geneli")).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Kapsam" })).not.toBeInTheDocument();
  });

  it("düzen olumsuz onay kutusu değil seçim alanıdır; is_butterfly aynı alanla gider", async () => {
    const user = userEvent.setup();
    calApi.entries.mockResolvedValue({ results: [] });
    calApi.participantPreview.mockResolvedValue({});
    calApi.grid.mockResolvedValue(makeGrid());
    calApi.addEntry.mockResolvedValue(makeEntry({ is_butterfly: false }));
    dersler.listCourses.mockResolvedValue([
      {
        id: 10,
        name: "Coğrafya",
        levels: [9],
        level_labels: ["9. Sınıf"],
        course_type: "COMMON",
        source: "MEB_CATALOG",
        exam_mode: "WRITTEN",
        exam_mode_label: "Yazılı",
        is_active: true,
        catalog_excluded: false,
      },
    ]);

    renderPanel();

    // Eski çift olumsuz "Kelebek değil" kutusu yok.
    const duzen = await screen.findByRole("combobox", { name: "Düzen" });
    expect(screen.queryByRole("checkbox", { name: /Kelebek değil/ })).not.toBeInTheDocument();
    expect(duzen).toHaveValue("BUTTERFLY");
    expect(within(duzen).getByRole("option", { name: "Kelebek" })).toBeInTheDocument();
    expect(within(duzen).getByRole("option", { name: "Kendi dersliğinde" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Sınıf düzeyi" })).toBeInTheDocument();

    await user.type(screen.getByLabelText("Ders"), "Coğ");
    // Seçenek adı <mark> vurgusuyla bölünür ("Coğ" + "rafya") — alt etiketle aranır.
    await user.click(
      await screen.findByRole("option", { name: /9\. Sınıf · Yazılı/ }, { timeout: 3000 }),
    );
    await user.selectOptions(duzen, "HOME_CLASSROOM");
    await user.click(screen.getByRole("button", { name: "Havuza ekle" }));

    await waitFor(() =>
      expect(calApi.addEntry).toHaveBeenCalledWith(7, {
        course: 10,
        level: 9,
        exam_kind: "WRITTEN",
        is_butterfly: false,
        authority: "SCHOOL",
      }),
    );
  });

  it("tür ve düzen ders adına yapışık ek değil rozettir", async () => {
    calApi.entries.mockResolvedValue({
      results: [makeEntry({ exam_kind: "PRACTICE", is_butterfly: false })],
    });
    calApi.participantPreview.mockResolvedValue({});
    calApi.grid.mockResolvedValue(makeGrid());

    renderPanel();

    const tablo = within(await screen.findByRole("table"));
    expect(tablo.getByText("Uygulama")).toBeInTheDocument();
    expect(tablo.getByText("Kendi dersliğinde")).toBeInTheDocument();
    expect(tablo.queryByText(/\[Uygulama\]|Kelebek değil/)).not.toBeInTheDocument();
  });

  it("girdi kaldırma sessiz geçmez — ders adıyla bildirilir", async () => {
    const user = userEvent.setup();
    calApi.entries.mockResolvedValue({ results: [makeEntry()] });
    calApi.participantPreview.mockResolvedValue({});
    calApi.grid.mockResolvedValue(makeGrid());
    calApi.removeEntry.mockResolvedValue(undefined);

    renderPanel();
    await user.click(await screen.findByRole("button", { name: "Coğrafya girdisini kaldır" }));

    await waitFor(() => expect(calApi.removeEntry).toHaveBeenCalledWith(41));
    expect(await screen.findByText("“Coğrafya” havuzdan kaldırıldı.")).toBeInTheDocument();
  });

  it("kapsam hücresinden girdinin kapsamı düzeltilir (PATCH)", async () => {
    // Denetim bulgusu (31.08.2026): seçmeli dialog havuzdaki dersi kilitli
    // gösterdiğinden yanlış şube seçimini düzeltmenin yolu yoktu.
    const user = userEvent.setup();
    calApi.entries.mockResolvedValue({ results: [makeEntry()] });
    calApi.participantPreview.mockResolvedValue({});
    calApi.grid.mockResolvedValue(makeGrid());
    calApi.patchEntry.mockResolvedValue(makeEntry({ participant_type: "SECTIONS" }));
    okul.listClassSections.mockResolvedValue([
      {
        id: 3,
        school_year: 1,
        school_year_name: "2026-2027",
        class_level: 9,
        class_section: "A",
        class_label: "9/A",
        group: null,
        group_name: "",
      },
      {
        id: 9,
        school_year: 1,
        school_year_name: "2026-2027",
        class_level: 10,
        class_section: "A",
        class_label: "10/A",
        group: null,
        group_name: "",
      },
    ]);

    renderPanel();
    await user.click(
      await screen.findByRole("button", { name: "Coğrafya katılımcı kapsamını düzenle" }),
    );

    const dialog = await screen.findByRole("dialog", { name: "Katılımcı kapsamını düzenle" });
    // Seçenekler oturum sihirbazıyla aynı sözcüklerdir (docs/sozluk.md).
    const secici = within(dialog).getByLabelText("Coğrafya katılımcı kapsamı");
    expect(within(secici).getByRole("option", { name: "Sınıf düzeyinin tamamı" })).toBeDefined();
    expect(within(secici).getByRole("option", { name: "Seçili şubeler" })).toBeDefined();
    await user.selectOptions(secici, "SECTIONS");
    // Şubesiz "Seçili şubeler" kaydedilemez; çıkış yolu sözlük adıyla söylenir.
    expect(within(dialog).getByRole("alert")).toHaveTextContent(
      "En az bir şube seçin ya da “Sınıf düzeyinin tamamı” seçeneğine dönün.",
    );
    expect(within(dialog).getByRole("button", { name: "Kaydet" })).toBeDisabled();
    // Yalnız girdinin SEVİYESİNDEKİ şubeler listelenir (10/A çıkmaz).
    expect(within(dialog).queryByLabelText("Coğrafya: 10/A")).not.toBeInTheDocument();
    await user.click(await within(dialog).findByLabelText("Coğrafya: 9/A"));
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(calApi.patchEntry).toHaveBeenCalledWith(41, {
        participant_type: "SECTIONS",
        section_ids: [3],
      }),
    );
  });
  it("kapsamı ders havuzundan farklı girdi 'özel' rozeti taşır", async () => {
    // Kapsamın kaynağı ders havuzudur; takvimdeki istisna görünür kalmalı.
    calApi.entries.mockResolvedValue({
      results: [
        makeEntry({
          participant_type: "SECTIONS",
          section_ids: [3],
          participant_label: "1 şube",
          scope_differs_from_catalog: true,
        }),
      ],
    });
    calApi.participantPreview.mockResolvedValue({});
    calApi.grid.mockResolvedValue(makeGrid());

    renderPanel();

    expect(await screen.findByText("özel")).toBeInTheDocument();
  });
});
