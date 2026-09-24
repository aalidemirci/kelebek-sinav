# Kelebek Sınav — Değerlendirme ve Geliştirme Planı

*Tarih: 18.09.2026 · Sürüm: 2026.9.0-beta.5 (commit `febfbe5`) · Durum: taslak,
kullanıcı kararı bekleyen maddeler §4.5'te.*

**Yöntem.** Kod okuması (backend, frontend, evrak şablonları, masaüstü kabuğu),
`.ornek-evrak/` altındaki yedi örnek PDF'in görsel incelemesi, `docs/mevzuat/`
metinleriyle karşılaştırma ve saha vakasının (TDE 9 + TDE 10 oturumunda soru
dosyası hatası) kök neden analizi. Dört paralel inceleme (backend doğruluk ·
arayüz ve dil · evrak · kılavuz/kapılar/paketleme) bu belgede birleştirildi.
CLAUDE.md §1-3'te "bulgu sayılmaz" denen kalıplar (auth yok, soft-delete,
şifreli alan süzmesi vb.) ve `docs/teknik-borc.md`'deki kabul edilmiş borçlar
yeniden raporlanmadı.

**İşaretler.** *Doğrulandı* = kodda somut girdi → yanlış çıktı senaryosu
gösterildi (ya da örnek PDF'te görüldü). *Olası* = kanıt eksik, test gerekir.
*Kapatıldı* = bu oturumda düzeltildi (§2).

---

## 1. Yönetici özeti

- **Mimari sağlam.** View → servis → model katmanı korunmuş; kelebek motoru
  bağımsız doğrulayıcıdan geçiyor; determinizm (seed) ve KVKK disiplini (adsız
  hata metinleri, kategori-düzeyi gerekçe, snapshot şifrelemesi) kodda tutarlı;
  ~600 test, backend satır kapsamı %89.
- **Saha vakasının kökü terminoloji.** "Ortak kitapçık" kutusu MEB'in "ortak
  sınav" terimiyle karışıyordu; backend de uyuşmazlığı reddettiği için yanlış
  işaret ikinci satıra zorla taşındı; dağıtımdan sonra geri yol yoktu. Beş
  değişiklikle **kapatıldı** (§2).
- **Doğruluk:** sekiz somut bulgu; üçü kapatıldı (bayrak kilidi, R8 şablon
  yorumu sızıntısı, karma seviyede seviyesiz ders adı), beşi planda (klasik
  düzende R1 basılmıyor, ders birleştirme dağıtılmış oturumu bozuyor, takvim
  girdisinin ölü oturum bağı, ayar ucunda 500, soru dosyası silme kapısı ve
  diskte kalan dosyalar) + iki tutarlılık boşluğu (yoklama kayıtları, medya
  yedeği).
- **Kullanılabilirlik:** en kritik açık akışsaldı — dağıtımdan sonra oturum ne
  düzenleniyor, ne siliniyordu ("Taslağa al" ile kapatıldı). Kalanlar: geri
  dönüşsüz işlemlerde onay diyaloğu eksikleri, iç kodların (K5, R10, seed,
  "Koşu #2") yüzeye sızması, sihirbazın her açılışta 1. adıma dönmesi.
- **Dil:** "ortak" sözcüğü üç anlamda; salon/derslik, personel/öğretmen,
  seviye/sınıf, kapsam/katılımcı tipi çiftleri ekran ekran değişiyor;
  "Özürlü/Özürsüz" mevzuattaki "mazeret"le çelişiyor; iki Disiplin Defteri
  kalıntısı (temizlendi).
- **Evrak:** sınav süresi hiçbir belgede yok; R6'da yazı tarihi ve tebliğ eden
  imzası yok; takvim PDF'inde ders saati başlangıcı ve onay tarihi yok, "Okul
  Zümre Başkanı" imza yeri hiç dolmuyor; kaymakamlık satırı büyük harfe
  çevrilmiyor; çift yüz basımda yaprak-1 sağ sayfaya bağlanmıyor.
- **Teslimat:** GitHub'da test/lint kapısı yok, frontend değişikliği CI'ı hiç
  tetiklemiyor; kılavuz beş iş akışını anlatmıyordu (üçü eklendi).

---

## 2. Saha vakası: "Türk Dili ve Edebiyatı — 9. ve 10. Sınıf" (kapatıldı)

### 2.1 Hata zinciri

1. Sihirbazın **Ders ekle** formunda her satırda "Ortak kitapçık (bu dersin tüm
   seviyeleri tek kitapçık/tek çakışma grubu)" kutusu vardı. MEB dilinde
   "ortak sınav / ortak yazılı" okul geneli sınav demek olduğundan kutu TDE 9
   için işaretlendi.
2. Backend kuralı (`_ensure_shared_booklet_sync`) kardeş satırda **farklı**
   bayrağı reddediyordu → TDE 10 eklenirken kutu yine işaretlenmek zorunda
   kaldı.
3. İki satır da `shared_booklet=True` olunca çakışma grubu `"<ders>:*"` oldu:
   motor 9 ve 10. sınıf TDE öğrencilerini **aynı sınav** sayıp yan yana
   oturtmadı (kelebek kalitesi gereksiz düştü) ve soru dosyası kuralı "grup
   başına tek dosya"ya döndü.
4. Sorular paneli ise satır başına ayrı **Yükle** gösterdi; ikinci yükleme
   "Ortak kitapçıkta soru dosyası tek satıra yüklenir…" hatasıyla döndü —
   arayüz ile backend sözleşmesi çelişiyordu.
5. Dağıtılmış oturumda ders satırı düzenlenemiyor (`_ensure_draft`), oturum
   taslağa alınamıyor ve silinemiyordu → tek çare oturumu baştan kurmaktı.

### 2.2 Yapılan değişiklikler

| Katman | Değişiklik | Yer |
|---|---|---|
| Backend | `shared_booklet` **dersin oturum içi niteliği**: açık verilen değer kardeş satırlara yayılır, verilmeyen değer kardeşten miras alınır; uyuşmazlık reddi kalktı | `services.py` `_sync_shared_booklet`, `_inherited_shared_booklet`, `add_session_course`, `update_session_course` |
| Backend | **Taslağa al**: DAĞITILDI → TASLAK geçişi; yerleşim + gözetmen görevlendirmesi silinir, ders/salon/kural/muafiyet/soru dosyası/kitapçık koşusu korunur | `services.py` `revert_session_to_draft`, `views.py` `POST /exam-sessions/{id}/revert-to-draft/` |
| Backend | Yükleme reddi artık dosyanın **hangi seviye satırında** olduğunu ve çıkış yolunu söylüyor | `services.py` `upload_question_document` |
| Backend | Kullanıcıya görünen ek "ortak kitapçık" → **"tüm seviyeler aynı kitapçık"** (tek sabit `SHARED_BOOKLET_SUFFIX`) | `services.py` |
| Backend | Karma seviyeli oturumda evrak ders adı **seviyeli** ("Coğrafya — 9. Sınıf"); tek seviyede yalın ad | `services.py` `_seat_course_names` (R1/R4/R5/R7) |
| Şablon | R8 doluluk tablosunda çok satırlı `{# #}` yorumu çıktıya basılıyordu → `{% comment %}` | `r8_validation.html` |
| Frontend | Kutu ekleme formundan **çıktı**; aynı ders ≥2 seviyedeyken listenin altında ders-başı "… aynı soru kitapçığını çözecek" kutusu (`updateCourse`) + formda bilgi satırı | `SinavSihirbazi.tsx` |
| Frontend | Sorular paneli aynı-kitapçık satırlarını **tek satırda** gösterir, dosya hangi satırdaysa oradan okur/oraya yükler (`groupQuestionRows`) | `SorularPaneli.tsx` |
| Frontend | Oturum başlığında **"Taslağa al"** (onay diyaloğu) | `OturumDetayPage.tsx`, `api.ts` |
| Frontend | Disiplin Defteri kalıntıları: kurtarma anahtarı çıktısının başlığı, ders yılı açıklaması | `KurtarmaAnahtariDiyalogu.tsx`, `AyarlarPage.tsx` |
| Belge | Kılavuz 8. adıma üç bölüm (aynı kitapçık · soru dosyaları/kitapçık · Taslağa al); CLAUDE.md §2-3; tasarım §4 ve §12 satırı | |
| Test | Backend: kardeş senkron + miras, taslağa alma (servis + API + kapılar), yükleme mesajı, karma seviyede ders adı, R8 sızıntı koruması · Frontend: ders-başı kutu, tek seviyede bölüm yok, panelde tek satır/tek yükleme, "Taslağa al" diyaloğu | |

