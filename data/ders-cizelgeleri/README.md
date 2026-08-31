# Ders Çizelgeleri (sınav ders havuzu kaynağı)

Bu dizindeki `.md` dosyaları ders kataloğunun (`Course`) kaynağıdır
(ADR-0016 K6). Yükleme **tembel tohumdur**: ders havuzu ekranı ilk kez
açıldığında `apps.dersler.services.ensure_seeded()` koşar ve katalogda hiç
MEB kaydı yoksa buradaki dosyaları içe aktarır (idempotent). Çevrimdışı
güncelleme yolu = uygulama sürümüyle gelen yeni `.md` dosyasıdır (K5); ayrı
bir yönetim komutu YOKTUR.

> **Kurulu bir veritabanı bu dosyalar değişince kendiliğinden güncellenmez:**
> tohum "katalog zaten yüklü" diye erken döner. Mevcut kurulumlara ulaşması
> gereken değişiklikler bir veri göçüyle taşınır (emsal:
> `apps/dersler/migrations/0003_course_exam_mode_data.py`).

> Dizin `data/` altında çünkü backend konteyneri yalnız `./backend` ve
> `./data`'yı mount eder; `docs/` konteynerden görünmez.

## Dosya formatı (markdown tablo)

```markdown
| Ders | Seviyeler | Tür | Sınav |
|---|---|---|---|
| Türk Dili ve Edebiyatı | 9-12 | ORTAK | YAZILI |
| Beden Eğitimi ve Spor | 9-11 | ORTAK | UYGULAMA |
| Rehberlik ve Yönlendirme | 9-12 | ORTAK | YOK |
| Seçmeli İngilizce | 11-12 | SECMELI | YAZILI |
```

- **Ders:** havuzdaki benzersiz ad (eşleştirme anahtarı — yeniden adlandırma
  yeni ders sayılır).
- **Seviyeler:** virgüllü liste ve/veya aralık: `9, 10` · `9-12` · `0, 9-12`.
  Geçerli düzeyler: **0 (Hazırlık — ADR-0012)**, 9, 10, 11, 12.
- **Tür:** `ORTAK` veya `SECMELI` (Seçmeli yazımı da kabul edilir).
- **Sınav (isteğe bağlı 4. sütun):** `YAZILI` · `UYGULAMA` · `YOK`. Sütun hiç
  yoksa ya da hücre boşsa `YAZILI` varsayılır — **üç sütunlu eski dosyalar
  aynen çalışır** (`cerceveler/*.md`). Yazımı tanınmayan hücre satırı düşürür
  ve hata listesine yazar (sessizce `YAZILI` sayılmaz).

Sınav sütunu bir SÜZGEÇTİR: sınav takvimi havuzu kendiliğinden yalnız
`ORTAK` + `YAZILI` satırlardan doldurulur, seçmeliler ekrandan seviye/şube
seçilerek eklenir. `UYGULAMA` (uygulama sınavıyla değerlendirilen; salon planı
gerektirmez) ve `YOK` (notla değerlendirilmeyen) dersler otomatik havuza
girmez — gerekirse elle eklenebilir.

Tablo dışı satırlar (başlık, açıklama) yok sayılır; hatalı satırlar import'u
durdurmaz, satır numarasıyla raporlanır. Bir dosyada birden çok tablo olabilir.
PDF/XLSX çizelge desteği gerçek dosyalar temin edilince eklenecek (ADR-0016
Riskler).

`README.md` ve `ders-adi-takma-adlari.md` import'ta atlanır; `cerceveler/`
alt dizini de taranmaz (glob özyinelemesiz). Gerçek çizelge:
`anadolu-lisesi-2025-2026.md` (TTK 09.05.2025 — AL + Hazırlık AL birleşik;
Tur 237).
