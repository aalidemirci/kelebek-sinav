# Sürüm notları

Paketler GitHub Releases'ta ve indir.okulapp.org'dadır. En yeni sürüm en üsttedir;
yayımlanmamış değişiklikler "Yayımlanmadı (taslak)" başlığı altında toplanır ve
sürüm çıkarılırken bu başlık sürüm numarası ve tarihle değiştirilir.

## Yayımlanmadı (taslak)

Bu sürüm veritabanında değişiklik yapar; güncelleme ilk açılışta kendiliğinden
uygulanır, yapmanız gereken bir işlem yoktur.

### Kelebek dağıtımı

- **Yeni seçenek: şube dağılımı.** Program bir şubenin aynı sınava giren
  öğrencilerini olabildiğince az salonda toplar; bu bilinçli bir tercihtir
  (kâğıtlar şube şube kolay ayrılır, tekrarlanan sınavlarda bütün sınıf düzeyi
  birbirine karışmaz). Şubelerin salonlarda olabildiğince karışmasını isteyen
  okullar için Ayarlar → Okul Bilgileri'ne **"Şube dağılımı"** seçeneği eklendi:
  **Şubeler salonlara dağıtılır** seçildiğinde her şubenin öğrencileri oturumdaki
  bütün salonlara paylaştırılır. Varsayılan **Şubeler bir arada**dır; ayarı
  değiştirmeyen okulda dağıtım eskisiyle birebir aynıdır.
- Yeni açılan oturumlar okulun seçimiyle gelir; tek bir sınav için sihirbazın
  1. adımındaki "Ayrıntılı ayarlar"dan değiştirilebilir (dağıtılmış oturumda önce
  taslağa alınır). Kelebek kuralı, salon doluluk dengesi ve "aynı dağıtım numarası
  aynı yerleşimi verir" kuralı iki seçimde de aynıdır. "Kendi dersliğinde"
  düzeninde seçenek yoktur.
- Dağıtım doğrulama raporu hangi seçimle dağıtıldığını yazar ("Şube dağılımı").
- Kız/erkek ayrışmasında "Ayrı salonlar" seçiliyken, sıra yetmediğini söyleyen
  uyarı dersin adı yerine programın iç kodunu ("12:10" gibi) gösteriyordu;
  artık dersin adını yazar.

## 2026.10.0-beta.4 — 24.10.2026

Bu sürüm veritabanında değişiklik yapmaz; güncellemeden sonra yapmanız gereken
bir işlem yoktur.

### Dağıtım doğrulama raporu

- **Kural ihlali olmayan oturumda "kaçınılmaz oldu" uyarısı artık çıkmaz.**
  Program dağıtım sırasında bir öğrenciyi geçici olarak aynı sınava giren
  biriyle aynı sıraya koyup sonra başka bir sıraya alsa da uyarı listede
  kalıyor, dağıtım doğrulama raporuna "KURAL İHLALİ YOKTUR" ile yan yana
  basılıyordu. Uyarılar artık öğrencilerin son oturduğu yerlerden üretilir:
  yalnız gerçekten aynı sıraya düşen öğrenciler için ve sıra başına bir kez
  yazılır.
- Oturma düzeni değişmez: aynı dağıtım numarası yine aynı yerleşimi verir.
  Bu sürümden önce dağıtılmış bir oturumun raporu eski uyarıları taşımaya
  devam eder; temiz rapor isterseniz oturumu Yerleşim sekmesinde yazan
  dağıtım numarasıyla yeniden dağıtın. Yeniden dağıtımda elle yapılan koltuk
  değişiklikleri ve gözetmen görevlendirmeleri yeniden yapılır.

## 2026.10.0-beta.3 — 23.10.2026

Bu sürüm veritabanında değişiklik yapar; güncelleme ilk açılışta kendiliğinden
uygulanır, yapmanız gereken bir işlem yoktur.

### Ortak Yazılı Sınav Sistemi (OYSS)

