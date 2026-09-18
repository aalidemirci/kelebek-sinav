// Sınav Sihirbazı testleri (F3): Adım 0 beyan kilidi, kaldığı adımdan başlama,
// tıklanabilir Stepper, adım geçişleri, HOME_CLASSROOM'da salon adımının
// atlanması. API ağ çağrıları vi.mock'lanır; ortak oturum kurucusu
// testFixtures.ts'ten gelir (test dosyasından test dosyasına import YOK — OYS
// Tur 232). Ön kontrol adımı Kişiler ekranına bağlantı verdiği için sihirbaz
// Router içinde çizilir.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { ExamSession, ExamSessionCourseRow, ParticipantsResponse } from "./api";
import { makeReport, makeSession } from "./testFixtures";

const sessionApi = vi.hoisted(() => ({
  preCheck: vi.fn(),
  confirmTransferCheck: vi.fn(),
  update: vi.fn(),
  participants: vi.fn(),
  addCourse: vi.fn(),
  updateCourse: vi.fn(),
  removeCourse: vi.fn(),
  setRooms: vi.fn(),
  distribute: vi.fn(),
}));

const dersler = vi.hoisted(() => ({
  listCourses: vi.fn(() => Promise.resolve([])),
}));

const okul = vi.hoisted(() => ({
  listClassSections: vi.fn(() => Promise.resolve([])),
  listClassSectionGroups: vi.fn(() => Promise.resolve([])),
}));

const salonlar = vi.hoisted(() => ({
  list: vi.fn((): Promise<{ count: number; next: null; previous: null; results: unknown[] }> =>
    Promise.resolve({ count: 0, next: null, previous: null, results: [] }),
  ),
}));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, examSessionApi: { ...actual.examSessionApi, ...sessionApi } };
});
vi.mock("../dersler/api", async (importActual) => {
  const actual = await importActual<typeof import("../dersler/api")>();
  return { ...actual, derslerApi: { ...actual.derslerApi, ...dersler } };
});
vi.mock("../okul/api", async (importActual) => {
  const actual = await importActual<typeof import("../okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...okul } };
});
vi.mock("../salonlar/api", async (importActual) => {
  const actual = await importActual<typeof import("../salonlar/api")>();
  return { ...actual, examRoomApi: { ...actual.examRoomApi, ...salonlar } };
});

import SinavSihirbazi, { initialStep } from "./SinavSihirbazi";

const ONAY_ZAMANI = "2026-06-10T10:00:00+03:00";

function makeCourseRow(overrides: Partial<ExamSessionCourseRow> = {}): ExamSessionCourseRow {
  return {
    id: 11,
    course_id: 3,
    course_name: "Coğrafya",
    participant_type: "LEVEL",
    level: 9,
    display_label: "Coğrafya — 9. Sınıf",
    section_ids: [],
    duration_minutes: null,
    shared_booklet: false,
    ...overrides,
  };
}

function makeParticipants(overrides: Partial<ParticipantsResponse> = {}): ParticipantsResponse {
  return {
    total_count: 30,
    has_blocking_conflicts: false,
    warnings: [],
    courses: [
      {
        session_course_id: 11,
        course_id: 3,
        course_name: "Coğrafya",
        count: 30,
        warnings: [],
        participants: [],
      },
    ],
    ...overrides,
  };
}

function renderWizard(session: ExamSession) {
  const onChanged = vi.fn();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const { unmount } = render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <MemoryRouter>
          <SinavSihirbazi session={session} onChanged={onChanged} />
        </MemoryRouter>
      </SnackbarProvider>
    </QueryClientProvider>,
  );
  return { onChanged, unmount };
}

afterEach(() => vi.clearAllMocks());

