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
   öğrenci verisi/e-Okul ihracı depoya girmez. İki katman: `.gitignore`
   ÖNLER, `packaging/depo_sizintisi.py` DENETLER (gates.sh'in ilk kapısı —
   izlenen dosyalarda veri biçimi + TCKN sağlaması arar). Dağıtım paketinin
   karşılığı `packaging/veri_sizintisi.py`, iki platform derlemesinde koşar.
   Her iki betik de bulguyu KONUMLA raporlar, eşleşen değeri BASMAZ —
   hata çıktısı da bir sızıntı kanalıdır.

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
- **`table-layout: fixed` + sütun yüzdesi = content-box tuzağı:** hücre dolgusu
  yüzdenin DIŞINA eklenir ve tablo sayfayı taşırır (ölçüldü: R1 yoklama +91pt,
  R4 duyuru +57pt). Çözüm `box-sizing: border-box`'u O TABLOYA vermek; ama o
  zaman ad sütununun içi dolgu kadar daralır — `_NAME_CELL_CHROME_PX` yatay
  dolguyu da içermek ZORUNDA, yoksa adlar sarar ve sayfa bütçesi kırılır.
- **Kroki kutu modeli:** `box-sizing: border-box` YALNIZ `.kroki` alt ağacına
  verilir. GLOBAL verilirse sütunlar daralır, metin sarar ve R1 yoklama + R4
  duyuru ikinci sayfaya taşar (denendi, beş test kırmızı) — o ölçüler
  content-box'a göre kalibre edildi.
- **Salon planında ÖN CEPHE bandı:** ızgaranın 0. satırı öğretmen masası/tahta/
  kapı içindir ve arayüzdeki "Sıra satırı" sayımına GİRMEZ (`planEdit
  .FRONT_BAND_ROWS`). `layout.DEFAULT_LAYOUT_PLAN` (6×4) ile `planEdit
  .emptyPlan()` BİREBİR aynı kalmalı — test ikisini karşılaştırır.
- **Varsayılan salon şablonu bilinçlidir** (`layout.default_section_plan`,
  02.09.2026): öğretmen masası **(0, 0) ön-sol**, **kapı YOK**, 4 sütun × 5 sıra
  ikili = 40 koltuk. "Numaralandırma öğretmen masasının önünden başlar" kuralı
  numaralandırma KODUNDA değil ŞABLONDA yaşar — `reference_cell` masayı bulur,
  S rotası oradan başlar; masa taşınırsa numaralar da taşınır. Kapı
  `_REFERENCE_PRIORITY`de yoktur (yalnız krokiye çizilir); varsayılana konursa
  resmî salon evrakına YANLIŞ bilgi basılır. Şablonun tek doğruluk kaynağı
  backend'dir: FE kendi kopyasını üretmez, `GET /exam-rooms/default-plan/`
  (`services.default_room_plan`) çağırır — hem "Yeni salon" hem editördeki
  "Varsayılan şablon" düğmesi. Şablon `desk_rows`/`cols` alır: 4×5 sabit
  değildir, editör açık salonun ızgarasını gönderir (okullar arası fark).
  Eski kurulumlar için toplu düzeltme `POST /exam-rooms/apply-default-plan/`
  (`apply_default_plan_to_rooms`): her salon KENDİ ölçüsünde şablona çekilir
  (kapasite korunur), bozuk/boş plan 5×4'e kurtarılır ve **yerleşimi yapılmış
  salon ATLANIR** — `SeatAssignment` koltuğu `(desk_row, desk_col, slot)` +
  `seat_no` ile saklar, numaralandırma yönü değişirse basılmış evrakla plan
  çelişir. Editörden tek tek değiştirmek yine serbesttir (bilinçli karar);
  atlama yalnız KÖRLEMESİNE toplu iş içindir.