### 2.3 Mevcut oturumunuz için yol

1. Güncel sürümle oturumu açın → **Taslağa al** (onay) → sihirbaz **Ders ve
   Katılımcılar** adımına dönün.
2. Listenin altındaki "Türk Dili ve Edebiyatı: 9. sınıf, 10. sınıf aynı soru
   kitapçığını çözecek" kutusunun **boş** olduğundan emin olun (eski kayıt
   işaretli gelir; kaldırın — tek tıkla iki satır birden düzelir).
3. Salonlar → **Dağıt** → **Sorular ve Kitapçıklar**: iki satır, iki dosya →
   **Kitapçıkları üret**.

Gözetmen görevlendirmesi yeniden yapılır; yerleştirme kuralları ve daha önce
yüklenen 9. sınıf dosyası korunur.

---

## 3. Değerlendirme

### 3.1 Mimari ve doğruluk

**Güçlü yanlar.** Motor/doğrulayıcı çift denetimi gerçek; `(desk_row,
desk_col)` kimliğinden sert kısıt, leksikografik ceza demeti ve seed
determinizmi testlerle sabit. Servis katmanı Türkçe `ValidationError` ile tek
hata sözleşmesi kuruyor; SNAPSHOT deseni arşiv evrakını sabitliyor; şifreleme
katmanı doğuştan selector disipliniyle kurulmuş. Mevzuat invariantları (takvim
pencereleri, günlük sınav yükü, kapsam kesişimi) testlerle korunuyor.

**Zayıf yanlar.** (1) Durum makinesinin tüketicileri eşit değil: aynı kapı bir
yolda var, komşu yolda yok. (2) Veri modeli varsayımları evrak katmanına sızmış:
R1 "salon = `ExamSessionRoom`" varsayıyor, klasik düzen ve kural pinleri bunu
kırmış. (3) `services.py` 2.600 satıra ulaştı; iki doğruluk kaynağı ve bayat
docstring birikiyor.

**Bulgular.**

| # | Bulgu | Yer | Durum | Öneri |
|---|---|---|---|---|
| A1 | **Klasik düzende (kendi dersliğinde) R1 hiç basılmıyor**; kural pini oturum salon listesi dışına düşen öğrencinin salonu da basılmıyor. Sihirbaz klasikte salon adımını atlar → `ExamSessionRoom` yok → `_room_sheets` boş döner; `?room_id=` ile istenince "Salon bu oturumda tanımlı değil" | `services.py` `_room_sheets`, `distribute_session` HOME_CLASSROOM dalı, `_resolve_rule_pins` | Doğrulandı (kod) | Yaprak kaynağını `SeatAssignment.room_id` kümesinden türet (`_seated_rooms` var); `room_id` denetimini ona bağla; klasik düzen + dış salon pinli R1 testi |
| A2 | `shared_booklet` kardeş satır varken PATCH ile değiştirilemiyordu | `update_session_course` | **Kapatıldı** | — |
| A3 | **Ders birleştirme dağıtılmış/onaylı oturumu bozuyor**: `consolidate_duplicate_course` `ExamSessionCourse.course`'u durum kapısız taşır; `SeatAssignment.conflict_group` eski kimlikte kalır → kitapçık üretimi her öğrenci için "soru dosyası eksik" der | `dersler/services.py` `consolidate_duplicate_course` | Doğrulandı (kod) | Taşımayı TASLAK oturumla sınırla; diğerlerinde `conflict_group`'u aynı işlemde yeniden yaz ya da birleştirmeyi reddet |
| A4 | **Takvim girdisi soft-silinmiş oturum bağını canlı sayıyor**: `remove_calendar_entry` ve `unplace_entry` yalnız `session_id is not None` bakar; slottan üretilen oturum silinince girdi ne havuza alınır ne silinir (400), ızgara ölü `session_id` basar | `services_calendar.py` | Doğrulandı (kod) | Canlılık koşulunu tek yardımcıya çek (`place_entry`/`auto_place`'te zaten var) ve iki fonksiyonda kullan |
| A5 | **Ayar ucunda geçersiz değer 500**: `PUT /setup/school-config/` `daily_period_count=0` ya da `exam_period_nos=[99]` → Django `ValidationError` DRF'ye çevrilmiyor | `okul/views.py` school-config ucu | Doğrulandı (kod) | `except DjangoValidationError → serializers.ValidationError(exc.message_dict)`; API testi |
| A6 | **Soru dosyası DELETE durum kapısını atlıyor** (onaylı/arşiv oturumda silinebiliyor) ve **değiştirilen/silinen PDF diskte kalıyor** (`storage.delete` yalnız anonimleştirmede) — sınav öncesi gizlilik | `views.py` `question` DELETE dalı; `upload_question_document` | Doğrulandı (kod) | Silmeyi servise al (durum kapısı + `on_commit` dosya silme); yükleme değişiminde eski dosyayı sil |
| A7 | **Yeniden aç → yeniden dağıt yoklama kayıtlarını bayat bırakıyor** (`ExamAttendanceRecord` eski salon/koltuk snapshot'ıyla canlı kalır; "zaten işaretli" reddi). Bugün eklenen "Taslağa al" da aynı boşluğu paylaşır (bilinçli — CLAUDE.md §3) | `distribute_session`, `revert_session_to_draft` | Doğrulandı (kod) | Yeniden dağıtım/taslağa almada yoklama kayıtlarını soft-sil + uyarı; test |
| A8 | **Yedek medya dizinini kapsamıyor**: geri yüklemeden sonra `QuestionDocument.file`/`BookletRun.file` satırı var, dosya yok → indirme uçları `FileNotFoundError` ile 500 | `desktop/backup.py`, `views.py` indirme uçları | Olası (etki) | İndirmede `storage.exists` + Türkçe 404; medyanın yedek kapsamı **karar** (§4.5) |
| A9 | R8 doluluk tablosunda şablon yorumu çıktıya basılıyordu | `r8_validation.html` | **Kapatıldı** | — |
| A10 | Karma seviyeli oturumda (Coğrafya 9 + 10) R1/R4/R7 iki kitapçık grubunu tek "Coğrafya (40)" satırında birleştiriyordu; örnek fixture ders adına seviyeyi gömdüğü için görünmüyordu | `_seat_rows` | **Kapatıldı** | `evrak_ornek.py` fixture'ını katalog adlarına çevir (P1) |
| A11 | Yerleşimi yapılmış salonun `layout_plan`'ı denetimsiz değişiyor; kroki güncel plandan çizilir, eşleşmeyen koordinat sessizce düşer → öğrenci yoklamada var, krokide yok | `update_exam_room`, `reports.build_room_kroki` | Doğrulandı (kod) | Yerleşimli salonda plan değişikliğini reddet ya da `ExamSessionRoom`'a plan snapshot'ı; eşleşmeyen koordinatta uyarı |
| A12 | `swap_seats` PINNED (kural) satırı uyarısız MANUAL'a çeviriyor | `swap_seats` | Doğrulandı (kod) | Kurallı koltuğu takasta reddet ya da uyarı |
| A13 | `remove_exam_session` SESSION kapsamlı `PlacementRule`/`ProctorExemption` satırlarını canlı bırakıyor; atomic değil | `remove_exam_session` | Doğrulandı (kod) | Aynı işlemde soft-sil; `@transaction.atomic` |
| A14 | `_validate_participant_refs` `int(sid)` — `section_ids` tip denetimsiz, `["abc"]` 500 | `services.py` | Doğrulandı (kod) | Serializer düzeyinde tam sayı listesi doğrulaması (takvim tarafındaki `_bulk_item_int` emsali) |
| A15 | MEB dersinin adı `update_course` ile değiştirilebiliyor; sonraki `sync_catalog` adı görmeyip dersi çizelge-dışı pasifleştirir, aynı adla yenisini yaratır | `dersler/services.py` | Olası | MEB kaynaklı derste ad değişikliğini kilitle ya da takma ad tablosuna yaz |

**Mimari/tutarlılık notları.** İki doğruluk kaynağı: kural doğrulaması
`serializers.py` ile `services.py`'de iki kez; `level_label` `catalog.py`
("9. sınıf") ile `dersler/services.py` ("9. Sınıf") farklı; `tr_upper` üç
kopya (`shared/text.py`, `okul/normalize.py`, `dersler/text.py`). Hata
sözleşmesi tutarsız: `views.py` `exc.messages` (liste), `views_calendar.py`
`message_dict` — FE iki biçimi ayrı ele almak zorunda. Katman ihlali: birkaç
view ORM `delete()`'i doğrudan çağırıyor (`ExamTrackItem` docstring'i
"is_active=False" derken DELETE soft-siler, matris işaretleri kaybolur). N+1:
`ExamSessionSerializer` iç içe `courses/rooms`, takvim `entry_participant_preview`
şube başına sorgu — ölçek küçük ama liste uçları `select_related` almalı.
Bayat metinler: `services.py` başlık docstring'i F7'nin "alınmadığını" söylüyor;
`_proctor_names_by_room` "R9 basımı"; `shared/crypto.py` var olmayan
`find_student_by_tckn`'e atıf (CLAUDE.md "TCKN toplanmaz" ile çelişen DD
metni); `services.py`'de çift `@transaction.atomic`.

