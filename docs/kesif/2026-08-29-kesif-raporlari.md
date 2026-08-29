

================================================================================
AJAN: be
================================================================================

# OYS `sinav_islemleri` Backend Analizi (kelebek-sinav portu için)

Kök: `C:\Users\aalid\.claude\apps\okulapp\backend\apps\sinav_islemleri` — 85 dosya, ~898K, 16.580 satır Python. Büyük dosyalar: `services.py` 2354, `models.py` 1121, `services_calendar.py` 1096, `views.py` 1077, `engine.py` 533, `views_calendar.py` 540, `serializers.py` 509, `reports.py` 445, `layout.py` 331, `selectors.py` 280, `participants.py` 260, `booklet.py` 225, `validator.py` 162, `word_template.py` 110.

## 1. Modeller ve FK haritası (`models.py`)

Hepsi `shared.models.BaseModel` mirası: `created_at/updated_at/created_by/deleted_at/deleted_by` + `objects` (canlı) / `all_objects` soft-delete yöneticileri; teklikler hep `condition=Q(deleted_at__isnull=True)` kısmi unique.

**Salon/oturum çekirdeği:**
- `ExamRoom` (satır 44): `name` (uq alive), `block`, `linked_section` → FK **core.Section** (PROTECT; "bu salon 11-C'nin dersliği"), `layout_plan` JSONField (şema `layout.py`'da doğrulanır), `numbering_scheme` (S_PATTERN/STRAIGHT), `is_active`. Kapasite alan değil — plandan hesaplanır.
- `ExamSession` (140): `name, exam_date, start_time, duration_minutes(40)`, `session_type` (SCHOOL/DISTRICT/PROVINCE/NATIONAL), `layout_mode` (BUTTERFLY/HOME_CLASSROOM — K3), `proctors_enabled` (K2, varsayılan False), `semester` → FK **core.Semester**, `status` (DRAFT→DISTRIBUTED→APPROVED→ARCHIVED), `distribution_params` JSON (seed/strict/checkerboard/placed/pinned/rooms_per_section/warnings), `transfer_check_confirmed_by/at` + `approved_by/at` → FK **core.User**, `anonymized_at` (F27).
- `ExamSessionCourse` (229): session FK, `course` → FK **ders_yapisi.Course** (PROTECT), TEK `level` (uq: session+course+level alive), `participant_type` (LEVEL/SECTIONS/GROUPS), `section_ids`/`group_ids` JSON id listeleri (PII tutulmaz), `duration_minutes` (boş=oturum süresi), `shared_booklet` (K7 — kardeş satırlarda senkron).
- `ExamSessionRoom` (295): session+room, `order`, `capacity_override`.

**Yerleşim/kurallar (kişisel veri):**
- `SeatAssignment` (338, kvkk=True): student FK (core.Student, null=arşiv anonim) + **SNAPSHOT** `full_name/student_number/class_label`, room FK, koltuk kimliği `desk_row/desk_col/slot` + `seat_no`, `status` (NORMAL/PINNED/MANUAL), `conflict_group` ("<course_id>:<level>" veya ":*"). Uq: (session,room,seat_no) ve (session,student).
- `ExamAttendanceRecord` (420, kvkk=True): sınava GİRMEYEN kaydı — snapshot alanları + `excuse_status` (PENDING/EXCUSED/UNEXCUSED) + serbest `note` (belge no/tarih; tanı yazılmaz). Uq (session,student).
- `PlacementRule` (520, kvkk=True + `kvkk_special_category=True`): scope SESSION/PERMANENT (oturum kuralı kalıcıyı ezer), `rule_type` (HOME_CLASSROOM/FIXED_ROOM/FRONT_ROW/SEPARATE_ROOM), `target_room`, `reason_category` YALNIZ kategori (DISABILITY/IEP/HEALTH/OTHER — serbest metin alanı bilinçli yok).

**Gözetmen (K2 opsiyonel):**
- `ProctorAssignment` (663, kvkk=True): teacher FK **core.User** + `teacher_name` snapshot, `role` PROCTOR/RESERVE (CHIEF Tur 235'te kaldırıldı — salon başına TAM 1 gözetmen, uq (session,room,role=PROCTOR)), `acknowledged/acknowledged_at` (tebliğ-tebellüğ).
- `ProctorExemption` (742, kvkk special): teacher + scope + `reason_category` (HEALTH/DUTY/OTHER).

**Soru/kitapçık:**
- `QuestionDocument` (605): session_course FK + kısmi unique (yeniden yükleme soft-delete), `file` PDF, `page_count`, `sha256`, `score_mode` (SINGLE_BOX/QUESTION_TABLE), `question_count`. Ölçekleme yok — bant sabit 4 cm.
- `BookletRun` (812, kvkk=True): status PENDING/IN_PROGRESS/COMPLETED/FAILED, `file` ZIP, `backup_copies`, `manifest` JSON (PII'siz), `error_message`, `completed_at`.

**Takvim (ADR-0044, FAZ T):**
- `ExamCalendar` (879): school_year+semester FK (core), `round` 1-3 (uq year+sem+round), `start/end_date` (CheckConstraint), status DRAFT/SUBMITTED/APPROVED, `description_text` (varsayılan mevzuat-metinli), submitted_by/approved_by.
- `ExamCalendarEntry` (973): calendar FK, course FK (ders_yapisi), `level`, `exam_kind` (WRITTEN/PRACTICE), `is_butterfly`, `placed_date`+`period_no` (CheckConstraint: birlikte boş/dolu), `session` → FK ExamSession SET_NULL (slot→oturum bağı).
- `ExamTrackItem` (1044): global süreç kalemi kataloğu (migration 0021'de 8 kalem seed: KSD ilanı→soru+CA teslimi→basım→paketleme→uygulama→'G' girişi→puan girişi (10 iş günü)→analiz raporu).
- `ExamTrackMark` (1075): entry×item uq, status DONE/NOT_APPLICABLE ("yapılmadı"=kayıt yokluğu), `marked_by/at`.

**Dış FK özeti:** core.Section, core.Semester, core.SchoolYear, core.User, core.Student — hepsi katılımcı/onay/dönem bağları. ders_yapisi.Course (2 model). Bildirim/zumre/program/gorevlendirme'ye FK YOK (yalnız servis çağrısı).

## 2. Servis katmanı haritası

### 2a. KELEBEK motoru — `engine.py` (SAF, Django'suz; port için altın)
`distribute_butterfly(participants, rooms, *, seed, strict, preplaced, previous_seats)` (408):
- **Faz 0** üç kademe: `_room_quotas` (94, en-büyük-kalan, kapasite-oransal doluluk dengesi E2) → `_group_room_quotas` (112, her çakışma grubu salon kotalarına oransal bölünür) → `_pack_section_chunks` (141, şubeler first-fit-decreasing ile salonlara BÜTÜN paketlenir — şube başına salon sayısı 1-2'ye iner). Salon-içi karışım `_deal_order` (75, boyut-azalan ağırlıklı round-robin).
- **Faz 1** `_constructive_fill` (242): koltuklar S-rota sırasında gezilir; kuyruk rotasyonu `_LOOKAHEAD=24`; komşuluk 2D geometriden (rota sırasından DEĞİL). Ceza `_pair_penalty` (203): aynı sıra=∞ (sert), 1. halka (Chebyshev≤1) +`_FIRST_RING_WEIGHT=10`, diğer 1/d². Önceki oturum aynı-sıra `_PREV_SEAT_WEIGHT=5` yumuşak ceza.
- **Faz 2** `_local_search` (337): `random.Random(seed)` — ikili takas + boş koltuğa taşınma; bütçe `min(6000, 40×max(n,koltuk))`; yalnız iyileştiren hamle. **Aynı seed → aynı sonuç (deterministik).**
- Kenar durumlar: tek grup + kapasite ≥ 2N → satranç modu `_checkerboard_seats` (pinliyken atlanır); baskın grup (>kapasite/2) uyarısı; kapasite yetersiz → Türkçe ValueError.
- `distribute_home_classroom` (496): klasik düzen — şube→derslik eşlemesi ("9/A"→RoomSeats), okul no sırasında (sayısal önce); eksik eşleme/kapasite Türkçe ValueError.
- Girdi/çıktı saf dataclass'lar: `RoomSeats`, `Placement`, `DistributionResult`, `PrevSeats = dict[student_id → (room_id,row,col)]`.

### 2b. Salon planı — `layout.py` (yalnız `django.core.exceptions.ValidationError` bağımlılığı)
`validate_layout_plan` (166): JSON şema — `grid{rows,cols}` (max 30×30) + `desks[{row,col,type:SINGLE/DOUBLE/TRIPLE,disabled}]` + `furniture[{kind:DOOR/BLACKBOARD/SMART_BOARD/TEACHER_DESK,row,col,facing}]`; hücre çakışma, tek öğretmen masası kuralı; Türkçe hatalar. `numbered_seats(plan, scheme)` (275): referans=öğretmen masası→tahta→(0,0); başlangıç=referansa en yakın aktif sıra; sütun yönü sol/sağ yarıya, satır yönü ön/arka yarıya göre; S düzeni sütunlarda yön ters; `slot` fiziksel sol→sağ; koordinat `x = col + (slot-(size-1)/2)/size, y = row`. `default_section_plan` (62): 4 sütun × 5 sıra ikili = 40 koltuk, kapı sol-ön, öğretmen masası sağ-ön; `DEFAULT_LAYOUT_PLAN` 5×4 boş.

### 2c. Katılımcı çözümleyici — `participants.py`
`resolve_session` (191): LEVEL→`core_selectors.level_roster(level)`; SECTIONS→`get_section`+`section_roster`; GROUPS→`get_section_group`+`group_member_student_ids`+şube roster kesişimi. Çakışma grubu `_conflict_group`: shared_booklet→`"{course_id}:*"`, değilse `"{course_id}:{level}"`. Ders içi mükerrer teklenir; **öğrenci iki derste = sert çakışma** (`has_blocking_conflicts` → dağıtım reddedilir). `overlapping_session_conflicts` (227): aynı tarih + zaman aralığı kesişen oturumlarla ortak öğrenci uyarısı (okul no ile, ad asla — KVKK).

### 2d. Bağımsız doğrulayıcı — `validator.py` (tamamen saf, sıfır import motor)
`validate_seating(placed, *, strict, enforce_group_separation)` (78): sert=aynı grup aynı sırada (desk kimliğinden, mesafeden değil); strict=1. halka da sert; bütünlük (çifte koltuk/çifte öğrenci); metrikler: `first_ring_same_group_pairs`, `min_same_group_distance` (grup başına), `proximity_score` Σ1/d², `cross_group_same_section_first_ring_pairs` (K1 gözlem), `room_counts`. Klasik düzende yalnız bütünlük.

### 2e. `services.py` ana bölümleri
- Salon: `create_exam_room` (107), `update_exam_room` (140, `linked_section_id=...` sentinel), `generate_section_rooms` (188, şube başına derslik, `max(5, ceil(n/8))` satır, idempotent + orphan raporu), `room_seats`/`room_capacity`/`preview_room_seats` (266, kaydedilmemiş plan önizleme — iş kuralı backend'de).
- Oturum: `create/update_exam_session`, `remove_exam_session` (362, alt satırlar + takvim girdisi çözülür), `confirm_transfer_check` (381, Adım 0), `semester_options`, `pre_check_summary` (410, seviye sayıları + nakil özeti), `add/update/remove_session_course` (494+, tek-seviye doğrulama `_validate_participant_refs`, ders-seviye havuz uyumu, `_ensure_shared_booklet_sync`), `set_session_rooms` (584, replace semantiği).
- **Dağıtım:** `distribute_session` (672, @atomic): çözümleyici → sert çakışma engeli → seed yoksa `randrange(1,1e6)` → HOME_CLASSROOM ise linked_section haritası; BUTTERFLY ise `_resolve_rule_pins` (1148: HOME_CLASSROOM kuralı bağlı dersliğe, FIXED/SEPARATE hedef salona, FRONT_ROW ön sıra ilk boş; SEPARATE_ROOM salonu kelebekten çıkarılır; öğrenci-id sıralı deterministik) + `_previous_seats_map` (1133) → motor → bağımsız doğrulayıcı → eski yerleşim soft-delete + gözetmenler sıfırlanır → `SeatAssignment.bulk_create` snapshot → doluluk farkı uyarısı `_occupancy_gap_warning` (eşik %20) + `rooms_per_section` metriği → status=DISTRIBUTED + `distribution_params`.
- `swap_seats` (821, T11): yalnız DISTRIBUTED; iki aşamalı yazım (unique kaçışı seat_no=0 geçici); MANUAL işaret + doğrulayıcı raporu döner.
- `seating_report` (946): kayıtlı yerleşimi plandan koordinat türeterek yeniden doğrular; plan dağıtım sonrası değiştiyse "yeniden dağıtın" sert ihlali.
- Yaşam döngüsü: `approve_session` (989, sert ihlal varsa red), `reopen_session` (1018), `archive_session` (1037, arşivden evrak basımı açık).
- Kurallar: `create_placement_rule` (1057), `_effective_rules` (1117, SESSION > PERMANENT).
- Gözetmen: `assign_proctor` (1426, muafiyet+çakışma sert; kendi-şube elle atamada uygulanmaz), `auto_assign_proctors` (1506): havuz = aktif öğretmen − (muaf ∪ aynı-pencere görevli `_busy_teacher_ids` ∪ o saatte dersli `_lesson_busy_teacher_ids` (1354, **program köprüsü**: zil çizelgesi + `program.services.teachers_free_at`) ∪ devamsız `_absent_teacher_ids` (1396, **gorevlendirme köprüsü** `absent_staff_ids`)); adil yük `_semester_duty_counts`, kendi-şube kaçınma `advised_or_taught_sections`, 5 salona 1 yedek, replace semantiği. `proctor_candidates` (1605), `acknowledge_proctor` (1485).
- Soru/kitapçık: `upload_question_document` (1667): PDF magic + ≤20MB + pypdf sayfa + **A4 DİKEY doğrulaması** (595.28×841.89 ±6pt, /Rotate normalize; yatay/Letter red — Türkçe yönlendirmeli); `request_booklet_run` (1822, eksik dosya grup-anahtarı bazında ders adıyla listelenir), `generate_booklets_for_run` (1859, Celery gövdesi; testlerde doğrudan çağrılır).
- Yoklama (Tur 245): `mark_absent` (1982, yalnız APPROVED/ARCHIVED + anonim değil; snapshot SeatAssignment'tan), `update_attendance_record` (arşivde de açık), `unmark_absent`.
- F27 anonimleştirme: `anonymize_exam_session` (2049, ad/no→"—", FK'lar None, not silinir; düzen istatistiği kalır; all_objects dahil), `anonymize_expired_exam_archives` (2083, `EXAM_ARCHIVE_RETENTION_DAYS=730`, denetim.log_audit).
- Evrak: `render_room_layout_pdf` (2118, oturumsuz boş kroki), `render_session_report` (2210), `render_session_reports_zip` (2336).

### 2f. Takvim — `services_calendar.py` (ADR-0044)
- `statutory_window` (86): dönem+tur → mevzuat penceresi (`_WINDOW_MONTH`: d1r1=Ekim, d1r2=Aralık, d2r1=Mart, d2r2=Mayıs; ayın son Pazartesisi + 11 gün; tur 3 = dönemin son 2 haftası). `generate_default_calendars` (116, 2 dönem × 2 tur, idempotent, havuzu programdan doldurur).
- `DEFAULT_CALENDAR_DESCRIPTION` (34): 8 maddelik mevzuat-dayanaklı açıklama metni (ÖDY md.5, OKY md.45/48/49) — create'te kopyalanır.
- Havuz: `add_calendar_entry` (304, ders-seviye katalog uyumu eklenirken doğrulanır), `fill_calendar_pool` (358, `ders_yapisi.taught_course_levels`'tan; round 3 elle; created/existed/skipped raporu).
- **Yerleştirme:** `place_entry` (461): zil çizelgesi period doğrulaması; aralık dışı/hafta sonu/tatil uyarıları (`closed_calendar_events_between`); **günlük sınav yükü ÖĞRENCİ-BAZLI** `_daily_exam_load` (667, Tur 648/ADR-0044 karar 13): `ders_yapisi.course_level_student_ids` ile öğrenci başına sayım; kayıt verisi olmayan ders seviyenin tamamını kapsar (konservatif); **3. sınav=uyarı (OKY md.45 "günde ikiyi geçmemesi esası"), ≥4=hata**. `unplace_entry`, oturuma bağlı girdi taşınamaz/silinemez korumaları.
- Onay: `submit_calendar`/`approve_calendar`/`reopen_calendar` (262-290) + `_notify_calendar_event` (229, **bildirim sinyali** `exam_calendar_submitted`→MUDUR/ADMIN, `exam_calendar_approved`→MYRD/ADMIN, transaction.on_commit).
- **Slot→oturum (D4):** `create_session_from_slot` (552): yalnız APPROVED takvim; is_butterfly=True + oturumsuz girdiler; saat zil çizelgesinden (yoksa 08:00); ad kırpma (max_length koruması); LEVEL-tipi ders satırları + `section_rooms_for_levels` ile şube derslikleri ön-seçilir; girdiler session'a bağlanır.
- `calendar_grid` (732): FE+PDF ortak ızgara (seviyeler×günler×hücreler+havuz+doğrulama). `calendar_validation` (624). `entry_participant_preview` (703, `course_level_coverage`).
- PDF: `render_calendar_pdf` (915, WeasyPrint A4 YATAY, `calendar_pdf.html`; `_tr_date` Türkçe ay/gün sabitleri; `_calendar_signatures` (844): **zumre köprüsü `apps.is_installed("apps.zumre")` korumalı** — zümre başkanı imza blokları, yoksa boş imza çizgileri).
- Süreç takip: `create/update_track_item`, `set_track_mark` (999, upsert; note=None mevcut notu korur), `track_matrix` (1039, satır=girdi, sütun=aktif kalem).

### 2g. Kitapçık — `booklet.py` (saf) + `word_template.py`
- Yöntem: WeasyPrint başlık bandı OVERLAY + pypdf bindirme (ReportLab bilinçli red). Bant sözleşmesi: üst 4mm + 32mm ≤ 40mm; ölçekleme YOK; soru 1:1 A4 tuvale merge. `_header_page_indices` (86): ≤2 sayfa→yalnız 1.; >2→tek numaralı sayfalar; "Sayfa x/y" hepsinde. Salon başına TEK WeasyPrint render (90×4 sayfa < 30 sn hedefi). `build_room_package` (149): eksik grup öğrencileri atlanıp `missing_groups`'a; isimsiz yedek kopyalar gruplardan dönüşümlü. `package_zip` (218): salon adı=dosya adı.
- `word_template.py`: stdlib zipfile ile .docx (python-docx yok) — A4 dikey, üst marj 4 cm (2268 twip), 6 kurallık yönerge paragrafları (`_GUIDE_PARAGRAPHS`).

## 3. PDF/Rapor kataloğu (`reports.py` + `templates/sinav_islemleri/`)

Hepsi WeasyPrint (`render_pdf`, 380) — ortak `reports/base.html` (DejaVu Sans, `{% include "print/_design.css" %}` — **paylaşılan `backend/templates/print/_design.css`'e bağımlı**, @page A4 dikey + altbilgi üretim zamanı/Sayfa x-y/sınav adı; text-transform:uppercase YASAK — WeasyPrint TR "i→I" tuzağı):

| Kod | Belge | Şablon | Builder |
|---|---|---|---|
| R1 | Salon Oturma Planı (kroki) | `r1_kroki.html` | `build_room_kroki` (113) — GRID kimliğinden çizim, Seat.x/y ASLA |
| R2 | Salon Yoklama/İmza | `r2_attendance.html` | `build_room_attendance` (seat_no sıralı) |
| R2k | Şube Yoklama | aynı şablon | `build_section_attendance` (okul no sıralı) |
| R3 | Salon Kapı Listesi | `r3_door.html` | `build_door_lists` |
| R4 | Şube Duyuru Listesi | `r4_announcement.html` | `build_announcements` |
| R5 | Toplu Dağıtım Çizelgesi | — Excel | `build_r5_workbook` (388, openpyxl) |
| R6 | Gözetmen Görevlendirme/Tebliğ-Tebellüğ | `r6_assignment.html` | `build_assignment_context` (257) |
| R7 | Evrak Zarfı Kapağı/Salon Tutanağı | `r7_envelope.html` | `build_envelope_sheets` (285, ders deste sayımı) |
| R8 | Dağıtım Doğrulama Raporu | `r8_validation.html` | `build_validation_context` (328, doğrulayıcı metrikleri + seed/params) |
| R9 | Evrak Teslim Tutanağı | `r9_handover.html` | `build_handover_rows` (309, gözetmen adı basılı/elle) |
| R10 | Kitapçıklar | `booklet_overlay.html` | BookletRun ZIP (async) |
| — | Boş salon planı | `room_layout.html` | `render_room_layout_pdf` (PII'siz, kapıya asılır) |
| — | Takvim PDF | `calendar_pdf.html` | `render_calendar_pdf` (A4 yatay, imza blokları) |
| — | Soru şablonu | — | `build_question_template_docx` |

Sıralama yardımcıları: `student_number_sort_key` (sayısal önce), `class_label_sort_key` (9/A < 10/B seviye-sayısal).

## 4. Sinyaller/olaylar ve modül bağımlılıkları

`signals.py` BOŞ (7 satır — yayınlanan sinyal yok). Yön haritası:
- **ALINAN (dışa çağrı):** `core.selectors` (level_roster/section_roster/get_section/get_section_group/group_member_student_ids/active_student_counts_by_level/transfer_movement_summary/get_semester/semesters_for_year/get_active_school_year/list_sections/advised_or_taught_sections/closed_calendar_events_between/users_with_role/get_student), `core.services` (active_teachers/get_letterhead_identity/grade_level_options/file_serving.serve_protected_file), `ders_yapisi.services` (get_course/course_names_by_ids/level_label/normalize_levels/taught_course_levels/course_level_student_ids/course_level_coverage), `program.services` (bell_schedule_for_year/bell_schedule_for/teachers_free_at), `gorevlendirme.services.absent_staff_ids`, `zumre.services` (chairs_for_courses/school_chair — `apps.is_installed` korumalı zarif düşüş), `bildirim.signals` (exam_calendar_submitted/approved), `denetim.services` (log_audit, log_access SENSITIVE_READ).
- **VEREN:** hiçbir app `sinav_islemleri`'nden import etmez (yalnız `config/settings+urls`, `denetim/kvkk_scope.py` string model referansları — KVKK ihraç kapsamı, `bildirim` sinyal tanımı kendi tarafında). Modül temiz çıkarılabilir.

## 5. API yüzeyi (`urls.py` + `views.py`/`views_calendar.py`)

Router `api/v1/` altında: `exam-rooms` (CRUD-sil yok + `seats`, `layout-pdf`, `preview-seats`, `generate-section-rooms`), `exam-sessions` (CRUD + `pre-check`, `question-template`, `semesters`, `confirm-transfer-check`, `courses`, `rooms` PUT, `participants`, `distribute`, `seating`, `booklets`, `reports/<code>` (r1-r9+zip, ?room_id=), `swap-seats`, `proctors` GET/POST, `proctors/auto`, `proctor-candidates`, `approve/reopen/archive`), `exam-session-courses` (patch/delete + `question` GET/POST/DELETE + `question/download`), `placement-rules`, `proctor-assignments` (+`acknowledge`), `proctor-exemptions`, `booklet-runs` (+`download`), `exam-attendance-records`, `exam-calendars` (+`generate-defaults`, `default-description`, `fill-pool`, `entries`, `grid`, `pdf`, `participant-preview`, `create-session`, `submit/approve/reopen`, `track`, `track-mark`), `exam-calendar-entries` (+`place`, `unplace`), `exam-track-items`. İzinler: `permissions.py` — `_EXAM_MANAGERS = {ADMIN, MUDUR, MUDUR_YARDIMCISI}`; `CanApproveExamCalendar` yalnız MUDUR+ADMIN (dört göz); `CanViewExamTrack` +ZUMRE_BASKANI. Kişisel verili her okuma/indirme `audit.log_access(SENSITIVE_READ)` düşer; Django ValidationError → DRF 400 Türkçe.

## 6. Test kapsamı ve kritik iş kuralları

24 test dosyası, ~6.000 satır. Omurga: **motor çıktısı her testte bağımsız doğrulayıcıdan geçer**. Öne çıkanlar: `test_engine.py` (aynı seed=aynı çıktı, satranç modu, baskın grup, kapasite, şube yoğunlaşması), `test_layout.py` (S-rota, referans köşeleri, 2D tuzak `test_s_route_2d_trap`), `test_placement_rules.py` (pin seed'ler arası sabit, önceki-oturum kaçınma), `test_booklets.py` (başlık sayfa kuralları, A4 kontrolü, 90×4 performans, seviye başına ayrı soru dosyası), `test_calendar_api.py` (784 satır: öğrenci-bazlı günlük yük — ayrık kümeler uyarısız, 3.=uyarı, 4.=hata; havuz doldurma idempotent), `test_reports.py` (Türkçe karakter/taşma, tüm kodlar, görsel QA çıktıları), `test_archive_anonymization.py` (730 gün, geri dönüşsüz).

**Mevzuat kuralları kod içinde:** OKY md.45 günlük sınav limiti (öğrenci-bazlı, 2 esas/3 uyarı/4 red); OKY md.48 mazeret 5 iş günü + 'G'; OKY md.49 sonuç 10 iş günü; ÖDY md.5 statutory pencereler + KSD; tebliğ-tebellüğ; KVKK: snapshot deseni, kategori-only gerekçe, ad asla hata/uyarı metninde (okul no kullanılır), 730 gün saklama + anonimleştirme.

## 7. Port değerlendirmesi (kelebek-sinav: tek kullanıcı, çevrimdışı, girişsiz)

**AYNEN taşınabilir (saf/az bağımlı çekirdek):** `engine.py` (import: layout.Seat + participants.Participant — dataclass'lar), `validator.py` (sıfır bağımlılık), `booklet.py` (Django template.loader + weasyprint + pypdf), `word_template.py` (stdlib), `layout.py` (tek Django bağı ValidationError), `reports.py` builder'ları + sıralama anahtarları, tüm rapor şablonları (base.html'in `print/_design.css` include'u kopyalanmalı), booklet_overlay.html bant sözleşmesi, `services_calendar.py` statutory pencere/`_tr_date`/DEFAULT_CALENDAR_DESCRIPTION sabitleri, track item seed listesi.

**UYARLANACAK:** (1) core köprüleri → yerel Student/Section/Semester tablolarına (level_roster/section_roster imzaları küçük: `(id, ad, no, şube)` tuple'ları); (2) tek kullanıcı → tüm `created_by/approved_by/User` FK'ları, RBAC permissions, SENSITIVE_READ/AccessLog, bildirim sinyalleri SADELEŞİR/atılır; onay akışları tek tıka iner (ExamCalendar SUBMITTED ara durumu gereksizleşebilir); (3) Celery → senkron çağrı veya thread (`generate_booklets_for_run` zaten testlerde doğrudan çağrılıyor — task sarmalayıcı atılır, BookletRun status makinesi korunabilir); (4) `serve_protected_file`/FileField → yerel dosya sistemi; (5) `_lesson_busy_teacher_ids`/`_absent_teacher_ids` program+gorevlendirme köprüleri → yoksa boş küme (kod zaten zarif düşüşlü); (6) zumre imza köprüsü → elle girilen imza listesi (kod zaten `is_installed` korumalı, boş-imza dalı hazır); (7) letterhead_identity → tek kurumsal ayar kaydı; (8) `_daily_exam_load` ders_yapisi kayıt köprüsü → basitleşmiş yerel ders-öğrenci eşlemesi veya seviye-bazlı konservatif sayım (kod bu düşüşü zaten yapıyor).

**ALINMAYACAK:** JWT/axes/throttle katmanı, drf-spectacular, denetim.kvkk_scope ihraç altyapısı, bildirim modülü, Celery beat + redis, F27 gece görevi (tek kullanıcıda menü eylemi olabilir), transfer_check (e-Okul nakil senkronu OYS'ye özgü — istenirse basit onay kutusu), `ExamSessionType` DISTRICT/PROVINCE/NATIONAL ayrımı (okul-içi araç). WeasyPrint Windows'ta GTK bağımlılığı ister — disiplin-defteri-codex PyInstaller şablonundaki çözüm neyse ona uyulmalı; alternatif değerlendirilecekse bant/kroki şablonları WeasyPrint CSS'ine (@page, counter(pages)) sıkı bağlı olduğu unutulmamalı.

## key_facts
- Kelebek motoru engine.py SAF Python'dur (Django import yok; yalnız layout.Seat + participants.Participant dataclass'ları) — porta bire bir kopyalanabilir; validator.py sıfır bağımlılıkla tamamen bağımsız
- Determinizm sözleşmesi: distribute_butterfly(seed) ayni seed'de ayni sonucu verir; seed yoksa services.distribute_session random.randrange(1,1_000_000) üretir ve distribution_params.seed'e yazar (R8'de basılır)
- Motor 3 fazlı: Faz0 salon kotaları (en-büyük-kalan) → grup-salon kotaları → şube first-fit-decreasing paketleme; Faz1 kurucu (S-rota + LOOKAHEAD=24, ceza: aynı sıra=inf, 1.halka +10, 1/d², önceki-oturum +5); Faz2 seed'li yerel arama (bütçe min(6000, 40×n))
- Sert kısıt denetimi (desk_row,desk_col) KİMLİĞİNDEN yapılır, mesafeden değil — komşu sıra koltuk koordinatları çakışabilir (layout.py koordinat sözleşmesi: x = col + (slot-(size-1)/2)/size)
- Çakışma grubu anahtarı '<course_id>:<level>' veya shared_booklet'te '<course_id>:*' — soru dosyası, kitapçık ve R8 etiketleri hep bu anahtarla eşleşir (participants._conflict_group ↔ services._session_course_group_key birebir)
- SeatAssignment/ExamAttendanceRecord/ProctorAssignment SNAPSHOT deseni kullanır (full_name/student_number/class_label kopyalanır) — arşiv evrakı kaynak kayıt değişse de sabit kalır; tek kullanıcılı portta da korunmalı
- Oturum durum makinesi: DRAFT→DISTRIBUTED→APPROVED→ARCHIVED; yalnız taslak düzenlenir, dağıtım DRAFT/DISTRIBUTED'da, onay sert ihlal varsa reddedilir, arşivden evrak yeniden basılabilir (render/booklet guard'ları ARCHIVED kabul eder)
- PlacementRule 4 tip: HOME_CLASSROOM/FIXED_ROOM/FRONT_ROW/SEPARATE_ROOM; SESSION kapsamı PERMANENT'i ezer; pinli öğrenci PINNED statüsüyle yerleşir, motor taşıyamaz; SEPARATE_ROOM salonu kelebek listesinden çıkarılır; gerekçe YALNIZ kategori (serbest metin alanı bilinçli yok — KVKK Madde 6)
- Rapor kataloğu: R1 kroki, R2/R2k yoklama, R3 kapı, R4 duyuru, R5 Excel (openpyxl), R6 gözetmen tebliğ, R7 zarf/tutanak, R8 doğrulama, R9 teslim tutanağı, R10 kitapçık ZIP + oturumsuz boş salon planı + takvim PDF (A4 yatay) + Word soru şablonu (stdlib zipfile, python-docx yok)
- Tüm PDF'ler WeasyPrint 63.1 + pypdf 5.1.0 + openpyxl 3.1.5; ortak şablon reports/base.html backend/templates/print/_design.css'i include eder (kopyalanmalı); text-transform:uppercase YASAK (WeasyPrint Türkçe i→I tuzağı); DejaVu Sans
- Kitapçık motoru: overlay bandı üst 4mm+32mm≤40mm sözleşmesi; soru PDF'i ÖLÇEKLENMEZ (1:1 merge); ≤2 sayfa→bant yalnız 1. sayfa, >2→tek numaralı sayfalar; salon başına TEK WeasyPrint render (90 öğrenci×4 sayfa <30sn hedefi); upload A4 DİKEY zorunlu (595.28×841.89 ±6pt, /Rotate normalize)
- Günlük sınav limiti ÖĞRENCİ-BAZLIDIR (services_calendar._daily_exam_load, ADR-0044 karar 13): ders_yapisi.course_level_student_ids ile öğrenci başına sayım; kayıt verisi olmayan ders seviyenin tamamını kapsar (konservatif düşüş); 3. sınav=uyarı (OKY md.45), ≥4=ValidationError
- Takvim statutory pencereleri: dönem1 tur1=Ekim, tur2=Aralık; dönem2 tur1=Mart, tur2=Mayıs; ayın son Pazartesisi + 11 gün; tur 3 = dönemin son iki haftası (elle); DEFAULT_CALENDAR_DESCRIPTION 8 maddelik mevzuat metni create'te kopyalanır
- Slot→oturum üretimi (create_session_from_slot): yalnız APPROVED takvim; is_butterfly girdilerden DRAFT oturum; saat zil çizelgesinden (yoksa 08:00); şube derslikleri section_rooms_for_levels ile ön-seçilir; girdi.session bağı SET_NULL — oturum silinirse slot yeniden üretilebilir
- auto_assign_proctors havuzu: aktif öğretmen − muaf − aynı-pencere görevli − o saatte dersli (program köprüsü) − devamsız (gorevlendirme köprüsü); adil yük dönem sayacıyla, kendi-şube kaçınma, salon başına TAM 1 gözetmen, 5 salona 1 yedek; program/gorevlendirme köprüleri yoksa kod boş kümeye zarif düşer
- Zümre imza köprüsü apps.is_installed('apps.zumre') korumalı — modül yoksa derslerden boş imza çizgileri basılır; portta bu dal hazır sadeleşme noktası
- Hiçbir başka app sinav_islemleri'nden import etmez (yalnız config + denetim kvkk_scope string referansları) — modül temiz çıkarılabilir; signals.py boştur, tek dış sinyal takvim onay bildirimi (bildirim modülüne, on_commit)
- BaseModel deseni: soft-delete (deleted_at + kısmi unique 'alive' kısıtları) + created_by/updated_at; teklikler hep condition=Q(deleted_at__isnull=True) — SQLite'ta da çalışır, portta korunmalı
- Klasik düzen (HOME_CLASSROOM): ExamRoom.linked_section eşlemesinden şube→derslik, okul no sırasında (sayısal önce); eşlenmemiş şube Türkçe hata; kurallar uygulanmaz, doğrulayıcı yalnız bütünlük denetler (enforce_group_separation=False)
- Yoklama yalnız APPROVED/ARCHIVED oturumda işlenir (mazeret güncellemesi arşivde de açık — belge 5 iş günü içinde gelir, OKY md.48); mark_absent referansı SeatAssignment'tır, katılımcı yeniden çözülmez
- F27: ARŞİV oturum 730 gün (2 ders yılı) sonra geri dönüşsüz anonimleştirilir (ad/no→'—', FK'lar koparılır, not silinir; koltuk/salon/grup düzeni istatistik olarak kalır; all_objects dahil)
- Celery yalnız 2 görevde: generate_booklets (gövdesi services.generate_booklets_for_run — senkron çağrılabilir, testler öyle yapıyor) ve gece anonimleştirme; portta Celery tamamen atılabilir
- Test omurgası: motorun her çıktısı bağımsız validator'dan geçer; 24 dosya ~6000 satır; kritik testler: aynı-seed determinizm, satranç modu, S-rota 2D tuzağı, pin sabitliği, öğrenci-bazlı günlük yük senaryoları, kitapçık başlık sayfa kuralları, 90×4 performans
- Katılımcı çözümleyici DB'ye yazmaz — liste anlık türetilir; öğrenci iki derse düşerse sert çakışma (dağıtım engellenir); uyarı metinlerinde AD ASLA (okul no kullanılır — kod genelinde tutarlı KVKK kuralı)
- Salon planı JSON şeması: grid(max 30×30) + desks(SINGLE/DOUBLE/TRIPLE, disabled) + furniture(DOOR/BLACKBOARD/SMART_BOARD/TEACHER_DESK, tek öğretmen masası); numaralandırma referansı öğretmen masası→tahta→(0,0); S düzeni varsayılan; default_section_plan 4 sütun×5 sıra ikili=40 koltuk

## riskler
- WeasyPrint Windows'ta GTK/Pango yerel kütüphaneleri ister — PyInstaller onedir paketlemede en riskli bağımlılık; disiplin-defteri-codex şablonunda WeasyPrint emsali yoksa erken bir paketleme denemesi (spike) yapılmalı; tüm evrak katmanı (R1-R10, takvim, boş kroki) @page/counter(pages) gibi WeasyPrint'e özgü CSS'e sıkı bağlı, alternatif motora geçiş şablonların yeniden yazılması demek
- core köprüsü geniş: ~15 selector/servis fonksiyonu (level_roster, section_roster, get_letterhead_identity, grade_level_options, closed_calendar_events_between, active_teachers, advised_or_taught_sections...) yerel modellerle yeniden yazılmalı — imzalar basit ama davranış ayrıntıları (açık kayıt filtresi, nakilde üyelik kapanması) testlerle sabitlenmeli
- Öğrenci-bazlı günlük yük (_daily_exam_load) ders_yapisi'nin ders-öğrenci kayıt verisine dayanır; portta bu veri modeli yoksa kod konservatif seviye-bazlı sayıma düşer — seçmeli/grup derslerinde yanlış pozitif uyarılar geri gelir (OYS'nin Tur 648'de çözdüğü sorun)
- distribution_params/manifest/section_ids gibi JSONField'lar SQLite'ta sorunsuz ama kısmi unique + CheckConstraint'lerin SQLite karşılıkları migration'da doğrulanmalı (Django destekliyor; yine de WAL + tek dosya senaryosunda test edilmeli)
- Tek kullanıcıya indirgeme durum makinelerini bozabilir: approved_by/submitted_by/marked_by kaldırılırsa R6 tebliğ-tebellüğ ve takvim imza akışının evrak anlamı korunacak şekilde sadeleştirilmeli (unvan kuralları gereği resmî evrakta ad/unvan yine gerekir — kullanıcı ayarlarından beslenmeli)
- Önceki-oturum farklılığı (_previous_seats_map) tüm SeatAssignment geçmişini okur — portta arşiv/anonimleştirme politikası değişirse bu yumuşak kısıtın veri kaynağı da değişir
- Gözetmen öneri havuzunun program (zil çizelgesi/ders programı) ve gorevlendirme (devamsızlık) köprüleri portta büyük olasılıkla olmayacak — kod boş kümeye düşer ama bu, 'o saatte dersi olan öğretmen önerilir' davranış gerilemesi olarak kullanıcıya açıklanmalı
- pypdf ile bozuk/şifreli PDF'lerde upload doğrulaması istisna çeşitliliği gösterir — çevrimdışı masaüstünde hata raporlama kanalı olmadığından Türkçe hata mesajlarının kapsamı korunmalı
- Kitapçık üretimi bellek-içi çalışır (tüm soru PDF'leri + overlay bytes) — çok salonlu büyük oturumlarda masaüstü makinede bellek tüketimi test edilmeli (OYS hedefi 90 öğrenci×4 sayfa <30sn)


================================================================================
AJAN: fe
================================================================================

# GÖREV B — OYS Sınav Frontend Derin Okuma Raporu

Kök: `C:\Users\aalid\.claude\apps\okulapp\frontend\src\modules\sinav-islemleri` (22 kaynak dosya + 11 test; toplam 7.818 satır, test hariç ≈6.300). Yardımcı katmanlar: `src/ui` (M3 "Mürekkep" kiti, ADR-0048), `src/lib` (api/queryClient/download/roles/pagination).

## 1) Ekran / Rota Kataloğu

Rotalar `src/App.tsx` 189-195'te, hepsi `lazy()` import:

| Rota | Bileşen | Satır | İşlev |
|---|---|---|---|
| `/sinav-islemleri` | `SinavIslemleriHub.tsx` | 40 | 4 `HubFeatureCard`: Oturumlar, Salonlar, Ders Havuzu, Sınav Takvimi |
| `/sinav-islemleri/oturumlar` | `OturumlarPage.tsx` | 242 | Oturum listesi + "Yeni sınav oturumu" dialogu (ad, tarih, saat, süre, dönem, düzen BUTTERFLY/HOME_CLASSROOM, gözetmen aç/kapa). Durum rozetleri DRAFT→DISTRIBUTED→APPROVED→ARCHIVED. `StatusBadge` ve `formatDate` (gg.aa.yyyy) buradan export edilir |
| `/sinav-islemleri/oturumlar/:id` | `OturumDetayPage.tsx` | 180 | TASLAK'ta `SinavSihirbazi`; sonrasında sekmeler: Yerleşim / Sorular ve Kitapçıklar / Gözetmenler / Yoklama (yalnız APPROVED+ARCHIVED) / Rapor Merkezi. Üstte yaşam döngüsü: Taslağı sil, Onayla (DISTRIBUTED→APPROVED), Yeniden aç, Arşivle (geri dönüşsüz, salt-okunur + yeniden basım) |
| — (OturumDetay içinde) | `SinavSihirbazi.tsx` | 780 | 5 adımlı sihirbaz (aşağıda §5) |
| — (sekme) | `YerlesimPaneli.tsx` | 283 | Salon-sekmeli renkli kroki + tıkla-takas + doğrulayıcı raporu + doluluk çipleri |
| — (sekme) | `SorularPaneli.tsx` | 328 | Ders başına soru PDF yükleme (score_mode SINGLE_BOX/QUESTION_TABLE), Word şablonu indirme (4 cm üst boşluk), blob-URL `<embed>` PDF önizleme, kitapçık üretimi (R10) — 4 sn `refetchInterval` polling'li koşu listesi + ZIP indirme |
| — (sekme) | `GozetmenlerPaneli.tsx` | 339 | Salon başına `Autocomplete` ile gözetmen atama (`getDisabled` sözleşmesi: muaf/meşgul/dersli/devamsız/atanmış görünür ama seçilemez), Yedekler satırı, "Otomatik Öner" (replace semantiği + Confirm), tebellüğ işleme |
| — (sekme) | `YoklamaPaneli.tsx` | 215 | Sınava girmeyen işaretleme (salon listesinden), mazeret durumu PENDING/EXCUSED/UNEXCUSED + belge no/tarih notu; arşivde de güncellenebilir (MEB 5 iş günü kuralı) |
| — (sekme) | `RaporlarPaneli.tsx` | 105 | R1-R9 katalogdan (api.ts `REPORT_CATALOG`, 333-344) tek tek indirme + "Tümünü indir (ZIP)"; R1/R2/R3/R7 salon filtreli; R6 yalnız gözetmen modülü açıkken; R5 xlsx, diğerleri pdf |
| `/sinav-islemleri/salonlar` | `SalonlarPage.tsx` | 242 | Salon kart listesi (kapasite/blok/bağlı şube), yeni salon, "Şube dersliklerini oluştur" (40 koltuklu otomatik üretim, idempotent); seçilen salon aynı sayfada `RoomEditor`'e geçer (rota değişmez, state geçişli) |
| — (SalonlarPage içinde) | `RoomEditor.tsx` + `planEdit.ts` | 397+117 | Salon Editörü 2.0: 1-30×1-30 grid, TIKLA-YERLEŞTİR (DnD YOK — ADR-0016), 9 araçlı palet (tekli/ikili/üçlü sıra, öğretmen masası, tahta×2, kapı, kullanım-dışı anahtarı, silgi), canlı kapasite sayacı, backend `preview-seats` ile S-düzeni/düz koltuk numarası önizlemesi (her plan değişiminde çağrılır, `placeholderData: prev`), boş plan PDF'i indirme. `planEdit.ts` salt-immutable UI dönüşümleri: `applyTool`, `resizeGrid`, `capacityOf`, `cellContent`, `emptyPlan` (5×4) |
| `/sinav-islemleri/ders-havuzu` | `DersHavuzuPage.tsx` | 496 | MEB kataloğu + elle ders CRUD; seviye çipleri (0=Hazırlık), tür (COMMON/ELECTIVE), kaynak rozeti; MEB kaynaklı ad kilitli; filtre (seviye/tür/pasif) + offset sayfalama (25) |
| `/sinav-islemleri/takvimler` | `TakvimlerPage.tsx` | 281 | Takvim listesi (`DataTable`), durum DRAFT/SUBMITTED/APPROVED, dönem+durum filtresi, "Ön Tanımlı Takvimleri Üret" (mevzuat pencerelerine göre 4 taslak), yeni takvim dialogu (dönem, tur 1/2/3, tarih aralığı) |
| `/sinav-islemleri/takvimler/:id` | `TakvimDetayPage.tsx` | 290 | Sekmeler: Havuz / Yerleştirme / Süreç Takip / Önizleme; yaşam döngüsü Onaya Sun → Onayla → Taslağa Al; tarih düzenleme dialogu; PDF indir |
| — (sekme) | `TakvimHavuzPaneli.tsx` | 292 | "Programdan Doldur" (idempotent, round 3'te kapalı), elle ekleme (Autocomplete ders + seviye + Yazılı/Uygulama + "Kelebek değil"), katılımcı önizleme sütunu, yerleştirilen girdi silinemez |
| — (sekme) | `TakvimYerlestirmePaneli.tsx` | 307 | Izgara: satır=(gün, ders saati — zil çizelgesinden), sütun=seviye(+öğrenci sayısı); boş hücre "+" → o seviyenin havuz girdileri dialogda tıkla-yerleştir; dolu hücre çip + kaldır + oturuma git; hafta sonu uyarıyla yerleştirilebilir; APPROVED'da satır başına "Oturum Üret" (`create-session` → sihirbazı ön-dolu oturum) |
| — (sekme) | `TakvimTakipPaneli.tsx` + `KalemYonetimiDialog.tsx` | 307+239 | Excel "Sınav Takip" karşılığı matris: satır=ders+seviye, sütun=süreç kalemi; hücre tıkla-döngü boş→Yapıldı→Kapsam dışı→boş; "Not modu"nda tıklama not dialogu açar; tooltip kim/ne zaman/not; global kalem kataloğu CRUD (soft delete) |
| — (sekme) | `TakvimOnizlemePaneli.tsx` | 156 | Resmî PDF'in AÇIKLAMA bloğu (description_text) düzenleme + "Varsayılan metne dön" + onay damgaları (submitted_at/approved_at) + PDF indir; taslak/sunulmuşta "TASLAK" filigranı notu |

## 2) M3 Kit ("Mürekkep", ADR-0048) ve Tasarım Kalıpları

Kullanılan `src/ui` bileşenleri: `Button` (variant: filled/tonal/outlined/text + icon), `Card` (elevation), `Dialog` (95 s.; scrim %50, odak tuzağı `useFocusTrap`, `wide`/`full`/`dismissible` seçenekleri; **kritik**: `onClose` referansı sabit olmalı — `useCallback` yoksa focus-trap effect'i yazarken odağı çalar, kodda 3 yerde yorumla belgelenmiş), `Tabs` (205), `Stepper` (74; done/current/upcoming/**skipped** durumları — klasik düzende Salonlar adımı "atlandı"), `Autocomplete` (376; 300 ms debounce, `minChars`, klavye gezinme, `getDisabled(item)→neden` sözleşmesi, chip'li seçili durum), `DataTable` (343; caption + onRowClick), `Select`, `TextField`, `Icon` (Material Symbols adları), `Skeleton/SkeletonList`, `SnackbarProvider` (kuyruklu; `success/error/show`), `ConfirmProvider` (promise tabanlı `confirm({title,message,confirmLabel})`), `EmptyState`, `HubFeatureCard`.

Token sistemi: `tailwind.config.js` renkleri `rgb(var(--oys-<rol>) / <alpha>)` CSS değişkenlerinden üretir (index.css) — M3 rolleri (primary/secondary/tertiary/error/success/warning/info + container/on-* çiftleri, surface-container-lowest..highest, outline/outline-variant, inverse-*), tipografi sınıfları (`text-headline-medium`, `text-title-small`, `text-body-medium`, `text-label-small`...), biçim (`rounded-shape-xs..lg`), gölge (`shadow-elevation-1..3`), `state-layer` hover katmanı. Kural: ham renk/px yok; tek belgeli istisna dinamik grid sütunu (`gridTemplateColumns: repeat(n, minmax(3rem, max-content))` — RoomEditor 384 ve YerlesimPaneli 197, ikisi aynı grid kimliğini kullanır, kroki R1 ile birebir).

Belirgin kalıplar: (a) her yerde tıkla-yerleştir/tıkla-takas, DnD kütüphanesi bilinçli yok; (b) çakışma grubu renk kodlaması 6 tonluk `GROUP_TONES` döngüsü + ikinci turda ring ayracı (YerlesimPaneli 23-30); (c) liste→dialog CRUD deseni (DersHavuzu, Salonlar, Takvimler paralel); (d) rozet/çip dili (durum, seviye, tür, kaynak, doluluk); (e) `role="alert"`, `aria-label`, `aria-pressed`, min 36px hedef gibi erişilebilirlik disiplini; (f) yıkıcı işlemler daima `useConfirm`.

## 3) React Query Kalıbı ve API İstemcisi

- `src/lib/queryClient.ts` (37): tek singleton; `staleTime 30sn`, `gcTime 5dk`, `refetchOnWindowFocus false`, retry: 4xx'te hiç / diğerinde 1; mutasyonlarda retry yok.
- `src/lib/api.ts` (~140): fetch tabanlı; `API_BASE = VITE_API_BASE_URL || "/api/v1"`; Bearer + 401'de tek seferlik refresh; hata sözleşmesi `{code, message, fields}` → `ApiError`; `get/post/patch/put/del/postForm/getBlob`; 403 `personnel_inactive` ve `password_change_required` oturum-sonu kapıları.
- `src/lib/download.ts` (14): `saveBlob(blob, filename)` — tüm PDF/ZIP/xlsx/docx indirmeleri bundan geçer.
- Modül istemcisi `sinav-islemleri/api.ts` (694): elle yazılmış TS interface'ler + 6 API nesnesi: `courseApi`, `examRoomApi`, `examSessionApi` (~35 uç: pre-check, participants, distribute{seed,strict}, seating, swap-seats, approve/reopen/archive, reports/zip, booklets, proctors/auto, question upload/download, question-template), `attendanceApi`, `examCalendarApi` (~20 uç: generate-defaults, fill-pool, grid, participant-preview, place/unplace, create-session, track/mark, pdf), `examTrackItemApi`. `REPORT_CATALOG` sabiti backend REPORT_CODES ile birebir.
- Kullanım kalıbı: sorgu anahtarları dizi (`["exam-session", id]`, `["exam-seating", id]`, `["exam-calendar-grid", id]` — Havuz ve Yerleştirme panelleri aynı grid anahtarını paylaşıp önbellekten yararlanır); mutasyon → `invalidateQueries` + snackbar; özel dokunuşlar: kitapçık koşularında koşullu `refetchInterval` 4000 ms, RoomEditor önizlemesinde `queryKey`'e `plan` nesnesi koyup `placeholderData:(prev)=>prev` ile titremesiz canlı önizleme, SorularPaneli'nde `retry:false` (404=yüklenmemiş olağan), SalonlarPage'de `setQueryData` ile kayıt sonrası yerel liste güncelleme.
- İş kuralı konumu: numaralandırma, dağıtım, doğrulama, çakışma grubu, takvim kuralları TAMAMEN backend'de; frontend yalnız uçları sürer (CLAUDE.md §10 yansıması). İstemci tarafında yalnız `planEdit.ts` (görsel durum) ve Türkçe `toLocaleLowerCase("tr")` ilk-harf filtreleri vardır.

## 4) Çok Kullanıcılı / Role Bağlı Noktalar (tek kullanıcıda sadeleşir)

- `src/lib/roles.ts` 488-496: `CAN_VIEW_EXAM_OPERATIONS = [ADMIN, MUDUR, MUDUR_YARDIMCISI]`, `CAN_APPROVE_EXAM_CALENDAR = [ADMIN, MUDUR]`, `CAN_VIEW_EXAM_TRACK = +ZUMRE_BASKANI`. `useAuth()+hasAnyRole` yalnız 3 dosyada: `TakvimlerPage` (buton gizleme, salt-okunur liste), `TakvimDetayPage` (ZUMRE_BASKANI yalnız Süreç Takip sekmesi; onay butonu müdüre), `TakvimTakipPaneli` (işaretleme idare-only). Oturum/salon/ders ekranlarında frontend rol kontrolü YOK (menü + backend korur). Tek kullanıcıda: tüm `isManager/canApprove/editable` bayrakları `true` sabitlenir, `useAuth` bağımlılığı silinir.
- Kim/ne zaman damgaları: ön kontrol onayı `transfer_check_confirmed_by_name/_at`, takip hücresi `marked_by_name/marked_at`, takvim `submitted_at/approved_at` — tek kullanıcıda "kim" alanı anlamsızlaşır, "ne zaman" kalabilir.
- Gözetmen tebellüğü (acknowledge) çok-kişili bir onay akışıdır; tek kullanıcıda idarenin elle işlediği işaret olarak kalabilir veya atılabilir.
- Takvim onay akışı (submit→approve, MY hazırlar / müdür onaylar — ADR-0044 D2) tek kullanıcıda tek "Onayla" düğmesine iner.
- Çapraz modül köprüleri (portta EN BÜYÜK bağımlılık sorunu): `sectionsApi` (`modules/siniflar/api.ts` — şube listesi + şube grupları; sihirbaz Adım 2 ve salon-şube eşlemesi bunsuz çalışmaz), gözetmen aday havuzu ders programı `teachers_free_at` + `gorevlendirme` devamsızlık köprüleri (Tur 459), takvim ızgarası zil çizelgesi (`grid.periods` boşsa panel "Ders Programı → Zil Çizelgesi" yönlendirmesi yapar), "Programdan Doldur" ders programına, pre-check nakil hareketleri Öğrenci İşleri siciline bağlıdır. Kelebek-sinav'da bunların yerel karşılıkları (basit şube/öğrenci/öğretmen/ders-saati tabloları veya e-Okul içe aktarma) tanımlanmalı; gözetmen uygunluk köprüleri ya atılır ya elle işaretlenen "meşgul/muaf" alanına indirgenir.
- Girişe bağlı altyapı (portta ALINMAZ): token refresh, `personnel_inactive`/`must_change_password` kapıları, impersonation, KVKK AccessLog/SENSITIVE_READ notları, Sentry.

## 5) UX Akışı — Adım Adım

**A. Kurulum:** Ders Havuzu (MEB kataloğu + elle) → Salonlar ("Şube dersliklerini oluştur" ile 40 koltuklu otomatik plan veya elle: palet aracı seç → hücreye tıkla; numaralandırma önizlemesi anahtarla; kaydet; kapı planı PDF'i indir).

**B. Takvim (isteğe bağlı üst akış):** "Ön Tanımlı Takvimleri Üret" → takvim detayında Havuz'u "Programdan Doldur" veya elle → Yerleştirme ızgarasında boş hücre "+"→dialog'dan ders seç (uyarılar snackbar'da) → Önizleme'de açıklama metnini düzenle → Onaya Sun → Onayla (filigransız PDF) → satırda "Oturum Üret" → üretilen oturum sihirbaza ön-dolu düşer. Süreç Takip matrisi tüm yaşam boyu işaretlenir.

**C. Oturum sihirbazı (TASLAK):** Adım 0 Veri Ön Kontrolü — seviye başına aktif öğrenci + son 30 gün nakil gelen/giden; onay kutusu işaretlenmeden geçilmez, onay kim/ne zaman yazılır. Adım 1 Oturum Bilgileri. Adım 2 Ders ve Katılımcılar — Autocomplete ders + seviye + katılımcı tipi LEVEL/SECTIONS/GROUPS + "Ortak kitapçık"; canlı katılımcı sayıları ve çakışma uyarıları; engelleyici çakışmada Devam kilitli. Adım 3 Salonlar (yalnız kelebek; klasikte Stepper'da "atlandı") — kapasite yeterlilik progressbar'ı (yetersizse kırmızı + eksik koltuk sayısı). Adım 4 Dağıt & Önizle — seed (boş=rastgele; aynı seed=aynı yerleşim) + katı mod; Dağıt → durum DISTRIBUTED, detay sekmeli görünüme döner.

**D. DISTRIBUTED:** Yerleşim'de doğrulayıcı özeti (İHLAL=0 / sert ihlaller, 1. halka çifti, yakınlık skoru), doluluk çipleri, kullanılan seed; iki dolu koltuğa tıkla→takas→rapor anında yenilenir. Gözetmenler'de salon başına atama / Otomatik Öner. Sorular'da PDF yükle + kitapçık üret. → **Onayla** (backend İHLAL=0 şartı) → APPROVED: her şey kilitli, Yoklama sekmesi açılır, tebellüğ işlenebilir, Rapor Merkezi'nden R1-R9 + ZIP. → **Arşivle**: salt-okunur + yeniden basım; mazeret durumu arşivde de güncellenir.

## key_facts
- Modül kökü: frontend/src/modules/sinav-islemleri — 22 kaynak dosya, test hariç ~6.300 satır; en büyükler SinavSihirbazi.tsx 780, api.ts 694, DersHavuzuPage.tsx 496, RoomEditor.tsx 397
- 7 rota (App.tsx 189-195, hepsi lazy): hub, oturumlar, oturumlar/:id, salonlar, ders-havuzu, takvimler, takvimler/:id; salon editörü rotasız state geçişi, oturum panelleri sekme
- Sihirbaz 5 adım: Veri Ön Kontrolü (nakil onayı zorunlu, kim/ne zaman yazılır) → Oturum Bilgileri → Ders ve Katılımcılar (LEVEL/SECTIONS/GROUPS + ortak kitapçık) → Salonlar (klasikte 'atlandı') → Dağıt & Önizle (seed + katı mod)
- Oturum yaşam döngüsü: DRAFT → DISTRIBUTED (takas+gözetmen+soru serbest) → APPROVED (kilit, Yoklama açılır, İHLAL=0 şartı) → ARCHIVED (salt-okunur, yeniden basım açık); takvimde DRAFT → SUBMITTED → APPROVED
- TÜM iş kuralları backend'de: dağıtım, swap doğrulayıcısı, koltuk numaralandırma (RoomEditor her plan değişiminde POST /exam-rooms/preview-seats çağırır, placeholderData ile titremesiz), takvim grid/kural denetimi; istemcide yalnız planEdit.ts immutable görsel dönüşümleri
- DnD bilinçli YOK (ADR-0016): salon editörü palet+tıkla-yerleştir, yerleşim tıkla-takas, takvim tıkla-yerleştir — port bu kalıbı aynen koruyabilir
- planEdit.ts (117 satır) saf fonksiyonlar (applyTool/resizeGrid/capacityOf/emptyPlan) — AYNEN taşınabilir; YerlesimPaneli+RoomEditor aynı grid kimliğini (desk_row:desk_col:slot) ve inline gridTemplateColumns istisnasını paylaşır, kroki R1 ile birebir
- Rapor kataloğu api.ts 333-344 REPORT_CATALOG: R1 kroki, R2 salon yoklama, R2K şube yoklama, R3 kapı, R4 duyuru, R5 Excel çizelge, R6 gözetmen tebliğ (yalnız gözetmen modülü açıkken), R7 zarf/tutanak, R8 doğrulama, R9 teslim tutanağı + tümü-ZIP + R10 kişiselleştirilmiş kitapçık (SorularPaneli, 4sn polling)
- Çakışma grubu görselleştirme: 6 tonluk GROUP_TONES token döngüsü (error-container bilinçle hariç), 6+ grupta ring ayracı; conflict_group_labels ile insan-okur lejant
- React Query kalıbı: tek queryClient (staleTime 30sn, gcTime 5dk, 4xx retry yok, refetchOnWindowFocus false), dizi queryKey'ler, mutasyon→invalidate+snackbar; exam-calendar-grid anahtarı Havuz/Yerleştirme panellerince paylaşılır
- API istemcisi lib/api.ts: fetch + Bearer + 401 refresh + ApiError{status,code,message,fields} + getBlob/postForm; indirmeler lib/download.ts saveBlob'dan; tek kullanıcıda auth katmanı tamamen düşer
- M3 'Mürekkep' kiti (ADR-0048): tailwind.config.js renkleri rgb(var(--oys-*)) CSS değişkenlerinden; tipografi/shape/elevation token sınıfları; kullanılan bileşenler Button, Card, Dialog, Tabs, Stepper(skipped destekli), Autocomplete(getDisabled sözleşmeli, 376 satır), DataTable, Select, TextField, Icon, Skeleton, Snackbar, Confirm, EmptyState, HubFeatureCard
- Dialog focus-trap tuzağı (kodda 3 kez belgelenmiş): onClose referansı useCallback ile sabitlenmeli, yoksa her render'da odak paneli çalar — port ederken korunacak davranış
- Rol bağımlılığı yalnız 3 takvim dosyasında (TakvimlerPage, TakvimDetayPage, TakvimTakipPaneli — useAuth+hasAnyRole; CAN_VIEW_EXAM_OPERATIONS=ADMIN/MUDUR/MY, CAN_APPROVE=ADMIN/MUDUR, ZUMRE_BASKANI salt-okunur takip); oturum/salon/ders ekranlarında frontend rol kodu yok — tek kullanıcıda bayraklar true sabitlenir
- Çapraz modül bağımlılıkları (port kritik): sectionsApi (modules/siniflar — şube+grup listeleri; sihirbaz Adım 2 ve salon-şube eşlemesi), gözetmen aday havuzu ders programı+devamsızlık köprüleri (Tur 459), takvim ızgarası zil çizelgesine (grid.periods) muhtaç, 'Programdan Doldur' ders programına, pre-check Öğrenci İşleri nakil verisine bağlı
- Takvim→oturum köprüsü: APPROVED takvimde satır başına 'Oturum Üret' (create-session) sihirbaza ön-dolu oturum açar — iki alt sistem gevşek bağlı, port sıralaması için oturum tarafı takvimsiz de çalışır
- Salon üretimi kısayolu: POST /exam-rooms/generate-section-rooms her aktif şubeye 40 koltuklu ikili-sıra derslik üretir (idempotent, orphan uyarılı) — tek kullanıcılı kurulumda hızlı başlangıç için değerli
- Türkçe yerel arama kalıbı: küçük listeler (ders ~60, öğretmen ~50) tek seferde yüklenip toLocaleLowerCase('tr') ile istemcide ilk-harf öncelikli süzülür (SinavSihirbazi.searchCourses, GozetmenlerPaneli.searchCandidates)
- Yoklama modeli: seat_assignment üstünden 'girmedi' kaydı + mazeret PENDING/EXCUSED/UNEXCUSED + belge no/tarih serbest metin (dosya yüklenmez); arşivde güncellenebilir (MEB 5 iş günü)
- Tarih/kimlik formatları: formatDate gg.aa.yyyy (OturumlarPage 45-48), saatler HH:MM dilimlenir, F27 anonimleştirilmiş arşivde student_id null olabilir — SeatAssignmentRow ve ExamAttendanceRecordRow tipleri bunu içerir

## riskler
- Şube/grup verisi olmadan sihirbazın Adım 2'si (SECTIONS/GROUPS) ve klasik düzen (linked_section_id) çalışmaz — kelebek-sinav'da yerel şube+öğrenci şeması ve içe aktarma yolu (e-Okul listesi vb.) tasarlanmadan bu ekranlar taşınamaz
- Gözetmen aday uygunluğu (is_lesson_busy/is_absent) OYS'nin ders programı ve görevlendirme modüllerinden beslenir; tek başına uygulamada bu köprüler yok — ya özellik budanır ya öğretmen tablosuna elle 'muaf/meşgul' alanı eklenir, aksi hâlde Otomatik Öner yanıltıcı olur
- Takvim yerleştirme ızgarası zil çizelgesi (periods) olmadan hiç render olmaz (TakvimYerlestirmePaneli 87-94) — portta ya basit yerel ders-saati tanımı eklenir ya takvim alt sistemi ikinci faza bırakılır
- RoomEditor numaralandırma önizlemesi her plan değişiminde backend'e POST atar — localhost+waitress'te sorun değil ama pywebview tek-iş parçacıklı sunucu yapılandırmasında sık istekle UI takılması test edilmeli
- Onay/tebellüğ/kim-ne-zaman damgaları çok kullanıcılı hesap modeline dayanır; tek kullanıcıda alanlar şemadan çıkarılırsa backend rapor şablonları (R6 tebliğ-tebellüğ, R9 tutanak) da uyarlanmak zorunda — evrak-şema bağı gözden kaçabilir
- REPORT_CATALOG kodları backend REPORT_CODES ile birebir tutulmalı; SorularPaneli'ndeki 6 maddelik şablon kuralları listesi backend word_template._GUIDE_PARAGRAPHS ile çift-kaynaklıdır (Tur 646 yorumu) — port sırasında iki listenin senkronu unutulabilir
- Kitapçık üretimi kuyruklu/asenkron (BookletRun PENDING→IN_PROGRESS polling) — OYS'de arka plan işçisi varsayar; masaüstünde ya senkron üretime çevrilir ya yerel thread kuyruğu kurulur
- Tailwind M3 token sistemi index.css'teki --oys-* değişkenlerine bağlı; disiplin-defteri-codex şablonunun mevcut token adlarıyla birebir örtüşmüyorsa bileşenler sessizce renksiz kalır — taşımadan önce token adları eşitlenmeli
- Autocomplete/Dialog/DataTable gibi kit bileşenleri modül dışı ortak koddan geliyor (src/ui, 2.400+ satır ilgili altküme) — modülü tek başına kopyalamak derlenmez; kitin gereken altkümesi bilinçli seçilip birlikte taşınmalı
- formatDate/StatusBadge gibi yardımcılar OturumlarPage'den, CalendarStatusBadge TakvimlerPage'den export ediliyor (sayfalar arası çapraz import) — port sırasında dolaşık bağımlılık; ortak bir utils dosyasına ayrıştırılmalı


================================================================================
AJAN: ders
================================================================================

# GÖREV C — OYS ders yapısı + MEB ders çizelgesi katmanı (port analizi)

## 0. Modül haritası ve bağımlılık yönleri

`backend/apps/ders_yapisi` **taban modüldür** (ADR-0017): `sinav_islemleri`, `program`, `zumre` ona string-label FK verir (`"ders_yapisi.Course"`), model importu yasak — erişim yalnız `apps.ders_yapisi.services` fasadı üzerinden (dosya başındaki `__all__`, services.py:52-129). Ters yönde `ders_yapisi`, sınav modeline yalnız `django_apps.get_model("sinav_islemleri","ExamSessionCourse")` ile runtime'da dokunur (selectors.py:279-294 `_session_course_counts`, services.py:604 `consolidate_duplicate_course`). `ders_yapisi` → `apps.core.selectors` bağımlıdır (şube/yıl).

Dosya boyutları: `models.py` 633, `selectors.py` 1280, `services.py` 2356, `views.py` 750, `serializers.py` 449, `catalog_parser.py` 136, `curriculum_parser.py` 197 satır. Komutlar: `management/commands/import_course_catalog.py` (108), `import_curriculum.py` (141), `curriculum_plan.py`, `normalize_course_names.py`, `sync_lesson_enrollments.py`.

## 1. Ders / çizelge modelleri (models.py)

**Course** (satır 53-123; `db_table="sinav_islemleri_course"` — tablo fiziksel olarak eski modülde kaldı):
- `name` (CharField 120, canlıda unique: `uq_course_name_alive` koşullu constraint, soft-delete'liler ayrı)
- `short_code` (16, aSc eşlemesi için), `default_weekly_hours` (nullable — MEB kataloğunda YOK, aSc/elle doldurur)
- `levels` **JSONField list** (örn. `[9,10]`; sorgu `levels__contains=[level]` = Postgres `jsonb @>`)
- `course_type`: `COMMON|ELECTIVE` (CourseType), `source`: `MEB_CATALOG|MANUAL` (CourseSource), `is_active` (pasif ders yeni planlamada seçilemez, silinmez)
- `VALID_COURSE_LEVELS = (0, 9, 10, 11, 12)`; **0 = Hazırlık** (models.py:39-40). Yani OYS **yalnız lise** varsayar — ortaokul/ilkokul kademesi yok.

**CourseAlias** (126-182, Tur 565): `alias_key` (normalize anahtar, canlıda unique), `display_name`, `course` FK (PROTECT), `source: OPERATOR|SEED`. OPERATOR SEED'i ezebilir, tersi olmaz.

**Müfredat çerçevesi üçlüsü** (ADR-0037, satır 494-633) — "okul türü + sürüm" katmanı:
- `CurriculumFramework`: `name`, **`program_key`** (slug — okul türünü taşıyan TEK alan: `anadolu-lisesi`, `anadolu-lisesi-hazirlik`), `version` ("2025"), `source`, `is_active`, `notes` (TTK karar no). Canlıda `(program_key, version)` unique.
- `CurriculumEntry`: `(framework × course × class_level) → weekly_hours + course_type + order`. `course_type` seviyeye göre değişebildiği için Course'takinden bağımsız (örn. Bilişim Tek. Hazırlık'ta ORTAK, 9-12'de seçmeli).
- `CurriculumAssignment`: `(school_year × class_level) → framework` — kademeli geçişin tek doğruluk kaynağı.

**Portla İLGİSİZ çekirdek** (aynı dosyada): `Classroom`, `SectionClassroomAssignment`, `CourseClassroomRule`, `LessonGroup` (şube×ders×grup×haftalık saat), `LessonEnrollment` + `TeachingAssignment` (tarihli, `DateRangeField` + `ExclusionConstraint` + btree_gist = **Postgres-only**). Bunlar ders programı/yoklama altyapısıdır.

Not: DB'de ayrıca "okul türü" alanı YOK — `core.SchoolConfig` (models.py:1466+) yalnız `prep_class_enabled` ve `education_type (FULL_DAY|DUAL)` taşır. Okul türü tamamen `program_key` + hangi katalog dosyasının yüklendiğiyle belirlenir.

## 2. MEB çizelge verisi nereden geliyor? → SABİT, ELLE KÜRATÖRLENMİŞ MARKDOWN FIXTURE

AI-import **çizelge verisini üretmez**. Zincir şöyle:

**a) Katalog (Course havuzu):** `data/ders-cizelgeleri/anadolu-lisesi-2025-2026.md` — tek küratörlenmiş dosya; kaynak **TTK 09.05.2025/05 kararı** (`data/raw/Ders Çizelgeleri.pdf`'ten elle aktarılmış; raw klasörü şu an boş). Format: `| Ders | Seviyeler | Tür |` markdown tablosu (Seviyeler: `9, 10` / `9-12` / `0, 9-12`; Tür: ORTAK/SECMELI). İçerik: 19 ortak + 45 seçmeli satır (4 seçmeli grup başlığı altında). Slash'lı kombine dersler var ("Görsel Sanatlar/Müzik").
- Parser: `catalog_parser.parse_markdown_catalog` (saf, DB'siz) → `CourseRow(name, levels, course_type)`.
- Yükleme 1: `python manage.py import_course_catalog` (idempotent; ad-eşleşmeli upsert `services.import_course_rows`, satır 947-996 — MEB kaynağı kazanır, `is_active` bilinçle korunur).
- Yükleme 2 (**tembel tohum**): `services.ensure_meb_catalog` (999-1034) — katalog boşsa `/data/ders-cizelgeleri/*.md` yükler; **program içe aktarma view'larının başında çağrılır** (program/views.py:351 e-Okul PDF yolu, 436 AI-JSON yolu; AI yolunda atomic İÇİNDE ki dry-run tohumu da geri alsın).

**b) Çerçeve (haftalık saat matrisi):** `data/ders-cizelgeleri/cerceveler/anadolu-lisesi-2025.md` + `hazirlik-anadolu-lisesi-2025.md`. Format: üstte `- ad/program_key/version/source/notes` meta bloğu, altta `| Ders | Hazırlık | 9 | 10 | 11 | 12 | Tür |` matrisi (`-` = o seviyede yok). Parser: `curriculum_parser.parse_markdown_framework` (saf). Yükleme: `import_curriculum` komutu — `upsert_curriculum_framework` + `set_curriculum_entry`; ders adı `selectors.course_by_normalized_name` ile Course'a bağlanır, **önce katalog import şart**. Çerçeveler yalnız ORTAK dersleri taşır; **seçmeli bütçesi türetilir: 40 − ortak toplam** (`WEEKLY_TOTAL_HOURS = 40`, selectors.py:851; AL 9/10/11/12 ortak = 32/33/19/15).

**c) Takma ad seed'i:** `data/ders-cizelgeleri/ders-adi-takma-adlari.md` (~55 veri satırı, `| Takma ad | Kanonik ad |`) — e-Okul kısaltmalarını ("Din Kül. ve Ah. Bil.") kanoniğe bağlar; `ensure_course_aliases` (services.py:1099-1145, satır-bazlı idempotent) yükler.

**d) Tur 563 / AI-import'un GERÇEK rolü:** AI-import (Tur 551-569) e-Okul **ders programını** (JSON) içe aktarır; MEB çizelgesini değil. Ders adı ÇÖZÜM ZİNCİRİ `program/eokul_importer.py` `resolve_course` (satır 458-566): (0) operatör eşleştirmesi `course_mappings` → (1) `meb_course_by_normalized_name` → (2) `course_by_alias` → (3) AI'ın `subject_canonical` önerisi (yalnız çözülemezse; tutarsa alias öğrenilir) → (4) `repair_truncated_course_name` (kırpık PDF hücresi onarımı, MEB katalogdan tek-kesin sonek tamamlama) → (5) casing-duyarsız `course_by_normalized_name` → (6) kirlenmiş metin reddi / `create_missing_courses=False` ise atla → (7) `create_course(titlecase_tr(ad), levels=[şube seviyesi], MANUAL)`. Tur 563'ün kendisi: seviye hücrenin şubesinden gelir (hazırlık=0 dahil) + `_ensure_course_level` MANUAL derste seviye birleşimi yapar (MEB dersine dokunmaz); ayrıca `TimetableOptionsView` (program/views.py:206-231) AI prompt'una `prep_class_enabled` + `shift_period_counts` bağlamını verir. **Port için ders çizelgesi kaynağı = statik dosya; AI yalnız (opsiyonel) e-Okul çıktısını bu havuza EŞLER.**

## 3. Sınav modülü ders_yapisi'ndan neyi kullanıyor?

FK'ler: `sinav_islemleri.ExamSessionCourse.course → "ders_yapisi.Course"` (models.py:246) ve `ExamCalendarEntry.course` (models.py:990). Çakışma/benzersizlik grubu **(session, course, level)** — ADR-0016 §3.

Servis çağrıları (hepsi `apps.ders_yapisi.services` fasadından):
- `sinav_islemleri/services.py:28`: `level_label`, `normalize_levels`; `:509` `get_course(course_id, active_only=True)` + `:518` **`lv not in course.levels` seviye doğrulaması** ("havuz tanımı"); `:71,2167` `course_names_by_ids`.
- `services_calendar.py`: `:323` `get_course`; `:377` **`taught_course_levels(year_id)`** (yılda fiilen okutulan distinct (ders,seviye) — takvimin "Programdan Doldur" üreticisi; kaynak canlı LessonGroup, CLUB hariç); `:685` **`course_level_student_ids`** (günlük yük/öğrenci çakışması, PII'siz id kümesi); `:710` **`course_level_coverage`** (takvim dipnotu: "9-A + 9-B" / "11-A (Grup: Almanca)" + öğrenci sayısı); `:861` `course_names_by_ids`; `level_label`.
- Testler `ders_yapisi.tests.factories.CourseFactory`'yi yeniden dışa aktarır.

Frontend: ders kataloğu ucu **`/exam-courses/`** hâlâ sınav modülünün istemcisinde (`frontend/src/modules/sinav-islemleri/api.ts` `courseApi`: list `{level, course_type, include_inactive, q, limit, offset}`, create, patch). `SinavSihirbazi.tsx` Autocomplete ile ders seçer, `course.levels`'tan seviye dropdown'ı kurar (satır 475-498), şubeleri seviyeye süzer; `DersHavuzuPage.tsx` katalog CRUD ekranı. Backend `CourseViewSet` (ders_yapisi/views.py:87): okuma oturumlu herkese, yazma `CanManageCourses`; DELETE yok (`is_active=False`).

**Kritik tespit:** sınav planlama tarafının ders_yapisi'na ZORUNLU bağımlılığı yalnız **Course(id, name, levels, course_type, is_active) + level_label/normalize_levels**'tır. `taught_course_levels`/`course_level_*` LessonGroup/LessonEnrollment verisine dayanır — tek kullanıcılı masaüstünde ders programı verisi olmayacağından bu "Programdan Doldur" ve öğrenci-çakışma özellikleri ya atlanır ya elle seçime döner.

## 4. Yinelenen ders tespiti / birleştirme

- **Normalize anahtarları** (selectors.py:34-100, saf fonksiyonlar): `_match_key` (TR-duyarlı küçük harf + şapka Â/Î/Û düzleme + boşluk normalize; public yüzü `course_match_key`), `_canon_course_key` (= `_match_key` + baştaki "seçmeli " önekini atar). `_meb_catalog_index` (103-123) slash'lı katalog adlarını parçalayıp anahtar→seviye kümesi dizini kurar (çizelge doğrulaması `course_off_catalog` / `lesson_groups_off_catalog` bunu kullanır).
- **Tespit:** `selectors.duplicate_course_candidates` (330-406) — canlı Course'ları `_canon_course_key`'e göre kümeler; istisna `_split_catalog_elective_cluster` (297-327): resmi adı zaten "Seçmeli X" olan MEB dersleri öneksiz "X" ile mükerrer SAYILMAZ. Her üyeye kullanım sayıları (`group_count`, `entry_count`, `exam_count` — sınav sayısı get_model köprüsüyle) + önerilen kanonik sıralaması: öneksiz > MEB kaynaklı > en çok kullanılan > küçük id.
- **Birleştirme:** `services.consolidate_duplicate_course` (542-643, atomic) — LessonGroup/CurriculumEntry/CourseAlias/ExamSessionCourse referanslarını kanoniğe taşır (unique çakışanı soft-delete), seviyeleri BİRLEŞTİRİR, kopya adını alias olarak ÖĞRENİR (`learn_course_alias`), kopyayı soft-delete eder.
- **API/UI:** `GET /exam-courses/duplicates/` + `POST /exam-courses/merge/` (views.py:128-159); istemci `ders-yapisi/api.ts` `duplicateCourses`/`mergeCourses`.
- Yardımcı temizlikler: `normalize_uppercase_course_names` (683-716, e-Okul BÜYÜK HARF adları `titlecase_tr` ile başlıklar), `repair_truncated_course_name` (767-823), `suspect_import_courses` (826-879), `discard_course`/`decommission_course_artifacts`.

## 5. Masaüstü portu için minimum ders modeli önerisi

**AYNEN taşınabilir (saf, Django-bağımsız ya da kolay sökülür):**
- `catalog_parser.py` (136 satır) ve `curriculum_parser.py` (197) — DB'siz saf parser'lar (yalnız `CourseType/CourseSource/CourseRow` importları yerelleştirilir).
- Normalize fonksiyonları: `_match_key`, `_canon_course_key`, `titlecase_tr`, `_tr_upper/_tr_lower`, `normalize_levels`, `level_label` — birebir kopya.
- Veri dosyaları: `anadolu-lisesi-2025-2026.md`, `cerceveler/*.md`, `ders-adi-takma-adlari.md` (uygulama içine gömülü kaynak olarak; TTK kararı kaynak notlarıyla).
- `import_course_rows` + `ensure_meb_catalog` deseni (idempotent, `is_active` koruyan upsert).

**UYARLANIR:**
- **Course (minimum):** `id, name (canlıda unique), levels, course_type (COMMON|ELECTIVE), source (MEB_CATALOG|MANUAL), is_active`; istenirse `short_code`, `default_weekly_hours`. `db_table` bagajı atılır. **SQLite uyarısı:** `levels__contains` JSONField sorgusu SQLite'ta desteklenmez → ya (a) ayrı `CourseLevel(course_id, level)` tablosu, ya (b) Python tarafında süzme (katalog ≤ ~200 kayıt, sorun değil), ya (c) levels'ı CSV metin tutup LIKE. Öneri: (a) — "okul türü + kademe" filtresi ilk sınıf vatandaş olacaksa normalize tablo temiz.
- **Okul türü:** OYS'de alan yok; portta açık model gerekli. Öneri: `SchoolType`/config'te `school_type_key` (slug) + katalog dosyalarını okul türü başına ayır (`data/ders-cizelgeleri/<okul-turu>.md`) ya da katalog formatına `- okul_turu:` meta satırı ekle. Mevcut veride yalnız Anadolu Lisesi var; **diğer türlerin (Fen L., AİHL, MTAL, ortaokul, ilkokul) çizelgeleri TTK PDF'lerinden elle küratörlenmeli** — mekanizma hazır, veri yok.
- **Kademe:** `VALID_COURSE_LEVELS=(0,9..12)` lise-sabit; ortaokul/ilkokul desteklenecekse geçerli seviye kümesi okul türünden türetilmeli (örn. tür→seviye aralığı haritası).
- **Haftalık saat istenirse:** CurriculumFramework/Entry yerine tek tablo yeter: `(school_type, version, course, level) → weekly_hours, course_type`; `CurriculumAssignment` (yıl×seviye→çerçeve kademeli geçişi) tek kullanıcılı sınav uygulaması için büyük olasılıkla gereksiz — sınav planlama saat bilgisini hiç kullanmıyor (yalnız ders+seviye).
- Yinelenen tespiti basitleşir: `duplicate_course_candidates`'ın exam_count köprüsü tek modüle iner; `consolidate_duplicate_course`'tan LessonGroup/CurriculumEntry adımları düşer.
- `CourseAlias` YALNIZ e-Okul/AI içe aktarma yapılacaksa gerekli; elle havuz yönetiminde atlanabilir (ama `_match_key` tabanlı casing-duyarsız eşleşme her durumda kalsın — mükerrer üretimini önlüyor).

**ALINMAZ:** LessonGroup/LessonEnrollment/TeachingAssignment (Postgres ExclusionConstraint/btree_gist/DateRangeField; çok kullanıcılı ders programı gerçeği), Classroom + şube/ders derslik kuralları (sınav salonu `ExamRoom` zaten ayrı kavram — teknik borç F30 notu), `sync_lesson_enrollments*`, e-Okul/AI import hattı (eokul_importer 1250 satır), RBAC/permissions (`CanManageCourses` vb.), kapsam denetimleri (`curriculum_coverage`, `student_slot_coverage` — slot enjeksiyonlu, program modülüne bağlı), `shift_by_lesson_group` (ikili eğitim).

**Frontend referansı:** `DersCizelgeleriPage.tsx` (1097 satır; Çerçeveler + Kademeli Atama sekmeleri, `EntryMatrix` seviye-saat matrisi, `ElectivePickerDialog` "Katalogdan seçmeli ekle" — `/exam-courses/?course_type=ELECTIVE&level=N` filtresi) ve `SinavSihirbazi`'nın ders→seviye→şube akışı, yeni uygulamanın "MEB havuzundan ders ekle" ekranına doğrudan ilham; `CURRICULUM_LEVELS=[0,9,10,11,12]` ve `curriculumLevelLabel` istemci sabitleri de taşınabilir.

## 6. MEB çizelge verisi içeren dosyalar (depo taraması)

- `C:\Users\aalid\.claude\apps\okulapp\data\ders-cizelgeleri\anadolu-lisesi-2025-2026.md` — katalog (64 ders satırı; TTK 09.05.2025/05)
- `C:\Users\aalid\.claude\apps\okulapp\data\ders-cizelgeleri\cerceveler\anadolu-lisesi-2025.md` — 9-12 ortak saat matrisi (16 ders satırı)
- `C:\Users\aalid\.claude\apps\okulapp\data\ders-cizelgeleri\cerceveler\hazirlik-anadolu-lisesi-2025.md` — Hazırlık sütunlu varyant (`program_key: anadolu-lisesi-hazirlik`)
- `C:\Users\aalid\.claude\apps\okulapp\data\ders-cizelgeleri\ders-adi-takma-adlari.md` — ~55 takma ad satırı
- `C:\Users\aalid\.claude\apps\okulapp\data\ders-cizelgeleri\README.md` ve `cerceveler\README.md` — format sözleşmeleri (port dokümantasyonuna kopyalanmalı)
- JSON/Django-fixture biçiminde MEB verisi YOK (aranan `*fixture*` sonuçları test/e2e altyapısı); `data/raw/` boş (kaynak PDF depoda değil). Demo tohumu `sinav_islemleri/management/commands/seed_exam_demo.py` `ders_services.create_course` ile uydurma ders açar — MEB verisi değildir.

## key_facts
- Course modeli ders_yapisi'nda ama tablo adı db_table='sinav_islemleri_course' (ADR-0017 taşıma); portta bu bagaj atılır.
- Minimum sınav bağımlılığı: Course(id, name, levels, course_type, source, is_active) + level_label/normalize_levels — sınav planlama haftalık saati HİÇ kullanmıyor, yalnız (course, level).
- Course.levels JSONField listtir ve selectors.courses() 'levels__contains=[level]' (jsonb @>) ile süzer — SQLite'ta contains lookup YOK: portta CourseLevel ara tablosu ya da Python süzme gerekir.
- VALID_COURSE_LEVELS = (0, 9, 10, 11, 12); 0=Hazırlık — OYS lise-sabittir; okul türüne göre kademe için bu küme türetilebilir hale getirilmeli.
- MEB çizelge verisi FIXTURE'dır: elle küratörlenmiş markdown (data/ders-cizelgeleri/*.md, kaynak TTK 09.05.2025/05); AI-import çizelgeyi ÜRETMEZ, yalnız e-Okul programındaki ders adlarını kataloğa çözer.
- Katalog formatı: '| Ders | Seviyeler | Tür |' (9-12 aralık sözdizimi, ORTAK/SECMELI); parser catalog_parser.parse_markdown_catalog SAF (DB'siz) — birebir taşınabilir.
- Çerçeve formatı: meta blok (ad/program_key/version/source/notes) + '| Ders | Hazırlık | 9..12 | Tür |' saat matrisi; curriculum_parser da saf; (program_key, version) idempotent upsert anahtarı.
- Okul türü DB'de alan DEĞİL — yalnız CurriculumFramework.program_key slug'ı taşır ('anadolu-lisesi', 'anadolu-lisesi-hazirlik'); mevcut veri SADECE Anadolu Lisesi; diğer okul türleri için TTK PDF'lerinden yeni md dosyaları küratörlenmeli.
- Çerçeveler yalnız ORTAK ders taşır; seçmeli bütçesi türetilir: 40 − ortak toplam (WEEKLY_TOTAL_HOURS=40, selectors.py:851; AL ortak 9/10/11/12 = 32/33/19/15).
- Tembel tohum deseni: services.ensure_meb_catalog + ensure_course_aliases (idempotent, dosya yoksa sessiz) program import view'larının başında çağrılır — masaüstünde ilk açılış tohumu olarak aynen kullanılabilir.
- import_course_rows idempotent upsert: ada göre eşleşir, MEB kaynağı kazanır ama is_active bilinçle korunur (idarenin pasifleştirdiği ders import'la geri açılmaz).
- Sınav modülü çağrıları: get_course(active_only), 'lv not in course.levels' seviye doğrulaması (sinav_islemleri/services.py:509-521), course_names_by_ids, level_label, taught_course_levels, course_level_coverage, course_level_student_ids (son üçü LessonGroup/Enrollment'a dayanır — masaüstünde yok).
- ExamSessionCourse FK → ders_yapisi.Course; benzersizlik (session, course, level); katalog API rotası /exam-courses/ (liste herkese, yazma CanManageCourses, DELETE yok — is_active=False).
- Mükerrer tespiti: duplicate_course_candidates (canon key = TR-duyarsız + şapka düzleme + 'seçmeli ' önek atma); resmi 'Seçmeli X' MEB dersleri öneksiz X ile mükerrer sayılmaz (_split_catalog_elective_cluster).
- Birleştirme: consolidate_duplicate_course tüm referansları taşır, seviyeleri birleştirir, kopya adını CourseAlias olarak öğrenir, kopyayı soft-delete eder; API: GET /exam-courses/duplicates/ + POST /exam-courses/merge/.
- Normalize yardımcıları saf ve kopyalanabilir: _match_key (İ/I + Â/Î/Û), _canon_course_key, titlecase_tr, repair_truncated_course_name; Python .upper/.lower TR'de bozuk olduğundan elle çeviri tablosu kullanılır.
- CourseAlias (takma ad) 2 kaynaklı: SEED (ders-adi-takma-adlari.md, ~55 satır) + OPERATOR (UI 'Bağla' öğrenmesi); OPERATOR SEED'i ezer, tersi olmaz — yalnız e-Okul/AI içe aktarma yapılacaksa gerekli.
- e-Okul/AI ders adı çözüm zinciri (eokul_importer.resolve_course:458-566): operatör eşleme → MEB normalize → alias → AI subject_canonical → kırpık ad onarımı → casing-duyarsız → (opsiyonel) MANUAL create + titlecase.
- LessonGroup/LessonEnrollment/TeachingAssignment Postgres-only (DateRangeField, ExclusionConstraint, btree_gist migration 0003) — porta ALINMAZ.
- Classroom (program dersliği) ile sınav salonu (ExamRoom, 2D oturma düzeni) OYS'de bilinçle AYRI kavramlardır (teknik borç F30) — portta yalnız ExamRoom tarafı ilgilidir.
- Veri dosyaları: anadolu-lisesi-2025-2026.md (64 ders), cerceveler/anadolu-lisesi-2025.md (16 ortak ders matrisi), cerceveler/hazirlik-anadolu-lisesi-2025.md, ders-adi-takma-adlari.md; JSON/Django-fixture yok, data/raw boş.
- Frontend referans ekranları: DersCizelgeleriPage.tsx (çerçeve CRUD + EntryMatrix + ElectivePickerDialog 'Katalogdan seçmeli ekle' = /exam-courses/?course_type=ELECTIVE&level=N) ve SinavSihirbazi ders→seviye→şube akışı; CURRICULUM_LEVELS=[0,9,10,11,12] istemci sabiti.
- Ders havuzu API istemcisi hâlâ sinav-islemleri/api.ts'te (courseApi, /exam-courses/); ders-yapisi/api.ts yalnız grup/derslik/mükerrer uçlarını kapsar — portta tek modülde birleştirilebilir.

## riskler
- SQLite geçişi: levels__contains JSONField sorgusu SQLite'ta çalışmaz — Course.levels tasarımı (ayrı tablo veya Python süzme) portta değiştirilmeden selectors.courses() birebir taşınamaz.
- MEB çizelge verisi yalnız Anadolu Lisesi için mevcut; 'okul türüne göre havuz' hedefi için diğer tür çizelgeleri (Fen, AİHL, MTAL, ortaokul...) TTK kaynaklarından elle küratörlenmek zorunda — kaynak PDF depoda yok (data/raw boş), format sözleşmesi README'lerde.
- Okul türü OYS'de veri modeli olarak yok (program_key slug'ına gömülü); portta açık okul-türü modeli/konfigürasyonu tasarlanmalı, yoksa katalog filtrelemesi kurulamaz.
- VALID_COURSE_LEVELS lise-sabit (0,9-12); ortaokul/ilkokul kademeleri hedefleniyorsa normalize_levels/level_label/CURRICULUM_LEVELS dahil tüm seviye doğrulamaları genişletilmeli.
- taught_course_levels / course_level_coverage / course_level_student_ids LessonGroup+LessonEnrollment verisine dayanır — masaüstünde ders programı olmayacağından sınav takviminin 'Programdan Doldur' ve öğrenci-çakışma denetimi özellikleri ya düşer ya elle veri girişine bağlanır.
- Course tablosu OYS'de soft-delete (BaseModel deleted_at) + koşullu unique constraint desenine dayanır; port şablonu (disiplin-defteri-codex) farklıysa uq_course_name_alive benzeri kısıtlar yeniden kurgulanmalı.
- catalog_parser/curriculum_parser 'saf' olsa da apps.ders_yapisi.models/services'ten enum/CourseRow import eder — kopyalarken bu üç küçük bağımlılık yerelleştirilmeli.
- Seçmeli/'Seçmeli X' önek ayrımı ince kural yüküdür (_canon_course_key + _split_catalog_elective_cluster + alias seed istisnaları); mükerrer birleştirme portlanacaksa bu istisnalar test edilmeden basitleştirilirse resmi 'Seçmeli Biyoloji' ile 'Biyoloji' yanlışlıkla birleştirilir.
- MEB çizelgesi güncellenebilir (yeni TTK kararı): portta sürüm alanı (version) ve 'MEB kaynağı kazanır ama is_active korunur' upsert semantiği korunmazsa kullanıcı düzenlemeleri güncellemede ezilir.


================================================================================
AJAN: sablon
================================================================================

# GÖREV D — Disiplin Defteri masaüstü ŞABLONU (kelebek-sinav için iskelet çıkarımı)

Kaynak: `C:\Users\aalid\.claude\apps\disiplin-defteri-codex` (VERSION `2026.7.0-beta.1`, CalVer). Durum: F0–F5 tamam; CI'da Windows `setup.exe`+`portable.zip` ve Linux `.deb` (debian:11+12 kurulum provası) uçtan uca yeşil (24.07.2026). Ölçek: backend ~22.500 satır Py + 470 test · desktop/packaging ~4.700 satır + ~111 test · frontend ~26.900 satır TS/TSX + 360 test. Aşağıdaki her satır kodda doğrulandı.

## 1. `desktop\` katmanı — dosya dosya sözleşmeler (~1.700 satır + 12 test dosyası)

**Açılış sırası (`desktop/main.py`, 183 satır):** `resolve_app_paths` → `paths.ensure()` → `configure_logging` → `DD_RTHOOK_UYARI` env'ini günlüğe taşı → `get_app_version` → `check_sync_hazard` (uyarır, engellemez) → `SingleInstanceLock.acquire()` → **belirteç üret + `os.environ[DD_SESSION_TOKEN]`** (settings okunmadan ÖNCE — kritik) → `prepare_data()` → `serve()` → finally: env temizle + kilit bırak. `prepare_data`: `ensure_stamp_compatible` → `check_database_integrity` → `encrypt_legacy_backups` → `daily_backup` → `rotate_backups` → `prepare_django(resolve_backend_dir(), data)` → `has_pending_migrations()` ise `pre_migrate_backup` → `run_migrations` → `write_version_stamp`. Sıra bilinçli: bütünlük denetimi yedekten ÖNCE (bozuk DB rotasyonla sağlam yedekleri eskitmesin). `serve`: `build_wsgi_application` → `assert_session_guard_installed` (fail-closed) → `BackgroundServer.start` → `wait_until_ready` → `check_health` → `--autotest` ise pencere açmadan EXIT_OK; değilse `require_window_runtime` → `open_window`.

| Dosya | Satır | Sözleşme |
|---|---|---|
| `paths.py` | 180 | `AppPaths(root,data,backups,logs,cache)` frozen dataclass; Win `%LOCALAPPDATA%\DisiplinDefteri` (Roaming ASLA — OneDrive/gezici profil SQLite bozar), Linux XDG üçlü ayrım (share/state/cache); `DD_APP_HOME` tek hamlede ezer (test/taşınabilir kip); `platformdirs` bilinçli KULLANILMADI (saf `os.environ` — Linux testleri Win yerleşimini doğrulayabilsin); `resource_root()` = `sys._MEIPASS` veya depo kökü; `resolve_backend_dir()` gerçek `config/settings.py` DOSYASI arar (`DD_BACKEND_DIR` > `resource_root()/backend` > depo) — bulamazsa `FileNotFoundError`; `check_sync_hazard` `_SYNC_MARKERS` (onedrive/dropbox/…/appdata\roaming) |
| `lock.py` | 109 | Tek-instance: Win `msvcrt.locking(LK_NBLCK)`, POSIX `fcntl.flock(LOCK_EX|LOCK_NB)`; dosya `a+b` açılır (PID YAZILMAZ — bayat PID sorunu yok, kilit OS tarafından süreç ölünce düşer); alınamazsa `AlreadyRunningError` (çıkış 2); context manager |
| `errors.py` | 79 | `StartupError(message, hint)` + `full_message`; çıkış kodları: 0 OK, 1 beklenmeyen, 2 zaten çalışıyor, 3 DB bozuk, 4 şema-çok-yeni, 5 migrate hatası, 6 sunucu, 7 WebView2 yok, 8 PDF duman (giris.py) — CI ve kurulum testleri bu kodlara bakar |
| `integrity.py` | 57 | `PRAGMA integrity_check(1)` (hızlı; ilk hatada durur); dosya yoksa sessiz döner (ilk açılış); `sqlite3.DatabaseError` veya `!= "ok"` → `DatabaseCorruptError` + yedek klasörünü gösteren Türkçe ipucu |
| `backup.py` | 189 | **Dosya kopyalanmaz**: `sqlite3.Connection.backup()` ile RAM'de tutarlı görüntü (`database_snapshot` → `serialize()`), `.ddbak` şifreli kapsayıcıya atomik yazım; `gunluk-YYYY-MM-DD.ddbak` gün-idempotent (aynı gün yeniden ÜRETMEZ — akşam bozulan veri sabahki yedeği ezmesin); `pre-migrate-<sürüm>-<tarih>` sadece bekleyen göç varsa; rotasyon: günlük 14 GÜN, pre-migrate son 5 ADET; desen dışı dosyalara DOKUNMAZ; `encrypt_legacy_backups` eski düz `.sqlite3` yedekleri dönüştürür. **DİKKAT:** `load_public_key` başarısızsa (parola hiç kurulmadıysa `yedekleme.json` YOKTUR) yedek UYARIyla ATLANIR |
| `backup_crypto.py` | 190 | Zarf: DEK'ten HKDF ile X25519 özel anahtar türetilir; açık anahtar `yedekleme.json`'da (parolasız açılışta yedek alınabilsin); içerik ephemeral X25519 + AES-256-GCM, `DDBAK\x02` magic + kurtarma başlığı (`guvenlik.json` kopyası) gömülü; atomik `.tmp`+`replace` |
| `version.py` | 109 | Damga DOSYA (`surum.json`), tablo DEĞİL (DB bozukken de okunur, migration gerektirmez, eksikse engel sayılmaz — kullanıcıyı kilitlemeyen tarafta hata); `version_key` ön-sürüm sıralaması (`-dev` < kesin); damga yeni → `SchemaTooNewError` (eski exe yeni DB'yi AÇMAZ); sürüm kaynağı `DD_APP_VERSION` > paket kökündeki `VERSION` |
| `session_guard.py` | 99 | Authsuz programın TEK ağ sigortası: açılış başına `secrets.token_urlsafe(32)`; pencere URL'sinde `?t=`; middleware çerez(`dd_oturum`, HttpOnly, SameSite=Strict) > `X-DD-Token` başlığı > sorgu; `hmac.compare_digest`; belirteçsiz → sözleşmeli 403 JSON; `DD_SESSION_TOKEN` boşsa `MiddlewareNotUsed` (geliştirme/test hiç yüklemez → backend'in desktop'a import bağımlılığı YOK); belirteç asla loglanmaz |
| `server.py` | 206 | waitress arka plan thread'i, `host=127.0.0.1`, **`port=0`** (boş portu OS seçer — önce ara sonra bağlan yarışı yok), `effective_port` METİN döner (int'e çevrilir), `ident=None` (sürüm sızdırma yok), `threads=6`; `ServerFactory` enjekte edilebilir (test); `check_health` İKİ istek: belirteçsiz → 403 BEKLENİR (200 dönerse koruma yok → durur), belirteçli → 2xx; `HEALTH_PATH = "/api/v1/setup/status/"` |
| `django_bootstrap.py` | 103 | `sys.path.insert(0, backend)` + `DD_DATA_DIR` + `DJANGO_SETTINGS_MODULE=config.settings` → `django.setup()`; Django import'ları TEMBEL (paths/lock/backup testleri Django'suz koşar); `has_pending_migrations` (`MigrationExecutor.migration_plan`); `run_migrations` (`call_command("migrate", interactive=False)` → hata `MigrationError`); `assert_session_guard_installed` fail-closed; `apply_access_log_policy` `django.setup()` ve `get_wsgi_application()` SONRASI yeniden uygulanır (dictConfig susturmayı siler) |
| `logging_setup.py` | 106 | `RotatingFileHandler` 1 MB×3, yalnız veri dizini `logs/uygulama.log`; `PiiSafeFormatter` sorgu dizesini kırpar (`?search=Ayşe` → `?…`); waitress/django.server erişim logları SUSTURULUR (KVKK); `--autotest`'te stderr echo; `propagate=False` |
| `dialogs.py` | 80 | GUI'den başlatılan programda stderr görünmez → önce günlük, sonra Win `ctypes.windll.user32.MessageBoxW`, Linux zenity→kdialog; hiçbir koşulda hata yükseltmez |
| `window.py` | 288 | **MSHTML düşüşü KODLA ENGELLİ**: WebView2 registry tespiti (`EdgeUpdate\Clients\{F3017226-…}` üç anahtar, `pv` ∉ {"", "0.0.0.0"}) yoksa `WebViewUnavailableError` (çıkış 7); `webview.start(gui="edgechromium"/"qt", private_mode=False, storage_path=cache/webview)`; `module.settings["ALLOW_DOWNLOADS"]=True` (pywebview 5.x indirmeleri engeller — `saveBlob` sessizce yutulurdu); `TitleBarApi` js_api köprüsü DWM koyu başlık çubuğu (attribute 20/19) + WinForms ikon + `SetCurrentProcessExplicitAppUserModelID("DisiplinDefteri.Desktop")`; pencere 1280×860, min 1024×700; pywebview TEMBEL import |

Testler `desktop/tests/` (12 dosya): backend testleriyle AYNI pytest sürecinde koşamazlar (günlük yapılandırması) — `gates.sh` ayrı `-w /repo` koşusuyla çözer.

## 2. `packaging\` — ortak spec kalıbı + iki platform hattı

- **`pyinstaller/disiplin_defteri.spec` (255):** Windows+Linux ORTAK. **Tasarımdan bilinçli sapma:** backend `collect_submodules('apps')` ile donmaz; `Tree()` ile KAYNAK ağaç olarak kopyalanır (`backend/config|apps|shared|templates`, `frontend/dist`; excludes: tests/__pycache__). Bedeli **K7**: backend'in üçüncü taraf paketleri `hiddenimports`'ta AÇIKÇA sayılmak zorunda (`collect_submodules`: django, rest_framework, whitenoise, waitress, weasyprint, fontTools, openpyxl, pypdf, webview + elle: pydyf/tinycss2/cssselect2/tinyhtml5/pyphen/PIL/brotli/zopfli/argon2/_argon2_cffi_bindings/cryptography.fernet/filetype/sqlparse/platformdirs/django.db.backends.sqlite3). `datas`: VERSION, LICENSE, .ico, DejaVu 4 TTF + lisans, `fonts.conf.tmpl`, `collect_data_files(django/rest_framework/weasyprint/pyphen/tinyhtml5/webview)`. `DD_WITH_QT=0` → PyQt5'siz hızlı CI derlemesi; `DD_DLL_DIR` → Windows DLL klasörü (yoksa `SystemExit`). `upx=False` (AV yanlış-pozitif), `console=not WINDOWS`, onedir `COLLECT`.
- **`pyinstaller/giris.py` (203):** paket giriş noktası; normalde `desktop.main.run()`'a devreder; `--pdf-duman [dosya]` teşhis kipi: `ĞÜŞİÖÇ ığüşiöç` PDF'i üretir, pypdf ile metni harf harf + `/BaseFont` içinde "DejaVu" doğrular, başarısızsa `FONTCONFIG_FILE/PATH` teşhisi basar; çıkış 8. `print()` KULLANMAZ (penceresiz derlemede `sys.stdout=None` → AttributeError); `_write` stderr'i None kontrolüyle yazar.
- **`pyinstaller/rthook_dd.py` (129):** giriş betiğinden ÖNCE koşar; (1) Win: `WEASYPRINT_DLL_DIRECTORIES` = paket kökü, (2) Win: `fonts.conf.tmpl`'i `@FONT_DIR@/@CACHE_DIR@` doldurup YAZILABİLİR cache'e yazar + `FONTCONFIG_FILE/PATH`, (3) her platform: `DD_FRONTEND_DIR = <paket>/frontend/dist`. Hata programı DURDURMAZ; uyarılar `DD_RTHOOK_UYARI` env'inde birikir, main.py günlüğe taşır.
- **`pyinstaller/fonts.conf.tmpl` (53):** DOCTYPE satırı BİLİNÇLİ YOK (fonts.dtd çözülmeyince libfontconfig yapılandırmayı SESSİZCE reddeder — ilk CI'da PDF Verdana ile dizildi); tek `<dir>` = gömülü DejaVu, `WINDOWSFONTDIR` EKLENMEZ; sans/serif/mono → DejaVu eşlemeleri + append_last fallback.
- **`pyinstaller/fonts.paket.conf` (59) + build.ps1 adım 4b:** PyInstaller MSYS2 `etc/fonts` ağacını gömer ve libfontconfig **`FONTCONFIG_FILE`'ı DİNLEMEYİP DLL yanındaki o ağaçtan okur** (FC_DEBUG ile kanıtlı) → build.ps1 `_internal\etc\fonts\fonts.conf`'u bu dosyayla EZER (conf.d korunur — yalnız çizim tercihleri). İki fontconfig düzeltmesi de gerekli.
- **`windows/dll_kapanisi.py` (192):** DLL listesi ELLE YAZILMAZ; MSYS2 mingw64/bin'de `SEED_PATTERNS` (libpango*/libpangoft2*/libharfbuzz*/libgobject*/libglib*/libgio*/libfontconfig*/libfreetype*) → `ntldd -R` (yoksa `objdump -p`) özyinelemeli kapanış; yalnız mingw64 içi DLL'ler kopyalanır (KERNEL32 vb. dışarıda). Depoda `windows/dll/` altında üretilmiş ~30 DLL duruyor.
- **`windows/build.ps1` (200):** 8 adım: ön koşul (PATH'ten python — **mingw64\bin altındaki python.exe ELENİR**, ilk CI'da gerçek Python'u gölgeledi) → pip → DLL kapanışı → PyInstaller (`DD_WITH_QT`, `DD_DLL_DIR`) → `veri_sizintisi.py` denetimi → paket içi fontconfig → duman testleri (**`Invoke-Uygulama` = `Start-Process -Wait -PassThru`** — GUI exe'yi `&` beklemez, `$LASTEXITCODE` anlamsız) → portable zip → Inno (iscc PATH + 3 aday konum) → SHA256SUMS. PS1 dosyası BOM'lu olmalı (ilk CI kusuru; `packaging/tests/test_betik_kodlamasi.py` bunu sabitler).
- **`windows/disiplin-defteri.iss` (122):** `AppId={{F0ACB44A-…}}` **ASLA DEĞİŞMEZ; yeni projede YENİ GUID üretilmeli** (yoksa yan yana kurulum). `PrivilegesRequired=lowest` → `{autopf}`=`%LOCALAPPDATA%\Programs` (UAC'siz, VS Code deseni); Turkish.isl; `AppMutex`; WebView2 Evergreen kurucusu pakete girdiyse `[Run]`'da sessiz kurulum (registry `WebView2Eksik` denetimiyle); kaldırma veriyi SİLMEZ (FinishedLabel'da açıkça yazar); sürüm bazlı .ico adı ikon önbelleğini yeniler.
- **`linux/build.sh` (184):** YALNIZ `python:3.12-bullseye` kabında (glibc 2.31 = Pardus 21; §5.2) — host'tan `docker-build.sh` (29) sarmalar (`HOST_UID/GID` ile sahiplik iadesi). Adımlar: apt (pango/harfbuzz/fontconfig/dejavu; `libharfbuzz-subset0` OPSİYONEL — Debian 11'de yok; Qt için libGL+xcb seti) → pip (`DD_WITH_QT=0` ise PyQt satırları grep'le atlanır) → `frontend/dist/index.html` ön koşulu → PyInstaller → veri_sizintisi → `--pdf-duman` + `--autotest` (paketlenmiş ikili üzerinden) → `.deb` (opt/disiplin-defteri + /usr/bin symlink + .desktop + hicolor 7 boyut ikon; `debian-control.tmpl` @VERSION@/@SIZE@/@DEPENDS@; **Depends'e pango bundle'lanmaz — sistem paketleri**; sürümde `-`→`~` çevrimi: `2026.7.0~dev < 2026.7.0`) → `.tar.gz` + `kur.sh`/`kaldir.sh`/BENIOKU → SHA256SUMS.
- **`linux/kap-ici-test.sh` (64):** temiz debian:11/12 kabında `dpkg -i` + `apt-get -f install` → dosya yerleşimi testleri → `--pdf-duman` → `--autotest` ×2 (ikincisi VAR OLAN DB üzerinde) → `dpkg -r` + temizlik doğrulaması.
- **`veri_sizintisi.py` (~100):** pakete `.sqlite3/.xls/.xlsx`, `backend/data|media`, `-shm/-wal` sızmadığını YOL bazlı denetler (içerik okumaz — hata çıktısı da PII içermez); iki platform build'inde de koşar.
- **`.github/workflows/paketleme.yml` (225):** tetik `v*` tag + packaging/VERSION PR + dispatch. İşler: `arayuz` (node 24, `npm ci`+`build` → `frontend-dist` artefaktı) → `linux` (bullseye kabı, build.sh) → `linux-kurulum` (matrix debian 11/12, kap-ici-test.sh) → `windows` (windows-latest + setup-python 3.12 + msys2/setup-msys2 [pango,fontconfig,ntldd-git,binutils] + choco innosetup + WebView2 Evergreen indirimi `continue-on-error` + **mingw PATH'e SONA eklenir**) → `yayin` (tag'de `gh release create`, `~`→`.` ad düzeltme, beta/rc/dev → `--prerelease`).
- Varlıklar: `fontlar/` DejaVu 4 kesim + lisans; `ikonlar/` .ico + 16–512 png + `ikon_uret.py`; `requirements-paketleme.txt`: pyinstaller 6.11.1, pywebview 5.3.2, pythonnet 3.0.5 (win32), PyQt5 5.15.11 + PyQtWebEngine 5.15.7 (linux).

## 3. Backend kalıbı — kelebek-sinav'ın ihtiyacı olan parçalar

- **`config/settings.py` (179, TEK dosya):** `DD_DATA_DIR` → `DATA_DIR` (varsayılan repo içi `backend/data`); sabit SECRET_KEY (yorumla gerekçeli, `DD_SECRET_KEY` ezer); `DEBUG=_bool_env("DD_DEBUG", False)` (KVKK — DEBUG sayfası ham TCKN döker); `ALLOWED_HOSTS=[127.0.0.1, localhost, backend]` (son ad yalnız compose ağı); INSTALLED_APPS: contenttypes+auth (altyapı, model FK'sız)+staticfiles+DRF+okul+disiplin; MIDDLEWARE: Security+WhiteNoise+Common+`AppLockMiddleware`; **`DD_SESSION_TOKEN` doluysa `desktop.session_guard.SessionTokenMiddleware` başa insert edilir** (string referans — import yok); SQLite `init_command`: `journal_mode=WAL; foreign_keys=ON; busy_timeout=5000; synchronous=NORMAL` + `transaction_mode=IMMEDIATE`; `TIME_ZONE=Europe/Istanbul`, `USE_TZ=True`; WhiteNoise: `WHITENOISE_ROOT=FRONTEND_DIR` (`DD_FRONTEND_DIR` env) + `WHITENOISE_INDEX_FILE`; `MEDIA_ROOT=DATA_DIR/media`; DRF: `AUTHENTICATION []` + `AllowAny` + `UNAUTHENTICATED_USER None` + LimitOffset 25 + `EXCEPTION_HANDLER=shared.exceptions.dd_exception_handler`.
- **`config/urls.py` (38):** `/api/v1/` altında iki app; sonda `re_path(r"^(?!api/|static/).*$", spa)` catch-all — `index.html` yoksa 503 + Türkçe açıklama (beyaz ekran yerine).
- **`shared/`:** `models.py` (88) FK'sız `BaseModel` (created/updated/deleted_at + `objects`/`all_objects` + soft `delete()`/`hard_delete()`/`restore()`); `exceptions.py` (60) `{code,message,fields}` sözleşmesi (DRF "invalid"→"validation_error", İngilizce model-sızdıran 404 metni → "Kayıt bulunamadı."); `working_days.py` (51) `add_working_days` + `WorkingDayPredicate` enjeksiyonu; `letterhead.py` (57) antet bağlamı; `crypto.py` (335) `EncryptedCharField/EncryptedTextField` + Argon2id KDF + süreç-ömrü anahtar tutucu + `plaintext_writes()` geçiş kipi; `text.py` (19).
- **`apps/okul/` — kelebek-sinav ihtiyaç haritası:** `SchoolConfig` (singleton pk=1, `setup_completed` kapısı, `load()` okuma-yazmaz; `services/setup.py` whitelist güncelleme + `mark_setup_completed` + `get_letterhead_identity`) → **GEREKLİ** (salon listeleri/tutanaklar antetli basılacaksa). `Personnel` (login'siz; `get_full_name`/`username` OYS şablon paritesi property'leri) → **GEREKLİ** (gözetmen ataması). `Student` (düzleştirilmiş satır: tckn/ad/soyad/no/class_level/class_section/`class_label` property; guardian_* alanları şifreli) → **GEREKLİ** (kelebek dağıtımı sınıf/şube üzerinden; guardian alanları muhtemelen gereksiz → sadeleştirilebilir ama import parser'ı onları bekliyor). `SchoolYear`+`SchoolTerm` → **muhtemelen lazım** (kayıtlar yıl bazlı ise). `Holiday`+`calendar.py` (`is_working_day`, resmî/dini seed) → sınav planlamada yasal iş-günü süresi YOK → **büyük olasılıkla ALINMAZ** (sınav tarihinin tatile denk gelme uyarısı istenirse lite alınır). `ClassResponsibility` → salon/gözetmen modeline İLHAM, birebir değil. Import boru hattı (`normalize.py` 211 — TCKN checksum, telefon 0 iadesi, `10/A|10-A`, `_TR_UPPER_MAP` YALNIZ eşleştirme için; `excel_veli.py` 325 fuzzy başlık `COLUMN_SYNONYMS`; `excel_personel.py` 179; `services/imports.py` 595 preview/commit + sha256 idempotency-uyarı + **xlsx ve pano yapıştırma aynı `rows` matrisi**; `ImportRun` modeli) → **GEREKLİ, en değerli yeniden kullanım**. `lock_middleware.py` (71, 423 Locked + `ALLOWED_PREFIXES`: security/, setup/status/, updates/ — health check kilitliyken de çalışmalı) + `app_password.py` (607, zarf şifreleme + kurtarma anahtarı + `guvenlik.json`) + `encrypted_backup.py` → **OPSİYONEL**; sınav verisi disiplin kadar hassas değil — v1'de atlanabilir, AMA aşağıdaki yedek bağlantısına dikkat. `updates.py` (274, GitHub latest-release + sha256 doğrulamalı kurucu indirme, `DD_UPDATE_REPOSITORY`) → depo adı değişerek **KOPYALA** (UpdateBanner FE'de hazır). `year_rollover.py` (325) → sınav uygulamasında muhtemelen gereksiz.

## 4. Frontend kalıbı

- **`ui/` M3 kiti (23 bileşen, çoğu testli):** Autocomplete, Avatar, Button, Card, ClickableRow, ConfirmProvider, DataTable, DensitySwitcher, Dialog, EmptyState, HubFeatureCard, Icon (material-symbols), ModuleHeader, Select, Skeleton, Snackbar(+Provider), SortHeader, Stepper, Tabs, TextField, ThemeSwitcher, listStyles.ts — OYS'den AYNEN; kelebek-sinav'a birebir taşınır.
- **`lib/`:** `api.ts` (117) authsuz fetch sarmalayıcı — `ApiError{status,code,fields}`, `{code,message,fields}` sözleşmesi, `getBlob/postBlob` (PDF/Excel), FormData'da Content-Type'ı tarayıcıya bırakır, `API_BASE=/api/v1`; `format.ts` — **`todayIso()`** (yerel saat; `toISOString().slice(0,10)` YASAK), `formatDate` gg.aa.yyyy, `Intl` tr-TR; `download.ts` `saveBlob` (revokeObjectURL 1 sn gecikmeli — WebView indirme yarışı); `formErrors.ts`, `pagination.ts`, `gradeLevels.ts`, `queryClient.ts` (staleTime 30 sn, 4xx retry yok, refetchOnWindowFocus false).
- **Hooks:** `useAutosave`, `useDensity`, `useFormErrors`, `useTabParam`, `useTheme`.
- **Kabuk:** `App.tsx` (66) — `AppShell > GuvenlikKapisi > KurulumKapisi > Routes` (kilit kapısı kurulum kapısından ÖNCE); `AppShell.tsx` (269) sidebar + NAV_ITEMS + PAGE_TITLES + UpdateBanner + Theme/DensitySwitcher; `KurulumKapisi.tsx` (89) — `setup_completed=false` iken her rota `/kurulum`'a; **FAIL-OPEN** (durum okunamazsa içeri alır — sihirbaz da aynı backend'e muhtaç), `tamamRef` kısa devre, yönlendirme sebebi `Navigate state` ile taşınır.
- **Yapı:** Vite 6 + React 18.3 + TS 5.9 + Tailwind 3.4 + TanStack Query 5 + react-router 7 + zod 4; `@` alias'ı vite+tsconfig eş; vite proxy `/api → http://backend:8000` + `usePolling` (Windows bind-mount); vitest (jsdom, `src/test/setup.ts`, css:false); eslint 9 flat + prettier. `tailwind.config.js` (246): renkler `rgb(var(--md-*) / <alpha>)` kanal formülü (`index.css` 400 satır token), M3 rol token safelist'i. **`App.test.tsx` "M3 token bütünlüğü"** testi derlenmiş CSS'e karşı üretilmeyen sınıfı yakalar; **`format.test.ts` "tarih disiplini" kaynak-tarama testi** `toISOString().slice` desenini tüm src'de yasaklar — iki koruma testi de yeni depoya taşınmalı.

## 5–6. Kapı zinciri + Docker

`scripts/gates.sh` (55): backend pytest (`--cov=apps --cov=shared --cov-fail-under=75`, pyproject'te) → ruff check → ruff format --check → mypy (strict + django-stubs/drf-stubs) → **AYRI koşu** `-w /repo` desktop+packaging pytest (`--no-cov`) → desktop ruff+mypy (`--config backend/pyproject.toml`, `MYPYPATH=/repo/backend`) → packaging ruff+mypy → FE tsc → eslint → prettier → vitest. Ruff: `E,F,I,UP,B,DJ,S,C4`, satır 100, py312.

`docker-compose.yml`: host'a Python/Node KURULMAZ; `backend` (python:3.12-slim + libpango/libpangoft2/libharfbuzz(+subset)/libfontconfig/libglib/fonts-dejavu-core — **cairo/gdk-pixbuf YOK**, WeasyPrint 63+ saf-Python render) volume `./backend:/app` + `.:/repo`, `DD_DEBUG=1`, `command: sleep infinity`, **hiç port açılmaz**; `frontend` node:20-slim. Bedeli: compose kök yazdığı için `backend/data/`, `node_modules/`, `dist/` root sahipli.

## 7. Bilinen tuzaklar (yeni depoda aynen geçerli)

1. **Tarih disiplini:** UTC'den tarih türetme TR'de 00:00–02:59 arası bir gün geri kayar → FE `todayIso()` + kaynak tarama testi; BE `timezone.now().date()` yerine yerel tarih. (18 formda aynı anda yakalanmış sınıf.)
2. **Türkçe büyük harf:** evrak şablonlarında `text-transform:uppercase` YASAK (i→I); `.upper()/.lower()` yalnız `_TR_UPPER_MAP` üzerinden ve YALNIZ eşleştirme için.
3. **K7 hiddenimports:** backend kaynak ağaç olarak paketlendiğinden yeni Python bağımlılığı spec'e elle eklenmeli — testler yakalamaz, paket sahada çöker; `--pdf-duman` yalnız WeasyPrint zincirini yakalar.
4. **W1–W9** (`packaging/windows/NOTLAR.md`): 24.07.2026 CI yeşili ile büyük bölümü doğrulandı; ilk koşuda çıkan 3 gerçek kusur: PS1 BOM'suzluğu, MSYS2 python gölgelemesi, paket içi fontconfig (`etc/fonts` ezme). W5 (WebView2 LinkId) hâlâ `continue-on-error`.
5. Fontconfig ÇİFT düzeltme (rthook `FONTCONFIG_FILE` + build.ps1 `_internal\etc\fonts` ezme) — ikisi de şart; DOCTYPE'sız fonts.conf.
6. GUI exe + PowerShell: `Start-Process -Wait -PassThru` şart; penceresiz derlemede `print()` çöker.
7. Desktop testleri backend testlerinden AYRI pytest sürecinde (logging çakışması).
8. Parolasız kipte `daily_backup` ATLANIR (yedekleme.json yalnız `app_password.enable/recover` üretir) — parola özelliği alınmayacaksa `backup.py` düz snapshot'a uyarlanmalı ya da kurulumda koşulsuz DEK üretilmeli.
9. `%APPDATA%`/OneDrive senkronu SQLite bozar → veri LOCALAPPDATA + `check_sync_hazard`.
10. Inno `AppId` ve `MAGIC=DDBAK`, `dd_oturum`, `X-DD-Token`, `DisiplinDefteri.Desktop` gibi kimlikler yeni projede YENİDEN üretilmeli (çakışma/karışma).

## 8. Kelebek-sinav için KOPYALA / UYARLA / ALMA tablosu

| Parça | Karar | Not |
|---|---|---|
| `desktop/` 15 dosya | **KOPYALA** | Yalnız ad/kimlik değişimi: `DD_*`→`KS_*` env'leri, `DisiplinDefteri`→`KelebekSinav` dizin adları, pencere başlığı/boyutu, `dd_oturum` çerezi, `HEALTH_PATH` |
| `desktop/backup_crypto.py` + backup şifreleme | **UYARLA/KARAR** | Parola özelliği alınmazsa: ya düz `.sqlite3` snapshot yaz (backup.py ~20 satır sadeleşir) ya koşulsuz DEK üret |
| `packaging/pyinstaller/*` (spec, giris, rthook, fonts.conf.tmpl, fonts.paket.conf) | **KOPYALA** | hiddenimports listesi yeni bağımlılık setine göre gözden geçirilir; WeasyPrint kullanılmayacaksa DLL kapanışı + fontconfig + `--pdf-duman` TAMAMEN düşer (Windows hattı çok sadeleşir) — salon listeleri PDF basılacaksa AYNEN kalır |
| `packaging/windows/` (build.ps1, dll_kapanisi, .iss) | **KOPYALA** | YENİ AppId GUID + AppMutex + ürün adları; `dll/` klasörü CI'da yeniden üretilir |
| `packaging/linux/` (build.sh, docker-build, kap-ici-test, test-kurulum, kur/kaldir, control.tmpl, postinst/prerm, .desktop) | **KOPYALA** | paket adı/yolları değişir; bullseye kuralı ve Depends listesi aynen |
| `packaging/fontlar/`, `ikonlar/ikon_uret.py`, `veri_sizintisi.py`, `tests/` | **KOPYALA** | ikonlar yeniden çizilir |
| `.github/workflows/paketleme.yml` | **KOPYALA** | artefakt/paket adları; WeasyPrint'siz senaryoda msys2 adımı düşer |
| `config/settings.py` + `urls.py` (SPA catch-all) | **KOPYALA** | env ön eki + INSTALLED_APPS |
| `shared/models|exceptions|working_days|letterhead|text` | **KOPYALA** | working_days/letterhead yalnız gerekiyorsa |
| `shared/crypto.py` + `okul/lock_middleware` + `app_password` + `guvenlik/` FE | **ALMA (v1)** | Gerekirse sonradan blok hâlinde eklenebilir — bağımsız tasarlanmış |
| `apps/okul`: SchoolConfig+setup sihirbazı, Personnel, Student, ImportRun, normalize+excel parser'ları+imports, selectors/serializers/views ilgili kısımları | **UYARLA** | Kelebek-sinav'ın çekirdek verisi; guardian_* alanları sadeleştirilebilir (import parser'ı ile birlikte), şifreli alan sınıfları düz CharField'a döner |
| `apps/okul`: SchoolYear/SchoolTerm | **UYARLA** | Sınav dönemleri yıl bazlıysa al |
| `apps/okul`: Holiday+calendar, ClassResponsibility, year_rollover, purge/imha | **ALMA** | İş-günü yasal süre motoru sınav planlamada yok; ClassResponsibility yalnız desen ilhamı |
| `apps/okul/services/updates.py` + FE `guncelleme/` | **KOPYALA** | `DD_UPDATE_REPOSITORY` yeni depo |
| `apps/disiplin` tamamı (state_machine, discipline_periods, documents.py, 25 şablon, deadlines) | **ALMA** | Alan mantığı tamamen farklı; yalnız `documents.py`'nin WeasyPrint çağrı deseni + `templates/documents/base.html`+`print/_design.css` (A4 `@page`+`@bottom-center`) salon listesi PDF'i basılacaksa ŞABLON OLARAK uyarlanır |
| FE `ui/` kiti + `lib/` + `hooks/` + index.css + tailwind.config + vite/vitest/eslint/prettier + `test/setup.ts` | **KOPYALA** | M3 token bütünlüğü testi + tarih disiplini tarama testi MUTLAKA birlikte |
| FE `AppShell`, `App.tsx`, `KurulumKapisi`, `PanelPage`, `KurulumPage`, `KisilerPage`, `AyarlarPage` | **UYARLA** | NAV_ITEMS/rotalar/sihirbaz adımları yeni alana |
| FE `disiplin/ kurul/ odul/ imha/ yildevri/ bilgi-notlari/` | **ALMA» | — |
| `scripts/gates.sh`, `docker-compose.yml`, `docker/backend.Dockerfile`, `backend/pyproject.toml`, requirements* | **KOPYALA** | WeasyPrint/pypdf/openpyxl satırları ihtiyaca göre; kapsam kapısı %75 korunur |
| `website/` stub + `pages.yml` | **ALMA** | kelebek-sinav doğrudan okulapp.org düzenine girer (kendi alanına yazar, `okulapp.org/CLAUDE.md` kuralları) |

## key_facts
- Açılış sırası sözleşmesi (desktop/main.py): kilit → belirteç (settings'ten ÖNCE env'e) → sürüm damgası → integrity_check → günlük yedek+rotasyon → migrate(+öncesi yedek) → waitress thread → pywebview; her adımın ayrı çıkış kodu (0-8, desktop/errors.py) — CI ve kurulum testleri bu kodlara bakar
- Backend, PyInstaller'a KAYNAK AĞAÇ olarak girer (spec'te Tree'ler); bedeli K7: her yeni üçüncü taraf Python bağımlılığı packaging/pyinstaller/*.spec hiddenimports'a ELLE eklenmeli — testler yakalamaz, paket sahada çöker
- settings.py TEK dosya: SQLite WAL init_command (WAL+foreign_keys+busy_timeout 5000+synchronous=NORMAL) + transaction_mode=IMMEDIATE; DRF authsuz (AUTHENTICATION [], AllowAny, UNAUTHENTICATED_USER None); {code,message,fields} hata sözleşmesi FE lib/api.ts ile eşleşir
- Session guard: açılış başına secrets.token_urlsafe(32), pencere URL'sinde ?t=, sonra HttpOnly çerez; DD_SESSION_TOKEN boşken MiddlewareNotUsed → backend'in desktop'a import bağımlılığı yok; check_health belirteçsiz istekten 403 BEKLER (fail-closed)
- Veri dizini: Windows %LOCALAPPDATA% (Roaming/OneDrive ASLA — SQLite bozulur), Linux XDG share/state/cache ayrımı; KS_APP_HOME benzeri tek env ile ezilebilir; yedek = Connection.backup() RAM görüntüsü, dosya kopyalama ASLA (WAL tutarsızlığı)
- Parolasız kipte günlük yedek ATLANIR: yedekleme.json (X25519 açık anahtarı) yalnız app_password.enable/recover üretir; kelebek-sinav parola özelliğini almayacaksa backup.py düz snapshot'a uyarlanmalı
- Fontconfig ÇİFT düzeltme şart: rthook FONTCONFIG_FILE üretir AMA libfontconfig DLL yanındaki _internal/etc/fonts/fonts.conf'u okur → build.ps1 onu fonts.paket.conf ile ezer; fonts.conf'ta DOCTYPE satırı OLMAMALI (sessiz ret → sistem fontu)
- PDF duman testi (--pdf-duman, çıkış 8): ĞÜŞİÖÇ ığüşiöç PDF'i üret + pypdf ile metni ve /BaseFont'ta DejaVu'yu doğrula — WeasyPrint DLL zinciri ve font sorunlarını her derlemede yakalar; WeasyPrint kullanılmazsa bu hat tamamen düşer
- Windows tuzakları kodda çözülü: GUI exe için Start-Process -Wait -PassThru (LASTEXITCODE), penceresiz derlemede sys.stdout=None → print yasak, MSHTML düşüşü gui='edgechromium' + registry tespitiyle engelli, pywebview settings['ALLOW_DOWNLOADS']=True şart
- Inno: PrivilegesRequired=lowest → %LOCALAPPDATA%\Programs (UAC'siz); AppId GUID yeni projede MUTLAKA yeniden üretilmeli; WebView2 Evergreen kurucusu gömülü, yoksa sessiz kurulum + registry denetimi
- Linux: build YALNIZ python:3.12-bullseye kabında (glibc 2.31 = Pardus 21); pango/fontconfig .deb Depends ile sistemden (bundle edilmez); PyQt5+QtWebEngine pencere; kap-ici-test.sh debian:11+12'de dpkg -i + --autotest ×2 + --pdf-duman
- gates.sh zinciri: backend pytest(cov≥75)→ruff→ruff format→mypy strict→desktop+packaging pytest AYRI süreçte (-w /repo, logging çakışması)→desktop/packaging ruff+mypy→FE tsc→eslint→prettier→vitest; her şey Docker'da, host'a Python/Node kurulmaz, compose port açmaz
- İki koruma testi yeni depoya taşınmalı: format.test.ts 'tarih disiplini' kaynak tarama (toISOString().slice yasağı — todayIso() zorunlu) ve App.test.tsx 'M3 token bütünlüğü' (derlenmiş CSS'te üretilmeyen Tailwind sınıfı)
- FE iskeleti: 23 bileşenlik M3 ui/ kiti + lib/ (authsuz api.ts, saveBlob, queryClient staleTime 30sn/4xx-no-retry) + 5 hook; App = AppShell > (GuvenlikKapisi) > KurulumKapisi > Routes; KurulumKapisi FAIL-OPEN (backend okunamazsa içeri alır)
- Kurulum sihirbazı kalıbı: SchoolConfig singleton (pk=1) + setup_completed kapısı + mark_setup_completed servisi; health endpoint /api/v1/setup/status/ hem desktop check_health hem kilit muafiyeti tarafından kullanılır — üçü birlikte taşınır
- Import boru hattı en değerli yeniden kullanım: parser'lar rows matrisi alır → xlsx VE pano yapıştırma aynı yol; preview(dry-run)/commit iki adım; sha256 idempotency UYARI (engel değil); normalize.py TCKN checksum + _TR_UPPER_MAP (yalnız eşleştirme, evraka basılmaz)
- Türkçe iki gerçek tuzak: UTC'den tarih türetme 00:00-02:59'da bir gün geri kayar (18 formda yakalandı); text-transform:uppercase evrakta yasak (i→I, doğrusu İ)
- SQLite koşullu UniqueConstraint (partial index) çalışır — tek-aktif SchoolYear, canlı-tekil TCKN gibi kısıtlar şablonda hazır; select_for_update no-op (tek yazar, kabul)
- Sürüm damgası DOSYA (surum.json), tablo değil: eski exe yeni DB'yi açmaz; damga eksikse engel sayılmaz (kullanıcıyı kilitlemeyen tarafta hata); VERSION dosyası CalVer + v* tag → GitHub Release
- updates.py hazır kalıp: GitHub latest release + sha256 doğrulamalı kurucu indirme + FE UpdateBanner; tek değişiklik depo adı env'i
- Kimlik sabitlerinin tümü yeniden adlandırılmalı: DD_* env'leri (14 adet), DisiplinDefteri/disiplin-defteri dizinleri, dd_oturum çerezi, X-DD-Token, DDBAK magic, .ddbak uzantısı, AppUserModelID, Inno AppId+AppMutex
- kelebek-sinav'ın okul çekirdeğinden ihtiyacı: SchoolConfig+sihirbaz, Personnel, Student (guardian'sız sadeleştirilebilir), ImportRun+parser'lar, muhtemelen SchoolYear; Holiday/iş-günü motoru, ClassResponsibility, year_rollover, imha, disiplin app'i ALINMAZ
- veri_sizintisi.py her iki platform build'inde koşar: pakete .sqlite3/.xlsx/backend-data sızmasını yol bazlı keser (KVKK) — aynen taşınmalı

## riskler
- K7 hiddenimports: kelebek-sinav yeni bir Python paketi eklerse (ör. sınav çizelgeleme kütüphanesi) spec güncellenmezse paket 'geliştirmede çalışıyor, kurulumda çöküyor' verir; testler yakalamaz — yalnız --autotest/duman testleri kısmen yakalar
- Parola özelliği alınmadan backup.py aynen kopyalanırsa günlük yedek SESSİZCE hiç alınmaz (yedekleme.json yok → BackupCryptoError → warning+skip); düz snapshot uyarlaması veya koşulsuz DEK şart
- Inno AppId GUID'i ve DDBAK magic/çerez/env adları değiştirilmeden kopyalanırsa iki uygulama aynı makinede birbirinin kurulumunu/verisini karıştırır
- WeasyPrint alınacaksa Windows DLL zinciri (MSYS2+ntldd+fontconfig çifte düzeltme) tüm karmaşıklığıyla gelir; alınmayacaksa bu hattı erken kararlaştırmak packaging'i büyük ölçüde sadeleştirir — ortada kalmak en pahalı seçenek
- Disiplin Defteri'nde doğrulanamayan kalemler şablonla birlikte taşınır: .deb yükseltme yolu (D5), WebView2 yokluğu senaryosunun gerçek makine testi (D6), Argon2 cffi toplama (D7), WebView2 Evergreen LinkId (W5 continue-on-error)
- Desktop testleri backend testleriyle aynı pytest sürecinde koşturulursa logging yapılandırması çakışır — gates.sh'ın ayrı-koşu deseni korunmalı
- Öğrenci/veli gerçek verisi (KVKK): .gitignore data/media/xlsx engelleri ve veri_sizintisi denetimi kopyalanmazsa paket veya depo üzerinden kişisel veri sızma riski
- Frontend M3 token/tarih tarama testleri kopyalanmazsa aynı iki kusur sınıfı (üretilmeyen Tailwind sınıfı, UTC tarih kayması) yeni depoda sessizce geri gelir
- pywebview/PyQt5/pythonnet sürüm pinleri bilinçli; yükseltme (ör. PyQt6) Pardus 21 glibc 2.17/2.31 uyumluluğunu ve PyInstaller hook olgunluğunu yeniden ispatlamayı gerektirir


================================================================================
AJAN: eokul
================================================================================

# GÖREV E — e-Okul İçe Aktarma Boru Hatları: disiplin-defteri-codex ↔ okulapp Karşılaştırması ve kelebek-sinav Önerisi

## 0. Düzeltme: "import_okul_export" komutu YOK
okulapp'ta `import_okul_export` adında bir yönetim komutu bulunmuyor. Gerçek komutlar (`C:\Users\aalid\.claude\apps\okulapp\backend\apps\core\management\commands\`): `import_student_parents.py` (117 satır), `import_personnel.py` (117), `import_personnel_pdf.py` (95), `enrich_students_sube.py` (88), `anonymize_excel_for_test.py` (239 — gerçek veli Excel'ini test fixture'ına anonimleştirir). Ders programı tarafında ayrıca `apps/program/management/commands/import_eokul_schedule.py` var.

## 1. disiplin-defteri-codex boru hattı (TEK KULLANICILI ŞABLON — kelebek-sinav'ın birebir modeli)

**Dosyalar** (`C:\Users\aalid\.claude\apps\disiplin-defteri-codex\backend\apps\okul\`):
- `services/imports.py` (596 satır) — transaction sınırı, preview/commit, ImportRun yaşam döngüsü.
- `excel_veli.py` (326) — öğrenci-veli parser'ı (saf, DB'siz); `excel_personel.py` (180) — personel parser'ı; `normalize.py` (212) — saf normalize ediciler. Üçü de OYS'den "AYNEN alındı / sadeleştirilerek alındı" diye işaretli.
- `services/templates.py` (58) — indirilebilir xlsx şablon üretimi (başlıklar parser sinonimleriyle bire bir; ayrı şablon kod yolu yok).
- `views.py:350-412` — `_BaseImportView` (dosya VEYA pano metni tek uçta), 4 uç: `imports/students|personnel/preview|commit/` + `templates/students|personnel/` (urls.py:56-73).
- Frontend: `frontend/src/modules/kisiler/KisilerPage.tsx` (1087; `ImportPanel` satır 832-994, `ImportReportView` 996-1042, `IssueTable` 1044-1086), `modules/kurulum/KurulumPage.tsx` (709; 4 adım: okul kimliği → ders yılı → tatiller → kişiler; kişiler adımı yalnız YÖNLENDİRME + sayım kutuları, import Kişiler ekranında). API istemcisi `modules/okul/api.ts`: `ImportInput = { file: File } | { text: string }` (satır 267), preview/commit çiftleri 453-471.

**Anahtar tasarım kararları (tasarım §4.7'den koda inmiş):**
1. **Dosya + pano AYNI boru hattı**: her giriş `rows` matrisine indirgenir — `read_sheet(file_bytes)` (openpyxl read_only+data_only, etkin sayfa) ya da `text_to_grid(text)` (tab ayraçlı Excel yapıştırması). Hash: dosyada `sha256(bytes)`, metinde satır sonu normalize edilip `sha256(utf8)` (`file_hash`/`text_hash`, imports.py:130-144).
2. **Düzleştirilmiş hedef**: OYS'nin Enrollment/NameHistory/Parent/StudentParentLink zinciri YOK → `Student` satır içi alanlara yazılır: sorumlu veli → `guardian_name/guardian_kinship/guardian_phone`, diğer velinin telefonu → `guardian_phone2` (models.py:356-367; bu alanlar `EncryptedCharField` — uygulama parolası konursa şifrelenir).
3. **Idempotency UYARIDIR, ENGEL DEĞİL**: aynı sha256 daha önce COMPLETED ise `already_imported=True` uyarısıyla MEVCUT ImportRun satırı RUNNING'e çekilip güncellenir (`_open_run`, imports.py:185-211) — `uq_importrun_completed_per_hash` koşullu unique bozulmaz. okulapp'taki `force` bayrağı ve "yeniden işlenmez" davranışı bilinçli KALDIRILMIŞ (güncelleme meşru).
4. **Önizleme = gerçek ingest + rollback**: `_preview_students/_preview_personnel` gerçek `_ingest_*`'i `transaction.atomic()` içinde koşar, `transaction.set_rollback(True)` ile geri alır → ayrı hesaplayıcı yok, %100 sonuç paritesi. Ardından rollback DIŞINDA kalıcı `PREVIEWED` ImportRun yazılır (imports.py:549-583). Kural: ingest zincirine `transaction.on_commit` eklenemez (rollback yan etki sızdırır).
5. **ParserError → kalıcı FAILED izi**: hata transaction dışında `_record_failed` ile yazılır (`report={"error": str(exc)}` — yalnız yapısal bilgi, PII yok); xlsx olmayan bayt `BadZipFile/InvalidFileException` yakalanıp sözleşmeli 400'e çevrilir (".xls veya CSV desteklenmez" mesajı, imports.py:147-160).
6. **Öğrenci eşleştirme**: TCKN varsa `selectors.find_student_by_tckn` (DB filtresi DEĞİL — TCKN şifreliyken `filter(tckn=...)` boş dönerdi, F5-D5 vakası); yoksa okul numarası + ACTIVE durum; aynı numarada >1 aktif öğrenci → satır atlanır. "Boş hücre mevcut veriyi SİLMEZ" ilkesi: okul no/veli/demografi anahtarları yalnız dosyada veri varsa `fields`'a girer (imports.py:286-299). Değişen alanlar `update_fields` ile kaydedilir; created/updated/unchanged sayaçları ayrı.
7. **Personel eşleştirme**: normalize ad-soyad (`normalize_header`: Türkçe→ASCII küçük harf) anahtarlı upsert; ≤100 personel ölçeğinde yeterli, adaş çakışmasında son kayıt kazanır (imports.py:403-464). Yalnız `title`/`branch` güncellenir, boş hücre dokunmaz.
8. **Sınıf → ClassResponsibility tohumu**: import sonunda aktif yıl için görülen (level, section) çiftleri `ClassResponsibility.get_or_create` (imports.py:337-353) — kelebek-sinav'da karşılığı "şube → sınav salonu/derslik listesi" tohumu olabilir.

**Şablonlar + e-Okul rapor yönlendirmesi (KisilerPage.tsx:838-849):** öğrenci şablonu `Sınıf | Okul Numarası | Öğrenci Adı | Öğrenci Soyadı | Öğrenci Doğum Tarihi`; UI ipucu bu bilgilerin **e-Okul Öğrenci İşlemleri → Raporlar → OOG01001R070 "Şube Listesi (Doğum Tarihi/Yaş)"** raporundan alınabileceğini söyler. Personel şablonu `Adı | Soyadı | Görevi | Branşı`; ipucu **e-Okul Kurum İşlemleri → Raporlar → OOK01001R1 "Personel Listesi"**. Yani standalone'da e-Okul PDF PARSE EDİLMEZ; kullanıcı rapordan kopyalayıp şablona/panoya aktarır — PDF bağımlılığı (pypdf) bilinçli alınmamış.

**Rapor UX'i:** `StudentImportReport`/`PersonnelImportReport` dataclass'ları (file_hash, total_rows, processed, created/updated/unchanged, already_imported, dry_run, warnings[], skipped[]); `ImportIssue(row_number, field, issue, raw_value)`. UI: 5'li sayaç ızgarası + "Uyarılar (n)" ve "Atlanan satırlar (n)" tabloları (Satır/Alan/Sorun/Değer) + `dry_run` başlığı "Önizleme — hiçbir kayıt yazılmadı". **Aktar düğmesi yalnız önizleme raporu görüldükten sonra açılır** (`canCommit = report !== null && report.dry_run`, KisilerPage.tsx:868). Dosya/metin değişince rapor sıfırlanır → yeniden önizleme zorunlu (disiplin bunu istemci tarafında çözer; okulapp `expected_hash` ile sunucuda da doğrular).

**KVKK maskeleme:** geçersiz TCKN raporda `mask_tckn` ile (ilk 3 + yıldız + son 2; `shared/text.py:10-19`); telefon ve doğum tarihi ham değeri rapora hiç yazılmaz (bilinçli boş raw_value).

## 2. okulapp (OYS) boru hattı — ÇOK KULLANICILI, daha zengin ama sunucuya bağımlı

**Dosyalar** (`C:\Users\aalid\.claude\apps\okulapp\backend\apps\core\`): `services/imports.py` (1132), `excel_veli.py` (313), `excel_personel.py` (228), `pdf_personel.py` (137), `pdf_sube.py` (119), `normalize.py` (209), `views/imports.py` (751), `models.py:1385-1463` (ImportSourceType/ImportStatus/ImportRun).

**Desteklenen e-Okul kaynakları (ImportSourceType):**
- `STUDENT_PARENTS` — e-Okul **"Veli İletişim Bilgileri" Excel'i** (xlsx): `Sınıf | TCKN | Numa | Adı Soyadı | Veli Kim | Anne Adı SOYADI | AnneTel | Baba Adı SOYADI | BabaTel`. Fuzzy başlık eşleme (`COLUMN_SYNONYMS`), başlık satırı ilk 10 satırda taranır (`detect_columns`, en çok alan eşleşen usable satır kazanır). KRİTİK sütunlar okulapp'ta `("class","tckn","student_name")`; disiplin'de gevşetilmiş: `class` + (`number` VEYA `tckn`) + (`student_name` VEYA `student_first+student_last`).
- `PERSONNEL` — kendi standart Excel şablonu: `Ad Soyad | E-posta | Telefon | Branş | İşe Başlama | Rol 1..N | Kapsam 1..N` (dinamik rol çiftleri regex `^rol\s*(\d+)$`; e-posta kritik — Google OAuth whitelist'i beslediği için). e-Okul kaynaklı DEĞİL.
- `PERSONNEL_PDF` — **e-Okul "Personel Listesi" PDF'i** (`pdf_personel.py`): pypdf metin çıkarımı; kadro sözcükleri (`KADROLU/GÖREVLENDİRME/SÖZLEŞMELİ/İLSİS DIŞI`) adı görev+branş'tan ayıran ÇAPA; görev kalıpları uzun→kısa sırayla (`Müdür Yardımcısı` `Müdür`'den önce); e-Okul PDF görev'i branş'a bitişik basar ("CoğrafyaMüdür"). PDF'te e-posta/TCKN YOK → kullanıcı `can_login=False` + `@personel.local` placeholder ile açılır; sonradan Excel importu placeholder'ı İSİMLE bulup gerçek e-postayla birleştirir (`_find_placeholder_by_name`, imports.py:634-652, `merged_users` sayacı).
- `SUBE_LIST_PDF` — **e-Okul "Şube Listesi — Doğum Tarihi/Yaş" PDF'i** (`pdf_sube.py`): satır regex'i `^(\d+)\s+(.+?)\s+(\d+)\s+(\d{2}/\d{2}/\d{4})\s+(\d+)$`; cinsiyet etiketi (Erkek/Kız) soyada bitişik bastığından ad/soyad ayıracı olarak kullanılır; sayfa başlığından `9. Sınıf / A Şubesi` + `Sınıf Öğretmeni:` okunur. Eşleştirme SADECE okul numarasıyla; doğum tarihi+cinsiyet zenginleştirir, sınıf öğretmenini `Section.advisor` yapar.
- Ayrıca `apps/program/eokul_parser.py` (507) + `eokul_importer.py` (1250): **e-Okul sınıf ders programı PDF'i (OOK11003R010)** — koordinatlı fragment `(x,y,text)` ayrıştırma (pypdf extract_text Türkçe glifleri bozduğu için), gün sütunu x-kümeleme, saat çapaları; öğretmenler İSİMLE eşlenir. Gözetmen "meşgul" tespiti bu programa bağlı (`sinav_islemleri/services.py:1380-1394`: `program_services.teachers_free_at` + `core_services.active_teachers()`).

**Öğrenci-veli ingest'i (okulapp) disiplin'den farkları:** tarihsel model — `find_student_by_identifiers` (TCKN→numara→ad önceliği), `change_enrollment` (yıl bazlı Enrollment), `StudentNameHistory` (valid_from/valid_to), veli dedup'u **telefon+ad** ile (`find_parent_by_phone_and_name` — kardeşlerde tek Parent, `reused_parents` sayacı), `StudentParentLink` PRIMARY/SECONDARY + Kinship. `_resolve_parent_roles` (imports.py:391-451) disiplin'deki `_resolve_guardian`'ın kaynağı: ANNE/BABA atanmış ama verisi eksikse diğerine düşer + uyarı; DİĞER/boş → BABA varsayılır + uyarı. Aktif ders yılı yoksa RuntimeError (import reddedilir).

**Idempotency (okulapp)**: aynı hash COMPLETED ise `force=False`'ta HİÇ İŞLENMEZ, önceki rapor `already_processed=True` ile döner; `--force`/checkbox ile mevcut COMPLETED satırı yeniden RUNNING'e çekilir. Disiplin bunu "uyarı + her zaman yeniden işle"ye çevirdi.

**Önizle→onayla güvenliği (ADR-0034 §6)**: commit isteği `expected_hash` taşır; yüklenen dosyanın sha256'sı önizlenenle uyuşmazsa 400 `"Yüklenen dosya önizlenen dosyayla aynı değil"` (`_hash_mismatch_response`, views/imports.py:128-139). >500 satır (`ASYNC_ROW_THRESHOLD`, tasks.py:20) → base64 + Celery, 202 + `file_hash`; frontend import-runs listesini 5 sn × 60 poll'lar (OgrenciVeliImportPage.tsx:22). Önizleme kişisel veri okuması sayılır → AccessLog SENSITIVE_READ.

**Şablon üretimi (views/imports.py:517-751)**: openpyxl ile zengin şablon — TCKN/telefon/no sütunları metin biçimi (`@`, baştaki 0 korunur), doğum tarihi `DD.MM.YYYY`, `E,K` ve `ANNE,BABA,DİĞER` dropdown'ları, personelde "Roller" sayfasından named-range dropdown, "Yönerge" sayfası ("örnek satırları silmeden YÜKLEMEYİN" uyarısı). Disiplin'in şablonu (templates.py) bunun minimal hâli — dropdown/yönerge yok.

**Kurulum sihirbazı (okulapp `SetupWizardPage.tsx`, 683)**: 6 adım — Kurum → Ders Yılı → **Personel (e-Okul PDF veya standart şablon)** → **Öğrenci/Veli (e-Okul Excel veya standart şablon)** → **Şube Listesi PDF (doğum tarihi+rehber; standart şablon doğum tarihi getirdiyse otomatik "atlanabilir")** → **Haftalık ders programı (e-Okul PDF)**. Adımlar kilitlenmez, yalnız bağımlılık uyarısı verilir ("Önce 3. adımı tamamlayın — öğretmenler isimle eşlenir").

## 3. Normalizasyon çekirdeği (iki depoda fiilen AYNI — `normalize.py`)
- `normalize_tckn`: float metni temizle ('...901.0'), 11 hane + **resmî checksum** (ilk hane ≠0; 10. hane = (tek haneler×7 − çift haneler) mod 10; 11. = ilk 10 toplam mod 10). Geçersiz → None → satır SKIP (rapora maskeli).
- `normalize_phone`: int/float/+90/ayraç temizliği → `0XXXXXXXXXX` 11 hane; 10 haneye baştaki 0 eklenir; 12 hane `90...` ülke kodu atılır.
- `normalize_class_section`: `'10/A' | '10-A' | '10 A'` → `(10,'A')`; **9-12 dışı None** (lise varsayımı; kelebek-sinav farklı okul türü hedefleyecekse aralık config'e alınmalı — okulapp'ta `grade_levels.py`/`SchoolConfig` okul türü seçimi var).
- `split_full_name`: son kelime soyad; Title Case uygulanmaz (ham korunur).
- `normalize_excel_date`: datetime/date hücre + `%d.%m.%Y`, `%d/%m/%Y`, `%Y-%m-%d` metinleri; yıl<1900 ve (varsayılan) gelecek tarih → None; `allow_future=True` işe başlama için +730 gün.
- `normalize_gender`: E/ERKEK/MALE/M/B/BAY→'E', K/KIZ/FEMALE/F/BAYAN→'K'.
- Başlık normalize: `_TR_MAP` Türkçe→ASCII küçük harf + alfasayısal dışı → boşluk; **sinonim sırası kritik** (telefonlar isimlerden, veli isimleri öğrenci isimlerinden önce — 'annetel'→'anne' yanlış eşleşmesi engellenir).

## 4. Öğretmen (personel) tarafında hangi e-Okul/MEBBİS raporu?
- okulapp: **e-Okul "Personel Listesi" PDF'i** (Kurum İşlemleri raporu) — ad-soyad, görev, kadro durumu, branş verir; e-posta/TCKN vermez. MEBBİS raporu HİÇBİR depoda kullanılmıyor.
- disiplin-defteri: PDF parse edilmez; aynı raporun (**OOK01001R1**) ekranından/çıktısından kopyalanıp `Adı|Soyadı|Görevi|Branşı` şablonuna ya da panoya aktarılması istenir.
- kelebek-sinav için öneri: disiplin yolunu VARSAYILAN yap (şablon+pano — kırılgan PDF metin çıkarımına bağımlılık yok), okulapp `pdf_personel.py`'yi (137 satır, saf, pypdf) OPSİYONEL "PDF'ten oku" hızlandırıcısı olarak eklemeyi değerlendir. Gözetmenlik için gereken alanlar zaten bu rapordan çıkıyor: ad-soyad + görev (Müdür/Müdür Yrd./Öğretmen — muafiyet kuralları görevle kurulabilir) + branş (kendi-branş dersine gözetmen atamama kuralı). Kadro durumu (`kadro_durumu`) disiplin'e alınmamış; kelebek-sinav'da da gerekmez.

## 5. kelebek-sinav için ÖNERİLEN import mimarisi

**AYNEN AL (disiplin-defteri-codex'ten, kanıtlanmış ve tek-kullanıcıya uyarlı):**
1. `normalize.py` (212) — hiç değiştirmeden (sınıf aralığı 9-12'yi sabit tutma kararı hariç; parametreleştir).
2. `excel_veli.py` + `excel_personel.py` — fuzzy başlık tespiti, sinonim tabloları, `read_sheet`; kelebek'te veli alanları da gerekiyorsa (yoklama evrakında veli genellikle GEREKMEZ → sinonim tablosundan anne/baba sütunları çıkarılabilir, ama e-Okul "Veli İletişim" Excel'i elde en kolay bulunan öğrenci listesi olduğundan TANIMAYA devam etmesi pratik: fazla sütunlar yok sayılır).
3. `services/imports.py` iskeleti: dosya+pano tek boru hattı, sha256 idempotency-uyarısı (`already_imported` engel değil), gerçek-ingest+rollback önizleme, PREVIEWED/FAILED kalıcı izleri, `ImportRun` modeli (performed_by'sız), `mask_tckn`.
4. Frontend `ImportPanel`/`ImportReportView`/`IssueTable` deseni + "Önizle görülmeden Aktar kapalı" kuralı + şablon indir düğmesi; `KurulumPage` 4-adımlı sihirbaz iskeleti (okul kimliği → ders yılı → [tatil yerine: sınav dönemi/salonlar] → kişiler-yönlendirme).
5. `views.py:350-389` `_BaseImportView` + `templates.py` şablon üretimi.

**UYARLA:**
1. Öğrenci hedef modeli: kelebek'te veli zinciri gerekmez; `Student(student_number, first/last, class_level, class_section, gender, birth_date, tckn?)` yeterli. Cinsiyet, karma oturma düzeni (kız-erkek ayrımı) isteniyorsa şablona zorunlu değil opsiyonel sütun olarak kalsın (OOG01001R070 zaten veriyor). TCKN'yi kroki/yoklama evrakı istemiyorsa OPSİYONEL yap ama checksum'lı doğrulamayı koru (dedup anahtarı olarak değerli). Şifreleme (`EncryptedCharField`) kelebek'te muhtemelen gereksiz — tek kullanıcı, kurum içi makine; almazsan `find_student_by_tckn` selector dolambacı da sadeleşir (ama alırsan F5-D5 dersini unutma: şifreli alan DB filtresiyle aranamaz).
2. Personel modeli: `Personnel(first,last,title,branch)` + kelebek'e özgü `is_exempt`/`max_duty` gibi gözetmenlik alanları sonradan elle. Ad-bazlı upsert'i koru ama okulapp'ın `merged_users` dersini not et: iki kaynaklı (PDF+Excel) beslemeye girersen isim-birleştirme kurallarını baştan tasarla.
3. `_ensure_student_classes` karşılığı: import sonunda görülen (level, section) çiftlerinden şube listesi türet — kelebek'in salon/kroki planlaması için şube kataloğu tohumu.
4. e-Okul rapor yönlendirme metinleri: OOG01001R070 (öğrenci) ve OOK01001R1 (personel) ipuçları UI'da aynen kullanılabilir; ekrandan kopyala-yapıştır yolu Pardus'ta da dosyasız çalışır.

**ALMA (okulapp'a özgü, tek-kullanıcı hedefinde gereksiz/zararlı):**
- Celery/async 202 + polling (>500 satır eşiği): masaüstünde waitress senkron yeter; 2000 satırlık okul bile openpyxl'le saniyeler.
- `expected_hash` önizle→onayla sunucu doğrulaması: tek kullanıcıda istemci tarafı sıfırlama (disiplin deseni) yeterli.
- E-posta/rol/whitelist/OAuth zinciri (`excel_personel`'in Rol N/Kapsam N çiftleri, `FORBIDDEN_IMPORT_ROLES`, `suggest_username`): girişsiz uygulamada anlamsız — disiplin zaten söküp atmış.
- AccessLog SENSITIVE_READ denetimi, `performed_by`, KVKK anonimleştirme komutları.
- Enrollment/NameHistory/ParentLink tarihsel zinciri (yıl devrinde yeniden import etmek daha basit — disiplin §4.6 kararı).
- e-Okul ders programı PDF parser'ı (`eokul_parser.py`, 507+1250 satır): "öğretmen o saatte derste mi" bilgisi olmadan gözetmenlik yine kurulabilir (okulapp'ta bile bu yalnız `_busy_teacher_ids` kısıtı). İlk sürümde alma; ileride "meşgul öğretmen" özelliği istenirse ayrı iş.
- PDF parser'lar genel olarak: `pdf_sube.py` (öğrenci doğum tarihi/cinsiyet zenginleştirme) yerine OOG01001R070'in Excel/kopyala-yapıştır yolu; pypdf bağımlılığı ancak kullanıcı PDF yüklemekte ısrar ederse eklenmeli (Crystal Reports metin çıkarımı okul/yıl bazında kırılgandır — okulapp yorumları bunu belgeliyor).

**Sıralama önerisi (kurulum sihirbazı):** 1) Okul kimliği 2) Sınav dönemi/ders yılı 3) Personel (şablon/pano) 4) Öğrenci (şablon/pano) 5) Salonlar/derslikler — her adım disiplin'deki gibi kilitsiz, `SetupStatus` benzeri tek uçtan rozetli.

## key_facts
- disiplin-defteri-codex import çekirdeği: backend/apps/okul/services/imports.py (596), excel_veli.py (326), excel_personel.py (180), normalize.py (212), services/templates.py (58), views.py:350-412; frontend KisilerPage.tsx ImportPanel 832-1086, KurulumPage.tsx (709, 4 adım).
- okulapp import çekirdeği: backend/apps/core/services/imports.py (1132), excel_veli.py (313), excel_personel.py (228), pdf_personel.py (137), pdf_sube.py (119), views/imports.py (751), models.py:1385-1463 (ImportRun).
- 'import_okul_export' komutu okulapp'ta YOK; gerçek komutlar: import_student_parents, import_personnel, import_personnel_pdf, enrich_students_sube (core/management/commands).
- Desteklenen e-Okul kaynakları: 'Veli İletişim Bilgileri' xlsx (öğrenci+veli), OOG01001R070 Şube Listesi Doğum Tarihi/Yaş (PDF okulapp'ta / kopyala-yapıştır disiplin'de), OOK01001R1 Personel Listesi (PDF okulapp / şablon-pano disiplin), OOK11003R010 sınıf ders programı PDF (yalnız okulapp program app).
- e-Okul personel PDF'inde e-posta/TCKN yok; okulapp bu yüzden can_login=False + @personel.local placeholder üretir ve sonraki Excel importu isimle birleştirir (merged_users).
- TCKN doğrulama: 11 hane + resmî checksum (normalize.py:_valid_tckn_checksum); geçersiz TCKN satırı SKIP olur ve rapora mask_tckn ile maskeli yazılır (ilk3+*+son2); telefon/doğum tarihi ham değeri rapora hiç yazılmaz.
- Idempotency her iki depoda ImportRun(source_type, sha256 file_hash) + koşullu unique uq_importrun_completed_per_hash; okulapp'ta aynı hash force olmadan YENİDEN İŞLENMEZ, disiplin'de yalnız already_imported UYARISIdır ve mevcut COMPLETED satır güncellenir.
- Dry-run deseni (her ikisinde): gerçek ingest transaction.atomic içinde koşulur + transaction.set_rollback(True) → %100 sonuç paritesi; ardından rollback dışında kalıcı PREVIEWED ImportRun; ingest zincirine on_commit hook yasak.
- Disiplin'de dosya VE pano yapıştırma AYNI boru hattı: read_sheet/text_to_grid → rows matrisi; metin hash'i satır sonu normalize edilerek alınır; .xls/CSV reddedilir (BadZipFile→ParserError→400).
- Fuzzy sütun eşleme: Türkçe→ASCII normalize başlık + sinonim listeleri; SIRA KRİTİK (annetel anne'den önce); başlık satırı ilk 10 satırda aranır; kritik sütunlar disiplin'de class + (number|tckn) + (student_name|first+last) — okulapp'ta class+tckn+student_name.
- Sınıf ayrıştırma normalize_class_section: '10/A','10-A','10 A' → (10,'A'); 9-12 DIŞI None — kelebek-sinav farklı okul türü destekleyecekse bu aralık parametreleştirilmeli.
- Veli çözümü: Veli Kim = ANNE/BABA/DIGER; atanan velinin verisi eksikse diğerine düşülür + uyarı, belirsizde BABA varsayılır; disiplin veliyi Student.guardian_* düz alanlarına yazar (guardian_phone2 = diğer veli), okulapp Parent dedup'unu telefon+ad ile yapar (kardeşlerde tek Parent).
- 'Boş hücre mevcut veriyi silmez' ilkesi iki depoda da: alanlar yalnız dosyada veri varsa fields'a girer; created/updated/unchanged ayrı sayılır (update_fields ile).
- Hata raporlama UX: ImportIssue(row_number, field, issue, raw_value) + warnings/skipped tabloları (Satır/Alan/Sorun/Değer) + summary_tr(); Aktar düğmesi ancak dry_run raporu görüldükten sonra açılır (canCommit).
- okulapp'a özgü ve porta ALINMAYACAKlar: Celery async >500 satır (ASYNC_ROW_THRESHOLD, tasks.py:20) + file_hash polling, expected_hash sunucu doğrulaması, e-posta/Rol-Kapsam/whitelist, AccessLog SENSITIVE_READ, Enrollment/NameHistory/ParentLink tarihsel zinciri.
- Gözetmenlik veri bağımlılığı (okulapp sinav_islemleri/services.py:1380-1401): core_services.active_teachers() + program_services.teachers_free_at (ders programı) + gorevlendirme.absent_staff_ids; participants.py öğrenciden yalnız student_number/class_level/class_section kullanır.
- Disiplin'in Personnel upsert anahtarı normalize ad-soyad (adaşta son kayıt kazanır, ≤100 personel varsayımı); yalnız title/branch güncellenir.
- Şablon üretimi: disiplin templates.py minimal (başlık+örnek satır); okulapp views/imports.py:556-751 zengin (metin biçimli TCKN/tel sütunları '@', E/K ve ANNE/BABA/DİĞER dropdown, Roller named-range, Yönerge sayfası, 'örnek satırı silin' uyarısı) — kelebek için orta yol önerilir.
- Import sonrası şube tohumu: disiplin _ensure_student_classes aktif yıl için görülen (level,section) çiftlerini ClassResponsibility.get_or_create ile açar — kelebek'te salon/kroki için şube kataloğu tohumuna çevrilebilir.
- Disiplin Student.tckn/guardian_* EncryptedCharField: uygulama parolası varken DB filtresi çalışmaz → find_student_by_tckn selector'ı şart (F5-D5 kopya öğrenci vakası); kelebek şifreleme almazsa bu dolambaç gerekmez.
- Kurulum sihirbazları: okulapp 6 adım (kurum→yıl→personel PDF/şablon→öğrenci Excel/şablon→şube PDF→program PDF, adımlar kilitsiz + bağımlılık uyarılı, şube adımı doğum tarihi tamsa otomatik atlanabilir); disiplin 4 adım (okul→yıl→tatil→kişiler-yönlendirme, tek zorunlu kapı aktif ders yılı).
- PDF parser riskleri kodda belgeli: pypdf extract_text görev'i branş'a bitişik basar (CoğrafyaMüdür), cinsiyeti soyada bitiştirir, Türkçe glifleri bozar; okulapp bunları kadro-çapası, Erkek/Kız regex ayıracı ve koordinatlı fragment ayrıştırmayla çözmüş — kelebek ilk sürümde PDF yerine şablon+pano yolunu almalı.

## riskler
- normalize_class_section 9-12 aralığına sabit — kelebek-sinav ortaokul/farklı tür okullarda kullanılırsa satırlar sessizce 'Sınıf/şube çözülemedi' diye atlanır; aralık SchoolConfig benzeri ayara bağlanmalı.
- Disiplin personel eşleştirmesi ada dayalı: adaş personelde son kayıt kazanır (kodda kabul edilmiş sınırlama) — gözetmenlik çizelgesinde yanlış kişiye görev yazılabilir; kelebek'te en azından adaş uyarısı eklenmeli.
- e-Okul PDF raporları Crystal Reports çıktısıdır; metin çıkarımı okul/yıl/sürüm bazında kırılgan (bitişik alanlar, bozuk glifler) — PDF importu eklenirse gerçek dosyalarla fixture testi şart (okulapp test_eokul_parser deseni).
- Öğrenci Excel'inde TCKN yoksa dedup okul numarasına düşer; numara değişen/nakil öğrencide kopya kayıt riski — disiplin bunu '>1 aktif aynı numara → skip' ile kısmen korur, kelebek aynı korumayı taşımalı.
- Pano yapıştırma yolunda hücre tipleri kaybolur (her şey metin gelir); '2612.0' float temizliği _str'de var ama tarih hücreleri metin biçimine bağımlı — kullanıcıya GG.AA.YYYY biçim uyarısı UI'da korunmalı.
- already_imported'ı engel değil uyarı yapmak (disiplin kararı) yanlışlıkla eski dosyayla üzerine yazmayı mümkün kılar; kelebek'te sınav yerleşimi üretilmiş bir dönemde yeniden import, mevcut kroki/gözetmen atamalarını geçersizleştirebilir — import ile üretilmiş evrak arasında 'yeniden üretim gerekli' bayrağı düşünülmeli.
- ImportRun.report JSON'ı maskeli de olsa kişisel veri izi taşır (ad geçen uyarı metinleri); tek kullanıcılı uygulamada yedek/dışa aktarım senaryolarında bu tablo da veri kapsamına girer.
- Ders programı PDF'i alınmadığında 'öğretmen o saat derste' kısıtı kurulamaz; gözetmen önerisi yalnız muafiyet/çakışma/adil yük ile çalışır — kullanıcı beklentisi baştan netleştirilmeli.


================================================================================
AJAN: dokuman
================================================================================

# GÖREV F — OYS Belge/Mevzuat Katmanı Raporu (kelebek-sinav portu için)

Kaynaklar: `C:\Users\aalid\.claude\apps\okulapp\docs\adr\0016-sinav-islemleri-modulu.md` (116 satır), `docs\adr\0044-sinav-takvimi.md` (143 satır), `docs\adr\0043-zumre-modulu.md` (123 satır), `docs\adr\0017-ders-yapisi-cekirdegi-ve-program-importu.md`, `docs\adr\0050-uretilen-evrak-pdf-saklama.md`, `docs\kelebek-sinav-modulu-yol-haritasi.md` (v3, 276 satır), `docs\rapor-tasarim-standardi.md` (73 satır), `docs\MODULES.md` (sinav_islemleri: satır 622-731; ders_yapisi: satır 734-798), `CHANGELOG.txt` (68.255 satır; Tur 221-245, 637-648, 845), `data\mevzuat\meb-olcme-ve-degerlendirme-yonetmeligi.md` (452 satır), `data\mevzuat\meb-yazili-ve-uygulamali-sinavlar-yonergesi.md` (196 satır), `data\mevzuat-notlari\sinav-modulu-mevzuat-teyidi-2026-06-11.md` (59 satır).

## 1. Sınav modülünün tasarım kararları ve gerekçeleri

### 1.1 ADR-0016 (Tur 221, 11.06.2026) — çekirdek kararlar
- **Modeller** (`backend/apps/sinav_islemleri/`): `Course` (Tur 249'da `ders_yapisi`'ne taşındı, ADR-0017 karar 3 — `SeparateDatabaseAndState`, `db_table` korunur), `ExamRoom` (2D `layout_plan` JSON + `numbering_scheme` S_DUZENI|DUZ; kapasite ALANDA TUTULMAZ, plandan türetilir — drift imkânsız), `ExamSession`/`ExamSessionCourse`/`ExamSessionRoom`, `SeatAssignment` (ad/no/şube SNAPSHOT — arşiv yıllar sonra açılsa evrak tutarlı), `PlacementRule`, `QuestionDocument`+`BookletRun`, `ProctorAssignment`+`ProctorExemption`, `ExamAttendanceRecord` (Tur 245). Core eki: `SectionGroup`+`SectionGroupMembership` (Tur 222 — sicil gerçeği core'da; sınav modülü `core.selectors` köprüsünden salt-okunur, `SectionGroupInfo` dataclass).
- **K7 — çakışma birimi sınav grubudur:** anahtar `(course, level)` = `"<course_id>:<level>"`; `shared_booklet` işaretli ders `"<course_id>:*"` tek grup. Şube KISIT DEĞİLDİR — kopya riski aynı kitapçığı çözenler arasındadır.
- **K8 — bitişik masa sert, ötesi mesafe optimizasyonu:** aynı gruptan iki öğrenci aynı masada bitişik oturamaz (sert); *katı mod* birinci halkayı (Chebyshev ≤ 1 komşu sıra) da serte çevirir. Esnek kısıtlar öncelik sırasıyla: E1 mesafe maksimizasyonu (hedef: 1. halkada aynı-grup çifti = 0), E2 salonlar arası doluluk dengesi, E3 kız-erkek (varsayılan kapalı), E4 son N oturumla aynı koltuğa düşmeme, E5 aynı-şube ayrıştırma (kapalı; ADR-0044 karar 11'de V1'de YAPILMADI teyidi).
- **Motor** (`engine.py`, Tur 225): iki fazlı — kurucu round-robin (gruplar büyükten küçüğe, salon kotaları en-büyük-kalan `_room_quotas`) + yerel arama (ikili takas + boş-koltuğa-taşınma; `random.Random(seed)`, sabit iterasyon bütçesi). Skor `ceza = Σ 1/d²` (Öklid); iç aramada 1. halkaya +10 ağır ceza; önceki-oturum tekrarına +5 yumuşak ceza (Tur 226). **Aynı seed → aynı sonuç; "Yeniden Dağıt" = yeni seed.** Kritik tuzak (Tur 223/225 belgeli): komşuluk denetimi S-rotasından DEĞİL 2D geometriden; bitişik-masa denetimi mesafeden DEĞİL `(desk_row, desk_col)` kimliğinden (hücre-içi koltuk ofsetleri komşu sıralarla çakışabilir).
- **Bağımsız doğrulayıcı** (`validator.py`): motordan HİÇBİR ŞEY import etmez, sert kısıtları O(n²) sıfırdan denetler + R8 mesafe metriklerini üretir (grup başı min aynı-grup mesafesi, 1. halka çift sayısı, saf Σ 1/d² skoru; Tur 645 ekleri: `section_label`, `cross_group_same_section_first_ring_pairs`, `room_counts`). Test omurgası budur: 110 rastgele senaryoda sert ihlal=0, skor regresyon eşiği ≤24.0.
- **Kenar durumlar:** tek-grup/tam-doluluk matematiksel ihlalsizlik imkânsız → kapasite ≥ ~2× öğrenci ise **satranç düzeni** önerilir, değilse minimizasyon + açık ihlal listesi; baskın grup (> salon yarısı) → en iyi skor + uyarı; kapasite < öğrenci → dağıtım reddi; üçlü sıranın orta koltuğu iki kenarlı komşuluk. Pin varken satranç devre dışı (pin > satranç).
- **K3 — düzen oturum düzeyinde:** `layout_mode ∈ {BUTTERFLY, HOME_CLASSROOM}`. Klasik düzende de `SeatAssignment` üretilir (salon = `ExamRoom.linked_section` eşlemeli derslik, koltuk = okul no sırası; `distribute_home_classroom`) — yoklama/soru kağıdı/tutanak TEK altyapıdan. Klasikte ayrışma kısıtı uygulanmaz (`enforce_group_separation` politikası), bütünlük denetimi (çifte koltuk/öğrenci) her düzende çalışır.
- **K2 — gözetmen opsiyonel, varsayılan kapalı.** Tur 235: SALON BAŞKANI (CHIEF) rolü KALDIRILDI — okul içi sınavda salon başına TEK gözetmen (DB kısıtı `uq_proctor_session_room_proctor_alive`) + 5 salona 1 nöbetçi yedek. Tur 242: oto-atama BUTONU kalktı (ders programı verisi olmadan rastgele öneri hatalıydı) — salon başına aranabilir seçici; `auto_assign_proctors` servisi silinmedi (program verisi bağlanınca yeniden açılacak). Tur 459: `program.teachers_free_at` + `gorevlendirme.absent_staff_ids` köprüleri bağlandı.
- **K4-K5 — soru kağıdı:** WeasyPrint overlay + pypdf (ReportLab REDDEDİLDİ — yeni bağımlılık + ikinci PDF yolu + font gömme işi). Tur 227: overlay salon başına TEK render (performans anahtarı; 90×4 sayfa < 30 sn test edildi). **Tur 236 (kullanıcı kararı): ölçekleme TAMAMEN KALKTI** — sabit 4 cm üst başlık alanı (`.band`: top 4mm + height 32mm, overflow hidden, invariant ≤ 40mm) + stdlib zipfile ile üretilen 4 cm marjlı Word soru şablonu (`word_template.py`; python-docx bilinçli eklenmedi). Tur 646: bant üç-bölgeli modern düzen (sol kurum kimliği "T.C. · il · ilçe", orta alt-çizgili öğrenci alanları + soru-tablolu modda S1..Sn+TOPLAM, sağ 24×16mm çift çerçeveli PUAN kutusu; salt siyah, tablo düzeni) + yükleme doğrulaması: her sayfa A4 dikey ±6pt, /Rotate normalize, yatay sayfa Türkçe hatayla RED.
- **PlacementRule (Tur 226):** KENDI_DERSLIGINDE (kelebeği deler) / BELIRLI_SALON / ON_SIRA / AYRI_SALON (hedef salonu kelebekten çıkarır); kapsam SESSION > PERMANENT; `reason_category ∈ {DISABILITY, IEP, HEALTH, OTHER}` YALNIZ kategori (özel nitelikli veri işareti — tanı/rapor detayı asla).
- **Durum makinesi (Tur 229):** TASLAK→DAĞITILDI→ONAYLANDI (yalnız sert ihlal=0 ise) →DAĞITILDI (reopen) →ARŞİV (geri dönüşsüz, salt-okunur + yeniden basım açık). Onaylı oturuma SESSION kuralı eklenemez; yeniden dağıtım gözetmen atamalarını sıfırlar.
- **Tur 241 (kritik düzeltme):** `ExamSessionCourse` TEK seviyeli oldu (`level` alanı; "Matematik—9" ve "Matematik—10" ayrı satır); kitapçık doc sözlüğü `course_id` yerine grup anahtarıyla kurulur — eski anahtar aynı dersin iki seviyesini SESSİZCE EZİYORDU (tek PDF basardı).
- **Tur 243:** Faz 0 şube-hizalı paketleme (`_group_room_quotas` + `_pack_section_chunks` first-fit-decreasing) — şube başına salon sayısı 4-6'dan 1-2'ye; determinizm korunur (yeni kademelerde rng yok), `rooms_per_section` metriği R8'e akar.
- **Tur 245 — ExamAttendanceRecord:** sınava GİRMEYEN kaydı + mazeret durumu (Beklemede/Özürlü/Özürsüz) + not (belge no/tarih; sağlık tanısı yazılmaz uyarısı help_text'te). İşaretleme yalnız ONAYLI/ARŞİV oturumda; mazeret güncellemesi ARŞİVDE DE açık (Yön. md. 5(y): veli 5 iş günü penceresi).
- **Frontend deseni:** tıkla-yerleştir salon editörü (DnD kütüphanesi REDDEDİLDİ — erişilebilirlik + bağımlılık), tıkla-seç-tıkla koltuk takası (`swap_seats` üç aşamalı yazım), 5 adımlı sihirbaz (Adım 0 nakil ön kontrol onayı zorunlu — kim/ne zaman oturuma yazılır), numaralandırma önizlemesi İSTEMCİDE HESAPLANMAZ (`preview_room_seats` backend ucu — iş kuralı tek yerde).

### 1.2 ADR-0044 (Tur 638-648) — sınav takvimi + süreç takibi
- Excel kaynağı: `data/raw/Sınav Takip.xlsx` (satır=tarih+ders saati, sütun=seviye, hücre=ders + basım süreci durumu + "Kelebek Değil" bayrağı).
- Modeller: `ExamCalendar` (yıl+dönem+tur; DRAFT→SUBMITTED→APPROVED), `ExamCalendarEntry` (ders+seviye+tür WRITTEN|PRACTICE + `is_butterfly` + placed_date⇔period_no Check + session SET_NULL), `ExamTrackItem` (GLOBAL süreç kataloğu; 8 varsayılan kalem seed), `ExamTrackMark` (DONE/NOT_APPLICABLE; "yapılmadı"=kayıt yokluğu). Dördü de `kvkk_personal_data=False`.
- Karar 4: `generate_default_calendars` — Yönet. md. 5/1-ç pencerelerini dönem tarihlerinden hesaplar (`statutory_window`: son Pazartesi + 11 gün); tamamı elle düzenlenebilir; tur 3 → dönemin son iki haftası, elle.
- Karar 5: onay akışı — MUDUR_YARDIMCISI hazırlar+sunar, ONAYLAMAZ; approve {ADMIN, MUDUR} (dört göz + müdürün resmî tasarrufu). Havuz/yerleştirme yalnız DRAFT'ta.
- Karar 6: ızgara SEVİYE bazlı (9/10/11/12 + Hazırlık); alan (Say/EA/Dil) alt sütunu YOK (kullanıcı kararı); kısmi kapsam hücre dipnotu `ders_yapisi` grup kapsamından.
- Karar 7 (Tur 641): onaylı takvimde slot→DRAFT `ExamSession` üretimi (`create_session_from_slot`; saat zil çizelgesinden, salonlar `section_rooms_for_levels` ön-seçili; "Kelebek Değil" girdiler hariç; oturum silinirse bağ çözülür, yeniden üretilebilir).
- Karar 8 (Tur 640): resmî PDF `documents/base.html` + `.sig-grid` tablo imza; imzalar `apps.zumre.services.chairs_for_courses` + `school_chair` (apps.is_installed korumalı — zumre yoksa boş imza çizgisi, zarif bozulma); onaysızda "TASLAK" filigranı; `DEFAULT_CALENDAR_DESCRIPTION` mevzuat-dayanaklı metin; A4 YATAY (Tur 644); PDF SENSITIVE_READ.
- Karar 10 (Tur 637/644): ExamRoom'a `exam_excluded` bayrağı AÇILMAZ — filtre türetilmiştir (seviye kesişimi + is_active + sihirbazda elle çıkarma); kalıcı bayrak iki doğruluk kaynağı yaratır ve bayatlar. `generate_section_rooms` idempotent (linked_section VEYA ad çakışması → atlanır), öğrencisiz şubeye de 40 koltuklu (5×4 ikili sıra) salon üretir.
- Karar 11 (Tur 645): kelebek kriter denetimi — motor DOKUNULMADI; dört kullanıcı kriteri (seviye/ders/aynı-şube ayrımı + denge) kodda karşılanıyor; tek açık uç GROUPS-tipi farklı-grup komşuluğu (farklı kitapçık — düşük risk). Yalnız gözlemlenebilirlik eklendi (salon doluluk + >20 puan fark uyarısı).
- Karar 12 (Tur 647): havuz `ders_yapisi.LessonGroup`'tan otomatik dolar (timetable DEĞİL — programa yerleşmemiş grup da okutulur); `taught_course_levels(yıl)` distinct (ders, seviye); kapsam kulüp hariç MANDATORY+ELECTIVE, varsayılan YAZILI+kelebek; round 3 elle (servis reddi + FE gizli); katalog uyumsuzluğu `skipped` listesinde nedenli raporlanır, sessizce düşmez.
- Karar 13 (Tur 648): **günlük sınav limiti ÖĞRENCİ-bazlı** — seviye-bazlı ham sayım seçmeli/grup derslerinde yanlış pozitif üretiyordu. `_daily_exam_load` her dersin öğrenci kümesini `ders_yapisi.course_level_student_ids` (aktif LessonEnrollment id'leri, PII yok, bellekte) ile alır; eşik "öğrenci başına en yüksek günlük sınav": 3 → uyarı + etkilenen öğrenci sayısı, ≥4 → sert hata. Kayıt verisi olmayan ders seviyenin TAMAMINI kapsar sayılır (konservatif). Sınır: hesap (seviye, gün) kovası içi; çapraz-seviye birleşimi V2.
- Tur 644 denetim dersi: `entries` GET action'ı aynı url_path'li POST tarafından gölgelenip HER ZAMAN 405 dönüyordu (Havuz listesi hiç çalışmamıştı) — tek action'da GET+POST birleştirildi. Not sözleşmesi: gövdede `note` anahtarı yoksa mevcut not korunur; temizleme açık `note=""`.

### 1.3 Rapor tasarım standardı "Kurumsal Sade" (Tur 238-239, `docs/rapor-tasarim-standardi.md`)
- Tek doğruluk kaynağı `backend/templates/print/_design.css`; `var(--pr-*)` token'ları (WeasyPrint 63 destekli): `--pr-ink #0f172a`, `--pr-text #1e293b`, `--pr-secondary #475569`, `--pr-line #cbd5e1`, `--pr-fill-head #f1f5f9`; boyutlar `--pr-size-school 11.5pt` … `--pr-size-footer 7.5pt`; çizgiler `--pr-rule-strong 1.4pt`, `--pr-border 0.5pt`, `--pr-border-outer 0.9pt`.
- Bağlayıcı yasaklar: ❌ `text-transform` (WeasyPrint Türkçe i→I tuzağı — büyük harf doğrudan yazılır / Python `tr_upper`), ❌ renkli dolgu, ❌ zebra satır, ❌ DejaVu Sans dışı font, ❌ token dışı renk. @page margin kutularında `var()` çözülmeyebilir → altbilgi LİTERAL değer. Altbilgi düzeni: sol üretim zamanı · orta "Sayfa x / y" · sağ bağlam.
- Sınav evrakı base'i `apps/sinav_islemleri/templates/sinav_islemleri/reports/base.html`; `documents/base.html`'i extend ETMEZ (resmî yazışma ≠ evrak anatomisi). Kitapçık bandı `booklet_overlay.html` kapsam DIŞI (saf siyah, fotokopi güvenli).
- WeasyPrint TR-locale tuzağı (Tur 244/645): ondalık yüzdeler virgülle basılır → CSS geçersiz; `{% load l10n %}` + `|unlocalize` zorunlu.

### 1.4 Bağımlılık yönleri (MODULES.md satır 1656-1674)
`sinav_islemleri → core, bildirim, denetim, ders_yapisi (Course string-FK + servis köprüsü), gorevlendirme (servis*), program (servis*), zumre (servis*, apps.is_installed korumalı)`. `ders_yapisi` core gibi taban modüldür (string-label FK hedefi olabilir). Zümre açık arayüzü: `chairs_for_courses(course_ids, school_year_id) -> dict[int, ChairInfo]`, `school_chair`, `courses_for_chair`; `chair_full_name == ""` → boş imza çizgisi basılır.

## 2. Üretilmesi gereken resmî evrak listesi ve dayanakları

| Kod | Evrak | Dayanak / not |
|---|---|---|
| R1 | Salon Oturma Planı (kroki) | Dönemlik ODSGM/İl MEM kılavuzları (korpusta YOK); geometri grid kimliğinden, kapı/tahta/masa konumlu |
| R2 | Salon Yoklama/İmza Listesi | Kılavuz kaynaklı: oturma sıralı, imza sütunu, "Sınava Girmedi", evrak sayım satırı |
| R2k | Şube Yoklama Listesi (klasik) | Okul no sıralı, aynı yapı |
| R3 | Salon Kapı Listesi | Ad/no/şube/koltuk — TCKN ASLA |
| R4 | Şube Duyuru Listesi | Öğrenci→salon→koltuk |
| R5 | Toplu Dağıtım Çizelgesi (Excel, openpyxl) | İdare çalışma kopyası |
| R6 | Gözetmen Görevlendirme + Tebliğ-Tebellüğ | OKY müdür onayı/imza karşılığı tebliğ pratiği; yalnız gözetmen modülü açıkken; "UYGUNDUR" müdür bloku |
| R7 | Sınav Evrak Zarfı Kapağı / Salon Tutanağı | Yönet. md. 17(ç), Yön. md. 6(i) evrak düzeni; kayıtlı sayı basılı, giren/girmeyen elle, içerik kontrol kutuları |
| R8 | Dağıtım Doğrulama Raporu | İhlal=0 beyanı + bağımsız doğrulayıcı metrikleri + seed/parametreler + salon doluluk tablosu (Tur 645) + komisyon/müdür imzası |
| R9 | Evrak Teslim/Teslim Alma Tutanağı | Tur 240'tan beri TEK tablo (öncesi/sonrası imzalar yan yana); gözetmen kapalıysa ad elle |
| R10 | Kişiselleştirilmiş Soru Kitapçıkları | Salon paketi oturma sıralı, isimsiz yedek kopya; >2 sayfada başlık tek numaralı sayfalarda, her sayfada "Sayfa x/y" |
| — | Boş Salon Yerleşim Planı PDF (Tur 244, `room_layout.html`) | Oturumdan bağımsız, kapıya asılır; kişisel veri yok |
| — | Sınav Takvimi resmî PDF (Tur 640, `calendar_pdf.html`) | Yönet. md. 5/1-ç ilan yükümlülüğü; branş zümre başkanları + okul zümre başkanı imzaları + müdür UYGUNDUR; A4 yatay; TASLAK filigranı |
| — | Word soru şablonu (.docx, Tur 236/646) | 4 cm üst marj + 6 kurallık yönerge; stdlib zipfile ile üretilir |

Ek: ZIP paketi (R1-R9; R6 koşullu), tümü DejaVu Sans + Kurumsal Sade.

## 3. Planlama kuralları (mevzuat, madde numaralarıyla)

**Ölçme ve Değerlendirme Yönetmeliği (09.09.2023, RG 32304):**
- md. 3(ö): ortak yazılı sınav tanımı — birden fazla şubeye yönelik.
- md. 4(ç): BEP esas alınır; md. 4(d): güvenirlik-gizlilik-tarafsızlık; md. 4(e): aynı/farklı sorularla, aynı/farklı zamanda uygulanabilir.
- md. 5/1-b: ilçe/il/ülke ortak sınavları MEM yürütür; md. 5/1-c: dönemde her dersten İKİ yazılı; haftalık ≥6 saat derste il zümre kararıyla ÜÇÜNCÜ sınav.
- **md. 5/1-ç (takvim pencereleri):** 1D1S Ekim son–Kasım ilk hafta; 1D2S Aralık son–Ocak ilk; 2D1S Mart son–Nisan ilk; 2D2S Mayıs son–Haziran ilk. Tarihler öğretim yılı başında e-Okul'dan ilan; mücbir sebeple il MEM değiştirir. Mesleki yoğunlaştırılmış/işletmeli sınıflar istisna.
- md. 5/1-d: birden fazla şubede okutulan derslerin sınavlarının ORTAK yapılması esas; şube/sınıf bazlı analiz.
- **md. 5/1-k: bir sınıfta bir günde en fazla 2 yazılı+uygulamalı sınav; zorunlu hâlde bir fazla** (uygulama: 3.→uyarı, ≥4→sert hata, ADR-0044 karar 13).
- **md. 5/1-l: yazılı sınav süresi bir ders saatini aşamaz** (zorunlu hâller ve merkezî sınavlar hariç) — modülde varsayılan süre 40 dk (Tur 240, kullanıcı kararı).
- md. 5/1-f: KSD tablosu il zümre + ÖDM ile; md. 6/1-a-e: ortak yazılı karar/ilan/soru hazırlama mercileri; md. 17(ç): baskı-sevk-uygulama-değerlendirme (İl ÖDM görevleri).

**Yazılı ve Uygulamalı Sınavlar Yönergesi (11.10.2023):**
- md. 4(l): ortak yazılı tanımı; md. 4(j): mazeret sınavı tanımı.
- md. 5/1-b: okul geneli ortak sınav iş ve işlemleri OKUL MÜDÜRLÜKLERİNCE yürütülür; md. 5/1-ç: okul geneli tarihleri okul müdürlüğü duyurur, e-Okula giriş okul müdürlüğü sorumluluğu.
- md. 5/1-m: sorular KSD tablosuna göre; md. 5/1-n: okul geneli soru/cevap anahtarı eğitim kurumu sınıf/alan zümrelerince; md. 5/1-o-p: uygulama ve değerlendirme zümrelerce.
- **md. 5/1-s: ülke/il/ilçe ortak sınav tarihlerinde başka sınav yapılmaz; bir günde en fazla 2 (zorunlu hâlde +1); zorunlu hâl tespiti okul müdürlüğü sorumluluğu.** md. 5/1-ş: sınav gün/saatlerinde eğitime devam edilir.
- md. 5/1-u: BEP öğrencilerinin ortak sınav katılım sürecinden okul müdürlüğü sorumlu; md. 5/1-ü: katılmayanlar sınav bitiminde e-Okula işlenir.
- md. 5/1-v: NAKİL — önceki okulda girmediyse yeni okulda girer; sınav geçtiyse mazeret sınavına (sihirbaz Adım 0 nakil ön kontrolünün dayanağı).
- **md. 5/1-y: mazeret gerekçesi sınav tarihinden itibaren en geç 5 İŞ GÜNÜ içinde veliden yazılı** (Tur 245 ExamAttendanceRecord'un arşivde açık kalma gerekçesi); md. 5/1-z-aa-bb-cc: mazeret sınavı mercileri (okul geneli → okul müdürlüğü + kurum zümreleri); md. 5/1-çç: mazeretin mazereti yok — "katılmamış" sayılır.
- md. 6/1-a: 100 puan üzerinden; md. 6/1-f: girmeyen "G", kopya "K" — ortalamaya dâhil; md. 6/1-ğ-h: soru itirazı 3 iş günü / sonuç itirazı 3 iş günü, okul geneli için okul müdürlüğü cevaplar; md. 6/1-i: cevap kâğıtları okulda muhafaza.

**Korpusta OLMAYANLAR (dönemlik ODSGM/İl MEM kılavuz kaynaklı — her dönem teyit):** kelebek düzeni, S-numaralandırma, imzalı salon yoklama biçimi, "Sınava Girmedi" işaretleme biçimi, evrakın oturma sırasına paketlenmesi, arşiv SÜRESİ, sınav komisyonu kuruluşu. Modül ilkesi: "kılavuz uyumlu varsayılan, ayarla değiştirilebilir."

## 4. Masaüstü portta korunması gereken mevzuat invariantları

1. Günlük limit ÖĞRENCİ-bazlı ölçülür (3→uyarı, ≥4→hata); veri eksikken konservatif (ders seviyenin tamamını kapsar sayılır).
2. Takvim pencereleri md. 5/1-ç'den otomatik hesap + elle düzenlenebilir; dönemde 2 sınav varsayılan, 3. tur elle.
3. Onay = müdürün resmî tasarrufu: hazırlayan onaylayamaz (tek kullanıcılı uygulamada UI'da ayrı "onay" adımı olarak korunmalı — dört göz yerine bilinçli onay damgası kim/ne zaman).
4. Oturum onayı yalnız sert ihlal=0 ise; onaylı/arşiv kilidi; arşivden yeniden basım; snapshot alanları (SeatAssignment ad/no/şube) sayesinde sicil değişse de evrak sabit.
5. Bağımsız doğrulayıcı + R8 "ihlal=0 beyanı" — motor değişse bile denetim bağımsız kalır; aynı seed → aynı çıktı (determinizm).
6. Nakil ön kontrolü (Yön. md. 5/1-v) dağıtım öncesi zorunlu onay adımı.
7. Mazeret durumu güncellemesi arşivde de açık (5 iş günü penceresi, md. 5/1-y).
8. Çıktılarda TCKN/fotoğraf ASLA; gerekçeler yalnız kategori (ENGEL/BEP/SAĞLIK/DİĞER); hata/uyarı metinlerinde öğrenci adı yok (no/id kullanılır).
9. Baskı standardı: DejaVu Sans gömülü, text-transform yasak, |unlocalize (TR ondalık), gri tonlamalı, zebra yok.
10. Kitapçık: 4 cm bant invariantı (top 4mm + height 32mm ≤ 40mm), ölçekleme YOK, A4 dikey doğrulama, >2 sayfada tek-numaralı sayfalarda başlık, her sayfada Sayfa x/y, salon paketi oturma sıralı.
11. Sınav süresi varsayılanı 40 dk (md. 5/1-l bir ders saati sınırı bağlamında).
12. Kılavuz-kaynaklı operasyonel kurallar (S düzeni, yoklama biçimi) yapılandırılabilir varsayılan olarak tutulur.

## 5. Port değerlendirmesi (AYNEN / UYARLA / ALMA)

**AYNEN taşınabilir (saf Python, Django'ya minimal bağımlı):** `engine.py` (iki fazlı motor — stdlib random/math), `validator.py` (tam izole), `layout.py` (plan şema doğrulama + S/düz numaralandırma + kapasite — saf fonksiyonlar), `booklet.py` çekirdeği (WeasyPrint+pypdf; SQLite'ta da çalışır), `word_template.py` (stdlib zipfile), `reports.py` saf bağlam kurucular, `_design.css` + rapor şablonları (WeasyPrint), `catalog_parser` + `data/ders-cizelgeleri/anadolu-lisesi-2025-2026.md` (62 ders: 17 ortak + 45 seçmeli, Hazırlık=0 seviyesi), `_daily_exam_load` mantığı, `statutory_window` pencere hesabı, `default_section_plan` (40 koltuk 5×4 ikili sıra).

**UYARLANMALI:** (a) Celery async kitapçık üretimi → tek kullanıcıda senkron/thread (SavedReportRun durum deseni sadeleşir); (b) RBAC/SENSITIVE_READ/AccessLog → girişsiz tek kullanıcıda kalkar, ama onay damgaları (kim yerine "ne zaman") ve durum makinesi kalır; (c) core köprüsü (Student/Section/SectionGroup) → yerel SQLite sicil tablolarına iner — katılımcı çözümleyici `participants.py` arayüzü korunarak; (d) zümre imza köprüsü → basit yerel "branş → başkan adı" tablosu (zarif bozulma deseni korunur: ad yoksa boş çizgi); (e) `ders_yapisi.LessonGroup/LessonEnrollment` → basitleştirilmiş ders-grubu/kayıt modeli (btree_gist ExclusionConstraint PostgreSQL'e özgü — SQLite'ta servis katmanı denetimine çevrilir); (f) X-Accel-Redirect dosya sunumu → doğrudan dosya sistemi; (g) OpenAPI şema/regen zinciri → gereksiz.

**ALINMAMALI:** bildirim sinyalleri/EventType, e-Okul PDF importu, kiosk/SMS/OAuth katmanları, Docker/LAN yapılandırması, drf-spectacular şema sözleşmesi (Tur 840-845 izleği), kvkk_export/denetim modülü (tek kullanıcı-yerel veri), React Query sunucu-durumu katmanının çok kullanıcılı varsayımları.

## key_facts
- Çakışma birimi (K7): (course, level) çifti = aynı soru kitapçığı; shared_booklet → '<cid>:*' tek grup; şube kısıt DEĞİL — motor yalnız grup anahtarlarını görür (participants.py üretir)
- Sert kısıt (K8): aynı gruptan iki öğrenci aynı masada bitişik oturamaz; katı mod 1. halkayı (Chebyshev ≤1 komşu sıra) serte çevirir; bitişiklik denetimi (desk_row, desk_col) KİMLİĞİNDEN, mesafeden değil (koordinat çakışması tuzağı, Tur 223)
- Motor iki fazlı + deterministik: kurucu round-robin (en-büyük-kalan salon kotaları) + random.Random(seed) yerel arama; skor Σ 1/d² + 1.halka +10 + önceki-oturum +5; aynı seed → aynı sonuç; 110 rastgele senaryoda ihlal=0 test omurgası
- validator.py motordan TAM BAĞIMSIZ (hiçbir import yok), sert kısıtları O(n²) sıfırdan denetler + R8 metrikleri üretir; oturum onayı yalnız ihlal=0 ise — bu çift-denetim portta korunmalı
- Tur 243 Faz 0: _group_room_quotas + _pack_section_chunks (FFD) ile şubeler salonlara BÜTÜN paketlenir — şube başına 1-2 salon; rng'siz deterministik
- Klasik düzen (HOME_CLASSROOM) aynı SeatAssignment altyapısını kullanır: salon = ExamRoom.linked_section dersliği, koltuk = okul no sırası; ayrışma kısıtı uygulanmaz — yoklama/kitapçık/tutanak tek altyapıdan
- Kenar durumlar: tek-grup tam dolulukta satranç düzeni önerisi (kapasite ≥ ~2×), baskın grup uyarısı, kapasite yetersiz → red; pin varken satranç devre dışı
- PlacementRule: KENDI_DERSLIGINDE (kelebeği deler) / BELIRLI_SALON / ON_SIRA / AYRI_SALON; SESSION > PERMANENT; gerekçe YALNIZ kategori (ENGEL/BEP/SAĞLIK/DİĞER) — tanı detayı asla
- Kitapçık: ölçekleme YOK (Tur 236) — sabit 4cm bant (top 4mm + height 32mm ≤ 40mm invariantı); üç-bölgeli bant (Tur 646: kurum kimliği / alt-çizgili öğrenci alanları / 24×16mm çift çerçeveli PUAN); A4 dikey ±6pt yükleme doğrulaması; Word şablonu stdlib zipfile ile üretilir
- Kitapçık sayfa kuralları: ≤2 sayfa → başlık yalnız 1.'de; >2 → tek numaralı sayfalarda; her sayfada 'Sayfa x/y'; salon paketi oturma sırasında; WeasyPrint overlay SALON BAŞINA TEK render (90×4 sayfa <30sn); pypdf ile bindirme; ReportLab REDDEDİLDİ
- Durum makinesi: TASLAK→DAĞITILDI→ONAYLANDI(ihlal=0 şart)→reopen/ARŞİV(salt-okunur+yeniden basım); yeniden dağıtım gözetmen atamalarını sıfırlar; SeatAssignment ad/no/şube SNAPSHOT — arşiv evrakı sicil değişse de sabit
- Evrak seti: R1 kroki, R2/R2k yoklama-imza, R3 kapı, R4 duyuru, R5 Excel çizelge, R6 gözetmen tebliğ (koşullu), R7 zarf kapağı/tutanak, R8 doğrulama raporu, R9 tek-tablolu teslim tutanağı, R10 kitapçıklar + boş salon planı PDF + takvim resmî PDF + Word şablonu + ZIP
- Kurumsal Sade standardı: templates/print/_design.css --pr-* token'ları; DejaVu Sans; YASAK: text-transform (TR i→I tuzağı), zebra, renkli dolgu, token-dışı renk; @page footer'da literal renk; |unlocalize zorunlu (TR ondalık virgül CSS'i bozar)
- Günlük sınav limiti ÖĞRENCİ-bazlı (ADR-0044 karar 13): ders_yapisi.course_level_student_ids ile öğrenci kümesi kesişimi; 3.sınav→uyarı+etkilenen sayısı, ≥4→sert hata; kayıt verisi olmayan ders seviyenin tamamını kapsar (konservatif). Mevzuat: Yönet. md.5/1-k + Yön. md.5/1-s
- Takvim pencereleri (Yönet. md.5/1-ç): 1D1S Ekim son–Kasım ilk; 1D2S Aralık son–Ocak ilk; 2D1S Mart son–Nisan ilk; 2D2S Mayıs son–Haziran ilk; generate_default_calendars otomatik hesaplar (statutory_window), elle düzenlenebilir; dönemde 2 sınav, ≥6 saatlik derste il zümre kararıyla 3. (md.5/1-c)
- Takvim akışı: ExamCalendar DRAFT→SUBMITTED→APPROVED; hazırlayan onaylayamaz (müdürün resmî tasarrufu); havuz LessonGroup'tan otomatik dolar (kulüp hariç, round 3 elle); onaylı slottan tek tıkla DRAFT ExamSession (kelebek-değil girdiler hariç); PDF imzaları zümre köprüsünden zarif bozulmalı
- Sınav süresi: varsayılan 40 dk (Tur 240 kullanıcı kararı); mevzuat tavanı bir ders saati (Yönet. md.5/1-l)
- Nakil ön kontrolü sihirbaz Adım 0'da zorunlu onay (Yön. md.5/1-v: nakil öğrenci sınav durumu); mazeret bildirimi 5 iş günü (Yön. md.5/1-y) → ExamAttendanceRecord mazeret güncellemesi ARŞİVDE DE açık; girmeyen 'G', kopya 'K' ortalamaya dâhil (Yön. md.6/1-f)
- Kelebek düzeni/S-numaralandırma/yoklama biçimi/paketleme MEVZUATTA YOK — dönemlik ODSGM/İl MEM kılavuzlarından; 'kılavuz uyumlu varsayılan, ayarla değiştirilebilir' ilkesi (data/mevzuat-notlari/sinav-modulu-mevzuat-teyidi-2026-06-11.md)
- Gözetmen: opsiyonel, varsayılan kapalı; salon başına TEK gözetmen + 5 salona 1 yedek (CHIEF rolü Tur 235'te kaldırıldı); oto-atama UI'dan kalktı (Tur 242 — ders programı verisi olmadan yanlış kişi seçiyordu), listeden seçim; R6 tebliğ-tebellüğ + müdür UYGUNDUR
- Aynen taşınabilir saf çekirdek: engine.py, validator.py, layout.py (S/düz numaralandırma + plan şeması + kapasite plandan türetme), booklet.py, word_template.py, reports.py kurucular, catalog_parser + anadolu-lisesi-2025-2026.md (62 ders, Hazırlık=0), _design.css + rapor şablonları, statutory_window, _daily_exam_load, default_section_plan (40 koltuk 5×4)
- Uyarlanacaklar: Celery→senkron, RBAC/SENSITIVE_READ→kalkar ama onay damgaları+kilit kalır, core/ders_yapisi/zumre köprüleri→yerel SQLite tabloları (arayüz korunarak), btree_gist ExclusionConstraint→servis katmanı denetimi (SQLite'ta yok), X-Accel-Redirect→doğrudan dosya
- Frontend desenleri: tıkla-yerleştir salon editörü (DnD yok — bilinçli), tıkla-seç-tıkla koltuk takası (swap_seats üç aşamalı yazım), 5 adımlı sihirbaz, numaralandırma önizlemesi backend'de (preview_room_seats — iş kuralı tek yerde), çakışma grupları renk kodlu kroki
- Tur 241 kritik ders: ExamSessionCourse TEK seviyeli; kitapçık sözlüğü course_id yerine grup anahtarıyla — eski anahtar aynı dersin iki seviyesini sessizce eziyordu (portta baştan tek-seviyeli kurulmalı)
- Tur 644 dersi: aynı url_path'li GET/POST action gölgelenmesi (entries hep 405 dönüyordu) — DRF action tasarımında GET+POST tek action'da birleştirilir; not sözleşmesi: gövdede anahtar yoksa koru, temizleme açık boş string

## riskler
- Kelebek düzeni, S-numaralandırma, yoklama listesi biçimi ve evrak paketleme kanonik mevzuatta YOK — dönemlik ODSGM/İl MEM kılavuzlarından gelir; her dönem teyit gerekir, portta bu kurallar sabit kod değil yapılandırılabilir varsayılan olmalı
- Tek-grup/tam-doluluk senaryosunda matematiksel ihlalsizlik imkânsız — satranç önerisi + açık ihlal listesi UI'da mutlaka gösterilmeli; sessiz onay mevzuat riskı
- SQLite portunda PostgreSQL'e özgü yapılar (btree_gist ExclusionConstraint, kısmi/canlı-koşullu unique kısıtlar) birebir çevrilemez — canlı-tekillik SQLite partial index (WHERE deleted_at IS NULL) veya servis denetimiyle yeniden kurulmalı; atlanırsa çift kayıt sessizce oluşur
- Günlük limit denetimi ders-kayıt (LessonEnrollment) verisine muhtaç; masaüstü uygulamada bu veri girilmezse konservatif mod her dersi seviye-geneli sayar ve seçmeli derslerde yanlış pozitif uyarılar geri gelir (Tur 648 öncesi davranış)
- WeasyPrint tuzakları platform bağımsız taşınır: text-transform Türkçe i→I, TR-locale ondalık virgül (|unlocalize), @page margin kutusunda var() çözülmemesi — şablonlar kopyalanırken bu üç kural korunmazsa çıktı sessizce bozulur
- Tek kullanıcılı uygulamada 'hazırlayan onaylayamaz' dört-göz ilkesi fiziksel olarak sağlanamaz — onay ayrı, bilinçli bir UI adımı + zaman damgası olarak korunmalı; aksi hâlde takvim/oturum kilidi anlamını yitirir
- Kitapçık motoru eski yüklenen dar-marjlı PDF'lerde bant içeriğe binebilir (ölçekleme kalktığı için); A4/yön doğrulaması porta alınmazsa basım hatası sahada görülür
- Determinizm sözleşmesi kırılgan: motorun herhangi bir fazına dokunuş aynı seed'in çıktısını değiştirir (Tur 243 emsali — davranış değişikliği bilinçli yönetildi); port sırasında motor 'DOKUNULMAZ' taşınmalı, testler (ihlal=0, skor eşiği, determinizm) birlikte taşınmalı
- Zümre imza köprüsü ve il/ilçe kimlik bilgisi OYS'de kurum yapılandırmasından geliyor — portta karşılığı kurulmazsa takvim PDF'i ve kitapçık bandı eksik/boş üretilir (zarif bozulma var ama resmî evrakta boş imza bloğu kullanıcıyı yanıltabilir)
- Excel çıktısı (R5) openpyxl'e, PDF'ler WeasyPrint+pypdf'e bağımlı — PyInstaller onedir paketlemede WeasyPrint'in GTK/Pango yerel kütüphaneleri Windows+Pardus'ta ayrıca paketlenmeli (disiplin-defteri şablonunda çözülmüş olmalı, doğrulanmadan varsayılmamalı — bu depoda görülmedi)
- Mevzuat metinleri 2023 tarihli; 2025-26 MEB duyurularıyla kelebek uygulaması değişebilir — takvim açıklama metni (DEFAULT_CALENDAR_DESCRIPTION) ve pencere hesabı güncellenebilir tutulmalı
- Arşiv saklama süresi mevzuatta tanımsız ('muhafaza altına alınır') — masaüstünde silme/anonimleştirme politikası kullanıcıya bırakılmalı, otomatik silme kurgulanmamalı


================================================================================
AJAN: kararlar
================================================================================

# GÖREV G — Kesim ve Karar Analizi (kelebek-sinav portu)

Kaynaklar: `C:\Users\aalid\.claude\apps\okulapp\backend\apps\sinav_islemleri\` (21 py dosyası, 9.358 satır; en büyükler services.py 2354, models.py 1121, services_calendar.py 1096, views.py 1077), `frontend\src\modules\sinav-islemleri\` (22 kaynak dosya ~6.300 satır), şablon depo `disiplin-defteri-codex` (desktop/ 15 dosya, packaging/ windows+linux+pyinstaller+veri_sizintisi.py).

Doğrulanmış kritik gerçek: **hiçbir başka app `sinav_islemleri`'nden import etmiyor** — tek dış referans `denetim/kvkk_media_scope.py`'daki string kayıtları (`"sinav_islemleri.BookletRun"`, `"sinav_islemleri.QuestionDocument"`). Modül temiz kesilebilir.

---

## 1) BAĞIMLILIK KESİM LİSTESİ

Her satır: OYS bağlanma noktası → tek kullanıcılı çevrimdışı karşılığı (DD deseniyle).

| # | Bağlanma noktası | Yer | Karar | Karşılık |
|---|---|---|---|---|
| B1 | DRF izinleri (CanManage*, rol denetimi) | `sinav_islemleri/permissions.py` (74 s), view'lardaki `permission_classes` | **KALDIR** | DD `settings.py` kalıbı: `AUTHENTICATION []`, `AllowAny`, `UNAUTHENTICATED_USER None`; yerel güvenlik = `desktop/session_guard.py` belirteci (?t= → HttpOnly çerez, fail-closed 403) |
| B2 | FE auth: `lib/api.ts` Bearer+401 refresh, `useAuth`/`hasAnyRole` (yalnız TakvimlerPage, TakvimDetayPage, TakvimTakipPaneli) | frontend | **KALDIR** | DD authsuz `lib/api.ts` (aynı `ApiError{status,code,message,fields}` sözleşmesi); `CAN_VIEW/CAN_APPROVE` bayrakları `true` sabitlenir |
| B3 | Celery: `tasks.py` (57 s) — generate_booklets + gece anonimleştirme | tasks.py | **SADELEŞTİR** | `services.generate_booklets_for_run` zaten senkron çağrılabilir (testler öyle yapıyor) → doğrudan çağrı; anonimleştirme → açılış denetimi + kullanıcı-onaylı bakım komutu. Celery/Redis pakete hiç girmez |
| B4 | Bildirim sinyali: takvim onayında bildirim modülüne `on_commit` (tek dış sinyal; `signals.py` boş) | services_calendar | **KALDIR** | Tek kullanıcı kendine bildirim göndermez; snackbar yeter |
| B5 | `gorevlendirme` köprüsü: `absent_staff_ids` (services.py:1380-1401) | gözetmen havuzu | **KALDIR** | Kod zaten köprü yoksa boş kümeye zarif düşüyor — dal silinir; havuz = aktif personel − muaf |
| B6 | `program` köprüsü: `teachers_free_at`, "Programdan Doldur", zil çizelgesi (`grid.periods`, saat fallback 08:00) | services, services_calendar, FE | **SADELEŞTİR** | Oto-atama zaten UI'dan kalkmıştı (Tur 242) → tamamen alma; oturum saati = serbest giriş + ayarlanabilir varsayılan saat listesi (mini yerel ayar) |
| B7 | `zumre` köprüsü: `apps.is_installed('apps.zumre')` korumalı imza satırları | takvim PDF | **KALDIR** | Modülsüz dal hazır: derslerden boş imza çizgileri basılır — o dal kalıcılaşır |
| B8 | `ders_yapisi` köprüsü: Course FK, `course_level_student_ids` / `course_level_coverage` / `taught_course_levels` (LessonGroup/Enrollment'a dayanır) | services.py:509-521, services_calendar._daily_exam_load | **YERELLEŞTİR** | Course yerel tablo olur (aynı alanlar, `db_table` bagajı atılır); öğrenci kümesi köprüsü → yerel öğrenci `(level, section)` kayıtlarından türetilir; kayıt verisi yoksa "seviyenin tamamı" konservatif düşüşü aynen korunur |
| B9 | `core` köprüsü: Student/Personnel/SchoolYear/SchoolConfig/`active_teachers()` | participants, gözetmen, sihirbaz | **YERELLEŞTİR** | DD çekirdeğinden: SchoolConfig(pk=1)+setup kapısı, Personnel, Student (guardian alanları atılır), ImportRun+parser'lar, SchoolYear |
| B10 | Öğrenci İşleri nakil ön-kontrolü (sihirbaz Adım 0 zorunlu onay, Yön. md.5/1-v) | SinavSihirbazi | **SADELEŞTİR** | Veri sorgusu yok → kullanıcı beyanlı onay kutusu; "kim/ne zaman onayladı" damgası korunur (SchoolConfig'deki ad ile) |
| B11 | AuditLog/denetim, `kvkk_scope`/`kvkk_media_scope` string kayıtları, SENSITIVE_READ | denetim app | **KALDIR** | Denetim app'i taşınmaz; KVKK yükümlülüğü yerelde F27 anonimleştirme + veri_sizintisi.py paket denetimiyle karşılanır |
| B12 | "Hazırlayan onaylayamaz" çift-kişi takvim kuralı (DRAFT→SUBMITTED→APPROVED) | services_calendar | **SADELEŞTİR** | Tek kullanıcıda çift kişi yok: SUBMITTED atlanır ya da tek tıkla geçilir; APPROVED kilidi ve onay tarihi damgası kalır (resmî evrak gereği) |
| B13 | Postgres: `levels__contains` (jsonb @>) süzme | ders_yapisi selectors | **UYARLA** | SQLite'ta contains lookup yok → Python süzme (~60 ders, bkz. Karar K11) |
| B14 | Postgres: DateRangeField, ExclusionConstraint, btree_gist (LessonGroup zinciri) | ders_yapisi migration 0003 | **ALMA** | Zaten porta girmeyen modellerde; migration ağacı sıfırdan 0001 yazılır |
| B15 | `select_for_update`, çok okul-yılı eşzamanlılık varsayımları | services | **SADELEŞTİR** | DD kabulü: tek yazar, no-op; SQLite WAL + `transaction_mode=IMMEDIATE` yeter |
| B16 | X-Accel-Redirect / medya sunumu | rapor indirme | **UYARLA** | Doğrudan `FileResponse` (DD deseni), FE `saveBlob` aynen |
| B17 | `BaseModel.created_by` (User FK) | tüm modeller | **UYARLA** | User modeli yok → alan düşer; soft-delete (`deleted_at` + koşullu unique) ve `updated_at` aynen korunur — SQLite kısmi index'i destekliyor (DD'de kanıtlı) |
| B18 | e-Okul/AI içe aktarma zinciri (eokul_importer.resolve_course, AI subject_canonical), PDF parser'lar | ders_yapisi, core | **ALMA (v1)** | İlk sürüm: DD şablon+pano+xlsx yolu; CourseAlias SEED dosyası (`ders-adi-takma-adlari.md`) yine taşınır çünkü xlsx'teki ders adları da MEB adına çözülmek zorunda |
| B19 | Celery polling (SorularPaneli 4 sn) | FE | **SADELEŞTİR** | Senkron üretim + tek istek; 90×4 sayfa <30 sn hedefi masaüstünde kabul edilebilir bekleme |

---

## 2) VERİLMESİ GEREKEN KARARLAR

**K1 — Kapsam.** Seçenekler: (a) yalnız kelebek dağıtım+evrak; (b) a + takvim planlama; (c) b + gözetmen. **Öneri: (c), ama fazlı** — oturum tarafı takvimsiz çalışıyor (iki alt sistem gevşek bağlı, slot→oturum köprüsü tek yönlü `create_session_from_slot`), takvim F6'ya, gözetmen F7'ye ertelenir. Gerekçe: takvim PDF'i + öğrenci-bazlı günlük limit denetimi mevzuat değeri taşıyor (Yönet. md.5/1-ç, OKY md.45), atılması ürünü yarım bırakır.

**K2 — Gözetmen ataması.** Seçenekler: alma / listeden elle seçim / oto-atama dahil. **Öneri: listeden elle seçim, ayarla açılır (varsayılan kapalı).** Gerekçe: oto-atama OYS'de bile ders programı verisi olmadan yanlış kişi seçtiği için UI'dan kaldırıldı (Tur 242); masaüstünde program verisi hiç yok. R6 tebliğ + salon başına 1 + 5 salona 1 yedek kuralı korunur.

**K3 — PDF motoru.** **Öneri: WeasyPrint 63.1 + pypdf 5.1.0 + openpyxl 3.1.5 (aynen).** Gerekçe: ReportLab OYS'de reddedilmiş; DD şablonunda fontconfig çift-düzeltmesi, DejaVu paketlemesi ve `--pdf-duman` (çıkış kodu 8, ĞÜŞİÖÇ doğrulaması) hazır — motor değişimi tüm rapor şablonlarını çöpe atar.

**K4 — Veri şifreleme.** Seçenekler: DD EncryptedCharField+uygulama parolası / düz SQLite. **Öneri: şifreleme ALMA.** Gerekçe: kelebek verisi ad+okul no+şube; TCKN, veli, sağlık verisi yok (PlacementRule gerekçesi bilinçle yalnız kategori — KVKK md.6 tasarımı zaten kodda). Bedel/fayda dengesiz (DD'de parola DB filtrelerini kırıp selector dolambacı gerektiriyordu, F5-D5 vakası). Karşılık: %LOCALAPPDATA% konumu, F27 anonimleştirme, veri_sizintisi.py. `backup.py` X25519'suz düz `Connection.backup()` snapshot'a uyarlanır — parolasız kipte günlük yedeğin atlandığı DD dalı kaldırılıp yedek her gün alınır.

**K5 — Ders havuzu kaynağı ve güncellemesi.** **Öneri:** MEB fixture md dosyaları (`anadolu-lisesi-2025-2026.md` 64 ders, çerçeveler, takma adlar) pakete gömülür; ilk açılışta `ensure_meb_catalog`+`ensure_course_aliases` tembel tohumu (idempotent, dosya yoksa sessiz — aynen). Güncelleme yolu = uygulama sürümüyle yeni md (CalVer) + UI'dan elle ders ekleme/pasifleştirme (`is_active` import'la geri açılmaz kuralı korunur). Diğer okul türleri v1'de md küratörlenmez; `VALID_COURSE_LEVELS=(0,9,10,11,12)` sabiti SchoolConfig'den türetilebilir hale getirilir ki ortaokul isteği gelirse kırılmasın.

**K6 — Python sürümü.** **Öneri: 3.12.** DD Linux build zinciri `python:3.12-bullseye` (glibc 2.31 = Pardus 21) üzerine kurulu; sapma tüm kap-içi-test hattını yeniden doğrulamayı gerektirir.

**K7 — Sürümleme.** **Öneri: CalVer + VERSION dosyası + `surum.json` DB damgası (dosya, tablo değil) + v* tag → GitHub Release + updates.py (depo adı env değişir).** DD'den birebir.

**K8 — Pencere düzeni.** **Öneri: tek pywebview penceresi, içeride React Router rotaları + panel sekmeleri (OYS FE düzeni zaten böyle: 7 lazy rota + oturum detayında sekmeler).** Çok pencere pywebview/waitress karmaşası getirir.

**K9 — Yedekleme.** **Öneri:** günlük açılış yedeği + rotasyon, `Connection.backup()` RAM görüntüsü (dosya kopyalama asla — WAL), migrate öncesi otomatik yedek; kimlik: `.ksbak` uzantı + yeni magic.

**K10 — Öğrenci verisi girişi.** **Öneri:** DD import boru hattı: `read_sheet/text_to_grid` → aynı rows matrisi (xlsx VE pano), dry-run/commit iki adım, sha256 idempotency uyarısı, fuzzy sütun eşleme, "boş hücre silmez" ilkesi. Veli alanları tamamen atılır; e-Okul PDF parser'ları v1'de alınmaz (pypdf glif/bitişme riskleri kodda belgeli). Kritik sütun kümesi: class + number + name (TCKN'siz — kelebek TCKN'ye hiç ihtiyaç duymuyor, hiç toplamamak en iyi KVKK önlemi).

**K11 — Course.levels SQLite'ta.** Seçenekler: CourseLevel ara tablosu / JSON + Python süzme. **Öneri: JSON + Python süzme.** Gerekçe: ~60 kayıt, tek kullanıcı, sorgu sayısı düşük; ara tablo migration+serializer maliyeti getirir. `normalize_levels`/`level_label` saf yardımcıları aynen.

**K12 — Günlük sınav limiti + takvim pencereleri.** **Öneri: al.** `statutory_window` (Ekim/Aralık/Mart/Mayıs son Pazartesi+11 gün) ve `_daily_exam_load` (öğrenci-bazlı, 3.=uyarı, ≥4=hata) mevzuat çekirdeği; tek uyarlama B8'deki veri kaynağı.

**K13 — Kitapçık (R10) + Word şablonu.** **Öneri: al, senkron.** booklet.py/word_template.py saf; A4 dikey ±6pt doğrulama, 4 cm bant invariantı, salon başına tek render aynen.

**K14 — F27 anonimleştirme.** **Öneri: koru, tetikleyici değişir.** 730 gün kuralı KVKK saklama süresi gerekçesiyle kalır; Celery beat yerine açılışta aday tespiti + kullanıcı onaylı geri dönüşsüz çalıştırma (FE'de sayaçlı uyarı). `student_id null` tipleri FE'de zaten hazır.

**K15 — Kimlik sabitleri.** Tümü yeniden adlandırılmalı (F0 işi): `DD_*` → `KS_*` (14 env), veri dizini `kelebek-sinav`, çerez `ks_oturum`, `X-KS-Token`, yedek magic+`.ksbak`, AppUserModelID, **Inno AppId GUID mutlaka yeni üretilir**, AppMutex.

**K16 — Klasik düzen (HOME_CLASSROOM).** **Öneri: al.** Aynı SeatAssignment altyapısı, `ExamRoom.linked_section` eşlemesi, okul no sırası; yoklama/kitapçık/tutanak tek altyapıdan besleniyor — kesmek evrak setini ikiye bölerdi.

---

## 3) ÇIKARIM HARİTASI (dosya düzeyinde, DD kalıbıyla)

### AYNEN (kopyala, import yolları dışında dokunma)
- `sinav_islemleri/engine.py` (533) — saf Python, Django import'u yok
- `sinav_islemleri/validator.py` (162) — sıfır bağımlılık, çift-denetim korunur
- `sinav_islemleri/layout.py` (331) — plan şeması, S/düz numaralandırma, koordinat sözleşmesi
- `sinav_islemleri/booklet.py` (225), `word_template.py` (110)
- `sinav_islemleri/participants.py` (260) — dataclass + `_conflict_group` anahtarı (`<cid>:<level>` / `<cid>:*`)
- `templates/sinav_islemleri/reports/` 11 şablon (base, _head, r1_kroki, r2_attendance, r3_door, r4_announcement, r6_assignment, r7_envelope, r8_validation, r9_handover, room_layout) + `booklet_overlay.html` + `calendar_pdf.html` + `backend/templates/print/_design.css`
- `ders_yapisi` saf parser'lar: catalog_parser, curriculum_parser, normalize yardımcıları (_match_key, _canon_course_key, titlecase_tr, repair_truncated_course_name)
- `data/ders-cizelgeleri/*.md` (AL 64 ders + çerçeveler + `ders-adi-takma-adlari.md`)
- FE: `planEdit.ts` (117), GROUP_TONES döngüsü, REPORT_CATALOG (api.ts:333-344), RoomEditor/YerlesimPaneli grid kimliği ve tıkla-yerleştir/tıkla-takas kalıpları, Dialog useCallback onClose disiplini
- DD şablonundan aynen: `desktop/` tamamı (main, errors 0-8 çıkış kodları, lock, session_guard, integrity, paths, logging_setup, server, window, django_bootstrap, version), `packaging/veri_sizintisi.py`, fontconfig çift-düzeltme, pyinstaller spec kalıbı, Inno/deb betikleri, kap-ici-test.sh, gates.sh, FE ui/ M3 kiti + lib/ + KurulumKapisi + queryClient, koruma testleri (format.test.ts tarih disiplini, App.test.tsx M3 token bütünlüğü), updates.py

### UYARLA
- `models.py` (1121): created_by düşer, soft-delete+koşullu unique kalır, SNAPSHOT deseni (SeatAssignment/ExamAttendanceRecord/ProctorAssignment) kalır, migration'lar 0001'den yeniden
- `services.py` (2354): Celery→senkron; ders_yapisi/core/zumre/gorevlendirme/program köprüleri yerel arayüzlere (fonksiyon imzaları korunarak); durum makinesi, PlacementRule, swap, seed sözleşmesi aynen
- `services_calendar.py` (1096): statutory_window+_daily_exam_load çekirdeği aynen; onay akışı tek-kullanıcı; bildirim dalı silinir
- `selectors.py` (280), `serializers.py` (509), `views.py` (1077) + `views_calendar.py` (540) + `urls.py`: permission_classes/rol düşer, GET+POST tek-action dersi (Tur 644) korunur
- `reports.py` (445): zumre imza dalı → boş çizgi dalı sabitlenir
- FE `api.ts` (694) → DD authsuz istemciye; `SinavSihirbazi.tsx` (780): Adım 0 beyana döner, sectionsApi yerel uca; takvim sayfalarında rol bayrakları true; `GozetmenlerPaneli.tsx`: aday havuzu = aktif personel; `SorularPaneli`: polling → senkron
- DD `backup.py`: X25519/parola dalı çıkar, düz günlük snapshot
- DD okul import çekirdeği: `imports.py` (596) + `normalize.py` (212) + `templates.py` (58) → veli/TCKN alanları atılarak; `_ensure_student_classes` → şube kataloğu tohumu
- `ders_yapisi` services/selectors: `levels__contains` → Python süzme; mükerrer tespit + consolidate + CourseAlias (SEED+OPERATOR) alınır
- POST `/exam-rooms/generate-section-rooms` (idempotent 40 koltuk üretimi) — hızlı başlangıç için aynen ama tek kullanıcı bağlamında

### ALMA
- `permissions.py`, `signals.py`, `tasks.py` (Celery sarmalayıcı), `admin.py`
- denetim app'i, kvkk_scope/kvkk_media_scope, AccessLog/SENSITIVE_READ
- bildirim modülü ve takvim onay sinyali; gorevlendirme/program/zumre köprü uçları
- LessonGroup/LessonEnrollment/TeachingAssignment ve btree_gist migration'ları
- `db_table='sinav_islemleri_course'` bagajı (ADR-0017)
- e-Okul/AI import zinciri, PDF parser'lar (excel_veli veli kısmı, pdf_personel, pdf_sube), Celery ASYNC_ROW_THRESHOLD, expected_hash
- FE useAuth/rol altyapısı, Bearer/refresh
- DD'den: app_password/EncryptedCharField, yedekleme.json X25519, Holiday/iş-günü motoru, ClassResponsibility (tohum fikri hariç), year_rollover, imha, disiplin app'i, guardian_* alanları

---

## 4) FAZ PLANI

**F0 — İskelet (şablon türetme).** DD'den repo türet; K15 kimlik sabitleri toplu değişimi; boş Django+FE ayağa kalkar; packaging spec'leri derlenir. *Kapı:* Windows exe açılır/kapanır, çıkış kodları 0-8 testleri, `--pdf-duman` geçer (WeasyPrint requirements'a F0'da girer ki hiddenimports/fontconfig sorunları erken yakalansın), gates.sh yeşil.

**F1 — Çekirdek veri + kurulum sihirbazı.** SchoolConfig(pk=1)+setup_completed+health ucu; SchoolYear; Personnel; Student (guardian'sız); import boru hattı (şablon üret + xlsx + pano, dry-run/commit); Course + MEB tohumu + CourseAlias; şube tohumu. *Kapı:* import dry-run/commit parite testleri, tohum idempotentliği, TR sütun eşleme testleri.

**F2 — Salonlar + motor.** ExamRoom + plan JSON + RoomEditor + `preview-seats`; engine/validator/layout/participants kopyası; `generate-section-rooms`. *Kapı:* saf motor test omurgası taşınmış ve yeşil — aynı-seed determinizm, satranç, S-rota 2D tuzağı, pin sabitliği, rastgele senaryolarda ihlal=0.

**F3 — Oturum akışı.** 5 adımlı sihirbaz (Adım 0 beyanlı), ExamSession+Course (baştan tek-seviyeli, Tur 241), dağıtım+seed, durum makinesi DRAFT→ARŞİV, PlacementRule 4 tip, swap, yoklama (APPROVED/ARCHIVED kuralı), SNAPSHOT. *Kapı:* uçtan uca senaryo testi; onay ihlal=0 şartı; arşivde mazeret güncellenebilir.

**F4 — Evrak seti.** R1–R5, R7–R9 + boş salon planı + tümü-ZIP; _design.css; ARCHIVED yeniden basım guard'ları. *Kapı:* her raporda TR karakter duman testi, `text-transform` yasağı tarama testi, `|unlocalize` denetimi.

**F5 — Kitapçık.** R10 senkron + QuestionDocument A4 dikey ±6pt doğrulama + Word şablonu. *Kapı:* bant invariantı (≤40mm), sayfa kuralları (≤2/>2), 90×4 <30 sn performans testi.

**F6 — Takvim.** ExamCalendar + statutory_window + grid + `_daily_exam_load` + slot→oturum + takvim PDF (A4 yatay). *Kapı:* pencere hesap ve limit senaryo testleri (öğrenci-bazlı sayım dahil).

**F7 — Gözetmen (ayara bağlı).** Elle atama, salon başına 1 + yedek kuralı, R6, yeniden dağıtımda sıfırlama. *Kapı:* ayar kapalıyken R6 katalogda görünmez.

**F8 — Bakım.** Günlük yedek+rotasyon, F27 elle-tetikli anonimleştirme, surum.json damgası, updates.py+UpdateBanner. *Kapı:* eski exe yeni DB'yi açmaz testi; anonimleştirme sonrası evrak yeniden basımı kırılmaz.

**F9 — Paketleme + saha.** PyInstaller onedir + Inno (yeni GUID, WebView2 gömülü) + .deb (bullseye kabı, pango/fontconfig Depends); kap-ici-test debian 11+12 ×2 + `--autotest` + `--pdf-duman`; veri_sizintisi.py her iki platformda. *Kapı:* temiz Windows 11 ve Pardus 21'de kurulum→sihirbaz→dağıtım→R1 PDF uçtan uca.

## key_facts
- sinav_islemleri modülü dışarıdan hiç import edilmiyor; tek dış referans denetim/kvkk_media_scope.py'daki 2 string kaydı — modül temiz kesilir
- engine.py (533), validator.py (162), layout.py (331), booklet.py (225), word_template.py (110), participants.py (260) saf/yarı-saf: porta bire bir kopyalanır
- services.py 2354 + services_calendar.py 1096 satır UYARLA sınıfının ana yükü: Celery→senkron, 5 köprü (core/ders_yapisi/zumre/gorevlendirme/program) yerel arayüze
- Celery yalnız 2 görevde ve generate_booklets_for_run zaten senkron çağrılabilir — Celery/Redis pakete hiç girmez
- FE rol kodu yalnız 3 takvim dosyasında; bayraklar true sabitlenerek auth katmanı tamamen düşer (DD authsuz lib/api.ts aynı hata sözleşmesini taşıyor)
- Gözetmen oto-atama zaten OYS UI'ından kaldırılmıştı (Tur 242) — portta elle listeden seçim + ayara bağlı (varsayılan kapalı), R6 koşullu
- Veri şifreleme önerilmiyor: kelebek verisi ad+no+şube; TCKN/veli/sağlık toplanmaz; backup.py parolasız düz Connection.backup() snapshot'a uyarlanır
- Course.levels JSONField'ın levels__contains sorgusu SQLite'ta yok — ~60 ders için Python süzme önerisi (ara tablo maliyetine değmez)
- MEB ders verisi fixture md dosyalarıdır (AL 64 ders + çerçeveler + ~55 takma ad); ensure_meb_catalog tembel tohumu idempotent — çevrimdışı güncelleme = CalVer uygulama sürümüyle
- VALID_COURSE_LEVELS=(0,9,10,11,12) lise-sabiti SchoolConfig'den türetilebilir yapılmalı; v1 fixture yalnız Anadolu Lisesi
- Takvim ve oturum alt sistemleri gevşek bağlı (create_session_from_slot tek yönlü) — takvim F6'ya güvenle ertelenir
- statutory_window + _daily_exam_load (öğrenci-bazlı, 3.=uyarı ≥4=hata) mevzuat çekirdeği olarak alınır; öğrenci kümesi kaynağı yerel şube kayıtlarına uyarlanır
- SNAPSHOT deseni (SeatAssignment ad/no/şube kopyası), durum makinesi, çift-denetim (motor+bağımsız validator), ihlal=0 onay şartı portta aynen korunur
- ExamSessionCourse baştan tek-seviyeli kurulmalı, kitapçık sözlüğü grup anahtarıyla (Tur 241 dersi)
- Klasik düzen (HOME_CLASSROOM) alınır — yoklama/kitapçık/tutanak tek SeatAssignment altyapısından
- PDF motoru WeasyPrint 63.1 + pypdf 5.1.0 aynen; DD'de fontconfig çift-düzeltme ve --pdf-duman (çıkış 8) hattı hazır; text-transform:uppercase yasağı test edilmeli
- İmport yolu v1'de şablon+pano+xlsx (DD boru hattı: rows matrisi, dry-run/commit, sha256 uyarı); e-Okul PDF parser'ları ve AI zinciri alınmaz; TCKN hiç toplanmaz
- F27 anonimleştirme (730 gün) korunur ama Celery beat yerine açılış denetimi + kullanıcı onaylı tetik
- Kimlik sabitleri F0'da toplu değişir: DD_*→KS_* (14 env), .ddbak→.ksbak, dd_oturum, X-DD-Token, AppUserModelID, Inno AppId GUID mutlaka yeni
- Python 3.12 sabit (Linux build python:3.12-bullseye = Pardus 21 glibc 2.31); PyInstaller onedir + Inno lowest-privilege + .deb
- Her yeni Python bağımlılığı packaging/pyinstaller spec hiddenimports'a elle eklenmeli (K7) — WeasyPrint bu yüzden F0'da girmeli
- İki koruma testi taşınmalı: format.test.ts (toISOString yasağı/todayIso) ve App.test.tsx (M3 token bütünlüğü); veri_sizintisi.py her iki platform build'inde
- DnD bilinçli yok (ADR-0016): salon editörü palet+tıkla-yerleştir, koltuk tıkla-takas — FE kalıpları aynen
- Rapor şablonları 11 dosya templates/sinav_islemleri/reports/ + booklet_overlay.html + calendar_pdf.html + print/_design.css birlikte kopyalanır
- Faz sırası: F0 iskelet → F1 veri+kurulum → F2 salon+motor → F3 oturum → F4 evrak → F5 kitapçık → F6 takvim → F7 gözetmen → F8 bakım → F9 paketleme; her fazın doğrulama kapısı raporda

## riskler
- hiddenimports körlüğü (K7): WeasyPrint/pypdf/openpyxl zinciri spec'e elle eklenmezse testler geçer, paket sahada çöker — F0'da pdf-duman zorunlu kapı
- services.py 2354 satırın köprü uyarlaması en riskli iş kalemi: fonksiyon imzaları korunmazsa motor/rapor testleri sessizce anlamını yitirir
- SQLite'ta levels__contains ve benzeri JSON sorgularının Python süzmeye çevrilmesi sırasında davranış sapması (aktif/pasif ders, seviye doğrulaması services.py:509-521)
- Öğrenci-bazlı günlük limit (_daily_exam_load) yerel veriye uyarlanırken konservatif düşüş kuralı (kayıtsız ders=seviyenin tamamı) kaybedilirse mevzuat denetimi gevşer
- Fontconfig/DejaVu hattı: fonts.conf'ta DOCTYPE kalırsa sessiz ret → sistem fontuyla bozuk Türkçe evrak; build.ps1 ezme adımı atlanmamalı
- Inno AppId GUID yenilenmezse disiplin-defteri kurulumlarıyla çakışır; DD_* env/çerez/magic kalıntıları iki uygulamanın aynı makinede veri karıştırmasına yol açar
- Takvim onay akışının tek-kullanıcıya sadeleştirilmesi resmî evrak damgalarını (onaylayan/tarih) silmemeli — kilit ve damga korunmazsa basılan takvim PDF'inin resmî değeri düşer
- Parolasız düz yedek: DD'de günlük yedek parolasız kipte atlanıyordu; bu dal kaldırılmazsa kelebek-sinav hiç yedek almaz
- UTC tarih tuzağı: 00:00-03:00 arası toISOString ile bir gün geri kayma — format.test.ts koruma testi taşınmazsa sınav tarihli evrakta nüksedebilir
- MEB çizelge verisi yalnız Anadolu Lisesi: farklı okul türünde çalışan kullanıcı için ders havuzu boş başlar; elle ekleme yolu F1'de eksiksiz olmalı
- F27 anonimleştirme geri dönüşsüz: elle tetiğe çevrilirken onay diyaloğu ve aday listesi gösterimi olmadan çalıştırılırsa veri kaybı şikayeti kaçınılmaz
- Pardus tarafı yalnız bullseye kabında derlenmiş build ile test ediliyor; PyQt5+QtWebEngine bağımlılık seti kelebek için de kap-içi-test ×2 olmadan güvenilmez
