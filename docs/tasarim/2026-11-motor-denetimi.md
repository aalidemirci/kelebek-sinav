# Öğrenci dağıtım motoru ve kopya konumu: denetim raporu

*Tarih: 06.11.2026 · Durum: kararlar uygulandı, sürüm yayımlanmadı · Üst belge:
[genel tasarım §2.4](2026-08-29-genel-tasarim.md)*

Veri sentetiktir. Ölçülen şey kopya değil, oturma geometrisidir. Kopya hiç ölçülmedi: hiçbir
karar için "kopya azalır" denemez. Yön sıralaması sınırlı kanıta, sayılar varsayıma dayanır.

## 1. Düz cevap

**Hata var mıydı?** Yakınlık aritmetiği doğru: motor toplamı doğrulayıcıyla aynı, iki sınavlı
tam salonda gerçek optimumu her dağıtım numarasında buluyor. Hata, ihlal içeren takasların
kabulündeydi: sonsuz ceza ihlal saymıyor, takas iki öğrencinin ortak terimini yanlış ölçüyordu.
En çok "aynı sıraya oturtma" kipi etkileniyordu (72/72 mevcutta ilk ölçümde onaylanabilir plan 30
numarada 1), üçlü sıra da etkileniyordu. Kip kapalı ve ikili sırada ihlal, ölçülen koşularda alt
sınırda kaldı. Düzeltildi (bölüm 4).

**Hangi pozisyonlar?** En tutarlı sinyal yakın yan komşudur. Ön-arka ve çaprazda fazlalık
görülmemesi 1,8-2,2 m'ye aittir; bizim yaklaşık 1 m'lik ön-arkamız için söylenemez. Arka sıra,
köşe ve masaya uzaklık için atanmış koltukta kanıt bulunamadı. Tanıdık komşu riski artırıyor gibi
görünüyor, ama bu sınırlı ve koşullu bir bulgudur; lise verisi yok.

**Daha iyi yaklaşım var mı?** Önce hata düzeltmesi ve tekrar sorunu gerekiyordu, yeni ağırlık
formülü değil. Literatür sayısal ağırlık vermiyor. Motor en iyi bulunan planın ortalama %9,27
üstünde kalıyor, ama daha düşük ceza her zaman daha az yakınlık demek değil. Daha güçlü arama
şimdilik gerekçesiz.

## 2. Kanıt tablosu

Numaralar Ek A'daki künyelerdir.

