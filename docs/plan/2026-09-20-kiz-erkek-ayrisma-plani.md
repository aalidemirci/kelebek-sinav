# Plan — Kız/erkek ayrışması (aynı sıraya oturtmama · ayrı salonlar)

> **Durum:** PLAN — kod YAZILMADI. 20.09.2026'da hazırlandı, aynı gün kullanıcı
> kararıyla revize edildi (§2 K1). Uygulamayı başka bir oturum (Opus 5) devralacak.
> Bu belge tek başına okunabilir olmalıdır: önce §0'ı (çalışma ağacının durumu),
> sonra §2'yi (alınmış ve açık kararlar) okuyun.
>
> İstek (kullanıcı, 20.09.2026): "kız/erkek aynı sırada oturmasını engelleyen veya
> farklı salonlarda sınav olmalarını sağlayan bir özelliğimiz var mı? bazı okullarda
> gerekli olabilir." · Revizyon: "cinsiyet bilgisi zaten e-okul sınıf listelerinde
> var. ordan alalım. herhangi bir yerde yayınlanmayacağı ve hizmet gereği sadece yerel
> cihazda işlendiği/kullanıldığı için kvkk açısından da sorun olmaz. şube işaretleme
> yerine direkt rapordan bu verileri alacak bir planlama yapalım. kullanıcıya ek iş
> çıkarmayalım."

## 0. Başlamadan önce — çalışma ağacı TEMİZ DEĞİL

20.09.2026 oturumunda iki özellik yazıldı, tam kapı (`bash scripts/gates.sh`) iki
kez yeşil geçti, çalışan uygulamada uydurma veriyle doğrulandı, ama **commit
edilmedi** (kullanıcı talimatı beklendi):

1. **BEP kapsamındaki öğrenciler + bireysel soru dosyası** — `backend/apps/sinav/
   {services_individual,views_individual,question_pdf}.py`, `migrations/0016_*`,
   `templates/sinav/reports/bep_idare_ozeti.html`, `tests/test_individual_questions.py`,
   `frontend/src/modules/bep/**`, `oturumlar/SoruYuklemeDialog.tsx`,
   `docs/mevzuat/ozel-egitim-hakkinda-khk-573.md` + `sinav/{models,services,selectors,
   serializers,urls,apps,booklet}.py`, `okul/services/persons.py` değişiklikleri.
2. **Zümrelerin branştan üretimi** — `backend/apps/okul/{models,serializers,views,
   urls}.py`, `okul/services/departments.py`, `okul/migrations/0010_*`,
   `shared/text.py` (+ `shared/tests/test_text.py`), `dersler/text.py`,
   `frontend/src/modules/ayarlar/ZumrelerPaneli.tsx`, `okul/api.ts`.

**Ortak dosyalar** (iki özellik de dokundu): `CLAUDE.md`, `docs/sozluk.md`,
`docs/tasarim/2026-08-29-genel-tasarim.md`, `docs/teknik-borc.md`,
`frontend/src/modules/kilavuz/KilavuzPage.tsx(+test)`,
`frontend/src/modules/kisiler/KisilerPage.tsx(+test)`. Bu yüzden yola göre iki TEMİZ
commit çıkmaz (`git add -p` bu ortamda yok). Öneri: kullanıcıya sorun; onay verirse
**tek commit** atın ki her commit kapıdan geçsin:

```
feat(sinav,okul): BEP bireysel soru dosyası ve zümrelerin branştan üretimi
```

Yeni işe bu commit'ten SONRA, ayrı bir dalda başlayın (global kural: commit/push
yalnız kullanıcı isteyince; varsayılan dalda iseniz önce dal açın). Bu plan dosyası
da o commit'e girebilir. Kullanıcıya hâlâ açık duran iki soru: (a) BEP idare
özetinin KVKK dipnotunda md. 6/3 bendi yazılsın mı (aday 6/3-b + 573 KHK md. 16/1 —
teknik borç TB16); (b) zümrelerin kendiliğinden üretimi yalnız katalog boşken
çalışıyor — itirazı var mı.

## 1. Durum tespiti — özellik bugün YOK

