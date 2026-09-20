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
  (tarih/saat) OLMADAN basılır · `overflow: hidden` blok kutunun yanına
  float konmaz (içerik float'ın ALTINA kayar) — yan yana iki kutu gerekiyorsa
  iki hücreli tablo (`.fp-hbody`) · aynı görsel TEK nesne olarak gömülür:
  görsel SAYAN testte her fotoğraf farklı üretilir. Bütçe sabitleri
  `reports.py` (`PHOTO_PLAN_BOX_PX` — R1 fotoğraflı plan, `KROKI_BOX_LAYOUT_PX`,
  `_ANN_FIXED_PX`) — ÖLÇÜLEREK bulundu; garanti
  `test_reports.py::test_r1_salon_evraki_iki_yaprak` (bir derslikte 40 öğrenci
  sığar, fazlası kontrolsüz taşmaz).
- **PDF üretimi TEK kapıdan ve SIRAYLA (19.09.2026 çöküş tanısı):** WeasyPrint'e
  yalnız `shared.pdf.html_to_pdf` ile gidilir — süreç genelinde kilit + paylaşılan
  `FontConfiguration`. Pango/fontconfig C katmanı aynı süreçte EŞZAMANLI basımda
  yerel belleği bozuyor: paketli program "Tümünü indir"de `libpangoft2` erişim
  ihlaliyle kapandı (Pango NULL yazı tipi verdi), aynı DLL'lerle Windows tanısında
  paralel basım yığın bozulmasıyla (0xC0000374) düştü, sıralı basım düşmedi.
  Gömülü sunucu altı iş parçacıklıdır; kilit olmadan evrak/kitapçık/takvim PDF'i
  çakışır. Koruma testi `shared/tests/test_pdf.py` başka `write_pdf`e izin vermez.
  Yerel çöküş Python istisnası DEĞİLDİR, `uygulama.log`a düşmez — `logs/cokme.log`
  (`faulthandler`, `desktop.logging_setup.enable_crash_log`) o anın yığınını tutar.
  Tanı düzeneği (Windows): kurulu programın `_internal` DLL'leri + yerel Python312;
  önce `SetDllDirectoryW(_internal)` ŞART — yoksa PATH'teki GTK3-Runtime DLL'leri
  karışır ve süreç ilk basımda çöker (yanıltıcı "bilinmeyen modül" kaydı).
- **Şifreli alan sorguları:** ad-temelli filtre/sıralama/teklik DB'de
  çalışmaz → selector katmanında Python ile (tasarım §5). Yeni ad sorgusu
  doğrudan ORM filtresiyle yazılmaz.
- **`table-layout: fixed` + sütun yüzdesi = content-box tuzağı:** hücre dolgusu
  yüzdenin DIŞINA eklenir ve tablo sayfayı taşırır (ölçüldü: R1 yoklama +91pt,
  R4 duyuru +57pt). Çözüm `box-sizing: border-box`'u O TABLOYA vermek; ama o
  zaman ad sütununun içi dolgu kadar daralır — `_NAME_CELL_CHROME_PX` yatay
  dolguyu da içermek ZORUNDA, yoksa adlar sarar ve sayfa bütçesi kırılır.
- **Kroki kutu modeli:** `box-sizing: border-box` YALNIZ `.kroki` ve `.fplan`
  (fotoğraflı plan) alt ağaçlarına verilir. GLOBAL verilirse sütunlar daralır,
  metin sarar ve evrak ikinci sayfaya taşar (denendi — o gün R1 yoklama + R4
  duyuru, beş test kırmızı) — öteki tablolar content-box'a göre kalibre edildi.
- **Öğrenci fotoğrafı KVKK verisidir (19.09.2026, tasarım §6 + §9):**
  `okul.StudentPhoto` — tek alan `EncryptedTextField` (base64 JPEG); parola
  açıkken şifreli, `encrypted_field_map` parola geçişine kendiliğinden katar,
  yedeğe girer. Kaynak e-Okul OOG01001R080 **Excel**'idir (`okul/eokul_foto.py`
  — BIFF8 içindeki OfficeArt görsel deposu + şekil çapası; okul no çapanın
  ALTINDAKİ hücreden). PDF yolu YAZILMADI (konumdan eşleştirme kırılgan).
  Görsel Pillow'la YENİDEN KODLANIR (EXIF/meta atılır, ≤240×320); e-Okul'un
  "fotoğraf yok" simgesi (birden çok şeklin paylaştığı görsel, DIB/metafile)
  yer tutucudur ve kayıtlı fotoğrafı SİLMEZ. Mükerrer yükleme: aynı sha256
  sessiz geçer, FARKLI fotoğrafta `on_conflict` (keep/replace) idarecinin
  seçimidir — sessizce ezilmez. Öğrenci aktif olmaktan çıkınca
  (`update_student`) ya da silinince (`delete_student`) fotoğraf KATI silinir;
  evrak ve uç (`photo_data_uris`) yalnız aktif öğrencinin fotoğrafını verir ve
  çözülemeyen değeri atlar (evrak fotoğrafsız basılır, çökmez). Paket
  sigortası: `--pdf-duman` JPEG'in PDF'e gerçekten gömüldüğünü sınar —
  WeasyPrint çözemediği görseli yalnız UYARIYLA atlar.
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
  çizelge adıysa korunur. (7) Program ANAHTARI kaldırmak/yeniden adlandırmak
  (1)'in istisnasıdır ve veri göçü İSTER: anahtar `SchoolConfig.level_programs`
  içinde kayıtlıdır, `validate_level_programs` bilinmeyen anahtarı REDDEDER
  (Okul Bilgileri hiç kaydedilemez) ve çizelge matrisi bayat anahtara kutu
  çizmez. Emsal `okul/0007` (19.09.2026 — AİHL B grubu yedi programa bölündü;
  eski anahtar yenilerine AÇILIR, havuz aynı kalır). Aynı bölünme bir ilkeyi de
  yerleştirdi: programa göre değişen ZORUNLULUK kodla değil, varsayılan dışı
  program dosyasındaki SEÇMELİ satırla anlatılır ("Osmanlı Türkçesi | 10" —
  tür çatışmasında SEÇMELİ kazanır). İki alanı karıştırma: `exam_mode` çizelge
  verisidir, senkronda EZİLİR (`levels`/`course_type` sınıfı); `is_active` idari
  karardır ve KORUNUR.