| Pozisyon | Ne biliyoruz | Kanıt gücü | Kaynak |
|---|---|---|---|
| Yakın yan (yaklaşık 1,2 m) | Serbest koltukta yan çift +1,105 ortak yanlış (taban 2,34). Rastgele koltuk, 4 gözetmen ve 2 form birlikte uygulanınca +0,111, anlamsız. Saha deneyinde fazlalık yalnız doğrudan yan komşuda | Eldeki en iyi kanıt; üniversite, çoktan seçmeli; biri kopya şüphesiyle incelenmiş vaka | 1, 2 |
| Ön-arka | -0,062; 1,8 m'de fazlalık görülmedi. Yön ile mesafe ayrılamıyor | Zayıf; bizim mesafeye taşınmaz, sıfır sayılamaz | 1, 2 |
| Çapraz | 2,2 m'de fazlalık görülmedi; ayrı etki büyüklüğü yok | Zayıf | 2 |
| Araya boş koltuk ya da öğrenci girmesi | İki koltuk öte +0,614, kararsız. Boş koltuk +0,147, anlamsız, üst sınırı yaklaşık 0,61 | Zayıf; boşluk güvence değil | 1, 2 |
| Arka sıra, köşe, ön sıra | Atanmış koltukta kanıt bulunamadı | Yok | 5 |
| Masaya uzaklık, gözetmen konumu | Kanıt bulunamadı | Yok | - |
| Tanıdık komşu | Yalnız kopya mümkünken arkadaş 16,50, yabancı 10,20 (24'er çift); başka hile de açıkken fark yok | Sınırlı, koşullu, ağırlıkla ilişkisel; şube üzerinden ölçülmüş kanıt yok | 3, 4, 5, 6 |
| Gözetim | Gözetmen başına 44,2 yerine 8,4 öğrenci izi siliyor. Lise: ceza tehdidine ek kamera geçmeyi 9,5 puan düşürüyor | Etkisi için orta; "yerleşimden güçlü" sınanmadı | 2, 7, 8 |
| Kitapçık çeşidi | Kaynaklar çelişiyor; etkisi ayrışmıyor | Zayıf | 10-14 |
| Mesafe eğrisi, sayısal ağırlık | Tek ölçüm 5 denekli | Yok | 16 |
| Türkiye, lise, ikili sıra, kelebek | Akademik çalışma bulunamadı, arama tamamlanamadı; incelenen resmî metinlerde oturma kuralı bulunamadı | Yok | 17, 18 |

## 3. Kullanıcı kararları (06.11.2026)

| Karar | Sonuç | Nerede |
|---|---|---|
| 1. Kız/erkek ve üçlü sıra düzeltmesi | Girdi | Sayılı yol, `engine._uses_counted_path`; genel tasarım "Eki: sayılı yol ve motor sürümü" |
| 2. Harman her dağıtımda açık, kapılı biçim yok | Girdi sıralaması eklenip yeniden ölçüldükten sonra girdi; altın kayıt yenilendi | `_input_key`, `_blend_section_order`, `_blend_room_order`; "Eki: girdi sırası ve harman" |
| 3. Daraltılmış yakınlık cezası | Seçimlik "Yakınlık önceliği", varsayılan kapalı, katı dağıtımda ve kendi dersliğinde devre dışı | `okul.ProximityMode`; "Eki: yakınlık önceliği" |
| 4. Kaçınılmaz çiftler masaya yaklaştırılmaz | Masaya uzaklık yalnız eşitlik bozar | `_pair_penalty`; sayılı yolda demetin son bileşeni |
| 5. "Bir arada" varsayılan kalır | Kaldı; en yakın komşuların çoğunun aynı şubeden olduğu kılavuza yazıldı | Kılavuz 8. adım; bölüm 5 |
| Sürüm alanı ve eksik sıra uyarısı | R8 "Dağıtım yöntemi sürümü" basar; sihirbaz eksik sıra sayısını söyler | `ENGINE_VERSION`, `separation_desk_gap` |
| R8 kız/erkek satırı | Yalnız kuralın adı ve konum; okul numarası ve cinsiyet sözcüğü yok | `validator._check_separation` |

Sınav çeşidi ekranda iki yerde farklı ayrıntıda geçer, evraka basılmaz. Sihirbaz salon adımı salon
başına sayı göstermez, yalnız genel cümleyi yazar ("sınav çeşidi arttıkça mesafe genellikle artar").
Salon başına sınav sayısı ve oran (bölüm 5) yalnız dağıtımdan sonra Yerleşim sekmesindedir. Karar
raporunun önerisi sihirbazda salon başına gösterimdi; bu biçim uygulanmadı, çünkü salon adımında
henüz yerleşim yoktur ve oran yerleşimden hesaplanır.

**Uygulanmayanlar ve gerekçesi**

- **Metreli model:** yan ağırlığının 2, 3 ya da 5 olması fark etmiyor; salt mesafe koridor
  karşısını 3 katına çıkarıyor; sıra adımı değişince sonuç tersine dönüyor.
- **Çoklu başlangıç (varsayılan):** süre 10 kat; 200 öğrenci, 4 sınavda önde aynı sınav %41,8'den
  %59,3'e çıkıyor; kız/erkek hatasını çözmüyor.
- **Eşik tavlaması (şimdilik):** ortalama açık %1,43, ama kız/erkek onayı 12/12'den 0/12'ye
  düşüyor; ikincil ceza ve önceki sıra cezası yok; 6x4'te en kötü %12,78. Bu eksikler kapanmadan
  değerlendirilemez.
- **Tek hamle onarımı:** ölçülen hiçbir senaryoda ek kazanç yok.
- **Arka sıra, köşe ya da ön sıra cezası; arkadaşlık anketi; dış çözücü bağımlılığı.**
- **Herhangi bir katsayıyı kılavuzda ya da R8'de bilimsel sonuç diye yazmak.**

## 4. Birleşik ölçüm: ürün kodu

Rapor önerileri önce ayrı ayrı ölçülmüştü. Düzeltme, girdi sıralaması, harman ve yakınlık kipi
birleştikten sonra aynı senaryolar ürün motoruyla koşuldu. "Önce" 2026.10.0-beta.7 motorudur.

**Kız/erkek, "aynı sıraya oturtma", bağımsız dağılım, 30 veri**

| Mevcut | Matematiksel sınırın izin verdiği | Onay önce / sonra | Kabulsüz temiz plan | Ayrışma ihlali ort. önce / sonra | Aynı sıra ihlali ort. önce / sonra |
|---|---|---|---|---|---|
| 80/80 | 13 | 0 / 13 | 0 / 0 | 62,90 / 0,57 | 27,53 / 7,00 |
| 76/76 | 30 | 0 / 30 | 0 / 12 | 17,57 / 0 | 13,37 / 2,53 |
| 72/72 | 30 | 2 / 30 | 2 / 23 | 9,53 / 0 | 7,60 / 0,93 |
| 40x4 | 18 | 0 / 18 | 0 / 17 | 49,67 / 0,40 | 12,97 / 0,03 |
| 60/50/50 | 13 | 0 / 13 | 0 / 11 | 60,03 / 0,57 | 19,40 / 0,07 |
| 36x4 | 30 | 30 / 30 | 30 / 30 | 0 / 0 | 0 / 0 |

- Bu veri kümesinde onay her satırda sınıra eşit. Kümeli ve numara sırasına bloklu dağılımda da
  (72/72, 60/50/50) sınıra eşit.
- 80/80'de 30 verinin 17'sinde onay matematiksel olarak imkânsız: tek kız sayılı tam dolu salonda,
  joker yoksa ve Σceil(n/2) sıra sayısını aşıyorsa en az bir karışık sıra zorunludur. Sihirbaz bunu
  dağıtımdan önce eksik sıra sayısıyla söyler.
- 2 ikili + 2 üçlü tam salonda onay 30/30, sınıra eşit (önce 0/30). Birleşik ölçümün ilk koşusunda
  bu kurulum 12/30 kalmış, kusur `_key_targets` ile kapanmıştı.
- Şube içinde tümüyle tek cinsiyet: sınırın izin verdiği 360 verinin hepsinde ilk numara onay verdi.
  Bedeli aynı sıra ihlalidir (2 ikili + 2 üçlü, tek cinsiyet şube: ort. 26,00): kız/erkek ihlali
  kabulle geçilmediği için önce o sağlanır.
- Üçlü sıra, kural yok: [20,12,4] ihlal 14,27'den 8'e; [26,10] 23,40'tan 16'ya; [18,14,4] 13,10'dan
  8'e; [12,12,12] 0.

**Tekrar (4 salon 5x4, 3 ardışık oturum, önceki koltuk açık, 20 numara; önce / sonra)**

| Senaryo | Farklı numarada aynı koltuk | Sıra arkadaşı tekrarı | Halka tekrarı |
|---|---|---|---|
| 2 sınav tam | %100 / %3,06 | %100 / %2,38 | %61,82 / %13,18 |
| 4 sınav tam | %31,50 / %1,69 | %17,75 / %1,81 | %31,85 / %7,40 |
| 2 sınav %85 | %44,93 / %2,43 | %27,63 / %2,81 | %31,18 / %10,91 |
| 4 sınav %85 | %17,68 / %1,58 | %11,87 / %1,44 | %16,79 / %2,98 |
| 2 sınav, şube = salon payı | %100 / %4,84 | %100 / %5,25 | %61,82 / %29,01 |
| 4 sınav, şube = salon payı | %31,62 / %3,91 | %19,19 / %3,81 | %33,65 / %20,73 |

Bedel: aynı salonda kalma %100'den %36-56'ya iner (şube bölünüyorsa); şube salon payına tam
oturuyorsa %100 kalır. Sonuç düzenin numaraya bağlandığını gösterir, kopya azaldığını göstermez.

**Girdi sırası (aynı numara, aynı koltukta kalan öğrenci)**

| Senaryo | Motor | Ders satırı ters | Öğrenci sırası karışık | Salon sırası ters | Ders + salon |
|---|---|---|---|---|---|
| 2 sınav tam | önce | %100 | %3,56 | %0 | %0 |
| 2 sınav tam | sonra | %100 | %100 | %100 | %100 |
| Üçlü + ikili, kız/erkek | önce | %100 | %1,42 | %0 | %0 |
| Üçlü + ikili, kız/erkek | sonra | %100 | %100 | %100 | %100 |

Ölçülmemiş kalan salon listesi sırası böylece kapandı. Ayrıca 1500 karşılaştırmalık sıra değiştirme
denemesinde plan farkı çıkmadı.

**Harmanın güvencesi (40 veri, beş kurulum).** Ayrışma kapalı ve önceki koltuk yokken grup deseni ve
yakınlık skoru harmansız hâliyle aynı. Önceki koltuk varken desen ve skor değişir (kurulumlarda desen
aynılığı 0-27/40); ihlal sayısı 40/40 değişmedi, ama bunun güvencesi yoktur.

**Yakınlık önceliği (4 salon × 40 koltuk, 20 veri, salon başına çift; kapalı / açık)**

| Senaryo | Tam ön-arka | Koridor çaprazı | Komşu sıra (halka) | Aynı sınav medyanı (m) |
|---|---|---|---|---|
| 2 sınav %100 | 32,00 / 32,00 | 24,00 / 24,00 | 110,00 / 110,00 | 1,25 / 1,25 |
| 2 sınav %85 | 20,00 / 20,46 | 7,26 / 10,36 | 64,01 / 68,00 | 1,25 / 1,25 |
| 3 sınav %100 | 18,80 / 16,00 | 6,89 / 11,38 | 62,56 / 66,72 | 1,25 / 1,25 |
| 3 sınav %85 | 12,20 / 6,28 | 2,41 / 6,01 | 32,77 / 40,73 | 1,27 / 1,63 |
| 4 sınav %100 | 11,88 / 0 | 5,06 / 6,96 | 37,98 / 45,00 | 1,52 / 2,11 |
| 4 sınav %85 | 4,76 / 0 | 1,51 / 2,94 | 18,32 / 25,34 | 2,01 / 2,11 |

Metre değerleri varsayımdır (sıra 1,2 m, koridor 0,6 m, sıra adımı 1,1 m). Katı dağıtımda 20 veride
plan aynı kaldı. Kız/erkek açık tam salonda tam ön-arka 3 sınavda 18,89'dan 16,32'ye, 4 sınavda
8,38'den 2,01'e iner; 2 sınavda 30,43'ten 29,55'e. Doluluk, sıra türü ve dengesiz mevcut
ayrıntısı genel tasarımın "Eki: yakınlık önceliği" bölümündedir.

**Süre (Docker, tek koşu, saniye; yalnız göreli okuyun)**

| Senaryo | Öğrenci | Önce | Sonra |
|---|---|---|---|
| İkili tam, 4 sınav | 1200 | 1,03 | 0,82 |
| İkili tam, 4 sınav, kız/erkek | 1200 | 0,88 | 0,34 |
| Üçlü, 6 sınav | 1200 | 1,36 | 0,19 |
| Karma tekli + ikili, 12 sınav | 1200 | 0,51 | 0,35 |
| Karma, baskın 800 + 30 küçük sınav | 1190 | 0,63 | 1,06 |
| 20 ikili + 20 üçlü tam, 30 sınav | 2000 | ölçülmedi | 5,11 |

Tablo ölçülen senaryoları gösterir, üst sınır değildir. Ölçek dışı bir kurulumda (90 salon: 30 tekli,
30 ikili, 30 üçlü sıralı; 3600 öğrenci, 40 sınav, kız/erkek açık, bağımsız dağılım) tam dolu salonlarda
tek dağıtım üç koşuda 11,4-14,6 sn, başka işlerin yükü altındaki bir koşuda 15,5 sn, son ölçümün 16 ek koşusunda
12,9-22,8 sn sürdü. Aynı kurulum
%97 dolulukta 0,35-0,37 sn'dir. Tam dolulukta farkın neden bu kadar büyüdüğü incelenmedi.

Rapordaki karma salon süre sorunu (720 öğrenci 0,53'ten 13,82 sn'ye, 1000 öğrenci 87,57 sn) bu
ölçekte (1200-2000 öğrenci) çözüldü: kota düzeltmesi artımlıdır, hamle başına yalnız iki salon yeniden hesaplanır ve testle sınırlıdır.
Karma salon kotası testle kilitlidir (`test_karma_salonda_kota_sira_sayisina_iner`). Yakınlık kipinin
süre farkı 1200 öğrencide en çok 0,04 sn ölçüldü.

## 5. Sınav çeşidi ve şube ölçüleri

**Önünde aynı sınav olan öğrenci** (Yerleşim sekmesindeki oranın tanımı): ilk dolu satırın
arkasındaki öğrencilerden, aynı sütunda plandaki bir önceki sırada aynı sınava giren biri olanların
payı. Plana konmamış boş satır atlanır, planda olup boş kalan sıra atlanmaz; sütununun ilk
sırasındaki öğrenci paydaya girmez. Boşluksuz planda bu, bir satır öndeki sıradır. Ürün motoru, 4 salon 5x4, eşit mevcut, varsayılan seçenekler, 20 veri, ortalama:

| Sınav sayısı | %100 dolu | %85 dolu | %70 dolu |
|---|---|---|---|
| 1 | %100 | %100 | %100 |
| 2 | %100 | %76,9 | %59,6 |
| 3 | %59,8 | %46,9 | %24,2 |
| 4 | %33,9 | %18,4 | %3,8 |
| 5 | %0,1 | %6,1 | %0,2 |
| 6 | %12,0 | %1,6 | %0 |

Tablo eşit mevcut ve kız/erkek kapalı içindir. İki sınavlı tam salonda %100 güvencesi yalnız bu
koşulda vardır; başka durumda oran salona göre değişir ve bir sınır gibi okunacak aralık yoktur.
Kılavuz bu yüzden aralık yazmaz, kullanıcıyı Yerleşim sekmesindeki değere yönlendirir.

Mevcutlar eşit değilken (ürün motoru, 4 salon 5x4 tam dolu, kız/erkek kapalı, 12 veri, salon başına
en düşük-en yüksek): [90, 70] %90,6-96,9, [100, 60] %84,4-93,8, [110, 50] %78,1-96,9, [120, 40]
%75,0-100, [130, 30] %78,1-93,8, [140, 20] %84,4-93,8, [150, 10] %90,6-93,8, [155, 5] %93,8-96,9.
Oran mevcut farkıyla tek yönlü inmez. %100 için salon içi eşitlik de şart değildir: 96 dağıtımın 384
salonunda %100 çıkan tek salon 30/10 dağılımlıydı.

Kız/erkek "Aynı sıraya oturtma" açıkken eşit mevcutta bile güvence kalkar (80/80, tam dolu, 12 veri,
en düşük salon oranı; parantezde %100'ün altına inen veri sayısı): bağımsız dağılım %78,1 (8), şube
içi kümeli %34,4 (11), tek cinsiyetli şube %0 (8).

Genel yön aşağıdır, ama tek düze değildir (5 sınav tamda %0,1, 6 sınav tamda %12,0). Bu yüzden
sihirbaz "genellikle artar" der. Oran yapısal değil, cezanın ürünüdür; yakınlık önceliği açıkken
4 sınavlı tam salonda tam ön-arka çifti sıfıra iner. Kopya azalması ölçülmedi.

**En yakın aynı sınav komşusunun aynı şubeden olma oranı** (ürün motoru, 5x4 salon, 10 veri, ikinci
oturum, ortalama; parantezde tek koşu aralığı):

| Senaryo | Şubeler bir arada | Şubeler salonlara dağıtılır |
|---|---|---|
| 2 sınav × 160, %100, 8 salon | %100 | %21,7 (19,5-24,7) |
| 2 sınav × 120, %75, 8 salon | %100 | %20,4 (17,7-23,0) |
| 3 sınav × 128, %80, 12 salon | %96,8 | %16,8 (11,7-21,4) |
| 5 sınav, %82, 12 salon | %92,5 | %13,9 (10,2-15,6) |
| 180/60, %75, 8 salon | %80,8 | %21,7 (17,5-24,4) |

4 salonlu tekrar senaryolarında "bir arada" %77,47-100 ölçüldü; aralık bu yüzden %77-100 yazılır.
Dağıtılan kipte kılavuz %14-22 der. Karar raporundaki %17-29 harmandan önceki motora ve komşu sıra
çiftine aitti; ürün motorunda komşu sıra çifti için aynı oran %13,6-21,4'tür. Oranın kendisi tanışıklık
ölçmez: kaynak 3-6 şube üzerinden kanıt vermez.

## 6. Açık sınırlar

- **Kopya hiç ölçülmedi.** Tek gerçek doğrulama, gerçek komşu ile komşu olmayan çiftlerin ortak
  yanlışlarını kurum içinde, anonim karşılaştırmaktır.
- **Gerçek okul verisi yok.** Kız/erkek dağılımı üç modelle varsayıldı; numara sırasına bloklu
  düzenin ne kadar yaygın olduğu bilinmiyor.
- **Yayın kapısı koşulmadı.** Paketli Windows'ta süre ve aynı numara aynı plan sözleşmesi sınanmadı.
- **Aynı sıra ihlali kimi kümeli senaryoda yüksek kalır.** Kız/erkek ihlali kabulle geçilmediği için
  önce o sağlanır; aynı sınav ihlali idare kabulüne kalır.
- **Sınırın izin vermediği kurulumda** (eksik sıra var) şube içi tek cinsiyet birden fazla karışık
  sıra bırakabilir (20 ikili salon, 6 sınav: eksik 1 sıra, karışık 5); plan zaten onaylanmaz.
- **Şube salon payına tam oturuyorsa** öğrenci aynı salonda kalır, halka tekrarı %21-29'dadır.
- **Harman ve kız/erkek:** numara sırasına bloklu dağılımda tek başına harman ölçümünde sıfır ihlalli
  numara 120'de 111'den 98'e indi (p=0,011); bağımsız dağılımda fark yok. Bu ölçüm birleşik motorda
  tekrarlanmadı.
- **5x4 salonda gerçek optimum bilinmiyor.** Yalnız 3x4 örneğinde 67,837 değeri matematiksel olarak
  kanıtlandı.
- **Motorda süre ya da düğüm bütçesi yok.** Sınır sayaçla konur (`_FLOOR_SPLIT_BUDGET`), duvar saati
  kullanılmaz: aynı numara aynı plan. Bu yüzden en kötü süre bilinmiyor; ölçülen en büyük değer süre
  tablosunun altındaki 3600 öğrencilik kurulumdur.
- **Kaynak sınırı.** Topîrceanu tam metni ve Houston 1976 görülmedi. DergiPark ve YÖK Tez araması
  tamamlanamadı; "literatürde yok" denemez.
- **Mevzuat teyidi gerekir.** OYSS'de sınavı "ilgili sınıfta dersi olan öğretmen" yapar; bunun karma
  salonla ilişkisi çıkarımdır. Ülke geneli sınavda aynı düzeyde başka sınav yapılamaması 2025-2026
  kılavuzunda görüldü, 2026-2027'de sürdüğü doğrulanmadı ve OYSS'ye taşınmaz.

---

# Ekler

## Ek A. Kaynak künyeleri

**Konum, tanışıklık, gözetim, kitapçık**

1. Lin, M.-J., Levitt, S.D. (2020). Catching Cheating Students. *Economica* 87, 885-900. doi:10.1111/ecca.12331. Tam metin.
2. Cagala, T., Glogowsky, U., Rincke, J. (2024). Detecting and Preventing Cheating in Exams: Evidence from a Field Experiment. *Journal of Human Resources* 59(1), 210-241. doi:10.3368/jhr.0620-10947r1. Okunan: 20.07.2021 çalışma metni; dergi sürümü görülmedi.
3. Potipiti, T., Kingsuwankul, S. (2020). Friends and exam cheating: An experimental study in Thailand. *Kasetsart Journal of Social Sciences* 41, 250-255. Tam metin. Ücretli deney, üniversite.
4. Fendler, R.J., Yates, M.C., Godbey, J.M. (2018). Observing and Deterring Social Cheating on College Exams. *IJ-SoTL* 12(1), Art. 4. Tam metin.
5. Houston, J.P. (1986). Classroom Answer Copying: Roles of Acquaintanceship and Free versus Assigned Seating. *Journal of Educational Psychology*. ERIC EJ336921. Özet; tanışıklık sonucu yalnız ikincil aktarımla görüldü.
6. Topîrceanu, A. (2017). Breaking up friendships in exams: A case study for minimizing student cheating in higher education using social network analysis. *Computers & Education* 115, 171-187. doi:10.1016/j.compedu.2017.08.008. Yalnız arama özeti; x2,8-3,3 değerinin ölçütü ve karşılaştırma tabanı doğrulanamadı.
7. Borcan, O., Lindahl, M., Mitrut, A. (2017). Fighting corruption in education: What works and who benefits? *AEJ: Economic Policy* 9(1), 180-209. Kabul edilmiş sürüm, tam metin.
8. Lucifora, C., Tonello, M. (2019). Monitoring and Sanctioning Cheating at School: What Works? Evidence from a National Evaluation Program. 70th Economic Policy Panel. Tam metin. 6. ve 10. sınıf birlikte, okul düzeyi gösterge.
9. Lucifora, C., Tonello, M. (2015). Cheating and social interactions. Evidence from a randomized experiment in a national evaluation program. *JEBO* 115, 45-66. doi:10.1016/j.jebo.2014.12.006. Okunan: IZA DP 6967 (2012).
10. Houston, J.P. (1983). Alternate Test Forms as a Means of Reducing Multiple-Choice Answer Copying in the Classroom. *Journal of Educational Psychology*. ERIC EJ284902. Özet.
11. Kerkvliet, J., Sigmund, C.L. (1999). Can We Control Cheating in the Classroom? *The Journal of Economic Education* 30(4), 331-343. doi:10.1080/00220489909596090. Özet; öz bildirim.
12. Mai, T. (2024). Social Network Formation and Exam Fraud: A Friend in Need is a Friend Indeed. Job market paper, hakemsiz. Tam metin. Vietnam lisesi, salon düzeyi.
13. Harpp, D.N. (2008). Crime in the Classroom Part IV: Conclusions. *Journal of Chemical Education*. ERIC EJ827384. Özet.
14. Harpp, D.N. (2018). Crime in the Classroom: Analysis over 26 Years. *Journal of Chemical Education*. ERIC EJ1170370. Özet.
15. McManus, I.C., Lissauer, T., Williams, S.E. (2005). Detecting cheating in written medical examinations by statistical analysis of similarity of answers: pilot study. *BMJ* 330(7499), 1064-1066. doi:10.1136/bmj.330.7499.1064. Aktarımla kullanıldı.
16. Wiwatwisawakorn, K., Ladavichitkul, P. (2011). A Preliminary Study of Distance Between Examination Seats for Preventing Cheat With Speed-Accuracy Tradeoff. *IMECS 2011*, Vol II, Hong Kong. Tam metin. 5 denek.

**Türkiye metinleri**

17. T.C. MEB, 2025-2026 Eğitim Öğretim Yılı 2. Dönem 2. Yazılı Sınavlar (Ülke Geneli Ortak) Kılavuzu, odsgm.meb.gov.tr. Tam metin.
18. MEB OYSS Uygulama Kılavuzu 2026-2027, seçilmiş bölümler (depoda `docs/mevzuat/`).
19. ÖSYM Sınav Uygulama Yönergesi 2023. Cevap dağılımları incelenir; yöntem ve eşik yazmıyor.
20. Bingöl EFOR Projesi Ölçme ve Değerlendirme Sınavları Lise (V) Uygulama Yönergesi (2024). Yerel uygulama: kitapçıklar S düzeninde.

**Yöntem kaynakları (konum riski ölçmez)**

21. Leinonen, R. (31.10.2025). Integer programming formulations for exam hall allocation. Aalto Üniversitesi sunumu.
22. Agalday, F., Nizam, A. (2022). Performance Improvement of Genetic Algorithm Based Exam Seating Solution by Parameter Optimization. *J Inno Sci Eng* 6(2), 220-232. doi:10.38088/jise.1006070.
23. Bulut ve Subaşı (2015). Merkezî sınavlar için genetik algoritmalar ile en iyi oturma planı. *DEÜ Mühendislik Fakültesi Fen ve Mühendislik Dergisi* 17(3), 122-137.
24. Adetona, S.O., Akintoye, F.A. Design and Implementation of an Examination Seating Arrangement Application to Curb Examination Malpractice. *AJERD* 6(2), 143-156.
25. Karaköse, E. (2025). Sınavlarda kopya çekim vakalarını azaltacak bir uygulama: Bartın Üniversitesi örneği. Yüksek lisans tezi, Tez No 930639. Özet; gerçek kopya ölçülmemiş.
26. Alazraki Salas, P.L., Gómez de Silva Garza, A. (2024). Finding Optimal Classroom Arrangements to Minimize Cheating in Exams Using a Hybrid AI System. *LNCS, HAIS*, 126-138. doi:10.1007/978-3-031-74183-8_11. Özet; simülasyon.

**Kanıt olarak kullanılmayanlar**

- Houston 1976 (JEP) yön iddiası: birincil metin görülmedi, aktarımlar kısmen farklı; hipotez kalır.
- Martinelli vd. 2018: gözetim değil teşvik ölçüyor.
- Selçuk 1995: künye doğrulanmadı.
- Bergtold vd. 2019: serbest koltuk, yön sorusuna katkı vermiyor.
- Griebeler 2017: tasarımı görülmedi, kuramsal olabilir.

## Ek B. Kaynaklara ilişkin ayrıntılar

- **Lin-Levitt:** Ön-arka üst sınırı yaklaşık 0,23; yanın beşte biri civarı, yan etkinin alt sınırıyla yaklaşık %38. Yan çiftin 47 kat değeri yalnız en uç %0,1 dilime aittir. Atanmış koltuklu finalde +0,111 (SH 0,195), güven aralığı yaklaşık -0,27 ile +0,49; hangi önlemin etkili olduğu ayrışmıyor.
- **Potipiti:** Yan yana yabancı 10,20, iki sıra ayrı yabancı 10,00, yani yabancı komşuda iz yok. Başka hile açıkken 11,41 ve 12,83 (p=.4711).
- **Fendler:** Eşleşen yanlış %35,57 (serbest, 86 öğrenci) ve %31,69 (atanmış, 74 öğrenci), Z=2,41. %20 şans değeri yazarların varsayımıdır. Atanmış salonda başka şubeden komşu ile rastgele koltuk birlikte; ayrılmıyor.
- **Borcan:** Yazılı -0,21 SS, geçme -9,5 puan, genel -0,31 SS; ceza tehdidine ek kameranın etkisi, rüşvet kanalını da içerir.
- **Lucifora-Tonello 2019:** Dış gözlemci yaklaşık -%20, devamsızlık yaklaşık +%8; öğretmen manipülasyonu dahil.
- **Kitapçık:** Houston 1983'te yalnız soru sırası yetmiyor, soru ve şık birlikte değişince tespit edilebilir kopya kalkıyor. Kerkvliet-Sigmund'da çok sürüm ve fazla gözetmen caydırıyor. Mai'de etki reform öncesinde sürüyor, reform sonrasında neredeyse kayboluyor. Harpp'ta form ve atanmış koltuk ayrışmıyor. OYSS kâğıdı hazır geldiği için form bu sınavda uygulanamaz görünüyor (çıkarım).
- **Taşıma uyarısı (çıkarım):** Koridor karşısının literatürdeki "yan" ile aynı kanal olduğu gösterilmedi. Bizim ön-arka 0,9-1,3 m varsayımı ölçülmedi.

## Ek C. Arama kalitesi (5x4 ve 3x4, en iyi bulunan plana göre ortalama açık %)

Bu ölçüm düzeltmeden önceki motora aittir; birleşik motorda tekrarlanmadı.

| Yöntem | Rapor | Yeni numaralar | 12 yeni geometri | Süre (200 öğrenci) |
|---|---|---|---|---|
| Tek dağıtım | 9,27 | 9,41 | 11,66 | 0,33-0,41 sn |
| 10'un en iyisi | 4,10 | 4,05 | 6,47 | 2,0-3,5 sn |
| 30'un en iyisi | 2,53 | 2,49 | 4,40 | yaklaşık 10 sn |
| Eşik 20 bin adım | 1,43 | 1,41 | 2,11 | 0,14-0,17 sn |

- Çözücünün kanıtlı alt sınırına göre tek dağıtım %15,96; gerçek açık bu iki değer arasındadır.
- Kuyruk: 3x4'te en kötü +%16,91; 5 sınav %85 eşitte +%43,65.
- Önde aynı sınav oranı en iyi planlarda 5x4'te 7 senaryoda azalıyor, 2'sinde artıyor (4 sınav tam eşit %41'den %80'e), 3'ünde plan seçimine bağlı. 6 ve 8 satırlı salonda yön tersine dönüyor.
- Genel doğru cümle: ceza ile yakınlık aynı yönde olmak zorunda değil.

## Ek D. Denetimde düşen sonuçlar

- "Harman her dolulukta sorunu tam çözer": doluluk yalnız %70-100 ölçüldü; şube bölünmüyorsa tabanda kalıyor.
- "Onay her zaman sınıra eşit": ayrı ölçümde üçlü ve ikili karışık salonda eşit değildi, `_key_targets` ile kapandı.
- "Süre değişmedi" ve "en kötü durum": karma salonda çürüdü, artımlı hesapla giderildi.
- "681/681 güvence verir": yalnız başka yeri kırmadığını gösterir; ters çevrilmiş kabul koşulu da geçmişti. Yeni yolun kalitesini `test_sayili_yol.py` kilitler.
- "4 sınavda %42 önde aynı sınav yapısaldır": cezanın ürünü çıktı.
- "Eşik yalnız çarpık salonda takılır": 6x4 ve 5x5'te de takılıyor.
- "Tanıklık kanıtı güçlendi": derece "sınırlı, koşullu, ağırlıkla ilişkisel" olarak kaldı.
- "Salonlar arası takas yapılmamalı" yasağı: yalnız ceza kazancı için geçerli; kız/erkek dengesinde gerekli.
