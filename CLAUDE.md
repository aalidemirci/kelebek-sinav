# CLAUDE.md — Kelebek Sınav

> Her oturumda otomatik yüklenir. Amaç: projeyi ilk kez gören bir ajanın kodu
> doğru okuması ve **kasıtlı kararları kusur sanmaması**. Ana referans:
> `docs/tasarim/2026-08-29-genel-tasarim.md` — "neden böyle?" sorusunun cevabı
> %90 oradadır. Ham keşif malzemesi: `docs/kesif/`.
>
> Depo dili **Türkçe**: yorumlar, commit mesajları, testler, dokümanlar,
> kullanıcıya görünen tüm metinler. Tanımlayıcılar (sınıf/alan/uç adları)
> İngilizce — model ve API yüzeyi OYS'den çıkarıldığı için birebir korunur.

---

## 1. Altın kurallar

1. **Köken iki depo, kalıp değişmez.** İş mantığı OYS'den
   (`../okulapp/backend/apps/sinav_islemleri` + `ders_yapisi`), masaüstü/
   paketleme/M3 iskeleti disiplin-defteri-codex'ten (`../disiplin-defteri-codex`)
   çıkarılır. Tasarım belgesindeki **AYNEN/UYARLA/ALMA** haritasına uymayan
   "iyileştirme" yapma; AYNEN sınıfındaki dosyalarda imza/sözleşme değiştirme.
2. **Eski PySide6 uygulaması (`../sinav-islemleri`) referans DEĞİLDİR** —
   kullanıcı kalitesini beğenmedi; oradan kod alma.
3. **okulapp bu cihazda bayat olabilir.** OYS koduna bakmadan önce
   `git -C ../okulapp fetch` + `origin/main` teyidi.
4. **Tek kullanıcılı, girişsiz, çevrimdışı masaüstü.** "Auth yok / CSRF yok /
   herkese açık endpoint" bulgu değildir (DD §6 kalıbı). Yerel güvenlik =
   oturum belirteci (`X-KS-Token`, fail-closed) + opsiyonel uygulama parolası
   + Fernet alan şifrelemesi (tasarım §5).
5. **Test/lint yalnız Docker'da.** Host'a Python/Node kurulmaz. Kapı:
   `bash scripts/gates.sh` yeşil olmadan iş bitmiş sayılmaz.
6. **KVKK:** TCKN, veli verisi, sağlık serbest metni **hiç toplanmaz**;
   uyarı/hata metinlerinde öğrenci adı asla (okul no kullanılır); gerçek
   öğrenci verisi/e-Okul ihracı depoya girmez (`.gitignore` engeller).

## 2. Bilinen tuzaklar (gerçek kusurların yaşadığı yerler)

- **Tarih disiplini:** `new Date().toISOString().slice(0,10)` YASAK →
  `lib/format.ts::todayIso()`; backend'de UTC'den yerel tarih türetme yasak.
  Koruma testi `format.test.ts` F0'da taşınır.
- **Türkçe büyük harf:** evrak şablonlarında `text-transform: uppercase`
  YASAK (WeasyPrint i→I basar); Python'da çıplak `.upper()/.lower()` TR metne
  uygulanmaz — normalize yardımcıları kullanılır (yalnız eşleştirme için).
- **hiddenimports (DD borç K7):** her yeni Python bağımlılığı ÜÇ yere elle
  eklenir — `packaging/pyinstaller/*.spec` hiddenimports, `test_spec_kapsami.py`
  içindeki `DAGITIM_IMPORT_ESLEME` ve `giris.py` içindeki `RUNTIME_MODULES`.
  İlk ikisi statiktir; sigorta **`--bagimlilik-duman`** kipidir: paketlenmiş
  ikili her derlemede modülleri gerçekten import eder. (`--pdf-duman` yalnız
  WeasyPrint zincirini sınar — 30.08.2026'da `xlrd` eklendiğinde yeni
  bağımlılığı sınayan kapı olmadığı görüldü.)
- **WeasyPrint ölçü tuzakları (evrak sayfa bütçesi):** iç birim CSS px'tir
  (1 pt = 4/3 px) · tablo hücresine `height` vermek satırı KISALTMAZ, UZATIR
  (satır ölçüsü punto + dolgu ile ayarlanır) · gövdedeki `<style>` ve inline
  `style` özniteliğindeki CSS değişkenleri YOK SAYILIR (hesaplanan kurallar
  `<head>`e, `extra_style` bloğuna basılır) · sütun genişliği hesabına
  güveniliyorsa `table-layout: fixed` şart · hücreye BLOK kutu koyan tablolarda
  `tr { break-inside: avoid }` ŞART: `documents/base.html` bunu `.doc-table`
  için TANIMLAMAZ (kardeş `sinav/reports/base.html` tanımlar) ve kural yoksa
  uzun tablo satırı sayfa sınırında bölünüp devam sayfasında satır başlığı
  (tarih/saat) OLMADAN basılır. Bütçe sabitleri `reports.py`
  (`KROKI_BOX_*_PX`, `_ATT_FIXED_PX`, `_ANN_FIXED_PX`) — ÖLÇÜLEREK bulundu;
  garanti `test_reports.py::test_r1_salon_evraki_iki_yaprak` (bir derslikte
  40 öğrenci sığar, fazlası kontrolsüz taşmaz).
