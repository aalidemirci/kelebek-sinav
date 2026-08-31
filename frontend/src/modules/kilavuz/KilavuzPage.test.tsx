// Kullanım Kılavuzu testleri: adım sırası, ders havuzu pasifleştirme ipucu
// (kullanıcı isteğinin çekirdeği) ve sınav takvimi bölümündeki mevzuat
// dayanakları. Metin kayarsa test kırılır — kılavuz "boş sayfa" olamaz.

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import KilavuzPage from "./KilavuzPage";

function renderPage() {
  return render(
    <MemoryRouter>
      <KilavuzPage />
    </MemoryRouter>,
  );
}

describe("KilavuzPage", () => {
  it("adımları sırayla ve ilgili ekran bağlantılarıyla listeler", () => {
    renderPage();

    expect(
      screen.getByRole("heading", { level: 1, name: "Kullanım Kılavuzu" }),
    ).toBeInTheDocument();
    const basliklar = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent ?? "");
    expect(basliklar[0]).toBe("Kurulum ve okul künyesi");
    expect(basliklar).toContain("Sınav takvimi");
    expect(basliklar).toContain("Zümreler ve zümre başkanları kurulu");

    expect(screen.getByRole("link", { name: "Ders Havuzu" })).toHaveAttribute("href", "/dersler");
    expect(screen.getByRole("link", { name: "Ayarlar → Zümreler" })).toHaveAttribute(
      "href",
      "/ayarlar?tab=zumreler",
    );
  });

  it("ders havuzunda pasifleştirme ipucunu anlatır", () => {
    renderPage();
    expect(screen.getByText(/Okulunuzda okutulmayan dersleri/)).toBeInTheDocument();
    expect(screen.getByText(/ders eşleştirmesi ilk seferde doğru olur/)).toBeInTheDocument();
  });

  it("günlük sınav sayısı sınırını mevzuat dayanağıyla verir", () => {
    renderPage();
    expect(
      screen.getByText(/bir günde yapılacak yazılı ve uygulamalı sınavların sayısının ikiyi/i),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/Ölçme ve Değerlendirme Yönetmeliği/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Yazılı ve Uygulamalı Sınavlar Yönergesi/).length).toBeGreaterThan(
      0,
    );
    expect(screen.getByText(/Dördüncü sınavı hiç kabul etmez/)).toBeInTheDocument();
  });

  it("küme, koltuk sabitleme ve kopyalama adımlarını anlatır", () => {
    renderPage();
    expect(screen.getByText(/İkili eğitim yapıyorsanız derslikleri kümeleyin/)).toBeInTheDocument();
    expect(screen.getByText(/kendi dersliğinde, arka sırada ve tek başına/)).toBeInTheDocument();
    expect(screen.getByText(/tanı ya da rapor bilgisi hiç kaydedilmez/)).toBeInTheDocument();
    expect(screen.getByText(/öğretmen masasına en yakın sıralara/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ayarlar → Şube Kümeleri" })).toHaveAttribute(
      "href",
      "/ayarlar?tab=sube-kumeleri",
    );
  });

  it("Bakanlık/MEM sınavlarının takvimde ayrı göründüğünü söyler", () => {
    renderPage();
    expect(screen.getByText(/BAK \/ İL \/ İLÇE/)).toBeInTheDocument();
    expect(screen.getByText(/mazeret sınavlarının bu takvimi izleyen hafta/)).toBeInTheDocument();
  });
});
