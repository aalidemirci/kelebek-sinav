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
kurulu; sınav takvimi imza bloğunun kaynağı, B7 revizyonu; **`branches`** JSON —
zümrenin öğretmen sicilindeki branşları, 20.09.2026: zümreler branşlardan ÜRETİLİR
ve başkan adayları bu branşların öğretmenleridir, aşağıdaki not) · `StudentPhoto`
(öğrenci başına tek fotoğraf: `image`* base64 JPEG + sha256 + ölçü — 19.09.2026,
§6; öğrenci aktif olmaktan çıkınca ya da silinince KATI silinir).

**Zümrelerin branştan üretimi (20.09.2026, kullanıcı isteği —
`okul/services/departments.py`).** İstek: "zümreleri e-Okul'dan yüklenen öğretmen
listesindeki branş bilgisinden otomatik üret; sonradan ekleme çıkarma yapılabilsin;
zümre başkanı seçerken ilgili branştaki öğretmenler listelensin." Kararlar:

* **Branş ayrı katalog DEĞİLDİR**, e-Okul'dan gelen serbest metindir
  (`Personnel.branch`). Zümre branşlarını METİN listesi olarak taşır
  (`SubjectDepartment.branches`); eşleşme yazıma değil ANAHTARA göredir
  (`departments.branch_key` — harf büyüklüğü, Türkçe harf, şapka ve boşluk katlanır:
  "COĞRAFYA" = "Coğrafya", "Ahlâk" = "Ahlak"). Anahtar backend'de üretilir ve iki
  serileştiricide döner (`Personnel.branch_key`, `SubjectDepartment.branch_keys`) —
  arayüz normalizasyon KOPYALAMAZ, yalnız eşitlik sorar.
* **Bir branş en çok bir zümrededir** (`_ensure_branches_free`); bir zümre birden
  çok branş taşıyabilir (Tarih + Coğrafya + Felsefe → "Sosyal Bilimler"). Branşı boş
  zümrede başkan adayı bütün aktif öğretmenlerdir (eski davranış); arayüzdeki
  "tüm öğretmenleri göster" kutusu istisnalar içindir. Kayıtlı başkan listede
  yoksa seçenek olarak korunur ("başka branş" / "listede yok").
* **Üretim idempotenttir ve ad tekliğini çiğnemez:** branşı bir zümrede olan aday
  atlanır (COVERED), adı branşla aynı olan zümre yeniden yaratılmaz — branş ona
  bağlanır (LINKABLE), kalanı için zümre açılır (NEW). Zümre adı imza bloğuna
  "<ad> Zümre Başkanı" diye basıldığından tamamı büyük/küçük yazım başlık biçimine
  çevrilir (`shared.text.tr_title` — ders adlarıyla TEK uygulama).
* **Kendiliğinden üretim YALNIZ katalog boşken** (öğretmen aktarımının commit ucu —
  `generate_if_catalog_empty`; sonuç yanıtta `departments_created`). Katalogda tek
  zümre bile varsa idarecinin düzeni sayılır: kaldırılan zümre sonraki aktarımda
  sessizce geri gelmez. O durumda üretim Ayarlar → Zümreler'deki "Branşlardan zümre
  üret" penceresinden, adaylar görülüp seçilerek yapılır. Önizleme ucu üretmez;
  içe aktarma servisine (`imports.py`) dokunulmadı — tetik view katmanındadır.
* Adaylar AKTİF öğretmenlerden okunur; branşı boş kayıt (memur, hizmetli) aday
  üretmez. Veri göçü yok: eski kurulumdaki elle açılmış zümreler üretim penceresinde
  aynı adlı branşa bağlanır.

