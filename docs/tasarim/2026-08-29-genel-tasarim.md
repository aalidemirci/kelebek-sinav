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
| U4 | Okul türü | Seviye kümesi ve veri formatı okul türüne göre parametrik. **03.09.2026 revizyonu:** sekiz ortaöğretim türünün TTK çizelgeleri program dosyası olarak gömülü; havuz okulun yürürlükteki çizelgesinden türetilir, kademeli dönüşüm seviye bazlı atamayla (§7.2) |

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
| K17 | Linux pencere motoru **PyQt5 + QtWebEngine** (F9'da kayda geçti — karar F0 paket iskeletinden) | WebKitGTK/PyGObject yolu ELENDİ: typelib paketleme + Pardus 21/23 ABI oynaklığı. PyQt5 tekerlekleri manylinux2014 (glibc 2.17) olduğundan bullseye derlemesi Pardus 21'de çalışır. Qt'nin sistemden beklediği X/GL/ses kütüphaneleri `.deb` Depends'ine girer — tek doğruluk kaynağı `packaging/linux/build.sh::DEPENDS_QT` |
| K19 | **Takvim havuzu ORTAK + YAZILI derslerle açılır**; seçmeliler seviye/şube kapsamı seçilerek eklenir. `Course.exam_mode` (YAZILI/UYGULAMA/YOK) çizelgenin isteğe bağlı 4. sütunundan gelir (31.08.2026) | Saha geri bildirimi: kataloğun tamamı havuza basılınca ~175 girdi çıkıyor, idareci sınavı yapılacak ~30 girdi kalana dek tek tek siliyordu. Karar gerekçesi, alternatifleri ve sonuçları **§7.1**'de |

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
| B7 | `zumre` imza köprüsü | UYARLA (30.08.2026 revizyonu) | Zümre yapısı okul app'inde yerelleşti (`okul.SubjectDepartment`: ad + başkan→Personnel + kurul üyeliği); imza bloğu takvim başına seçilir (`ExamCalendar.signatory_departments`). Seçim yoksa OYS'nin modülsüz dalı (derslerden boş imza çizgileri) yedek yol olarak DURUR |
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
`ImportRun` (source_type, sha256, koşullu unique) · `ClassSectionGroup`
(şube kümesi SAY/EA/DİL — `ClassSection.group` FK, TEK üyelik) · `SubjectDepartment`
(zümre adı, başkan→`Personnel`, `is_board_member` — okul zümre başkanları
kurulu; sınav takvimi imza bloğunun kaynağı, B7 revizyonu).

**Ders havuzu (OYS ders_yapisi'ndan):** `Course` (name, `levels` JSON,
course_type ORTAK/SECMELI, source MEB/MANUAL, `is_active`, **`exam_mode`
YAZILI/UYGULAMA/YOK** — 31.08.2026 K19; çizelgenin isteğe bağlı "Sınav"
sütunundan gelir, varsayılan YAZILI) ·
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
`ExamRoomGroup` (derslik kümesi Sabah/Öğle — `ExamRoom.group` FK, TEK üyelik;
`block` ALANINDAN AYRI: blok evraka basılır, küme basılmaz) ·
`PlacementRule` BEŞ tipli (BELIRLI_KOLTUK eklendi) + koltuk koordinatı
(`target_desk_row/col/slot` — `seat_no` DEĞİL) + `seat_preference` (ön/arka,
odak = öğretmen masası) + `solo_desk` (sıra tek başına; kapasite azalır) ·
`ExamCalendarEntry.authority` (SCHOOL/MINISTRY/PROVINCIAL/DISTRICT — sınavı
hazırlayan makam; teklik kısıtına GİRMEZ) · `ExamCalendar.footnote_text`
(düzenlenebilir dipnot, varsayılandan kopyalanır) + `signatory_departments`
(M2M → `okul.SubjectDepartment`) · `ExamCalendarEntry.participant_type` +
`section_ids` (LEVEL/SECTIONS — `ExamSessionCourse` ile **birebir aynı kalıp**;
31.08.2026 K19). Girdinin `level`'ı zorunlu ve teklik anahtarının parçası
olduğundan yön oturum tarafının TERSİDİR: seviye verilir, şubeler ona karşı
denetlenir. Şube kümesi kimliği girdiye YAZILMAZ — seçim anında somut şube
pk listesine açılır (§10 kümeler invariantı).

(*) işaretli alanlar şifrelenir — bkz. §5.

**Motor sözleşmeleri (aynen korunur):**
- Çakışma birimi `(course, level)`; anahtar `"<course_id>:<level>"`, ortak
  kitapçıkta `"<course_id>:*"`. Şube kısıt DEĞİL; motor yalnız grup anahtarı görür.
- Sert kısıt: aynı gruptan iki öğrenci **aynı masada** oturamaz — denetim
  `(desk_row, desk_col)` kimliğinden, mesafeden değil. Katı mod 1. halkayı
  (Chebyshev ≤ 1) serte çevirir.
- Determinizm: aynı seed → aynı sonuç; seed yoksa üretilip
  `distribution_params.seed`'e yazılır ve R8'de basılır.
- **Ceza demeti (31.08.2026, K18):** `_pair_penalty` LEKSİKOGRAFİK ikili döner
  `(birincil, ikincil)`. Birincil bugünkü skalerin BİT BİT aynısıdır (aynı sıra
  = ∞ sert kısıt); ikincil yalnız komşu çiftlerde çiftin ODAĞA (öğretmen masası,
  `layout.reference_cell`) uzaklığıdır. İkincil ancak birincil TAM EŞİTKEN karar
  verir → ihlal sayısı (birincilin ∞ olduğu çift sayısı) YAPISAL OLARAK artamaz.
  Yeni rng çekilişi yoktur; determinizm korunur.
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

- **Öğrenci:** e-Okul sınıf/okul listesi **veya pano yapıştırma** → aynı
  `rows` matrisi (DD `read_sheet`/`text_to_grid`). Kritik sütunlar:
  sınıf/şube + okul no + ad-soyad (TCKN'siz). Fuzzy TR sütun eşleme (sinonim
  sıralaması kritik), başlık ilk 10 satırda aranır; `normalize_class_section`
  ("10/A", "10-A", "10 A") — **seviye aralığı okul türünden parametrik** (U4).
- **Öğretmen:** e-Okul/MEBBİS personel listesi (dosya/pano; e-Okul personel
  PDF'inde TCKN/e-posta yok — zaten toplamıyoruz). Upsert anahtarı normalize
  ad-soyad (DD kabulü, ≤100 personel).
- **Gerçek e-Okul biçimi (30.08.2026 düzeltmesi, F1 varsayımının revizyonu):**
  e-Okul'un "Excel" düğmesi `.xlsx` DEĞİL, **Excel 97-2003 (.xls / BIFF8)**
  üretir ve dosya BÜYÜK harfli `.XLS` uzantısıyla iner — openpyxl bu kabı hiç
  açmaz, bu yüzden `xlrd` eklendi ve `read_sheet` kap imzasına göre yol seçer.
  Ayrıca **sınıf listesi (OOG01001R020) düz tablo değildir:** tek sayfada şube
  şube bloklar hâlinde gelir ve **sınıf/şube için sütun yoktur** — bilgi yalnız
  blok başlığındadır (`AL - 10. Sınıf / A Şubesi …`). Blokları düzleştirip
  sentetik "Sınıf/Şube" sütunu yazan, sayaç dipnotlarını boşaltan önişleyici:
  `apps/okul/eokul.py` (satır numaraları korunur — uyarılar Excel'deki satırla
  aynı kalsın). **Şube harfi ASCII'ye KATLANMAZ:** e-Okul şubeleri Türk
  alfabesi sırasıyla açar, yani aynı okulda hem `10/I` hem `10/İ` bulunur;
  katlama iki sınıfı tek şubeye çökertirdi (`normalize.tr_upper`).
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

- Gömülü veri: [data/ders-cizelgeleri/](../../data/ders-cizelgeleri/) —
  okul türü başına **program dosyaları** (`<program_key>.md`; 03.09.2026'da
  15 dosya: AL, Fen, SBL ve hazırlık varyantları, AİHL (+program/proje),
  GSL dört bölüm, Spor (+tematik), MTAL ortak dersler) +
  `ders-adi-takma-adlari.md` (~55 takma ad). Eski birleşik
  `anadolu-lisesi-2025-2026.md` ve OYS'den kopyalanan `cerceveler/` (KS'de
  hiç tüketilmeyen saat matrisleri) kaldırıldı — bkz. §7.2.
- Parser'lar saf ve aynen taşınır: `catalog_parser`, `curriculum_parser`,
  normalize yardımcıları (`_match_key`, `titlecase_tr`,
  `repair_truncated_course_name` — çıplak `.upper()/.lower()` TR'de yasak).
- Çizelge tablosunun **isteğe bağlı 4. sütunu "Sınav"**: `YAZILI` / `UYGULAMA` /
  `YOK`. Sütun yoksa veya hücre boşsa `YAZILI` sayılır — üç sütunlu dosyalar
  (`cerceveler/*.md` ve elle yazılmış eski çizelgeler) değişmeden çözülür.
  Tanınmayan etiket satırı, mevcut hata kalıbındaki gibi, `errors`'a düşürür ve
  satır atlanır.
- İlk açılışta idempotent tohum; UI: ders havuzu sayfası (liste + elle ekle +
  **düzenle** + pasifleştir + mükerrer tespiti/birleştirme
  `consolidate_duplicate_course`). Liste "Sınav" sütununu gösterir; sınav
  biçimi ders bazında değiştirilebilir (§7.1).
- Yeni okul türü = yeni md dosyası + `program_key` (+ `okul.SchoolType`'a bir
  satır); kod değişikliği gerekmez (U4 altyapı şartı).

### 7.2 Okul türü çizelgeleri ve kademeli dönüşüm (03.09.2026)

**Sorun (kullanıcı bulgusu).** Hazırlıksız bir Anadolu Lisesi'nde ders havuzu
"Hazırlık, 9. Sınıf, …" etiketleri gösteriyordu: gömülü tek dosya AL ile
"Hazırlık Sınıfı Bulunan AL" çizelgelerinin birleşimiydi ve tohum okulun
yapılandırmasına bakmıyordu. Aynı kökten iki eksik daha: diğer ortaöğretim
türlerinin çizelgesi yoktu (TB2) ve okul türü dönüşümündeki "kademeli"
uygulama (yeni çizelge 9'dan başlar, üst sınıflar eskide kalır) hiç
modellenmemişti — oysa MTAL'de 2026-2027'de üç nesil (2023/40, 2024/41,
2026/85) aynı anda yürürlüktedir, GSL/Spor 2025 çizelgeleri de ortak dersleri
hazırlık-9-10'dan başlatır.

**Karar.**

1. **Program dosyası = TTK çizelgesi.** Her çizelge ayrı `.md` (meta bloğu:
   `program_key`, `okul_turu` (virgülle çoklu — ÇPAL, AL/MTAL/AİHL dosyalarını
   paylaşır), `hazirlik`, `bolum`, `varsayilan`, `kaynak`, `yururluk`,
   `kademeli`, `kademeli_ilk_seviyeler`, `secmeli_kademeli`). Yürürlük kuralı
   dosyada yaşar; `CatalogProgram.covers(seviye, yıl, tür)` üç kalıbı tek
   kuralla verir (kademesiz · ortak kademeli/seçmeli hemen · tümü kademeli).
2. **Seviye ataması** (`catalog.default_assignment`): okul türü + hazırlık +
   aktif ders yılı → her seviyede hangi program(lar). Aynı bölüm grubunda
   birden çok nesil varsa (seviye, tür) için EN YENİ kapsayan nesil; hiçbiri
   kapsamıyorsa en yeni program yedek + UYARI (aktarılmamış önceki nesil).
   `SchoolConfig.level_programs` (`{"9": ["fen-lisesi-2025"]}`) seviye bazında
   ezer: kademeli tür dönüşümü, çok programlı okul, bölümlü GSL'de bulunmayan
   bölümü bırakma. Boş sözlük = varsayılan. OYS'nin
   `CurriculumFramework/Entry/Assignment` üçlüsü (ADR-0037) ALINMADI: KS'de
   haftalık saat ve ders programı yok; dosya + JSON alanı yeter.
3. **Birleştirme** (`catalog.effective_rows`): ad → seviye birleşimi; tür
   çatışmasında SEÇMELİ (havuz otomatik doldurması eksik doldurur, idareci
   ekler), sınav biçiminde YOK > UYGULAMA > YAZILI. Aynı çizelgede hem ortak hem
   seçmeli olan ders tek kayıttır: ortak bölümü lise seviyesindeyse ORTAK +
   birleşim (Fen BTY 9-10), yalnız hazırlıkta ortaksa SEÇMELİ (AL BTY) — dosya
   notlarında gerekçelenir.
4. **Senkron** (`services.sync_catalog` + `ensure_catalog_synced`): etkin
   satırlar upsert; çizelge dışı kalan MEB dersi `is_active=False +
   catalog_excluded=True`; geri girerse yalnız bayraklı kayıt açılır (idari
   pasif korunur, K5). Tetik DAMGA'dır (`catalog_stamp` = yapılandırma + yıl +
   dosya özetleri): ilk kurulum, ayar kaydı, kurulum tamamlama, ders yılı
   aktivasyonu, ders listesi açılışı ve **sürümle gelen yeni dosya** aynı
   yoldan iner — 0003 tarzı veri göçü artık gerekmez. Türün hiç dosyası yoksa
   dokunulmaz (uyarı).
5. **Arayüz:** okul türü seçici `GET /setup/school-types/` (veri olmayan tür
   "çizelge verisi yok" ekiyle); kurulum 1. adımı ve Ayarlar → Okul bilgileri
   ortak `CizelgeAtamaMatrisi` bileşenini kullanır — plan `GET
   /courses/catalog-status/` önizlemesiyle (kaydedilmemiş seçim), "Seviye
   bazında özelleştir" program × seviye matrisi açar. Ders havuzu ekranı
   yürürlükteki çizelgeyi dayanağıyla (TTK karar tarih/sayı) ve uyarıları
   basar; "Çizelgeyi yeniden uygula" zorla senkron; çizelge dışı ders "Çizelge
   dışı" rozetiyle idari pasiften ayrılır.

**Kaynak usulü (evrakmotoru ile aynı).** Resmî PDF (ttkb.meb.gov.tr /
meslek.meb.gov.tr) `data/raw/` altında (git dışı); `pypdf` düzen kipi (MTAL
ÇÖP'lerinde döndürülmüş tablo için `orientations`) → `scripts/
cizelge_metninden_tablo.py` taslağı → satır satır teyit → dosya + kürasyon
notu + dayanak. AL çizelgesi evrakmotoru korpusundaki kanonik aktarımla
karşılaştırıldı: 9-12 satırları birebir doğru çıktı; kullanıcının şüphesi
(yanlış çizelge) doğrulanmadı, sorun tohumun yapılandırmaya bakmamasıydı.
Kürasyon düzeltmesi: "Hedef Temelli Destek Eğitimi" `YOK` (kararın
AÇIKLAMALAR bölümü: "Ders notla değerlendirilmez").

**Bilinçli boşluklar** (TB2): GSL/Spor önceki nesil çizelgeleri (2026-2027'de
yalnız 12. sınıf ortak dersleri; uyarıyla yedek), MTAL seçmeli tablosu ve
hazırlıklı MTAL (resmî PDF taranmış görüntü), MTAL alan/dal meslek dersleri
(56 alan — okul elle ekler), ÖP Fen/SBL (2025/24-25; SBL nüshası "TASLAK").

### 7.1 Sınav biçimi (`exam_mode`) ve havuz doldurmanın daralması (31.08.2026, K19)

**Sorun (saha geri bildirimi).** Takvim havuzu "Katalogdan Doldur" ile aktif
kataloğun TAMAMINI (19 ortak + 45 seçmeli satır) okulun öğrencisi olan her
seviyeye açıyordu: ölçülen **169 (ders, seviye) çifti**. İdareci gerçekte sınav
yapılacak ~30 girdi kalana dek satırları tek tek siliyor; tek tek ekleme
(autocomplete) yolu da aynı derecede yavaş kalıyordu. Havuza sınavı hiç olmayan
ders (Rehberlik ve Yönlendirme) ve uygulama sınavı yapılan dersler (Beden
Eğitimi ve Spor, Görsel Sanatlar/Müzik, Spor Eğitimi, Sanat Eğitimi) de
giriyordu.

**Karar.**

1. `Course.exam_mode`: `WRITTEN` (Yazılı, varsayılan) / `PRACTICE` (Uygulama) /
   `NONE` (Sınav yok). Kaynak çizelgenin "Sınav" sütunu (yukarıdaki madde).
2. `fill_calendar_pool` yalnız **ORTAK + YAZILI** dersleri çeker
   (`taught_course_levels(course_types=[COMMON], exam_modes=[WRITTEN])`).
   Ölçülen etki: 169 → **33 girdi** (hazırlıksız, 9-12 öğrencili okul).
   Dönüş sözlüğünün şekli değişmez (`created/existed/skipped/total_pairs`).
3. Seçmeliler ayrı akıştan gelir: seviye sekmeli seçim diyaloğu
   (`elective-options` ucu, ders adları TR sıralı) + tek çağrılık toplu ekleme
   (`bulk-entries`). Havuzda olan ders işaretli ve kilitli görünür; reddedilen
   kalem sessizce düşmez, `skipped` nedeniyle raporlanır.
4. Takvim girdisi **katılımcı kapsamı** kazanır (`participant_type` +
   `section_ids`): "Seviye geneli" varsayılan, "Şube seç" seçeneğinde şube
   kümesi çipleri kümeyi somut şube listesine AÇAR. Dayanak Yönerge md. 5/1-b —
   okul geneli ortak yazılı sınavlar aynı sınıf düzeyinde birden çok şubesi
   bulunan okullarda ortak yapılır; yalnız bir-iki şubenin aldığı seçmelide
   kapsam doğal olarak dardır.
5. Takvim yaratılırken (yalnız tur 1 ve 2) havuz **kendiliğinden tohumlanır**;
   tohum hatası takvim yaratılmasını ASLA düşürmez. Tur 3 havuzu elle
   doldurulur (Yönerge md. 5/1-c: üçüncü sınav il sınıf/alan zümresi kararına
   bağlıdır — otomatik varsayım yapılamaz).
6. Elle ekleme formu KALIR ve kenar durumların yoludur: uygulama sınavı,
   "kelebek değil" ve üst makam sınavı girdileri oradan eklenir. Seçilen dersin
   `exam_mode`'u UYGULAMA ise formun "Tür" alanı kendiliğinden Uygulama'ya
   gelir (iki alan ayrı kalır: `exam_mode` dersin niteliği, `ExamKind` o
   girdinin türüdür).

**Sınıflamanın statüsü — mevzuat değil kürasyon.** Mevzuat hangi dersin yazılı,
hangisinin uygulamalı sınavla ölçüleceğini ders ders saymaz; Yönetmelik
md. 5/1-ı ile Yönerge md. 5/1-ğ yalnız Türkçe/Türk dili ve edebiyatı ve yabancı
dil derslerinde yazılı + uygulamalı iki aşamayı zorunlu kılar. Bu yüzden
`exam_mode` bir **çizelge kürasyonudur**: varsayılanı yaygın okul pratiğidir ve
idareci Ders Havuzu ekranından ders bazında değiştirebilir. "Rehberlik ve
Yönlendirme" satırı kataloğa sınav için değil ders programı doğrulaması için
girmiştir (çizelge kürasyon notu, Tur 362) → `NONE`.

**Alternatifler ve neden reddedildi.**

- *(a) Bugünkü hâl — her şeyi doldur, idareci silsin.* Ölçülen yük ~135 satır
  silme; kullanıcı bunu "çok uzun sürüyor, deneyimi zayıflatıyor" diye bildirdi.
  Reddedildi.
- *(b) Ders programı / ders kayıt verisinden türetmek (OYS'nin kaynağı).* KS'de
  ne ders programı ne de ders kaydı verisi var (B6 ve B8 sapmaları, TB4) —
  türetilecek veri yok. Reddedildi.
- *(c) Seçmelileri de otomatik doldurup kapsamı sonradan daraltmak.* Bir
  seçmelinin hangi seviyede fiilen açıldığı okul kararıdır; katalog bunu
  bilmez — otomatik doldurma (a)'nın seçmeli hâline dönerdi. Reddedildi.
- *(ç) `ExamKind.PRACTICE`'i ders niteliği olarak yeniden kullanmak.* İkisi
  ayrı kavram: `ExamKind` bir takvim girdisinin türü, `exam_mode` dersin
  niteliğidir; birleştirmek "bu ders bu kez uygulamalı sınandı" kaydını
  imkânsız kılardı. Reddedildi — iki enum ayrı durur.

**Sonuçlar.**

- `exam_mode` MEB kaynağının kazandığı **çizelge verisidir**: import'ta
  `levels`/`course_type` gibi ezilir. `is_active` ise bilinçle korunur — o idari
  karardır (K5). İkisi karıştırılmamalı; kod bunu yorumla söylemelidir.
- Kapsam **kümeler invariantına tabidir**: girdi yalnız LEVEL/SECTIONS tutar,
  küme kimliği tutmaz (§10) — üçüncü bir katılımcı tipi eklenmez (TB7 kesimi
  takvim tarafında da geçerlidir).
- Mevcut kurulumlar için **veri göçü şarttır**: `ensure_meb_catalog` tek bir
  `MEB_CATALOG` kaydı varsa hiçbir dosyayı okumadan döner, yani çizelgeye sütun
  eklemek yalnız sıfırdan kurulan makineleri etkiler. Göç ada göre (normalize
  eşleştirmeyle) sınıflar; geri alma `noop` — idarecinin elle verdiği değerler
  silinmesin diye.
- Günlük sınav yükü hesabı **gevşetilmez**: kapsam verisi geldi diye
  `_daily_exam_load`'un "kayıt verisi olmayan ders seviyenin tamamını kapsar"
  konservatif düşüşü kaldırılmaz (risk #4, TB10).

---

## 8. Arayüz planı (M3 "Mürekkep")

DD'nin 23 bileşenlik M3 kiti + Tailwind token altyapısı aynen (`rgb(var(--*))`
CSS değişkenleri; ham renk/px yasak; M3 token bütünlüğü testi taşınır).

Rotalar (tek pencere, lazy): **Hub** → Oturumlar → Oturum Detayı (sekmeler:
Yerleşim/Gözetmen/Sorular/Yoklama/Çıktılar) → Salonlar (+ Salon Editörü) →
Ders Havuzu → Takvimler → Takvim Detayı (Havuz/Yerleştirme/Takip) → Kişiler
(öğrenci/öğretmen + içe aktarma) → Ayarlar/Kurulum sihirbazı (Ayarlar sekmeleri:
Ders Yılları/Şubeler/**Şube Kümeleri**/**Zümreler**/Okul Bilgileri/Güvenlik/
Güncelleme) → Oturum Detayı sekmelerine **Yerleştirme Kuralları** eklendi;
Salonlar ekranında **Kümeler** diyaloğu (toplu atama) →
**Kullanım Kılavuzu** (`/kilavuz`, statik adım adım anlatım).
Takvim Detayı → Havuz paneli 31.08.2026'da ikiye ayrıldı (K19, §7.1):
**"Zorunlu dersleri ekle"** (eski "Katalogdan Doldur" ucu, daraltılmış kapsam) +
**"Seçmeli ders seç"** diyaloğu (seviye sekmeleri · onay kutulu ders listesi ·
satır içi katılımcı kapsamı: Seviye geneli / şube kümesi çipleri / tek tek
şube). Küme çipi şubeleri seçime EKLER, ayrı durum tutmaz — emsal desen
`SinavSihirbazi.applyGroup`. Havuz tablosunda kapsam sütunu görünür.

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

**Varsayılan salon şablonu (02.09.2026 kullanıcı kararı).** Okul içinde
salonlar birbirine benzer, okullar arasında farklıdır: uygulama tek bir
varsayılan biçim dayatır, farkı olan salonu idareci editörden düzeltir.
Şablon = **öğretmen masası ön-sol (0, 0)** + 4 sütun × 5 sıra ikili sıra;
**kapı yoktur** (yeri okula göre değişir, numaralandırmaya girmez ve yanlış
basılırsa resmî krokide yanlış bilgi olur). Masa sol öndeyken numaralandırma
kendiliğinden onun önünden başlar — kural şablona yazılıdır, numaralandırma
koduna değil (`reference_cell`). Şablonu backend üretir
(`GET /exam-rooms/default-plan/`, `desk_rows`/`cols` parametreli); tüketicileri:
şube derslikleri üretimi, "Yeni salon" ve editördeki "Varsayılan şablon"
düğmesi (açık salonun ızgara ölçüsünde uygular).

Değişiklikten önce kurulmuş okullar için **toplu düzeltme**: Salonlar →
"Şablonu topluca uygula" (`POST /exam-rooms/apply-default-plan/`). Diyalog eski
düzendeki salonları işaretli açar, her salon kendi satır/sütun ölçüsünde kalır
(kapasite değişmez) ve **yerleşimi yapılmış salonlar atlanır** — `SeatAssignment`
koltuğu `(desk_row, desk_col, slot)` + `seat_no` ile sakladığından numaralandırma
yönü değişirse basılmış evrakla plan çelişirdi. Aynı salon editörden tek tek
değiştirilebilir: bilinçli karar serbest, körlemesine toplu iş değil.

---

## 9. Evrak kataloğu

**30.08.2026 sadeleştirmesi (kullanıcı kararı).** Basılı set on bir belgeden
altıya indi; salon evrakı TEK belgede birleşti. Gerekçe: bir salon için R1
(kroki) + R2 (yoklama) + R3 (kapı listesi) + R7 (zarf kapağı) ayrı ayrı
basılıyordu — dört yaprak. Artık tek belge, çift yüz basıldığında **salon
başına bir kâğıt**.

| Kod | Belge | Kapsam | Yaprak |
|---|---|---|---|
| R1 | **Salon Sınav Evrakı** — oturma planı krokisi · gözetmen kontrol listesi · evrak sayımı · teslim zinciri (yaprak 1) + yoklama ve imza listesi (yaprak 2) | salon | 2 |
| R4 | **Şube Sınav Duyurusu** — öğrenci → salon + koltuk; sınıf panosuna asılır | şube | 1 |
| R5 | Toplu Dağıtım Çizelgesi (openpyxl) — idare çalışma kopyası, basılmaz | oturum | — |
| R6 | Gözetmen Görevlendirme / Tebliğ-Tebellüğ (yalnız gözetmen ayarı açıkken) | oturum | 1 |
| R7 | **Sınav İhlal ve Kopya Tutanağı** — salon zarfına konan boş form | salon | 1 |
| R8 | Dağıtım Doğrulama Raporu (seed basılır) — idare nüshası | oturum | 1 |

Ayrıca: R10 kişiselleştirilmiş kitapçık ZIP · oturumsuz boş salon yerleşim
planı · resmî takvim PDF (A4 yatay) · Word soru şablonu · tümü-ZIP.

**Takvim PDF'i (30.08.2026 eklentileri):** okul dışı makam sınavları (Bakanlık /
İl MEM / İlçe MEM) hücrede nötr dolgu + sol kenar çizgisi + makam etiketiyle
ayrışır — RENKLİ DOLGU YOK (palet nötr slate); tablonun altında lejant satırı ·
AÇIKLAMALAR bloğunun ardına düzenlenebilir **DİPNOT** bloğu (`footnote_text`) ·
imza bloğu takvime seçilen zümrelerden üretilir, seçim yoksa derslerden boş
çizgi (B7 revizyonu). Şablon sözleşmesi değişmedi: `chairs` + `school_chair_name`.

**Kaldırılanlar:** R2 (salon yoklama — R1'e girdi) · R2k (şube yoklama —
duyuru ve salon yoklaması ikisini de karşılıyordu) · R3 (kapı listesi — kroki
ve duyuru zaten söylüyor) · R9 (teslim tutanağı — teslim zinciri R1 yaprak
1'e girdi). Eski R7 (zarf kapağı) içeriği R1'in sayım bölümüne taşındı; R7
kodu **ihlal/kopya tutanağına** verildi (kaynak: evrakmotoru SAL-SNV-FR-007).

**Sayfa bütçesi (bağlayıcı).** Bir derslikte **40 öğrenci sığar**, fazlası
**kontrolsüz taşmaz**. İki mekanizma: `reports.kroki_metrics` krokiyi ayrılan
kutuya sığdırır (hücre yüksekliği + punto salonun satır/sütun sayısından),
`reports.list_row_metrics` yoklama/duyuru satırının punto ve dolgusunu sayfa
bütçesinden türetir. Ölçüler WeasyPrint kutu ağacından ÖLÇÜLEREK bulundu;
garanti `test_reports.py::test_r1_salon_evraki_iki_yaprak` ile sabittir.
Birim uyarısı: WeasyPrint iç birimi CSS px'tir (1 pt = 4/3 px) ve tablo
hücresine `height` vermek satırı kısaltmaz, UZATIR.

Şablonlar: `templates/sinav/reports/` (base · _head · _kroki · _kroki_style ·
r1_salon_evraki · r4_announcement · r6_assignment · r7_tutanak ·
r8_validation · room_layout) + `booklet_overlay` + `calendar_pdf` +
**`print/_design.css` ("Kurumsal Sade": `--pr-*` token'ları, DejaVu,
`text-transform` YASAK — WeasyPrint TR i→I tuzağı, `|unlocalize` zorunlu)**
birlikte kopyalanır. Hesaplanan CSS kuralları **`<head>` içinde** basılmalıdır:
WeasyPrint gövdedeki `<style>` öğesini ve inline `style` özniteliğindeki CSS
değişkenlerini yok sayar (ölçüldü).

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
- **Sınavı hazırlayan makam** (30.08.2026): ülke geneli sınavlar Bakanlıkça,
  il geneli sınavlar il MEM'ce belirlenen tarih/saatte yapılır ve o tarihlerde
  başka sınav yapılmaz (Yönerge md. 5) → takvim girdisinde `authority` alanı;
  aynı gün+seviyede okul sınavı ile üst makam sınavı yan yana düşerse UYARI
  (sert kısıt değil — "zorunlu hâl" takdiri okul müdürlüğünündür).
- **Mazeret sınavı takvimi**: mevzuat okul geneli sınavların mazeret işlemlerini
  okul müdürlüğüne bırakır, TARİH VERMEZ (Yönerge md. 5) → "izleyen hafta"
  ifadesi varsayılan dipnot metnindedir ve madde numarasına BAĞLANMAZ;
  kullanıcı `footnote_text` ile değiştirebilir.
- **Kümeler YALNIZ seçim aracıdır** (31.08.2026): küme kimliği hiçbir oturum
  kaydına yazılmaz; sihirbaz kümeyi yazma anında somut şube/salon pk'lerine
  açar. **Aynı kural takvim girdisine de uygulanır** (31.08.2026 eki):
  `ExamCalendarEntry` yalnız LEVEL/SECTIONS tutar, küme kimliği tutmaz; slottan
  oturum üretilirken girdinin kapsamı olduğu gibi `ExamSessionCourse`'a taşınır.
  Aksi hâlde küme sonradan değişince ONAYLANMIŞ oturumun katılımcı kümesi
  geriye dönük kayar (SNAPSHOT deseni + "aynı seed → aynı dağıtım" ihlali).
- **Havuz otomatik doldurması dar kapsamlıdır** (31.08.2026, K19):
  `fill_calendar_pool` yalnız ORTAK + YAZILI dersleri çeker; seçmeliler seçim
  diyaloğuyla, uygulama sınavı yapılan ve sınavı hiç olmayan dersler ise ELLE
  eklenir. Sınav biçimi sınıflaması mevzuat hükmü değil çizelge kürasyonudur
  (§7.1) — idareci ders bazında değiştirebilir, bu yüzden koda gömülü ders adı
  listesi tutulmaz.
- **Özel durum yerleştirmesi**: koltuk koordinatı `(desk_row, desk_col, slot)`
  ile tutulur — `seat_no` numaralandırma düzeni değişince kayar, koordinat
  kaymaz. "Tek başına" kardeş koltukları motor girdisinden DÜŞÜRÜR; sahte
  `SeatAssignment` ASLA yazılmaz (student FK'sı + SNAPSHOT deseni).
- **İmza bloğu sözleşmesi**: `_calendar_signatures` çıktısı
  `{"chairs": [{"name", "role"}], "school_chair_name"}` — `calendar_pdf.html`
  bu iki anahtarı tüketir; kaynak değişse de sözleşme değişmez.

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

> **31.08.2026 sapması:** `engine.py` · `validator.py` · `layout.py` AYNEN
> sınıfından ÇIKTI. Gerekçe: kaçınılmaz komşu çiftlerin öğretmen masasına
> çekilmesi (kullanıcı isteği) motorun ceza fonksiyonuna dokunmayı gerektirdi;
> `layout._reference_cell` public `reference_cell` oldu (ikinci doğruluk
> kaynağı doğmasın diye). Sert kısıt, determinizm ve doğrulayıcı sözleşmesi
> DEĞİŞMEDİ — bkz. §4 ceza demeti.

### UYARLA
`models.py` (created_by düşer; soft-delete + koşullu unique + SNAPSHOT kalır;
şifreli alanlar doğuştan; migration 0001'den) · `services.py` 2354 (Celery→
senkron; 5 köprü yerel arayüze — **fonksiyon imzaları korunarak**) ·
`services_calendar.py` (çekirdek aynen; onay tek-kullanıcı; bildirim dalı
silinir) · selectors/serializers/views/urls (izinler düşer; GET+POST tek-action
— Tur 644 dersi) · `reports.py` (zümre imza dalı; takvimde seçilen zümre yoksa
boş çizgi — B7 revizyonu) · FE `api.ts` →
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
| **F2 eki (31.08.2026)** | Derslik kümeleri (Sabah/Öğle) + toplu atama; motor odak altyapısı (`reference_cell` → `RoomSeats.focus`) | Küme CRUD + toplu atama testleri; odak taşınması satranç modunda korunur; mevcut motor testleri DEĞİŞMEDEN yeşil |
| **F3 Oturum akışı** | 5 adımlı sihirbaz; ExamSession+Course (tek-seviyeli); dağıtım+seed; durum makinesi; PlacementRule 4 tip; takas; yoklama; SNAPSHOT. Sapma: katılımcı tipi yalnız LEVEL/SECTIONS — OYS'deki GROUPS (şube-içi grup) alınmadı (TB7); Adım 0 nakil özeti veri sorgusu yerine beyan + son içe aktarma tazeliği (B10) | Uçtan uca senaryo; onayda ihlal=0 şartı; arşivde mazeret güncellenebilir |
| **F3 eki (31.08.2026)** | Şube kümeleri; oturum planı kopyalama (`copy-plan`); koltuk sabitleme (BELIRLI_KOLTUK + ön/arka + tek başına); kaçınılmaz komşuların odağa çekilmesi | Küme→şube açılımı seviyeyle kesişir; kopyalama idempotent + şube yıllar arası yeniden eşlenir; sabit koltuk üç seed'de aynı; tek başına kardeş koltuğu kapatır; odak terimi ihlal sayısını ARTIRMAZ ve determinizmi bozmaz |
| **F4 Evrak seti** | R1-R5, R7-R9 + boş plan + tümü-ZIP; _design.css; ARCHIVED yeniden basım | Her raporda TR karakter duman testi; `text-transform` tarama testi; `|unlocalize` denetimi |
| **F5 Kitapçık** | R10 senkron + A4 ±6pt doğrulama + Word şablonu | Bant ≤ 40mm invariantı; sayfa kuralları; 90×4 < 30 sn |
| **F6 Takvim** | ExamCalendar + statutory_window + grid + günlük limit + slot→oturum + takvim PDF; **30.08.2026 eki:** hazırlayan makam (`authority`), düzenlenebilir dipnot, seçilen zümrelerden imza bloğu | Pencere hesabı + öğrenci-bazlı limit senaryoları; makam ızgara hücresinde + PDF etiketinde; üst makam günü çakışması uyarı üretir; seçili zümre PDF'e başkan adıyla basılır, seçim yoksa yedek dal |
| **F6 eki (31.08.2026)** | `Course.exam_mode` + çizelgenin isteğe bağlı "Sınav" sütunu + ada göre veri göçü; havuz otomatik doldurması ORTAK+YAZILI'ya daraldı; seçmeli seçim diyaloğu (seviye sekmeleri + kapsam) ve toplu ekleme ucu; takvim girdisinde katılımcı kapsamı (LEVEL/SECTIONS); tur 1-2 takviminde otomatik havuz tohumu (K19, §7.1) | Üç sütunlu çizelgeler DEĞİŞMEDEN çözülür; göç ada göre UYGULAMA/YOK işaretler ve geri alınabilir; fill-pool seçmeli/uygulama/sınavsız dersi ÇEKMEZ; toplu ekleme idempotent ve reddedilen kalem sessizce düşmez; şube kapsamı slottan üretilen oturuma taşınır; tur 3'te tohum koşmaz; `_daily_exam_load` değişmeden yeşil |
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
   tamamı" kuralı gevşetilirse mevzuat denetimi delinir. **31.08.2026 eki:**
   takvim girdisine şube kapsamı gelmesi bu kuralı DEĞİŞTİRMEZ — kapsam yalnız
   katılımcı önizlemesinde ve slottan oturum üretiminde kullanılır;
   `_daily_exam_load` şube listesine bakmaz (TB10).
5. **Fontconfig/DejaVu:** fonts.conf'ta DOCTYPE kalırsa sessiz ret → bozuk
   Türkçe evrak; build.ps1 ezme adımı atlanmamalı.
6. **Kimlik çakışması:** Inno AppId GUID yenilenmez veya `DD_*` kalıntısı
   kalırsa iki uygulama aynı makinede veri karıştırır.
7. **UTC tarih tuzağı:** 00:00-03:00 arası bir gün geri kayma —
   format.test.ts koruma testi taşınmazsa sınav tarihli evrakta nüksedebilir.
8. **Okul türü verisi (U4):** 03.09.2026'dan itibaren sekiz türün çizelgesi
   gömülü (§7.2); kalan boşluklar (MTAL seçmeli/meslek dersleri, GSL/Spor
   önceki nesil) uyarıyla görünür, elle ekleme yolu açık.
9. **F27 geri dönüşsüz:** onay diyaloğu + aday listesi olmadan tetiklenirse
   veri kaybı şikâyeti kaçınılmaz.
10. **Takvim damgaları:** tek-kullanıcı sadeleştirmesi onaylayan/tarih
    damgalarını silerse basılan takvim PDF'inin resmî değeri düşer.

## 14. Açık işler / teknik borç başlangıcı

- e-Okul PDF parser'ları (şube listesi, personel) → v2 adayı.
- Okul türü çizelgeleri: sekiz tür gömülü (§7.2, 03.09.2026). Kalan
  küratörlük: GSL/Spor önceki nesil çizelgeleri (2023/41-42, 2024/46-47), MTAL
  seçmeli dersler tablosu (2026/62 — taranmış PDF, OCR/elle aktarım gerekir),
  hazırlıklı MTAL (2024/42, 2026/63), ÖP Fen/SBL (2025/24-25). Meslek dersleri
  özel: ortak sınavın en az biri uygulamalı yapılır (Yönetmelik md. 5/1-h) —
  sınıflama zümre kararına bağlı, katalogla taşınmaz.
- Ortaokul/ilkokul kademesi → seviye kümesi parametrik olduğunda değerlendirilir.
- okulapp.org yayın alanı: sürüm kartı + tanıtım sayfaları (DD deseni;
  `okulapp.org/CLAUDE.md` "Ortak çalışma düzeni"ne tabi).