- **OYSS uygulama takvimi programda.** 2026-2027 1. dönem 1. yazılıda lisede 9, 10 ve 11.
  sınıfların on dersi (Biyoloji, Kimya, Tarih, Matematik, Fizik, Felsefe, Coğrafya, Türk
  Dili ve Edebiyatı, Din Kültürü ve Ahlak Bilgisi, İngilizce) takvim oluşturulurken resmî
  gününe ve ders saatine yerleşir: günde tek sınav 2., iki sınav 2. ve 4. ders saati,
  10 Kasım'da 4. ders saati. Sınavlar okul sınavı olarak kalır; okul müdürlüğü gerekirse
  saati Yerleştirme sekmesinde değiştirir.
- **Bakanlık bandı OYSS sınavlarını da gösterir.** Takvim sayfasındaki bant her sınavın
  gününü, ders saatini ve takvimdeki durumunu söyler; daha önce oluşturulmuş taslak
  takvimde "Takvime uygula" ülke geneli ve OYSS sınavlarını birlikte uygular.
- **Ders adları eşleştirilir.** İngilizce sınavı birinci yabancı dil dersine, 11.
  sınıfta seçmeli okutulan Matematik, Fizik, Kimya, Biyoloji ve Coğrafya seçmeli derse
  bağlanır. 7. ve 11. sınıf İngilizce OYSS dışındadır; 10. sınıf Türk Dili ve Edebiyatı
  bu turda ülke geneli sınavdır (12 Kasım).
- **OYSS sınavı başka güne konursa takvim doğrulaması uyarır.** Mazeret haftası (23-27
  Kasım 2026) bantta yazar.
- **OYSS soru kâğıdına öğrenci bilgisi basılır.** EBA'dan indirilen OYSS soru kâğıdı
  olduğu gibi yüklenir; program kâğıdı tanır ve Bakanlığın başlığını örten bant yerine
  öğrencinin adını, sınıfını/şubesini ve numarasını 1. sayfadaki kendi alanlarına basar.
  A4'e çift yüzlü basımda yapraklar karışmasın diye 3. sayfanın (varsa 5. sayfanın)
  üstüne de aynı bilgilerle bir kimlik satırı eklenir. Kâğıdın kendi sayfa numarası
  korunur; isimsiz yedeklerde alanlar boş kalır. Sorular panelinde dosya "OYSS soru
  kâğıdı" olarak görünür.

### Sınav tedbirlerinin dayanağı

- **İdare özetinin dayanağına Özel Eğitim Hizmetleri Yönetmeliği eklendi.** Tedbirlerin
  yönetmelikteki karşılığı md. 24/1'dir: tüm ölçme ve değerlendirme süreçlerinde "süre,
  ortam, yöntem, cihaz ve materyallerde düzenlemeler yapılarak gerekli tedbirler alınır".
- **Kılavuz tedbirlerin dayanağını anlatır.** "Kalıcı sınav tedbirleri" başlığında bu
  maddenin alıntısı ve kararı kimin verdiği yer alır: tedbir BEP'in parçasıdır, BEP'i ve
  sınavda refakat gereken öğrencileri okulun BEP geliştirme birimi belirler; program
  kararı kaydeder. BEP başlığındaki dayanak satırı idare özetininkiyle yeniden aynıdır;
  "Dayanak metinler" kartı alıntı yapılan dört metni sayar.

## 2026.10.0-beta.2 — 07.10.2026

Bu sürüm veritabanında değişiklik yapar; güncelleme ilk açılışta kendiliğinden
uygulanır, yapmanız gereken bir işlem yoktur.

### Şubesi değişen ve nakil gelen öğrenciler

- **Öğrencinin şubesi değişince seçmeli ders listeleri de toparlanır.** Zorunlu
  dersler ve şubenin tamamının aldığı seçmeliler zaten yeni şubeye geçiyordu;
  artık eski şubenin öğrenci listelerinden de çıkar.
- **Bölünerek okutulan seçmelide seçim sorulur.** Yeni şube bir seçmeliyi
  bölünerek okutuyorsa (dersi şubenin yalnız bir kısmı alıyorsa) öğrenci
  "seçmeli ders seçimi bekliyor" olur; nakil gelen öğrenci de öyle. Ders Havuzu
  ve Kişiler ekranlarında bant çıkar, **Seçimleri yap** penceresinden öğrencinin
  aldığı dersler işaretlenir (eski şubesinde aldığı ders işaretli gelir). Eskiden
  öğrenci bu derslerin sınavından sessizce düşüyordu.