**Test boşlukları.** Klasik düzen + dış salon pinli R1; `consolidate` dağıtılmış
oturumda; ölü oturum bağlı takvim girdisi; ayar ucu 400; soru dosyası DELETE
kapısı + disk temizliği; reopen → dağıt → yoklama; medya eksikken indirme;
`swap_seats` PINNED; oturum listesi sorgu sayısı. Testi olmayan FE bileşenleri:
`TakvimDetayPage`, `TakvimTakipPaneli`, `KalemYonetimiDialog`,
`KapsamDuzenleDialog`, `DersSubeKapsamiDialog`, `RoomEditor`,
`SablonUygulaDialog`, `DerslikKumeleriDialog`, `UpdatePanel`,
`KurtarmaAnahtariDiyalogu`, `SubeKapsamSecici`, `TextField`.

### 3.2 Kullanılabilirlik

| Öncelik | Bulgu | Yer | Öneri |
|---|---|---|---|
| Yüksek | Dağıtımdan sonra çıkmaz sokak (düzenleme/silme/geri dönüş yok) | `OturumDetayPage` | **Kapatıldı** ("Taslağa al"); "Yeniden dağıt" (seed/katı mod) düğmesi DAĞITILDI'da hâlâ yok — kılavuz var olmayan düğmeye yolluyor (`KilavuzPage` 8. adım ipucu) |
| Yüksek | Geri dönüşsüz işlemlerde onay yok: "Tebellüğ işle" (geri alma ucu yok), yüklü soru PDF'ini "Kaldır", onaylı takvimi "Taslağa Al" (damga düşer), oturum "Onayla" (kilitler; `approved_by_name` sorulmuyor) | `GozetmenlerPaneli`, `SorularPaneli`, `TakvimDetayPage`, `OturumDetayPage` | `useConfirm` + onaylayan ad alanı |
| Yüksek | Gözetmen modülü sonradan açılamıyor ("Taslakta açılabilir" ama taslağa dönüş yoktu) | `GozetmenlerPaneli` | Taslağa al ile dolaylı çözüldü; ayarı durumdan bağımsız düzenlenebilir yap |
| Yüksek | Ön kontrol "kim" bilgisi hiç alınmıyor; ekran "onay kim/ne zaman yazılır" derken ad hep "—" | `SinavSihirbazi` PreCheckStep | Ad alanı ekle ya da metni düzelt |
| Orta | Sihirbaz her açılışta 1. adıma dönüyor, Stepper tıklanamıyor | `SinavSihirbazi`, `Stepper` | Kaldığı adımdan başlat; tamamlanan adımlar tıklanabilir |
| Orta | "Dağıt & Önizle" adımında önizleme yok | `SinavSihirbazi` | "Dağıt" |
| Orta | Evrak dosya adları kod+kimlik (`r7_oturum_3.pdf`, `kitapciklar_oturum_12.zip`, `sinav_takvimi_4.pdf`) | `EvrakPaneli`, `SorularPaneli`, `TakvimDetayPage` | "Salon-Sinav-Evraki_<oturum>_<tarih>.pdf" |
| Orta | Takvim yerleştirme uyarıları kırmızı snackbar kuyruğunda akıp kayboluyor | `TakvimYerlestirmePaneli` | Kalıcı uyarı bandı/diyalog (otomatik yerleştirme raporu emsali) |
| Orta | Tek kullanıcıda "Onaya Sun → Onayla" iki tıklık ritüel | `TakvimDetayPage` | Tek "Onayla" (**karar**, §4.5) |
| Orta | "Pasifle" ile "Sil (kalem gizlenir)" aynı işi yapıyor | `KalemYonetimiDialog` | Birini kaldır |
| Orta | Yükleme/boş durum kalıpları karışık (düz metin vs `SkeletonList`/`EmptyState`); her hata "Takvim bulunamadı" | çeşitli | Tek kalıp |
| Orta | Gezinme sırası kurulum akışının tersi (Takvimler, Oturumlar, Salonlar, Kişiler, Ders Havuzu, Ayarlar) | `AppShell` | Kılavuz sırasıyla hizala |
| Düşük | Erişilebilirlik: `role="combobox"` sarmalayıcı div'de; bazı onay kutuları boyutsuz; sabit `grid-cols-3` dar ekranda sıkışır | `Autocomplete`, `CizelgeAtamaMatrisi`, `SinavSihirbazi` | ARIA 1.2'ye çek; responsive grid |
| Düşük | Ham renk (`text-white`, `bg-white/95`) ve iki tema anahtarı | `AppShell` | Token'a çek; tek anahtar |