- **Şifreli alan sorguları:** ad-temelli filtre/sıralama/teklik DB'de
  çalışmaz → selector katmanında Python ile (tasarım §5). Yeni ad sorgusu
  doğrudan ORM filtresiyle yazılmaz.
- **Soft-delete ileri-FK'da SÜZMEZ:** `obj.fk` erişimi `_base_manager`
  üzerinden (ve `select_related` JOIN'iyle) çözülür — silinmiş kayıt geri
  gelir. Silme her yerde soft olduğundan `on_delete=PROTECT` de hiç
  tetiklenmez. Evrağa ad basan her yol `deleted_at`'i ELLE denetler
  (emsal `services_calendar._chair_name`).
- **SQLite:** `levels__contains` yok (Python süzme); yedek daima
  `Connection.backup()` (dosya kopyalama WAL'de yasak).
- **Kimlik sabitleri:** `KS_*` env, `ks_oturum`, `X-KS-Token`, `.ksbak`,
  yeni Inno AppId GUID — şablondan kalan `DD_`/`ddbak`/disiplin kalıntısı
  sıfır tolerans.

## 3. Değişmez sözleşmeler (motor)

- Çakışma grubu anahtarı `"<course_id>:<level>"` / ortak kitapçıkta
  `"<course_id>:*"` — soru dosyası, kitapçık ve R8 hep bu anahtarla eşleşir.
- Sert kısıt denetimi `(desk_row, desk_col)` KİMLİĞİNDEN (mesafeden değil).
- Aynı seed → aynı dağıtım; seed R8'de basılır.
- Motor çıktısı bağımsız `validator.py`'den geçer; onay yalnız ihlal=0.
- SNAPSHOT deseni: SeatAssignment/yoklama/gözetmen kayıtlarındaki ad/no/şube
  kopyaları arşiv evrakının sabitliği içindir — kaldırılmaz.
- `ExamSessionCourse` tek-seviyeli; kitapçık sözlüğü grup anahtarıyla
  (OYS Tur 241 dersi).
- Takvim ızgarası hücre anahtarı `"<iso_tarih>|<period_no>|<level>"` — FE ve
  PDF ORTAK tüketir; hücre sözlüğüne alan eklenir, anahtar biçimi değişmez.
- Takvim imza bloğu sözleşmesi `{"chairs": [{"name", "role"}],
  "school_chair_name"}` (`_calendar_signatures` çıktısı). Kaynak takvime seçilen
  zümrelerdir (`okul.SubjectDepartment`); seçim yoksa derslerden boş çizgi
  üretilir (B7 revizyonu) — şablon iki anahtarı görmeye devam eder.
- **Ceza demeti:** `engine._pair_penalty` leksikografik `(birincil, ikincil)`
  döner. Birincil sert/yumuşak yakınlık cezasıdır (sert kısıt kaynağı);
  ikincil YALNIZ eşitlik bozar (kaçınılmaz komşu çiftin öğretmen masasına
  uzaklığı). İkincil hiçbir koşulda ihlal sayısını artıramaz.
- **Kümeler seçim aracıdır:** şube/derslik kümesi kimliği HİÇBİR oturum
  kaydına yazılmaz; sihirbaz kümeyi somut pk listesine açar.
- **Koltuk sabitleme koordinattır:** `(desk_row, desk_col, slot)` — `seat_no`
  numaralandırma düzeni değişince kayar. "Tek başına" kardeş koltukları motor
  girdisinden düşürür; sahte `SeatAssignment` yazılmaz.
- `ExamCalendarEntry.authority` teklik kısıtına GİRMEZ: bir (ders, seviye, tür)
  ya okul ya üst makam sınavıdır. Aynı gün+seviyede ikisi birden varsa UYARI
  üretilir (sert kısıt değil — "zorunlu hâl" takdiri okul müdürlüğünündür).

## 4. Nasıl koşulur

```bash
docker compose build backend
docker compose run --rm backend python manage.py migrate
docker compose run --rm frontend npm install
bash scripts/gates.sh
```

(F0 tamamlanana dek bu komutlar iskelet gerektirir — faz durumu için
`docs/tasarim/…§12`.)

## 5. Commit ve süreç

- Conventional Commits, Türkçe, kapsam etiketli: `feat(sinav): …`,
  `fix(okul): …`, `chore(paket): …`.
- Sürüm: CalVer, `VERSION` dosyası; sürüm çıkışı ileride okulapp.org kartına
  dokunur (DD §5 deseni; `../okulapp.org/CLAUDE.md` kuralları).
- Faz kapıları (F0-F9) tasarım belgesi §12'de — kapısı geçilmeden faz kapanmaz.
