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
          Teknik Anadolu, Çok Programlı Anadolu, Güzel Sanatlar ve Spor Lisesi — ve sekizinin de
          çizelgesi programla birlikte gelir. Hazırlık sınıfı varsa burada işaretleyin — hazırlıksız
          okulda program hiç hazırlık satırı üretmez.
        </p>
        <p>
          <strong>Çizelgede eksik kalanlar sınırlıdır</strong> ve program bunları gizlemez. Mesleki
          ve Teknik Anadolu Lisesinde yalnız zorunlu dersler gelir: alan/dal meslek derslerini ve
          seçmeli dersleri Ders Havuzu ekranından elle eklersiniz (4. adım); hazırlık sınıfı bulunan
          mesleki ve teknik çizelge de henüz yoktur. Güzel Sanatlar Liselerinde 2026-2027 ders
          yılında 12. sınıfın tabi olduğu önceki çizelge bulunmaz; program o sınıf düzeyinde en yeni
          çizelgeyi kullanır ve bunu ders havuzunda uyarıyla bildirir. Spor Lisesinde bu boşluk
          yoktur: 2026-2027 ders yılından itibaren yeni çizelge bütün sınıf düzeylerinde uygulanır.
        </p>
        <p>
          Okul türünün altındaki <strong>çizelge ataması</strong> kartı, hangi sınıf düzeyinde hangi
          Talim ve Terbiye Kurulu çizelgesinin yürürlükte olduğunu kararın tarih ve sayısıyla
          gösterir. Bütün sınıf düzeyleri aynı çizelgeyle okuyorsa dokunmanız gerekmez.{" "}
          <strong>“Sınıf düzeyine göre özelleştir”</strong> üç durum içindir:{" "}
          <em>kademeli dönüşüm</em> — Anadolu Lisesi'nden Fen Lisesi'ne dönen okulda yeni tür 9.
          sınıftan başlar, üst sınıflar eski çizelgede kalır —, <em>çok programlı okul</em>: aynı
          sınıf düzeyine birden çok çizelge işaretlenir — ve <em>program/proje uygulayan okul</em>.
          Kademeli bir çizelgede kapsanmayan sınıf düzeyi kalırsa program onu en yeni programa
          düşürür ve kartta uyarı gösterir; sessizce geçmez.
        </p>
        <p>
          Program/proje çizelgeleri kendiliğinden gelmez, okul uyguladığını işaretler. Anadolu İmam
          Hatip Lisesinde spor, musiki, geleneksel ve çağdaş görsel sanatlar, ilahiyat odaklı
          hafızlık, fen ve teknoloji, çocuk gelişimi ve eğitimi ile Kur'an eğitim merkezi
          programlarının dersleri ayrı çizelgelerdir: okul yalnız kendi programını, ana çizelgenin{" "}
          <strong>yanına</strong> işaretler; öbür programların dersleri havuza girmez. Bu okullarda
          Osmanlı Türkçesi zorunlu ders olmaktan çıkar, program 10. sınıfta işaretlenince ders
          seçmeliye döner. Fen ve sosyal bilimler programının da kendi çizelgesi vardır: yeni ders
          getirmez, işaretlenince yalnız Osmanlı Türkçesi seçmeliye döner. Tematik program uygulayan
          Spor Lisesi de çizelgesini buradan seçer.
        </p>
        <p>
          Verilerinizi korumak için <Ekran to="/ayarlar?tab=guvenlik">Ayarlar → Güvenlik</Ekran>{" "}
          bölümünden uygulama parolası kurabilirsiniz. Parola kurulunca öğrenci ve öğretmen adları
          diskte şifreli tutulur; kurtarma anahtarını mutlaka güvenli bir yere not edin (ayrıntısı
          9. adımda).
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

      <Adim no={3} icon="group" title="Kişiler: öğrenci ve öğretmen listeleri">
        <p>
          <Ekran to="/kisiler">Kişiler</Ekran> ekranından öğrenci ve öğretmen listelerini içe
          aktarın. En hızlı yol e-Okul'dan indirdiğiniz raporu doğrudan yüklemektir (öğrenciler için
          Sınıf/Şube Öğrenci Listesi, öğretmenler için Personel Listesi raporu); program hazır
          şablon indirmenize ya da listeyi panodan yapıştırmanıza da izin verir.
        </p>
        <p>
          İçe aktarma iki aşamalıdır: <strong>önizleme hiçbir şey yazmaz</strong>, ne olacağını
          gösterir; onaylayınca kayıt işlenir. Aktarım sonrası şubeler kataloğa kendiliğinden düşer.
        </p>
        <Ipucu>
          Öğretmen listesi iki yerde işinize yarar: gözetmen görevlendirmesinde aday havuzu ve zümre
          başkanı seçiminde seçenek listesi buradan gelir. Bu yüzden öğretmenleri zümrelerden önce
          girin.
        </Ipucu>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Şube kataloğu: Ayarlar → Şubeler
        </h3>
        <p>
          Öğrenci aktarımında görülen her şube{" "}
          <Ekran to="/ayarlar?tab=subeler">Ayarlar → Şubeler</Ekran> sekmesindeki şube kataloğuna
          kendiliğinden eklenir; çoğu okulda bu sekmeye hiç dokunmanız gerekmez. İki durumda işinize
          yarar: öğrencisi henüz aktarılmamış bir şubeyi elle eklemek ve artık bulunmayan bir şubeyi
          kaldırmak. Kaldırmak öğrenci kayıtlarını etkilemez; aktarım o şubeyi yeniden görürse şube
          geri gelir. Katalog aktif ders yılına bağlıdır ve üç yeri besler: “Kendi dersliğinde”
          düzenindeki salon-şube eşlemesi, şube sınav duyurusu ve sihirbazdaki şube seçim listeleri.
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Öğrenci fotoğrafları (isteğe bağlı)
        </h3>
        <p>
          Fotoğraflar aktarılırsa salon evrakındaki oturma planı ve Yoklama ekranı her koltukta
          öğrencinin fotoğrafını gösterir; gözetmen öğrenciyi yerine fotoğrafla eşleştirerek
          oturtur. Fotoğrafları e-Okul'dan alırsınız: <strong>Öğrenci İşlemleri → Raporlar</strong>{" "}
          altındaki <strong>OOG01001R080 - Fotoğraflı Öğrenci Listesi</strong> raporunu{" "}
          <strong>Excel</strong> olarak indirin ve <Ekran to="/kisiler">Kişiler</Ekran> ekranındaki{" "}
          <strong>Öğrenci fotoğrafları</strong> kartından yükleyin. e-Okul bu raporu{" "}
          <strong>sınıf düzeyi başına</strong> verir; her düzeyin dosyasını ayrı ayrı aktarın.
          Fotoğraf okul numarasıyla eşleşir, bu yüzden önce öğrenci listesini aktarın.
        </p>
        <p>
          Önizleme, dosyadaki fotoğrafların kaçının yeni, kaçının kayıtlı fotoğrafla aynı, kaçının
          farklı olduğunu söyler; aynı dosyayı ikinci kez yüklemek hiçbir şeyi değiştirmez. Kayıtlı
          fotoğrafı yenisinden <strong>farklı</strong> öğrenciler varsa hangisinin kalacağını siz
          seçersiniz: <em>Mevcut fotoğrafları koru</em> ya da <em>Yenileriyle değiştir</em>.
          e-Okul'da fotoğrafı bulunmayan öğrencinin kayıtlı fotoğrafı silinmez.
        </p>
        <Ipucu>
          Fotoğraf kişisel veridir. Program onu yalnız bu bilgisayardaki veritabanında tutar ve
          yedeğe katar; uygulama parolası kuruluysa şifreli saklar. Okuldan ayrılan ya da silinen
          öğrencinin fotoğrafı kendiliğinden silinir. Bütün fotoğrafları kalıcı olarak kaldırmak
          için kartın üstündeki ya da <Ekran to="/ayarlar?tab=guvenlik">Ayarlar → Güvenlik</Ekran>{" "}
          bölümündeki <strong>“Tüm fotoğrafları sil”</strong> düğmesini kullanın.
        </Ipucu>
      </Adim>

      <Adim no={4} icon="menu_book" title="Ders Havuzu: tür ve sınav biçimi">
        <p>
          <Ekran to="/dersler">Ders Havuzu</Ekran>, okulun <strong>yürürlükteki</strong> haftalık
          ders çizelgesinden kendiliğinden türetilir: okul türü, hazırlık sınıfı, aktif ders yılı ve
          1. adımdaki çizelge ataması birlikte hangi Talim ve Terbiye Kurulu çizelgesinin geçerli
          olduğunu söyler. Sınav takvimi ve sınav oturumları dersleri bu havuzdan seçer. Ders{" "}
          <strong>silinmez</strong>, pasifleştirilir — geçmiş evrak bozulmasın diye.
        </p>
        <p>
          Listenin üstündeki <strong>“Yürürlükteki çizelge”</strong> kartı hangi programın hangi
          sınıf düzeyinde uygulandığını, dayanağını (kararın tarihi ve sayısı) ve varsa uyarıları
          gösterir. Okul türünü, hazırlık seçimini ya da ders yılını değiştirdiğinizde havuz
          kendiliğinden yenilenir; <strong>“Çizelgeyi yeniden uygula”</strong> düğmesi bunu elle
          tetikler ve kaç dersin eklendiğini, güncellendiğini ve çizelge dışı kaldığını söyler.
        </p>
        <p>
          Çizelge değişince havuzda kalan eski dersler <strong>“Çizelge dışı”</strong> rozetiyle
          pasifleşir; o ders çizelgeye geri girerse kendiliğinden yeniden açılır. Sizin{" "}
          <strong>“Pasifleştir”</strong> dediğiniz ders ise asla kendiliğinden açılmaz — aktiflik
          idari bir karardır, program ona dokunmaz.
        </p>
        <p>
          Listenin iki sütunu takvim havuzunun nasıl dolacağını belirler. <strong>Tür</strong>{" "}
          dersin <em>zorunlu</em> mu yoksa <em>seçmeli</em> mi olduğunu, <strong>Sınav</strong> ise
          dersin sınavının <em>Yazılı</em> mı, <em>Uygulama</em> mı olduğunu ya da o dersin hiç
          sınavı olmadığını (<em>Sınav yok</em>) söyler. MEB çizelgesinden gelen dersler için bu
          alanlar hazır doldurulmuştur: Beden Eğitimi ve Spor, Görsel Sanatlar/Müzik, Spor ve Sanat
          Eğitimi <em>Uygulama</em>, Rehberlik ve Yönlendirme <em>Sınav yok</em> gelir. Okulunuzun
          uygulaması farklıysa satırdaki <strong>Düzenle</strong> düğmesiyle dersin adını, sınıf
          düzeylerini, türünü ve sınav biçimini değiştirebilirsiniz.
        </p>
        <p>
          <strong>Ancak çizelgeden gelen bir derste bu düzenleme kalıcı değildir.</strong> Ad, sınıf
          düzeyi, tür ve sınav biçimi <em>çizelge verisidir</em>: çizelge yeniden uygulandığında
          (okul türü, hazırlık ya da ders yılı değişikliği; program güncellemesiyle gelen yeni
          çizelge) MEB değerine döner. Kalıcı olarak farklı kalması gereken bir ders için çizelge
          dersini <strong>pasifleştirip</strong> yanına <em>farklı adla</em> elle bir ders ekleyin —
          elle eklenen derse çizelge güncellemesi dokunmaz. Buna karşılık{" "}
          <strong>pasifleştirme her zaman kalıcıdır</strong>.
        </p>
        <p>
          Seçmeli derslerde <strong>“Şubeler”</strong> sütununa basıp o dersi hangi şubelerin
          aldığını işaretleyin — sınav takvimi havuzu bu bilgiyle kendiliğinden dolar ve her
          takvimde yeniden şube seçmezsiniz. Şubeleri girilmemiş yazılı seçmeli, sütunda uyarı
          işaretiyle görünür. Bu tanım ders yılına özeldir: yeni ders yılında yeniden girilir
          (şubeler her yıl yeniden kurulduğu için eski seçim taşınmaz).
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Seçmeli dersi şubenin bir kısmı alıyorsa: öğrenci listesi
        </h3>
        <p>
          Bir şubedeki öğrencilerin hepsi aynı seçmeliyi almayabilir; örneğin 9/A ve 9/B'de bir grup
          Kur'an-ı Kerim, bir grup Peygamberimizin Hayatı dersini alır. Böyle bir derste şubeyi
          işaretlemek yetmez: program şubenin tamamını o dersin öğrencisi sayar, iki dersi aynı
          oturuma koyduğunuzda her öğrenci iki derse düşer ve dağıtım durur. Dersi{" "}
          <strong>alan öğrencileri</strong> girdiğinizde sınav oturumu her öğrenciyi yalnız kendi
          dersine alır, kitapçığını kendi dersinin sorularıyla basar ve salon evrakındaki ders
          sayıları doğru çıkar. Öğrencileri ayrık iki seçmeli takvimde aynı ders saatine de
          konabilir.
        </p>
        <p>
          En kısa yol e-Okul'dur: e-Okul'da <strong>Öğrenci Seçmeli Derslerini Belirle</strong>{" "}
          ekranının <strong>Raporlar</strong> menüsünden{" "}
          <strong>OOK10002R010 - Seçmeli Ders Öğrencileri</strong> raporunu <strong>PDF</strong>{" "}
          olarak kaydedin (aynı raporun Excel çıktısında ders adları bulunmaz). Sonra{" "}
          <Ekran to="/dersler">Ders Havuzu</Ekran> ekranının üstündeki{" "}
          <strong>“e-Okul'dan seçmeli öğrencileri aktar”</strong> düğmesiyle dosyayı seçin, önce{" "}
          <strong>Önizle</strong> — hangi e-Okul dersinin havuzdaki hangi derse eşleştiğini ve kaç
          öğrencinin geleceğini görürsünüz — sonra <strong>Aktar</strong>. Raporun kapsadığı
          şubelerde her dersin bu yılki öğrenci listesi ve şubeleri yenilenir; raporda olmayan
          derslere ve şubelere dokunulmaz, yani raporu tek bir sınıf düzeyi için de alabilirsiniz.
          Öğrenciler okul numarasıyla eşleştiği için önce öğrenci listesini (3. adım) güncelleyin;
          nakil gelen öğrenci de e-Okul'da seçmelisi girilip rapor yeniden aktarılınca listeye
          girer.
        </p>
        <p>
          Aktarım ders havuzunu da toparlar. Raporda olup havuzda hiç karşılığı olmayan seçmeli
          önizlemede <strong>“Havuza ekle”</strong> kutusuyla, işaretli gelir; aktarınca seçmeli
          ders olarak havuza eklenir (istemediğinizin işaretini kaldırın). Raporun bütün şubelerini
          kapsadığı bir sınıf düzeyinde öğrencisi olmayan seçmeli <strong>“Bu yıl açılmadı”</strong>{" "}
          sayılır: Ders Havuzu'nda kendiliğinden gizlenir (“Açılmayanları göster” ile görünür),
          takvimde “Dersleri ekle” onları atlananlar listesine tek tek yazmaz. Bu dersler
          pasifleştirilmez; şubelerini girerseniz yeniden açılır.
        </p>
        <p>
          Elle düzeltmek için dersin <strong>“Şubeler”</strong> penceresinde şubenin yanındaki{" "}
          <strong>Öğrenciler</strong> düğmesine basın: <em>Şubenin tamamı bu dersi alıyor</em> ya da{" "}
          <em>Yalnız işaretlenen öğrenciler alıyor</em>. İşaretlemediğiniz öğrencileri aynı adımda
          başka bir seçmeliye (örneğin Peygamberimizin Hayatı) yazabilirsiniz. Listesi girilmiş
          şubeler “Şubeler” sütununda öğrenci sayısıyla görünür (“9: A (14), B”).
        </p>
        <Ipucu>
          Liste dağıtımdan sonra değişirse (e-Okul'u yeniden aktardınız ya da bir öğrencinin dersi
          değişti) yerleşim ve kitapçıklar eski listeye göre kalır. Oturum sayfası bunu bir uyarı
          bandıyla söyler; oturumu yeniden dağıtın.
        </Ipucu>
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
          “Yabancı Dil”) ve her zümrenin başkanını öğretmen listesinden seçin.
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
          <Ekran to="/salonlar">Salonlar</Ekran> ekranında sınav yapılacak salonları tanımlayın:
          sıra düzenini oturma düzeni editöründe çizin, tek/çift kişilik sıraları ve numaralandırma
          yönünü seçin. Bir salonu bir şubeye bağlarsanız (şube dersliği) “Kendi dersliğinde”
          yapılacak sınavlarda program o salonu kullanır.
        </p>
        <p>
          Planın en üstündeki şerit salonun <strong>ön cephesidir</strong> — öğretmen masası, tahta
          ve kapı oraya konur. Bu şerit <strong>satır sayımına girmez</strong>: “Sıra satırı” ve
          “Sıra sütunu” alanları yalnız öğrenci sıralarını sayar.
        </p>
        <p>
          Yeni salon boş planla değil <strong>varsayılan şablonla</strong> açılır: öğretmen masası
          ön-solda, kapı çizilmemiş, bütün hücreler ikili sıra — dört sütun ve beş sırayla kırk
          koltuk. Koltuk numaraları <strong>öğretmen masasının önünden</strong> başlar; masayı başka
          bir köşeye taşırsanız numaralandırma da onunla döner. Kapı yalnız krokiye çizilir,
          numaralandırmaya girmez — varsayılanda hiç yoktur, çünkü yeri okuldan okula değişir ve
          uydurulmuş bir kapı resmî salon evrakına yanlış bilgi basmak olurdu. Editördeki{" "}
          <strong>“Varsayılan şablon”</strong> düğmesi aynı düzeni açık salona uygular ve bunu{" "}
          <strong>salonun kendi satır/sütun ölçüsünde</strong> yapar, 4×5'e zorlamaz; kaydetmezseniz
          kalıcı olmaz.
        </p>
        <p>
          Program daha önce kurulmuşsa ve onlarca salon eski düzende kaldıysa Salonlar sayfasındaki{" "}
          <strong>“Şablonu topluca uygula”</strong> düğmesini kullanın. Diyalog eski düzendeki
          salonları işaretli açar, her salonu kendi ölçüsünde şablona çeker ve kapasiteyi korur.{" "}
          <strong>Yerleşimi yapılmış salonlar atlanır</strong> ve adlarıyla bildirilir: basılmış
          evraktaki koltuk numarası planla çelişmesin diye. Onları editörden tek tek
          değiştirebilirsiniz.
        </p>
        <p>
          Salon planı bir kez çizilir, her sınavda yeniden kullanılır. Boş yerleşim planını PDF
          olarak alıp kapıya asabilirsiniz.
        </p>
        <Ipucu>
          <strong>İkili eğitim yapıyorsanız salonları kümeleyin.</strong> “Şube dersliklerini
          oluştur” her şube için bir salon (şube dersliği) üretir; ikili eğitimde liste
          kalabalıklaşır ve sihirbazda tek tek işaretlemek zorlaşır. Salonlar ekranındaki{" "}
          <strong>“Salon kümeleri”</strong> düğmesiyle “Sabah”, “Öğle” gibi kümeler tanımlayıp
          salonları topluca atayın — sınav sihirbazında kümenin tamamı tek tıkla seçilir. Küme
          yalnız seçim kolaylığıdır; evrağa basılan konum bilgisi salonun “blok/kat” alanıdır.
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
          Bakanlık bir ders yılının sınav haftalarını ayrıca ilan ettiyse takvimler{" "}
          <strong>o tarihlerle</strong> açılır. 2026-2027 için Ölçme, Değerlendirme ve Sınav
          Hizmetleri Genel Müdürlüğünün 10.09.2026 tarihli yazısı esastır: 1. dönem 1. yazılı 2-13
          Kasım 2026, 1. dönem 2. yazılı 4-15 Ocak 2027, 2. dönem 1. yazılı 29 Mart-9 Nisan 2027, 2.
          dönem 2. yazılı 7-18 Haziran 2027. Bu tarihler <strong>varsayılandır</strong>: yeni takvim
          penceresinde tarih alanları onlarla dolar, siz değiştirebilirsiniz. Tarihleri ilandan
          farklı bir taslak takvimde başlığın altında bir öneri görünür; “Tarihleri düzenle”
          penceresindeki <strong>“Bu tarihleri kullan”</strong> düğmesi ilan edilen haftaları tek
          tıkla yazar.
        </p>
        <p>
          Aynı yazının ekindeki <strong>ülke geneli ortak yazılı sınavlar</strong> Bakanlıkça
          hazırlanır. 2026-2027'de lisede dört tanedir: 10. sınıf Türk Dili ve Edebiyatı (12.11.2026
          Perşembe), 9. sınıf Matematik (06.01.2027 Çarşamba), 9. sınıf Türk Dili ve Edebiyatı
          (07.04.2027 Çarşamba) ve 10. sınıf Matematik (09.06.2027 Çarşamba). Takvim oluşturulurken
          program bunları <strong>Bakanlık sınavı</strong> olarak resmî günlerine, okulunuzun ilk
          sınav saatine sabitler. Bakanlık takvimi ders saatini vermez; saat uygulama esaslarıyla
          belli olunca sınavı <strong>Yerleştirme</strong> sekmesinde doğru saate taşırsınız. O gün
          o sınıf düzeyine otomatik yerleştirmede okul sınavı konmaz. Takvim sayfasının üstündeki
          bant sınavların durumunu gösterir; daha önce oluşturulmuş taslak takvimde{" "}
          <strong>“Takvime uygula”</strong> düğmesini kullanın.
        </p>
        <p>
          Takvimin dört sekmesi vardır: <strong>Havuz</strong> (hangi ders hangi sınıf düzeyinde
          sınav olacak), <strong>Yerleştirme</strong> (hangi gün, hangi ders saati),{" "}
          <strong>Süreç Takip</strong> (soru teslimi, basım, puan girişi gibi kalemler) ve{" "}
          <strong>Önizleme</strong> (açıklamalar, dipnot, imza zümreleri ve PDF).
        </p>
        <p>
          Takvimin iki durumu vardır: <strong>Taslak</strong> ve <strong>Onaylandı</strong>. Havuz,
          yerleştirme, açıklama, dipnot ve imza zümreleri yalnız taslak durumda değişir. Takvim
          hazır olduğunda başlıktaki <strong>“Onayla”</strong> düğmesine basarsınız; onay tarihi ve
          onaylayan kaydedilir, PDF'teki “TASLAK” filigranı kalkar. Onaylı takvimi düzenlemek için
          önce <strong>“Taslağa al”</strong> deyin: program onayın kalkacağını söyleyip sizden onay
          ister; bu takvimden üretilmiş oturumlar etkilenmez, ama duyurmadan önce takvimi yeniden
          onaylamanız gerekir.
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Havuzu doldurmak: zorunlu dersler ve seçmeliler
        </h3>
        <p>
          Havuz sekmesinde iki düğme vardır. <strong>“Dersleri ekle”</strong>, ders havuzundaki{" "}
          <em>zorunlu</em> ve sınavı <em>Yazılı</em> dersleri — ve{" "}
          <strong>şubelerini girdiğiniz</strong> seçmelileri — öğrencisi olan her sınıf düzeyi için
          tek tıkla havuza koyar; uygulama sınavı yapılan ve sınavı olmayan dersler eklenmez. Şubesi
          henüz girilmemiş seçmeli atlanır ve size bildirilir. <strong>“Seçmeli ders seç”</strong>{" "}
          ise sınıf düzeyi sekmeleri açar: kalan seçmelileri elle işaretlersiniz. Havuzda zaten
          bulunan ders işaretli ve kilitli görünür, ikinci kez eklenmez.
        </p>
        <Ipucu>
          Bir seçmeliyi <strong>hangi şubelerin aldığını</strong> her takvimde yeniden seçmeyin:
          bunu bir kez <Ekran to="/dersler">Ders Havuzu</Ekran> ekranında, dersin{" "}
          <strong>“Şubeler”</strong> sütunundan girin. Dört sınav takvimi de o bilgiyi kullanır,
          havuz kendiliğinden dolar.
        </Ipucu>
        <p>
          Seçmeli seçim penceresinde şube kutuları ders havuzundaki tanımdan <strong>dolu</strong>{" "}
          gelir; dilerseniz o takvime mahsus değiştirebilirsiniz. <strong>Katılımcılar</strong>{" "}
          alanının iki seçeneği vardır: <em>Sınıf düzeyinin tamamı</em> ya da{" "}
          <em>Seçili şubeler</em>. Şube seçerken Ayarlar’daki <strong>şube kümelerini</strong> (SAY,
          EA, DİL gibi — 8. adımda anlatılır) çipe basarak topluca ekleyebilirsiniz. Küme yalnız
          seçim kolaylığıdır — takvime kümenin adı değil, seçilen şubeler yazılır.
        </p>
        <p>
          Katılımcıları yanlış verdiyseniz girdiyi silmeniz gerekmez: havuz tablosunda{" "}
          <strong>“Katılımcılar”</strong> sütunundaki değere basınca düzenleme penceresi açılır.
          Takvim taslak olduğu sürece çizelgeye yerleştirilmiş girdinin katılımcıları da buradan
          düzeltilir. Bir girdinin katılımcıları ders havuzundaki tanımdan farklıysa yanında{" "}
          <strong>“özel”</strong> rozeti görünür — o sınava mahsus istisna yaptığınızı hatırlatır.
        </p>
        <Ipucu>
          Yeni bir takvim açtığınızda zorunlu dersler <strong>kendiliğinden</strong> havuza gelir
          (1. ve 2. sınav takvimlerinde). Geriye yalnız seçmelileri işaretlemek ve gerekiyorsa özel
          durumları — “Kendi dersliğinde” yapılacak sınavlar (formdaki <strong>Düzen</strong>{" "}
          alanı), uygulama sınavları, Bakanlık/MEM sınavları — havuz formundan elle eklemek kalır.
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
            <strong>Boşları doldur:</strong> yalnız havuzda bekleyenleri yerleştirir, çizelgedeki
            sınavlara hiç dokunmaz.
          </li>
          <li>
            <strong>Sabitler hariç yeniden dağıt:</strong> kilitlemediğiniz sınavları havuza alıp
            baştan dağıtır. Sonucu beğenmezseniz tekrar çalıştırabilirsiniz.
          </li>
        </ul>
        <p>
          Elle yerleştirdiğiniz her sınav <strong>kendiliğinden sabitlenir</strong>: yerleştirme
          çizelgesindeki çipin üzerinde kilit simgesi görünür ve otomatik dağıtım onu yerinden
          oynatmaz. Kilide tıklayarak sabitlemeyi kaldırabilir, otomatik yerleşmiş bir sınavı da
          kilitleyebilirsiniz. Bir sınavı havuza geri alırsanız sabitlemesi düşer. Çipteki{" "}
          <strong>“Uygulama”</strong> rozeti uygulamalı sınavı, <strong>“Kendi dersliğinde”</strong>{" "}
          rozeti kelebek dağıtıma girmeyen sınavı gösterir.
        </p>
        <p>
          Elle yerleştirirken program bir kuralı <em>hatırlatıyor</em> ama yerleştirmeyi
          engellemiyorsa (örneğin aynı gün üçüncü sınav) uyarı, çizelgenin üstündeki{" "}
          <strong>“Yerleştirme uyarıları”</strong> bandında birikir ve siz <strong>“Kapat”</strong>{" "}
          diyene dek ekranda kalır. Kabul edilmeyen yerleştirmenin gerekçesi ise ekranın altında
          kısa bir bildirimle gösterilir.
        </p>
        <p>Program dağıtırken şu kurallara uyar:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>Aynı öğrenciye günde ikiden fazla sınav düşürmez.</li>
          <li>Katılımcıları kesişen iki sınavı aynı saate koymaz.</li>
          <li>Üst makam sınavı olan güne o sınıf düzeyinin okul sınavını yazmaz.</li>
          <li>Hafta sonlarını ve sınav saati işaretlemediğiniz ders saatlerini kullanmaz.</li>
          <li>
            Bakanlık/İl MEM/İlçe MEM sınavlarını <strong>hiç yerleştirmez</strong> — tarihleri
            ilgili makamın kılavuzundadır, onları siz koyarsınız.
          </li>
          <li>
            Sınavları haftaların <strong>son gününden başlayarak</strong> yerleştirir: Bakanlığın
            10.09.2026 tarihli yazısı okul geneli sınav tarihlerinin, derslerin konu kapsamı ve
            öğretim sürecinin ilerleyişi gözetilerek sınav haftalarının son gününden başlanarak
            planlanmasını ister. Bu bir tercihtir; “Otomatik yerleştir” penceresindeki kutuyu
            kaldırırsanız sınavlar günlere dengeli yayılır.
          </li>
        </ul>
        <Ipucu>
          2. dönem 2. yazılı haftasına YKS gibi merkezî bir sınav denk gelirse o sınava girecek
          öğrencilerin yazılılarını okul yönetimi ayrıca planlar (aynı yazı, 11. madde). Program
          bunu kendiliğinden bilmez; o hafta için takvimi elle gözden geçirin.
        </Ipucu>
        <p>
          İşlem bitince bir rapor açılır: kaç sınav yerleştirildi, hangileri yerleştirilemedi ve
          neden. Yerleştirilemeyen sınav kalırsa takvim aralığını genişletin, sınav saati ekleyin ya
          da o sınavı elle koyun.
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Aynı saate iki sınav: katılımcı kuralı
        </h3>
        <p>
          Bir öğrenci aynı anda iki salonda olamaz. Bu yüzden program, aynı gün ve ders saatine{" "}
          <strong>katılımcıları kesişen</strong> iki sınav koymanızı kabul etmez. Katılımcılar
          kesişmiyorsa — örneğin 9/A'nın Almanca, 9/B'nin Fransızca sınavı — aynı saatte yan yana
          yapılabilir. Sınıf düzeyinin tamamına yapılan bir sınav o düzeydeki her şubeyle kesişir.
          Aynı şubede iki seçmeli de aynı saate konabilir: iki dersin öğrenci listesi girilmişse ve
          iki dersi birden alan öğrenci yoksa (9/A'nın bir grubu Kur'an-ı Kerim, kalanı
          Peygamberimizin Hayatı). Böyle öğrenci varsa program kaç öğrenci olduğunu söyleyerek
          reddeder; listesi girilmemiş şube “şubenin tamamı” sayılır.
        </p>
        <p>
          Günlük sınav sayısı hesabı ise yalnız <em>tam</em> listeye güvenir: bir seçmelinin o sınıf
          düzeyindeki bütün şubelerinde öğrenci listesi varsa sayım listedeki öğrencilere göre
          yapılır; tek bir şubesi listesizse ders o düzeydeki herkesin yüküne eklenir. Bir şubenin
          seçmeliyi aldığını bilmek, o şubedeki her öğrencinin aldığını göstermez — sayım bu yüzden
          ihtiyatlı kalır.
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
          <li>Aynı gün ve sınıf düzeyinde iki sınava kadar sessizce izin verir.</li>
          <li>
            <strong>Üçüncü sınavda uyarır</strong> ama engellemez — “zorunlu hâl” takdiri okul
            müdürlüğünündür.
          </li>
          <li>
            <strong>Dördüncü sınavı hiç kabul etmez</strong>; yerleştirme reddedilir.
          </li>
          <li>
            Sayım <strong>öğrenci bazlıdır</strong>: aynı gün aynı sınıf düzeyine konan derslerin
            kaç öğrenciyi birlikte etkilediğine bakılır.
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
          Okul dışı makam sınavları takvimde ayrı görünür: yerleştirme çizelgesinde BAK / İL / İLÇE
          rozeti taşırlar, PDF'te ise gölgeli ve sol kenarı çizgili hücrede “BAKANLIK SINAVI”, “İL
          MEM SINAVI” veya “İLÇE MEM SINAVI” etiketiyle basılırlar. Aynı güne hem okul hem üst makam
          sınavı koyarsanız program uyarır.
        </p>
        <Mevzuat kaynak="MEB Yazılı ve Uygulamalı Sınavlar Yönergesi md. 5">
          Ülke geneli yapılacak ortak yazılı sınavlar Bakanlıkça, il geneli yapılacak ortak yazılı
          sınavlar ise il millî eğitim müdürlüğünce belirlenen tarih ve saatlerde yapılır.
        </Mevzuat>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Süreç Takip: işleri izleme ve kalemleri düzenleme
        </h3>
        <p>
          <strong>Süreç Takip</strong> sekmesi, takvimdeki her sınav için yapılacak işleri
          izlediğiniz bir çizelgedir: satırlar sınavlar (ders ve sınıf düzeyi), sütunlar süreç
          kalemleridir (soru teslimi, basım, puan girişi gibi). Bir hücreye tıkladıkça durum sırayla
          değişir: işaretsiz → <em>Yapıldı</em> → <em>Kapsam dışı</em> → işaretsiz.{" "}
          <strong>“Not modu”</strong> açıkken tıklama durumu değiştirmez, o hücre için not
          yazabileceğiniz bir pencere açar; işaretin tarihi ve notu, fareyle hücrenin üzerine
          gelince görünür.
        </p>
        <p>
          Kalemleri okulunuza göre düzenlemek için <strong>“Kalem yönetimi”</strong> düğmesini
          kullanın: yeni kalem ekleyebilir, adını ve açıklamasını değiştirebilir, kullanmadığınız
          kalemi <strong>“Pasifleştir”</strong> ile gizleyebilirsiniz. Kalem listesi bütün takvimler
          için tektir: pasifleştirdiğiniz kalem bütün takvimlerin çizelgesinden kalkar.
          Pasifleştirme işaretleri silmez; kalemi <strong>“Etkinleştir”</strong> ile geri
          getirdiğinizde eski işaretler de geri gelir.
        </p>

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
          Takvim onaylandıktan sonra yerleştirme çizelgesindeki her sınav saati için{" "}
          <strong>“Oturum üret”</strong> düğmesiyle <Ekran to="/oturumlar">Oturum</Ekran>{" "}
          üretebilirsiniz; sihirbazla elle de oturum açabilirsiniz. Oturumda dersleri, katılacak
          şubeleri ve kullanılacak salonları seçersiniz.
        </p>
        <p>
          Dağıtımı başlattığınızda program öğrencileri salonlara “kelebek” düzende yerleştirir: aynı
          dersi aynı sınıf düzeyinde alan öğrenciler yan yana ve ön arkaya düşmez. Sonuç bağımsız
          bir denetimden geçer; <strong>kural ihlali varsa onay verilmez</strong>. Aynı dağıtım
          numarası (seed) aynı dağıtımı üretir ve bu numara dağıtım doğrulama raporuna basılır.
        </p>
        <p>
          Öğrenci sayıları karışmaya elverişli değilse — örneğin salonda tek ders varsa — aynı
          sınava giren öğrencilerin yan yana düşmesi matematiksel olarak kaçınılmaz olabilir. Bu
          durumda program o çiftleri <strong>öğretmen masasına en yakın sıralara</strong> çeker;
          gözetim en zor olan yerler öğretmenin önünde kalır. Bu yalnız bir tercihtir: kaçınılmaz
          olmayan hiçbir komşuluğu yaratmaz ve kural ihlali sayısını artırmaz.
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Şube ve salon kümeleriyle hızlı seçim
        </h3>
        <p>
          Sihirbazın katılımcı adımında{" "}
          <Ekran to="/ayarlar?tab=sube-kumeleri">Ayarlar → Şube Kümeleri</Ekran> ekranında
          tanımladığınız kümeler (Sayısal, Eşit Ağırlık, Dil…) çip olarak görünür; çipe basınca o
          kümenin şubeleri seçime eklenir. Küme seçili sınıf düzeyiyle kesiştirilir — bir oturum
          dersi tek sınıf düzeyine bağlıdır. Salon adımında da salon kümeleri düğme olarak çıkar.
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Engelli ve özel durumlu öğrencilerin salonunu ve yerini sabitleme
        </h3>
        <p>
          Engel durumu, BEP ya da sağlık nedeniyle belirli bir yerde oturması gereken öğrencilerin{" "}
          <strong>salonu ve koltuğu</strong>, oturum detayındaki{" "}
          <strong>Yerleştirme Kuralları</strong> sekmesinden <strong>“Kural ekle”</strong> ile
          sabitlenir. Kural sahibi öğrenci kelebek dağıtım çalışmadan önce yerine oturtulur;{" "}
          <strong>dağıtım onu yerinden oynatamaz</strong>. Kalan öğrenciler artakalan koltuklara
          kelebek düzende dağıtılır.
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
            <strong>Salon</strong> zorunludur — öğrencinin sınava gireceği salonu seçersiniz.
          </li>
          <li>
            <strong>Koltuk</strong> isteğe bağlıdır: “salon içinde serbest” bırakabilir ya da
            listeden birebir bir koltuk seçebilirsiniz. Liste her koltuğu sözle tarif eder: sırası,
            sütunu, sıra içindeki yeri (sol / orta / sağ) ve o plandaki koltuk numarası.
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
          uygulanır: oturumu dağıttıktan sonra kural eklerseniz oturum başlığındaki{" "}
          <strong>“Yeniden dağıt”</strong> düğmesine basmanız gerekir; bu, yeni bir dağıtım
          numarasıyla bütün yerleşimi yeniler. Ders, şube ya da salon seçimini de değiştirecekseniz{" "}
          <strong>“Taslağa al”</strong> ile sihirbaza dönün (aşağıda anlatılır). Onaylanmış oturuma
          kural eklenemez — önce “Yeniden aç” ile onayı geri alın; arşivlenmiş oturum
          değiştirilemez.
        </Ipucu>
        <p>Kural yazarken üç noktaya dikkat edin:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>“Kendi dersliğinde” için bağlı şube şarttır.</strong> Program öğrencinin
            şubesine <em>bağlı</em> bir salon (şube dersliği) arar (Salonlar ekranındaki “bağlı
            şube” alanı); bulamazsa dağıtımı reddeder ve hangi şubenin dersliğinin eksik olduğunu
            söyler.
          </li>
          <li>
            <strong>Kural, oturumun salon listesinde olmayan bir salonu da hedef alabilir.</strong>{" "}
            Öğrenci oraya yerleşir; o salon yerleşimde, gözetmen listesinde ve salon sınav evrakında
            ayrı bir salon olarak görünür. Tek öğrenci için açılan salona da gözetmen gerektiğini
            unutmayın.
          </li>
          <li>
            <strong>Koltuk, numarasıyla değil koordinatıyla saklanır.</strong> Numaralandırma yönünü
            değiştirmek kuralı bozmaz; ama salon planını değiştirip o koltuğu kaldırırsanız kural
            “Seçilen koltuk salonun planında yok” hatası verir. Aynı koltuk iki kurala verilemez ve
            hedef salonda boş koltuk kalmazsa dağıtım durur.
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
          şubelerini ve kullanılacak salonlarını bu taslağa aktarabilir, sonra üzerinde değişiklik
          yapabilirsiniz. Zaten ekli olanlar atlanır ve size listelenir. Sınav tarihi ve saati,
          dağıtım numarası, yerleşim, yoklama, gözetmen görevlendirmesi ve onay damgaları
          kopyalanmaz — bunlar her oturuma özgüdür.
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Aynı ders birden çok sınıf düzeyinde: ayrı sorular mı, aynı kitapçık mı?
        </h3>
        <p>
          Bir dersi iki sınıf düzeyinde (örneğin Türk Dili ve Edebiyatı 9 ve 10) aynı oturuma
          eklerseniz her sınıf düzeyi <strong>ayrı bir sınavdır</strong>: kendi soru dosyasını alır
          ve kelebek dağıtımda 9 ile 10. sınıf öğrencileri yan yana oturabilir, çünkü farklı
          soruları çözerler. Program bunu varsayılan sayar; ek bir şey işaretlemeniz gerekmez.
        </p>
        <p>
          Yalnız dersin tüm sınıf düzeyleri <strong>aynı soru kitapçığını</strong> çözecekse ders
          listesinin altındaki “… aynı soru kitapçığını çözecek” kutusunu işaretleyin. O zaman
          Sorular sekmesinde o ders tek satır olur, tek dosya yüklenir ve bu öğrenciler birbirinin
          yanına oturtulmaz. Bu kutunun MEB mevzuatındaki “ortak sınav” kavramıyla ilgisi yoktur:
          okul geneli ortak yazılı sınav zaten olağan durumdur ve kutu boşken yürür.
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Soru dosyaları ve kişiselleştirilmiş kitapçıklar
        </h3>
        <p>
          Dağıtımdan sonra <strong>Sorular ve Kitapçıklar</strong> sekmesinde her ders ve sınıf
          düzeyi satırına A4 dikey soru PDF dosyasını yüklersiniz. Panelden indirilen Word şablonu
          sayfanın üst 4 santimetresini boş bırakır; oraya öğrencinin adı, numarası, salonu ve puan
          bölümü basılır. “Kitapçıkları üret” düğmesi salon salon ZIP paketi çıkarır: her öğrenciye
          oturma sırasında, adına basılı bir kitapçık. İsimsiz yedek kopya sayısı salon başına
          eklenir.
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Dağıtımdan sonra fark edilen hata: “Yeniden dağıt” ve “Taslağa al”
        </h3>
        <p>
          Dağıtımı beğenmediyseniz ya da sonradan yerleştirme kuralı eklediyseniz oturum
          başlığındaki <strong>“Yeniden dağıt”</strong> düğmesi ders, şube ve salon seçimine
          dokunmadan yerleşimi baştan kurar (dağıtım numarasını boş bırakırsanız yeni bir
          numarayla). Elle yaptığınız koltuk takasları ve gözetmen görevlendirmeleri sıfırlanır;
          daha önce bastığınız evrakı ve ürettiğiniz kitapçıkları yeniden üretmeniz gerekir. Eski
          kitapçık paketleri Sorular ve Kitapçıklar sekmesinde{" "}
          <strong>“Eski yerleşime göre — yeniden üretin”</strong> uyarısıyla işaretlenir; koltuk
          takasından sonra da aynı uyarı çıkar.
        </p>
        <p>
          Yanlış sınıf düzeyi, eksik şube ya da yanlış işaretlenmiş kitapçık kutusu gibi{" "}
          <em>seçimin kendisindeki</em> bir hatayı dağıtımdan sonra fark ederseniz oturum
          başlığındaki <strong>“Taslağa al”</strong> düğmesi sihirbaza geri döndürür: yerleşim ve
          gözetmen görevlendirmeleri silinir; ders, şube ve salon seçimi, yerleştirme kuralları ve
          yüklenmiş soru dosyaları korunur. Düzeltip yeniden dağıtırsınız. Onaylanmış oturumda önce
          “Yeniden aç”, sonra “Taslağa al” denir; arşiv geri dönüşsüzdür.
        </p>
      </Adim>

      <Adim no={9} icon="description" title="Evrak, gözetmenler ve yoklama">
        <p>
          Evrak, oturum <strong>dağıtıldığı andan itibaren</strong> basılır; onayı beklemeniz
          gerekmez. Onay yerleşimi kilitler; arşivlenmiş oturumdan da yeniden basım yapılabilir.
          Oturum detayındaki <strong>Evrak</strong> sekmesinde salon sınav evrakı tek belgede
          birleşiktir ve çift yüz basıldığında salon başına bir kâğıttır. <strong>1. yaprak</strong>{" "}
          fotoğraflı oturma planıdır ve yoklama da onun üstünde alınır: her koltuğun kartında
          öğrencinin fotoğrafı, adı, numarası ve şubesi, bir imza yeri ve bir “Yok” kutusu vardır.
          Öğrenci imzasını kendi kartına atar; sınava girmeyenin “Yok” kutusu işaretlenir.{" "}
          <strong>2. yaprak</strong> salon ve oturum bilgilerini, gözetmen işlemlerini, sınav evrakı
          sayımını ve teslim zincirini taşır. Ayrıca şube sınav duyurusu (kapıya asılan liste),
          gözetmen görevlendirme yazısı, dağıtım doğrulama raporu ve ihlal/kopya tutanağı üretilir.
          Hepsi PDF olarak indirilir ve doğrudan basılabilir.
        </p>
        <p>
          Fotoğrafı aktarılmamış öğrencinin kartında fotoğraf yerine boş bir kutu basılır (3. adım).
          Salonun oturma düzeni dağıtımdan sonra değiştirildiyse koltuğu yeni planda bulunmayan
          öğrenciler plan yerine altta ayrı bir listede, imza yeriyle basılır ve yaprak bunu
          uyarıyla bildirir.
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Gözetmen görevlendirme ve muaf öğretmenler
        </h3>
        <p>
          Gözetmen görevlendirmesi oturum bazında açılır: sihirbazın{" "}
          <strong>Oturum Bilgileri</strong> adımındaki gözetmen görevlendirmesi kutusunu
          işaretlerseniz oturum detayındaki <strong>Gözetmenler</strong> sekmesinde her salona
          öğretmen listesinden elle gözetmen atarsınız. Kutu boşsa görevlendirme yazısı basılmaz,
          salon evrakındaki görevli adı elle yazılır. Görevlendirme yazısı tebellüğ imzası için yer
          bırakır.
        </p>
        <p>
          Bir öğretmeni gözetmenlikten muaf tutmak için <strong>Gözetmenler</strong> sekmesinin
          altındaki <strong>“Muaf öğretmenler”</strong> bölümünü kullanın: öğretmeni, gerekçe
          kategorisini (sağlık, idari görev, diğer) ve muafiyetin kalıcı mı yoksa yalnız o oturum
          için mi olduğunu seçersiniz. Muaf öğretmenler aday listesinde görünmeye devam eder ama
          seçilemez; yanlarında nedeni yazar (“muaf” gibi) — böylece “neden seçemiyorum” sorusu
          ekranda yanıtlanır. Gerekçe yalnız kategori olarak tutulur; açıklama yazılmaz.
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Yoklama: sınava girmeyen öğrenciler ve mazeret
        </h3>
        <p>
          Oturum <strong>onaylandıktan sonra</strong> oturum detayında <strong>Yoklama</strong>{" "}
          sekmesi açılır (yerleşim kesinleşmeden yoklama alınmaz). Sekme, basılı evraktaki
          fotoğraflı oturma planının aynısını salon salon gösterir: sınava girmeyen öğrencinin
          kartına basarsınız, kart <strong>“Girmedi”</strong> olarak işaretlenir ve öğrenci “Sınava
          girmeyenler” listesine <em>Beklemede</em> durumuyla düşer. Böylece gözetmenin basılı
          plandaki “Yok” işaretlerini aynı düzende, karttan karta aktarırsınız. Veli mazeretini
          bildirince durumu <em>Mazeretli</em> ya da <em>Mazeretsiz</em> yapar, belgenin numarasını
          ve tarihini not alanına yazarsınız (belgenin kendisi programa yüklenmez). Yanlış işareti
          karta yeniden basarak ya da listedeki “İşareti kaldır” ile geri alırsınız.
        </p>
        <Mevzuat kaynak="MEB Yazılı ve Uygulamalı Sınavlar Yönergesi md. 5">
          Ortak sınavlara katılmayan öğrencilerin bilgileri okul müdürlüğü tarafından sınav
          bitiminde e-Okula işlenir. Geçerli mazereti bulunan öğrencilerin sınava katılmama
          gerekçesi ortak yazılı sınav uygulama tarihinden itibaren en geç 5 (beş) iş günü
          içerisinde velisi tarafından okul müdürlüğüne yazılı olarak bildirilir.
        </Mevzuat>
        <p>
          Mazeret belgesi sınavdan günler sonra gelebildiği için yoklama{" "}
          <strong>arşivlenmiş oturumda da güncellenebilir</strong>: oturumu arşive kaldırmış olmanız
          mazeret durumunu işlemenize engel değildir.
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Mazeret takibi ve mazeret sınavı
        </h3>
        <p>
          <Ekran to="/mazeret">Mazeret Takibi</Ekran> ekranı, dönemin bütün sınavlarında girmeyen
          öğrencileri sınav sınav tek listede toplar. Mazeret durumu ve belge notu burada da
          güncellenir. Sınav tarihinden itibaren 5 iş günü geçtiği hâlde kararı verilmemiş kayıt
          “süre geçti” diye işaretlenir. Süre hafta sonları düşülerek hesaplanır; resmî tatiller
          hesaba katılmaz. Bu işaret bir uyarıdır, mazereti kabul edip etmemek okul müdürlüğünün
          kararıdır.
        </p>
        <p>
          Mazereti kabul edilen (<em>Mazeretli</em>) öğrencileri işaretleyip{" "}
          <strong>“Mazeret sınavı oluştur”</strong> dersiniz. Farklı günlerin sınavları aynı mazeret
          sınavında toplanabilir; her ders ve sınıf düzeyi ayrı satır olur ve oturuma{" "}
          <strong>yalnız Mazeretli öğrenciler</strong> girer. Oturum taslak açılır. Salon seçimi,
          dağıtım, evrak ve yoklama normal oturumdaki gibidir; yalnız ders eklenmez, dersler ve
          öğrenciler bu ekrandan gelir. Bir öğrencinin durumu sonradan <em>Mazeretsiz</em> yapılırsa
          öğrenci mazeret sınavından kendiliğinden düşer. Oturum dağıtılmışsa program yeniden
          dağıtmanızı ister. Aynı öğrenci iki sınavın mazeretine aynı oturumda seçilemez, çünkü aynı
          anda iki sınava girilmez.
        </p>
        <Mevzuat kaynak="MEB Ortaöğretim Kurumları Yönetmeliği md. 48/1">
          Sınavlara katılmayan, performans çalışmasını yerine getirmeyen veya projesini zamanında
          teslim etmeyen öğrencilerden, özrünü 36 ncı maddenin yedinci fıkrasına göre
          belgelendirenlerin mazeret sınavı ilgili zümrenin belirleyeceği bir zamanda önceden
          duyurularak bir defaya mahsus yapılır.
        </Mevzuat>
        <p>
          Bu yüzden mazeret sınavına da girmeyen öğrenciye ikinci bir mazeret sınavı açılmaz.
          Ekrandaki <strong>Rapor (PDF)</strong> resmî antetli ve imzalı takip çizelgesidir. Dört
          bölümü vardır: (A) sınava girmeyen bütün öğrenciler; (B) e-Okul'a “G” işlenecekler; (C)
          mazeret sınavı bekleyenler; (D) ülke, il ve ilçe geneli sınavlarda il/ilçe millî eğitim
          müdürlüğüne bildirilecekler. <strong>Rapor (Excel)</strong> aynı bölümleri ayrı sayfalarda
          verir ve e-Okul'a işlerken çalışma kopyası olarak kullanılır. Ülke ve il geneli sınavların
          mazeret sınavı tarihi il millî eğitim müdürlüğünce ilan edilir; mazeret sınavının tarihini
          o ilana göre seçin.
        </p>
        <Mevzuat kaynak="MEB Yazılı ve Uygulamalı Sınavlar Yönergesi md. 5">
          Ülke, il ve ilçe geneli ortak yazılı sınavlara katılamayan öğrencilerden okul
          müdürlüklerince mazeret sınavına katılmasına karar verilen öğrenciler resmî yazı ile
          il/ilçe millî eğitim müdürlüklerine bildirilir.
        </Mevzuat>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Mazeret sınav takvimi
        </h3>
        <p>
          Son sınav yapılıp yoklamalar girildikten sonra mazeret sınavlarını tek tek açmak yerine{" "}
          <Ekran to="/mazeret?tab=takvim">Mazeret Takvimi</Ekran> sekmesinden bir takvim
          kurabilirsiniz. Bu takvimde <strong>yalnız mazeret sınavları</strong> yer alır; herkesin
          girdiği sınavlar görünmez. İlk günü, sınavların <strong>kaç güne sığacağını</strong>, bir
          öğrencinin <strong>bir günde en çok kaç sınava gireceğini</strong> ve kullanılacak ders
          saatlerini siz belirlersiniz. Program sınavları asıl sınav takvimindeki sırayla
          yerleştirir: önce yapılan sınavın mazereti de önce yapılır. Aynı öğrenci aynı saatte iki
          sınava konmaz; farklı öğrencilerin sınavları aynı saate düşerse tek mazeret oturumunda
          toplanır.
        </p>
        <p>
          Sığmayan sınav olursa program gerekçesini (hangi okul numarası için yer kalmadığını) ve bu
          kurallarla en az kaç gün gerektiğini söyler; gün sayısını artırabilir ya da “Asıl takvim
          sırasını kesin koru” seçeneğini kapatabilirsiniz — o zaman sınavlar boş saatlere öne
          çekilir, yalnız her öğrencinin kendi sırası korunur. Bir sınavı elle başka gün ve saate
          taşıyıp sabitleyebilirsiniz; aynı saatte başka sınavı olan öğrenci varsa taşıma
          reddedilir. Ülke, il ve ilçe geneli sınavların mazereti kendiliğinden yerleşmez: tarihini
          il/ilçe millî eğitim müdürlüğü ilan eder, ilan edilen gün ve saati elle girersiniz.
        </p>
        <p>
          Takvimi onayladıktan sonra <strong>“Oturumları oluştur”</strong> her sınav saati için
          mazeret oturumunu açar; salon, dağıtım ve evrak normal oturumdaki gibidir.{" "}
          <strong>“Takvim (PDF)”</strong> ilan nüshasıdır: öğrenci adı ya da numarası taşımaz,
          panoya asılabilir. <strong>“Öğrenci listesi (PDF)”</strong> hangi öğrencinin hangi sınava
          gireceğini gösterir; isterseniz adları gizleyip yalnız okul numarasıyla alırsınız. Takvim
          kurulduktan sonra mazereti kabul edilen öğrenci için <strong>“Kayıtları güncelle”</strong>{" "}
          düğmesi çıkar.
        </p>
      </Adim>

      <Adim no={10} icon="shield_lock" title="Bakım: yedek, parola ve güncelleme">
        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Yedek alma ve yedekten dönme
        </h3>
        <p>
          Program <strong>her gün ilk açılışta</strong> kendiliğinden bir günlük yedek alır (aynı
          gün ikinci açılışta sabahki yedeğin üzerine yazmaz) ve son 14 günün yedeğini saklar. Bunun
          dışında <Ekran to="/ayarlar?tab=guvenlik">Ayarlar → Güvenlik</Ekran> bölümünden
          istediğiniz an elle şifreli yedek (<span className="font-mono">.ksbak</span>)
          alabilirsiniz; elle yedek için uygulama parolasının kurulu olması gerekir.
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
          Program hiç açılmıyorsa (bozuk veritabanı) bu ekrana ulaşamazsınız. O durumda Windows’ta
          Başlat menüsündeki <strong>“Yedekten Geri Yükle”</strong> kısayolunu, Pardus/Linux’ta
          uçbirimden <span className="font-mono">kelebek-sinav --geri-yukle</span> komutunu
          kullanın. Araç yedekleri en yeniden eskiye listeler; şifreli yedek için uygulama
          parolanızı ya da kurtarma anahtarınızı sorar.
        </p>
        <Ipucu>
          Sınav dönemi başlamadan bir yedek alıp <strong>okul dışında</strong> saklayın. Program
          çevrimdışıdır; veriler yalnız bu bilgisayarda durur, bir bulut kopyası yoktur. Günlük
          yedekler de aynı bilgisayarda tutulur — disk giderse onlar da gider.
        </Ipucu>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">
          Uygulama parolası, kilit ekranı ve kurtarma anahtarı
        </h3>
        <p>
          Uygulama parolası isteğe bağlıdır.{" "}
          <Ekran to="/ayarlar?tab=guvenlik">Ayarlar → Güvenlik</Ekran> bölümündeki{" "}
          <strong>“Parola koy”</strong> ile kurduğunuzda öğrenci ve öğretmen ad-soyadları ile
          öğrenci fotoğrafları şifrelenir ve program her açılışta <strong>kilit ekranıyla</strong>{" "}
          başlar: parola girilmeden hiçbir kayıt görünmez. Bilgisayarın başından kalkarken{" "}
          <strong>“Şimdi kilitle”</strong> ile programı kapatmadan kilitleyebilir, aynı bölümden
          parolayı değiştirebilir ya da kaldırabilirsiniz. Bu koruma tam disk şifrelemesi değildir:
          okul numarası, sınıf/şube ve oturma düzeni şifrelenmez.
        </p>
        <p>
          Parolayı kurduğunuz anda program size bir <strong>kurtarma anahtarı</strong> gösterir. Bu
          anahtar <strong>yalnız bir kez</strong> gösterilir ve hiçbir yerde saklanmaz; pencere,
          yazdırdığınızı ya da kaydettiğinizi onaylamadan kapanmaz. Çıktıyı okul kasası gibi kilitli
          bir yerde tutun, bilgisayarın kendisinde saklamayın. Parolayı unutursanız kilit
          ekranındaki <strong>“Parolamı unuttum”</strong> bağlantısıyla kurtarma anahtarını girip
          yeni bir parola belirlersiniz. Hem parola hem kurtarma anahtarı kaybolursa şifreli
          ad-soyadlara ve şifreli yedeklere ulaşmanın yolu yoktur.
        </p>

        <h3 className="pt-1 text-title-small font-semibold text-on-surface">Programı güncelleme</h3>
        <p>
          Program açılışta — internet varsa — yayımlanan son sürümü sorar; yeni sürüm çıktıysa
          ekranın üstünde <strong>“Kelebek Sınav … hazır”</strong> afişi belirir. İstediğiniz an{" "}
          <Ekran to="/ayarlar?tab=guncelleme">Ayarlar → Güncelleme</Ekran> sekmesindeki{" "}
          <strong>“Şimdi denetle”</strong> ile de bakabilirsiniz. Programın internete çıkan{" "}
          <strong>tek isteği budur</strong>; kişisel veri taşımaz, internet yoksa sessizce atlanır.
        </p>
        <p>
          Windows’ta kurulum dosyası programın içinden indirilir ve bütünlüğü doğrulanmadan size
          sunulmaz: indirme bitince programı kapatıp indirilen kurulum dosyasını çalıştırın.
          Pardus/Linux’ta yeni paketi indirme sayfasından alıp kurarsınız. Verileriniz kurulum
          klasörünün dışında durduğu için güncellemede korunur; program ayrıca her sürüm
          güncellemesinden önce kendiliğinden bir yedek bırakır. Afişteki{" "}
          <strong>“Daha sonra”</strong> o sürümün afişini kapatır; güncellemeyi sonradan Ayarlar →
          Güncelleme sekmesinden yapabilirsiniz.
        </p>
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
