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

**Durum:** Tasarım aşaması tamamlandı, F0 (iskelet) başlamadı.
Plan: [docs/tasarim/2026-08-29-genel-tasarim.md](docs/tasarim/2026-08-29-genel-tasarim.md)

## Köken

İş mantığı [okulapp (OYS)](https://github.com/aalidemirci/okulapp)
`sinav_islemleri` + `ders_yapisi` modüllerinden, masaüstü/paketleme/arayüz
iskeleti disiplin-defteri-codex projesinden türetilir. Ayrıntı: tasarım
belgesi §11 (AYNEN/UYARLA/ALMA haritası).
