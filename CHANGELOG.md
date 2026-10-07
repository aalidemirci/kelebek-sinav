# Sürüm notları

Paketler GitHub Releases'ta ve indir.okulapp.org'dadır. En yeni sürüm en üsttedir;
yayımlanmamış değişiklikler "Yayımlanmadı (taslak)" başlığı altında toplanır ve
sürüm çıkarılırken bu başlık sürüm numarası ve tarihle değiştirilir.

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