- Seçim yapılana kadar o şubenin bölünmüş dersini içeren sınav oturumu
  dağıtılamaz; sihirbaz nedenini söyler ve pencereye bağlantı verir.
- Öğrenci aktarımının önizlemesi kaç öğrencinin seçim bekleyeceğini aktarmadan
  önce söyler. e-Okul seçmeli raporu yeniden aktarılınca raporda geçen
  öğrencilerin seçimi kendiliğinden kapanır.
- Okuldan ayrılan ya da sicilden silinen öğrencinin seçmeli ders kayıtları
  silinir (fotoğraf ve BEP kaydı gibi). Güncellemeden önce şube değiştirmiş ya da
  ayrılmış öğrencilerin eski kayıtları ilk açılışta bir kez toparlanır.

### Kalıcı sınav tedbirleri

- Kişiler ekranındaki **BEP** sekmesi **BEP ve tedbirler** oldu. Öğrenciye bir
  kez tedbir girilir, bütün sınav oturumlarında geçerli olur: **kendi sınıfında**,
  **ayrı salon** ya da **ön sırada** sınava girme (istenirse salon içinde ön/arka
  sıra ve sırada tek başına), **ek süre** (dakika), **okuyucu desteği**, **yazıcı
  desteği**. Gerekçe yalnız kategoridir (BEP, engel durumu, sağlık, diğer); tanı
  ya da rapor kaydedilmez.
- Öğrenci adıyla ya da okul numarasıyla eklenir; birden çok öğrenci için okul
  numaraları yazılarak toplu eklenebilir.
- Yer tedbiri dağıtımda yerleştirme kuralı gibi uygulanır; o oturumda öğrenciye
  kural eklenirse kural geçerli olur. Oturumun Yerleştirme Kuralları sekmesinde
  sınava giren tedbirli öğrenciler görünür. Tedbir oturum dağıtıldıktan sonra
  girildiyse orada ve idare özetinde "yer tedbiri bu dağıtımda uygulanmadı —
  oturumu yeniden dağıtın" yazar.
- Ek süre ile okuyucu ve yazıcı desteği salon evrakına, yoklama listesine ve
  kitapçığa basılmaz; yalnız oturumun **idare özetinde** (BEP özetiyle birlikte)
  görünür. Görevli öğretmeni program atamaz.
- Dağıtım, okuyucu ya da yazıcı desteği alan öğrenci ayrı salonda değilse ya da
  aynı ayrı salonda iki destekli öğrenci varsa uyarır. Ek süreli öğrencinin iki
  sınavı arasında süre kalmazsa (aynı gün çakışan oturumlar, takvimde ardışık iki
  ders saati) uyarılırsınız; uyarılar öğrencinin adını ya da numarasını söylemez.

## 2026.10.0-beta.1 — 02.10.2026

Bu sürüm veritabanında değişiklik yapmaz; güncellemeden sonra yapmanız gereken
bir işlem yoktur.

### Sınav takvimi

- **Takvim PDF'i tek A4 sayfaya sığar.** Program sayfa yönünü (yatay ya da
  dikey) ve yazı büyüklüğünü takvimin içeriğine göre kendisi seçer; tipik bir
  lisenin eskiden üç sayfa tutan takvimi artık tek sayfadır. Çok uzun bir takvim
  ikinci sayfaya geçer; bir günün sınavları iki sayfaya bölünmez.
- Tablo yenilendi: tarih (gg.aa.yyyy), gün ve ders saati ayrı sütunlarda; bir
  günün ders saatleri tek tarih hücresinde toplanır. Açıklamalar iki sütunda,
  dipnot açıklamaların sonunda basılır.
- **İmza bölümü:** takvim için zümre seçilmemişse Ayarlar → Zümreler'de
  "Kurulda" işaretli zümrelerin tamamı basılır. Eskiden her ders için ayrı ve
  boş bir imza yeri basılıyordu. Hiç zümre tanımlı değilse yalnız düzenleyen
  müdür yardımcısı ile okul müdürü imzalar.
- Takvim tarih aralığının dışında kalan bir sınav PDF'ten artık düşmez, kendi
  tarihiyle basılır; doğrulama uyarısı dersin ve sınıf düzeyinin adını söyler.
- PDF hazırlanırken düğme "Hazırlanıyor…" yazar.