- **Sentetik veri fixture'ı eklerken muafiyet ADIYLA yazılır:** hem
  `.gitignore` hem `depo_sizintisi.MUAF_YOLLAR` tek tek dosya adı tutar; joker
  (`veri/*.xls`) o klasöre bırakılan GERÇEK bir e-Okul ihracını da muaf tutar
  ve KVKK koruması tam orada delinir. Sağlamalı örnek bir kimlik numarası test
  KAYNAĞINA yazılmaz, çalışma anında üretilir (aksi hâlde kapı kendi testini
  yakalar — `test_depo_sizintisi.py` deseni).
- **Aynı çizelgenin YENİ KARARI yeni program dosyasıdır** (ders havuzu
  maddesinin eki — 19.09.2026, TTK 02.09.2026/102-103 Spor emsali): eski dosya
  yerinde düzenlenmez ve silinmez (`program_key` kararlı anahtardır; aktif ders
  yılı eski olan kurulum onunla çözülür), yeni dosya yeni `yururluk` ile eklenir
  ve program her (seviye, tür) için en yeni KAPSAYAN nesli kendisi seçer. İki
  sonucu: hiçbir neslin kapsamadığı seviyede yedek, yürürlüğü BAŞLAMIŞ en yeni
  nesildir (2026 çizelgesi 2025-2026'ya sızmaz); AÇIK atama (`level_programs`
  — varsayılan dışı Tematik Spor yalnız böyle seçilir) yeni nesle kendiliğinden
  GEÇMEZ, `catalog._superseded_by` UYARIR ve atamaya dokunmaz (idari karar).
  TTKB listesinde bağlantısı değişen çizelgede önce karar sayfasına bakın:
  yeniden dizgi sanılan şey yeni karar çıkabilir. 09.2026'dan beri TTKB PDF'leri
  DYS çıktısıdır (sayfa Form XObject'e sarılı): düz pypdf düzen kipi yalnız
  filigranı döker ve PDF "taranmış" SANILIR — `scripts/cizelge_pdf_metni.py`
  formu açar; usul `data/ders-cizelgeleri/README.md` "Aktarım tuzakları".
- **Django `{# #}` yorumu TEK satırlıktır:** çok satıra yayılınca metin olarak
  BASILIR (R8 doluluk tablosunda örnek PDF'e sızdı, 18.09.2026). Şablonda çok
  satırlı açıklama `{% comment %}` bloğuyla yazılır; koruma testi
  `test_reports.py::test_r8_yorum_sizintisi_yok`.
- **"Ortak" sözcüğü üç anlam taşımaz:** MEB'de "ortak sınav/ortak yazılı" okul
  geneli sınavdır. Kullanıcı metninde ders türü için "zorunlu", seviyeler arası
  tek kitapçık için "tüm seviyeler aynı kitapçık" kullanılır; "ortak" yalnız
  MEB anlamında geçer ("ortak öğrenci" de yazılmaz: "iki dersi birden alan
  öğrenci").
- **Kullanıcı metninin sözlüğü `docs/sozluk.md`'dir (bağlayıcı):** salon/derslik,
  öğretmen/personel, sınıf düzeyi, katılımcı kapsamı, "dağıtım numarası" (seed),
  "kural ihlali"; iç kodlar (K5, R10, F6…) ve iç kimlikler (`id=…`) kullanıcı
  metninde, hata mesajında ve evrakta GEÇMEZ. Sınıf düzeyi etiketi tek
  kaynaktan: `dersler.text.level_label` / FE `gradeLevelLabel` ("9. Sınıf").
- **Servis hatası merkezî çevrilir:** `ks_exception_handler` Django
  `ValidationError`'ını 400'e çevirir (DRF tanımaz → 500 olurdu) ve kaynağı
  servis hatası olan alan-sözlüğü retlerinde `message`'a GEREKÇEYİ yazar (arayüz
  snackbar'da `message` basar). Serializer alan hatalarında genel cümle kalır.
- **DRF tek alanlı UniqueConstraint'ten ALAN düzeyinde UniqueValidator türetir;**
  `Meta.validators = []` onu silmez. Teklik mesajı servisten gelecekse alan elle
  tanımlanır (`validators=[]`) — emsal `SubjectDepartmentSerializer`,
  `ExamTrackItemSerializer`.
- **Soft-delete `SET_NULL`'ı da tetiklemez:** silinen oturuma bağlı takvim
  girdisinde `session_id` ölü kimliği taşır. Canlılık tek yardımcıdan sorulur
  (`services_calendar.has_live_session`); liste/ızgara yalnız canlı kimliği döner.
- **`version_key` iki kopyadır** (`desktop/version.py`, `okul/services/updates.py`)
  ve AYNI kalmalıdır; ön-sürüm eki doğal sıralanır (`beta.10 > beta.9`).
- **Mevzuat atfı depodaki metinden doğrulanır:** `docs/mevzuat/` (ÖDY, Yönerge,
  OKY seçilmiş maddeler + atıf haritası, KVKK 6698 seçilmiş maddeler + atıf
  haritası). Yeni atıf eklerken önce metni ekleyin. Öğrenci fotoğrafı biyometrik
  İŞLENMEDİĞİ için KVKK md. 5 kapsamındadır ve evrak dipnotlarındaki md. 5/2-ç
  dayanağı buna bağlıdır: programa yüz tanıma, otomatik fotoğraf eşleştirme ya
  da fotoğraftan özellik çıkarımı EKLENMEZ — eklenirse veri md. 6'ya girer ve
  md. 5/2 şartlarının hiçbiri yetmez (gerekçe `docs/mevzuat/kvkk-6698.md`
  "Değerlendirme notları").
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
  (OYS Tur 241 dersi). **`shared_booklet` dersin oturum içi niteliğidir,
  satırın değil** (18.09.2026): kardeş satırlar daima aynı değeri taşır — açık
  verilen değer `_sync_shared_booklet` ile kardeşlere YAYILIR, verilmeyen değer
  kardeşten miras alınır (eski "uyuşmazlıkta ret" kalktı; idareci ilk satırda
  yanlış işaretlediği bayrağı ikinci satıra zorla taşıyor, sonra soru dosyası
  yükleyemiyordu). Arayüz: ekleme formunda SORULMAZ; yalnız aynı ders ≥2
  seviyedeyken listenin altındaki ders-başı kutu vardır ve Sorular paneli grubu
  TEK satırda gösterir (`groupQuestionRows`). Kullanıcıya "ortak kitapçık"
  DENMEZ — MEB'de "ortak sınav" okul geneli sınavdır; ek metni tek yerde
  (`SHARED_BOOKLET_SUFFIX`).
- **Durum makinesinde geri yol** (18.09.2026): DAĞITILDI → TASLAK
  `revert_session_to_draft` (`POST /exam-sessions/{id}/revert-to-draft/`,
  FE "Taslağa al"). Yerleşim + gözetmen görevlendirmesi soft-delete,
  `distribution_params` sıfırlanır; ders/salon satırları, kural, muafiyet, soru
  dosyası ve kitapçık koşuları KORUNUR. Onaylı oturum önce `reopen`.
- **Yoklaması alınmış oturumun yerleşimi DEĞİŞMEZ:** yoklama sınavdan sonra
  alınır; o andan itibaren yerleşim sınavın yapıldığı düzenin kaydıdır.
  `_ensure_no_attendance` yeniden dağıtımı ve taslağa almayı REDDEDER (kayıtlar
  sessizce silinmez — idareci isterse önce Yoklama sekmesinden kaldırır).
- **Mazeret sınavı yoklama kaydından TÜRER** (19.09.2026, `services_makeup`,
  ekran `/mazeret`): oturum `ExamSession.is_makeup`, satırı
  `ParticipantType.MAKEUP` ("Mazeretli öğrenciler"), bağ
  `ExamAttendanceRecord.makeup_course`. Katılımcı listesi SAKLANMAZ —
  `participants._resolve_makeup` bağlı kayıtlardan YALNIZ hâlâ "Mazeretli" + aktif
  olanı verir; sonradan değişen sayıyla uyarılır ve `placement_drift`e düşer.
  MAKEUP satırı elle eklenmez/değiştirilmez (`MAKEUP_ROW_MANUAL_MESSAGE` — plan
  kopyalama da atlar; yalnız süre ve "aynı kitapçık" açık) ve takvimde üçüncü tip
  DEĞİLDİR (`CALENDAR_PARTICIPANT_CHOICES`). Mazeret oturumundaki kayda ikinci
  mazeret sınavı AÇILMAZ (OKY md. 48/1 "bir defaya mahsus"), kayıtlar tek dönemden
  gelir ve mazeret oturumunun dönemi değişmez, aynı öğrenci bir oturumda iki
  mazerete alınamaz; onaylanmış mazeret sınavından çıkarma reddedilir. Bağın
  canlılığı `live_makeup_course` ile ELLE sorulur (soft-delete SET_NULL'ı
  tetiklemez; silinen mazeret oturumunun kaydı kendiliğinden serbest kalır).
  5 iş günü süresi UYARIDIR (kullanıcı kararı; hafta sonu düşülür, tatil verisi
  yok). Rapor ucu biçimi `?kind=pdf|xlsx` alır — `?format=` DRF içerik
  müzakeresine ayrılmıştır, "pdf" verilince uç 404 döner.
- **Mazeret TAKVİMİ öğrenci öğrenci hesaplar, olağan takvimle KARIŞMAZ** (20.09.2026,
  `makeup_schedule` saf modül + `services_makeup_plan`, ekran `/mazeret?tab=takvim`):
  kapsam sınıf düzeyi/şube değil, takvime AÇIKÇA bağlanmış yoklama kayıtlarıdır
  (`ExamAttendanceRecord.makeup_plan_item` → `MakeupPlanItem` = ders + düzey). Bağ
  anlık türetilmez: sonradan "Mazeretli" olan kayıt kendiliğinden bir saate düşseydi
  çakışma güvencesi sessizce delinirdi — taslakta "Kayıtları güncelle" ile eklenir.
  SERT: aynı öğrenci aynı saatte iki sınavda olamaz (elle taşımada ret, onayı engeller)
  ve otomatik yerleştirmede öğrenci başına günlük sınır (1-3; Yönerge md. 5/1-s gereği
  4 yok). SIRA kullanıcı kararıdır: `strict_order` açıkken bir sınav, asıl takvimde
  kendinden önceki hiçbir sınavdan önceye konmaz; asıl takvimde AYNI saatteki sınavlar
  küme sayılır, birbirini itmez. Kapalıyken yalnız her öğrencinin kendi sırası korunur.
  Sıra anahtarı kalemin EN ERKEN asıl oturumunun tarih+saatidir. Sabit (`is_pinned`) ve
  oturumu üretilmiş kalem yerinde kalır, yalnız doluluk sayılır, sıra kuralının dışındadır.
  Ülke/il/ilçe geneli sınav (`external`) OTOMATİK YERLEŞMEZ — tarihini il/ilçe MEM ilan
  eder (Yönerge md. 5/1-aa, bb), idareci elle sabitler. Sığmayan kalemin gerekçesi
  kalemde SAKLANIR (`note`; sonradan hesaplanan gerekçe o anki dolulukla çelişirdi),
  "en az gün" ise her istekte aynı girdiyle yeniden hesaplanır. Tarih sınırları (dönem
  dışı, hafta sonu, olağan sınav haftasıyla çakışma, üst makam günü) UYARIDIR. Takvime
  alınmış kayıt elle mazeret sınavına alınamaz (`create_makeup_session(from_plan=…)`);
  onaylı takvimin her saati TEK mazeret oturumu olur (`create_sessions`, idempotent) ve
  oturumu üretilmiş takvim yeniden açılamaz. İlan PDF'i ADSIZDIR (öğrenci adı/numarası
  yok); öğrenci listeli nüsha ayrı belgedir ve adlar gizlenebilir.
- **Karma seviyeli oturumda evrak ders adı:** `_seat_course_names` aynı ders
  ≥2 seviyedeyse adı seviyeyle basar ("Coğrafya — 9. Sınıf"; R1/R5/R7 ve kitapçık
  bandı); şube duyurusunda (R4) `SeatRow.course_plain` ile SEVİYESİZ basılır
  (şube tek seviyededir).
- **Karışık salonda DERS KODU:** oturma planı kartının rozeti ve planda yeri
  olmayanlar listesinin "Ders" sütunu TEK HARF taşır (A, B, C — ders
  etiketinin doğal sırası); açıklaması planın üstünde, künyede kod özeti,
  sayım tablosunda kod + tam ad + süre.
  Gerekçe ölçümdür: gerçek ders etiketi ("Türk Dili ve Edebiyatı — 10. Sınıf")
  dar sütunda sarıp 40 öğrencili evrakı üçüncü sayfaya taşırıyordu. Sayfa
  bütçesi testleri bu yüzden GERÇEK uzunlukta adlarla koşar (`_GERCEK_DERSLER`);
  "Ders 0" gibi kısa fixture'a dönmeyin. R4'te ad/ders sütun payı en uzun
  metinlere göre bölüşülür (`_announcement_columns`).
- **Evrakta sınav süresi:** `ReportHeader.duration_label` üst bantta
  ("40 dk" / "derse göre 40-60 dk"), ders bazlı süre R1 sayım tablosunda;
  ders süresi oturum süresini ezer (`_group_durations`).
- **Soru dosyası satırı iz, dosyası geçicidir:** değiştirilen/kaldırılan soru
  PDF'i DİSKTEN de silinir (`_retire_question_documents`, commit sonrası);
  satır (sayfa sayısı, sha256) kalır. Silme ucu yükleme ile aynı durum
  kapısından geçer (onaylı/arşivde ret). Yedek medya dosyalarını KAPSAMAZ;
  dosyası olmayan kayıtta indirme `media_missing` 404 döner.
- **Ders birleştirme grup anahtarını yeniden yazar:** `consolidate_duplicate_course`
  sınav dersi, takvim girdisi ve seçmeli kapsamı taşır; yerleşim snapshot'larındaki
  `conflict_group` aynı işlemde güncellenir. İki ders aynı dağıtılmış oturumdaysa
  REDDEDER.
- **İhlal/uyarı metni idareci diliyle, denetim kimlikle:** `validator.PlacedStudent`
  ve `engine.RoomSeats` isteğe bağlı ETİKET alanları taşır (salon adı, sıra konumu,
  ders etiketi, okul no). Etiketler denetime ve yerleşime GİRMEZ; etiketsiz kurulumda
  metin ham kimlik ve koordinata düşer (motor testleri değişmeden yeşil — `focus`
  ile aynı genişletme deseni). Konum tek yerden: `layout.desk_position_label` ("3. sıra,
  1. sütun"; ön cephe bandı sayılmaz, FE `planEdit.seatPositionLabel` ile AYNI).
  Yeni bir uyarıya `room_id`, `id=`, `(2,1)` ya da iç kural kodu (`AYRI_SALON`)
  yazmayın; KVKK gereği öğrenci ADI da yazılmaz, okul numarası yazılır.
- **Kitapçık üretimi yerleşimin kopyasıdır:** ZIP salon/koltuk/ad taşır. Yerleşim
  sonradan değişirse (yeniden dağıtım, taslağa alma, koltuk takası) üretim
  `is_stale` olur (`selectors.booklet_run_is_stale` — canlı yerleşimin son
  `updated_at`'i üretimden yeniyse). Dosya silinmez; arayüz satırı uyarıyla
  işaretler. Yerleşime dokunan yeni bir işlem `updated_at`'i İLERLETMELİDİR
  (`QuerySet.update()` ilerletmez).
- **Uygulama içi güncelleme yalnız Windows'tadır:** `updates.installer_supported`;
  Linux'ta `can_download` false + `platform: "linux"` döner, arayüz paketle
  güncellemeye yönlendirir. Testler Linux kabında koştuğu için güncelleme
  testlerinde platform fixture'la Windows'a çevrilir.
- Takvim ızgarası hücre anahtarı `"<iso_tarih>|<period_no>|<level>"` — FE ve
  PDF ORTAK tüketir; hücre sözlüğüne alan eklenir, anahtar biçimi değişmez.
- Takvim imza bloğu sözleşmesi `{"chairs": [{"name", "role"}],
  "school_chair_name"}` (`_calendar_signatures` çıktısı). Kaynak takvime seçilen
  zümrelerdir (`okul.SubjectDepartment`); seçim yoksa derslerden boş çizgi
  üretilir (B7 revizyonu) — şablon iki anahtarı görmeye devam eder.
  `school_chair_name` slotunun ETİKETİ "Düzenleyen — Müdür Yardımcısı"dır
  (18.09.2026; eski "Okul Zümre Başkanı" mevzuatta yoktu ve hiç dolmuyordu).
  Antet resmî yazışma usulündedir: kurum satırı `tr_upper`, birim satırı
  "<Okul Adı> Müdürlüğü" (`letterhead_unit`).
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
- **Seçmeli ders öğrenci listesi ŞUBE BAZINDADIR** (`dersler.CourseEnrollment`,
  19.09.2026, tasarım §7.3 — TB7/TB10'u kapattı): (ders, yıl, şube) satırı varsa
  o şubeden YALNIZ listedekiler dersi alır, yoksa şubenin TAMAMI — veri girmeyen
  okulda hiçbir şey değişmez. Uygulandığı üç yer: SECTIONS katılımcı çözümü
  (`_resolve_sections`; LEVEL satırı listeyi UYGULAMAZ, varlığını uyarır),
  takvim slot kesişimi (`_scope_overlaps` + `EnrollmentIndex`) ve
  `course_level_student_ids` — sonuncusu dersin o seviyedeki BÜTÜN kapsam
  şubeleri listeliyse küme döner, tek şube listesizse boş (günlük limit
  düşüşü). Satırlar KATI silinir (tam değiştirme, tarih tutulmaz;
  `all_objects...hard_delete()`); `set_course_sections` kapsamdan çıkan şubenin
  listesini düşürür; yıl geçişinde kopyalanmaz. Kaynak e-Okul OOK10002R010
  **PDF**'idir (TB1'in tek istisnası — Excel ihracında ders adı yok;
  `enrollment_import.py` satırdan yalnız okul no + sınıf/şube okur, ad
  AYRIŞTIRILMAZ) ya da şube penceresindeki seçici. Aktarım yalnız raporun
  KAPSADIĞI şubelerde (raporda satırı geçen) yeniler: rapor tek düzey/şube için
  alınmış olabilir, kapsam dışı şubenin listesi ve kapsamı SİLİNMEZ; raporda
  olmayan derse hiç dokunulmaz. Aktarım havuzu da toparlar (kullanıcı kararı):
  havuzda HİÇ adayı olmayan başlık önizlemede `addable` gelir, idarecinin
  işaretlediği `add_titles` seçmeli (MANUAL) açılır — zorunlu adla çakışan başlık
  açılmaz; kapsanan şubeler `ElectiveReportSection`e yazılır ve öğrencili bütün
  şubeleri kapsanan düzeyde kapsamı olmayan seçmeli "bu yıl açılmadı" sayılır
  (`selectors.elective_offer_status`) — PASİFLEŞTİRİLMEZ (`is_active` idari
  karar), Ders Havuzu'nda gizlenir, `fill_calendar_pool` onları `skipped`'a tek
  özet satırla yazar; şube girilince kendiliğinden açılır. Liste dağıtımdan SONRA
  değişirse yerleşim DEĞİŞMEZ: `participants.placement_drift` snapshot'ı güncel
  çözümle karşılaştırır, oturum sayfası "yeniden dağıtın" bandı gösterir.
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
  az biri LEVEL ise var, ikisi de SECTIONS ise ortak şubeler; ortak şubede iki
  dersin de öğrenci listesi varsa soru ÖĞRENCİYE iner (liste kesişimi), biri
  listesizse şube kesişir (19.09.2026 — ret metni iki dersi birden alan öğrenci
  SAYISINI söyler). Bu kural `_daily_exam_load`u GEVŞETMEZ (ADR-0044 karar 13,
  risk #4): oradaki soru "öğrenci o GÜN kaç sınava girer" ve ders kaydı yalnız
  TAM listede bilinir (aşağıda); eksikse kapsam ihtiyatlı okunur; burada soru
  "aynı ANDA olabilir mi" ve kesişim kesin cevap verir. Denetim
  `calendar_validation`da da durur (kural öncesi kurulmuş takvimler +
  yerleştirmeden sonra genişletilen kapsam ya da değişen liste).
- **Otomatik yerleştirme KURAL MOTORU TUTMAZ** (`auto_place_entries`, F6 eki-2):
  yalnız SIRA ve TERCİH üretir, her yerleştirmeyi `place_entry`ye yaptırır ve
  reddedilen slotu atlar (`place_entry` kendi savepoint'inde koşar — `_seed_pool`
  emsali). Skorlama yaklaşıktır, kararı veren yerleştirmedir; ikinci bir mevzuat
  kopyası yazılırsa iki motor zamanla ayrışır. Üst makam sınavları OTOMATİK
  YERLEŞTİRİLMEZ (tarihleri ilgili makamın kılavuzunda — Yönerge md. 5), rapora
  gerekçesiyle düşer. Ceza demeti leksikografiktir (motor `_pair_penalty`
  deseni): `(3. sınav, kapasite aşımı, seviye günlük yükü, [geç gün], gün
  toplamı, saat)` — köşeli bileşen yalnız "son günden başla" açıkken (aşağıda).
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
- **Sınav haftaları VARSAYILANDIR, kısıt değil** (19.09.2026, kullanıcı kararı —
  "katı bir kısıtlama olmasın"): Bakanlığın ilan ettiği haftalar
  `sinav/official_windows.py`'de yıl bazında durur (2026-2027: ÖDSHGM
  10.09.2026 yazısı, metni `docs/mevzuat/`); `default_window` ilanı, ilan yoksa
  Yönetmelik kuralını (`statutory_window`) verir. Yalnız yeni takvimin ön
  tarihleri ve takvim sayfasındaki öneridir — takvim tarihi idarecinin kararıdır,
  yerleştirme buna göre REDDEDİLMEZ. Yeni yılın yazısı gelince tabloya yıl eklenir
  (önce metin `docs/mevzuat/`e). Otomatik yerleştirmenin "son günden başla"sı
  (yazı md. 7) da TERCİHTİR: ceza demetinde geç gün, gün toplamından ÖNCE gelir
  (`from_last_day`, varsayılan açık; kapalıyken eski dengeli yayma).
- **Ülke geneli sınavlar resmî GÜNE sabitlenir, saati idarecinindir**
  (19.09.2026, kullanıcı kararı): yazının eki `official_windows.NATIONAL_EXAMS`te
  (gün verir, ders saati VERMEZ). `apply_national_exams` havuzdaki (ders, düzey,
  YAZILI) girdiyi MINISTRY yapar — o turun yazılısı ülke geneli sınavdır — ve
  `place_entry` ile resmî güne, okulun ilk uygun sınav saatine SABİTLER (tek kural
  motoru; sert çakışan saat atlanır). Takvim oluşturulurken `_seed_pool` onu
  kendiliğinden koşar (hata yutulur); eski taslaklar için `national-exams` ucu.
  İdempotent: resmî gündeki girdinin SAATİNE dokunmaz (idareci düzeltti). Gün
  takvim aralığı dışındaysa YERLEŞTİRMEZ (ızgarada görünmeyen güne konmaz), girdi
  MINISTRY olarak havuzda bekler. Plan okulun AKTİF ÖĞRENCİSİ olan düzeylerden
  kurulur, derslerden değil — aksi hâlde havuzda olmayan ders sessizce kaybolurdu.
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

Ön yüz testleri kapıda KAPSAMLA koşar; eşikler `frontend/vitest.config.ts`te
(19.09.2026 ölçümü: satır %89,5 · dal %84,9 · işlev %63,2 → eşik 82/78/55). JSON
raporunun `success` alanı eşiği SÖYLEMEZ; kapı özet satırının varlığını ve
"does not meet" satırının yokluğunu ayrıca arar.

Kapı betiği GitHub'da da koşar (`.github/workflows/kapilar.yml` — her PR ve
main push'u; betiği OLDUĞU GİBİ çağırır, ikinci komut listesi tutulmaz). Bu
makinede Docker Desktop elle başlatılır; ana ağaçta düzenleme sürerken kapıyı
ayrı bir `git worktree` kopyasında koşmak iki işi birbirinden ayırır.

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