- Program cinsiyet verisini **hiç toplamıyor**. e-Okul OOG01001R020 (Sınıf/Şube
  Öğrenci Listesi) Excel'inde **"Cinsiyeti" sütunu VAR**: blok başlığı `S.No |
  Öğrenci No | Adı | Soyadı | Cinsiyeti | Pansiyon Durum` (`backend/apps/okul/
  eokul.py` modül açıklaması). `eokul.duzlestir_sinif_listesi` bu başlığı ve sütunu
  düz matrise TAŞIR; sütun yalnız `excel_ogrenci.COLUMN_SYNONYMS`te karşılığı
  olmadığı için atılır. Yani okuma tarafı küçük bir iştir.
- Kelebek motorunda tek sert kısıt: **aynı çakışma grubundan** (`conflict_group` =
  aynı ders+düzey) iki öğrenci aynı sırada oturamaz (`engine._pair_penalty`,
  `validator.validate_seating`). Şube de cinsiyet de kısıt DEĞİL.
- OYS ADR-0016 K8'de "E3 kız-erkek (varsayılan kapalı)" diye bir ESNEK kısıt fikri
  vardı (`docs/kesif/2026-08-29-kesif-raporlari.md` §1.1); OYS kodunda karşılığı yok
  (`git -C ../okulapp grep -i "gender\|cinsiyet" origin/main -- backend/apps/
  sinav_islemleri` boş döner — 20.09.2026'da denetlendi). DD/OYS'de `normalize_gender`
  vardı (E/ERKEK/MALE/M/B/BAY→'E', K/KIZ/FEMALE/F/BAYAN→'K'); KS'ye alınmamıştı.

## 2. Kararlar

### Alınmış (kullanıcı, 20.09.2026) — yeniden tartışmayın

- **K1 — Kaynak öğrenci bazlı cinsiyettir ve e-Okul sınıf listesinden KENDİLİĞİNDEN
  okunur.** Şube işaretleme YOK; okul ayarına bağlı "oku/okuma" anahtarı YOK —
  kullanıcıya ek iş çıkarılmaz. Gerekçesi (kullanıcının): veri zaten e-Okul
  listesinde, hiçbir yerde yayınlanmıyor, yalnız yerel cihazda ve hizmet gereği
  işleniyor. Bu, tasarım §5'teki "demografi alanı yok" tutumunu BİLİNÇLE değiştirir;
  belgeleri güncelleyin (§3.6). Önceki plan taslağındaki "şube bazlı ayrışma grubu"
  seçeneği DÜŞTÜ.

### Açık — kod yazmadan ÖNCE `AskUserQuestion` ile sorun (öneri ilk seçenek)

- **K2 — Kural düzeyi:** oturum bazında üç değerli seçenek — `Kapalı` / `Aynı sıraya
  oturtma` / `Ayrı salonlar`; okul genelinde varsayılanı Okul Bilgileri'nden gelir
  (ihtiyacı olan okul bir kez ayarlar, her oturumda yeniden seçmez — "ek iş yok"
  ilkesi). Varsayılanın varsayılanı KAPALI.
- **K3 — Sert mi esnek mi:** öneri SERT (mevcut aynı-grup kuralıyla aynı muamele):
  sağlanamazsa ihlal listelenir ve oturum ONAYLANAMAZ; idareci salon ekler ya da
  kuralı gevşetir. (OYS fikri esnekti; esnek kural garanti vermez.)
- **K4 — Cinsiyeti bilinmeyen öğrenci** (elle eklenmiş ya da eski aktarımdan kalmış):
  öneri "joker" — sıra kuralına girmez; ayrı salon kuralında boş kapasitesi en çok
  olan bölüme eklenir ve UYARI üretilir ("N öğrencinin cinsiyet bilgisi yok — e-Okul
  sınıf listesini yeniden aktarın").
- **K5 — Yerleştirme kuralıyla (pin) çakışma:** öneri "pin kazanır + uyarı" (emsal:
  pin > satranç düzeni). Doğrulayıcı bunu ihlal sayacak mı? Sayarsa oturum
  onaylanamaz, idareci pini kaldırmak zorunda kalır.
- **K6 — "Kendi dersliğinde" düzeni + karma şube:** bu düzende öğrenciler okul no
  sırasıyla oturur ve ayrışma kısıtı hiç uygulanmaz. Öneri: "Aynı sıraya oturtma"
  açıkken şube içinde önce bir grup sonra öteki (her biri okul no sırasıyla),
  sınır bir sıranın ortasına düşerse bir koltuk atlanır; "Ayrı salonlar" bu düzende
  anlamsızdır (herkes kendi dersliğinde) → seçilirse açık ret mesajı. Kullanıcı
  1. aşamada bunu kapsam dışı bırakmak isteyebilir — sorun.

**Sormadan uygulanacaklar:** varsayılan KAPALI · cinsiyet HİÇBİR evraka, kitapçığa,
dışa aktarıma (R5 Excel dahil) ve listeye basılmaz · R8'e yalnız kuralın adı ve ihlal
sayısı girer · ihlal/uyarı metninde öğrenci ADI geçmez (okul no geçer) · ekranda
koltuk kartlarına K/E rozeti konmaz.

## 3. Teknik tasarım

### 3.1 Soyutlama: motor cinsiyet bilmez, "ayrışma anahtarı" bilir

`participants.Participant` ve `validator.PlacedStudent`e VARSAYILANLI tek alan:
`separation_key: str = ""` (emsal: `focus` ve etiket alanları — eski çağıranlar ve
motor testleri değişmeden yeşil kalmalı). Anahtarı SERVİS katmanı öğrencinin
cinsiyetinden üretir ("K" / "E" / boş = joker). Motor ve doğrulayıcı yalnız "iki boş
olmayan anahtar farklı mı?" diye sorar — böylece motor sözleşmesi cinsiyete değil
soyut bir ayrışmaya bağlanır ve test verisi kişisel veri taşımaz.

### 3.2 Veri: e-Okul'dan kendiliğinden okuma (kullanıcıya ek iş YOK)

- `okul.Student.gender` — `EncryptedCharField(max_length=1, blank=True, default="")`,
  değerler "K" / "E" / boş; adlarla AYNI koruma (parola açıkken şifreli;
  `encrypted_field_map` kendiliğinden kapsar). Göç `okul/0011`. Şifreli alanda DB
  süzmesi çalışmaz — cinsiyete göre süzme/sayma Python'da (CLAUDE.md §2 "Şifreli alan
  sorguları"). `Student` model açıklamasındaki "demografi alanı YOKTUR" cümlesini
  güncelleyin.
- `okul/normalize.py`: `normalize_gender(value) -> str` geri gelir (DD'deki eşleme:
  E/ERKEK/BAY/B/M/MALE→"E", K/KIZ/BAYAN/F/FEMALE→"K"; tanınmayan → ""), TR-duyarlı
  katlamayla (`_ascii_upper`). Modül başlığındaki "cinsiyet … KALDIRILDI" notunu
  güncelleyin; `tests/test_normalize.py`'ye testini ekleyin.
- `okul/excel_ogrenci.py`: `COLUMN_SYNONYMS["gender"] = ["cinsiyeti", "cinsiyet"]`
  (KRİTİK DEĞİL — `CRITICAL_FIELDS`e girmez; sütun yoksa aktarım aynen çalışır),
  `ParsedRow.gender`. Eşleme sırasına dikkat: `_match_field_for_header` alt dize
  arar ("adi" ⊂ "soyadi" dersi) — "cinsiyeti" başka bir anahtarı içermiyor, yine de
  testle sabitleyin. Modül başlığındaki "cinsiyet sütunları KALDIRILDI" notunu
  güncelleyin.
- `okul/eokul.py`: `duzlestir_sinif_listesi` "Cinsiyeti" sütununu zaten taşıyor —
  sentetik örnek üretici (`tests/veri/uret_eokul_ornekleri.py`) sütunu zaten yazıyor;
  test_eokul'a "cinsiyet düz matriste korunur" iddiası ekleyin. Dipnot satırları
  ("Kız/Erkek/Toplam Öğrenci Sayısı") bugünkü gibi boşaltılmaya devam etmeli.
- `okul/services/imports.py::_process_student_row`: yeni kayıtta yaz; mevcut kayıtta
  YALNIZ dolu ve farklıysa güncelle (boş gelen değer kayıtlı cinsiyeti SİLMEZ —
  personelde `title/branch` emsali). Önizleme = gerçek yazım + geri alma paritesi
  bozulmamalı; rapor sayaçlarına dokunmayın (cinsiyet farkı "güncellenen" sayılır).
- **Eski kurulumlar:** öğrenciler cinsiyetsiz aktarılmış durumda. Çözüm kullanıcının
  aynı e-Okul sınıf listesini BİR KEZ yeniden yüklemesidir (upsert okul numarasıyla;
  "bu içerik daha önce aktarılmış" uyarısı engel değildir). Program bunu kendisi
  söylemeli: kural açıkken cinsiyeti boş öğrenci varsa dağıtım uyarısı + Okul
  Bilgileri'ndeki seçeneğin altında sayaç ("312 öğrenciden 40'ının cinsiyet bilgisi
  yok — e-Okul sınıf listesini yeniden aktarın").
- Elle eklenen öğrenci için Kişiler'deki düzenleme diyaloğuna isteğe bağlı "Cinsiyet"
  seçimi (— / Kız / Erkek). Listeye SÜTUN eklemeyin. Uygulama şablonuna (sınıf, no,
  ad, soyad) isteğe bağlı "Cinsiyet" sütunu eklenebilir; zorunlu değildir.
- Kişiler ekranındaki içe aktarma ipucu ("cinsiyet, pansiyon okunmaz") ve sayfa
  açıklaması güncellenmeli: cinsiyet okunur, yalnız yerleşim kuralında kullanılır,
  hiçbir belgeye basılmaz; pansiyon yine okunmaz.
- `sinav.SeatAssignment.separation_key` (SNAPSHOT deseni — CLAUDE.md §3): arşiv
  oturumun yeniden doğrulaması ve R8 yeniden basımı canlı öğrenci verisine bağlı
  kalmasın. Göç `sinav/0017`. Ad gibi şifreli mi? Tek harf + öğrenci bağı olduğundan
  EVET (`EncryptedCharField`); F27 anonimleştirmesinde ad/no ile birlikte BOŞALTIN
  (anonim arşivde kuralın yeniden doğrulanması gerekmez; R8 sayıları
  `distribution_params`ta durur — bunu test edin).
- `okul.SchoolConfig.default_separation_mode` (NONE/DESK/ROOM, varsayılan NONE) ·
  `sinav.ExamSession.separation_mode` (yeni oturumda okul varsayılanından dolar;
  yalnız TASLAKta değişir; `copy_session_plan` kopyalar; dağıtımda
  `distribution_params`a yazılır ki R8 basabilsin).

### 3.3 Motor (`sinav/engine.py` — 31.08.2026'dan beri AYNEN sınıfında DEĞİL)

DEĞİŞMEYECEK sözleşmeler (CLAUDE.md §3): sert kısıt denetimi `(desk_row, desk_col)`
KİMLİĞİNDEN (mesafeden değil) · aynı seed → aynı dağıtım (yeni `rng` çekilişi
eklemeyin) · ceza demeti leksikografik, ikincil bileşen ihlal sayısını artıramaz.

- **ÖNCE altın kayıt alın:** motoru değiştirmeden önce sabit seed'li 3-4 senaryonun
  yerleşimini (öğrenci → salon, koltuk) bir teste dökün. Kural KAPALIYKEN yeni motor
  bu çıktıları BİT BİT vermelidir (regresyon kapısı).
- **Sıra düzeyi (DESK):** bugün `_placement_penalty` ve `_student_penalty_at`
  yalnız AYNI gruptan çiftlere bakar (`if other_group != group: continue`) ve
  `occupied` listesi `(Seat, grup)` taşır. Listeyi `(Seat, grup, ayrışma)` yapın;
  aynı sıradaki (dr == 0 ve dc == 0) iki boş olmayan FARKLI anahtar için birincil
  ceza `math.inf`. Bu çift farklı gruptan da olabilir — `continue`den ÖNCE
  denetleyin. `_local_search` takaslarında ve pinli (`fixed`) yerleşimlerde de aynı
  demet kullanılmalı.
- **Salon düzeyi (ROOM):** `distribute_butterfly`den ÖNCE servis katmanında bölün:
  katılımcıları anahtara göre ayırın, salonları kapasite ihtiyacına göre bölüştürün
  (deterministik: salonları kullanım sırasıyla gezin, ihtiyacı en büyük bölümden
  başlayın), her bölüm için motoru AYNI seed'den türeyen sabit alt seed'le
  (`seed + bölüm sırası`) çağırın, sonuçları birleştirin. Bölüşüm imkânsızsa
  (salon sayısı < bölüm sayısı ya da kapasite yetmiyor) `ValidationError`:
  "Ayrı salon kuralıyla kız öğrenciler için X, erkek öğrenciler için Y koltuk
  gerekiyor; seçili salonlar bu bölüşüme yetmiyor. Salon ekleyin ya da kuralı 'Aynı
  sıraya oturtma' yapın." (iç kod, kimlik yok).
- Satranç düzeni (tek grup + bol kapasite) sıra kuralını kendiliğinden sağlar;
  baskın grup uyarısı bölüm başına hesaplanmalı.
- Fizibilite notu: ikili sırada yan yana oturanlar zaten FARKLI dersten olmak
  zorunda; yeni kural "farklı ders + aynı cinsiyet" ister. Dar kapasitede ihlalsiz
  çözüm çıkmayabilir — mevcut davranış korunur: en iyi çözüm + açık ihlal listesi +
  onay engeli.
- `distribute_home_classroom`: K6 kararına göre (blok sıralama + sınırda koltuk
  atlama ya da kapsam dışı).

### 3.4 Doğrulayıcı (`sinav/validator.py` — motordan HİÇBİR ŞEY import etmez)

`validate_seating`e kip parametresi (`separation: str = "NONE"`); DESK: aynı
`(room_id, desk_row, desk_col)`'da iki farklı boş olmayan anahtar → sert ihlal;
ROOM: aynı salonda iki farklı boş olmayan anahtar → sert ihlal. Metin idareci
diliyle ve etiket alanlarından (`room_label`, `desk_label`, `student_number`):
"D-201 salonu, 3. sıra, 1. sütun: kız ve erkek öğrenci aynı sırada (okul no 101 ve
205)". Öğrenci ADI yazılmaz (CLAUDE.md §1.6). `services.seating_report`,
`swap_seats` ve `approve_session` kipi oturumdan okuyup geçirir — elle takas sonrası
ihlal görünür ve onay engellenir (mevcut akış).

### 3.5 Servis / API / arayüz

- `services.distribute_session`: anahtarları üret (3.1 — yerleşen öğrencilerin
  cinsiyeti TEK sorguda, Python'da), kipi uygula, uyarıları
  `distribution_params["warnings"]`a ekle (cinsiyeti boş öğrenci sayısı, pin
  çakışması). `participants.py` AYNEN sınıfındadır — imza değiştirmeyin; varsayılanlı
  alanı serviste doldurun.
- Ayarlar → Okul Bilgileri: "Kız/erkek ayrışması" varsayılanı + cinsiyeti boş öğrenci
  sayacı (yalnız kural açıkken). `SinavSihirbazi` + `DagitimSecenekleri.tsx`: kip
  seçimi ve açıklaması (kapasite etkisi: "Ayrı salonlar" salon sayısını artırabilir).
  Okul varsayılanı KAPALI iken bu seçim sihirbazda göze batmamalı (ayrıntı bölümünde).
- `YerlesimPaneli`: ihlal metni zaten genel listeden gelir; koltuk kartına rozet YOK.
- R8 (`r8_validation.html`) "A. DAĞITIM BİLGİLERİ"ne tek satır: kuralın adı.
  R1/R4/R5/R7/kitapçık/mazeret belgeleri: HİÇBİR değişiklik — koruma testi yazın
  (BEP emsali: `test_individual_questions.py::test_salon_evrakinda_ve_pakette_ayiran_
  isaret_yok`): çıktılarda "Kız"/"Erkek"/"Cinsiyet" geçmemeli; R5 Excel'de sütun yok.
- Öğrenci API'si (`StudentSerializer`): `gender` alanı yalnız düzenleme formu için
  döner; liste ekranı göstermez. Yedek/geri yükleme ve parola geçişi alanı
  kendiliğinden kapsar — `test_app_password`/`test_backup_restore`'a iddia ekleyin.
- Sözlük (`docs/sozluk.md`, bağlayıcı): "kız/erkek ayrışması"; seçenekler "Kapalı /
  Aynı sıraya oturtma / Ayrı salonlar". İç kodlar (DESK/ROOM, separation_key)
  kullanıcı metninde geçmez.
- Kılavuz: öğrenci aktarımı adımına "cinsiyet de okunur, yalnız bu kural için
  kullanılır, hiçbir belgeye basılmaz" + yeni kural başlığı. Mevzuat kutusu YOK (§3.6).

### 3.6 Mevzuat ve KVKK — iddia ETMEYİN, doğrulayın

- Depodaki sınav mevzuatında (ÖDY, Yönerge, OKY — `docs/mevzuat/`) kız/erkek ayrı
  oturtmaya ilişkin hüküm YOKTUR (başlamadan `grep -i "kız\|erkek\|karma"` ile teyit
  edin). Özellik bu yüzden **okul tercihi** olarak sunulur: varsayılan KAPALI,
  kılavuzda mevzuat kutusu YOK, evrakta dayanak satırı YOK.
- Karma eğitim ilkesinin 1739 sayılı Millî Eğitim Temel Kanunu md. 15'te olduğu
  HATIRLANIYOR — DOĞRULANMADI. Kılavuzda ya da belgede anılacaksa önce metni usulünce
  depoya alın (hafıza: "Mevzuat metni aktarım usulü" — mevzuat.gov.tr iframe adresi
  `MevzuatTur=1&MevzuatNo=1739`, tarayıcıda alt dize birebirlik denetimi; WebFetch
  özetler, kullanmayın).
- KVKK: cinsiyet md. 6/1'deki özel nitelikli veri listesinde YOKTUR
  (`docs/mevzuat/kvkk-6698.md` metninden doğrulayın) → md. 5 kapsamı; veri okulun
  e-Okul'da zaten işlediği veridir, programda yalnız yerelde ve yerleşim kuralı için
  kullanılır (kullanıcı değerlendirmesi, 20.09.2026). Yine de ölçülülük (md. 4/2-ç)
  gereği: alan şifreli, hiçbir çıktıya basılmaz, öğrenci ayrılınca/silinince kayıtla
  birlikte gider. `kvkk-6698.md` "Değerlendirme notları"na kısa bir madde ekleyin
  (YORUM olarak, kullanıcı kararını tarihle anarak).
- Belgelerde güncellenecek "toplanmaz" ifadeleri: tasarım §4 (`Student` satırı), §5
  ve §6; `okul/models.py::Student` açıklaması; `excel_ogrenci.py`, `eokul.py`,
  `normalize.py` modül başlıkları; Kişiler ekranı ipucu; README'de "TCKN/veli
  tutulmaz" cümlesi DOĞRU kalır. CLAUDE.md §1.6'daki liste (TCKN, veli, sağlık
  serbest metni) değişmez; §2'ye "cinsiyet yalnız yerleşim kuralı içindir, hiçbir
  çıktıya basılmaz, ekranda rozet olarak gösterilmez" maddesi eklenir.

## 4. Aşamalar ve kabul ölçütleri

1. **Hazırlık:** §0 commit'i (kullanıcı onayıyla) → dal aç → §2'deki AÇIK kararları sor.
2. **Veri yolu** (3.2): `normalize_gender` + sütun eşlemesi + `Student.gender` göçü +
   `_process_student_row`; testler — e-Okul sentetik örneğinden K/E okunur; sütunsuz
   şablon/pano aktarımı aynen çalışır; boş değer kayıtlı cinsiyeti silmez; önizleme
   hiçbir şey yazmaz; parola açıkken ham sütun "K"/"E" DEĞİLDİR (şifreli).
3. **Altın kayıt testi** (motor değişmeden): sabit seed senaryoları.
4. **Motor + doğrulayıcı** (3.3-3.4): kural açıkken uygun kapasitede karışık sıra = 0;
   aynı seed → aynı sonuç; kural kapalıyken altın kayıtla bit bit aynı; imkânsız
   kapasitede ihlal listelenir, çökmez; ROOM bölüşümü deterministik; joker + uyarı;
   pin çakışması K5 kararına uygun. `test_engine.py`'deki rastgele senaryo omurgasına
   (ihlal=0) ayrışmalı varyant ekleyin.
5. **Model + servis + API** (3.2, 3.5): `distribute_session`, `seating_report`,
   `swap_seats`, `approve_session`, `copy_session_plan`, `revert_session_to_draft`,
   anonimleştirme; mazeret oturumu da aynı motordan geçer.
6. **Arayüz:** okul varsayılanı + sayaç, sihirbaz/dağıtım seçeneği, Kişiler düzenleme
   alanı ve ipucu metni, kılavuz.
7. **Evrak koruma testi + R8 satırı.**
8. **Belgeler** (3.6 listesi) + bu planın başına "UYGULANDI" notu.
9. **Kapı:** `bash scripts/gates.sh` yeşil; ardından çalışan uygulamada uydurma
   veriyle uçtan uca deneme (§5 düzeneği): sentetik e-Okul sınıf listesi aktar →
   kural açık dağıt → karışık sıra yok → R1/R4 PDF'inde cinsiyet izi yok.

## 5. Bu makinede çalışma notları (20.09.2026 oturumundan)

- Test/lint YALNIZ Docker'da: `docker compose run --rm -T backend sh -c "ruff
  format . && ruff check . && mypy . && pytest <yol> -q --no-cov -p no:cacheprovider"`.
  Git Bash'te `export MSYS_NO_PATHCONV=1` şart. Tam kapı ~10-15 dk sürer; arka
  planda koşun ve **koşu bitene kadar ağaca dokunmayın**.