### 3.3 Dil ve terminoloji

Öne çıkan örnekler (tam liste inceleme çıktısında; 40 kalem):

| Yer | Mevcut | Sorun | Öneri |
|---|---|---|---|
| `KurtarmaAnahtariDiyalogu` | "DİSİPLİN DEFTERİ — KURTARMA ANAHTARI" | Şablon kalıntısı | **Kapatıldı** |
| `AyarlarPage` | "Kurul, tutanak ve disiplin kayıtları…" | Şablon kalıntısı | **Kapatıldı** |
| `SinavSihirbazi` | "Ortak kitapçık (…)" | MEB "ortak sınav"la çatışma | **Kapatıldı** |
| `GozetmenlerPaneli` | "kapalı (K2 — varsayılan)… R9 tutanağında… R6" | İç kod + kaldırılmış belge kodu | "Gözetmen modülü bu oturumda kapalı; görevlendirme yazısı basılmaz, salon evrakındaki görevli adı elle yazılır." |
| `SorularPaneli`, `EvrakPaneli` | "Puan bölümü (K5)", "Kişiselleştirilmiş kitapçıklar (R10)", "Koşu #2", "Tek PUAN kutusu" | Geliştirici kodları, rastgele büyük harf | Kodsuz etiket; "Üretim · 16.11.2026 09:05" |
| `oturumlar/api.ts` | `EXCUSED: "Özürlü"`, `UNEXCUSED: "Özürsüz"` | Mevzuat "mazeret" der; "özürlü" engellilik çağrışımı | "Mazeretli / Mazeretsiz" |
| Sihirbaz, Yerleşim, kopyalama | "Seed (boş = rastgele)", "(seed 4231)" | Programcı terimi | "Dağıtım numarası" (yardım metninde bir kez "seed") |
| `YerlesimPaneli` | "Sert kısıt ihlali yok (İHLAL = 0)", "1. halka…", "Yakınlık skoru" | Motor iç ölçütleri | "Kural ihlali yok — onaylanabilir." + "Ayrıntı" açılır bölümü |
| `KurallarPaneli` | "sıra 1-0, koltuk 0" | 0 tabanlı koordinat | "3. sıra, 1. sütun, sol koltuk (no 5)" |
| `TakvimHavuzPaneli` | Onay kutusu "Kelebek değil" (`checked={!butterfly}`) | Çift olumsuz | "Düzen: Kelebek / Kendi dersliğinde" |
| `TakvimYerlestirmePaneli` | " [U]", " (KD)" | Açıklanmayan kısaltma | Rozet "Uygulama" / "Klasik" |
| `KisilerPage`, `PanelPage`, `SifreliYedekleme`, `UpdatePanel` | "(soft delete)", "alias", "X25519 ve AES-256-GCM", "Release" | İngilizce/kripto jargonu | Türkçe karşılık; teknik ad Hakkında'da |
| `lib/gradeLevels.ts` vs backend | "9. sınıf" / "9. Sınıf" | İki yazım | Tek yardımcı, "9. Sınıf" |
| `oturumlar/api.ts` | `ARCHIVED: "Arşiv"` | Diğerleri fiil | "Arşivlendi" |
| `SinavSihirbazi` | "önce Okul modülünden e-Okul listesini aktarın" | Menüde "Okul" yok | "Kişiler ekranından" + bağlantı |
| `AyarlarPage` | "şube yoklama listeleri bu katalogdan beslenir" | R2k kaldırıldı | "Şube sınav duyurusu…" |

