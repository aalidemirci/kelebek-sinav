# Kelebek Sınav — Genel Tasarım ve Geliştirme Planı

*Tarih: 29.08.2026 · Durum: Kabul edildi (dört ana karar kullanıcı onaylı) ·
Kaynak analiz: [docs/kesif/2026-08-29-kesif-raporlari.md](../kesif/2026-08-29-kesif-raporlari.md)*

---

## 1. Altmış saniyede proje

Liseler için **tamamen çevrimdışı, tek kullanıcılı, girişsiz** bir masaüstü
programı (Windows 10/11 + Pardus 21/23): ortak sınavlarda öğrencileri kelebek
düzeniyle salonlara dağıtır, sınav takvimini mevzuat pencerelerine göre planlar
ve tüm salon/takvim evrakını PDF olarak üretir.

**Köken:** OYS'nin (okulapp — çok kullanıcılı Django+React okul yönetim
sistemi) `sinav_islemleri` + `ders_yapisi` modüllerinden **kod çıkarılarak**
türetilir. Mimari şablon: **disiplin-defteri-codex** (aynı kullanıcının kanıtlı
masaüstü mimarisi). Eski PySide6 "Kelebek Sınav" (apps/sinav-islemleri) temel
alınmaz — kullanıcı kalitesini beğenmedi; işlevsel referans dahi OYS'dir.

| Katman | Teknoloji |
|---|---|
| Backend | Django 5.1 + DRF 3.15, **SQLite** (WAL), Python **3.12** |
| Evrak | WeasyPrint 68.0 + pypdf 6.14.2 + openpyxl 3.1.5 (DD sabitlemeleri), DejaVu Sans gömülü |
| Frontend | React 18 + TypeScript + Vite + Tailwind (M3 "Mürekkep" kiti) |
| Masaüstü | pywebview + waitress (127.0.0.1, rastgele boş port) |
| Paket | Windows: PyInstaller onedir + Inno Setup · Linux: PyInstaller onedir → `.deb` |
| Güvenlik | Uygulama parolası (opsiyonel) + Fernet alan şifrelemesi + X25519 şifreli yedek |
| Sürüm | CalVer (`VERSION` dosyası) + `surum.json` DB damgası + GitHub Release |

Geliştirme yalnız Docker'da (host'a Python/Node kurulmaz); kapı zinciri
`scripts/gates.sh` (pytest cov≥75 → ruff → mypy strict → FE tsc/eslint/vitest).

---

## 2. Verilmiş kararlar

### 2.1 Kullanıcı kararları (29.08.2026)

| # | Karar | Seçim |
|---|---|---|
| U1 | Kapsam | **Tam kapsam, fazlı:** önce kelebek dağıtım + evrak (F1-F5), sonra sınav takvimi (F6), gözetmen (F7) |
| U2 | Gözetmen | **Elle listeden seçim, ayara bağlı (varsayılan kapalı).** Oto-atama alınmaz: OYS'de Tur 242'de program verisi eksikken askıya alınmış, Tur 459'da program+devamsızlık köprüleriyle yeniden açılmıştı — masaüstünde bu köprüler hiç olmayacağından aynı yanlış-seçim sorunu geri gelirdi. Salon başına 1 gözetmen + 5 salona 1 yedek + R6 tebliğ korunur |
| U3 | Şifreleme | **Parola + alan şifrelemesi ALINIR** (öneri düz SQLite idi; kullanıcı şifreleme istedi — bkz. §5) |
| U4 | Okul türü | **v1 yalnız Anadolu Lisesi çizelgesi gömülü**; seviye kümesi ve veri formatı okul türüne göre parametrik — diğer türler sonraki sürümlerde veri dosyasıyla gelir |

### 2.2 Teknik kararlar

