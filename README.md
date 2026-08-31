# Kelebek Sınav

Liseler için **tamamen çevrimdışı, tek kullanıcılı** kelebek sınav planlama
masaüstü uygulaması (Windows 10/11 + Pardus 21/23).

- Ortak sınav takvimini mevzuat pencerelerine göre planlar (öğrenci bazlı
  günlük sınav limiti denetimiyle),
- öğrencileri kelebek düzeniyle salonlara dağıtır (deterministik, seed'li,
  bağımsız doğrulayıcılı),
- tüm salon ve takvim evrakını A4 PDF olarak üretir: oturma planı, yoklama,
  evrak sayımı ve teslim zinciri **tek salon evrakında** birleşiktir (çift yüz
  basıldığında salon başına bir kâğıt); ayrıca şube duyurusu, ihlal tutanağı,
  görevlendirme yazısı ve kişiselleştirilmiş soru kitapçıkları,
- programın kendi içinde adım adım bir **kullanım kılavuzu** taşır (mevzuat
  dayanaklarıyla; çevrimdışı).

Veri kurumda kalır: tek yerel SQLite dosyası, telemetri yok. Tek dış istek,
GitHub'daki son sürümü soran anonim güncelleme denetimidir — kişisel veri
taşımaz, çevrimdışıyken sessizce atlanır. Öğrenci/öğretmen verisi e-Okul
raporlarından (xlsx/pano) içe aktarılır; ders havuzu MEB ders çizelgesinden
okul türü ve kademeye göre tohumlanır. Opsiyonel uygulama parolası ile alan
şifrelemesi ve şifreli yedek.

**Durum:** Sınav takvimi genişletildi (30.08.2026): takvim girdisine **sınavı
hazırlayan makam** eklendi (Okul / Bakanlık / İl MEM / İlçe MEM) — üst makam
sınavları ızgarada rozetle, PDF'te ayrı biçimde görünür ve aynı güne okul sınavı
konursa program uyarır; takvimin altına kullanıcı tarafından düzenlenebilir bir
**dipnot** basılır (varsayılanı mazeret sınavı takvimini ve kılavuz tarihlerini
söyler); imza bloğundaki **zümreler artık seçilebilir** — zümreler ve başkanları
Ayarlar → Zümreler ekranında personel listesinden tanımlanır. Ayrıca programa
adım adım **Kullanım Kılavuzu** sayfası eklendi.

Önceki durum: F9 (paketleme) tamamlandı — Windows setup.exe (WebView2 gömülü,
yönetici gerektirmez) + portable.zip ve Linux .deb + .tar.gz yerel olarak
üretildi; temiz debian:11/12 kaplarında kurulum → Türkçe PDF → `--autotest`
provaları ve Windows 11'de paketten gerçek pencere açılışı (kurulum sihirbazı)
doğrulandı. F9 denetimi zincirdeki bayat noktaları kapattı: Pardus 21
SQLite'ında (`serialize` yok) yedek çöküşü, işlevsiz Inno AppMutex, CI'da
`backend/**` değişikliklerinin paket kapısını tetiklememesi, VERSION↔etiket
kapısı, `.ksbak`/medya sızıntı taraması, `docs/kurulum.md`. Önceki fazlar:
bakım (F8), gözetmen (F7), takvim (F6), kitapçık (F5), evrak seti (F4),
oturum akışı (F3), salonlar + motor (F2). Kalan saha adımı: gerçek Pardus 21
masaüstünde pencere/Qt provası (packaging/README.md "doğrulanmamış" listesi).
F9 sonrası: e-Okul'un **Excel raporları artık değiştirilmeden** yükleniyor —
sınıf listesi (OOG01001R020) ve personel listesi (OOK01001R1) `.XLS` biçiminde
iner, şube blokları ve sayaç dipnotları otomatik çözülür; şube harfleri Türk
alfabesine göre ayrışır (`10/I` ile `10/İ` ayrı sınıflardır).
Plan: [docs/tasarim/2026-08-29-genel-tasarim.md](docs/tasarim/2026-08-29-genel-tasarim.md)

## Köken

İş mantığı [okulapp (OYS)](https://github.com/aalidemirci/okulapp)
`sinav_islemleri` + `ders_yapisi` modüllerinden, masaüstü/paketleme/arayüz
iskeleti disiplin-defteri-codex projesinden türetilir. Ayrıntı: tasarım
belgesi §11 (AYNEN/UYARLA/ALMA haritası).