- **Kullanıcıya gösterilen her katalog listesi TR sıralanır:** DB `order_by`
  SQLite'ta BINARY'dir (Ç/Ğ/İ/Ö/Ş/Ü, Z'den sonra). ViewSet'lerde `get_queryset`
  QuerySet döndürür (detay yolları için), sıralı liste `list()` override'ında
  `*_sorted()` selector'ıyla verilir.
- **Soft-delete ileri-FK'da SÜZMEZ:** `obj.fk` erişimi `_base_manager`
  üzerinden (ve `select_related` JOIN'iyle) çözülür — silinmiş kayıt geri
  gelir. Silme her yerde soft olduğundan `on_delete=PROTECT` de hiç
  tetiklenmez. Evrağa ad basan her yol `deleted_at`'i ELLE denetler
  (emsal `services_calendar._chair_name`).
- **Ders havuzu okulun YÜRÜRLÜKTEKİ çizelgesinden türetilir (03.09.2026,
  tasarım §7.2):** `data/ders-cizelgeleri/<program_key>.md` dosyaları TTK
  çizelgeleridir (meta bloğu: `okul_turu`, `hazirlik`, `bolum`, `yururluk`,
  `kademeli`…); `apps.dersler.catalog` okul türü + hazırlık + aktif ders yılı +
  `SchoolConfig.level_programs`'tan seviye→program planını çözer, satırları
  ada göre birleştirir (tür çatışmasında SEÇMELİ, sınavda YOK>UYGULAMA>YAZILI
  kazanır), `services.sync_catalog` kataloğa uygular. Tuzaklar: (1) senkron
  DAMGA ile tetiklenir (`catalog_stamp` = yapılandırma + yıl + dosya özetleri);
  eski "MEB kaydı varsa dosyayı okuma" erken dönüşü YOK, dosya değişikliği
  veri göçü GEREKTİRMEZ (0003 göçü tarihsel emsaldir, tekrarlanmaz). (2)
  Çizelge dışı kalan MEB dersi `is_active=False + catalog_excluded=True` olur ve
  yalnız BU bayraklı kayıt senkronla geri açılır; idarecinin pasifleştirdiği
  ders (bayraksız) asla geri açılmaz — `is_active` idari karardır. (3) Okul
  türünün HİÇ program dosyası yoksa senkron hiçbir kayda dokunmaz (veri yokluğu
  sessiz silmeye dönüşmez). (4) Ayar kaydı (`update_school_config`), kurulum
  tamamlama ve ders yılı aktivasyonu senkronu KENDİLERİ koşturur — testlerde
  `settings.CATALOG_DIR` tmp dizine çevrilmezse gerçek çizelgeler yüklenir.
  (5) Kademeli çizelgede (GSL/Spor 2025, MTAL nesilleri) kapsanmayan seviye en
  yeni programa DÜŞER ve plan uyarı taşır — sessiz düşme yok; uyarı ders havuzu
  panelinde görünür. (6) Aynı ders programlar arasında AYNI adla yazılır
  (kademeli/çok programlı birleşim ada göredir); "Seçmeli X" öneki resmî
  çizelge adıysa korunur. İki alanı karıştırma: `exam_mode` çizelge verisidir,
  senkronda EZİLİR (`levels`/`course_type` sınıfı); `is_active` idari karardır
  ve KORUNUR.
- **Sentetik veri fixture'ı eklerken muafiyet ADIYLA yazılır:** hem
  `.gitignore` hem `depo_sizintisi.MUAF_YOLLAR` tek tek dosya adı tutar; joker
  (`veri/*.xls`) o klasöre bırakılan GERÇEK bir e-Okul ihracını da muaf tutar
  ve KVKK koruması tam orada delinir. Sağlamalı örnek bir kimlik numarası test
  KAYNAĞINA yazılmaz, çalışma anında üretilir (aksi hâlde kapı kendi testini
  yakalar — `test_depo_sizintisi.py` deseni).
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
- **Takvim girdisi katılımcı kapsamı LEVEL/SECTIONS'tır** (kümeler kuralının
  takvim ayağı): `ExamCalendarEntry.participant_type` + `section_ids` —
  ÜÇÜNCÜ TİP YOK, şube kümesi kimliği girdiye YAZILMAZ (arayüz kümeyi somut
  şube pk listesine açar). `level` zorunlu ve teklik anahtarının parçası
  olduğundan yön oturum tarafının TERSİDİR: seviye verilir, şubeler ona karşı
  denetlenir (hepsi o seviyeye ait ve canlı olmalı). Slottan oturum üretilirken
  kapsam olduğu gibi `ExamSessionCourse`'a taşınır — "LEVEL" sabiti yazılmaz.
  Kapsamdaki şube SONRADAN silinebilir (JSON liste, FK koruması yok; onaylı
  takvimde girdi de düzenlenemez): `create_session_from_slot` kayıp şubeyi
  ATLAR, kapsamı tümüyle silinmiş girdiyi oturuma almaz/BAĞLAMAZ ve slotun
  kalanını üretir — kilitlemek OYS Tur 644'ün kapattığı hata sınıfını geri
  getirirdi. Sessiz düşmenin panzehiri `calendar_validation` uyarısıdır.
- **Havuz otomatik doldurması:** `fill_calendar_pool` ORTAK + YAZILI dersleri
  ve **şube kapsamı GİRİLMİŞ** yazılı seçmelileri çeker (03.09.2026); dönüş
  sözlüğünün şekli (`created/existed/skipped/total_pairs`) değişmez. Kapsamsız
  seçmeli `skipped`'a nedeniyle yazılır (sessiz düşme yok) ve seçim
  diyaloğundan elle eklenir; uygulama sınavı (`PRACTICE`) ve sınavsız (`NONE`)
  dersler hiç girmez. Tohum tur 1-2'de takvim yaratılırken kendiliğinden koşar,
  tur 3'te koşmaz; tohum hatası takvim yaratılmasını düşürmez.
- **Seçmeli ders kapsamının KAYNAĞI ders havuzudur** (`dersler
  .CourseSectionOffering`, 03.09.2026): "bu seçmeliyi hangi şubeler alıyor"
  bir kez Ders Havuzu ekranında girilir, dört takvim de onu kullanır. Anahtar
  `(ders, ders yılı, seviye)` — `Course` üzerinde ALAN OLAMAZ: katalog yıldan
  bağımsızdır ve `sync_catalog` alanlarını ezer, şube ise yıla bağlıdır (yıl
  geçince pk'ler ölü referansa dönerdi). Kapsam YALNIZ `ELECTIVE` derste
  yazılabilir. `set_course_sections` TAM DEĞİŞTİRMEDİR (gönderilmeyen seviye
  silinir); okuma (`course_section_map`) silinmiş şubeyi süzer. Yıl geçişinde
  kopyalama YOKTUR — her yıl yeniden girilir (bilinçli karar).
- **Takvim girdisi kapsamın KOPYASINI tutar** (snapshot): katalog sonradan
  değişince onaylanmış takvimin kapsamı geriye dönük kaymaz — küme kuralının
  aynı gerekçesi. `add_calendar_entries_bulk` kapsam GÖNDERİLMEMİŞSE katalogdan
  ön-dolar, gönderilmişse gönderilen kazanır (tek sınava mahsus istisna).
  Fark `scope_differs_from_catalog` ile rozetlenir (`entries` ucunda küme
  context'ten gelir — satır başına sorgu yok).
- **Koltuk sabitleme koordinattır:** `(desk_row, desk_col, slot)` — `seat_no`
  numaralandırma düzeni değişince kayar. "Tek başına" kardeş koltukları motor
  girdisinden düşürür; sahte `SeatAssignment` yazılmaz.
- `ExamCalendarEntry.authority` teklik kısıtına GİRMEZ: bir (ders, seviye, tür)
  ya okul ya üst makam sınavıdır. Aynı gün+seviyede ikisi birden varsa UYARI
  üretilir (sert kısıt değil — "zorunlu hâl" takdiri okul müdürlüğünündür).
- **Aynı slotta kapsam kesişimi SERT kısıttır** (03.09.2026): `place_entry`
  aynı gün+saat+seviyede kapsamı kesişen ikinci sınavı REDDEDER — üç kanallı
  uyarı deseninin tek istisnası, çünkü "zorunlu hâl" yorumu yok (öğrenci aynı
  anda iki salonda olamaz). Kesişim `_scope_overlaps`: seviye farklıysa yok, en
  az biri LEVEL ise var, ikisi de SECTIONS ise `section_ids` kesişimi. Bu kural
  `_daily_exam_load`u GEVŞETMEZ (ADR-0044 karar 13, risk #4): oradaki soru
  "öğrenci o GÜN kaç sınava girer" ve ders kaydı bilinmediğinden kapsam
  ihtiyatlı okunur; burada soru "aynı ANDA olabilir mi" ve kesişim kesin cevap
  verir. Denetim `calendar_validation`da da durur (kural öncesi kurulmuş
  takvimler + yerleştirmeden sonra genişletilen kapsam).
- **Otomatik yerleştirme KURAL MOTORU TUTMAZ** (`auto_place_entries`, F6 eki-2):
  yalnız SIRA ve TERCİH üretir, her yerleştirmeyi `place_entry`ye yaptırır ve
  reddedilen slotu atlar (`place_entry` kendi savepoint'inde koşar — `_seed_pool`
  emsali). Skorlama yaklaşıktır, kararı veren yerleştirmedir; ikinci bir mevzuat
  kopyası yazılırsa iki motor zamanla ayrışır. Üst makam sınavları OTOMATİK
  YERLEŞTİRİLMEZ (tarihleri ilgili makamın kılavuzunda — Yönerge md. 5), rapora
  gerekçesiyle düşer. Ceza demeti leksikografiktir (motor `_pair_penalty`
  deseni): `(3. sınav, kapasite aşımı, seviye günlük yükü, gün toplamı, saat)`.
- **Sabitleme (`is_pinned`) elle yerleştirmenin yan etkisidir:** `place_entry`
  varsayılan `pin=True` (idareci bilerek koydu), otomatik yerleştirme
  `pin=False`. `REDISTRIBUTE` kipi yalnız sabitsizleri havuza alır; `unplace`
  bayrağı DÜŞÜRÜR (havuzdaki girdinin korunacak slotu yok) ve yerleşmemiş girdi
  sabitlenemez — aksi hâlde otomatik yerleştirmeyi sessizce engellerdi.
- **Ders saati ayarı ikilidir** (`SchoolConfig.daily_period_count` +
  `exam_period_nos`): gün uzunluğu genel liselerde 8'dir ama mesleki/teknik
  programlarda değişir, bu yüzden AYARDIR; `bell_schedule` boşken varsayılan
  çizelge ondan türer (`default_bell_schedule` — 08:30'dan 50'şer dakika, ilk 8
  saat eski sabit listeyle BİREBİR). `exam_period_nos` otomatik yerleştiriciyi
  BAĞLAR, elle yerleştirmeyi yalnız UYARIR (mevzuat saat kısıtı koymaz; Yönerge
  md. 5 saati okul müdürlüğüne bırakır). Ayar açıkça gönderilirse aralık dışı
  saat HATA, yalnız gün kısaldıysa taşan kuyruk kırpılır.
- **Salon kapasitesi UYARIDIR:** aynı slottaki toplam mevcut aktif salon
  kapasitesini aşarsa uyarılır; kapasite 0 iken (salon tanımsız) denetim hiç
  çalışmaz — sert kısıt, kataloğu eksik okulda takvimi kurulamaz hâle getirirdi.

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
- Sürüm: CalVer, `VERSION` dosyası. `v*` etiketi paketleri üretir, GitHub
  Release'i açar ve paketleri R2'ye (`indir.okulapp.org/kelebek-sinav/`)
  yükler — hat ve gereken secret'lar `packaging/README.md` "Yayın hattı".
  Elle kalan tek iş okulapp.org deposundaki `src/data/ks-release.json`'dur;
  o siteye yazarken `../okulapp.org/CLAUDE.md` "Ortak çalışma düzeni" kuralları
  BAĞLAYICIDIR (taze taban · yalnız kendi alanı: `ks-release.json` +
  `src/pages/kelebek-sinav/**` · commit başlığı "Kelebek Sınav: …").
- Faz kapıları (F0-F9) tasarım belgesi §12'de — kapısı geçilmeden faz kapanmaz.
