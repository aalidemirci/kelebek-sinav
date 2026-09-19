# Teknik borç kütüğü

Buraya giren her kalem **biliniyor ve kabul edilmiş** demektir; denetimlerde
yeniden raporlanmaz (gerekçenin kendisi çürütülmedikçe).

## Açık

- **TB1 — e-Okul PDF parser'ları yok (v1 kararı, B18):** raporların **PDF**
  çıktıları içe aktarılamaz; yol e-Okul'un **Excel** ihracı (.xls) + uygulama
  şablonu (.xlsx) + pano. Gerekçe: pypdf glif/bitişme riskleri OYS kodunda
  belgeli. Pratik etkisi 30.08.2026'da küçüldü: OOG01001R020 (Sınıf/Şube
  Öğrenci Listesi) ve OOK01001R1 (Personel Listesi) Excel ihraçları artık
  **değiştirilmeden** yükleniyor (bkz. `apps/okul/eokul.py`), yani PDF yolu
  yalnız Excel düğmesi olmayan raporlar için gerekir. v2 adayı. **Tek istisna
  (19.09.2026):** OOK10002R010 Seçmeli Ders Öğrencileri PDF'ten okunur
  (`apps/dersler/enrollment_import.py`) — Excel ihracı ders adı bantlarını
  düşürdüğü için başka yol yok. Satırdan yalnız okul no + sınıf/şube alınır (ad
  ayrıştırılmaz); gerçek raporda 25 ders / 8.385 satır Excel ihracıyla birebir
  ölçüldü (tasarım §6). Yeni bir e-Okul sürümü başlık biçimini değiştirirse
  belirti "hiç ders başlığı bulunamadı" reddidir, sessiz eksik aktarım değil.
- **TB2 — Çizelge verisi boşlukları (U4, 03.09.2026'da daraldı):** sekiz
  ortaöğretim türünün TTK çizelgeleri gömülü (tasarım §7.2). Kalanlar:
  (a) GSL 2025 çizelgeleri ortak dersleri kademeli uygular; 2026-2027'de
  12. sınıfın tabi olduğu önceki nesil (TTK 2023/41, 2024/46) aktarılmadı
  — program en yeni çizelgeyi yedek kullanır ve ders havuzu ekranında uyarır;
  2027-2028'de kendiliğinden kapanır. Spor Lisesi'nde aynı boşluk 19.09.2026'da
  KAPANDI: TTK 02.09.2026/102-103 (yeni nesil dosyalar `spor-lisesi-2026`,
  `spor-lisesi-tematik-2026`) 2026-2027'den itibaren tüm sınıf seviyelerine
  girer, 2025/9-10 kalkar; Spor'un önceki nesli (2023/42, 2024/47, tematik
  2024/48) yalnız GEÇMİŞ 2025-2026 yılının 11-12. sınıfları için eksiktir.
  (b) MTAL seçmeli dersler tablosu (TTK
  2026/62, 2024/41 eki) ve hazırlıklı MTAL çizelgesi (2024/42, 2026/63) resmî
  PDF'te taranmış görüntü — OCR ya da elle aktarım bekliyor; MTAL alan/dal
  meslek dersleri (56 alan) katalogla taşınmaz, okul elle ekler. (c) Özel
  Program Uygulayan Fen/SBL (2025/24-25; SBL nüshası "TASLAK") ve Özel Program
  Uygulayan Hazırlık Sınıfı Bulunan Anadolu Lisesi (TTK 02.09.2026/104 —
  2026-2027'den itibaren hazırlık sınıfından başlayarak kademeli; yalnız proje
  protokolü kapsamındaki okullar, Açıklamalar md. 1). Sonuncusu aktarılacaksa
  ÖNCE `CatalogProgram.covers` düzeltilir: `kademeli_ilk_seviyeler`de 9 ve üstü
  yokken tavan 9 sayılıyor, "yalnız hazırlıktan başlar" ifade edilemiyor
  (ayrıntı `data/ders-cizelgeleri/README.md` "Aktarılmayanlar"). Yeni dosya
  eklerken **"Sınav" sütunu** kürasyonu şart (K19, tasarım §7.1).
- **TB3 — Şifreli kipte ad-temelli DB sorgusu yok (U3 bedeli):** arama/
  sıralama/teklik selector katmanında Python ile; yeni ad sorgusu ORM
  filtresiyle yazılamaz (DD F5-D5 dersi).