| # | Karar | Gerekçe |
|---|---|---|
| K3 | PDF motoru WeasyPrint + pypdf + openpyxl, DD sabitlemeleriyle **aynen** (F0 itibarıyla 68.0 / 6.14.2 / 3.1.5) | ReportLab OYS'de reddedilmiş; DD şablonunda fontconfig çift-düzeltme + `--pdf-duman` hattı hazır |
| K5 | Ders havuzu = pakete gömülü MEB fixture md + ilk açılışta idempotent tembel tohum (`ensure_meb_catalog` + `ensure_course_aliases`) | Çevrimdışı güncelleme yolu = CalVer uygulama sürümü; UI'dan elle ekleme/pasifleştirme; `is_active=False` import'la geri açılmaz |
| K6 | Python 3.12 sabit | DD Linux build zinciri `python:3.12-bullseye` (glibc 2.31 = Pardus 21) |
| K7 | CalVer + `VERSION` + `surum.json` (dosya, tablo değil) + updates.py | DD'den birebir; eski exe yeni DB'yi açmaz |
| K8 | Tek pywebview penceresi; içeride React Router rotaları + panel sekmeleri | OYS FE düzeni zaten böyle; çok pencere pywebview/waitress karmaşası |
| K9 | Yedek: günlük açılış yedeği + rotasyon, `Connection.backup()` RAM görüntüsü (dosya kopyalama asla — WAL), migrate öncesi ayrı yedek, `.ksbak` + yeni magic | DD deseni; **DD'deki "parolasız kipte günlük yedek atlanır" dalı düzeltilir: parolasızsa düz, parolalıysa X25519 şifreli — yedek her gün alınır** |
| K10 | Öğrenci girişi: DD import boru hattı (xlsx VE pano → aynı rows matrisi, dry-run/commit, sha256 idempotency uyarısı, fuzzy TR sütun eşleme, "boş hücre silmez") | e-Okul PDF parser'ları v1'de alınmaz (pypdf glif/bitişme riskleri OYS kodunda belgeli); **TCKN hiç toplanmaz** |
| K11 | `Course.levels` JSON + Python süzme | SQLite'ta `levels__contains` yok; ~60 ders için ara tablo maliyetine değmez |
| K12 | `statutory_window` + `_daily_exam_load` (öğrenci-bazlı günlük limit) alınır | Mevzuat çekirdeği (Yönetmelik md. 45, Yönerge md. 5/1-ç, ADR-0044 karar 13) |
| K13 | Kitapçık (R10) + Word soru şablonu alınır, **senkron** | booklet.py/word_template.py saf; 90×4 sayfa < 30 sn masaüstünde kabul edilebilir |
| K14 | F27 anonimleştirme (ARŞİV + 730 gün) korunur; Celery beat yerine **açılışta aday tespiti + kullanıcı onaylı geri dönüşsüz tetik** | KVKK saklama süresi gerekçesi geçerli kalır |
| K16 | Klasik düzen (HOME_CLASSROOM) alınır | Yoklama/kitapçık/tutanak tek SeatAssignment altyapısından; kesmek evrak setini ikiye bölerdi |

### 2.3 Kimlik sabitleri (F0'da toplu — DD kalıntısı sıfır toleranslı)

`KS_*` env öneki (DD'de 17 `DD_*` env: 13 çalışma zamanı + 4 derleme betiği) · veri dizini `kelebek-sinav`
(%LOCALAPPDATA%, Roaming/OneDrive asla) · çerez `ks_oturum` · `X-KS-Token` ·
yedek uzantısı `.ksbak` + yeni magic · AppUserModelID · **Inno AppId GUID
mutlaka yeni üretilir** (yoksa Disiplin Defteri kurulumlarıyla çakışır) ·
AppMutex `KelebekSinav`.

---

## 3. Bağımlılık kesim listesi (OYS → tek kullanıcılı çevrimdışı)

Doğrulanmış kritik gerçek: **hiçbir başka OYS app'i `sinav_islemleri`'nden
Python import'u yapmıyor** — modül temiz kesilir. Dış referansların tümü string
düzeyinde: denetim app'i (kvkk_media_scope 2, kvkk_scope 6, services 5,
anonymize_database ~8 kayıt), core purge/reset yönetim komutları, bildirim
takvim sinyal alıcıları ve config settings kayıtları. Ayrıca `ders_yapisi`
selectors/services `ExamSessionCourse`'a `get_model` ile erişir (ters yönde
çalışma zamanı bağı) — iki modül birlikte taşındığından kesimi engellemez.

