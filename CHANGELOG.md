# Sürüm notları

Paketler GitHub Releases'ta ve indir.okulapp.org'dadır. En yeni sürüm en üsttedir;
yayımlanmamış değişiklikler "Yayımlanmadı (taslak)" başlığı altında toplanır ve
sürüm çıkarılırken bu başlık sürüm numarası ve tarihle değiştirilir.

## Yayımlanmadı (taslak)

Bu sürüm veritabanında değişiklik yapar; güncelleme ilk açılışta kendiliğinden
uygulanır, yapmanız gereken bir işlem yoktur.

### Oturum onayı

- **Kural ihlali olan yerleşim de onaylanabiliyor.** Sınıf düzeyleri ya da
  derslerin öğrenci sayıları karışmaya elverişli olmadığında aynı sınava giren
  öğrencilerin yan yana düşmesi kaçınılmaz olabiliyor; program bu durumda oturumu
  hiç onaylatmıyordu. Artık onay penceresi ihlalleri listeler ve **"İhlalleri gördüm;
  oturumu bu hâliyle onaylıyorum"** kutusu işaretlenince onay verilir. İhlal sayısı
  onay kaydına geçer, oturum başlığında "N kural ihlaliyle onaylandı" rozeti görünür
  ve Dağıtım Doğrulama Raporu oturumun bu ihlallerle, idarenin kararıyla onaylandığını
  yazar. Onayı geri almak kaydı siler.
- **Dağıtım Doğrulama Raporu ihlalleri iki kez basmıyor.** Aynı ihlaller "Dağıtım
  uyarıları" bölümünde "kural ihlali değildir" başlığı altında bir kez daha yazılıyor,
  rapor gereksiz yere uzuyordu. Artık ihlaller yalnız üstteki listede görünür.
- **Kabulle de onaylanamayan durumlar.** Kız/erkek ayrışması ihlali (kural açıkken),
  bozuk yerleşim kaydı (aynı koltukta iki öğrenci, salon planı dağıtımdan sonra
  değişmiş) ve dağıtımdan sonra eklendiği için koltuğu olmayan öğrenci onayı
  engeller. Sonuncusu yenidir: eskiden ihlal yoksa yerleşimde olmayan öğrenciyle de
  onay verilebiliyordu, şimdi önce yeniden dağıtmanız istenir (yoklaması alınmış
  oturum hariç — onun yerleşimi sınavın kaydıdır).

### Kelebek dağıtımı

- **Önemli: aynı dağıtım numarası artık eski sürümden farklı plan verir.** Dağıtım yöntemi
  değişti. Daha önce yapılmış dağıtımlar, basılmış evrak ve onaylı oturumlar kayıtlı olduğu için
  etkilenmez; ama eski bir numarayı bu sürümde yeniden girerseniz başka bir yerleşim çıkar. Dağıtım
  Doğrulama Raporu artık "Dağıtım yöntemi sürümü" satırını basar: aynı numara, aynı sürümde ve aynı
  girdilerle aynı yerleşimi verir. Öğrencilerin başka sınavlardaki son yerleri de girdidir.
- **Kız/erkek "Aynı sıraya oturtma" kuralı artık sağlanabiliyor.** Program bu kuralda kurulabilecek
  planları çoğu kez bulamıyor, oturum onaylanamıyordu. Sentetik denemelerde, mümkün olan her durumda
  onaylanabilir plan çıktı. Bedeli, kimi salonda aynı sınavdan yan yana düşen öğrencinin artabilmesidir:
  kız/erkek ihlali kabulle geçilmediği için önce o sağlanır, öteki ihlali onay penceresinde görürsünüz.
- **Üçlü sıralı salonlarda aynı sıraya düşen aynı sınav öğrencisi azaldı.**
- **Tam dolu salonda önceden uyarı.** "Aynı sıraya oturtma" seçiliyken bütün sıralar ikiliyse, her koltuk
  doluyorsa, cinsiyeti bilinmeyen öğrenci yoksa ve kız ve erkek sayısı tek düşüyorsa bir sıra karışık
  kalmak zorundadır; bu durumda hiçbir dağıtım sıraları ayıramaz. Tekli sıra ya da cinsiyeti bilinmeyen
  öğrenci varsa bu zorunluluk kalkabilir. Sihirbazın salon adımı bunları hesaba katar, sıralar yetmiyorsa
  dağıtımdan önce kaç sıra eksik olduğunu söyler. Kız ve erkek sayısı yazılmaz.
- **Numara değişince plan gerçekten değişiyor.** İki sınavlı tam dolu salonda her numara herkesi aynı
  koltuğa oturtuyordu. Artık öğrencinin yeri numaraya bağlıdır, okul numarası sırası korunmaz; şube
  sayımı aynıdır. Derslerin ve salonların seçilme sırası planı değiştirmez.
- **Yeni seçenek: yakınlık önceliği.** Ayarlar → Okul Bilgileri ve sihirbazın Dağıt adımında "Bütün
  komşu sıralar" (varsayılan) ya da "En yakın komşular öncelikli". "Bütün komşu sıralar" seçiliyken
  bu seçeneğin plana etkisi yoktur; yukarıdaki numara değişikliği iki seçimde de geçerlidir. "En yakın
  komşular öncelikli"nin bedeli vardır, kazancı salona göre değişir; Kılavuz ayrıntısını yazar. Katı dağıtımda ve "Kendi
  dersliğinde" düzeninde uygulanmaz.
- **Salonlarda sınav çeşidi.** Yerleşim sekmesi her salon için sınav sayısını ve önünde aynı sınav olan
  öğrenci oranını gösterir; sihirbazın salon adımında sınav çeşidinin mesafeye etkisi kısaca yazar.
  Bu bilgi yalnız ekrandadır, evraka basılmaz.