- **TB4 — Gözetmen oto-atama yok (U2):** ders programı verisi olmadığından
  elle seçim; OYS'deki adil-yük sayacı alınmadı.
- **TB6 — Logo v1 geometrik yer tutucu:** `logo_uret.py` koltuk-karesi
  kelebeği üretiyor; markalaşmış bir çizim istenirse `kelebek-sinav-logo.png`
  değiştirilip `ikon_uret.py` yeniden koşulur (sözleşme hazır).
- **TB11 — Yedek medya dosyalarını kapsamaz (K3 kararı, 18.09.2026):** `.ksbak`
  yalnız veritabanıdır; soru PDF'leri ve üretilmiş kitapçık ZIP'leri yedeğe
  GİRMEZ. Gerekçe: soru dosyası sınavdan sonra tarihsel değer taşımaz, yedeği
  büyütür ve taşınan her kopya gizlilik yüküdür. Bedeli: geri yüklenen ya da
  başka makineye taşınan kurulumda eski oturumların soru dosyası/kitapçık
  indirmesi çalışmaz — indirme uçları bu durumda Türkçe `media_missing` 404
  döner (500 değil) ve idareci dosyayı yeniden yükler. Evrak PDF'leri (R1-R8,
  takvim) etkilenmez: her istekte veritabanından yeniden üretilir.
- **TB12 — `sinav/services.py` tek dosya (≈2.800 satır, 18.09.2026
  değerlendirmesi A10):** oturum yaşam döngüsü, soru dosyası, yoklama, gözetmen
  ve evrak bağlamı aynı modülde. Bölme (services/ paketi, takvim emsali
  `services_calendar.py`) davranış değiştirmeyen saf taşıma işidir; AYNEN
  sınıfındaki imzalar korunarak ayrı bir oturumda yapılmalı — düzeltme
  turlarıyla karıştırılırsa `git blame` izini ve incelemeyi zorlaştırır.

