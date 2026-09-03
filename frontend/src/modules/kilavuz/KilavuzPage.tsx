// Kullanım Kılavuzu — programın adım adım anlatımı (statik içerik, çevrimdışı).
// Kalıp HakkindaPage'den: max-w-4xl kap, üstbaşlık üçlüsü, bölüm başına Card +
// 44px ikon rozeti. Ekranlara `Link` ile atlanır (ham <a href> YOK).
//
// Mevzuat atıfları DEPODAKİ tam metinlerden alınmıştır
// (docs/mevzuat/meb-olcme-ve-degerlendirme-yonetmeligi.md ve
// docs/mevzuat/meb-yazili-ve-uygulamali-sinavlar-yonergesi.md). Madde numarası
// UYDURULMAZ: evrak şablonlarındaki kural burada da geçerli — numara kayarsa
// metin yanlışlar, bu yüzden yalnız kanıtlı maddeler anılır ve bent harfi
// verilmez.

import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import Card from "../../ui/Card";
import Icon from "../../ui/Icon";

/** Kılavuz bölümü — numaralı adım kartı (ikon rozeti + başlık + içerik). */
function Adim({
  no,
  icon,
  title,
  children,
}: {
  no: number;
  icon: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <Card className="p-5 sm:p-6">
      <div className="flex items-start gap-4">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-shape-md bg-primary-container text-on-primary-container">
          <Icon name={icon} size="xl" />
        </span>
        <div className="min-w-0">
          <p className="text-label-medium font-semibold tracking-wide text-primary">{no}. ADIM</p>
          <h2 className="mt-0.5 text-title-large font-semibold text-on-surface">{title}</h2>
          <div className="mt-3 space-y-3 text-body-medium text-on-surface-variant">{children}</div>
        </div>
      </div>
    </Card>
  );
}

/** Vurgulu ipucu kutusu (tertiary yüzey — gövde metninden ayrışır). */
function Ipucu({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-shape-md bg-tertiary-container px-4 py-3 text-body-medium text-on-tertiary-container">
      {children}
    </div>
  );
}

/** Mevzuat alıntısı — kaynak adı + madde; bent harfi verilmez. */
function Mevzuat({ kaynak, children }: { kaynak: string; children: ReactNode }) {
  return (
    <div className="rounded-shape-md border-l-4 border-outline bg-surface-container px-4 py-3">
      <p className="text-body-medium text-on-surface">{children}</p>
      <p className="mt-1 text-body-small text-on-surface-variant">{kaynak}</p>
    </div>
  );
}

/** Ekran bağlantısı — kılavuzdan doğrudan ilgili sayfaya atlar. */
function Ekran({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
    >
      {children}
    </Link>
  );
}