- Ön yüz statik denetimleri host'ta (node_modules Linux kurulumu — `npm run` çalışmaz):
  `frontend` dizininden `node node_modules/typescript/bin/tsc --noEmit` ·
  `node node_modules/eslint/bin/eslint.js src` ·
  `node node_modules/prettier/bin/prettier.cjs --check src`. vitest Docker'da:
  `docker compose run --rm -T frontend npx vitest run <yol>`.
- Dosyayı betikle yazarken satır sonu LF olmalı (`open(..., newline="\n")`); Bash
  heredoc içinde tırnaklı/kaçışlı Python yazmayın (iki kez kırıldı) — betiği Write
  aracıyla scratchpad'e yazıp çalıştırın.
- Canlı deneme: scratchpad'de `KS_DATA_DIR` ile `migrate` + tohum betiği
  (`manage.py shell < seed.py`), `docker compose run --rm -T frontend npm run build`,
  sonra `docker compose run --rm -T -p 127.0.0.1:8791:8000 -e KS_DATA_DIR=… -e
  KS_FRONTEND_DIR=/repo/frontend/dist -e KS_APP_VERSION=$(cat VERSION) backend
  python manage.py runserver 0.0.0.0:8000 --noreload`; ekran görüntüsü başsız Chrome
  ile (`chrome.exe --headless=new --screenshot=… --window-size=1400,1000
  --virtual-time-budget=15000 <url>`). Bitince konteyneri durdurun.
