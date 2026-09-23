// Güvenlik kapısı testi (F5-D5): kilitliyken içerik GÖRÜNMEZ, kilit açılınca
// görünür; durum ucu hata verirse kapı FAIL-OPEN davranır (kullanıcı içeride
// kalmaz — gerçek kapı backend'dedir).

import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const guvenlik = vi.hoisted(() => ({
  durum: vi.fn(),
  kur: vi.fn(),
  ac: vi.fn(),
  kilitle: vi.fn(),
  kurtar: vi.fn(),
  parolaDegistir: vi.fn(),
  kaldir: vi.fn(),
}));

vi.mock("./api", () => ({ guvenlikApi: guvenlik }));
// Kayıp ekranının içindeki geri yükleme kartı kendi testinde sınanır.
vi.mock("./YedektenGeriYukleme", () => ({ default: () => <p>Geri yükleme kartı</p> }));

import { kilitKapisiYayinla } from "../../lib/kilit";
import GuvenlikKapisi, { kilitOlayiYayinla } from "./GuvenlikKapisi";

const ACIK = {
  password_set: true,
  locked: false,
  security_file_missing: false,
  reset_available: false,
  transition_pending: false,
  transition: "",
  protected_fields: ["ad"],
};
const KILITLI = { ...ACIK, locked: true };

function icerikliKapi() {
  return render(
    <GuvenlikKapisi>
      <p>Gizli içerik</p>
    </GuvenlikKapisi>,
  );
}

describe("GuvenlikKapisi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("kilitliyken içerik yerine kilit ekranını gösterir", async () => {
    guvenlik.durum.mockResolvedValue(KILITLI);
    icerikliKapi();
    expect(await screen.findByText("Kayıtlar kilitli")).toBeInTheDocument();
    expect(screen.queryByText("Gizli içerik")).toBeNull();
  });

  it("kilit açılınca içeriği gösterir", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValue(KILITLI);
    guvenlik.ac.mockResolvedValue(ACIK);
    icerikliKapi();

    await kullanici.type(await screen.findByLabelText(/Uygulama parolası/), "Deneme-Parola-1");
    await kullanici.click(screen.getByRole("button", { name: "Aç" }));

    expect(await screen.findByText("Gizli içerik")).toBeInTheDocument();
  });

  it("parola kurulu değilse doğrudan içeriği gösterir", async () => {
    guvenlik.durum.mockResolvedValue({ ...ACIK, password_set: false });
    icerikliKapi();
    expect(await screen.findByText("Gizli içerik")).toBeInTheDocument();
  });

  it("durum ucu hata verirse fail-open davranır", async () => {
    guvenlik.durum.mockRejectedValue(new Error("bağlantı yok"));
    icerikliKapi();
    expect(await screen.findByText("Gizli içerik")).toBeInTheDocument();
  });

  it("kilitle olayında içeriği gizler", async () => {
    guvenlik.durum.mockResolvedValue(ACIK);
    icerikliKapi();
    expect(await screen.findByText("Gizli içerik")).toBeInTheDocument();

    act(() => kilitOlayiYayinla());
    await waitFor(() => expect(screen.queryByText("Gizli içerik")).toBeNull());
    expect(screen.getByText("Kayıtlar kilitli")).toBeInTheDocument();
  });

  it("güvenlik dosyası kayıpsa kilit ekranı yerine kayıp ekranını gösterir", async () => {
    guvenlik.durum.mockResolvedValue({ ...KILITLI, security_file_missing: true });
    icerikliKapi();

    expect(
      await screen.findByRole("heading", { name: "Güvenlik dosyası bulunamadı ya da okunamıyor" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Kayıtlar kilitli")).toBeNull();
    expect(screen.queryByText("Gizli içerik")).toBeNull();
    expect(screen.getByText("Geri yükleme kartı")).toBeInTheDocument();
  });

  it("oturum ortasındaki 423 olayında durumu sunucudan yeniden okur", async () => {
    guvenlik.durum.mockResolvedValueOnce(ACIK);
    icerikliKapi();
    expect(await screen.findByText("Gizli içerik")).toBeInTheDocument();

    guvenlik.durum.mockResolvedValueOnce({ ...KILITLI, security_file_missing: true });
    act(() => kilitKapisiYayinla());

    expect(
      await screen.findByRole("heading", { name: "Güvenlik dosyası bulunamadı ya da okunamıyor" }),
    ).toBeInTheDocument();
    expect(guvenlik.durum).toHaveBeenCalledTimes(2);
  });

  it("kayıp ekranındaki yeniden denetle dosya geri konunca kilit ekranına geçer", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValueOnce({ ...KILITLI, security_file_missing: true });
    icerikliKapi();

    guvenlik.durum.mockResolvedValueOnce(KILITLI);
    await kullanici.click(await screen.findByRole("button", { name: "Yeniden denetle" }));

    expect(await screen.findByText("Kayıtlar kilitli")).toBeInTheDocument();
  });
});