describe("SinavSihirbazi — başlangıç adımı (kaldığı yerden)", () => {
  it("ön kontrol onayı yoksa 0; onaylı ve derssizse 1; ders varsa 2", () => {
    expect(initialStep(makeSession())).toBe(0);
    // Onay yokken ders olsa bile (kopyalanmış plan) ön kontrol atlanamaz.
    expect(initialStep(makeSession({ courses: [makeCourseRow()] }))).toBe(0);
    expect(initialStep(makeSession({ transfer_check_confirmed_at: ONAY_ZAMANI }))).toBe(1);
    expect(
      initialStep(
        makeSession({ transfer_check_confirmed_at: ONAY_ZAMANI, courses: [makeCourseRow()] }),
      ),
    ).toBe(2);
  });

  it("dersi olan onaylı oturum (Taslağa al'dan dönüş) Ders ve Katılımcılar adımında açılır", async () => {
    sessionApi.participants.mockResolvedValue(makeParticipants());
    renderWizard(
      makeSession({ transfer_check_confirmed_at: ONAY_ZAMANI, courses: [makeCourseRow()] }),
    );

    expect(
      await screen.findByRole("heading", { name: "Ders ve Katılımcılar" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Coğrafya — 9. Sınıf")).toBeInTheDocument();
    expect(sessionApi.preCheck).not.toHaveBeenCalled();
  });
});

describe("SinavSihirbazi — Stepper ile adıma dönüş", () => {
  it("tamamlanmış adıma tıklanınca o adım açılır; güncel ve gelecek adımlar düğme değildir", async () => {
    const user = userEvent.setup();
    sessionApi.participants.mockResolvedValue(makeParticipants());
    renderWizard(
      makeSession({ transfer_check_confirmed_at: ONAY_ZAMANI, courses: [makeCourseRow()] }),
    );
    await screen.findByRole("heading", { name: "Ders ve Katılımcılar" });

    const ray = screen.getByRole("list", { name: "Sınav sihirbazı adımları" });
    // 2. adımdayız: önceki iki adım tıklanır; güncel (2) ve gelecek (3, 4) tıklanmaz.
    expect(within(ray).getAllByRole("button")).toHaveLength(2);
    expect(within(ray).queryByRole("button", { name: /Salonlar/ })).not.toBeInTheDocument();
    expect(within(ray).queryByRole("button", { name: /Dağıt/ })).not.toBeInTheDocument();

    await user.click(within(ray).getByRole("button", { name: "Oturum Bilgileri adımına dön" }));
    expect(await screen.findByRole("heading", { name: "Oturum Bilgileri" })).toBeInTheDocument();
    // Artık 1. adımdayız: yalnız Veri Ön Kontrolü geriye dönük tıklanır.
    expect(within(ray).getAllByRole("button")).toHaveLength(1);
  });

  it("klasik düzende 'atlandı' işaretli Salonlar adımı Dağıt adımından da tıklanamaz", async () => {
    const user = userEvent.setup();
    sessionApi.participants.mockResolvedValue(makeParticipants());
    renderWizard(
      makeSession({
        layout_mode: "HOME_CLASSROOM",
        transfer_check_confirmed_at: ONAY_ZAMANI,
        courses: [makeCourseRow()],
      }),
    );

    await user.click(await screen.findByRole("button", { name: "Devam" }));
    expect(await screen.findByRole("heading", { name: "Dağıt" })).toBeInTheDocument();

    const ray = screen.getByRole("list", { name: "Sınav sihirbazı adımları" });
    // Dağıt adımındayız: 0, 1 ve 2 tıklanır; atlanan Salonlar (3) tıklanmaz.
    expect(within(ray).getAllByRole("button")).toHaveLength(3);
    expect(within(ray).queryByRole("button", { name: /Salonlar/ })).not.toBeInTheDocument();
    expect(within(ray).getByText("atlandı")).toBeInTheDocument();
  });
});

describe("SinavSihirbazi — Adım 0 (Veri Ön Kontrolü)", () => {
  it("onaysız oturum Adım 0'da başlar; beyan işaretlenmeden ilerlenemez", async () => {
    const user = userEvent.setup();
    sessionApi.preCheck.mockResolvedValue({
      active_students_by_level: { "9": 120, "10": 96 },
      last_student_import: {
        file_name: "ogrenciler.xlsx",
        finished_at: "2026-06-01T09:00:00+03:00",
      },
    });
    sessionApi.confirmTransferCheck.mockResolvedValue(
      makeSession({ transfer_check_confirmed_at: "2026-06-14T10:00:00+03:00" }),
    );
    const { onChanged } = renderWizard(makeSession());

    expect(await screen.findByRole("heading", { name: "Veri Ön Kontrolü" })).toBeInTheDocument();
    // Yeni sözleşme: seviye sayıları + son aktarım dosyası görünür.
    expect(await screen.findByText("120")).toBeInTheDocument();
    expect(screen.getByText("ogrenciler.xlsx")).toBeInTheDocument();

    const kaydet = screen.getByRole("button", { name: "Kaydet ve devam et" });
    expect(kaydet).toBeDisabled();
    await user.click(screen.getByRole("checkbox"));
    expect(kaydet).toBeEnabled();

    await user.click(kaydet);
    // Ad boş bırakıldı → boş gönderilir, backend okul müdürünü damgalar.
    await waitFor(() =>
      expect(sessionApi.confirmTransferCheck).toHaveBeenCalledWith(5, { confirmed_by_name: "" }),
    );
    expect(onChanged).toHaveBeenCalled();
    // Onay sonrası Adım 1'e geçilir.
    expect(await screen.findByRole("heading", { name: "Oturum Bilgileri" })).toBeInTheDocument();
  });

  it("onaylayan adı girilirse kırpılarak confirmed_by_name olarak gönderilir", async () => {
    const user = userEvent.setup();
    sessionApi.preCheck.mockResolvedValue({
      active_students_by_level: { "9": 120 },
      last_student_import: null,
    });
    sessionApi.confirmTransferCheck.mockResolvedValue(
      makeSession({ transfer_check_confirmed_at: "2026-06-14T10:00:00+03:00" }),
    );
    renderWizard(makeSession());

    // KVKK: ad uydurmadır.
    await user.type(
      await screen.findByLabelText("Onaylayan (boş bırakılırsa okul müdürü)"),
      "  Zeynep Arslan ",
    );
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Kaydet ve devam et" }));

    await waitFor(() =>
      expect(sessionApi.confirmTransferCheck).toHaveBeenCalledWith(5, {
        confirmed_by_name: "Zeynep Arslan",
      }),
    );
  });

  it("hiç öğrenci aktarımı yoksa uyarı Kişiler ekranına bağlantı verir", async () => {
    sessionApi.preCheck.mockResolvedValue({
      active_students_by_level: {},
      last_student_import: null,
    });
    renderWizard(makeSession());

    expect(await screen.findByText(/Henüz öğrenci aktarımı yapılmamış/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Kişiler ekranından" })).toHaveAttribute(
      "href",
      "/kisiler",
    );
    // Menüde "Okul" diye bir ekran yok — eski yönlendirme kalmamalı.
    expect(screen.queryByText(/Okul modülünden/)).not.toBeInTheDocument();
  });

  it("onaylı, derssiz oturum Adım 1'den başlar; gözetmen anahtarı Adım 1'de (F7)", async () => {
    renderWizard(makeSession({ transfer_check_confirmed_at: ONAY_ZAMANI }));

    expect(await screen.findByRole("heading", { name: "Oturum Bilgileri" })).toBeInTheDocument();
    expect(sessionApi.preCheck).not.toHaveBeenCalled();
    // Gözetmen anahtarı F7 ile Adım 1'e geldi (U2 — varsayılan kapalı). Etikette
    // evrak kodu (R6) geçmez — docs/sozluk.md §2.
    const kutu = screen.getByRole("checkbox", {
      name: "Gözetmen görevlendirmesi yapılacak (görevlendirme yazısı basılır)",
    });
    expect(kutu).not.toBeChecked();
    expect(screen.queryByText(/R6/)).not.toBeInTheDocument();
    // Düzen seçeneklerinde sözlük dışı "klasik" geçmez.
    expect(screen.getByRole("option", { name: "Kendi dersliğinde" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /klasik/ })).not.toBeInTheDocument();
  });
});

describe("SinavSihirbazi — adım geçişleri", () => {
  it("Adım 1 kaydedilince update çağrılır ve Adım 2'ye geçilir", async () => {
    const user = userEvent.setup();
    const session = makeSession({ transfer_check_confirmed_at: ONAY_ZAMANI });
    sessionApi.update.mockResolvedValue(session);
    const { onChanged } = renderWizard(session);

    await user.click(await screen.findByRole("button", { name: "Kaydet ve devam et" }));

    await waitFor(() =>
      expect(sessionApi.update).toHaveBeenCalledWith(
        5,
        expect.objectContaining({ name: "2. Ortak Sınav", layout_mode: "BUTTERFLY" }),
      ),
    );
    expect(onChanged).toHaveBeenCalled();
    expect(
      await screen.findByRole("heading", { name: "Ders ve Katılımcılar" }),
    ).toBeInTheDocument();
    // Ders yokken ilerlenemez.
    expect(screen.getByRole("button", { name: "Devam" })).toBeDisabled();
  });

  it("çakışma kilidi: has_blocking_conflicts Devam düğmesini kilitler", async () => {
    const session = makeSession({
      transfer_check_confirmed_at: ONAY_ZAMANI,
      courses: [makeCourseRow()],
    });
    sessionApi.participants.mockResolvedValue(
      makeParticipants({
        has_blocking_conflicts: true,
        warnings: ["Öğrenci 154 iki derse düşüyor."],
      }),
    );
    renderWizard(session);

    expect(await screen.findByText(/dağıtım engellenecek/)).toBeInTheDocument();
    // Uyarı metni ham "⚠" karakteri taşımaz — simge Icon bileşeniyle verilir.
    expect(screen.getByText("Öğrenci 154 iki derse düşüyor.")).toBeInTheDocument();
    expect(screen.queryByText(/⚠/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Devam" })).toBeDisabled();
  });

  it("ders satırı katılımcıları sözlükteki adla gösterir ('Sınıf düzeyinin tamamı')", async () => {
    sessionApi.participants.mockResolvedValue(makeParticipants());
    renderWizard(
      makeSession({ transfer_check_confirmed_at: ONAY_ZAMANI, courses: [makeCourseRow()] }),
    );

    expect(await screen.findByText("Sınıf düzeyinin tamamı")).toBeInTheDocument();
    expect(screen.queryByText("Seviye geneli")).not.toBeInTheDocument();
  });

  it("'Ders ekle' penceresi: alan 'Katılımcılar', seçenekler sözlükten", async () => {
    const user = userEvent.setup();
    const session = makeSession({ transfer_check_confirmed_at: ONAY_ZAMANI });
    sessionApi.update.mockResolvedValue(session);
    renderWizard(session);

    await user.click(await screen.findByRole("button", { name: "Kaydet ve devam et" }));
    await user.click(await screen.findByRole("button", { name: "Ders ekle" }));
    const dialog = await screen.findByRole("dialog", { name: "Ders ekle" });

    const katilimcilar = within(dialog).getByLabelText("Katılımcılar");
    expect(
      within(katilimcilar).getByRole("option", { name: "Sınıf düzeyinin tamamı" }),
    ).toBeInTheDocument();
    expect(
      within(katilimcilar).getByRole("option", { name: "Seçili şubeler" }),
    ).toBeInTheDocument();
    expect(within(dialog).queryByText("Katılımcı tipi")).not.toBeInTheDocument();
  });

  it("aynı ders iki seviyede: ders-başı 'aynı kitapçık' kutusu updateCourse'u çağırır; ekleme formunda kutu yok", async () => {
    const user = userEvent.setup();
    const session = makeSession({
      transfer_check_confirmed_at: ONAY_ZAMANI,
      courses: [
        makeCourseRow(),
        makeCourseRow({ id: 12, level: 10, display_label: "Coğrafya — 10. Sınıf" }),
      ],
    });
    sessionApi.participants.mockResolvedValue(makeParticipants());
    sessionApi.updateCourse.mockResolvedValue(makeCourseRow({ shared_booklet: true }));
    const { onChanged } = renderWizard(session);

    const kutu = await screen.findByRole("checkbox", {
      name: /Coğrafya: 9. Sınıf, 10. Sınıf aynı soru kitapçığını çözecek/,
    });
    expect(kutu).not.toBeChecked();
    await user.click(kutu);
    // Bayrak dersin niteliğidir: tek satırdan gönderilir, backend kardeşlere yayar.
    await waitFor(() =>
      expect(sessionApi.updateCourse).toHaveBeenCalledWith(11, { shared_booklet: true }),
    );
    expect(onChanged).toHaveBeenCalled();

    // "Ders ekle" penceresinde eski "Ortak kitapçık" kutusu artık yok.
    await user.click(screen.getByRole("button", { name: "Ders ekle" }));
    const dialog = await screen.findByRole("dialog", { name: "Ders ekle" });
    expect(within(dialog).queryByRole("checkbox")).not.toBeInTheDocument();
    expect(within(dialog).queryByText(/Ortak kitapçık/)).not.toBeInTheDocument();
  });

  it("tek seviyeli ders listesinde 'aynı kitapçık' bölümü görünmez", async () => {
    const session = makeSession({
      transfer_check_confirmed_at: ONAY_ZAMANI,
      courses: [makeCourseRow()],
    });
    sessionApi.participants.mockResolvedValue(makeParticipants());
    renderWizard(session);

    expect(await screen.findByText("Coğrafya — 9. Sınıf")).toBeInTheDocument();
    expect(screen.queryByText("Aynı ders birden çok sınıf düzeyinde")).not.toBeInTheDocument();
  });

  it("HOME_CLASSROOM: salon adımı atlanır (2→4) ve dağıtım koşar", async () => {
    const user = userEvent.setup();
    const session = makeSession({
      layout_mode: "HOME_CLASSROOM",
      transfer_check_confirmed_at: ONAY_ZAMANI,
      courses: [makeCourseRow()],
    });
    sessionApi.participants.mockResolvedValue(makeParticipants());
    // Klasik düzende backend dağıtım numarasını hep 0 döndürür (karıştırma yok).
    sessionApi.distribute.mockResolvedValue({
      status: "DISTRIBUTED",
      seed: 0,
      checkerboard: false,
      placed: 30,
      warnings: [],
      report: makeReport(),
    });
    const { onChanged } = renderWizard(session);

    // Stepper salon adımını baştan "atlandı" işaretler.
    expect(await screen.findByText("atlandı")).toBeInTheDocument();

    await user.click(await screen.findByRole("button", { name: "Devam" }));

    // Salon adımı görülmeden Dağıt'a ulaşılır; salon ucu hiç çağrılmaz. Adım adı
    // "Dağıt"tır — önizleme olmadığı için eski "Dağıt & Önizle" adı yanıltıyordu.
    expect(await screen.findByRole("heading", { name: "Dağıt" })).toBeInTheDocument();
    expect(screen.queryByText(/Önizle/)).not.toBeInTheDocument();
    expect(salonlar.list).not.toHaveBeenCalled();
    // "Kendi dersliğinde" düzeninde karıştırma yoktur: numara ve katı dağıtım sonucu
    // değiştirmez → sorulmaz; açıklama da o düzeni anlatır.
    expect(screen.getByText(/okul numarası sırasıyla yerleştirilir/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Dağıtım numarası/)).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: /Katı dağıtım/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Dağıt" }));
    await waitFor(() =>
      expect(sessionApi.distribute).toHaveBeenCalledWith(5, { seed: undefined, strict: false }),
    );
    // Sonuç cümlesinde anlamsız "dağıtım numarası 0" yazılmaz.
    expect(await screen.findByText("Dağıtım tamamlandı: 30 öğrenci yerleşti.")).toBeInTheDocument();
    expect(onChanged).toHaveBeenCalled();
  });

  it("dağıtım UYARI döndürürse uyarılar okunmadan sekmeli görünüme geçilmez", async () => {
    const user = userEvent.setup();
    sessionApi.participants.mockResolvedValue(makeParticipants());
    sessionApi.distribute.mockResolvedValue({
      status: "DISTRIBUTED",
      seed: 7,
      checkerboard: false,
      placed: 30,
      warnings: ["Yerleştirme kuralları klasik düzende uygulanmaz."],
      report: makeReport(),
    });
    const { onChanged } = renderWizard(
      makeSession({
        layout_mode: "HOME_CLASSROOM",
        transfer_check_confirmed_at: ONAY_ZAMANI,
        courses: [makeCourseRow()],
      }),
    );

    await user.click(await screen.findByRole("button", { name: "Devam" }));
    await user.click(await screen.findByRole("button", { name: "Dağıt" }));

    expect(await screen.findByRole("heading", { name: "Dağıtım tamamlandı" })).toBeInTheDocument();
    expect(
      screen.getByText("Yerleştirme kuralları klasik düzende uygulanmaz."),
    ).toBeInTheDocument();
    expect(screen.getByText("Kural ihlali yok — oturum onaylanabilir.")).toBeInTheDocument();
    // Oturum artık taslak değil: önceki adımlara dönüş kapanır, sorgu henüz tazelenmez.
    const ray = screen.getByRole("list", { name: "Sınav sihirbazı adımları" });
    expect(within(ray).queryByRole("button")).not.toBeInTheDocument();
    expect(onChanged).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Yerleşimi görüntüle" }));
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("uyarılar okunurken sayfadan ayrılınırsa oturum yine de tazelenir (liste 'Taslak' kalmaz)", async () => {
    const user = userEvent.setup();
    sessionApi.participants.mockResolvedValue(makeParticipants());
    sessionApi.distribute.mockResolvedValue({
      status: "DISTRIBUTED",
      seed: 7,
      checkerboard: false,
      placed: 30,
      warnings: ["Salon doluluk farkı yüksek."],
      report: makeReport(),
    });
    const { onChanged, unmount } = renderWizard(
      makeSession({
        layout_mode: "HOME_CLASSROOM",
        transfer_check_confirmed_at: ONAY_ZAMANI,
        courses: [makeCourseRow()],
      }),
    );

    await user.click(await screen.findByRole("button", { name: "Devam" }));
    await user.click(await screen.findByRole("button", { name: "Dağıt" }));
    await screen.findByRole("heading", { name: "Dağıtım tamamlandı" });
    expect(onChanged).not.toHaveBeenCalled();

    unmount();
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  /** Kelebek oturumu: Ders (2) → Salonlar (3) → Dağıt (4). Seçili salon oturumda hazır. */
  async function kelebekteDagitAdiminaGit(user: ReturnType<typeof userEvent.setup>) {
    sessionApi.participants.mockResolvedValue(makeParticipants());
    salonlar.list.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [{ id: 1, name: "D-204", capacity: 40, group_id: null }],
    });
    sessionApi.setRooms.mockResolvedValue({ rooms: [] });
    renderWizard(
      makeSession({
        transfer_check_confirmed_at: ONAY_ZAMANI,
        courses: [makeCourseRow()],
        rooms: [{ id: 91, room_id: 1, room_name: "D-204", order: 0, capacity_override: null }],
      }),
    );

    await user.click(await screen.findByRole("button", { name: "Devam" }));
    await user.click(await screen.findByRole("button", { name: "Kaydet ve devam et" }));
    await screen.findByRole("heading", { name: "Dağıt" });
  }

  it("KELEBEK: seçenekler sözlük diliyle sorulur; numara + katı dağıtım gövdeye gider", async () => {
    const user = userEvent.setup();
    sessionApi.distribute.mockResolvedValue({
      status: "DISTRIBUTED",
      seed: 4231,
      checkerboard: true,
      placed: 30,
      warnings: [],
      report: makeReport(),
    });
    await kelebekteDagitAdiminaGit(user);

    // Sözlük: "seed" → "dağıtım numarası"; "katı mod (1. halka…)" → "Katı dağıtım…".
    const numara = screen.getByLabelText("Dağıtım numarası (boş bırakılırsa rastgele)");
    const kati = screen.getByRole("checkbox", {
      name: "Katı dağıtım: yan, ön ve arka komşuluk da kesinlikle yasak",
    });
    expect(kati).not.toBeChecked();
    expect(screen.queryByText(/1\. halka|Katı mod|[Ss]eed \(boş/)).not.toBeInTheDocument();

    await user.type(numara, "4231");
    await user.click(kati);
    await user.click(screen.getByRole("button", { name: "Dağıt" }));

    await waitFor(() =>
      expect(sessionApi.distribute).toHaveBeenCalledWith(5, { seed: 4231, strict: true }),
    );
    expect(
      await screen.findByText("Dağıtım tamamlandı: 30 öğrenci yerleşti (dağıtım numarası 4231)."),
    ).toBeInTheDocument();
  });

  it("KELEBEK: uç hatasında 'Dağıtım başarısız.' gösterilir, adımda kalınır", async () => {
    const user = userEvent.setup();
    sessionApi.distribute.mockRejectedValue(new Error("ağ koptu"));
    await kelebekteDagitAdiminaGit(user);

    await user.click(screen.getByRole("button", { name: "Dağıt" }));

    await waitFor(() =>
      expect(sessionApi.distribute).toHaveBeenCalledWith(5, { seed: undefined, strict: false }),
    );
    expect(await screen.findByText("Dağıtım başarısız.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Dağıt" })).toBeInTheDocument();
  });
});
