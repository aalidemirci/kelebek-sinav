// Yerleşim krokisi testleri (F3): API mock'lanır; kroki çizimi (rapor, doluluk
// çipleri, seed, rozet, lejant), yer değiştirmenin İKİ YOLU (sürükle-bırak ve
// tıkla-tıkla) ve KİLİT (yalnız DAĞITILDI) doğrulanır. Ortak kurucular
// testFixtures.ts'ten — test dosyası test dosyasından import ETMEZ (OYS Tur 232).
//
// Sürükleme userEvent'te yoktur; fireEvent + sahte `dataTransfer` ile sürülür
// (jsdom DataTransfer'ı desteklemez, RTL bu nesneyi olaya kendisi bağlar).

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { FURNITURE_LABELS } from "../salonlar/planEdit";
import type { ExamSession } from "./api";
import { makeReport, makeRoomGeometry, makeSeating, makeSession, paginated } from "./testFixtures";

const sessionApi = vi.hoisted(() => ({
  seating: vi.fn(),
  swapSeats: vi.fn(),
  moveSeat: vi.fn(),
}));
const roomApi = vi.hoisted(() => ({ list: vi.fn() }));

vi.mock("./api", async (importActual) => {
  const actual = await importActual<typeof import("./api")>();
  return { ...actual, examSessionApi: { ...actual.examSessionApi, ...sessionApi } };
});
vi.mock("../salonlar/api", async (importActual) => {
  const actual = await importActual<typeof import("../salonlar/api")>();
  return { ...actual, examRoomApi: { ...actual.examRoomApi, ...roomApi } };
});

import YerlesimPaneli from "./YerlesimPaneli";

function renderPanel(session: ExamSession) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SnackbarProvider>
        <YerlesimPaneli session={session} />
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

/** İkinci sırası BOŞ geometri: (0,0) dolu ikili sıra, (0,1) boş ikili sıra. */
function bosKoltukluGeometri() {
  return makeRoomGeometry({
    layout_plan: {
      grid: { rows: 1, cols: 3 },
      desks: [
        { row: 0, col: 0, type: "DOUBLE" },
        { row: 0, col: 1, type: "DOUBLE" },
      ],
      furniture: [{ kind: "TEACHER_DESK", row: 0, col: 2 }],
    },
  });
}

/** jsdom'da DataTransfer yoktur — sürükleme olaylarına sahte nesne verilir. */
function sahteDataTransfer() {
  return { dropEffect: "", effectAllowed: "", setData: vi.fn(), getData: vi.fn(() => "") };
}

/** Kaynak öğeyi hedefin üstüne sürükleyip bırakır (dragstart → dragover → drop). */
function surukleBirak(kaynak: HTMLElement, hedef: HTMLElement) {
  const dataTransfer = sahteDataTransfer();
  fireEvent.dragStart(kaynak, { dataTransfer });
  fireEvent.dragOver(hedef, { dataTransfer });
  fireEvent.drop(hedef, { dataTransfer });
}