- **Kaçınılmaz çiftler masaya çekilmiyor.** Kılavuzdaki eski cümle düzeltildi: öğretmen masasına
  uzaklık yalnız iki yerleşim başka her bakımdan denkse birini seçtirir.
- **"Kaçınılmaz oldu" uyarısının metni değişti.** Aynı sırada çakışma kalınca dağıtım uyarısı artık
  "bu dağıtımda önlenemedi" der: çakışmanın nedeni her zaman sıra yetersizliği değildir.

### Dağıtım Doğrulama Raporu

- **Kız/erkek ihlali satırı yalnız kuralın adını ve yeri yazar;** öğrencinin numarası ve cinsiyeti
  yazmaz. Cinsiyeti bilinmeyen öğrenci sayısı rapordan çıktı, oturumun Yerleşim sekmesinde görünür.
- Rapor "Dağıtım yöntemi sürümü" ve "Yakınlık önceliği" satırlarını basar; aynı numara ipucu yukarıdaki
  kurala göre yenilendi. "Katı dağıtım" satırı çapraz komşuluğu da söyler.

### Öğrenci listesi

- **Öğrenci listesi cinsiyet bilgisini taşımıyor.** Liste ekranı bu bilgiyi zaten göstermiyordu; artık
  program arka planda da listeyle göndermiyor. Cinsiyet yalnız öğrencinin kartı açılınca okunur. Kart
  bilgiyi okuyamazsa bunu yazar ve kaydetmek alanı değiştirmez.

### Kılavuz

- **"Program yerleşimde neyi gözetir?"** Programın neyi gözettiği ve gözetmediği, dağıtım numarasının
  işleyişi, "Şubeler bir arada" seçiminde en yakın komşuların çoğunun aynı şubeden olduğu ve bu
  bilgilerin dayanağı yazıldı. Oranlar sentetik veriyle ölçülmüş oturma düzenidir; kopya ölçülmedi.

## 2026.10.0-beta.7 — 29.10.2026

Bu sürüm veritabanında değişiklik yapmaz; güncellemeden sonra yapmanız gereken
bir işlem yoktur.

### Sınav evrakı

- **Şube sınav duyurusu tek sayfada kalıyor.** Şubenin öğrencileri çok sayıda
  salona dağıldığında üstteki "şube aşağıdaki salonlara dağıtılmıştır" satırı
  birkaç satıra uzuyor ve duyurunun imza satırı ikinci sayfaya taşıyordu. Öğrenci
  listesi artık bu satırın uzunluğuna göre sıklaşır; duyuru tek sayfa kalır.
- **İhlal ve kopya tutanağı salon başına tek yaprak.** Salonda dört-altı ayrı sınav
  (örneğin aynı dersin birkaç sınıf düzeyi) olduğunda "Sınavı yapılan ders(ler)"
  listesi dar bir hücrede sarıyor, tutanak ikinci yaprağa taşıyordu. Liste artık
  kendi satırında, tam genişlikte; aynı dersin sınıf düzeyleri tek başlıkta toplanır
  ("Matematik — 9. Sınıf (7), 10. Sınıf (5)"), çok uzun listede yazı küçülür.

## 2026.10.0-beta.6 — 25.10.2026

Bu sürüm veritabanında değişiklik yapmaz; güncellemeden sonra yapmanız gereken
bir işlem yoktur.

### Salon sınav evrakı ve tutanak

- **Teslim zincirine son halka eklendi.** Salon evrakının "Evrak teslim zinciri"
  bölümünde yeni bir satır var: "Nöbetçi müdür yrd. — evrakı zümreden teslim
  alan". Zümre temsilcisi salonlardan topladığı sınav evrakını nöbetçi müdür
  yardımcısına teslim eder; saat ve imza bu satıra yazılır.
- **İhlal ve kopya tutanağı:** "Tutanak, öğrencinin sınav kâğıdıyla birlikte nöbetçi
  müdür yardımcısına teslim edildi." Eskiden "sınav evrakıyla birlikte" yazıyordu;
  salonun sınav evrakı ise zümre temsilcisine teslim edilir.

### Kılavuz

- **"Salon tam dolmadığında boş koltuklar neden önde kalır?"** Program boş kalan
  koltukları aynı sınava giren öğrencileri ayıran tampon olarak kullanır; bu yüzden
  boşluklar çoğunlukla ön ve orta sıralarda toplanır. Bölüm bunun nedenini ve
  boşluklar arkaya toplansaydı komşu sıralardaki aynı sınav çiftinin ne kadar
  artacağını anlatır.

## 2026.10.0-beta.5 — 25.10.2026

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

### Salon sınav evrakı

- **Gözetmen işlemleri listesi teslim akışını doğru anlatır.** "Sınav sonunda"
  sütunundaki "Evrak ve tutanaklar müdür yardımcısına teslim edildi" maddesi,
  aynı yaprağın imza bloğuyla çelişiyordu: sınav evrakı sayılarak zümre
  temsilcisine teslim edilir, nöbetçi müdür yardımcısına yalnız yoklama ve
  tutanaklar verilir. Maddeler artık "Evrak, zümre temsilcisiyle sayılıp ona
  teslim edildi." ve "Yoklama ve tutanaklar nöbetçi müdür yardımcısına verildi."
  biçimindedir.
- **"Sınav öncesi" sütununa yeni madde:** "Raporlu veya izinli öğrenci sınava
  alınmadı." (Ortaöğretim Kurumları Yönetmeliği md. 48/5). Evrak yine çift yüz
  basıldığında salon başına tek kâğıttır.

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