### Mazeret belgeleri

- Mazeret sınav takvimi, sınav takvimiyle aynı tablo düzenine geçti; ders saati
  ("2. Ders · 09:20") artık tek satırdır. İmzalar "Kurulda" işaretli
  zümrelerden gelir.
- Mazeret takip çizelgesinde bölüm başlığı, tablosundan ayrı bir sayfada
  kalmaz.

### Bütün belgeler

- İmza alanları bütün belgelerde aynı biçimdedir: adı bilinmeyen imza yerinde
  görev ve altında "Ad Soyad / İmza" yazar; "UYGUNDUR" her belgede aynı
  biçimde basılır (dağıtım doğrulama raporunda da).
- Salon sınav evrakında ve ihlal tutanağında atanmış gözetmenin, gözetmen
  görevlendirme belgesinde ve dağıtım doğrulama raporunda okul müdürünün adı
  imza çizgisinin altına basılır.
- Gözetmen görevlendirme ve tebliğ-tebellüğ belgesi resmî antetle basılır.
- Takvim ve mazeret belgelerinin sol altında düzenleme tarihi ve saati yer
  alır; tablo başlıkları öteki evrakla aynı renktedir.
- "T.C.", "UYGUNDUR", "TEBLİĞ EDEN" gibi başlıklar PDF içinde aranabilir.
- Şube sınav duyurusunun dayanak satırı tek satırdır; dağıtım doğrulama
  raporundaki ölçüler tek ondalıkla basılır.

## 2026.9.0-beta.13 — 24.09.2026

### Güvenlik

Bu sürüme geçmeniz önerilir. Aşağıdaki düzeltmeler programın çalıştığı
bilgisayardaki yerel dosyalarla ilgilidir; ağ üzerinden erişim gerektirmez ve
mevcut şifreli kayıtlarınızı etkilemez. Güncellemeden sonra yapmanız gereken bir
işlem yoktur.

- **Güvenlik dosyası kilidi güçlendirildi.** Uygulama parolası kuruluyken
  veri klasöründeki güvenlik dosyası (`guvenlik.json`) bulunamaz ya da
  okunamazsa program artık "Güvenlik dosyası bulunamadı ya da okunamıyor"
  ekranını açar ve yeni parola kurulmasına izin vermez. Ekran iki çıkış yolu
  gösterir: dosyanın sağlam kopyasını geri koymak ya da bir yedeği geri
  yüklemek (her şifreli yedek güvenlik dosyasını da içinde taşır).
- **Şifreli alanların korunması güçlendirildi.** Uygulama parolası kuruluyken
  kilit açılmadan kişisel veri alanlarına yazılamaz. Parolasız kullanım
  değişmedi.
- **Parola kurulurken eski kayıt kalıntıları temizlenir.** Kayıtlar
  şifrelendikten sonra veritabanı dosyası yeniden düzenlenir; şifrelemeden
  önceki sürümler dosyada kalmaz.
- **Kurtarma anahtarı yenilenebilir (görev devri).** Ayarlar → Güvenlik'teki
  "Kurtarma anahtarını yenile" ile, uygulama parolanızı girerek yeni bir
  kurtarma anahtarı üretebilirsiniz; eski anahtar bu bilgisayardaki kayıtların
  kilidini artık açmaz. Parolayı değiştirmek kurtarma anahtarını
  değiştirmez — kurtarma anahtarını elinde tutan kişi görevden ayrıldıysa bu
  işlemi ayrıca yapın. Yenilemeden önce alınmış yedekler eski anahtarla
  açılmaya devam eder; ekran ve kılavuz bunu ayrıntılı anlatır.

### Yedekleme

- Güvenlik dosyası kullanılamadığı gün otomatik yedek alınmaz ve eski yedekler
  silinmez; açılamayacak bir yedek üretmek yerine sağlam eski yedekler korunur.
- Oturum sürerken program kilitlenirse ya da güvenlik dosyası kaybolursa ekran
  hemen ilgili sayfaya (kilit ya da güvenlik dosyası) geçer.

### Belgeler

- Kılavuz ve kurulum belgesine görev devri ve güvenlik dosyası bölümleri
  eklendi.
- Örnek verilerdeki ilçe adı tarafsız bir örnekle değiştirildi.