**Ders havuzu (OYS ders_yapisi'ndan):** `Course` (name, `levels` JSON,
course_type ORTAK/SECMELI, source MEB/MANUAL, `is_active`, **`exam_mode`
YAZILI/UYGULAMA/YOK** — 31.08.2026 K19; çizelgenin isteğe bağlı "Sınav"
sütunundan gelir, varsayılan YAZILI) ·
`CurriculumFramework` + girdileri (program_key, version — idempotent upsert) ·
`CourseAlias` (SEED + OPERATOR; OPERATOR SEED'i ezer, tersi asla).
`VALID_COURSE_LEVELS` **SchoolConfig'den türetilir** (v1: 0=Hazırlık, 9-12).
`CourseSectionOffering` (seçmelinin (ders, yıl, seviye) şube kapsamı — 03.09.2026) ·
`CourseEnrollment` (seçmelinin (ders, yıl, şube) öğrenci listesi — 19.09.2026,
§7.3; listesiz şube dersi tamamen alır).

**Sınav çekirdeği (OYS sinav_islemleri'nden):** `ExamRoom` (plan JSON: grid ≤
30×30, SINGLE/DOUBLE/TRIPLE sıralar, kapı/tahta/öğretmen masası; kapasite
plandan) · `ExamSession` (durum makinesi DRAFT→DISTRIBUTED→APPROVED→ARCHIVED,
`layout_mode` BUTTERFLY/HOME_CLASSROOM, `distribution_params` ile seed) ·
`ExamSessionCourse` (**baştan tek-seviyeli** — Tur 241 dersi; `shared_booklet`
**dersin oturum içi niteliğidir**: kardeş satırlarda senkron YAZILIR, ret yok —
18.09.2026 revizyonu, CLAUDE.md §3)
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
pk listesine açılır (§10 kümeler invariantı). `IepStudent` (BEP kapsamındaki
öğrenciler — YALNIZ üyelik: `student_ref`*) · `IndividualQuestionDocument`
(oturumda bireysel soru dosyası: `session` + `student_ref`* + dosya + puan
bölümü; satırın varlığı seçimdir) · `ExamSession.individual_changed_at`
(kitapçık bayatlık damgası) — 20.09.2026, §9 "BEP…"; ikisinde de öğrenci bağı
FK DEĞİL şifreli metindir ve satırlar KATI silinir.

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
  `Personnel.first_name/last_name`, `StudentPhoto.image` (19.09.2026 —
  fotoğraf addan daha tanıtıcıdır) ve **tüm SNAPSHOT kopyaları**
  (`SeatAssignment.full_name`, `ExamAttendanceRecord`, `ProctorAssignment.teacher_name`).
  Kaynak şifreli olup snapshot düz kalsaydı şifreleme anlamsızlaşırdı.
  Fotoğrafın snapshot'ı YOKTUR: evrak basılırken canlı kayıttan okunur;
  arşiv evrakının yeniden basımında silinmiş fotoğraf yerine boş kutu çıkar
  (KVKK: ayrılan öğrencinin fotoğrafı saklanmaz).
- **Şifreli ÖĞRENCİ BAĞI (20.09.2026 — BEP):** `IepStudent.student_ref` ve
  `IndividualQuestionDocument.student_ref` FK değil, öğrenci pk'sini taşıyan
  `EncryptedCharField`'dır. Gerekçe aşağıdaki "açık kalanlar" satırının ters
  yüzüdür: okul no ve şube açık olduğu için düz FK, ad şifreli olsa bile "şu
  numaralı öğrenci BEP kapsamında" bilgisini açıkta bırakırdı. Bedeli: teklik,
  süzme ve öksüz kayıt temizliği Python'dadır (`services_individual`), FK
  bütünlüğü yoktur; çözülemeyen bağ (kilitli kasa, yarım geçiş) ATLANIR ve asla
  silinmez. Kullanıcı kararı: parola bu özellik için zorunlu değildir — kapalıyken
  bağ düz saklanır ve arayüz uyarır (§9 "BEP…" paragrafı, KVKK md. 6/4).
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
- **Tek istisna — OOK10002R010 Seçmeli Ders Öğrencileri (19.09.2026, §7.3):**
  *Öğrenci Seçmeli Derslerini Belirle → Raporlar* altındaki bu raporun Excel
  ihracı ders adı bantlarını DÜŞÜRÜR (Crystal "yalnız veri" çıktısı: satırlar
  gelir, hangi derse ait oldukları gelmez), yani Excel yolu yoktur. PDF okunur
  (`apps/dersler/enrollment_import.py`): ders başlığı + satırdan YALNIZ okul no
  ve sınıf/şube alınır, ad hiç ayrıştırılmaz. Glif riski gerçek raporla
  ölçüldü: 25 ders grubu, 8.385 satır aynı raporun Excel ihracıyla birebir.
  Desen öğrenci aktarımıyla aynıdır (önizle → rapor → aktar, `ImportRun`
  `ELECTIVES`, sha256 uyarısı); sorunlar sayfa/satır + okul no ile raporlanır.
- **Öğrenci fotoğrafları — OOG01001R080 (19.09.2026, kullanıcı isteği):**
  e-Okul bu fotoğraflı listeyi **sınıf düzeyi başına** verir; her düzeyin
  dosyası ayrı aktarılır. **Excel yolu seçildi, PDF değil:** `.XLS` (BIFF8)
  içinde fotoğraflar çalışma kitabının OfficeArt görsel deposundadır
  (MSODRAWINGGROUP → FBSE, gömülü JPEG/PNG), sayfadaki her şekil görsel
  sırasını ve hücre çapasını taşır; okul no çapanın ALTINDAKİ hücrenin sonundaki
  sayıdır (`apps/okul/eokul_foto.py`). Kayıt eşleşmesi okul numarasıyla,
  öğrenci aktarımından gelen kayda yapılır — Excel'in başlığında yalnız ilk
  şubenin adı bulunması sorun olmaz. PDF'te fotoğraf ile adın bağı yalnız sayfa
  KONUMUNDAN kurulabilirdi (kırılgan); PDF yolu yazılmadı. Gerçek raporla
  ölçüldü: 430 öğrenci hücresi (6'sında "fotoğraf yok" simgesi), 430 farklı
  okul no, etiketsiz 1 logo.
  Kurallar: (1) görsel Pillow'la YENİDEN KODLANIR (EXIF/meta atılır, ≤240×320,
  JPEG); (2) birden çok şeklin paylaştığı görsel ve DIB/metafile "fotoğraf yok"
  simgesidir — yer tutucu sayılır, kayıtlı fotoğrafı silmez; (3) **mükerrer
  yükleme** (kullanıcı kararı): aynı fotoğraf (sha256) sessiz geçer, kayıtlı
  fotoğrafı FARKLI öğrenci önizlemede sayılıp okul no · şube ile listelenir ve
  idareci `keep`/`replace` seçer; (4) desen öğrenci aktarımıyla aynıdır
  (önizle → rapor → aktar, `ImportRun` `PHOTOS`, sha256 uyarısı). Saklama
  kararı (kullanıcı): veritabanında, yedeğe girer, parola açıkken şifreli
  (§5); ayrılan öğrencinin fotoğrafı silinir; Kişiler ekranında "Tüm
  fotoğrafları sil". Tüketiciler: R1 fotoğraflı oturma planı (§9) ve oturum
  detayındaki Yoklama planı.

## 7. MEB ders havuzu planı

- Gömülü veri: [data/ders-cizelgeleri/](../../data/ders-cizelgeleri/) —
  okul türü başına **program dosyaları** (`<program_key>.md`; 03.09.2026'da
  15 dosya: AL, Fen, SBL ve hazırlık varyantları, AİHL (+program/proje),
  GSL dört bölüm, Spor (+tematik), MTAL ortak dersler; 19.09.2026'da AİHL
  program/proje dosyası B grubundaki yedi programa bölündü, AİHL Fen ve Sosyal
  Bilimler programı ile Spor'un 2026 nesli (+tematik) eklendi → 24 dosya; okul
  program/proje dosyalarından yalnız uyguladığını işaretler) +
  `ders-adi-takma-adlari.md` (~55 takma ad). Eski birleşik
  `anadolu-lisesi-2025-2026.md` ve OYS'den kopyalanan `cerceveler/` (KS'de
  hiç tüketilmeyen saat matrisleri) kaldırıldı — bkz. §7.2.