export default function KilavuzPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <header>
        <p className="text-label-medium font-semibold tracking-wide text-primary">Kelebek Sınav</p>
        <h1 className="mt-1 text-headline-medium font-semibold tracking-tight text-on-surface">
          Kullanım Kılavuzu
        </h1>
        <p className="mt-2 text-body-medium text-on-surface-variant">
          Programı ilk kez kuran bir okul için baştan sona sıra. Adımları yukarıdan aşağı izleyin;
          her adım bir sonrakinin verisini hazırlar. Program çevrimdışı çalışır, veriler yalnız bu
          bilgisayarda durur.
        </p>
      </header>

      <Adim no={1} icon="rocket_launch" title="Kurulum ve okul künyesi">
        <p>
          Program ilk açıldığında kurulum sihirbazı çalışır: okul adı, il, ilçe, okul müdürünün adı
          ve okul türü sorulur. Bu bilgiler <strong>bütün resmî evrakın antedinde</strong>{" "}
          kullanılır — sınav takvimi, salon evrakı, görevlendirme yazısı hepsi buradan beslenir.
        </p>
        <p>
          Sonradan değiştirmek için <Ekran to="/ayarlar?tab=okul">Ayarlar → Okul Bilgileri</Ekran>.
          Okul türü iki şeyi birden belirler: programın tanıyacağı sınıf düzeylerini (9-12,
          hazırlık) ve <strong>hangi MEB haftalık ders çizelgesinin</strong> uygulanacağını. Sekiz
          ortaöğretim türü tanınır — Anadolu, Fen, Sosyal Bilimler, Anadolu İmam Hatip, Mesleki ve
          Teknik Anadolu, Çok Programlı Anadolu, Güzel Sanatlar ve Spor Lisesi; çizelge verisi henüz
          gelmemiş türler listede işaretli görünür ve o okulda ders havuzu boş başlar. Hazırlık
          sınıfı varsa burada işaretleyin — hazırlıksız okulda program hiç 0. seviye satırı üretmez.
        </p>
        <p>
          Okul türünün altındaki <strong>çizelge ataması</strong> kartı, hangi seviyede hangi Talim
          ve Terbiye Kurulu çizelgesinin yürürlükte olduğunu kararın tarih ve sayısıyla gösterir.
          Bütün seviyeler aynı çizelgeyle okuyorsa dokunmanız gerekmez.{" "}
          <strong>“Seviye bazında özelleştir”</strong> iki durum içindir: <em>kademeli dönüşüm</em>{" "}
          — Anadolu Lisesi'nden Fen Lisesi'ne dönen okulda yeni tür 9. sınıftan başlar, üst sınıflar
          eski çizelgede kalır — ve <em>çok programlı okul</em>: aynı seviyeye birden çok çizelge
          işaretlenir. Kademeli bir çizelgede kapsanmayan seviye kalırsa program onu en yeni
          programa düşürür ve kartta uyarı gösterir; sessizce geçmez.
        </p>
        <p>
          Verilerinizi korumak için <Ekran to="/ayarlar?tab=guvenlik">Ayarlar → Güvenlik</Ekran>{" "}
          bölümünden uygulama parolası kurabilirsiniz. Parola kurulunca öğrenci ve personel adları
          diskte şifreli tutulur; kurtarma anahtarını mutlaka güvenli bir yere not edin.
        </p>
      </Adim>

      <Adim no={2} icon="calendar_month" title="Ders yılı ve dönemler">
        <p>
          <Ekran to="/ayarlar?tab=ders-yillari">Ayarlar → Ders Yılları</Ekran> ekranında içinde
          bulunduğunuz ders yılını açın ve <strong>aktif</strong> yapın, ardından 1. ve 2. dönem
          tarihlerini girin. Sınav takvimi pencereleri, oturumlar ve evrak hep aktif ders yılına
          bağlanır.
        </p>
        <p>
          Ders saatleri sınav takviminin satırlarını oluşturur.{" "}
          <Ekran to="/ayarlar?tab=okul">Ayarlar → Okul Bilgileri</Ekran> ekranında iki şeyi
          belirtirsiniz: <strong>günlük ders saati sayısı</strong> (genel liselerde 8; mesleki ve
          teknik programlarda atölye günleriyle değişir) ve{" "}
          <strong>sınav yapılabilecek ders saatleri</strong>. İkincisini işaretlerseniz otomatik
          yerleştirme sınavları yalnız o saatlere koyar; boş bırakırsanız bütün saatler sınava
          açıktır. Elle yerleştirmede bu seçim engel değildir, yalnız hatırlatma çıkar — sınav
          saatini okul müdürlüğü belirler.
        </p>
        <p>
          Saat bilgisi (08.30'dan başlayarak ellişer dakika) varsayılan bir zil çizelgesinden gelir;
          okulunuzun zil düzeni farklıysa takvimdeki ders saati <em>numaraları</em> yine doğrudur.
        </p>
      </Adim>

      <Adim no={3} icon="group" title="Kişiler: öğrenci ve personel listeleri">
        <p>
          <Ekran to="/kisiler">Kişiler</Ekran> ekranından öğrenci ve personel listelerini içe
          aktarın. En hızlı yol e-Okul'dan indirdiğiniz raporu doğrudan yüklemektir; program hazır
          şablon indirmenize ya da listeyi panodan yapıştırmanıza da izin verir.
        </p>
        <p>
          İçe aktarma iki aşamalıdır: <strong>önizleme hiçbir şey yazmaz</strong>, ne olacağını
          gösterir; onaylayınca kayıt işlenir. Aktarım sonrası şubeler kataloğa kendiliğinden düşer.
        </p>
        <Ipucu>
          Personel listesi iki yerde işinize yarar: gözetmen görevlendirmesinde aday havuzu ve zümre
          başkanı seçiminde seçenek listesi buradan gelir. Bu yüzden personeli zümrelerden önce
          girin.
        </Ipucu>
      </Adim>

      <Adim no={4} icon="menu_book" title="Ders havuzu: tür ve sınav biçimi">
        <p>
          <Ekran to="/dersler">Ders Havuzu</Ekran>, okulun <strong>yürürlükteki</strong> haftalık
          ders çizelgesinden kendiliğinden türetilir: okul türü, hazırlık sınıfı, aktif ders yılı ve
          1. adımdaki seviye ataması birlikte hangi Talim ve Terbiye Kurulu çizelgesinin geçerli
          olduğunu söyler. Sınav takvimi ve sınav oturumları dersleri bu havuzdan seçer. Ders{" "}
          <strong>silinmez</strong>, pasifleştirilir — geçmiş evrak bozulmasın diye.
        </p>
        <p>
          Listenin üstündeki <strong>“Yürürlükteki çizelge”</strong> kartı hangi programın hangi
          seviyede uygulandığını, dayanağını (kararın tarihi ve sayısı) ve varsa uyarıları gösterir.
          Okul türünü, hazırlık seçimini ya da ders yılını değiştirdiğinizde havuz kendiliğinden
          yenilenir; <strong>“Çizelgeyi yeniden uygula”</strong> düğmesi bunu elle tetikler ve kaç
          dersin eklendiğini, güncellendiğini ve çizelge dışı kaldığını söyler.
        </p>
        <p>
          Çizelge değişince havuzda kalan eski dersler <strong>“Çizelge dışı”</strong> rozetiyle
          pasifleşir; o ders çizelgeye geri girerse kendiliğinden yeniden açılır. Sizin{" "}
          <strong>“Pasifleştir”</strong> dediğiniz ders ise asla kendiliğinden açılmaz — aktiflik
          idari bir karardır, program ona dokunmaz.
        </p>
        <p>
          Listenin iki sütunu takvim havuzunun nasıl dolacağını belirler. <strong>Tür</strong>{" "}
          dersin <em>ortak (zorunlu)</em> mu yoksa <em>seçmeli</em> mi olduğunu,{" "}
          <strong>Sınav</strong> ise dersin sınavının <em>Yazılı</em> mı, <em>Uygulama</em> mı
          olduğunu ya da o dersin hiç sınavı olmadığını (<em>Sınav yok</em>) söyler. MEB
          çizelgesinden gelen dersler için bu alanlar hazır doldurulmuştur: Beden Eğitimi ve Spor,
          Görsel Sanatlar/Müzik, Spor ve Sanat Eğitimi <em>Uygulama</em>, Rehberlik ve Yönlendirme{" "}
          <em>Sınav yok</em> gelir. Okulunuzun uygulaması farklıysa satırdaki{" "}
          <strong>Düzenle</strong> düğmesiyle dersin adını, seviyelerini, türünü ve sınav biçimini
          değiştirebilirsiniz.
        </p>
        <p>
          <strong>Ancak çizelgeden gelen bir derste bu düzenleme kalıcı değildir.</strong> Ad,
          seviye, tür ve sınav biçimi <em>çizelge verisidir</em>: çizelge yeniden uygulandığında
          (okul türü, hazırlık ya da ders yılı değişikliği; program güncellemesiyle gelen yeni
          çizelge) MEB değerine döner. Kalıcı olarak farklı kalması gereken bir ders için çizelge
          dersini <strong>pasifleştirip</strong> yanına <em>farklı adla</em> elle bir ders ekleyin —
          elle eklenen derse senkron dokunmaz. Buna karşılık{" "}
          <strong>pasifleştirme her zaman kalıcıdır</strong>.
        </p>
        <p>
          Seçmeli derslerde <strong>“Şubeler”</strong> sütununa basıp o dersi hangi şubelerin
          aldığını işaretleyin — sınav takvimi havuzu bu bilgiyle kendiliğinden dolar ve her
          takvimde yeniden şube seçmezsiniz. Şubeleri girilmemiş yazılı seçmeli, sütunda uyarı
          işaretiyle görünür. Bu tanım ders yılına özeldir: yeni ders yılında yeniden girilir
          (şubeler her yıl yeniden kurulduğu için eski seçim taşınmaz).
        </p>
        <Ipucu>
          <strong>Önce havuzu okulunuza göre sadeleştirin.</strong> Okulunuzda okutulmayan dersleri
          havuzda <strong>pasif</strong> yapın (satırın sağındaki “Pasifleştir”); pasif ders takvim
          havuzuna kendiliğinden eklenmez, elle de seçilemez. Uygulama sınavı yapılan ve sınavı
          olmayan dersleri pasifleştirmenize <strong>gerek yoktur</strong> — “Sınav” alanları doğru
          olduğu sürece takvim havuzuna kendiliğinden girmezler. Bu iki alan doğruysa{" "}
          <strong>ders eşleştirmesi ilk seferde doğru olur</strong> ve takvim havuzunda tek tek
          silmeniz gereken satır kalmaz.
        </Ipucu>
        <p>
          Listede olmayan bir ders varsa elle ekleyin. Aynı dersin iki farklı yazımı (örneğin “Din
          Kül. ve Ah. Bil.” ile tam adı) havuza düşmüşse program bunları mükerrer olarak işaretler;
          birleştirdiğinizde eski yazım takma ad olarak kaydedilir ve bir daha yeni kayıt üretmez.
        </p>
      </Adim>

      <Adim no={5} icon="groups" title="Zümreler ve zümre başkanları kurulu">
        <p>
          <Ekran to="/ayarlar?tab=zumreler">Ayarlar → Zümreler</Ekran> ekranında okul zümre
          başkanları kurulunu oluşturan zümreleri girin (örneğin “Sosyal Bilimler”, “Matematik”,
          “Yabancı Dil”) ve her zümrenin başkanını personel listesinden seçin.
        </p>
        <p>
          Bu liste sınav takvimi PDF'inin <strong>imza bölümünü</strong> besler: takvimi hazırlarken
          hangi zümrelerin imzalayacağını seçersiniz, program da başkanların adlarını basar. Zümre
          tanımlamazsanız program eski davranışına döner ve takvimdeki her ders için boş bir imza
          çizgisi üretir.
        </p>
        <Mevzuat kaynak="MEB Yazılı ve Uygulamalı Sınavlar Yönergesi md. 4 ve md. 5">
          Eğitim kurumu sınıf/alan zümresi, aynı sınıfı okutan veya alanı aynı olan öğretmenlerden
          oluşur. Okul geneli ortak yazılı sınavların soruları ve cevap anahtarları bu zümrelerce
          hazırlanır; sınavın uygulanması ve değerlendirilmesi de zümrelerce yapılır.
        </Mevzuat>
      </Adim>

      <Adim no={6} icon="meeting_room" title="Salonlar ve oturma düzeni">
        <p>
          <Ekran to="/salonlar">Salonlar</Ekran> ekranında sınav yapılacak derslikleri tanımlayın:
          sıra düzenini 2B editörde çizin, tek/çift kişilik sıraları ve numaralandırma yönünü seçin.
          Bir dersliği bir şubeye bağlarsanız “kendi sınıfında” yapılacak sınavlarda program o
          salonu kullanır.
        </p>
        <p>
          Planın en üstündeki şerit salonun <strong>ön cephesidir</strong> — öğretmen masası, tahta
          ve kapı oraya konur. Bu şerit <strong>satır sayımına girmez</strong>: “Sıra satırı” ve
          “Sıra sütunu” alanları yalnız öğrenci sıralarını sayar.
        </p>
        <p>
          Yeni salon boş ızgarayla değil <strong>varsayılan şablonla</strong> açılır: öğretmen
          masası ön-solda, kapı çizilmemiş, bütün hücreler ikili sıra — dört sütun ve beş sırayla
          kırk koltuk. Koltuk numaraları <strong>öğretmen masasının önünden</strong> başlar; masayı
          başka bir köşeye taşırsanız numaralandırma da onunla döner. Kapı yalnız krokiye çizilir,
          numaralandırmaya girmez — varsayılanda hiç yoktur, çünkü yeri okuldan okula değişir ve
          uydurulmuş bir kapı resmî salon evrakına yanlış bilgi basmak olurdu. Editördeki{" "}
          <strong>“Varsayılan şablon”</strong> düğmesi aynı düzeni açık salona uygular ve bunu{" "}
          <strong>salonun kendi satır/sütun ölçüsünde</strong> yapar, 4×5'e zorlamaz; kaydetmezseniz
          kalıcı olmaz.
        </p>
        <p>
          Program daha önce kurulmuşsa ve onlarca derslik eski düzende kaldıysa Salonlar
          sayfasındaki <strong>“Şablonu topluca uygula”</strong> düğmesini kullanın. Diyalog eski
          düzendeki salonları işaretli açar, her salonu kendi ölçüsünde şablona çeker ve kapasiteyi
          korur. <strong>Yerleşimi yapılmış salonlar atlanır</strong> ve adlarıyla bildirilir:
          basılmış evraktaki koltuk numarası planla çelişmesin diye. Onları editörden tek tek
          değiştirebilirsiniz.
        </p>
        <p>
          Salon planı bir kez çizilir, her sınavda yeniden kullanılır. Boş yerleşim planını PDF
          olarak alıp kapıya asabilirsiniz.
        </p>
        <Ipucu>
          <strong>İkili eğitim yapıyorsanız derslikleri kümeleyin.</strong> “Şube dersliklerini
          oluştur” her şube için bir derslik üretir; ikili eğitimde liste kalabalıklaşır ve
          sihirbazda tek tek işaretlemek zorlaşır. Salonlar ekranındaki <strong>Kümeler</strong>{" "}
          düğmesiyle “Sabah”, “Öğle” gibi kümeler tanımlayıp salonları topluca atayın — sınav
          sihirbazında kümenin tamamı tek tıkla seçilir. Küme yalnız seçim kolaylığıdır; evrağa
          basılan konum bilgisi salonun “blok/kat” alanıdır.
        </Ipucu>
      </Adim>

      <Adim no={7} icon="event_note" title="Sınav takvimi">
        <p>
          <Ekran to="/takvimler">Takvimler</Ekran> ekranı dönem ve tur bazlı çalışır. “Ön tanımlı
          takvimleri üret” dediğinizde program, mevzuattaki dört sınav penceresine karşılık dört
          takvim açar (1. Dönem 1. ve 2. Sınav, 2. Dönem 1. ve 2. Sınav) ve havuzlarını doldurur.
          Haftalık ders saati altı ve üzeri derslerde il zümre kararıyla yapılabilen 3. sınav için
          takvimi elle açar, havuzunu da elle doldurursunuz.
        </p>
        <Mevzuat kaynak="MEB Ölçme ve Değerlendirme Yönetmeliği md. 5">
          Okullarda sınavlar; 1. dönem 1. sınavlar Ekim ayı son haftası–Kasım ayı ilk haftası, 1.
          dönem 2. sınavlar Aralık ayı son haftası–Ocak ayı ilk haftası, 2. dönem 1. sınavlar Mart
          ayı son haftası–Nisan ayı ilk haftası, 2. dönem 2. sınavlar Mayıs ayı son haftası–Haziran
          ayı ilk haftası aralığında yapılır.
        </Mevzuat>
        <p>
          Takvimin dört sekmesi vardır: <strong>Havuz</strong> (hangi ders hangi seviyede sınav
          olacak), <strong>Yerleştirme</strong> (hangi gün, hangi ders saati),{" "}
          <strong>Süreç Takip</strong> (soru teslimi, basım, puan girişi gibi kalemler) ve{" "}
          <strong>Önizleme</strong> (açıklamalar, dipnot, imza zümreleri ve PDF).
        </p>
        <p>
          Takvim <strong>Taslak → Onaya Sunuldu → Onaylandı</strong> sırasıyla ilerler. Havuz,
          yerleştirme, açıklama, dipnot ve imza zümreleri yalnız taslak durumda değişir; onaylı
          takvimi düzenlemek için önce “Taslağa Al” deyin. Taslak ve onaya sunulmuş takvimlerin
          PDF'inde “TASLAK” filigranı bulunur.
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Havuzu doldurmak: zorunlu dersler ve seçmeliler
        </h3>
        <p>
          Havuz sekmesinde iki düğme vardır. <strong>“Dersleri ekle”</strong>, ders havuzundaki{" "}
          <em>ortak</em> ve sınavı <em>Yazılı</em> dersleri — ve{" "}
          <strong>şubelerini girdiğiniz</strong> seçmelileri — öğrencisi olan her seviye için tek
          tıkla havuza koyar; uygulama sınavı yapılan ve sınavı olmayan dersler eklenmez. Şubesi
          henüz girilmemiş seçmeli atlanır ve size bildirilir. <strong>“Seçmeli ders seç”</strong>{" "}
          ise seviye sekmeleri açar: kalan seçmelileri elle işaretlersiniz. Havuzda zaten bulunan
          ders işaretli ve kilitli görünür, ikinci kez eklenmez.
        </p>
        <Ipucu>
          Bir seçmeliyi <strong>hangi şubelerin aldığını</strong> her takvimde yeniden seçmeyin:
          bunu bir kez <Ekran to="/dersler">Ders havuzu</Ekran> ekranında, dersin{" "}
          <strong>“Şubeler”</strong> sütunundan girin. Dört sınav takvimi de o bilgiyi kullanır,
          havuz kendiliğinden dolar.
        </Ipucu>
        <p>
          Seçmeli seçim penceresinde şube kutuları ders havuzundaki tanımdan <strong>dolu</strong>{" "}
          gelir; dilerseniz o takvime mahsus değiştirebilirsiniz. Kapsam iki türlüdür:{" "}
          <em>Seviye geneli</em> ya da <em>Şube seç</em>. Şube seçerken Ayarlar’daki{" "}
          <strong>şube kümelerini</strong> (SAY, EA, DİL gibi — 8. adımda anlatılır) çipe basarak
          topluca ekleyebilirsiniz. Küme yalnız seçim kolaylığıdır — takvime kümenin adı değil,
          seçilen şubeler yazılır.
        </p>
        <p>
          Kapsamı yanlış verdiyseniz girdiyi silmeniz gerekmez: havuz tablosunda{" "}
          <strong>“Kapsam”</strong> sütunundaki değere basınca kapsam düzenleme penceresi açılır.
          Takvim taslak olduğu sürece ızgaraya yerleştirilmiş girdinin kapsamı da buradan
          düzeltilir. Bir girdinin kapsamı ders havuzundaki tanımdan farklıysa yanında{" "}
          <strong>“özel”</strong> rozeti görünür — o sınava mahsus istisna yaptığınızı hatırlatır.
        </p>
        <Ipucu>
          Yeni bir takvim açtığınızda zorunlu dersler <strong>kendiliğinden</strong> havuza gelir
          (1. ve 2. sınav takvimlerinde). Geriye yalnız seçmelileri işaretlemek ve gerekiyorsa kenar
          durumları — kendi sınıfında yapılacak sınavlar, uygulama sınavları, Bakanlık/MEM sınavları
          — havuz formundan elle eklemek kalır.
        </Ipucu>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Takvimi otomatik kurma ve sınavları sabitleme
        </h3>
        <p>
          Havuzu doldurduktan sonra sınavları tek tek yerleştirmek zorunda değilsiniz. Yerleştirme
          sekmesindeki <strong>“Otomatik yerleştir”</strong> düğmesi havuzda bekleyen sınavları
          hafta içi günlere ve okulunuzun sınav saatlerine dağıtır. İki kipte çalışır:
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>Boşları doldur:</strong> yalnız havuzda bekleyenleri yerleştirir, ızgaradaki
            sınavlara hiç dokunmaz.
          </li>
          <li>
            <strong>Sabitler hariç yeniden dağıt:</strong> kilitlemediğiniz sınavları havuza alıp
            baştan dağıtır. Sonucu beğenmezseniz tekrar çalıştırabilirsiniz.
          </li>
        </ul>
        <p>
          Elle yerleştirdiğiniz her sınav <strong>kendiliğinden sabitlenir</strong>: ızgaradaki
          çipin üzerinde kilit simgesi görünür ve otomatik dağıtım onu yerinden oynatmaz. Kilide
          tıklayarak sabitlemeyi kaldırabilir, otomatik yerleşmiş bir sınavı da kilitleyebilirsiniz.
          Bir sınavı havuza geri alırsanız sabitlemesi düşer.
        </p>
        <p>Program dağıtırken şu kurallara uyar:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>Aynı öğrenciye günde ikiden fazla sınav düşürmez.</li>
          <li>Kapsamı kesişen iki sınavı aynı saate koymaz.</li>
          <li>Üst makam sınavı olan güne o seviyenin okul sınavını yazmaz.</li>
          <li>Hafta sonlarını ve sınav saati işaretlemediğiniz ders saatlerini kullanmaz.</li>
          <li>
            Bakanlık/İl MEM/İlçe MEM sınavlarını <strong>hiç yerleştirmez</strong> — tarihleri
            ilgili makamın kılavuzundadır, onları siz koyarsınız.
          </li>
        </ul>
        <p>
          İşlem bitince bir rapor açılır: kaç sınav yerleştirildi, hangileri yerleştirilemedi ve
          neden. Yerleştirilemeyen sınav kalırsa takvim aralığını genişletin, sınav saati ekleyin ya
          da o sınavı elle koyun.
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Aynı saate iki sınav: kapsam kuralı
        </h3>
        <p>
          Bir öğrenci aynı anda iki salonda olamaz. Bu yüzden program, aynı gün ve ders saatine{" "}
          <strong>kapsamları kesişen</strong> iki sınav koymanızı kabul etmez. Kapsamlar
          kesişmiyorsa — örneğin 9/A'nın Almanca, 9/B'nin Fransızca sınavı — aynı saatte yan yana
          yapılabilir. Seviye geneli bir sınav o seviyedeki her şubeyle kesişir.
        </p>
        <p>
          Bu, günlük sınav sayısı hesabını <em>gevşetmez</em>: bir şubenin seçmeli dersi aldığını
          bilmek, o şubedeki her öğrencinin aldığını göstermez. Günlük yük sayımı ihtiyatlı kalır.
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">Salon kapasitesi</h3>
        <p>
          Aynı saatte sınava girecek öğrenci sayısı aktif salonlarınızın toplam kapasitesini aşarsa
          program uyarır (engellemez). Otomatik yerleştirme de böyle saatlerden kaçınmaya çalışır.
          Salon tanımlamadıysanız bu denetim çalışmaz.
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Günlük sınav sayısı sınırı
        </h3>
        <p>
          Yerleştirme sırasında program günlük sınav yükünü sizin yerinize sayar ve mevzuattaki
          esası hatırlatır:
        </p>
        <Mevzuat kaynak="MEB Ölçme ve Değerlendirme Yönetmeliği md. 5">
          Bir sınıfta bir günde yapılacak yazılı ve uygulamalı sınavların sayısının ikiyi geçmemesi
          esastır. Ancak zorunlu hâllerde bir sınav daha yapılabilir.
        </Mevzuat>
        <Mevzuat kaynak="MEB Yazılı ve Uygulamalı Sınavlar Yönergesi md. 5">
          Ülke, il ve ilçe geneli ortak yazılı sınavların yapılacağı tarihlerde başka sınav
          yapılmaz. Bir günde yapılacak sınav sayısının ikiyi geçmemesi esastır. Ancak zorunlu
          hâllerde bir sınav daha yapılabilir. Zorunlu hâl kapsamına giren durumların belirlenmesi
          okul müdürlüklerinin sorumluluğundadır.
        </Mevzuat>
        <p>Program bu esası şöyle uygular:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>Aynı gün ve seviyede iki sınava kadar sessizce izin verir.</li>
          <li>
            <strong>Üçüncü sınavda uyarır</strong> ama engellemez — “zorunlu hâl” takdiri okul
            müdürlüğünündür.
          </li>
          <li>
            <strong>Dördüncü sınavı hiç kabul etmez</strong>; yerleştirme reddedilir.
          </li>
          <li>
            Sayım <strong>öğrenci bazlıdır</strong>: aynı gün aynı seviyeye konan derslerin kaç
            öğrenciyi birlikte etkilediğine bakılır.
          </li>
        </ul>
        <p>
          Ayrıca sınav süresiyle ilgili sınırı da unutmayın: ulusal/uluslararası izleme
          araştırmaları ile merkezî sınavlar dışında, zorunlu hâller hariç yazılı sınav süresi bir
          ders saatini aşamaz (Ölçme ve Değerlendirme Yönetmeliği md. 5).
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Bakanlık ve millî eğitim müdürlüğü sınavları
        </h3>
        <p>
          Her sınavı okul hazırlamaz. Havuza ders eklerken ya da havuz listesindeki{" "}
          <strong>“Hazırlayan”</strong> sütunundan sonradan seçerek sınavın <strong>Okul</strong>,{" "}
          <strong>Bakanlık</strong>, <strong>İl MEM</strong> veya <strong>İlçe MEM</strong> sınavı
          olduğunu işaretleyebilirsiniz.
        </p>
        <p>
          Okul dışı makam sınavları takvimde ayrı görünür: yerleştirme ızgarasında BAK / İL / İLÇE
          rozeti taşırlar, PDF'te ise gölgeli ve sol kenarı çizgili hücrede “BAKANLIK SINAVI”, “İL
          MEM SINAVI” veya “İLÇE MEM SINAVI” etiketiyle basılırlar. Aynı güne hem okul hem üst makam
          sınavı koyarsanız program uyarır.
        </p>
        <Mevzuat kaynak="MEB Yazılı ve Uygulamalı Sınavlar Yönergesi md. 5">
          Ülke geneli yapılacak ortak yazılı sınavlar Bakanlıkça, il geneli yapılacak ortak yazılı
          sınavlar ise il millî eğitim müdürlüğünce belirlenen tarih ve saatlerde yapılır.
        </Mevzuat>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Açıklamalar, dipnot ve imzalar
        </h3>
        <p>
          Önizleme sekmesinde takvimin altına basılacak <strong>açıklama maddelerini</strong> ve
          altındaki <strong>dipnotu</strong> düzenleyebilirsiniz. Dipnotun varsayılan metni,
          okulumuzda yapılan sınavların mazeret sınavlarının bu takvimi izleyen hafta içinde okul
          müdürlüğünce duyurulan tarihlerde; Bakanlık ya da İl/İlçe Millî Eğitim Müdürlüğü
          sınavlarının ise ilgili kılavuzda ilan edilen tarih ve saatlerde yapılacağını söyler.
          Okulunuzun uygulaması farklıysa metni değiştirip kaydedin; “Varsayılan dipnota dön”
          düğmesi her zaman ilk metni geri getirir.
        </p>
        <p>
          Aynı sekmede, imza bölümünde yer alacak zümreleri işaretlersiniz (5. adımda tanımladığınız
          liste). Seçtiğiniz her zümre için başkanının adıyla bir imza yeri, en altta da okul zümre
          başkanı ve okul müdürü için birer imza yeri basılır.
        </p>
        <Mevzuat kaynak="MEB Yazılı ve Uygulamalı Sınavlar Yönergesi md. 5">
          Ortak sınavlara mazeretleri nedeniyle katılamayan öğrenciler için mazeret sınavı yapılır.
          Geçerli mazereti bulunan öğrencilerin sınava katılmama gerekçesi, sınav tarihinden
          itibaren en geç beş iş günü içinde velisi tarafından okul müdürlüğüne yazılı olarak
          bildirilir. Okul geneli sınavların mazeret sınavlarına ilişkin iş ve işlemler okul
          müdürlüklerince yürütülür.
        </Mevzuat>
      </Adim>

      <Adim no={8} icon="event_seat" title="Sınav oturumları ve kelebek dağıtım">
        <p>
          Takvim onaylandıktan sonra her sınav slotu için <Ekran to="/oturumlar">Oturum</Ekran>{" "}
          üretebilirsiniz; sihirbazla elle de oturum açabilirsiniz. Oturumda dersleri, katılacak
          şubeleri ve kullanılacak salonları seçersiniz.
        </p>
        <p>
          Dağıtımı başlattığınızda program öğrencileri salonlara “kelebek” düzende yerleştirir: aynı
          dersi aynı seviyede alan öğrenciler yan yana ve ön arkaya düşmez. Sonuç bağımsız bir
          doğrulayıcıdan geçer; <strong>ihlal sıfır değilse onay verilmez</strong>. Aynı çekirdek
          sayı (seed) aynı dağıtımı üretir ve bu sayı doğrulama raporuna basılır.
        </p>
        <p>
          Öğrenci sayıları karışmaya elverişli değilse — örneğin salonda tek ders varsa — aynı
          sınava giren öğrencilerin yan yana düşmesi matematiksel olarak kaçınılmaz olabilir. Bu
          durumda program o çiftleri <strong>öğretmen masasına en yakın sıralara</strong> çeker;
          gözetim en zor olan yerler öğretmenin önünde kalır. Bu yalnız bir tercihtir: kaçınılmaz
          olmayan hiçbir komşuluğu yaratmaz ve ihlal sayısını artırmaz.
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Şube ve derslik kümeleriyle hızlı seçim
        </h3>
        <p>
          Sihirbazın katılımcı adımında{" "}
          <Ekran to="/ayarlar?tab=sube-kumeleri">Ayarlar → Şube Kümeleri</Ekran> ekranında
          tanımladığınız kümeler (Sayısal, Eşit Ağırlık, Dil…) çip olarak görünür; çipe basınca o
          kümenin şubeleri seçime eklenir. Küme seçili sınıf düzeyiyle kesiştirilir — bir oturum
          dersi tek seviyeye bağlıdır. Salon adımında da derslik kümeleri düğme olarak çıkar.
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Engelli ve özel durumlu öğrencilerin salonunu ve yerini sabitleme
        </h3>
        <p>
          Engel durumu, BEP ya da sağlık nedeniyle belirli bir yerde oturması gereken öğrencilerin{" "}
          <strong>salonu ve koltuğu</strong>, oturum detayındaki{" "}
          <strong>Yerleştirme Kuralları</strong> sekmesinden <strong>“Kural ekle”</strong> ile
          sabitlenir. Kural sahibi öğrenci kelebek motoru çalışmadan önce yerine oturtulur;{" "}
          <strong>motor onu taşıyamaz</strong>. Kalan öğrenciler artakalan koltuklara kelebek
          düzende dağıtılır.
        </p>
        <Mevzuat kaynak="MEB Yazılı ve Uygulamalı Sınavlar Yönergesi md. 5">
          Kaynaştırma/bütünleştirme yoluyla eğitim ve öğretimlerine devam eden öğrencilere yönelik
          ölçme ve değerlendirmede BEP esas alınır. Bu öğrencilerin ortak yazılı sınavlara
          katılımıyla ilgili süreçlerden okul müdürlükleri sorumludur.
        </Mevzuat>
        <p>
          Formda önce öğrenciyi (ad ya da okul numarasıyla aranır) ve gerekçe kategorisini
          seçersiniz. <strong>“Yerini ben seçeyim”</strong> kutusunu işaretlemezseniz öğrenci{" "}
          <strong>kendi dersliğinde, arka sırada ve tek başına</strong> oturur — en sık istenen
          bileşim budur, tek tıkla kurulur.
        </p>
        <p>Kutuyu işaretlerseniz yeri kendiniz belirlersiniz:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>Salon</strong> zorunludur — öğrencinin sınava gireceği dersliği seçersiniz.
          </li>
          <li>
            <strong>Koltuk</strong> isteğe bağlıdır: “salon içinde serbest” bırakabilir ya da
            listeden birebir bir koltuk seçebilirsiniz. Liste her koltuğu sıra satır-sütunu, sıra
            içi pozisyonu ve o plandaki koltuk numarasıyla birlikte gösterir.
          </li>
          <li>
            <strong>Salon içinde tercih</strong> koltuğu serbest bıraktığınızda devreye girer: ön
            sıra, arka sıra ya da fark etmez. Ön ve arka <em>öğretmen masasına</em> göre hesaplanır
            — masası çizilmemiş planda plandaki ilk sıra “ön” sayılır.
          </li>
          <li>
            <strong>“Tek başına otursun”</strong> sıradaki diğer koltukları kimseye vermez. Salon
            kapasitesi o kadar azalır (ikili sırada iki koltuk) ve dağıtım raporunda kaç koltuğun
            kapandığı uyarı olarak yazar; kalabalık oturumda ek salon gerekebilir.
          </li>
        </ul>
        <Ipucu>
          <strong>Kuralı dağıtımdan önce ekleyin.</strong> Kural yalnız dağıtım çalışırken
          uygulanır: oturumu dağıttıktan sonra kural eklerseniz “Yeniden Dağıt” demeniz gerekir ve
          bu, yeni bir çekirdek sayıyla bütün yerleşimi yeniler. Onaylanmış ya da arşivlenmiş
          oturuma kural eklenemez — önce onayı geri alın.
        </Ipucu>
        <p>Kural yazarken üç noktaya dikkat edin:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>“Kendi dersliğinde” için bağlı şube şarttır.</strong> Program öğrencinin
            şubesine <em>bağlı</em> bir derslik arar (Salonlar ekranındaki “bağlı şube” alanı);
            bulamazsa dağıtımı reddeder ve hangi şubenin dersliğinin eksik olduğunu söyler.
          </li>
          <li>
            <strong>Kuralda seçtiğiniz salonu oturumun salon listesine de ekleyin.</strong> Kural,
            oturumda seçili olmayan bir salonu da hedef alabilir; öğrenci oraya yerleşir ama o salon
            için salon sınav evrakı basılmaz — öğrenci hiçbir yoklama listesinde görünmez.
          </li>
          <li>
            <strong>Koltuk, numarasıyla değil koordinatıyla saklanır.</strong> Numaralandırma yönünü
            değiştirmek kuralı bozmaz; ama salon planını değiştirip o koltuğu kaldırırsanız kural
            “koltuk planda yok” hatası verir. Aynı koltuk iki kurala verilemez ve hedef salonda boş
            koltuk kalmazsa dağıtım durur.
          </li>
        </ul>
        <p>
          Kural <strong>eklendiği oturuma özgüdür</strong>: her sınav oturumunda yeniden tanımlanır
          ve bir öğrencinin aynı oturumda tek kuralı olur. Değiştirmek için kuralı kaldırıp yeniden
          ekleyin.
        </p>
        <p>
          Gerekçe olarak yalnız kategori seçilir (engel durumu, BEP, sağlık, diğer);{" "}
          <strong>tanı ya da rapor bilgisi hiç kaydedilmez</strong> — programda böyle bir alan
          bilinçli olarak yoktur. Kural basılı evraka da geçmez: oturma planında ve yoklama
          listesinde öğrenci diğerleri gibi görünür, dağıtım doğrulama raporunda ise yalnız{" "}
          <em>kaç</em> öğrencinin sabit kuralla yerleştiği sayı olarak yazar.
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Başka oturumdan kopyalama
        </h3>
        <p>
          Benzer bir oturum daha önce tanımlandıysa sihirbazın ders adımındaki{" "}
          <strong>“Başka oturumdan kopyala”</strong> düğmesiyle o oturumun derslerini, katılacak
          şubelerini ve kullanılacak dersliklerini bu taslağa aktarabilir, sonra üzerinde değişiklik
          yapabilirsiniz. Zaten ekli olanlar atlanır ve size listelenir. Sınav tarihi ve saati,
          dağıtım (seed), yerleşim, yoklama, gözetmen görevlendirmesi ve onay damgaları kopyalanmaz
          — bunlar her oturuma özgüdür.
        </p>
      </Adim>

      <Adim no={9} icon="description" title="Evrak, gözetmen ve yedekleme">
        <p>
          Oturum onaylanınca evrak paneli açılır. Salon sınav evrakı tek belgede birleşiktir: salon
          ve oturum bilgileri, oturma planı, gözetmen işlemleri, sınav evrakı sayımı ve teslim
          zinciri (1. yaprak) ile yoklama ve imza listesi (2. yaprak) — çift yüz basıldığında salon
          başına bir kâğıt. Ayrıca şube sınav duyurusu (kapıya asılan liste), gözetmen görevlendirme
          yazısı, dağıtım doğrulama raporu ve ihlal/kopya tutanağı üretilir. Hepsi PDF olarak
          indirilir ve doğrudan basılabilir.
        </p>
        <p>
          Gözetmenleri personel listesinden salonlara elle atarsınız. Muafiyet tanımladığınız
          öğretmenler aday listesinde görünmeye devam eder ama seçilemez; yanlarında nedeni yazar
          (“muaf” gibi) — böylece “neden seçemiyorum” sorusu ekranda yanıtlanır. Görevlendirme
          yazısı tebellüğ imzası için yer bırakır.
        </p>
        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Yedek alma ve yedekten dönme
        </h3>
        <p>
          Program her açılışta kendiliğinden bir <strong>günlük yedek</strong> alır. Bunun dışında{" "}
          <Ekran to="/ayarlar?tab=guvenlik">Ayarlar → Güvenlik</Ekran> bölümünden istediğiniz an
          elle yedek (<span className="font-mono">.ksbak</span>) alabilirsiniz.
        </p>
        <p>
          Yanlış ya da eksik veri girişinden sonra eski bir güne dönmek için aynı ekrandaki{" "}
          <strong>“Yedekten geri yükle”</strong> kartını kullanın: günlük yedeklerden birini seçin
          ya da elinizdeki .ksbak dosyasını yükleyin. Yedek şifreliyse uygulama parolası ya da
          kurtarma anahtarı istenir. Mevcut veritabanı <strong>silinmez</strong>; veri klasöründe{" "}
          <span className="font-mono">db-onceki-…</span> adıyla kenara alınır. Geri yükleme
          uygulandıktan sonra program <strong>kapatılıp yeniden açılmalıdır</strong> — atlanmasın
          diye ekran kapanmayan bir yönlendirmeye döner.
        </p>
        <p>
          Program hiç açılmıyorsa (bozuk veritabanı) bu ekrana ulaşamazsınız; o durumda Başlat
          menüsündeki <strong>“Yedekten Geri Yükle”</strong> kısayolunu kullanın.
        </p>
        <Ipucu>
          Sınav dönemi başlamadan bir yedek alıp <strong>okul dışında</strong> saklayın. Program
          çevrimdışıdır; veriler yalnız bu bilgisayarda durur, bir bulut kopyası yoktur. Günlük
          yedekler de aynı bilgisayarda tutulur — disk giderse onlar da gider.
        </Ipucu>
      </Adim>

      <Card className="p-5 sm:p-6">
        <div className="flex items-start gap-4">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-shape-md bg-secondary-container text-on-secondary-container">
            <Icon name="gavel" size="xl" />
          </span>
          <div>
            <h2 className="text-title-large font-semibold text-on-surface">Dayanak metinler</h2>
            <p className="mt-2 text-body-medium text-on-surface-variant">
              Bu kılavuzdaki alıntılar, programla birlikte gelen iki mevzuat metninden alınmıştır:
              <strong> Millî Eğitim Bakanlığı Ölçme ve Değerlendirme Yönetmeliği</strong> (Resmî
              Gazete 09.09.2023/32304) ve{" "}
              <strong>Millî Eğitim Bakanlığı Yazılı ve Uygulamalı Sınavlar Yönergesi</strong>{" "}
              (11.10.2023). Mevzuat değişebilir; resmî evrak hazırlarken yürürlükteki metni esas
              alın.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