describe("YerlesimPaneli", () => {
  it("krokiyi kural özeti, doluluk çipi, dağıtım numarası, rozet ve lejantla çizer", async () => {
    const seating = makeSeating();
    seating.rooms[0].assignments[0].status = "PINNED";
    seating.rooms[0].assignments[1].status = "MANUAL";
    sessionApi.seating.mockResolvedValue(seating);
    roomApi.list.mockResolvedValue(paginated([makeRoomGeometry()]));
    const { container } = renderPanel(makeSession({ status: "DISTRIBUTED" }));

    // Kural özeti + doluluk çipi + dağıtım numarası. Motor jargonu yüzeyde yok.
    expect(await screen.findByText("Kural ihlali yok — oturum onaylanabilir.")).toBeInTheDocument();
    expect(screen.getByText("D-204: 2/4 (%50)")).toBeInTheDocument();
    expect(screen.getByText(/Dağıtım numarası:/)).toBeInTheDocument();
    expect(screen.getByText("1234")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/seed|sert kısıt|İHLAL = 0|1\. halka|skoru/i);
    // Salon sekmesi + koltuklar (grid kimliğinden) + mobilya. Mobilya etiketi salon
    // editörüyle AYNI kaynaktan gelir (planEdit) — "Öğrt. Masası" kısaltması yok.
    expect(screen.getByRole("tab", { name: "D-204" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Ayşe Yılmaz/ })).toBeInTheDocument();
    expect(screen.getByText(FURNITURE_LABELS.TEACHER_DESK)).toBeInTheDocument();
    expect(screen.getByText("Öğretmen masası")).toBeInTheDocument();
    // PINNED/MANUAL rozetleri (class_label ile aynı span'da).
    expect(screen.getByText("9/A · Sabit")).toBeInTheDocument();
    expect(screen.getByText("9/B · Elle")).toBeInTheDocument();
    // Grup lejantı insan-okur etiketle.
    expect(screen.getByText("Matematik — 9. Sınıf")).toBeInTheDocument();
  });

  it("motor ölçütleri varsayılan KAPALI 'Ayrıntı' bölümündedir", async () => {
    sessionApi.seating.mockResolvedValue(
      makeSeating({
        report: makeReport({
          first_ring_same_group_pairs: 3,
          proximity_score: 12.5,
          cross_group_same_section_first_ring_pairs: 4,
          min_same_group_distance: { "10:9": 1.4142 },
        }),
      }),
    );
    roomApi.list.mockResolvedValue(paginated([makeRoomGeometry()]));
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    const ozet = await screen.findByText("Ayrıntı");
    const ayrinti = ozet.closest("details");
    expect(ayrinti).not.toBeNull();
    expect(ayrinti).not.toHaveAttribute("open");
    // Ölçütler DOM'dadır ama kapalı bölümün içinde — sade etiketlerle.
    const olcut = within(ayrinti as HTMLElement).getByText(
      "Yan yana/ön-arka düşen aynı sınav çifti: 3",
    );
    expect(olcut).not.toBeVisible();
    // Sayılar Türkçe biçimde (ondalık virgül — lib/format.ts).
    expect(
      within(ayrinti as HTMLElement).getByText("Yakınlık puanı (düşük iyidir): 12,5"),
    ).toBeInTheDocument();
    expect(
      within(ayrinti as HTMLElement).getByText(/Aynı şubeden, farklı sınava giren komşu çift:\s*4/),
    ).toBeInTheDocument();
    // En kısa mesafe grup anahtarıyla değil ders etiketiyle yazılır.
    expect(
      within(ayrinti as HTMLElement).getByText("Matematik — 9. Sınıf: 1,414"),
    ).toBeInTheDocument();
  });

  it("kural ihlali varken özet 'onaylanamaz' der ve ihlalleri listeler", async () => {
    sessionApi.seating.mockResolvedValue(
      makeSeating({
        report: makeReport({
          is_valid: false,
          hard_violations: ["101 ile 102 aynı sırada.", "103 ile 104 aynı sırada."],
        }),
      }),
    );
    roomApi.list.mockResolvedValue(paginated([makeRoomGeometry()]));
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    const uyari = await screen.findByRole("alert");
    expect(uyari).toHaveTextContent("2 kural ihlali var — onaylanamaz.");
    expect(within(uyari).getByText("101 ile 102 aynı sırada.")).toBeInTheDocument();
  });

  it("'Kendi dersliğinde' düzeninde dağıtım numarası satırı gösterilmez (karıştırma yok, hep 0)", async () => {
    sessionApi.seating.mockResolvedValue(
      makeSeating({ distribution_params: { seed: 0, layout_mode: "HOME_CLASSROOM" } }),
    );
    roomApi.list.mockResolvedValue(paginated([makeRoomGeometry()]));
    renderPanel(makeSession({ status: "DISTRIBUTED", layout_mode: "HOME_CLASSROOM" }));

    expect(await screen.findByText("Kural ihlali yok — oturum onaylanabilir.")).toBeInTheDocument();
    expect(screen.queryByText(/Dağıtım numarası/)).not.toBeInTheDocument();
  });

  it("onaylı oturumda özet 'onaylanabilir' demez (zaten onaylı)", async () => {
    sessionApi.seating.mockResolvedValue(makeSeating({ status: "APPROVED" }));
    roomApi.list.mockResolvedValue(paginated([makeRoomGeometry()]));
    renderPanel(makeSession({ status: "APPROVED" }));

    expect(await screen.findByText("Kural ihlali yok.")).toBeInTheDocument();
    expect(screen.queryByText(/onaylanabilir/)).not.toBeInTheDocument();
  });

  it("DAĞITILDI: iki koltuğa tıklayınca swap-seats çağrılır, ihlalsiz sonuç yeşil", async () => {
    const user = userEvent.setup();
    sessionApi.seating.mockResolvedValue(makeSeating());
    roomApi.list.mockResolvedValue(paginated([makeRoomGeometry()]));
    sessionApi.swapSeats.mockResolvedValue({ swapped: [], report: makeReport() });
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    await user.click(await screen.findByRole("button", { name: /Ayşe Yılmaz/ }));
    // İlk seçim vurgulanır (aria-pressed + etiket eki).
    expect(screen.getByRole("button", { name: /Ayşe Yılmaz.*takas için seçili/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await user.click(screen.getByRole("button", { name: /Mehmet Demir/ }));

    await waitFor(() => expect(sessionApi.swapSeats).toHaveBeenCalledWith(5, 11, 12));
    expect(await screen.findByText("Takas yapıldı; kural ihlali yok.")).toBeInTheDocument();
  });

  it("takas sonrası kural ihlali kırmızı snackbar'la duyurulur", async () => {
    const user = userEvent.setup();
    sessionApi.seating.mockResolvedValue(makeSeating());
    roomApi.list.mockResolvedValue(paginated([makeRoomGeometry()]));
    sessionApi.swapSeats.mockResolvedValue({
      swapped: [],
      report: makeReport({
        is_valid: false,
        hard_violations: ["101 ile 102 aynı grupta yan yana."],
      }),
    });
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    await user.click(await screen.findByRole("button", { name: /Ayşe Yılmaz/ }));
    await user.click(screen.getByRole("button", { name: /Mehmet Demir/ }));

    expect(
      await screen.findByText(
        "Takas yapıldı ama 1 kural ihlali oluştu; bu hâliyle oturum onaylanamaz.",
      ),
    ).toBeInTheDocument();
  });

  it("ONAYLI oturumda takas kilitli: koltuklar disabled, uç çağrılmaz", async () => {
    const user = userEvent.setup();
    sessionApi.seating.mockResolvedValue(makeSeating({ status: "APPROVED" }));
    roomApi.list.mockResolvedValue(paginated([bosKoltukluGeometri()]));
    renderPanel(makeSession({ status: "APPROVED" }));

    const seatA = await screen.findByRole("button", { name: /Ayşe Yılmaz/ });
    expect(seatA).toBeDisabled();
    // Yer değiştirme yönergesi de gösterilmez.
    expect(screen.queryByText(/Yer değiştirme:/)).not.toBeInTheDocument();
    // Sürüklenemez ve boş koltuk hedef değildir (tıklama da uç çağırmaz).
    expect(seatA).toHaveAttribute("draggable", "false");
    await user.click(seatA);
    await user.click(screen.getByRole("button", { name: /Mehmet Demir/ }));
    await user.click(screen.getAllByRole("button", { name: /^Boş koltuk/ })[0]);
    expect(sessionApi.swapSeats).not.toHaveBeenCalled();
    expect(sessionApi.moveSeat).not.toHaveBeenCalled();
  });

  it("DAĞITILDI: öğrenciyi boş koltuğa sürükleyince move-seat çağrılır", async () => {
    sessionApi.seating.mockResolvedValue(makeSeating());
    roomApi.list.mockResolvedValue(paginated([bosKoltukluGeometri()]));
    sessionApi.moveSeat.mockResolvedValue({ moved: {}, report: makeReport() });
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    const kaynak = await screen.findByRole("button", { name: /Ayşe Yılmaz/ });
    // Boş koltuk konumuyla adlandırılır (planEdit ile AYNI etiket kaynağı).
    const bos = screen.getByRole("button", { name: /^Boş koltuk \(ön cephe, 2\. sütun, sol/ });
    surukleBirak(kaynak, bos);

    // Hedef koltuk KİMLİĞİYLE gider; koltuk numarasını backend türetir.
    await waitFor(() =>
      expect(sessionApi.moveSeat).toHaveBeenCalledWith(5, 11, {
        room: 1,
        desk_row: 0,
        desk_col: 1,
        slot: 0,
      }),
    );
    expect(await screen.findByText("Öğrenci taşındı; kural ihlali yok.")).toBeInTheDocument();
    expect(sessionApi.swapSeats).not.toHaveBeenCalled();
  });

  it("dolu koltuğun üstüne bırakınca taşıma değil TAKAS olur", async () => {
    sessionApi.seating.mockResolvedValue(makeSeating());
    roomApi.list.mockResolvedValue(paginated([bosKoltukluGeometri()]));
    sessionApi.swapSeats.mockResolvedValue({ swapped: [], report: makeReport() });
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    const kaynak = await screen.findByRole("button", { name: /Ayşe Yılmaz/ });
    surukleBirak(kaynak, screen.getByRole("button", { name: /Mehmet Demir/ }));

    await waitFor(() => expect(sessionApi.swapSeats).toHaveBeenCalledWith(5, 11, 12));
    expect(sessionApi.moveSeat).not.toHaveBeenCalled();
  });

  it("fare olmadan da taşınır: önce öğrenci, sonra boş koltuk tıklanır", async () => {
    const user = userEvent.setup();
    sessionApi.seating.mockResolvedValue(makeSeating());
    roomApi.list.mockResolvedValue(paginated([bosKoltukluGeometri()]));
    sessionApi.moveSeat.mockResolvedValue({ moved: {}, report: makeReport() });
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    // Öğrenci seçilmeden boş koltuk tıklanabilir DEĞİLDİR (gürültü olmasın).
    const bosKoltuklar = await screen.findAllByRole("button", { name: /^Boş koltuk/ });
    expect(bosKoltuklar[0]).toBeDisabled();

    await user.click(screen.getByRole("button", { name: /Ayşe Yılmaz/ }));
    // Seçimden sonra boş koltuk etkinleşir ve ne yapacağını söyler.
    const hedef = (await screen.findAllByRole("button", { name: /^Boş koltuk/ }))[0];
    expect(hedef).toBeEnabled();
    expect(hedef).toHaveAccessibleName(/seçili öğrenciyi buraya taşı$/);
    await user.click(hedef);

    await waitFor(() =>
      expect(sessionApi.moveSeat).toHaveBeenCalledWith(5, 11, {
        room: 1,
        desk_row: 0,
        desk_col: 1,
        slot: 0,
      }),
    );
  });

  it("kuralla sabitlenmiş öğrenci sürüklenemez (hedef olmaya devam eder)", async () => {
    const seating = makeSeating();
    seating.rooms[0].assignments[0].status = "PINNED";
    sessionApi.seating.mockResolvedValue(seating);
    roomApi.list.mockResolvedValue(paginated([bosKoltukluGeometri()]));
    sessionApi.swapSeats.mockResolvedValue({ swapped: [], report: makeReport() });
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    const sabit = await screen.findByRole("button", { name: /Ayşe Yılmaz/ });
    expect(sabit).toHaveAttribute("draggable", "false");

    // Ama hedef olabilir: sabit koltuğa bırakılan öğrenci takas denemesi yapar;
    // reddi (ve gerekçesini) backend söyler.
    surukleBirak(screen.getByRole("button", { name: /Mehmet Demir/ }), sabit);
    await waitFor(() => expect(sessionApi.swapSeats).toHaveBeenCalledWith(5, 12, 11));
  });

  it("taşıma sonrası kural ihlali kırmızı snackbar'la duyurulur", async () => {
    sessionApi.seating.mockResolvedValue(makeSeating());
    roomApi.list.mockResolvedValue(paginated([bosKoltukluGeometri()]));
    sessionApi.moveSeat.mockResolvedValue({
      moved: {},
      report: makeReport({ is_valid: false, hard_violations: ["101 ile 102 aynı sırada."] }),
    });
    renderPanel(makeSession({ status: "DISTRIBUTED" }));

    const kaynak = await screen.findByRole("button", { name: /Ayşe Yılmaz/ });
    surukleBirak(kaynak, screen.getAllByRole("button", { name: /^Boş koltuk/ })[0]);

    expect(
      await screen.findByText(
        "Öğrenci taşındı ama 1 kural ihlali oluştu; bu hâliyle oturum onaylanamaz.",
      ),
    ).toBeInTheDocument();
  });
});