- **TB13 — Linux derleme tabanı Debian 11 destek dışı (19.09.2026):** `.deb`
  Pardus 21 uyumu için `python:3.12-bullseye` kabında derlenir ve `debian:11`'de
  sınanır; Debian 11 LTS 31.08.2026'da bitti. Güvenlik deposu boşaltıldığı için
  kaynak tarihli arşive sabitlendi (`packaging/README.md` "Debian 11 güvenlik
  deposu…"). Sıradaki kırılma: `deb.debian.org/debian bullseye` ANA deposu da
  arşive (`archive.debian.org`) taşınacak — o gün `bullseye` ve
  `bullseye-updates` satırları için de aynı sabitleme gerekir; belirtisi yine
  derleme kabında 404'tür. Kalıcı çözüm Pardus 21 desteğinin ne zaman
  bırakılacağı kararıdır (taban bookworm'a çıkarsa glibc yükselir, Pardus 21'de
  paket açılmaz) — karar kullanıcıdadır, saha kurulumlarına bakılarak verilir.

- **TB14 — Öğrenci fotoğrafı yalnız Excel'den (19.09.2026, tasarım §6):**
  e-Okul OOG01001R080 raporunun PDF'i okunmaz; fotoğraf ile okul no'nun bağı
  PDF'te yalnız sayfa konumundan kurulabilirdi. Excel ayrıştırması e-Okul'un
  bugünkü dizgisine dayanır: okul no, fotoğraf çapasının ALTINDAKİ hücrenin
  sonundaki sayıdır. e-Okul dizgiyi değiştirirse belirti sessiz eksik aktarım
  DEĞİLDİR — önizleme "Fotoğrafın altında okul numarası bulunamadı" satırlarını
  Excel konumuyla listeler ve eşleşme sayısı düşer. İkinci bilinçli bedel: fotoğrafın snapshot'ı
  yok (KVKK); ayrılan öğrencinin fotoğrafı silindiği için arşiv oturumunun
  salon evrakı yeniden basılırsa o kartta "fotoğraf yok" kutusu çıkar.

- **TB15 — PDF motoru uygulamayla aynı süreçte (19.09.2026):** WeasyPrint'in C
  katmanındaki (Pango, fontconfig) bir çöküş pencereyle birlikte bütün programı
  kapatır. Bilinen nedeni — eşzamanlı basım — `shared.pdf` kilidiyle kapandı;
  başka bir yerel hata yine programı kapatabilir. İzleme: `logs/cokme.log`.
  Kayıt yeni çöküş gösterirse sıradaki adım PDF üretimini ayrı bir alt süreçte
  koşmaktır (çöküş yalnız o isteği düşürür, pencere açık kalır); paketleme ve
  süreç haberleşmesi gerektirdiği için kullanıcı kararıyla ertelendi. Yan bulgu:
  Windows paketinde fontconfig önbelleği (`cache/fontconfig`) hiç yazılmıyor;
  paylaşılan `FontConfiguration` etkisini süreç başına tek taramaya indiriyor.

## Kapanan

- **TB7 — GROUPS katılımcı tipi (19.09.2026'da kapandı — başka yoldan):**
  OYS'nin şube-içi grup modeli + `ParticipantType.GROUPS`'u TAŞINMADI. Şubenin
  bir kısmının aldığı seçmeli için (ders, yıl, şube) öğrenci listesi geldi
  (`dersler.CourseEnrollment`, tasarım §7.3): listesiz şube dersi tamamen alır,
  listeli şubede yalnız listedekiler. Katılımcı tipi LEVEL/SECTIONS ikilisinde
  kalır (takvimdeki "üçüncü tip yok" kuralıyla uyumlu); liste SECTIONS
  çözümünde uygulanır. Grup ara modeli reddedildi: e-Okul veriyi zaten
  (ders → öğrenci) verir, grup eşlemeyi iki kez yaptırırdı.
- **TB10 — Ders kayıt verisi (19.09.2026'da kapandı):** kayıt verisi artık
  seçmeli ders öğrenci listesidir (TB7 kapanışı). `course_level_student_ids`
  dersin o seviyedeki BÜTÜN kapsam şubelerinde liste varken öğrenci kümesini
  döner ve `_daily_exam_load` onu kullanır; tek şube listesizse boş küme
  (bilinmiyor) → "kayıt verisi olmayan ders seviyenin tamamını kapsar" düşüşü
  AYNEN işler (Yönetmelik md. 5/1-k, Yönerge md. 5/1-s; ADR-0044 karar 13,
  tasarım risk #4). Değişmeyen: takvim girdisinin şube KAPSAMI (`section_ids`)
  günlük limite hâlâ GİRMEZ — kapsam beyandır, kayıt değil. Kapsamın
  kullanıldığı yerler: ızgara katılımcı önizlemesi, slottan oturum üretimi,
  aynı slot kesişimi sert kısıtı (`_scope_overlaps` — listeli şubede öğrenci
  düzeyinde), seçmeli kapsamın ders havuzundan ön-dolması.
- **TB8 — Yerleştirme kuralları arayüzü (31.08.2026'da kapandı, kütüğe
  18.09.2026'da işlendi):** oturum ayrıntısındaki "Kurallar" sekmesi
  (`KurallarPaneli`) koltuk sabitleme, tek başına oturtma ve ayrı tutma
  kurallarını yönetir; backend F3'ten beri tamdı. 18.09.2026'da iki boşluk
  kapandı: sabitlenmiş koltuk elle takasla bozulamaz (`swap_seats` PINNED reddi),
  oturum silinince oturuma özel kurallar ve gözetmen muafiyetleri de silinir.
- **TB9 — Şifreli `.ksbak` geri yükleme aracı (30.08.2026):** `--geri-yukle`
  kipi (desktop/restore.py + okul/services/backup_restore.py + manage.py
  restore_backup) düz VE şifreli yedeği açar; Windows'ta Başlat menüsü
  kısayolu + AllocConsole akışı, guvenlik.json gömülü başlıktan onarım,
  eski veritabanı `db-onceki-*` olarak kenara alınır. Ayrı oturumda
  geliştirildi, F9 sonrası birleştirildi (bkz. docs/kurulum.md §5.1).
- **TB5 — F0 paket kapısı (29.08.2026):** paketleme.yml ilk CI koşusu uçtan uca
  YEŞİL — Windows setup.exe + portable.zip, Linux .deb + .tar.gz, debian 11/12
  temiz kurulum provaları ve her iki platformda Türkçe PDF duman testi geçti
  (run 33257833345). DD `NOTLAR.md` W1-W9 varsayımlarından W1/W5 fiilen doğrulandı.
