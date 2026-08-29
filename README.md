# Kelebek Sınav

Liseler için **tamamen çevrimdışı, tek kullanıcılı** kelebek sınav planlama
masaüstü uygulaması (Windows 10/11 + Pardus 21/23).

- Ortak sınav takvimini mevzuat pencerelerine göre planlar (öğrenci bazlı
  günlük sınav limiti denetimiyle),
- öğrencileri kelebek düzeniyle salonlara dağıtır (deterministik, seed'li,
  bağımsız doğrulayıcılı),
- tüm salon ve takvim evrakını A4 PDF olarak üretir (kroki, yoklama, kapı
  listesi, tutanaklar, kişiselleştirilmiş soru kitapçıkları…).

Veri kurumda kalır: tek yerel SQLite dosyası, hiçbir dış servis çağrısı ve
telemetri yok. Öğrenci/öğretmen verisi e-Okul raporlarından (xlsx/pano) içe
aktarılır; ders havuzu MEB ders çizelgesinden okul türü ve kademeye göre
tohumlanır. Opsiyonel uygulama parolası ile alan şifrelemesi ve şifreli yedek.

**Durum:** F5 (kitapçık) tamamlandı — ders başına soru PDF'i yükleme (A4
dikey ±6pt doğrulaması, 20 MB sınırı, seviye/ortak-kitapçık grup anahtarı
kuralları), 4 cm üst marjlı Word soru şablonu ve kişiselleştirilmiş kitapçık
üretimi (R10): salon başına birleşik PDF + tümü-ZIP, bant üst 4 cm sabit,
soru sayfaları 1:1 (ölçekleme yok), üretim senkron (90×4 sayfa dakikanın çok
altında). Evrak seti (F4: R1-R5 + R7-R9 + boş plan + ZIP) ve arşivden yeniden
basım açık. Sırada F6: sınav takvimi (statutory_window + günlük limit).
Plan: [docs/tasarim/2026-08-29-genel-tasarim.md](docs/tasarim/2026-08-29-genel-tasarim.md)

## Köken

İş mantığı [okulapp (OYS)](https://github.com/aalidemirci/okulapp)
`sinav_islemleri` + `ders_yapisi` modüllerinden, masaüstü/paketleme/arayüz
iskeleti disiplin-defteri-codex projesinden türetilir. Ayrıntı: tasarım
belgesi §11 (AYNEN/UYARLA/ALMA haritası).
