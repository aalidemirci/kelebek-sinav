# Kelebek Sınav — Arayüz Sözlüğü ve Yazım Kuralları

*18.09.2026 · Değerlendirme raporu K1 kararı. Kullanıcıya görünen HER metin
(etiket, düğme, başlık, snackbar, hata, boş durum, kılavuz, evrak) bu sözlüğe
uyar. Kod tanımlayıcıları (İngilizce) ve kod yorumları kapsam dışıdır.*

Hedef okur mevzuata hâkim bir okul idarecisidir; yazılımcı değildir. Metin
onun diliyle konuşur: MEB terimleri MEB anlamıyla kullanılır, programın iç
kavramları (faz/karar/evrak kodları, motor ölçütleri) yüzeye çıkmaz.

## 1. Kavram sözlüğü

| Kavram (kod) | Kullanılır | Kullanılmaz | Not |
|---|---|---|---|
| `ExamRoom` | **salon**, sınav salonu | derslik (genel ad olarak) | "Derslik" yalnız iki yerde kalır: düzen adı **"Kendi dersliğinde"** ve bir şubeye bağlı salon için **"şube dersliği"** ("Şube dersliklerini oluştur") |
| `ExamRoomGroup` | **salon kümesi** | derslik kümesi | Düğme: "Salon kümeleri" |
| `ClassSectionGroup` | **şube kümesi** | — | |
| `Personnel` (arayüz) | **öğretmen** | personel | "Personel" yalnız e-Okul raporunun adı geçerken ("Personel Listesi raporu") |
| `level` etiketi | **sınıf düzeyi** | seviye | Değer biçimi: **"9. Sınıf"**, "Hazırlık" (tek kaynak: `gradeLevelLabel` / `level_label`) |
| Katılımcı kapsamı (`participant_type`) | alan adı **"Katılımcılar"**; seçenekler **"Sınıf düzeyinin tamamı"** / **"Seçili şubeler"** | "Katılımcı tipi", "Seviye geneli", "Şube şube", tek başına "Kapsam" | Oturum sihirbazı ve takvim aynı sözcükleri kullanır |
| `CourseType.COMMON` | **Zorunlu** (ders) | Ortak (ders) | |
| `CourseEnrollment` (seçmelinin şube listesi) | **öğrenci listesi**; şube durumu **"şubenin tamamı"** / **"N öğrenci (şubenin bir kısmı)"**; iki listenin kesişimi **"iki dersi birden alan öğrenci"** | ders grubu, grup listesi, ortak öğrenci | e-Okul raporu adıyla anılır: "OOK10002R010 - Seçmeli Ders Öğrencileri" |
| ortak sınav / ortak yazılı | yalnız MEB anlamında: okul (ya da il/ilçe/ülke) geneli sınav | başka hiçbir anlamda "ortak" | |
| `shared_booklet` | **"tüm seviyeler aynı kitapçık"**, kısa: "aynı kitapçık" | ortak kitapçık | |
| `seed` | **dağıtım numarası** | seed, tohum, çekirdek sayı | İlk geçtiği yardım metninde bir kez "(seed)" parantezi olabilir; R8'de "Dağıtım numarası (seed)" |
| sert kısıt ihlali | **kural ihlali** | sert kısıt, "İHLAL = 0", halka, yakınlık skoru | Motor ölçütleri yalnız "Ayrıntı" açılır bölümünde ve R8'in teknik bölümünde |
| katı mod | **Katı dağıtım** — "yan, ön ve arka komşuluk da kesinlikle yasak" | "Katı mod (1. halka…)" | |
| `SeparationMode` / `separation_key` | **kız/erkek ayrışması**; seçenekler **Kapalı** / **Aynı sıraya oturtma** / **Ayrı salonlar**; öğrenci alanı **Cinsiyet** (Belirtilmemiş / Kız / Erkek) | DESK, ROOM, ayrışma anahtarı, "cinsiyet kısıtı", "karma oturma" | Kural okulun TERCİHİDİR (mevzuat dayanağı yok), varsayılan Kapalı. Cinsiyet hiçbir evraka/dışa aktarıma basılmaz, listede sütun olmaz; R8'e yalnız kuralın adı girer |
| `ExcuseStatus` | **Beklemede / Mazeretli / Mazeretsiz** | Özürlü / Özürsüz | Mevzuat "mazeret" der |
| `ParticipantType.MAKEUP` | **"Mazeretli öğrenciler"** (ders satırında) | "mazeret grubu", "üçüncü tip" | "Katılımcılar" SEÇENEĞİ değildir — satırı yalnız Mazeret Takibi ekranı kurar |
| `MakeupPlan` | **mazeret sınav takvimi** (sekme: **Mazeret Takvimi**); belgeleri **"Takvim (PDF)"** = adsız ilan nüshası, **"Öğrenci listesi (PDF)"** | mazeret planı, telafi takvimi | Çizelgesi de "yerleştirme çizelgesi"dir; sıra kipi kullanıcıya "Asıl takvim sırasını kesin koru" diye sorulur |
| `ExamSession.is_makeup` | rozet **"Mazeret sınavı"**; ekran **Mazeret Takibi**; rapor **Mazeret Takip Çizelgesi** | telafi sınavı, bütünleme | Mevzuat "mazeret sınavı" der (OKY md. 48/1) |
| `SubjectDepartment.branches` | **branş** (zümrenin branşları); düğmeler **"Branşlardan zümre üret"**, **"Branşları düzenle"**; kutu **"Başkan adaylarında tüm öğretmenleri göster"**; aday notları **"yeni zümre"** / **"“X” zümresinde"** / **"“X” zümresi var — branşı ona bağlanır"** | alan, bölüm, departman; NEW/LINKABLE/COVERED gibi durum kodları | Branş öğretmen listesindeki (e-Okul) metindir; "Coğrafya" ile "COĞRAFYA" aynı branştır. Bir branş yalnız bir zümrede olabilir |
| `IepStudent` | **BEP kapsamındaki öğrenciler** (liste; Kişiler'de sekme: **BEP**) | kaynaştırma listesi, özel öğrenci, engelli listesi | Yalnız üyelik; tanı/açıklama alanı yoktur ve eklenmez. "BEP" sözcüğü YALNIZ bu listede, oturum panelindeki bölüm başlığında ve idare özetinde geçer |
| `IndividualQuestionDocument` | **bireysel soru dosyası**; karşıtı **"dersin soru dosyası"**; düğme **"Bireysel soru dosyası uygula"** / **"Seçimi kaldır"**; durum **"Dosya yüklenmedi"** | ortak kitapçık/ortak kâğıt (karşıtı için), BEP kâğıdı, özel sınav, ayrı kâğıt | "Ortak" yalnız MEB anlamındadır. Onay ve hata metninde öğrenci adı/numarası geçmez: "Bu öğrenci…" |
| BEP idare özeti | **"İdare özeti (PDF)"**; belge adı **BEP Kapsamındaki Öğrenciler — İdare Özeti** | BEP raporu, gözetmen notu, bilgi notu | Salonlara dağıtılmaz; "Tümünü indir" paketine girmez |
| Kitapçık üretiminin bayatlığı (`is_stale`) | **"Güncel değil — yeniden üretin"** | "Eski yerleşime göre" (tek nedeni söylüyordu) | Neden yerleşim de olabilir, bireysel soru dosyası da |
| Oturum durumu | **Taslak / Dağıtıldı / Onaylandı / Arşivlendi** | Arşiv | |
| Kitapçık üretim kaydı | **"Üretim"** + tarih-saat | Koşu #n | |
| `LayoutMode` | **Kelebek** / **Kendi dersliğinde** | "Kelebek değil", "klasik", "(KD)" | Seçim alanı adı: "Düzen" |
| `ExamKind.PRACTICE` rozeti | **Uygulama** | "[U]", "[UYGULAMA]" | Evrakta "Uygulamalı" |
| takvim yerleştirme ızgarası | **yerleştirme çizelgesi** | ızgara | |
| mükerrer ders birleştirme hedefi | **asıl kayıt** | kanonik kayıt | |
| ders takma adı | **takma ad** | alias | |
| kayıt silme (kişi, salon, ders) | "silinmez, gizlenir: geçmiş evrak değişmez" | soft delete | Geri alma ucu YOKTUR; "geri alınabilir" denmez. Yanlış silinen kişi yeniden eklenir ya da içe aktarılır |
| yedek şifrelemesi | "güçlü şifrelemeyle korunur" | X25519, AES-256-GCM, NAS | Teknik adlar yalnız Hakkında sayfasında |
| sürüm kaynağı | "yayımlanan son sürüm", "kurulum dosyası" | GitHub sürümü, Release, kurucu | |

## 2. İç kodlar yüzeye çıkmaz

Karar, faz ve evrak kodları kullanıcı metninde GEÇMEZ: `K2`, `K5`, `F6`, `R1`,
`R4`, `R5`, `R6`, `R7`, `R8`, `R9`, `R10`, `TB…`, `U2`, "Tur nnn". Evrak
kodunun yerine belgenin adı yazılır:

| Kod | Ad |
|---|---|
| R1 | Salon Sınav Evrakı |
| R4 | Şube Sınav Duyurusu |
| R5 | Toplu Dağıtım Çizelgesi |
| R6 | Gözetmen Görevlendirme Yazısı |
| R7 | Sınav İhlal ve Kopya Tutanağı |
| R8 | Dağıtım Doğrulama Raporu |
| R10 | Kişiselleştirilmiş kitapçıklar |

Bu adlar ARAYÜZ ve indirilen dosya adları içindir. Basılı belgenin başlığı
resmî işlevini söyler ve daha uzun olabilir: gözetmen yazısının başlığı
"GÖZETMEN GÖREVLENDİRME VE TEBLİĞ-TEBELLÜĞ BELGESİ"dir (öğretmen imzasıyla
tebellüğ eder) — fark bilinçlidir, başlık kısaltılmaz.

Açıklanmamış kısaltma kullanılmaz (KSD, KD, U). Kod yorumlarında ve testlerde
kodlar serbesttir.

## 3. Yazım kuralları

- **Düğmeler cümle düzenindedir:** "Onaya sun", "Taslağa al", "Oturum üret",
  "Kalem yönetimi", "Ön tanımlı takvimleri üret". Sayfa/sekme/bölüm
  **başlıkları** Başlık Düzenindedir: "Ders ve Katılımcılar".
- **Devam düğmesi** tek biçim: "Kaydet ve devam et" (kayıt yoksa "Devam").
  Vazgeçme: "Vazgeç"; salt bilgi diyaloğunda "Kapat".
- **Seçici yer tutucusu** tek biçim: "Seçin". Boş seçenek: "— yok —".
- **Tırnak:** JSX metninde “ ” (kıvrık). Kesme işareti düz `'`.
- **"resmî"** düzeltme işaretiyle yazılır ("resmi" değil).
- **Simgeler** `Icon` bileşeniyle verilir; metne ham "✓" / "⚠" yazılmaz.
- **Tarih/saat** yalnız `lib/format.ts` yardımcılarıyla (`formatDate` gg.aa.yyyy,
  `formatDateTime`); `toLocaleString`/`toISOString` ile yerel kopya yazılmaz.
- **Koltuk koordinatı** kullanıcıya 1 tabanlı ve sözle: "3. sıra, 1. sütun, sol
  koltuk (koltuk no 5)". Sıra içi konum: sol / orta / sağ.
- **Snackbar** tam cümledir ve noktayla biter; her durum geçişinin kendi
  cümlesi vardır ("Takvim onaya sunuldu.", "Takvim onaylandı.").
- **Geri dönüşü olmayan ya da damga düşüren her işlem** `useConfirm` onayından
  geçer; onay diyaloğunun başlığı soru, gövdesi sonuçtur (ikisi aynı cümle olmaz).
- **İndirilen dosya adı** belge adı + oturum/takvim adı + tarih taşır:
  `Salon-Sinav-Evraki_1-Ortak-Sinav_16.11.2026.pdf` (`lib/download.ts::dosyaAdi`).
- **Hata metinlerinde öğrenci adı asla** (okul numarası) — CLAUDE.md §1.6.

## 4. Sayfa ve gezinme adları

Gezinme etiketi kısa, sayfa başlığı (h1) tam addır ve üst çubuktaki başlıkla
AYNIDIR: Genel Bakış · Sınav Takvimleri (gezinme: Takvimler) · Sınav Oturumları
(Oturumlar) · Mazeret Takibi · Sınav Salonları (Salonlar) · Kişiler · Ders Havuzu ·
Ayarlar · Kullanım Kılavuzu (Kılavuz) · Hakkında ve Lisans.