| # | Bağlanma noktası | Karar | Karşılık |
|---|---|---|---|
| B1 | DRF izinleri / roller (`permissions.py`) | KALDIR | DD kalıbı: authsuz DRF + `desktop/session_guard.py` belirteci (fail-closed 403) |
| B2 | FE auth (Bearer + 401 refresh; rol kodu yalnız 3 takvim dosyasında) | KALDIR | DD authsuz `lib/api.ts` (aynı `ApiError{status,code,message,fields}`); `CAN_VIEW/CAN_APPROVE` bayrakları `true` |
| B3 | Celery (2 görev: kitapçık + gece anonimleştirme) | SADELEŞTİR | `generate_booklets_for_run` zaten senkron çağrılabilir → doğrudan çağrı; anonimleştirme → K14. Celery/Redis pakete hiç girmez |
| B4 | Takvim onayında bildirim sinyali (tek dış sinyal) | KALDIR | Snackbar yeter |
| B5 | `gorevlendirme` köprüsü (`absent_staff_ids`) | KALDIR | Kod köprüsüz boş kümeye zaten zarif düşüyor; havuz = aktif personel − muaf |
| B6 | `program` köprüsü (`teachers_free_at`, zil çizelgesi) | SADELEŞTİR | Oturum saati serbest giriş + ayarlanabilir varsayılan saat listesi |
| B7 | `zumre` imza köprüsü | KALDIR | Modülsüz dal (derslerden boş imza çizgileri) kalıcılaşır |
| B8 | `ders_yapisi` köprüsü (Course FK, `course_level_student_ids` vb.) | YERELLEŞTİR | Course yerel tablo (`db_table` bagajı atılır); öğrenci kümesi yerel `(level, section)` kayıtlarından; kayıt verisi yoksa "seviyenin tamamı" **konservatif düşüşü aynen korunur** |
| B9 | `core` köprüsü (Student/Personnel/SchoolYear/SchoolConfig) | YERELLEŞTİR | DD çekirdeğinden: SchoolConfig(pk=1)+kurulum kapısı, Personnel, Student (veli alanları atılır), ImportRun+parser'lar, SchoolYear |
| B10 | Nakil ön-kontrolü (sihirbaz Adım 0, Yönerge md. 5/1-v) | SADELEŞTİR | Kullanıcı beyanlı onay kutusu; "kim/ne zaman" damgası korunur |
| B11 | AuditLog/denetim/AccessLog | KALDIR | KVKK yükü yerelde: F27 anonimleştirme + `veri_sizintisi.py` paket denetimi + şifreleme (U3) |
| B12 | "Hazırlayan onaylayamaz" çift-kişi takvim kuralı | SADELEŞTİR | SUBMITTED tek tıkla geçilir; **APPROVED kilidi ve onay damgaları kalır** (resmî evrak değeri) |
| B13 | Postgres `levels__contains` | UYARLA | Python süzme (K11) |
| B14 | Postgres DateRangeField/ExclusionConstraint (LessonGroup zinciri) | ALMA | Porta girmeyen modellerde; migration ağacı 0001'den |
| B15 | `select_for_update`, çok-yıl eşzamanlılık | SADELEŞTİR | Tek yazar; SQLite WAL + `transaction_mode=IMMEDIATE` |
| B16 | X-Accel-Redirect medya | UYARLA | Doğrudan `FileResponse` + FE `saveBlob` |
| B17 | `BaseModel.created_by` (User FK) | UYARLA | User yok → alan düşer; soft-delete + koşullu unique aynen (SQLite kısmi index DD'de kanıtlı) |
| B18 | e-Okul/AI ders adı çözüm zinciri + PDF parser'lar | ALMA (v1) | Şablon+pano+xlsx yolu; **CourseAlias SEED dosyası yine taşınır** (xlsx'teki ders adları da MEB adına çözülmeli) |
| B19 | FE Celery polling (SorularPaneli 4 sn) | SADELEŞTİR | Senkron üretim + tek istek |

---

## 4. Veri modeli (özet)

**Okul çekirdeği (DD'den uyarlanır):** `SchoolConfig` (pk=1, okul adı/ilçe/tür,
`setup_completed`) · `SchoolYear` (tek aktif) · `Personnel` (ad-soyad*, branş,
unvan, `is_active`, gözetmen muafiyeti ayrı tabloda) · `Student` (ad*, soyad*,
okul no, `class_level`, `class_section` — **veli ve TCKN alanları yok**) ·
`ImportRun` (source_type, sha256, koşullu unique).

