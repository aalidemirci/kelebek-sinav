// Kullanım Kılavuzu testleri: adım sırası, ders havuzu pasifleştirme ipucu
// (kullanıcı isteğinin çekirdeği) ve sınav takvimi bölümündeki mevzuat
// dayanakları. Metin kayarsa test kırılır — kılavuz "boş sayfa" olamaz.
//
// 03.09.2026'da eklenen bölümler de kilitlidir: çizelge ataması (1. adım),
// yürürlükteki TTK çizelgesi ve düzenlemenin kalıcı olmaması (4. adım),
// varsayılan salon şablonu + toplu uygulama (6. adım), yerleştirme kuralının
// tuzakları (8. adım) ve yedekten geri yükleme (9. adım). Bu özellikler
// kılavuzda ANLATILMADAN sürüme girmesin.
//
// NOT: `getByText` yalnız elemanın DOĞRUDAN metin çocuklarına bakar; bu yüzden
// aranan ifade tek bir elemanın (çoğu yerde <strong>) içinde kalacak şekilde
// seçilmiştir — <strong> sınırını aşan bir regex hiç eşleşmez.

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

  it("ders havuzunda tür/sınav biçimi ayrımını ve pasifleştirme ipucunu anlatır", () => {
    renderPage();
    expect(screen.getByText(/Okulunuzda okutulmayan dersleri/)).toBeInTheDocument();
    expect(screen.getByText(/ders eşleştirmesi ilk seferde doğru olur/)).toBeInTheDocument();
    // Sınav biçimi alanı pasifleştirme ihtiyacını kaldırdı — kılavuz bunu söylemeli.
    expect(screen.getByText(/Rehberlik ve Yönlendirme/)).toBeInTheDocument();
    expect(screen.getByText(/pasifleştirmenize/)).toBeInTheDocument();
  });

  it("takvim havuzunun zorunlu/seçmeli ders akışını anlatır", () => {
    renderPage();
    expect(screen.getByRole("heading", { level: 3, name: /Havuzu doldurmak/ })).toBeInTheDocument();
    expect(screen.getByText(/Havuzda zaten bulunan ders işaretli ve/)).toBeInTheDocument();
    expect(
      screen.getByText(/takvime kümenin adı değil, seçilen şubeler yazılır/),
    ).toBeInTheDocument();
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

  it("okul türünü çizelge kaynağı olarak anlatır ve kademeli dönüşümü söyler", () => {
    renderPage();
    expect(screen.getByText(/hangi MEB haftalık ders çizelgesinin/)).toBeInTheDocument();
    expect(screen.getByText(/çizelge ataması/)).toBeInTheDocument();
    expect(
      screen.getByText(/Kademeli bir çizelgede kapsanmayan seviye kalırsa/),
    ).toBeInTheDocument();
  });

  it("ders havuzunun yürürlükteki çizelgeden türediğini ve senkron sınırlarını anlatır", () => {
    renderPage();
    expect(screen.getByText(/“Yürürlükteki çizelge”/)).toBeInTheDocument();
    expect(screen.getByText(/“Çizelge dışı”/)).toBeInTheDocument();
    // Çizelge dersinde Düzenle kalıcı DEĞİL (senkron levels/tür/sınav biçimini ezer);
    // pasifleştirme kalıcı. Kılavuz bu ayrımı söylemezse kullanıcı tuzağa düşer.
    expect(
      screen.getByText(/çizelgeden gelen bir derste bu düzenleme kalıcı değildir/),
    ).toBeInTheDocument();
    expect(screen.getByText(/pasifleştirme her zaman kalıcıdır/)).toBeInTheDocument();
  });

  it("varsayılan salon şablonunu ve toplu uygulamayı anlatır", () => {
    renderPage();
    expect(screen.getByText(/varsayılan şablonla/)).toBeInTheDocument();
    expect(screen.getByText(/öğretmen masasının önünden/)).toBeInTheDocument();
    expect(screen.getByText(/“Şablonu topluca uygula”/)).toBeInTheDocument();
    expect(screen.getByText(/Yerleşimi yapılmış salonlar atlanır/)).toBeInTheDocument();
  });

  it("yerleştirme kuralının seçeneklerini, zamanlamasını ve tuzaklarını anlatır", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { level: 3, name: /Engelli ve özel durumlu öğrencilerin/ }),
    ).toBeInTheDocument();
    // BEP dayanağı: ortak sınavlara katılım süreçleri okul müdürlüğünün sorumluluğunda.
    expect(
      screen.getByText(/katılımıyla ilgili süreçlerden okul müdürlükleri sorumludur/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Kuralı dağıtımdan önce ekleyin/)).toBeInTheDocument();
    expect(screen.getByText(/“Kendi dersliğinde” için bağlı şube şarttır/)).toBeInTheDocument();
    expect(
      screen.getByText(/Kuralda seçtiğiniz salonu oturumun salon listesine de ekleyin/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Koltuk, numarasıyla değil koordinatıyla saklanır/),
    ).toBeInTheDocument();
    expect(screen.getByText(/eklendiği oturuma özgüdür/)).toBeInTheDocument();
  });

  it("yedek alma ve yedekten geri yükleme akışını anlatır", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { level: 3, name: "Yedek alma ve yedekten dönme" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/her açılışta kendiliğinden bir/)).toBeInTheDocument();
    expect(screen.getByText(/Günlük yedekler de aynı bilgisayarda tutulur/)).toBeInTheDocument();
    expect(screen.getByText(/“Yedekten geri yükle”/)).toBeInTheDocument();
    expect(screen.getByText(/kapatılıp yeniden açılmalıdır/)).toBeInTheDocument();
    expect(screen.getByText(/“Yedekten Geri Yükle”/)).toBeInTheDocument();
  });

  it("Bakanlık/MEM sınavlarının takvimde ayrı göründüğünü söyler", () => {
    renderPage();
    expect(screen.getByText(/BAK \/ İL \/ İLÇE/)).toBeInTheDocument();
    expect(screen.getByText(/mazeret sınavlarının bu takvimi izleyen hafta/)).toBeInTheDocument();
  });
});