- Parser'lar saf ve aynen taşınır: `catalog_parser`, `curriculum_parser`,
  normalize yardımcıları (`_match_key`, `titlecase_tr`,
  `repair_truncated_course_name` — çıplak `.upper()/.lower()` TR'de yasak).
- Çizelge tablosunun **isteğe bağlı 4. sütunu "Sınav"**: `YAZILI` / `UYGULAMA` /
  `YOK`. Sütun yoksa veya hücre boşsa `YAZILI` sayılır — üç sütunlu dosyalar
  (elle yazılmış eski çizelgeler) değişmeden çözülür.
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
   kapsamıyorsa yürürlüğü BAŞLAMIŞ en yeni program yedek + UYARI (aktarılmamış
   önceki nesil; henüz başlamamış çizelge geçmiş yıla yedek olmaz).
   `SchoolConfig.level_programs` (`{"9": ["fen-lisesi-2025"]}`) seviye bazında
   ezer: kademeli tür dönüşümü, çok programlı okul, bölümlü GSL'de bulunmayan
   bölümü bırakma. Boş sözlük = varsayılan. **19.09.2026 eki (TTK 02.09.2026/
   102-103, Spor):** aynı çizelgenin yeni kararı YENİ program dosyasıdır; eski
   dosya geçmiş yıl için kalır. Açık atama yürürlük süzgecinden geçmediğinden
   yeni nesle kendiliğinden GEÇMEZ — aynı bölüm grubu + hazırlık varyantında
   daha yeni bir nesil o seviyenin ortak derslerini kapsıyorsa plan UYARIR
   (`catalog._superseded_by`), atamaya dokunmaz: atama idari karardır, sessiz
   düzeltme de sessiz düşme kadar yanlıştır. OYS'nin
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

**Bilinçli boşluklar** (TB2): GSL önceki nesil çizelgeleri (2026-2027'de
yalnız 12. sınıf ortak dersleri; uyarıyla yedek — Spor'da bu boşluk 19.09.2026'da
TTK 2026/102-103 ile kapandı), MTAL seçmeli tablosu ve hazırlıklı MTAL (resmî
PDF taranmış görüntü), MTAL alan/dal meslek dersleri (56 alan — okul elle
ekler), ÖP Fen/SBL (2025/24-25; SBL nüshası "TASLAK"), ÖP hazırlıklı Anadolu
Lisesi (2026/104 — yalnız protokollü proje okulları).

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

### 7.3 Seçmeli ders öğrenci listesi — "şubenin bir kısmı" (19.09.2026)

**Bağlam.** Şube kapsamı (`CourseSectionOffering`) "bu seçmeliyi hangi şubeler
alıyor"u söyler, "şubedeki hangi öğrenciler"i söylemez. Din öğretimi
seçmelilerinde tipik durum: 9/A ve 9/B'de bir grup Kur'an-ı Kerim, kalanı
Peygamberimizin Hayatı. İki ders de iki şubeyi kapsam gösterince katılımcı
çözümü her öğrenciyi iki derse yazıyor, oturum çakışmayla kilitleniyor, soru
kitapçığı yanlış derse basılıyor ve takvim iki sınavı aynı saate koymayı
reddediyordu.

**Karar.** Kural ŞUBE BAZINDADIR: (ders, ders yılı, şube) için
`dersler.CourseEnrollment` satırı varsa o şubeden YALNIZ listedeki öğrenciler
dersi alır; satır yoksa şubenin tamamı alır (bugünkü davranış — veri girmeyen
okulda hiçbir şey değişmez). Liste kaynağı e-Okul OOK10002R010 PDF'idir (§6)
ya da şube penceresindeki elle seçici; seçicinin "işaretlenmeyenleri şu derse
yaz" seçeneği tamamlayıcı dersin listesini aynı işlemde yazar.

- **Katılımcı çözümü** (`participants._resolve_sections`) SECTIONS
  satırında şube kadrosunu listeyle süzer; listedeki ama şubeden ayrılmış
  öğrenci SAYIyla uyarılır (ad yok). LEVEL satırı listeyi UYGULAMAZ ama
  listenin varlığını uyarır — "Sınıf düzeyinin tamamı" açık bir seçimdir.
- **Takvim sert kısıtı** (`_scope_overlaps`) ortak şubede soruyu öğrenciye
  indirir: iki ders de o şubede listeliyse kesişim liste kesişimidir; biri
  listesizse şube "tamamı" sayılır ve kesişir. Ret metni kaç öğrencinin iki
  dersi birden aldığını söyler.
- **Günlük sınav yükü** (TB10) listeye yalnız TAM olduğunda güvenir:
  `course_level_student_ids` dersin o seviyedeki BÜTÜN kapsam şubelerinde liste
  varken küme döner; tek şube listesizse boş (bilinmiyor) → ders seviyenin
  tamamının yüküne eklenir. Risk #4 korunur.
- **Yerleşim sapması:** dağıtılmış/onaylı oturumda yerleşim snapshot'ı
  (`SeatAssignment.student_id` + `conflict_group`) güncel çözümle karşılaştırılır
  (`participants.placement_drift`); fark varsa oturum sayfası "yeniden dağıtın"
  bandı gösterir. Yerleşim sessizce değiştirilmez (snapshot deseni).

**Alternatifler ve neden reddedildi.**

- *(a) OYS'nin `ParticipantType.GROUPS` + şube-içi grup modeli (TB7).* Grup
  bir ara kavramdır: idareci önce grup kurar, sonra öğrenci atar, sonra oturumda
  grubu seçer. e-Okul veriyi zaten (ders → öğrenci) biçiminde verir; ara model
  eşlemeyi iki kez yaptırırdı. Takvim girdisi için "ÜÇÜNCÜ TİP YOK" kuralı da
  yeni bir katılımcı tipini dışlar. Reddedildi.
- *(b) Listeyi oturum dersine (`ExamSessionCourse`) yazmak.* Her sınavda
  yeniden girilirdi; dört takvim ve her oturum aynı bilgiyi ister. Kaynak ders
  havuzudur — kapsam kararının (03.09.2026) aynı gerekçesi. Reddedildi.
- *(c) Listeyi `Course` üzerinde alan olarak tutmak.* Katalog yıldan
  bağımsızdır ve `sync_catalog` alanlarını ezer; öğrenci yıla bağlıdır.
  Reddedildi (anahtar yıl + şube içerir).

**Sonuçlar.**

- Liste satırları KATI silinir (soft-delete değil): yeniden aktarım ve elle
  düzeltme listeyi TAMAMEN değiştirir, eski satırlar tarih taşımaz; öğrenci-ders
  eşleşmesi amacı için gerekenden uzun saklanmaz (KVKK saklama ilkesi — veri
  minimizasyonu, CLAUDE.md §1.6).
- Şube kapsamdan çıkarılırsa (`set_course_sections`) o şubenin listesi de
  düşer — kapsam dışı şubede "bir kısmı" listesi anlamsızdır.
- e-Okul aktarımı yalnız raporun KAPSADIĞI şubelerde yeniler (raporda herhangi
  bir derste satırı geçen şubeler): rapor tek düzey ya da tek şube için
  alınabildiğinden, "rapordaki dersin bütün listesini sil" kuralı öbür
  düzeylerin listesini sessizce silerdi. Önizleme kapsamı ("9. Sınıf düzeyinden
  12 şube") söyler. Bedeli: hiçbir seçmeliyi almayan şube kapsanmaz, eski
  listesi varsa elle temizlenir.
- **Havuz otomasyonu (19.09.2026, kullanıcı kararı "açılmayanlar ayrılsın, yenisi
  eklensin"):** raporda olup havuzda hiçbir adayı bulunmayan seçmeli önizlemede
  "Havuza ekle" ile işaretli gelir ve aktarımda seçmeli (MANUAL) açılır —
  zorunlu dersle aynı adlı başlık açılmaz. Rapor kapsamı `ElectiveReportSection`e
  yazılır; öğrencili BÜTÜN şubeleri kapsanan düzeyde şube kapsamı olmayan seçmeli
  "bu yıl açılmadı" sayılır. Pasifleştirme DEĞİLDİR (`is_active` idari karar):
  Ders Havuzu'nda gizlenir, takvim havuzu doldurması onları tek özet satırla
  bildirir; şube girilince ders kendiliğinden yeniden açılır. Kısmi rapor
  (tek şube) o düzey hakkında hüküm vermez.
- Yıl geçişinde liste KOPYALANMAZ (şube pk'leri yıla bağlı; kapsam kararıyla
  aynı).
- Motor ve evrak DEĞİŞMEDİ: çakışma anahtarı hâlâ `"<course_id>:<level>"`;
  katılımcı doğru çözüldüğünde kitapçık, R1/R4/R5/R7 ve R8 kendiliğinden doğru
  olur.

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
| R1 | **Salon Sınav Evrakı** — fotoğraflı oturma planı, yoklama ve imza kartların üstünde (yaprak 1) + künye · gözetmen kontrol listesi · evrak sayımı · teslim zinciri (yaprak 2) — 19.09.2026 düzeni | salon | 2 |
| R4 | **Şube Sınav Duyurusu** — öğrenci → salon + koltuk; sınıf panosuna asılır | şube | 1 |
| R5 | Toplu Dağıtım Çizelgesi (openpyxl) — idare çalışma kopyası, basılmaz | oturum | — |
| R6 | Gözetmen Görevlendirme / Tebliğ-Tebellüğ (yalnız gözetmen ayarı açıkken) | oturum | 1 |
| R7 | **Sınav İhlal ve Kopya Tutanağı** — salon zarfına konan boş form | salon | 1 |
| R8 | Dağıtım Doğrulama Raporu (seed basılır) — idare nüshası | oturum | 1 |

Ayrıca: R10 kişiselleştirilmiş kitapçık ZIP · oturumsuz boş salon yerleşim
planı · resmî takvim PDF (A4 yatay) · Word soru şablonu · tümü-ZIP · BEP
kapsamındaki öğrenciler idare özeti (20.09.2026 — yalnız idare nüshası, tümü-ZIP'e
GİRMEZ; aşağıdaki "BEP…" paragrafı).

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
**kontrolsüz taşmaz**. Üç mekanizma: `reports.photo_plan_metrics` R1'in
fotoğraflı planını ayrılan kutuya (`PHOTO_PLAN_BOX_PX`) sığdırır,
`reports.kroki_metrics` boş salon planının krokisini (hücre yüksekliği + punto
salonun satır/sütun sayısından), `reports.list_row_metrics` duyuru satırının
punto ve dolgusunu sayfa bütçesinden türetir. Ölçüler WeasyPrint kutu ağacından ÖLÇÜLEREK bulundu;
garanti `test_reports.py::test_r1_salon_evraki_iki_yaprak` ile sabittir.
Birim uyarısı: WeasyPrint iç birimi CSS px'tir (1 pt = 4/3 px) ve tablo
hücresine `height` vermek satırı kısaltmaz, UZATIR.

**18.09.2026 evrak revizyonu (değerlendirme belgesi §3).** Örnek PDF'ler gerçek
uzunlukta ders adlarıyla yeniden üretilip gözle incelendi; bulgular ve kararlar:

* **Ders kodu.** Karışık salonda yoklama listesinin "Ders" sütunu ve kroki
  hücresi tek harf taşır (A, B, C — ders etiketinin doğal sırası); açıklama
  listenin üstünde ("DERS KODLARI: A = …"), künyede kod özeti, sayım tablosunda
  kod + tam ad + süre. Gerekçe ölçümdür: "Türk Dili ve Edebiyatı — 10. Sınıf"
  gibi gerçek bir etiket %16'lık sütunda sarıyor, 40 öğrencili R1 üçüncü sayfaya
  taşıyordu. Bütçe testleri artık gerçek uzunlukta adlarla koşar.
* **Seviye.** Aynı ders bir oturumda ≥2 seviyedeyse R1/R5/R7 ve kitapçık bandı
  adı seviyeyle basar; şube duyurusu (R4) seviyesiz basar (şube tek seviyededir)
  ve ad/ders sütun payını en uzun metinlere göre bölüşür.
* **Süre.** Üst bantta "Süre: 40 dk" (ders süreleri farklıysa "derse göre
  40-60 dk"); ders bazlı süre R1 sayım tablosunda. R6 görevlendirme yazısının
  giriş cümlesi de süreyi söyler.
* **Çift yüz baskı.** R1'in ilk yaprağı `break-before: right` ile daima ön yüze
  düşer; toplu basımda bir salonun krokisi öncekinin arkasına basılmaz.
* **Plan sonradan değiştiyse.** Yerleşimden sonra salon planı daraltılmışsa
  krokide görünmeyen öğrenciler için kroki altına "DİKKAT: N öğrencinin koltuğu
  güncel salon planında yok" notu düşer (yoklama listesi snapshot'tan tamdır).
  Salonu silinmiş oturumun evrakı da üretilir (snapshot + `include_deleted`).
* **R8 dili.** "İhlal", "seed", "sert/yumuşak kısıt" idareci diline çevrildi
  ("KURAL İHLALİ YOKTUR", "Dağıtım numarası"); imza "Düzenleyen — Müdür
  Yardımcısı". R4'e de düzenleyen imza satırı + dayanak eklendi.
* **Antet.** Resmî yazışma usulü: kurum satırı büyük harf (`tr_upper`), birim
  satırı "<Okul Adı> Müdürlüğü". Takvimde onay tarihi basılır.
* **Bilinçli olarak yapılmayanlar.** R1 yaprak 1'e "sınava girmeyen öğrenci
  numaraları" satırı ve daha büyük "tespit" kutusu eklenmedi — yaprak 1 bütçesi
  dolu, bilgi yaprak 2'deki yoklamada zaten var. Kitapçık bandına süre
  eklenmedi (`booklet.py` AYNEN sınıfında).

**19.09.2026 — fotoğraflı oturma planı, yoklama plan üzerinde (kullanıcı
kararı).** İstek: "salon oturma planını fotoğraflı yapalım; yoklama/imza da
doğrudan bu plan üzerinde olsun; bir sayfası fotoğraflı plan, bir sayfası
diğer hususlar." Yukarıdaki 18.09 maddelerinden "ders kodu", "plan sonradan
değiştiyse" ve "bilinçli olarak yapılmayanlar" bu düzende şöyle karşılanır:

* **Yaprak 1 = plan + yoklama.** Her koltuk bir KART: koltuk no (+ karışık
  salonda ders kodu rozeti), fotoğraf, ad, okul no · şube, "İmza" alanı ve
  "Yok" kutusu. Ayrı yoklama/imza listesi KALKTI — öğrenci imzasını kendi
  kartına atar, gözetmen girmeyenin "Yok" kutusunu işaretler. Yaprak 2 künye,
  gözetmen kontrol listesi, sayım ve teslim zincirini taşır; kontrol listesi
  maddeleri plana göre yeniden yazıldı ("Öğrenciler fotoğrafla eşleştirilip
  oturtuldu", "Plandaki imzalar alındı; girmeyenler işaretlendi").
* **Kart geometrisi hesaplanır** (`photo_plan_metrics`, kroki deseni): masalı
  satırlar kalan yüksekliği paylaşır, ön cephe bandı ince şerittir. İki düzen
  vardır ve BÜYÜK fotoğraf veren seçilir: DİKEY (fotoğraf üstte — tipik 5×4
  derslik) / YATAY (fotoğraf solda — 10×2 gibi derin salon). Fotoğraf 30 px'in
  altına inerse düşer (6×8 üçlü sıra gibi); ad, numara ve imza kalır.
  Ölçülen 8 geometride yaprak 1 tek sayfadır; `PHOTO_PLAN_BOX_PX = 820`
  ölçülen sınırın (835) altında pay bırakır.
* **Fotoğrafsız öğrenci** kartında fotoğraf yerine "fotoğraf yok" kutusu
  basılır; fotoğraf hiç aktarılmamış okulda plan yine tam çalışır.
* **Planda yeri olmayan öğrenci** (plan yerleşimden sonra daraltılmış):
  lejant satırı "DİKKAT: N öğrencinin koltuğu güncel salon planında yok…"
  uyarısına döner ve bu öğrenciler planın altında AYRI listede imza yeriyle
  basılır — kimse yoklamadan düşmez (A11'in yeni hâli).
* **KVKK satırı** yaprak 1'in altındadır; madde atfı yaprak 2 dipnotunda
  durur, yaprak 1'de tekrarlanmaz.
* **Uygulama içi eşi:** oturum detayındaki Yoklama sekmesi aynı planı salon
  salon gösterir (`YoklamaPlani`); karta basmak "Girmedi" işaretler, yeniden
  basmak onayla kaldırır. Salon planı yüklenemezse liste görünümüne düşülür —
  yoklama hiçbir koşulda alınamaz hâle gelmez.
* **Kaldırılan:** adlı kroki (`build_room_kroki(with_names=True)`,
  `KROKI_BOX_R1_PX`) — kroki artık yalnız boş salon planındadır.

**19.09.2026 — PDF motoru tek kapıdan, sırayla (çöküş tanısı).** Paketli program
(beta.6) "Tümünü indir" sırasında uyarı vermeden kapandı; Windows olay günlüğünde
`libpangoft2-1.0-0.dll` içinde erişim ihlali vardı. Makine kodu çözümlemesi: WeasyPrint
PDF'e yazı tipi gömerken Pango'dan NULL yazı tipi almış (`pango_fc_font_map_get_hb_face`
+4). Kurulu programın DLL'leri ve gerçek şablonlarla Windows'ta koşulan tanıda sıralı
basım (60 belge) hiç düşmedi; iki iş parçacığının eşzamanlı basımı yedi koşunun birinde
yığın bozulmasıyla (0xC0000374) düştü. Gömülü sunucu altı iş parçacıklıdır ve üç PDF yolu
(salon evrakı, kitapçık bandı, takvim) kilitsizdi. Kararlar (kullanıcı onaylı):

* **Tek kapı + kilit** — `shared.pdf.html_to_pdf`; basımlar süreç genelinde sırayla.
  Kilit süreyi uzatmadı (iş zaten Python kilidine bağlı). Koruma testi başka
  `write_pdf` çağrısına izin vermez.
* **Paylaşılan `FontConfiguration`** — Windows paketinde fontconfig önbelleği hiç
  yazılmıyor; paylaşım belge başına ~%4-9 hız kazandırdı (ölçüldü) ve her belgede
  fontconfig kurulumunu kaldırdı. Belgelerde `@font-face` yok (yalnız gömülü DejaVu).
* **Çöküş kaydı** — `faulthandler` açılışta `logs/cokme.log`a bağlanır; yerel çöküşte
  bütün iş parçacıklarının yığını (yalnız kod konumu) yazılır.
* **Ertelenen:** PDF üretimini ayrı alt süreçte koşmak (teknik borç TB15) — kayıt
  yeni bir çöküş gösterirse.

**20.09.2026 — BEP kapsamındaki öğrenciler + bireysel soru dosyası (kullanıcı
isteği).** İstek: "BEP kapsamındaki öğrencilerin sınavlarını da sisteme yükleyip
sınav evrakını isimlerine basalım; hangi öğrenciye ayrı sınav yapılacağını
kullanıcı seçsin; öğrenciyi ayrıştıracak bir işaret ne yoklama kâğıdına ne sınav
kâğıdına basılsın." Dayanak: ÖDY md. 4/1-ç, 5/1-n, 6/1-d · Yönerge md. 5/1-u ·
OKY md. 45/1-ğ · ÖDSHGM 10.09.2026 yazısı md. 8 · kanun düzeyinde 573 sayılı KHK
md. 16/1 ("sınavlarda gerekli önlemler alınır ve düzenlemeler yapılır"). OYS'de
karşılığı yoktur (yalnız `RuleReason.IEP` kategorisi vardı) — KS'ye özgü iştir.

* **İki kayıt** (`sinav/services_individual.py`): `IepStudent` kalıcı listedir ve
  YALNIZ üyelik tutar; `IndividualQuestionDocument` bir oturumda bir öğrenciye
  dersin soru dosyası yerine basılacak PDF'tir — satırın VARLIĞI seçimdir, dosya
  sonra yüklenir. Kullanıcı kararları: liste kalıcı + seçim oturumda; parola
  zorunlu değil, uyarı var; basılı bilgi yalnız idare özeti.
* **Öğrenci aynı ders grubunda kalır.** `conflict_group` değişmez: yerleşim, "aynı
  seed → aynı dağıtım", salon evrakı, ders kodu rozeti ve sayım tablosu bireysel
  dosyadan HABERSİZDİR. Bireysel dosya yalnız `booklet.build_room_package`in
  doküman sözlüğünde kendi anahtarıyla yaşar (`"<grup anahtarı>#<satır pk>"`);
  bant ders adı grubun adıyla AYNI yardımcıdan gelir (`services._band_course_name`).
* **İşaret yok — iki dolaylı iz kabul edildi.** Program kâğıdın KENDİSİNİ
  gizleyemez: sayfa sayısı ("Sayfa 1/2") ve soru bazlı puan tablosunun kutu sayısı
  farklı olabilir. Kelebek düzeninde komşular zaten farklı sınav çözdüğü için göze
  batmaz; "kendi dersliğinde" düzeninde batabilir — panel "aynı sayfa sayısı ve tek
  puan kutusu" önerir, PDF'in içine ad yazılmamasını söyler.
* **İsimsiz yedek bireysel dosyadan basılmaz** (`booklet.CourseDoc.backup`, §11
  sapma notu): aksi hâlde salona tek öğrenciye özgü sınavın adsız kopyası düşerdi.
* **Seçili ama dosyasız öğrenci kitapçık üretimini DURDURUR** ("soru dosyası
  eksik dersler" kuralının eşi). Ret metni öğrenci kimliği taşımaz, yalnız sayı
  söyler; kim olduğu panelde görünür. Kitapçığı bireysel dosyadan basılacak
  öğrenci, grubunun ders dosyasını gerektirmez (tek öğrencili mazeret oturumu).
* **Bayatlık.** Satırlar KATI silindiği için "bireysel dosyaya dokunuldu" damgası
  oturumda durur (`ExamSession.individual_changed_at`); üretimden sonra seçim,
  değiştirme ya da kaldırma üretimi `is_stale` yapar.
* **İdare özeti** (`bep_idare_ozeti.html`): oturuma giren BEP'li öğrenciler — salon,
  koltuk, okul no, ad, şube, ders, "basılacak kitapçık". `REPORT_CODES`te DEĞİLDİR:
  "Tümünü indir" paketine girmez, ayrı uçtan bilerek indirilir. Gözetmen/salon
  nüshası ÜRETİLMEZ (kullanıcı kararı — bilgiyi idareci kendisi aktarır). Dipnot
  md. 6/3 bendi göstermez (açık karar — `docs/mevzuat/kvkk-6698.md` "Değerlendirme
  notları — BEP").
* **KVKK (md. 6'ya işaret eden veri).** Şifreli öğrenci bağı (§5); tanı/açıklama/
  serbest metin alanı YOK; satırlar KATI silinir — öğrenci pasifleşince/silinince
  anında (`persons.register_student_forget_hook` → `forget_student`; bağımlılık
  yönü sinav → okul korunur), kancaya uğramayan yollar için okumada
  (`purge_stale`), arşiv anonimleştirmesinde, oturum silinince ve "Tüm BEP
  kayıtlarını sil" düğmesiyle; listeden çıkarma yalnız ONAYLANMAMIŞ oturumların
  dosyalarını düşürür (onaylı/arşiv oturumun kaydı o sınavın yapıldığı hâlin
  parçasıdır). Bireysel PDF diske `soru_b_<uuid>.pdf` adıyla yazılır; hata, günlük
  ve uç YOLU öğrenci kimliği taşımaz (öğrenci pk'si gövdede, satır kimliği opak).
* **Bilinçli olarak yapılmayanlar.** Ek süre / öğrenciye özgü süre (salon evrakına
  basılsa işaret olurdu); "bu derste hep ayrı kâğıt" gibi ders bazlı kalıcı tercih
  (hangi derslerin uyarlandığı da veridir); e-Okul'dan BEP aktarımı.

Şablonlar: `templates/sinav/reports/` (base · _head · _kroki · _kroki_style ·
_foto_plan · _foto_plan_style · r1_salon_evraki · r4_announcement ·
r6_assignment · r7_tutanak · r8_validation · room_layout · bep_idare_ozeti) + `booklet_overlay` + `calendar_pdf` +
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
  sınav; 3. tur dönemin son iki haftası elle. **19.09.2026 eki:** Bakanlık bir
  ders yılının haftalarını ayrıca ilan ettiyse varsayılan İLANDIR
  (`official_windows.OFFICIAL_WINDOWS` → `services_calendar.default_window`;
  2026-2027: ÖDSHGM 10.09.2026 / E-26614336-480.99-168561496 — 2-13 Kasım,
  4-15 Ocak, 29 Mart-9 Nisan, 7-18 Haziran). "Kılavuz uyumlu varsayılan,
  değiştirilebilir" ilkesi: yeni takvim tarihleri ilanla dolar, takvim sayfası
  farkı öneri olarak gösterir, hiçbir yerleştirme buna göre reddedilmez.
  Yazının md. 7'si ("son günden başlanarak") otomatik yerleştirmede TERCİHTİR
  (`from_last_day`, varsayılan açık). Göç `sinav/0013` yalnız dokunulmamış ve
  yerleştirmesiz taslakları ilana çeker. **Aynı gün eki — ülke geneli sınavlar:**
  yazının eki (`official_windows.NATIONAL_EXAMS`; lisede 10. TDE 12.11.2026, 9.
  Matematik 06.01.2027, 9. TDE 07.04.2027, 10. Matematik 09.06.2027) takvim
  oluşturulurken uygulanır (`apply_national_exams`): girdi Bakanlık sınavı olur,
  resmî GÜNÜNE okulun ilk uygun sınav saatiyle SABİTLENİR. Ek ders saati vermez —
  saati idareci düzeltir (kullanıcı kararı; havuzda bekletme seçeneği reddedildi,
  çünkü o zaman gün okul sınavlarına ancak elle yerleştirmeden sonra kapanırdı).
  Yönerge md. 5 gereği o gün o düzeye otomatik okul sınavı konmaz (mevcut üst
  makam kuralı).
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
- **Mazeret takibi ve mazeret sınavı** (19.09.2026, kullanıcı isteği ve
  kararları — `services_makeup`, ekran `/mazeret`): kaynak yoklama kaydıdır
  (`ExamAttendanceRecord`); dönemin bütün kayıtları tek listede izlenir.
  Mazeret sınavı Mazeret Takibi ekranından TOPLU açılır: seçilen kayıtlar tek
  TASLAK oturuma (`ExamSession.is_makeup`) girer, farklı günlerin sınavları
  birleşebilir, her (ders, düzey) bir `ParticipantType.MAKEUP` satırıdır
  ("Mazeretli öğrenciler"); salon/dağıtım/evrak/yoklama normal akıştır.
  Katılımcılar kayıttan ANLIK türetilir — YALNIZ "Mazeretli" + aktif öğrenci
  (OKY md. 48/1 "özrünü belgelendirenlerin"; Yönerge md. 5/1-aa); durum sonradan
  değişirse öğrenci düşer, dağıtılmış oturumda `placement_drift` bandı çıkar.
  "Bir defaya mahsus" (OKY md. 48/1; ülke/il/ilçe geneli için ayrıca Yönerge
  md. 5/1-çç): mazeret oturumundaki kayda ikincisi açılmaz. Süre dönemi aşamaz
  (48/1) → kayıtlar tek dönemden, mazeret oturumunun dönemi değiştirilemez.
  Aynı öğrenci bir oturumda iki derse düşemeyeceği için iki mazerete birden
  alınamaz. 5 iş günü (Yönerge md. 5/1-y; OKY md. 36/7 zorunlu hâlde 20 iş
  gününe uzatma) UYARIDIR — kullanıcı kararı "uyarsın, karar idarenin"; tatil
  verisi yok, hafta sonu düşülür. Rapor PDF (resmî antet, Düzenleyen — Müdür
  Yardımcısı / UYGUNDUR Okul Müdürü) + Excel; bölümler: tüm girmeyenler, e-Okul'a
  "G" (OKY md. 48/4, Yönerge md. 6/1-f), mazeret sınavı bekleyenler, il/ilçe
  MEM'e bildirim (Yönerge md. 5/1-z; oturum türü "Okul" dışı + Mazeretli).
  Ülke/il geneli sınavların mazeret TARİHİ il MEM'ce ilan edilir (md. 5/1-aa) —
  ekran uyarır, tarih idarecinin girdisidir.
- **Mazeret sınav takvimi** (20.09.2026, kullanıcı isteği ve kararları —
  `makeup_schedule`, `services_makeup_plan`): son sınav yapılıp yoklamalar
  girildikten sonra YALNIZ mazeret sınavlarını içeren ayrı takvim. OKY md. 48/1
  mazeret sınavının "önceden duyurularak" yapılmasını ister — takvim o duyurudur.
  Parametreler idarecinin: ilk gün, kaç güne sığacağı (hafta içi sayılır), öğrenci
  başına günlük en çok sınav (1-3; 2 esas, 3 zorunlu hâl — Yönerge md. 5/1-s,
  OKY md. 45/1-g), ders saatleri, sıra kipi. Kapsam öğrenci öğrenci bilindiği için
  çakışma ve günlük sınır KESİN denetlenir (olağan takvimin düzey/şube yaklaşıklığı
  burada yok). Kararlar: (1) sıra kesin korunur, "boş saatlere öne çek" seçeneğiyle
  öğrenci bazına gevşetilir; (2) sığmayan reddedilmez — gerekçesiyle listelenir ve
  "en az N gün gerekir" söylenir; (3) ülke/il/ilçe geneli sınavlar otomatik
  yerleşmez, idareci il/ilçe MEM'in ilan ettiği gün ve saate sabitler (Yönerge md.
  5/1-aa, bb); (4) ilan nüshası ADSIZDIR (tarih, saat, ders, öğrenci sayısı), öğrenci
  listeli nüsha ayrı belgedir ve adlar gizlenip yalnız okul numarasıyla basılabilir;
  (5) onaylı takvimin oturumları tek tıkla üretilir, aynı saatteki sınavlar tek
  oturumda toplanır. Dönem sınırı (OKY md. 48/1 "dönemi aşamaz"), hafta sonu, olağan
  sınav haftasıyla çakışma ve üst makam günü UYARIDIR ("katı bir kısıtlama olmasın").
- **BEP kapsamındaki öğrenci** (20.09.2026): ölçme ve değerlendirmede BEP esas
  alınır (ÖDY md. 4/1-ç, 5/1-n, 6/1-d; Yönerge md. 5/1-u; OKY md. 45/1-ğ) ve sınavı
  BEP'i doğrultusunda ders öğretmenince hazırlanır (ÖDSHGM 10.09.2026 yazısı
  md. 8) → oturumda "bireysel soru dosyası". Invariantlar: çakışma grubu DEĞİŞMEZ;
  salonlara giden evrakta ve kitapçık bandında ayıran işaret YOKTUR; seçili ama
  dosyasız öğrenci üretimi durdurur; idare özeti pakete girmez; ret/günlük/uç yolu
  öğrenci kimliği taşımaz (§9).
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
>
> **20.09.2026 sapması (`booklet.py` — AYNEN sınıfında KALIR):** `CourseDoc`'a
> VARSAYILANLI tek alan eklendi (`backup: bool = True`) ve isimsiz yedek döngüsü
> `backup=False` dokümanı atlar. İmzalar, varsayılan davranış ve çıktı DEĞİŞMEDİ;
> alan yalnız bireysel soru dosyası için `False` verilir (§9). Emsal:
> `validator.PlacedStudent` etiket alanları — aynı "varsayılanlı genişletme" deseni.
> Soru PDF'i doğrulaması (`question_pdf.validate_question_pdf`) `services
> .upload_question_document`ten AYNEN taşındı; ders dosyası ve bireysel dosya
> ortak kullanır, kurallar ve ret metinleri aynıdır.

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
| **F6 eki-2 (03.09.2026)** | Ders saati ayarı (`daily_period_count` + `exam_period_nos`; varsayılan zil çizelgesi ondan türer) · aynı slotta kapsam kesişimi SERT kısıt · salon kapasitesi uyarısı · `is_pinned` sabitleme · `auto_place_entries` (FILL/REDISTRIBUTE) + `auto-place` ve `pin` uçları · kılavuz bölümü | Otomatik dağıtım günde ikiyi geçmez ve sınav saatleri dışına çıkmaz; üst makam sınavı yerleştirilmez, rapora gerekçesiyle düşer; sabitlenen girdi REDISTRIBUTE'ta yerinde kalır; kapsamı kesişen ikinci sınav 400 alır ve eski çakışmalar `calendar_validation`da görünür; aynı havuz → aynı dağıtım; `_daily_exam_load` DEĞİŞMEDEN yeşil |
| **F6 eki-3 (03.09.2026)** | Seçmeli ders şube kapsamı ders havuzuna taşındı (`CourseSectionOffering` = (ders, ders yılı, seviye) → şubeler; Ders Havuzu ekranında "Şubeler" sütunu + diyalog) · `fill_calendar_pool` şubesi tanımlı yazılı seçmelileri de çeker · seçmeli seçim diyaloğu ve toplu ekleme kapsamı katalogdan ön-doldurur · takvim girdisi kopyayı tutar, fark "özel" rozetiyle görünür | Kapsam yalnız SEÇMELİ derse yazılır ve tam değiştirme yapar; silinmiş şube okumada düşer; kapsamsız seçmeli havuza GİRMEZ ve `skipped`'a nedeniyle yazılır; gönderilen kapsam katalogu ezer ve rozet üretir; yıl geçişinde kopyalama yok (her yıl yeniden girilir) |
| **F3 eki-2 (18.09.2026)** | Saha vakası (TDE 9 + TDE 10 oturumu): "Ortak kitapçık" kutusu MEB'in "ortak sınav" terimiyle karışıp her satırda işaretlendi → iki seviye tek çakışma grubu sayıldı, ikinci soru dosyası reddedildi, dağıtımdan sonra geri yol yoktu. Düzeltme: bayrak ders-başı ayar (kardeşlere yayılır, ret kalktı; ekleme formundan çıktı), Sorular paneli aynı-kitapçık grubunu tek satırda gösterir, `revert_session_to_draft` (DAĞITILDI → TASLAK, "Taslağa al"), karma seviyeli evrakta ders adı seviyeli (`_seat_course_names`), R8 çok satırlı `{# #}` sızıntısı `{% comment %}` ile kapandı | Kardeş senkron + miras testi; taslağa alma yerleşimi siler ve tanımı korur, tam döngü yeniden dağıtılır; R1/R7 karma seviyede "Coğrafya — 9. Sınıf" basar; R8 çıktısında `{#` yok; FE: ders-başı kutu `updateCourse` çağırır, panelde tek satır/tek Yükle, "Taslağa al" onay diyaloğundan geçer |
| **Değerlendirme turu (18.09.2026)** | `docs/degerlendirme/2026-09-18-…` planının uygulanması. Doğruluk: silinmiş salonun evrakı, soru dosyasının diskten silinmesi + silme ucunda durum kapısı, yoklaması alınmış oturumda yeniden dağıtım/taslağa alma reddi, sabit koltukta takas reddi, oturum silinince kural/muafiyet temizliği, ölü oturum bağının takvimde serbest kalması (`has_live_session`), ders birleştirmede grup anahtarının yeniden yazılması, MEB dersinde ad değişikliği reddi, merkezî Django `ValidationError` çevirisi, eksik medya dosyasında Türkçe 404, ön-sürüm doğal sıralaması. Evrak: §9 "18.09.2026 evrak revizyonu". Dil: `docs/sozluk.md` bağlayıcı sözlük; iç kod ve `id=` sızıntıları temizlendi; mazeret etiketleri "Mazeretli/Mazeretsiz". Mevzuat: OKY seçilmiş maddeleri depoya alındı, tüm atıflar metinden doğrulandı. Süreç: `kapilar.yml` (kapı betiği CI'da), backend test kapsamı %88 → %92 | Her düzeltme kendi regresyon testiyle; sayfa bütçesi testleri GERÇEK uzunlukta ders adlarıyla; `bash scripts/gates.sh` uçtan uca yeşil |
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
   takvim girdisine şube kapsamı gelmesi bu kuralı DEĞİŞTİRMEZ — kapsam
   katılımcı önizlemesinde, slottan oturum üretiminde ve (03.09.2026'dan beri)
   aynı SLOT kesişimi sert kısıtında kullanılır; `_daily_exam_load` şube
   listesine bakmaz (TB10). **19.09.2026 eki:** seçmeli ders öğrenci listesi
   (§7.3) gerçek kayıt verisidir ve günlük limite girer — ama yalnız dersin o
   seviyedeki BÜTÜN kapsam şubelerinde liste varken; eksik listede düşüş aynen
   işler.
5. **Fontconfig/DejaVu:** fonts.conf'ta DOCTYPE kalırsa sessiz ret → bozuk
   Türkçe evrak; build.ps1 ezme adımı atlanmamalı.
6. **Kimlik çakışması:** Inno AppId GUID yenilenmez veya `DD_*` kalıntısı
   kalırsa iki uygulama aynı makinede veri karıştırır.
7. **UTC tarih tuzağı:** 00:00-03:00 arası bir gün geri kayma —
   format.test.ts koruma testi taşınmazsa sınav tarihli evrakta nüksedebilir.
8. **Okul türü verisi (U4):** 03.09.2026'dan itibaren sekiz türün çizelgesi
   gömülü (§7.2); kalan boşluklar (MTAL seçmeli/meslek dersleri, GSL önceki
   nesil) uyarıyla görünür, elle ekleme yolu açık.
9. **F27 geri dönüşsüz:** onay diyaloğu + aday listesi olmadan tetiklenirse
   veri kaybı şikâyeti kaçınılmaz.
10. **Takvim damgaları:** tek-kullanıcı sadeleştirmesi onaylayan/tarih
    damgalarını silerse basılan takvim PDF'inin resmî değeri düşer.

## 14. Açık işler / teknik borç başlangıcı

- e-Okul PDF parser'ları (şube listesi, personel) → v2 adayı. (Seçmeli Ders
  Öğrencileri raporu 19.09.2026'dan beri PDF'ten okunur — Excel ihracında ders
  adı yok, §6.)
- Okul türü çizelgeleri: sekiz tür gömülü (§7.2, 03.09.2026). Kalan
  küratörlük: GSL önceki nesil çizelgeleri (2023/41, 2024/46; Spor'unki
  19.09.2026'da TTK 2026/102-103 ile gereksizleşti), MTAL
  seçmeli dersler tablosu (2026/62 — taranmış PDF, OCR/elle aktarım gerekir),
  hazırlıklı MTAL (2024/42, 2026/63), ÖP Fen/SBL (2025/24-25), ÖP hazırlıklı
  Anadolu Lisesi (2026/104). Meslek dersleri
  özel: ortak sınavın en az biri uygulamalı yapılır (Yönetmelik md. 5/1-h) —
  sınıflama zümre kararına bağlı, katalogla taşınmaz.
- Ortaokul/ilkokul kademesi → seviye kümesi parametrik olduğunda değerlendirilir.
- okulapp.org yayın alanı: sürüm kartı + tanıtım sayfaları (DD deseni;
  `okulapp.org/CLAUDE.md` "Ortak çalışma düzeni"ne tabi).