**Ders havuzu (OYS ders_yapisi'ndan):** `Course` (name, `levels` JSON,
course_type ORTAK/SECMELI, source MEB/MANUAL, `is_active`) ·
`CurriculumFramework` + girdileri (program_key, version — idempotent upsert) ·
`CourseAlias` (SEED + OPERATOR; OPERATOR SEED'i ezer, tersi asla).
`VALID_COURSE_LEVELS` **SchoolConfig'den türetilir** (v1: 0=Hazırlık, 9-12).

**Sınav çekirdeği (OYS sinav_islemleri'nden):** `ExamRoom` (plan JSON: grid ≤
30×30, SINGLE/DOUBLE/TRIPLE sıralar, kapı/tahta/öğretmen masası; kapasite
plandan) · `ExamSession` (durum makinesi DRAFT→DISTRIBUTED→APPROVED→ARCHIVED,
`layout_mode` BUTTERFLY/HOME_CLASSROOM, `distribution_params` ile seed) ·
`ExamSessionCourse` (**baştan tek-seviyeli** — Tur 241 dersi; `shared_booklet`)
· `ExamSessionRoom` · `SeatAssignment` (SNAPSHOT: ad/no/şube* kopyası;
`conflict_group`; NORMAL/PINNED/MANUAL) · `ExamAttendanceRecord` (girmeyen +
mazeret; arşivde güncellenebilir — MEB 5 iş günü) · `PlacementRule` (4 tip;
SESSION > PERMANENT; gerekçe **yalnız kategori** — KVKK md. 6 tasarımı aynen) ·
`ProctorAssignment`/`ProctorExemption` (U2) · `QuestionDocument` + `BookletRun`
· `ExamCalendar` + `ExamCalendarEntry` + `ExamTrackItem/Mark` (F6).

(*) işaretli alanlar şifrelenir — bkz. §5.

**Motor sözleşmeleri (aynen korunur):**
- Çakışma birimi `(course, level)`; anahtar `"<course_id>:<level>"`, ortak
  kitapçıkta `"<course_id>:*"`. Şube kısıt DEĞİL; motor yalnız grup anahtarı görür.
- Sert kısıt: aynı gruptan iki öğrenci **aynı masada** oturamaz — denetim
  `(desk_row, desk_col)` kimliğinden, mesafeden değil. Katı mod 1. halkayı
  (Chebyshev ≤ 1) serte çevirir.
- Determinizm: aynı seed → aynı sonuç; seed yoksa üretilip
  `distribution_params.seed`'e yazılır ve R8'de basılır.
- Çift denetim: motorun her çıktısı **bağımsız `validator.py`**'den geçer;
  onay yalnız ihlal=0 ise.

---

## 5. Şifreleme tasarımı (U3 — kullanıcı kararı)

DD'nin kanıtlı katmanı taşınır: `shared/crypto.py` (Fernet + Argon2id) +
`app_password` servisi (etkinleştir/kaldır/kurtarma anahtarı) + FE
`GuvenlikKapisi` + "Şimdi kilitle".

- **Şifrelenen alanlar:** `Student.first_name/last_name`,
  `Personnel.first_name/last_name` ve **tüm SNAPSHOT kopyaları**
  (`SeatAssignment.full_name`, `ExamAttendanceRecord`, `ProctorAssignment.teacher_name`).
  Kaynak şifreli olup snapshot düz kalsaydı şifreleme anlamsızlaşırdı.
- **Açık kalanlar:** okul no, sınıf/şube, koltuk/salon/grup düzeni (ad
  olmadan takma-adlıdır; motor, sıralama ve teklik bunlara dayanır).
- **Bedeller (bilinçli kabul):** ad temelli arama/sıralama/teklik DB'de
  çalışmaz → Python tarafında (~600-1000 kayıt; DD F5-D5 dersi: selector
  dolambacı baştan kurulur, migration acısı yaşanmaz — alanlar **doğuştan**
  `EncryptedCharField`). Parola süreç ömrünce bellekte (DD kabulü); boşta
  kilit yok, kilitleme = kapatma veya "Kilitle".
- **Yedek:** parola etkinken X25519 şifreli `.ksbak`; parolasızken düz
  `.ksbak`. Her iki kipte de günlük yedek **alınır** (K9 düzeltmesi).
- TCKN, veli, sağlık serbest metni **hiç toplanmaz** — en iyi KVKK önlemi
  veriyi hiç edinmemektir; şifreleme buna ek katmandır.

---

## 6. e-Okul içe aktarma planı

- **Öğrenci:** e-Okul sınıf/okul listesi xlsx **veya pano yapıştırma** → aynı
  `rows` matrisi (DD `read_sheet`/`text_to_grid`). Kritik sütunlar:
  sınıf/şube + okul no + ad-soyad (TCKN'siz). Fuzzy TR sütun eşleme (sinonim
  sıralaması kritik), başlık ilk 10 satırda aranır; `normalize_class_section`
  ("10/A", "10-A", "10 A") — **seviye aralığı okul türünden parametrik** (U4).
- **Öğretmen:** e-Okul/MEBBİS personel listesi xlsx/pano (e-Okul personel
  PDF'inde TCKN/e-posta yok — zaten toplamıyoruz). Upsert anahtarı normalize
  ad-soyad (DD kabulü, ≤100 personel).
- **Desen:** dry-run (atomic + `set_rollback`) → rapor (`ImportIssue`
  satır/alan/sorun/maskeli değer) → kullanıcı raporu gördükten sonra "Aktar";
  sha256 idempotency **uyarısı**; "boş hücre mevcut veriyi silmez";
  created/updated/unchanged ayrı sayılır.
- **İndirilebilir şablonlar:** başlık + örnek satır + yönerge sayfası
  (OYS'nin zengin şablonuyla DD minimalizminin ortası).
- Import sonrası görülen `(level, section)` çiftleri **şube kataloğu tohumu**
  olur (salon-şube eşleme ve R2k için).
- e-Okul PDF parser'ları (OOG01001R070, OOK01001R1) v1'de **alınmaz**; teknik
  borca yazılır (pypdf glif/bitişme riskleri OYS kodunda belgeli).

## 7. MEB ders havuzu planı

- Gömülü veri: [data/ders-cizelgeleri/](../../data/ders-cizelgeleri/)
  `anadolu-lisesi-2025-2026.md` (64 ders katalo­ğu, TTK 09.05.2025/05) +
  `cerceveler/` (AL + AL-Hazırlık saat matrisleri) + `ders-adi-takma-adlari.md`
  (~55 takma ad) — okulapp'tan kopyalandı, format aynı.
- Parser'lar saf ve aynen taşınır: `catalog_parser`, `curriculum_parser`,
  normalize yardımcıları (`_match_key`, `titlecase_tr`,
  `repair_truncated_course_name` — çıplak `.upper()/.lower()` TR'de yasak).
- İlk açılışta idempotent tohum; UI: ders havuzu sayfası (liste + elle ekle +
  pasifleştir + mükerrer tespiti/birleştirme `consolidate_duplicate_course`).
- Yeni okul türü = yeni md dosyası + `program_key`; kod değişikliği gerekmez
  (U4 altyapı şartı). Seçmeli bütçesi türetilir: 40 − ortak toplam.

---

## 8. Arayüz planı (M3 "Mürekkep")

DD'nin 23 bileşenlik M3 kiti + Tailwind token altyapısı aynen (`rgb(var(--*))`
CSS değişkenleri; ham renk/px yasak; M3 token bütünlüğü testi taşınır).

Rotalar (tek pencere, lazy): **Hub** → Oturumlar → Oturum Detayı (sekmeler:
Yerleşim/Gözetmen/Sorular/Yoklama/Çıktılar) → Salonlar (+ Salon Editörü) →
Ders Havuzu → Takvimler → Takvim Detayı (Havuz/Yerleştirme/Takip) → Kişiler
(öğrenci/öğretmen + içe aktarma) → Ayarlar/Kurulum sihirbazı.

Korunan FE desenleri: 5 adımlı sınav sihirbazı (Adım 0 beyanlı nakil onayı) ·
salon editörü **palet + tıkla-yerleştir** (DnD bilinçli yok — ADR-0016) ·
koltuk **tıkla-seç-tıkla takas** (kurala takılırsa Türkçe uyarı) · koltuk
numaralandırma önizlemesi backend'den (`preview-seats` — iş kuralı tek yerde) ·
çakışma grupları 6 tonluk renk rozetleri · React Query tek `queryClient`
(staleTime 30 sn, 4xx retry yok, mutasyon→invalidate+snackbar) · Dialog
`onClose` useCallback disiplini · `formatDate` gg.aa.yyyy + `todayIso()`
(UTC yasağı) · Türkçe yerel arama `toLocaleLowerCase('tr')`.

Hızlı başlangıç: `generate-section-rooms` — her aktif şubeye 40 koltuklu
(4 sütun × 5 sıra, ikili) derslik üretimi, idempotent.

---

## 9. Evrak kataloğu

R1 salon krokisi · R2 salon yoklama-imza · R2k şube yoklama · R3 kapı listesi ·
R4 duyuru (okul geneli alfabetik arama) · R5 Excel çizelge (openpyxl) ·
R6 gözetmen tebliğ-tebellüğ (yalnız gözetmen ayarı açıkken) · R7 zarf
kapağı/tutanak · R8 dağıtım doğrulama raporu (seed basılır) · R9 teslim
tutanağı · R10 kişiselleştirilmiş kitapçık ZIP · oturumsuz boş salon planı ·
resmî takvim PDF (A4 yatay) · Word soru şablonu (stdlib zipfile) · tümü-ZIP.

Şablonlar: `templates/sinav_islemleri/reports/` 11 dosya + `booklet_overlay` +
`calendar_pdf` + **`print/_design.css` ("Kurumsal Sade": `--pr-*` token'ları,
DejaVu, `text-transform` YASAK — WeasyPrint TR i→I tuzağı, `|unlocalize`
zorunlu)** birlikte kopyalanır.

Kitapçık invariantları: bant üst 4mm + 32mm ≤ 40mm; soru PDF'i **ölçeklenmez**
(1:1); A4 dikey ±6pt yükleme doğrulaması; ≤2 sayfa→bant yalnız 1. sayfada,
>2→tek sayfalarda; salon başına tek WeasyPrint render (90×4 sayfa < 30 sn).

## 10. Mevzuat invariantları (testlerle sabitlenecek)

Tam metinler: [docs/mevzuat/](../mevzuat/). Kelebek düzeni/S-numaralandırma/
paketleme mevzuatta YOK (ODSGM/İl MEM kılavuz geleneği) → "kılavuz uyumlu
varsayılan, ayarla değiştirilebilir" ilkesi.

- Takvim pencereleri (Yönerge md. 5/1-ç): 1D1S Ekim, 1D2S Aralık, 2D1S Mart,
  2D2S Mayıs — ayın son Pazartesisi + 11 gün (`statutory_window`); dönemde 2
  sınav; 3. tur dönemin son iki haftası elle.
- Günlük sınav limiti **öğrenci-bazlı**: 3. sınav = uyarı (OKY md. 45),
  ≥4 = sert hata; kayıt verisi olmayan ders "seviyenin tamamı" sayılır
  (konservatif düşüş korunmalı).
- Sınav süresi varsayılan 40 dk; tavan bir ders saati (md. 5/1-l).
- Mazeret bildirimi 5 iş günü (md. 5/1-y) → yoklama mazereti **arşivde de**
  güncellenebilir.
- Onay yalnız ihlal=0'da; APPROVED kilidi + onay damgası (tek kullanıcıda da).
- Nakil ön kontrolü beyanı (md. 5/1-v) damgalı.
- Uyarı/hata metinlerinde öğrenci ADI asla — okul no kullanılır.

---

## 11. Çıkarım haritası (AYNEN / UYARLA / ALMA)

### AYNEN (kopyala; import yolları dışında dokunma)
OYS: `engine.py` (533) · `validator.py` (162) · `layout.py` (331) ·
`booklet.py` (225) · `word_template.py` (110) · `participants.py` (260) ·
rapor şablonları (11) + `booklet_overlay.html` + `calendar_pdf.html` +
`print/_design.css` · ders_yapisi saf parser'ları + normalize yardımcıları ·
`data/ders-cizelgeleri/*.md` · FE `planEdit.ts`, GROUP_TONES, REPORT_CATALOG,
RoomEditor/YerlesimPaneli grid kimliği kalıpları.
DD: `desktop/` tamamı (main, errors 0-8, lock, session_guard, integrity,
paths, logging_setup, server, window, django_bootstrap, version) ·
`packaging/veri_sizintisi.py` · fontconfig çift-düzeltme · pyinstaller spec
kalıbı · Inno/deb betikleri + kap-ici-test.sh · gates.sh · FE ui/ M3 kiti +
lib/ + KurulumKapisi + queryClient · koruma testleri (format.test.ts tarih
disiplini, App.test.tsx M3 token bütünlüğü) · updates.py · `shared/crypto.py`
+ `app_password` + GuvenlikKapisi (U3).

### UYARLA
`models.py` (created_by düşer; soft-delete + koşullu unique + SNAPSHOT kalır;
şifreli alanlar doğuştan; migration 0001'den) · `services.py` 2354 (Celery→
senkron; 5 köprü yerel arayüze — **fonksiyon imzaları korunarak**) ·
`services_calendar.py` (çekirdek aynen; onay tek-kullanıcı; bildirim dalı
silinir) · selectors/serializers/views/urls (izinler düşer; GET+POST tek-action
— Tur 644 dersi) · `reports.py` (zümre imza dalı → boş çizgi) · FE `api.ts` →
DD authsuz istemci · `SinavSihirbazi` (Adım 0 beyan; sectionsApi yerel uca) ·
GozetmenlerPaneli (havuz = aktif personel − muaf) · SorularPaneli (senkron) ·
DD `backup.py` (iki kipte de günlük yedek) · DD import çekirdeği (veli/TCKN
alanları atılır; `_ensure_student_classes` → şube kataloğu tohumu) ·
ders_yapisi services (Python süzme; mükerrer + consolidate + CourseAlias).

### ALMA
`permissions.py`, boş `signals.py`, Celery `tasks.py`, `admin.py` · denetim
app'i + kvkk_scope kayıtları · bildirim modülü · gorevlendirme/program/zumre
köprü uçları · LessonGroup/LessonEnrollment/TeachingAssignment + btree_gist ·
`db_table='sinav_islemleri_course'` bagajı · e-Okul PDF parser'ları + AI ders
adı zinciri (v1) · FE useAuth/Bearer altyapısı · DD'den: Holiday/iş-günü
motoru, ClassResponsibility (tohum fikri hariç), year_rollover, imha, disiplin
app'i, guardian_* alanları.

---

## 12. Faz planı ve doğrulama kapıları

| Faz | İş | Kapı |
|---|---|---|
| **F0 İskelet** | DD'den şablon türetme; §2.3 kimlik sabitleri toplu değişimi; boş Django+FE ayakta; WeasyPrint requirements'a **F0'da** girer (hiddenimports/fontconfig erken yakalansın) | Windows exe açılır/kapanır; çıkış kodları 0-8 testleri; `--pdf-duman` (ĞÜŞİÖÇ + DejaVu /BaseFont) geçer; gates.sh yeşil |
| **F1 Çekirdek veri** | SchoolConfig + kurulum sihirbazı + health ucu; SchoolYear; Personnel; Student; **şifreleme + parola katmanı (doğuştan)**; import boru hattı (şablon + xlsx + pano); Course + MEB tohumu + CourseAlias; şube tohumu | dry-run/commit parite testleri; tohum idempotentliği; TR sütun eşleme; şifreli kipte ad-temelli selector testleri |
| **F2 Salon + motor** | ExamRoom + plan JSON + RoomEditor + preview-seats; engine/validator/layout/participants kopyası; generate-section-rooms | Saf motor test omurgası yeşil: aynı-seed determinizm, satranç modu, S-rota 2D tuzağı, pin sabitliği, rastgele senaryolarda ihlal=0 |
| **F3 Oturum akışı** | 5 adımlı sihirbaz; ExamSession+Course (tek-seviyeli); dağıtım+seed; durum makinesi; PlacementRule 4 tip; takas; yoklama; SNAPSHOT. Sapma: katılımcı tipi yalnız LEVEL/SECTIONS — OYS'deki GROUPS (şube-içi grup) alınmadı (TB7); Adım 0 nakil özeti veri sorgusu yerine beyan + son içe aktarma tazeliği (B10) | Uçtan uca senaryo; onayda ihlal=0 şartı; arşivde mazeret güncellenebilir |
| **F4 Evrak seti** | R1-R5, R7-R9 + boş plan + tümü-ZIP; _design.css; ARCHIVED yeniden basım | Her raporda TR karakter duman testi; `text-transform` tarama testi; `|unlocalize` denetimi |
| **F5 Kitapçık** | R10 senkron + A4 ±6pt doğrulama + Word şablonu | Bant ≤ 40mm invariantı; sayfa kuralları; 90×4 < 30 sn |
| **F6 Takvim** | ExamCalendar + statutory_window + grid + günlük limit + slot→oturum + takvim PDF | Pencere hesabı + öğrenci-bazlı limit senaryoları |
| **F7 Gözetmen** | Elle atama; salon başına 1 + yedek; R6; yeniden dağıtımda sıfırlama | Ayar kapalıyken R6 katalogda görünmez |
| **F8 Bakım** | Günlük yedek+rotasyon (iki kip); F27 elle-tetik anonimleştirme; surum.json; updates.py+UpdateBanner | Eski exe yeni DB'yi açmaz; anonimleştirme sonrası yeniden basım kırılmaz |
| **F9 Paketleme** | PyInstaller onedir + Inno (yeni GUID, WebView2 gömülü) + .deb (bullseye; pango/fontconfig Depends); kap-ici-test debian 11+12; veri_sizintisi.py ×2 platform | Temiz Windows 11 ve Pardus 21'de: kurulum → sihirbaz → içe aktarma → dağıtım → R1 PDF uçtan uca |

## 13. Riskler

1. **hiddenimports körlüğü (DD borç K7):** WeasyPrint/pypdf/openpyxl zinciri
   spec'e elle eklenmezse testler geçer, paket sahada çöker → F0 pdf-duman kapısı.
2. **services.py köprü uyarlaması** en riskli kalem: fonksiyon imzaları
   korunmazsa motor/rapor testleri sessizce anlamını yitirir.
3. **Şifreleme bedeli (U3):** ad-temelli her sorgu Python'a taşınmalı;
   atlanan tek sorgu şifreli kipte sessiz boş sonuç verir (DD F5-D5 vakası).
   Selector disiplinini F1'den kurmak şart.
4. **Konservatif düşüş kaybı:** günlük limitte "kayıtsız ders = seviyenin
   tamamı" kuralı gevşetilirse mevzuat denetimi delinir.
5. **Fontconfig/DejaVu:** fonts.conf'ta DOCTYPE kalırsa sessiz ret → bozuk
   Türkçe evrak; build.ps1 ezme adımı atlanmamalı.
6. **Kimlik çakışması:** Inno AppId GUID yenilenmez veya `DD_*` kalıntısı
   kalırsa iki uygulama aynı makinede veri karıştırır.
7. **UTC tarih tuzağı:** 00:00-03:00 arası bir gün geri kayma —
   format.test.ts koruma testi taşınmazsa sınav tarihli evrakta nüksedebilir.
8. **Tek okul türü verisi (U4):** farklı türde çalışan kullanıcı için havuz
   boş başlar → elle ekleme F1'de eksiksiz olmalı.
9. **F27 geri dönüşsüz:** onay diyaloğu + aday listesi olmadan tetiklenirse
   veri kaybı şikâyeti kaçınılmaz.
10. **Takvim damgaları:** tek-kullanıcı sadeleştirmesi onaylayan/tarih
    damgalarını silerse basılan takvim PDF'inin resmî değeri düşer.

## 14. Açık işler / teknik borç başlangıcı

- e-Okul PDF parser'ları (şube listesi, personel) → v2 adayı.
- Diğer okul türü çizelgeleri (Fen/SB/Meslek/İH) → veri dosyası küratörlüğü.
- Ortaokul/ilkokul kademesi → seviye kümesi parametrik olduğunda değerlendirilir.
- okulapp.org yayın alanı: sürüm kartı + tanıtım sayfaları (DD deseni;
  `okulapp.org/CLAUDE.md` "Ortak çalışma düzeni"ne tabi).