- Gerçek öğrenci verisi depoya ve araç çıktısına girmez; test/demodaki bütün ad,
  numara ve cinsiyetler uydurma olmalı. Sentetik fixture eklerken muafiyet ADIYLA
  yazılır (CLAUDE.md §2 — `.gitignore` + `depo_sizintisi.MUAF_YOLLAR`).

## 6. Riskler

- **Fizibilite:** dar kapasitede sıra kuralı ihlalsiz çözülemeyebilir; kullanıcı
  beklentisini arayüzde yönetin (kapasite ipucu, "salon ekleyin").
- **Determinizm:** ROOM bölüşümü ve alt seed'ler sıraya duyarlıdır — sözlük/küme
  yineleme sırasına güvenmeyin, her yerde sıralı liste kullanın.
- **Eski kurulum verisi:** cinsiyet boşken kural açılırsa herkes joker olur ve kural
  sessizce etkisiz kalır — uyarı ve sayaç bu yüzden ŞART (K4).
- **Kapsam kayması:** cinsiyet alanı girince listede/evrakta gösterme talepleri
  gelebilir; "yalnız yerleşim kuralı için, hiçbir çıktıya basılmaz" kısıtı
  CLAUDE.md'ye yazılmalı ve koruma testiyle sabitlenmeli.
- **e-Okul biçim değişikliği:** sütun adı değişirse cinsiyet sessizce boş gelir;
  aktarım raporuna "cinsiyet sütunu bulunamadı" BİLGİ satırı ekleyin (hata değil).
