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
  yalnız Excel düğmesi olmayan raporlar için gerekir. v2 adayı.
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
- **TB7 — GROUPS katılımcı tipi alınmadı (F3 kesim kararı):** OYS'de şube-içi
  grup (SectionGroup) kavramı ve GROUPS katılımcı tipi vardı; KS'de şube grubu
  modeli olmadığından oturum dersi yalnız LEVEL/SECTIONS ile tanımlanır.
  Seçmeli ders grupları gerekirse önce `okul` tarafına grup modeli gelir,
  sonra `ParticipantType.GROUPS` + çözümleyici OYS'den taşınır
  (`participants._resolve_groups`, OYS satır 141-169).
- **TB10 — Ders kayıt verisi yok; kapsam verisi günlük limite BAĞLANMADI
  (31.08.2026, K19):** takvim girdisi artık katılımcı kapsamı taşıyor
  (`participant_type` + `section_ids`), ama `services_calendar._daily_exam_load`
  bu listeye **bakmaz** ve bakmayacak. Gerekçe: kapsam idarecinin beyanıdır,
  öğrenci-ders eşleşmesi değil — `dersler.selectors.course_level_student_ids`
  KS'de hep boş küme döner (B8 sapması), yani şubelerin öğrencisi sayılsa bile
  "bu öğrenci bu dersi alıyor mu" sorusu cevapsız kalır. Kural "kayıt verisi
  olmayan ders seviyenin tamamını kapsar" konservatif düşüşünde KALIR
  (Yönetmelik md. 5/1-k, Yönerge md. 5/1-s; ADR-0044 karar 13, tasarım
  risk #4). Kapsam verisinin kullanıldığı yerler (18.09.2026 güncellemesi):
  (1) ızgara dipnotundaki katılımcı önizlemesi, (2) slottan oturum üretilirken
  `ExamSessionCourse`'a taşınan katılımcı tanımı, (3) aynı slotta kapsam
  kesişimi SERT kısıtı (`_scope_overlaps`, 03.09.2026 — "aynı ANDA iki salonda
  olamaz" sorusu kapsamla kesin cevaplanır), (4) seçmeli ders kapsamının ders
  havuzundan ön-dolması (`CourseSectionOffering`). GÜNLÜK limit bunların
  hiçbirinden beslenmez. Gerçek ders kayıt verisi (seçmeli ders grupları)
  gelirse sıra şudur: önce `okul` tarafına kayıt/grup modeli girer (bkz. TB7),
  sonra limit hesabı ondan beslenir — tersi mevzuat denetimini deler.
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

## Kapanan

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
