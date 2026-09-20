// Kullanım Kılavuzu testleri: adım sırası, ders havuzu pasifleştirme ipucu
// (kullanıcı isteğinin çekirdeği) ve sınav takvimi bölümündeki mevzuat
// dayanakları. Metin kayarsa test kırılır — kılavuz "boş sayfa" olamaz.
//
// 03.09.2026'da eklenen bölümler de kilitlidir: çizelge ataması (1. adım),
// yürürlükteki TTK çizelgesi ve düzenlemenin kalıcı olmaması (4. adım),
// varsayılan salon şablonu + toplu uygulama (6. adım), yerleştirme kuralının
// tuzakları (8. adım) ve yedekten geri yükleme (10. adım). Bu özellikler
// kılavuzda ANLATILMADAN sürüme girmesin.
//
// 18.09.2026 (değerlendirme §3.5): yanlış bilgiler düzeltildi ("her açılışta
// yedek" → her gün ilk açılışta; evrak onayı beklemez; olmayan "Yeniden Dağıt"
// düğmesi; çizelge verisi paragrafı), eksik konular eklendi (yoklama, muaf
// öğretmenler, Ayarlar → Şubeler, süreç takip kalemleri, parola/kilit/kurtarma
// anahtarı, güncelleme, Pardus geri yükleme) ve sözlük turu yapıldı.
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
    expect(basliklar).toContain("Evrak, gözetmenler ve yoklama");
    expect(basliklar).toContain("Bakım: yedek, parola ve güncelleme");

    // Sayfa adı her yerde "Ders Havuzu"dur (4. adım + seçmeli öğrenci listesi
    // + 7. adım ipucu).
    const dersHavuzu = screen.getAllByRole("link", { name: "Ders Havuzu" });
    expect(dersHavuzu.length).toBe(3);
    for (const link of dersHavuzu) expect(link).toHaveAttribute("href", "/dersler");
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

  it("seçmeliyi şubenin bir kısmı alıyorsa öğrenci listesini ve e-Okul raporunu anlatır", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { level: 3, name: /Seçmeli dersi şubenin bir kısmı alıyorsa/ }),
    ).toBeInTheDocument();
    // e-Okul yolu ekrandaki adlarla birebir: ekran → Raporlar → rapor kodu ve adı.
    expect(screen.getByText("Öğrenci Seçmeli Derslerini Belirle")).toBeInTheDocument();
    expect(screen.getByText("OOK10002R010 - Seçmeli Ders Öğrencileri")).toBeInTheDocument();
    // Excel ihracı ders adlarını düşürür — yalnız PDF okunur.
    expect(screen.getByText(/Excel çıktısında ders adları bulunmaz/)).toBeInTheDocument();
    expect(screen.getByText(/iki dersi birden alan öğrenci yoksa/)).toBeInTheDocument();
    // Havuz otomasyonu: yeni seçmeli onayla eklenir; açılmayan gizlenir ama pasif olmaz.
    expect(screen.getByText(/Havuza ekle/)).toBeInTheDocument();
    expect(screen.getByText(/Bu yıl açılmadı/)).toBeInTheDocument();
    expect(
      screen.getByText(/pasifleştirilmez; şubelerini girerseniz yeniden açılır/),
    ).toBeInTheDocument();
    // "Ortak" yalnız MEB anlamında (okul geneli sınav) geçer — docs/sozluk.md.
    expect(screen.queryByText(/ortak öğrenci/i)).not.toBeInTheDocument();
  });

  it("sınav haftalarını Bakanlık yazısıyla verir; son günden başlama bir tercihtir", () => {
    renderPage();
    // 2026-2027 için ÖDSHGM 10.09.2026 tarihli yazı (docs/mevzuat/meb-2026-2027-…).
    expect(screen.getByText(/10\.09\.2026 tarihli yazısı esastır/)).toBeInTheDocument();
    expect(screen.getByText(/1\. dönem 1\. yazılı 2-13 Kasım 2026/)).toBeInTheDocument();
    expect(screen.getByText(/Bu tarihleri kullan/)).toBeInTheDocument();
    expect(screen.getByText(/sınav haftalarının son gününden başlanarak/)).toBeInTheDocument();
    expect(screen.getByText(/kutuyu kaldırırsanız sınavlar günlere dengeli/)).toBeInTheDocument();
    expect(screen.getByText(/merkezî bir sınav denk gelirse/)).toBeInTheDocument();
    // Yazının eki: ülke geneli sınavlar — tarihleri resmî ekle birebir, saat verilmez.
    expect(
      screen.getByText(/10\. sınıf Türk Dili ve Edebiyatı \(12\.11\.2026/),
    ).toBeInTheDocument();
    expect(screen.getByText(/10\. sınıf Matematik \(09\.06\.2027 Çarşamba\)/)).toBeInTheDocument();
    expect(screen.getByText(/Bakanlık takvimi ders saatini vermez/)).toBeInTheDocument();
    expect(screen.getByText("“Takvime uygula”")).toBeInTheDocument();
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
    expect(screen.getByText(/İkili eğitim yapıyorsanız salonları kümeleyin/)).toBeInTheDocument();
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
    // Tam eşleşme: kartın adı <strong> içindedir (4. adım da aynı sözü cümle içinde anar).
    expect(screen.getByText("çizelge ataması")).toBeInTheDocument();
    expect(
      screen.getByText(/Kademeli bir çizelgede kapsanmayan sınıf düzeyi kalırsa/),
    ).toBeInTheDocument();
  });

  it("çizelge verisinin gerçek durumunu söyler: sekiz tür var, eksikler adıyla sayılır", () => {
    renderPage();
    // Eski metin "çizelge verisi henüz gelmemiş türler" diyordu — sekiz türün de
    // çizelgesi gömülüdür; eksik kalanlar docs/teknik-borc.md TB2'dekilerdir.
    expect(screen.getByText(/sekizinin de çizelgesi programla birlikte gelir/)).toBeInTheDocument();
    expect(screen.getByText(/Çizelgede eksik kalanlar sınırlıdır/)).toBeInTheDocument();
    expect(screen.getByText(/alan\/dal meslek derslerini ve seçmeli dersleri/)).toBeInTheDocument();
    expect(
      screen.getByText(/12\. sınıfın tabi olduğu önceki çizelge bulunmaz/),
    ).toBeInTheDocument();
    // TTK 02.09.2026/102: Spor Lisesi'nin yeni çizelgesi 2026-2027'den itibaren bütün
    // sınıf düzeylerinde — önceki çizelge boşluğu yalnız Güzel Sanatlar'da kaldı.
    expect(screen.getByText(/Spor Lisesinde bu boşluk yoktur/)).toBeInTheDocument();
    expect(screen.queryByText(/Güzel Sanatlar ve Spor Liselerinde/)).not.toBeInTheDocument();
    expect(screen.queryByText(/çizelge verisi henüz gelmemiş türler/)).not.toBeInTheDocument();
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
    // Düğmenin adı "Salon kümeleri"dir (eski "Kümeler" / "Derslik Kümeleri" değil).
    expect(screen.getByText("“Salon kümeleri”")).toBeInTheDocument();
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
    // Liste dışı salon artık evrakta basılıyor (A1 düzeltmesi) — eski "o salon için
    // evrak basılmaz" uyarısı yanlış bilgi olurdu.
    expect(
      screen.getByText(/Kural, oturumun salon listesinde olmayan bir salonu da hedef alabilir/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/salon sınav evrakı basılmaz/)).not.toBeInTheDocument();
    expect(
      screen.getByText(/Koltuk, numarasıyla değil koordinatıyla saklanır/),
    ).toBeInTheDocument();
    expect(screen.getByText(/eklendiği oturuma özgüdür/)).toBeInTheDocument();
  });

  it("dağıtım sonrası iki çıkış yolunu gerçek düğme adlarıyla anlatır", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { level: 3, name: /“Yeniden dağıt” ve “Taslağa al”/ }),
    ).toBeInTheDocument();
    // Düğme adı cümle düzenindedir; jargon ("çekirdek sayı") yerine sözlük terimi.
    expect(screen.getAllByText("“Yeniden dağıt”").length).toBeGreaterThan(0);
    expect(screen.queryByText(/Yeniden Dağıt/)).not.toBeInTheDocument();
    expect(screen.queryByText(/çekirdek sayı/)).not.toBeInTheDocument();
    expect(
      screen.getByText(/Aynı dağıtım\s+numarası \(seed\) aynı dağıtımı üretir/),
    ).toBeInTheDocument();
  });

  it("takvim onayını tek “Onayla” adımıyla anlatır", () => {
    renderPage();
    expect(screen.getByText(/Takvimin iki durumu vardır/)).toBeInTheDocument();
    expect(screen.queryByText(/Onaya Sunuldu/)).not.toBeInTheDocument();
    expect(screen.getByText(/program onayın kalkacağını söyleyip sizden onay/)).toBeInTheDocument();
  });

  it("evrakın dağıtımdan itibaren basıldığını söyler (onay beklenmez)", () => {
    renderPage();
    expect(screen.getByText("dağıtıldığı andan itibaren")).toBeInTheDocument();
    expect(screen.queryByText(/Oturum onaylanınca evrak paneli açılır/)).not.toBeInTheDocument();
  });

  it("muafiyetin nerede tanımlandığını söyler", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { level: 3, name: "Gözetmen görevlendirme ve muaf öğretmenler" }),
    ).toBeInTheDocument();
    expect(screen.getByText("“Muaf öğretmenler”")).toBeInTheDocument();
  });

  it("yoklama sekmesini mazeret süresinin dayanağıyla anlatır", () => {
    renderPage();
    expect(
      screen.getByRole("heading", {
        level: 3,
        name: "Yoklama: sınava girmeyen öğrenciler ve mazeret",
      }),
    ).toBeInTheDocument();
    // Alıntı depodaki Yönerge md. 5 metniyle birebirdir (docs/mevzuat).
    expect(
      screen.getByText(/en geç 5 \(beş\) iş günü\s+içerisinde velisi tarafından okul müdürlüğüne/),
    ).toBeInTheDocument();
    expect(screen.getByText("arşivlenmiş oturumda da güncellenebilir")).toBeInTheDocument();
    // Yoklama fotoğraflı plan üzerinde alınır (19.09.2026) — eski liste düğmesi yok.
    expect(screen.queryByText(/“Girmedi işaretle”/)).not.toBeInTheDocument();
  });

  it("mazeret takibini, bir defaya mahsus kuralını ve raporu anlatır (19.09.2026)", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { level: 3, name: "Mazeret takibi ve mazeret sınavı" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Mazeret Takibi" })).toHaveAttribute(
      "href",
      "/mazeret",
    );
    // Alıntılar depodaki OKY md. 48/1 ve Yönerge md. 5/1-z metniyle birebirdir.
    expect(
      screen.getByText(/önceden\s+duyurularak bir defaya mahsus yapılır\./),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/resmî yazı ile\s+il\/ilçe millî eğitim müdürlüklerine bildirilir\./),
    ).toBeInTheDocument();
    expect(screen.getByText("yalnız Mazeretli öğrenciler")).toBeInTheDocument();
  });

  it("mazeret sınav takvimini ve ilan nüshasının adsız olduğunu anlatır (20.09.2026)", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { level: 3, name: "Mazeret sınav takvimi" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Mazeret Takvimi" })).toHaveAttribute(
      "href",
      "/mazeret?tab=takvim",
    );
    expect(screen.getByText("yalnız mazeret sınavları")).toBeInTheDocument();
    expect(screen.getByText("bir günde en çok kaç sınava gireceğini")).toBeInTheDocument();
    expect(screen.getByText(/öğrenci adı ya da numarası taşımaz/)).toBeInTheDocument();
  });

  it("öğrenci fotoğraflarını ve fotoğraflı oturma planını anlatır (19.09.2026)", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { level: 3, name: "Öğrenci fotoğrafları (isteğe bağlı)" }),
    ).toBeInTheDocument();
    // e-Okul raporu kodu, biçimi ve düzey başına ayrı dosya.
    // e-Okul yolu ekrandaki adlarla birebir: modül → Raporlar → rapor kodu ve adı.
    expect(screen.getAllByText("Öğrenci İşlemleri → Raporlar").length).toBeGreaterThan(0);
    expect(screen.getByText("OOG01001R080 - Fotoğraflı Öğrenci Listesi")).toBeInTheDocument();
    expect(screen.getByText("sınıf düzeyi başına")).toBeInTheDocument();
    // Mükerrer yüklemede seçim kullanıcıdadır; KVKK silme düğmesi anlatılır.
    expect(screen.getByText("Mevcut fotoğrafları koru")).toBeInTheDocument();
    expect(screen.getByText("Yenileriyle değiştir")).toBeInTheDocument();
    expect(screen.getByText("“Tüm fotoğrafları sil”")).toBeInTheDocument();
    for (const link of screen.getAllByRole("link", { name: "Kişiler" })) {
      expect(link).toHaveAttribute("href", "/kisiler");
    }
    // Salon evrakı: 1. yaprak fotoğraflı plan + yoklama; eski "yoklama ve imza
    // listesi (2. yaprak)" anlatımı yanlış bilgi olurdu.
    expect(
      screen.getByText(/fotoğraflı oturma planıdır ve yoklama da onun üstünde/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/yoklama ve imza listesi/)).not.toBeInTheDocument();
  });

  it("Ayarlar → Şubeler sekmesini ve süreç takip kalemlerini anlatır", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { level: 3, name: "Şube kataloğu: Ayarlar → Şubeler" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ayarlar → Şubeler" })).toHaveAttribute(
      "href",
      "/ayarlar?tab=subeler",
    );
    expect(
      screen.getByRole("heading", {
        level: 3,
        name: "Süreç Takip: işleri izleme ve kalemleri düzenleme",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("“Kalem yönetimi”")).toBeInTheDocument();
  });

  it("yedek alma ve yedekten geri yükleme akışını anlatır", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { level: 3, name: "Yedek alma ve yedekten dönme" }),
    ).toBeInTheDocument();
    // Günlük yedek HER açılışta değil, her gün İLK açılışta alınır (desktop/backup.py).
    expect(screen.getByText("her gün ilk açılışta")).toBeInTheDocument();
    expect(screen.queryByText(/her açılışta kendiliğinden bir/)).not.toBeInTheDocument();
    expect(screen.getByText(/Günlük yedekler de aynı bilgisayarda tutulur/)).toBeInTheDocument();
    expect(screen.getByText(/“Yedekten geri yükle”/)).toBeInTheDocument();
    expect(screen.getByText(/kapatılıp yeniden açılmalıdır/)).toBeInTheDocument();
    expect(screen.getByText(/“Yedekten Geri Yükle”/)).toBeInTheDocument();
    // Pardus/Linux kurtarma komutu (docs/kurulum.md §5.1 ile aynı).
    expect(screen.getByText("kelebek-sinav --geri-yukle")).toBeInTheDocument();
  });

  it("parola, kilit ekranı, kurtarma anahtarı ve güncellemeyi anlatır", () => {
    renderPage();
    expect(
      screen.getByRole("heading", {
        level: 3,
        name: "Uygulama parolası, kilit ekranı ve kurtarma anahtarı",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("“Parolamı unuttum”")).toBeInTheDocument();
    expect(screen.getByText("yalnız bir kez")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 3, name: "Programı güncelleme" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ayarlar → Güncelleme" })).toHaveAttribute(
      "href",
      "/ayarlar?tab=guncelleme",
    );
    expect(screen.getByText("tek isteği budur")).toBeInTheDocument();
  });

  it("sözlük: personel/derslik kümesi/ızgara/seviye sözcükleri kılavuzda geçmez", () => {
    const { container } = renderPage();
    const metin = container.textContent ?? "";
    // "Personel" yalnız e-Okul raporunun adında kalır ("Personel Listesi raporu").
    expect(metin.replace(/Personel Listesi raporu/g, "")).not.toMatch(/personel/i);
    expect(metin).not.toMatch(/derslik kümesi|derslik kümeleri/i);
    expect(metin).not.toMatch(/ızgara/i);
    expect(metin).not.toMatch(/seviye/i);
  });

  it("Bakanlık/MEM sınavlarının takvimde ayrı göründüğünü söyler", () => {
    renderPage();
    expect(screen.getByText(/BAK \/ İL \/ İLÇE/)).toBeInTheDocument();
    expect(screen.getByText(/mazeret sınavlarının bu takvimi izleyen hafta/)).toBeInTheDocument();
  });
});
