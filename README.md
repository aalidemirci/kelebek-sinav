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

**Durum:** F6 (takvim) tamamlandı — mevzuat pencereli sınav takvimleri
(`statutory_window`: ayın son Pazartesisi + 11 gün; tur 3 dönemin son iki
haftası elle), ders havuzu + tıkla-yerleştir ızgarası, öğrenci-bazlı günlük
sınav limiti (3. sınav uyarı, ≥4 sert hata — konservatif düşüşle), onay akışı
(taslak → sunuldu → onaylı; damgalar korunur), onaylı slottan tek tıkla
kelebek oturum üretimi, süreç takip matrisi ve A4 yatay resmî takvim PDF'i
(TASLAK filigranlı). Önceki fazlar: kitapçık (F5), evrak seti (F4), oturum
akışı (F3), salonlar + motor (F2). Sırada F7: gözetmen görevlendirme.
Plan: [docs/tasarim/2026-08-29-genel-tasarim.md](docs/tasarim/2026-08-29-genel-tasarim.md)

## Köken

İş mantığı [okulapp (OYS)](https://github.com/aalidemirci/okulapp)
`sinav_islemleri` + `ders_yapisi` modüllerinden, masaüstü/paketleme/arayüz
iskeleti disiplin-defteri-codex projesinden türetilir. Ayrıntı: tasarım
belgesi §11 (AYNEN/UYARLA/ALMA haritası).