Tutarsız adlandırma kümeleri: **personel/öğretmen** (sekme "Öğretmenler",
düğme "Yeni personel", snackbar "Personel eklendi", "Öğretmen sicili");
**salon/derslik** ("Sınav Salonları", "Derslik Kümeleri", "Kullanılacak
derslikler", adım "Salonlar"); **seviye/sınıf** ("Sınıf" / "Seviye" / "Ders /
Seviye"); **katılımcı tipi/kapsam** ("Katılımcı tipi: Şube şube" / "Kapsam: Şube
seç"). Düğme yazımı karışık: Başlık Düzeni ("Onaya Sun", "Taslağa Al", "Oturum
Üret") ile cümle düzeni ("Yeni takvim", "Otomatik yerleştir"); devam düğmeleri
üç biçim ("Kaydet ve devam", "Kaydet ve devam et", "Onayla ve devam et");
seçici yer tutucuları beş biçim; tırnaklar “ ” ile " " karışık; ham "✓"/"⚠"
karakterleri `Icon` yerine.

### 3.4 Evrak (raporlar)

| Belge | Güçlü | Eksik / hatalı | Dil |
|---|---|---|---|
| **R1 Salon Sınav Evrakı** | FR-006 anatomisi korunmuş; 40 öğrenci iki yaprak (örnek PDF doğruluyor); beşer satır ayracı, ön cephe bandı okunur | **Sınav süresi hiçbir yerde yok** (`ReportHeader` taşımıyor; kontrol listesi "süresi duyuruldu" diyor) · "girmeyen öğrenci sayısı **ve okul numaraları**" alanı yalnız sayı · tespit/açıklama tek satır · karışık salonda kroki hücresi dersi göstermiyor · karma seviyede ders adı (**kapatıldı**) · plan değişikliğine karşı koruma yok (A11) | "müdür yrd.na" kısaltması; altbilgi "Üretim:" → "Düzenleme tarihi"; kroki lejandı sabit metin (masa yoksa yanlışlanır) |
| **R4 Şube Duyurusu** | Salon özeti üstte, okul no sırası, mazeret cümlesi YUSY 5/1-y ile birebir | İmza/kaşe alanı yok; dayanak/KVKK dipnotu yalnız bu belgede yok; süre yok | Temiz |
| **R6 Görevlendirme** | Resmî yazı üslubu, UYGUNDUR bloğu, yedekler sonda | Yazının **tarihi** ve **tebliğ eden** (müdür yardımcısı) imzası yok; görev bitiş saati yok; salon başına ders(ler) yok | `…"1. Ortak Yazılı Sınav" sınavında` tekrarı |
| **R7 Tutanak** | FR-007 fiil/hüküm eşlemesi birebir; koltuk no eklenmiş; imza üçlüsü mevzuat unvanlarıyla | Öğrenci beyanı satırı yok (kaynakta da yok — bilinçli olabilir); süre yok | Temiz |
| **R8 Doğrulama** | Seed basılı, adsız ihlal listesi, doluluk tablosu | Yorum sızıntısı (**kapatıldı**) · `report.params.seed` `unlocalize`siz | Müdürün imzaladığı belgede jargon ("1. halka", "Σ 1/d²", "Satranç modu"); **"Sınav Komisyonu"** mevzuatta olmayan organ → "Düzenleyen — Müdür Yardımcısı" |
| **Boş salon planı** | Kişisel veri yok; numaralar büyük | Düzenleme tarihi yok; lejant sorunu R1 ile aynı | — |
| **Takvim PDF** | Üst makam sınavları nötr dolgu + lejant; TASLAK filigranı; dipnot düzenlenebilir | Ders saatinin **başlangıç saati** basılmıyor (`start` bağlamda var, şablonda yok) · UYGUNDUR bloğunda **tarih yok**, `generated_at` kullanılmıyor · "Okul Zümre Başkanı" imza yeri **asla dolmaz** · antet "Beşiktaş KAYMAKAMLIĞI" — ilçe büyütülmüyor (`letterhead.py`, `tr_upper` var) · birim satırı resmî usulde "<Okul> Müdürlüğü" | "9. Sınıf (3)" parantez etiketsiz; "[UYGULAMA]" → "Uygulamalı"; "EĞİTİM ÖĞRETİM YILI" → "EĞİTİM VE ÖĞRETİM YILI" |
| **Kitapçık bandı** | 4 mm + 32 mm sözleşmesi; seviye etiketli ders adı; sayfa x/y | Süre yok; puan kutusunda "Rakamla / Yazıyla" yok (yaygın uygulama) | — |
| **Word şablonu** | Altı madde panelle özde aynı | "diğer kenar boşlukları 2 cm" ve "bant tek numaralı sayfalara" panelde yok — "birebir" iddiası tutmuyor | — |

Ortak: çift yüz basımda `.sheet { page-break-after: always }` yaprak-1'i sağ
sayfaya bağlamıyor (40'ı aşan salon sonrası tüm salonların yaprak-1'i arka yüze
düşer) → `break-before: right`; tablo iç çizgileri 0,5 pt açık gri
(fotokopide silikleşir) → ≥0,6 pt; `@bottom-right { content: "…exam_name" }`
addaki `"` altbilgiyi bozar; OKY (Ortaöğretim Kurumları Yönetmeliği) metni
depoda yok, R1/R7/takvim açıklamasındaki md. 45/48/49/86/164 atıfları
doğrulanamıyor (kılavuz "madde numarası depodaki metinden" kuralı koyarken).

### 3.5 Kılavuz, kapılar ve teslimat

- **Kılavuz** doğru ve iyi yazılmış: 50+ düğme/sekme adı kaynakla birebir,
  mevzuat atıfları (ÖDY md. 5, Yönerge md. 4-5) satır satır doğrulandı. Eksik
  akışlar: soru dosyası/kitapçık, aynı kitapçık, taslağa alma (**üçü eklendi**);
  yoklama sekmesi; güncelleme; Ayarlar → Şubeler; süreç takip kalemleri; parola
  değiştirme/kilit ekranı. Yanlış bilgi: "her açılışta günlük yedek" → gerçek
  "her gün ilk açılışta" (`KilavuzPage.test.tsx` metni kilitliyor, birlikte
  değişmeli); Pardus geri yükleme komutu yok; aynı kural kılavuzda ÖDY,
  uygulama uyarısında "OKY md. 45".
- **CI'da test/lint kapısı yok.** Tek iş akışı paketleme; PR tetikleyicisi
  `frontend/src`'yi kapsamıyor. Kalite tümüyle yerel `gates.sh`'a bağlı.
- Kapsam eşiği yalnız backend (%75); `desktop/`+`packaging/` `--no-cov`;
  frontend kapsam yapılandırılmış ama kapı yok. Düşük kapsamlı modüller:
  `okul/services/templates.py` %43, `persons.py` %47, `views_calendar.py` %63
  (dal %39), `updates.py` %66.
- Depo hijyeni: kökte boş `.github;C` dizini (PowerShell argüman kazası,
  silinmeli); izlenmeyen host artefaktları (`.coverage`, `coverage.xml`,
  `.mypy_cache`, `dist/`); `frontend/.gitignore` Playwright satırları (OYS
  kalıntısı). `packaging/README.md` "-dev" ön-sürüm notu VERSION ile uyumsuz.
- Doküman bayatlıkları: `teknik-borc.md` TB8 (kural ekranı var — kapanmalı)
  ve TB10 (kapsam artık `_scope_overlaps` + otomatik yerleştirmede de
  kullanılıyor); `docs/kurulum.md` "(v1: Anadolu Lisesi)"; CLAUDE.md §4 "F0
  tamamlanana dek" notu.

---

## 4. Geliştirme planı

Büyüklük: **S** ≤ yarım gün · **M** 1-2 gün · **L** 3+ gün. Her kalem
`scripts/gates.sh` yeşiliyle kapanır; kabul ölçütü her satırda.

### 4.1 P0 — Bu hafta (saha güvenliği)

| # | İş | Büyüklük | Kabul |
|---|---|---|---|
| P0-1 | **Bu oturumun düzeltmelerini yayımla**: beta.6 etiketi; okulapp.org sürüm kartı | S | Paket kapısı yeşil; TDE 9/10 senaryosu paketten uçtan uca (Taslağa al → kutu kaldır → dağıt → iki dosya → kitapçık) |
| P0-2 | **A1 — klasik düzende R1**: yaprak kaynağı `SeatAssignment` salon kümesi; dış salon pinli kural | M | Klasik oturumda salon başına R1 + `?room_id=` testi; kelebek testleri değişmeden yeşil |
| P0-3 | **A6 — soru dosyası silme kapısı + disk temizliği** | S | Onaylı oturumda DELETE 400; değiştirilen dosya `MEDIA_ROOT`'ta kalmaz (test) |
| P0-4 | **A3 — ders birleştirme kapısı** | S | Dağıtılmış/onaylı oturumu olan derste birleştirme reddedilir ya da `conflict_group` yeniden yazılır (test) |
| P0-5 | **A5 — ayar ucu 400** | S | Geçersiz `daily_period_count`/`exam_period_nos` API'de 400 + alan hatası |
| P0-6 | **R8 "Sınav Komisyonu" → mevzuat unvanı; jargon sadeleştirme; seed `unlocalize`** | S | Şablon testi; örnek PDF yenilenir |
| P0-7 | **Kılavuz düzeltmeleri**: "Yeniden Dağıt" ipucu, yedek sıklığı, Pardus geri yükleme, OKY/ÖDY dayanak tekleştirme | S | `KilavuzPage.test.tsx` güncel |

### 4.2 P1 — İki hafta (doğruluk + dil)

| # | İş | Büyüklük | Kabul |
|---|---|---|---|
| P1-1 | **A4** takvim girdisi canlılık yardımcısı | S | Silinen oturum sonrası girdi havuza alınır/silinir; ızgara ölü id basmaz |
| P1-2 | **A7** yeniden dağıtım/taslağa almada yoklama kayıtları | S | reopen → dağıt → onayla → yoklama tutarlı (test) |
| P1-3 | **A11** yerleşimli salonda plan değişikliği kilidi (ya da snapshot) + kroki uyarısı | M | Plan değişince R1 uyarı üretir ya da değişiklik reddedilir |
| P1-4 | **A12-A14** takasta PINNED, oturum silmede kural/muafiyet, `section_ids` tip doğrulaması | S | Üç test |
| P1-5 | **Sözlük kararı ve uygulaması** (§4.5 K1): ortak/zorunlu, salon/derslik, personel/öğretmen, seviye/sınıf, kapsam; "Özürlü" → "Mazeretli"; "seed" → "Dağıtım numarası"; iç kodlar (K2/K5/R6/R9/R10/F6/R1) yüzeyden çıkar | M | `grep` ile kod sızıntısı sıfır; tek `level_label`; FE testleri güncel |
| P1-6 | **Onay diyaloğu standardı**: Tebellüğ işle, soru dosyası kaldır, takvim taslağa al, oturum onayla (+ onaylayan ad) | S | Her birinde `useConfirm` testi |
| P1-7 | **DAĞITILDI'da "Yeniden dağıt"** (seed/katı mod diyaloğu) | S | Kılavuz ipucu gerçek düğmeye bağlanır |
| P1-8 | **Evrak süre alanı**: `ReportHeader.duration` + ders bazlı süre; R1 künye/sayım, R4, R7, kitapçık bandı | M | Sayfa bütçesi testleri (`iki_yaprak`, `r4 tek yaprak`) yeşil |
| P1-9 | **CI kalite kapısı**: `gates.yml` (pytest+ruff+mypy+FE tsc/eslint/prettier/vitest) her PR'da; `frontend/**` tetikleyicisi | M | Kırmızı test PR'ı bloklar |
| P1-10 | `evrak_ornek.py` fixture'ını katalog adlarına çevir; örnek PDF'leri yenile | S | Karma seviye örnekte görünür |

### 4.3 P2 — Bir ay (evrak + kullanılabilirlik)

| # | İş | Büyüklük | Kabul |
|---|---|---|---|
| P2-1 | **Takvim PDF**: ders saati başlangıcı, onay/düzenleme tarihi, "Okul Zümre Başkanı" slotu kararı, kaymakamlık büyük harf, birim satırı, "9. Sınıf (3)" etiketi, "Uygulamalı" | M | Şablon testleri; örnek PDF |
| P2-2 | **R6**: yazı tarihi, tebliğ eden imzası, görev bitiş saati, salon başına ders | S | Şablon testi |
| P2-3 | **R1/R4**: girmeyen öğrenci numaraları alanı, tespit kutusu, duyuruda imza/kaşe + dayanak dipnotu, kroki hücresinde ders kısaltması (karışık salon) | M | `iki_yaprak` bütçesi korunur |
| P2-4 | Çift yüz: yaprak-1 `break-before: right`; tablo çizgileri ≥0,6 pt; altbilgi tırnak kaçışı | S | 41 öğrencili salon sonrası yaprak-1 sağ sayfada (sayfa numarası testi) |
| P2-5 | Sihirbaz adım kalıcılığı + tıklanabilir Stepper; "Dağıt & Önizle" → "Dağıt"; ön kontrol ad alanı | M | FE testleri |
| P2-6 | Evrak dosya adları (belge + oturum adı + tarih); yükleme/boş durum kalıbı; gezinme sırası; düğme yazım standardı; tırnak/simge birliği | M | Prettier + eslint kuralı (custom) ya da gözden geçirme listesi |
| P2-7 | Takvim uyarılarını kalıcı banda taşı; "Kelebek değil" kutusunu düzen seçicisine çevir; " [U]/(KD)" rozetleri | S | FE testi |
| P2-8 | **A8** medya yedeği kararı + indirme uçlarında `storage.exists` 404 | S/M | Geri yükleme sonrası indirme 404 Türkçe (test) |
| P2-9 | Teknik borç kütüğü ve belgeler: TB8 kapat, TB10 güncelle, kurulum.md okul türü, CLAUDE.md §4 notu, `packaging/README.md` ön-sürüm notu; `.github;C` sil; bayat docstring'ler | S | — |
| P2-10 | Test boşlukları: FE testsiz bileşenler (öncelik `RoomEditor`, `TakvimDetayPage`, `KalemYonetimiDialog`, `DersSubeKapsamiDialog`); backend `okul/services/templates.py`, `persons.py`; frontend kapsam eşiği | L | Kapsam eşikleri gates'te |

### 4.4 P3 — Birikim

- `services.py` bölünmesi (`services_reports`, `services_booklet`,
  `services_proctor`) — imzalar korunarak, motor testleri değişmeden.
- Hata sözleşmesi tekleştirme (`message_dict` her yerde; FE `ApiError.fields`).
- `tr_upper` tek modül; `level_label` tek kaynak.
- N+1: oturum listesi ve takvim önizleme uçlarında `select_related`/toplu sayım.
- OKY metninin `docs/mevzuat/`'a eklenmesi ve tüm madde atıflarının bir kez
  doğrulanması (R1, R7, takvim açıklaması, uyarı metinleri).
- Kitapçık bandında süre ve "Rakamla / Yazıyla" (yaygın uygulama; zorunlu değil).
- Erişilebilirlik: `Autocomplete` ARIA 1.2, onay kutusu boyutları, responsive
  grid'ler; ham renk temizliği.
- TB1/TB2/TB4/TB7 (e-Okul PDF, MTAL çizelgeleri, gözetmen oto-atama, GROUPS)
  mevcut kütükte durur.

### 4.5 Karar gerektiren maddeler (kullanıcı)

| # | Karar | Seçenekler | Öneri |
|---|---|---|---|
| K1 | **Sözlük**: salon mu derslik mi; personel mi öğretmen mi; seviye mi sınıf düzeyi mi; "ortak" yalnız MEB anlamında mı | Tek sözlük dosyası (`frontend/src/lib/sozluk.ts` + backend sabitleri) | "Salon" (sınav bağlamı, mevzuat "sınav salonu"), "Öğretmen" (kullanıcı yüzeyi) / "Personel" (veri modeli), "Sınıf düzeyi" kullanıcıya / `level` kodda; "ortak" yalnız MEB anlamında, ders türü "Zorunlu" |
| K2 | Tek kullanıcıda takvim "Onaya Sun → Onayla" ritüeli | Kalsın (B12 damga değeri) / tek tık | Tek "Onayla" + onaylayan ad alanı (damga korunur) |
| K3 | Medya (soru PDF'leri, kitapçık ZIP'leri) yedeğe girsin mi | Girsin (ksbak büyür, gizlilik yükü) / girmesin + eksikte Türkçe uyarı | Girmesin; sınav sonrası soru dosyası zaten tarihsel değer taşımaz; indirme uçlarında 404 |
| K4 | R8 imza bloğu ve takvim "Okul Zümre Başkanı" slotu | Kaldır / "Sınav işlerinden sorumlu müdür yardımcısı" | İkincisi (Yönerge md. 5/1-b okul geneli sınavı müdürlüğe verir) |
| K5 | OKY metninin depoya alınması | Al (madde atıfları doğrulanır) / atıfları ÖDY-YUSY'ye indirge | Al — kılavuz kuralı bunu gerektiriyor |
| K6 | Evrak süre bilgisi: ders bazlı süre farklıysa R1 sayım tablosunda mı, künyede mi | — | Künye "Süre: 40 dk" + karışık salonda sayım tablosuna "Süre" sütunu |

---

## 5. Bu oturumun doğrulama durumu

`bash scripts/gates.sh` (Docker) 18.09.2026 — **tüm kapılar yeşil**:

| Kapı | Sonuç |
|---|---|
| Depo sızıntısı (KVKK) | 445 izlenen dosyada bulgu yok |
| Backend pytest | 646 geçti; satır kapsamı %87,9 (eşik %75) |
| Backend ruff / ruff format / mypy | temiz |
| Masaüstü + paketleme pytest | 187 geçti; ruff / mypy temiz |
| Frontend tsc / eslint / prettier | temiz |
| Frontend vitest | 58 dosya, 328 test geçti |

Yeni/güncellenen testler: `test_session_api.py::test_shared_booklet_flag_synced_across_siblings`
(yeni semantik), `test_booklets.py::test_shared_booklet_single_file_rule` (yeni
mesaj), `test_session_lifecycle.py::test_revert_to_draft_*` + `test_api_revert_to_draft`,
`test_reports.py::test_karma_seviyeli_oturumda_ders_adi_seviyeli_basilir` ve
`test_r8_yorum_sizintisi_yok`; FE: `SinavSihirbazi.test.tsx` (ders-başı kutu,
tek seviyede bölüm yok), `SorularPaneli.test.tsx` (tek satır/tek yükleme),
`OturumDetayPage.test.tsx` ("Taslağa al").

Ortam notu: bu makinede Docker Desktop bayat AF_UNIX soket dosyaları yüzünden
açılamıyordu; `%LOCALAPPDATA%\Docker\run` ve `docker-secrets-engine` dizinleri
`.bayat-<damga>` adıyla kenara alındı (silinmedi), Docker temiz başladı. Ayrıntı
proje hafızasında.

Değişiklikler çalışma ağacında, **commit edilmedi** (kullanıcı kararı):
`feat(sinav): aynı kitapçık bayrağı ders-başı ayar, taslağa alma, karma seviyede
evrak ders adı, R8 yorum sızıntısı` önerilen başlıktır.

> **Not (19.09.2026):** Yukarıdaki §5, değerlendirmenin yazıldığı andaki durumdur.
> O oturumun değişiklikleri sonradan commit edildi; planın uygulanması ve son
> doğrulama §6'dadır.

---

## 6. Uygulama günlüğü (18-19.09.2026)

Plan `gelistirme/plan-2026-09` dalında uygulandı. K1-K6 kararlarında planın kendi
önerileri benimsendi. Ön yüz işi iki paralel ajana (oturumlar+salonlar+ui /
takvim+kişiler+ayarlar+kılavuz), backend test kapsamı üçüncü bir ajana verildi;
hepsinin işi tek tek gözden geçirilip bu dala alındı.

### 6.1 Kalem kalem durum

| # | Durum | Not |
|---|---|---|
| P0-1 | **Yapılmadı (kullanıcıya bırakıldı)** | Etiket, push ve okulapp.org sürüm kartı dışa açık işlemlerdir; oturumun izin sınıflandırıcısı reddetti. Komutlar §6.4'te |
| P0-2 | Yapıldı | `_room_sheets` yerleşimden beslenir; klasik düzende ve oturum listesi dışına pinlenen salonda R1 basılır |
| P0-3 | Yapıldı | Silme ucu durum kapısından geçer; değiştirilen/kaldırılan soru PDF'i commit sonrası diskten silinir |
| P0-4 | Yapıldı | Birleştirme sınav dersini, takvim girdisini ve seçmeli kapsamı taşır, `conflict_group`'u yeniden yazar; iki ders aynı dağıtılmış oturumdaysa reddeder |
| P0-5 | Yapıldı (genişletildi) | Yalnız ayar ucu değil: `ks_exception_handler` çevrilmemiş her Django `ValidationError`'ı 400'e çevirir ve gerekçeyi `message`'a yazar |
| P0-6 | Yapıldı | R8 idareci diliyle; imza "Düzenleyen — Müdür Yardımcısı"; numara `unlocalize` |
| P0-7 | Yapıldı | Kılavuzda yanlış bilgiler düzeltildi, eksik konular eklendi (yeni "Bakım" adımı dahil) |
| P1-1 | Yapıldı | `has_live_session` / `live_session_ids`; liste ve ızgara yalnız canlı oturum kimliğini döner |
| P1-2 | Yapıldı | `_ensure_no_attendance`: yoklaması alınmış oturumda yeniden dağıtım ve taslağa alma reddedilir |
| P1-3 | **Kısmen (bilinçli)** | Plan değişikliği kilidi konmadı — tek salonu editörden değiştirmek CLAUDE.md'de belgeli bilinçli karardır. Yerine R1 krokisine "N öğrencinin koltuğu güncel salon planında yok" uyarısı ve doğrulamada salon adıyla ihlal |
| P1-4 | Yapıldı | Sabit koltukta takas reddi; oturum silinince kural ve muafiyet temizliği; `section_ids` tip denetimi |
| P1-5 | Yapıldı | `docs/sozluk.md` bağlayıcı; iki ön yüz taraması + backend metinleri (ihlal, uyarı, ret, evrak). İç kod ve `id=` sızıntısı kalmadı |
| P1-6 | Yapıldı | Tebellüğ işleme, soru dosyası kaldırma, takvimi taslağa alma, süreç kalemi pasifleştirme onaydan geçer; oturum onayı onaylayan adını sorar |
| P1-7 | Yapıldı | DAĞITILDI oturumda "Yeniden dağıt" diyaloğu; sonuç ve backend uyarıları diyalogda kalır |
| P1-8 | Yapıldı | Üst bantta süre, R1 sayım tablosunda ders bazlı süre, R6 giriş cümlesinde süre. Kitapçık bandına eklenmedi (`booklet.py` AYNEN) |
| P1-9 | Yapıldı | `.github/workflows/kapilar.yml` kapı betiğini olduğu gibi çağırır (ilk koşusu push'tan sonra görülecek) |
| P1-10 | Yapıldı | Örnek evrak üreticisi gerçek uzunlukta ders adları ve karma seviyeyle çalışır |
| P2-1 | Yapıldı | Antet resmî yazışma düzeninde, ders saati başlangıcı, onay tarihi, "N öğrenci", "(Uygulamalı)" |
| P2-2 | Yapıldı | Tebliğ eden / uygundur imza bloğu, süreli giriş cümlesi, "Gözetmen / Yedek gözetmen" |
| P2-3 | **Kısmen (bilinçli)** | Karışık salonda ders kodu + açıklama, R4'te düzenleyen satırı ve dayanak yapıldı. "Girmeyen öğrenci numaraları" satırı ve büyük tespit kutusu eklenmedi: yaprak 1 bütçesi dolu, bilgi yaprak 2'deki yoklamada var |
| P2-4 | Yapıldı | `break-before: right`, tablo çizgileri, altbilgide CSS kaçışı |
| P2-5 | Yapıldı | Sihirbaz kaldığı adımdan açılır, tamamlanan adımlara tıklanır, ön kontrolde onaylayan adı |
| P2-6 | **Kısmen (bilinçli)** | Dosya adları (`dosyaAdi`), yükleme/boş/hata kalıpları, düğme yazımı, tırnak ve simge birliği yapıldı. Gezinme sırası DEĞİŞTİRİLMEDİ: mevcut sıra günlük kullanım sırasıdır, kurulum sırası değil |
| P2-7 | Yapıldı | Kalıcı `UyariBandi`; "Kelebek değil" kutusu "Düzen" seçimine döndü; tür ve düzen rozetleri |
| P2-8 | Yapıldı | K3 kararı: yedek medyayı kapsamaz (TB11); indirme uçları `media_missing` 404 döner |
| P2-9 | Yapıldı | TB8 kapandı, TB10 güncellendi, TB11/TB12 eklendi; kurulum.md, packaging/README, CLAUDE.md, tasarım §9/§12 |
| P2-10 | Yapıldı | Backend kapsamı %87,9 → %92,9 (≈200 yeni test). Ön yüzde 58 → 69 test dosyası, 328 → 473 test; doğrudan testi olmayan bileşenlerin tamamı üst sayfa testinden geçiyor. Ön yüz kapsam eşiği kapıda: ölçüm satır %89,5 · dal %84,9 · işlev %63,2; eşik 82/78/55 |
| P3 | **Kısmen** | `tr_upper` ve `level_label` tek kaynak, oturum listesi ön-yüklemeli, OKY metni depoda ve atıflar doğrulandı, Autocomplete ARIA 1.2, hata sözleşmesi (servis + serializer retleri `message`'da). `services.py` bölünmesi yapılmadı → TB12 |

### 6.2 Plan dışında bulunup düzeltilenler

Uygulama sırasında ortaya çıkan, değerlendirmede yer almayan gerçek kusurlar:

- **Sayfa bütçesi gerçek adlarla kırılıyordu.** Karma seviye etiketi ("Türk Dili
  ve Edebiyatı — 10. Sınıf") dar "Ders" sütununda sarıp 40 öğrencili R1'i üçüncü,
  R4'ü ikinci sayfaya taşırıyordu; bütçe testleri "Ders 0" gibi kısa adlarla
  koştuğu için yeşildi. Çözüm ders kodu + açıklama; testler artık gerçek
  uzunlukta adlarla koşuyor.
- **Ön-sürüm sıralaması.** `beta.10 < beta.9` (dizge karşılaştırması): onuncu
  ön-sürümde güncelleme hiç önerilmezdi. İki `version_key` kopyası da doğal
  sıralamaya geçti.
- **Pardus'ta Windows kurulum dosyası öneriliyordu.** `can_download` platforma
  bakmıyordu. Artık `platform` alanı var; Linux'ta paketle güncellemeye yönlendirir.
- **Bayat kitapçık paketi.** Yeniden dağıtım, taslağa alma ya da koltuk takasından
  sonra eski ZIP uyarısız indirilebiliyordu; basılırsa kitapçıklar yanlış koltuğa
  giderdi. API `is_stale` döner, Sorular paneli satırı uyarıyla işaretler.
- **İhlal ve uyarı metinlerinde iç kimlikler.** "salon 3 sıra (2,1) pozisyon 0",
  "'10:9' grubundan", "id=42", "AYRI_SALON kuralına". Artık salon adı, ders adı,
  okul numarası ve krokiyle aynı sayımda "3. sıra, 1. sütun".
- **Süreç kalemi adı çakışması** genel "Gönderilen veride hatalar var" cümlesinin
  arkasında kalıyordu (DRF alan düzeyi `UniqueValidator`); **boş takvim adı**
  güncellemede kabul ediliyordu.
- **"Gerekirse geri alınabilir" vaadi.** Kişi silme onayı böyle diyordu ama geri
  alma ucu yok. Doğrusu yazıldı.
- **Seçmeli ders şubeleri diyaloğu** kayıtlı şubeler okunamadan "Kaydet"e izin
  veriyordu; kayıt tam değiştirme yaptığı için boş seçim var olan tanımı
  silebiliyordu.
- **Onaylı görünen taslak takvim.** Backend taslağa alınan takvimin eski onay
  damgasını saklıyor; önizleme damgayı her durumda basıyordu.
- **"Kendi dersliğinde" düzeninde** dağıtım numarası (hep 0), katı dağıtım ve
  dönüşümlü oturma hem sihirbazda soruluyor hem R8'de basılıyordu.
- **`formatDateTime`** günü sıfırsız basıyordu ("1.06.2026"); aynı ekranda iki
  yazım çıkıyordu.

### 6.3 Bilinçli olarak yapılmayanlar ve açık kalanlar

- **`services.py` bölünmesi (TB12).** Saf taşıma işidir; düzeltme turuyla aynı
  dalda yapılırsa inceleme ve `git blame` izi bozulur. Ayrı oturuma bırakıldı.
- **Ön yüz işlev kapsamı düşük (%63).** Satır içi olay işleyicileri ayrı işlev
  sayıldığı için satır/dal oranının altında kalır; eşik buna göre 55'tir.
  Kapsamlı koşu kapıyı yaklaşık yüzde otuz uzatır (205 sn → 267 sn) — kabul edildi.
- **Silinen kişiyi geri alma ucu.** Şifreli ad alanları ve numara tekliği
  yüzünden küçük iş değildir; ihtiyaç doğarsa ayrı kalem.
- **`ExamTrackItem` DELETE ucu** duruyor ama arayüz artık çağırmıyor (yerine
  pasifleştir/etkinleştir). Zararsız; kaldırılması ayrı bir API temizliği.
- **TTK çizelgesindeki "Ortak Dersler" başlığı** ile programdaki "Zorunlu" türü
  arasında kılavuzda köprü cümlesi yok. Sözlük "ortak" sözcüğünü yalnız MEB'in
  okul geneli sınavına ayırıyor; istenirse Ders Havuzu yardım metnine tek cümle
  eklenebilir.
- **Gezinme sırası** ve **R1 yaprak 1'e ek alanlar**: yukarıda gerekçeli.

### 6.4 Son doğrulama ve yayın adımları

`bash scripts/gates.sh` (Docker), 19.09.2026, plan dalının son ucunda — **tüm
kapılar yeşil**:

| Kapı | Değerlendirme anı (§5) | Uygulama sonu |
|---|---|---|
| Depo sızıntısı (KVKK) | bulgu yok | bulgu yok |
| Backend pytest | 646 test, kapsam %87,9 | **855 test, kapsam %92,9** (eşik %75) |
| Backend ruff / ruff format / mypy | temiz | temiz |
| Masaüstü + paketleme pytest, ruff, mypy | 187 test, temiz | 187 test, temiz |
| Ön yüz tsc / eslint / prettier | temiz | temiz |
| Ön yüz vitest | 58 dosya, 328 test | **69 dosya, 473 test** |
| Ön yüz kapsamı (yeni kapı) | ölçülmüyordu | satır %89,5 · dal %84,9 · işlev %63,2 (eşik 82/78/55) |

Tam koşu bir kez kırmızı verdi ve işe yaradı: değiştirilen bir ret metnine bağlı
test beklentisi (alt küme koşularında görünmeyen) ancak tam zincirde yakalandı.

**Yapılmayan yayın adımları.** Etiket, push ve site kartı dışa açık işlemlerdir;
otonom oturumda izin verilmedi ve dolanılmadı. `VERSION` bilerek `2026.9.0-beta.5`
olarak bırakıldı (etiketsiz yükseltme, paketleme hattının VERSION↔etiket kapısını
şaşırtır). Sırayla:

1. `git push origin main` — kapılar GitHub'da ilk kez koşar (`kapilar.yml`).
2. `VERSION` dosyasını `2026.9.0-beta.6` yapıp commit edin
   (`chore(surum): 2026.9.0-beta.6`), sonra `git tag v2026.9.0-beta.6` ve
   `git push origin main v2026.9.0-beta.6` — paketler üretilir, Release açılır,
   dosyalar indirme alanına yüklenir.
3. Paketler çıkınca `okulapp.org` deposunda `src/data/ks-release.json` güncellenir
   (o deponun "Ortak çalışma düzeni" kurallarıyla: taze `origin/main`, yalnız
   kendi alanı, commit başlığı "Kelebek Sınav: …").
4. P0-1'in kabul ölçütü pakette sınanır: TDE 9 + TDE 10 oturumu → dağıt → iki
   soru dosyası → kitapçık; ardından "Taslağa al" ve "Yeniden dağıt".
