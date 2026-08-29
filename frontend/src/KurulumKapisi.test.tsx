// Kurulum kapısı testi (F4-D4) — App.test.tsx kapının SONUCUNU (hangi sayfa
// açılıyor) pinler; burada davranışın kendisi izole edilir: yönlendirme, sihirbaz
// rotasının muaf olması, sihirbaz bitince geri sekmeme (durumun yeniden okunması)
// ve kurulum tamamken gereksiz istek atılmaması.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { KapiYonlendirmesi } from "./KurulumKapisi";
import type { SetupStatus } from "./modules/okul/api";

const okulApiMock = vi.hoisted(() => ({ getSetupStatus: vi.fn() }));

vi.mock("./modules/okul/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./modules/okul/api")>();
  return { ...actual, okulApi: okulApiMock };
});

import KurulumKapisi from "./KurulumKapisi";

const TAMAM: SetupStatus = {
  setup_completed: true,
  school_name: "Okul",
  has_active_school_year: true,
  student_count: 1,
  personnel_count: 1,
  class_section_count: 1,
};

const EKSIK: SetupStatus = { ...TAMAM, setup_completed: false };

/** Sihirbaz rotasına düşen yönlendirme sebebini ekrana yazar (sözleşme izi). */
function SebepIzi() {
  const { state } = useLocation();
  const sebep = (state as KapiYonlendirmesi | null)?.kapiYonlendirdi ?? "yok";
  return <p>Yönlendiren yol: {sebep}</p>;
}

/** Kapının sardığı sahte rota ağacı — gerçek sayfalara bağımlı kalmadan sınanır. */
function Deneme({ yol }: { yol: string }) {
  return (
    <MemoryRouter initialEntries={[yol]}>
      <KurulumKapisi>
        <Routes>
          <Route
            path="/"
            element={
              <>
                <h1>Panel içeriği</h1>
                <Link to="/kisiler">Kişilere git</Link>
              </>
            }
          />
          <Route path="/kisiler" element={<h1>Kişiler içeriği</h1>} />
          <Route
            path="/kurulum"
            element={
              <>
                <h1>Sihirbaz içeriği</h1>
                <SebepIzi />
                <Link to="/">Kurulumu bitir</Link>
              </>
            }
          />
        </Routes>
      </KurulumKapisi>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("KurulumKapisi", () => {
  it("kurulum eksikse içeriği göstermeden sihirbaza yönlendirir", async () => {
    okulApiMock.getSetupStatus.mockResolvedValue(EKSIK);
    render(<Deneme yol="/" />);
    expect(await screen.findByRole("heading", { name: "Sihirbaz içeriği" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Panel içeriği" })).not.toBeInTheDocument();
  });

  it("yönlendirmede hangi yoldan gelindiğini taşır (sessiz sekme yok)", async () => {
    // Üst menüden Kişiler'e tıklayan kullanıcı sihirbaza düşer; sihirbazın bunu
    // açıklayabilmesi için sebep gezinme durumunda taşınır.
    okulApiMock.getSetupStatus.mockResolvedValue(EKSIK);
    render(<Deneme yol="/kisiler" />);
    expect(await screen.findByText("Yönlendiren yol: /kisiler")).toBeInTheDocument();
  });

  it("sihirbaz rotasını durum beklemeden açar", () => {
    // Hiç sonuçlanmayan istek: kapı beklemeden içeriği göstermeli.
    okulApiMock.getSetupStatus.mockReturnValue(new Promise<SetupStatus>(() => {}));
    render(<Deneme yol="/kurulum" />);
    expect(screen.getByRole("heading", { name: "Sihirbaz içeriği" })).toBeInTheDocument();
  });

  it("sihirbaz bitirilince geri sekmez — durumu yeniden okur", async () => {
    const user = userEvent.setup();
    // İlk okuma "eksik" (sihirbaz açılışı), sonraki okumalar "tamam" (bitirildi).
    okulApiMock.getSetupStatus.mockResolvedValueOnce(EKSIK).mockResolvedValue(TAMAM);
    render(<Deneme yol="/kurulum" />);
    await user.click(await screen.findByRole("link", { name: "Kurulumu bitir" }));
    expect(await screen.findByRole("heading", { name: "Panel içeriği" })).toBeInTheDocument();
  });

  it("kurulum tamamsa sonraki gezinmelerde durumu tekrar sormaz", async () => {
    const user = userEvent.setup();
    okulApiMock.getSetupStatus.mockResolvedValue(TAMAM);
    render(<Deneme yol="/" />);
    await user.click(await screen.findByRole("link", { name: "Kişilere git" }));
    expect(await screen.findByRole("heading", { name: "Kişiler içeriği" })).toBeInTheDocument();
    expect(okulApiMock.getSetupStatus).toHaveBeenCalledTimes(1);
  });

  it("durum okunamazsa kapıyı açar (fail-open)", async () => {
    okulApiMock.getSetupStatus.mockRejectedValue(new Error("ağ yok"));
    render(<Deneme yol="/" />);
    expect(await screen.findByRole("heading", { name: "Panel içeriği" })).toBeInTheDocument();
  });
});
