# Kelebek Sınav

Liseler için **tamamen çevrimdışı, tek kullanıcılı** kelebek sınav planlama
masaüstü uygulaması (Windows 10/11 + Pardus 21/23).

- Ortak sınav takvimini mevzuat pencerelerine göre planlar (öğrenci bazlı
  günlük sınav limiti denetimiyle),
- öğrencileri kelebek düzeniyle salonlara dağıtır (deterministik, seed'li,
  bağımsız doğrulayıcılı),
- tüm salon ve takvim evrakını A4 PDF olarak üretir (kroki, yoklama, kapı
  listesi, tutanaklar, kişiselleştirilmiş soru kitapçıkları…).

Veri kurumda kalır: tek yerel SQLite dosyası, telemetri yok. Tek dış istek,
GitHub'daki son sürümü soran anonim güncelleme denetimidir — kişisel veri
taşımaz, çevrimdışıyken sessizce atlanır. Öğrenci/öğretmen verisi e-Okul
raporlarından (xlsx/pano) içe aktarılır; ders havuzu MEB ders çizelgesinden
okul türü ve kademeye göre tohumlanır. Opsiyonel uygulama parolası ile alan
şifrelemesi ve şifreli yedek.

**Durum:** F8 (bakım) tamamlandı — iki kipli günlük yedek (parolasızsa düz,
parolalıysa X25519 şifreli `.ksbak`; K9 düzeltmesi: yedek hiçbir kipte
atlanmaz), F27 arşiv anonimleştirmesi (ARŞİV + sınav tarihinden 730 gün;
açılışta aday tespiti + kullanıcı onaylı geri dönüşsüz tetik; evrak yeniden
basımı "—" işaretiyle açık kalır; kitapçık/soru dosyaları silinir) ve GitHub
Release güncelleme denetimi (SHA-256 doğrulamalı kurucu indirme + banner).
Önceki fazlar: gözetmen (F7), takvim (F6), kitapçık (F5), evrak seti (F4),
oturum akışı (F3), salonlar + motor (F2). Sırada F9: paketleme.
Plan: [docs/tasarim/2026-08-29-genel-tasarim.md](docs/tasarim/2026-08-29-genel-tasarim.md)

## Köken

İş mantığı [okulapp (OYS)](https://github.com/aalidemirci/okulapp)
`sinav_islemleri` + `ders_yapisi` modüllerinden, masaüstü/paketleme/arayüz
iskeleti disiplin-defteri-codex projesinden türetilir. Ayrıntı: tasarım
belgesi §11 (AYNEN/UYARLA/ALMA haritası).
