# Ders Çizelgeleri (sınav ders havuzu kaynağı)

Bu dizindeki her `.md` dosyası bir **çizelge programıdır**: TTK'nın bir okul
türü için kabul ettiği haftalık ders çizelgesinin, ders havuzuna gereken
kesiti (ders adı · seviyeler · ortak/seçmeli · sınav biçimi). Ders havuzu
(`Course`) bu dosyalardan **okulun yapılandırmasına göre** türetilir
(`apps.dersler.catalog` + `services.sync_catalog`, tasarım §7.2):

1. Okul türü + hazırlık bayrağı + aktif ders yılı → her sınıf seviyesinde
   hangi program(lar)ın uygulandığı (`default_assignment`; yürürlük/kademeli
   kuralı dosyanın meta bloğundan okunur).
2. `SchoolConfig.level_programs` seviye bazında bunu EZER (kademeli tür
   dönüşümü: "9 → Fen, 10-12 → AL"; çok programlı okul: aynı seviyede birden
   çok program; bölümlü GSL: bulunmayan bölümü bırakma).
3. Seviye planından etkin satırlar birleştirilir (ad → seviye birleşimi; tür
   çatışmasında SEÇMELİ, sınav biçimi çatışmasında YOK > UYGULAMA > YAZILI
   kazanır) ve kataloğa **idempotent** uygulanır: MEB kaydı yoksa yaratılır,
   varsa seviye/tür/sınav biçimi güncellenir, çizelge dışı kalan MEB dersi
   pasifleşir (`catalog_excluded`), geri girerse yalnız o bayraklı kayıt
   yeniden açılır. İdarecinin elle pasifleştirdiği ders senkronla açılmaz.
4. Senkron **damga** ile tetiklenir (`SchoolConfig.catalog_stamp` = okul
   yapılandırması + ders yılı + dosya özetleri): ilk kurulum, ayar değişikliği,
   ders yılı devri ve **uygulama sürümüyle gelen yeni/değişmiş dosya** aynı
   yoldan kataloğa iner. Eski "MEB kaydı varsa dosyayı okuma" erken dönüşü ve
   veri göçü ihtiyacı yoktur; dosya değişikliği bir sonraki API çağrısında
   (ders havuzu listesi, ayar kaydı, havuz doldurma) uygulanır.

> Dizin `data/` altında çünkü backend konteyneri yalnız `./backend` ve `./data`
> mount eder; paketli kipte PyInstaller `data/ders-cizelgeleri` ağacını backend
> ağacının yanına kopyalar (`settings.CATALOG_DIR`).

## Dosya formatı

Üstte `- anahtar: değer` meta bloğu, altında bir veya daha çok markdown tablo:

```markdown
- program_key: fen-lisesi-2025
- ad: Fen Lisesi Haftalık Ders Çizelgesi (TTK 09.05.2025/5)
- okul_turu: FEN_LISESI
- hazirlik: hayır
- kaynak: TTK 09.05.2025 tarihli ve 5 sayılı karar, s. 4 — https://…pdf
- yururluk: 2025-2026
- kademeli: hayır

| Ders | Seviyeler | Tür | Sınav |
|---|---|---|---|
| Türk Dili ve Edebiyatı | 9-12 | ORTAK | YAZILI |
| Beden Eğitimi ve Spor | 9-11 | ORTAK | UYGULAMA |
| Rehberlik ve Yönlendirme | 9-12 | ORTAK | YOK |
| Seçmeli Coğrafya | 11, 12 | SECMELI | YAZILI |
```

Meta alanları (`catalog_parser.parse_program_meta`; tablo başlayınca okuma biter):

| Alan | Zorunlu | Anlam |
|---|---|---|
| `program_key` | evet | Kararlı anahtar; `SchoolConfig.level_programs` buna işaret eder. Dosya adıyla aynı tutulur. |
| `ad` | evet | Kullanıcıya görünen ad (Ders Havuzu "yürürlükteki çizelge" paneli). |
| `okul_turu` | evet | `okul.SchoolType` kodu; virgülle birden çok tür (ÇPAL, AL/MTAL/AİHL çizelgelerini paylaşır). Boş = her türe uygulanan genel dosya. |
| `hazirlik` | hayır | `evet`: hazırlık sınıfı bulunan okul çizelgesi. Bölüm grubunda okulun bayrağıyla eşleşen varyant seçilir; tek varyant varsa her iki okul da onu kullanır (AİHL tek çizelgedir, 0. seviye satırları hazırlıksız okulda okul seviye kümesince düşer). Bayrak dosyanın 0. seviye satırı taşımasıyla AYNI olmalıdır (test denetler): matriste "hazırlıklı" etiketini basar. |
| `bolum` | hayır | Bölüm/varyant etiketi (GSL: Görsel Sanatlar/Tiyatro/Müzik/Türk Müziği; Spor: Tematik program; AİHL: B grubundaki yedi program/proje). Aynı türün farklı bölümleri varsayılanda BİRLEŞİR. |
| `varsayilan` | hayır | `hayır`: varsayılan atamaya girmez, yalnız matristen seçilir (Tematik Spor, AİHL program/proje dersleri). |
| `kaynak` | evet | Dayanak: TTK karar tarih/sayı + sayfa + bağlantı. |
| `yururluk` | evet | Başlangıç ders yılı (`2025-2026`). Öncesindeki yıllarda uygulanmaz. |
| `kademeli` | hayır | `evet`: başlangıç yılında `kademeli_ilk_seviyeler`den (varsayılan `0, 9`) başlar, her yıl bir üst seviyeye taşınır (kohort). |
| `kademeli_ilk_seviyeler` | hayır | Örn. `0, 9, 10` — GSL/Spor 2025 çizelgeleri hazırlık-9-10'dan başlar. |
| `secmeli_kademeli` | hayır | `hayır` (varsayılan): kademeli çizelgenin SEÇMELİ satırları tüm seviyelere hemen girer (GSL/Spor kararlarındaki "diğer bileşenleri tüm sınıf seviyelerinde" hükmü). |

Tablo sütunları:

- **Ders:** havuzdaki benzersiz ad (eşleştirme anahtarı). Programlar arasında
  aynı ders AYNI yazılır (kademeli/çok programlı okulda satırlar bu ada göre
  birleşir); çizelge dipnotları ("(2)", "*") ada dahil değildir.
- **Seviyeler:** `9, 10` · `9-12` · `0, 9-12`. Geçerli: **0 (Hazırlık)**, 9-12.
- **Tür:** `ORTAK` / `SECMELI`. Aynı ders hem ortak hem seçmeli bölümdeyse tek
  kayıt: ortak bölümü lise seviyesindeyse ORTAK + seviye birleşimi, yalnız
  hazırlıkta ortaksa SEÇMELİ (dosya notlarında gerekçelenir).
- **Sınav** (isteğe bağlı 4. sütun): `YAZILI` (varsayılan) · `UYGULAMA` · `YOK`.
  Havuz otomatik doldurması yalnız `ORTAK` + `YAZILI` çeker (K19). Sınıflama
  mevzuat hükmü değil kürasyondur (tasarım §7.1); okul Ders Havuzu'ndan
  değiştirir. Tanınmayan etiket satırı düşürür ve hata listesine yazar.

Tablo dışı satırlar (başlık, kürasyon notları) yok sayılır; hatalı satırlar
import'u durdurmaz. `README.md` ve `ders-adi-takma-adlari.md` program sayılmaz.

## Program dosyaları (03.09.2026; AİHL B grubu 19.09.2026'da bölündü)

| Dosya | Karar | Yürürlük |
|---|---|---|
| `anadolu-lisesi-2025.md` · `anadolu-lisesi-hazirlik-2025.md` | TTK 09.05.2025/5 | 2025-2026, tüm seviyeler |
| `fen-lisesi-2025.md` · `fen-lisesi-hazirlik-2025.md` | TTK 09.05.2025/5 | 2025-2026, tüm seviyeler |
| `sosyal-bilimler-lisesi-2025.md` · `sosyal-bilimler-lisesi-hazirlik-2025.md` | TTK 09.05.2025/5 | 2025-2026, tüm seviyeler |
| `anadolu-imam-hatip-lisesi-2025.md` (+ yedi B grubu program/proje dosyası, varsayılan dışı: `…-{spor,musiki,gorsel-sanatlar,ilahiyat-odakli-hafizlik,fen-ve-teknoloji,cocuk-gelisimi,kuran-egitim-merkezi}-2025.md`) | TTK 23.07.2025/26 | 2025-2026, tüm seviyeler |
| `guzel-sanatlar-lisesi-{gorsel-sanatlar,tiyatro}-2025.md` | TTK 09.05.2025/6 | 2025-2026, ortak dersler hazırlık-9-10'dan kademeli |
| `guzel-sanatlar-lisesi-{muzik,turk-muzigi}-2025.md` | TTK 09.05.2025/7 | 2025-2026, ortak dersler kademeli |
| `spor-lisesi-2026.md` (+ `spor-lisesi-tematik-2026.md`, varsayılan dışı) | TTK 02.09.2026/102, /103 | 2026-2027, tüm seviyeler (kademe yok) |
| `spor-lisesi-2025.md` (+ `spor-lisesi-tematik-2025.md`, varsayılan dışı) | TTK 09.05.2025/9, /10 | YALNIZ 2025-2026 (ortak dersler kademeli); 2026/102-103 ile 2026-2027'den itibaren tüm seviyelerde kaldırıldı |
| `mesleki-ve-teknik-anadolu-lisesi-2023.md` (yalnız ortak dersler) | TTK 2023/40 · 2024/41 · 2026/85 | 2023-2024'ten itibaren; üç neslin ortak bloğu aynı |

**Aynı çizelgenin yeni kararı = YENİ dosya** (19.09.2026, Spor emsali): eski
dosya yerinde düzenlenmez ve silinmez. `program_key` kararlı anahtardır
(`SchoolConfig.level_programs` ona işaret eder) ve aktif ders yılı eski olan
kurulum eski nesille çözülür; yeni dosya yeni `yururluk` ile eklenir, program
her (seviye, tür) için en yeni KAPSAYAN nesli kendisi seçer. İki sonucu:
(1) hiçbir neslin kapsamadığı seviyede yedek, yürürlüğü BAŞLAMIŞ en yeni
nesildir (henüz başlamamış çizelge geçmiş yıla sızmaz); (2) AÇIK atama
(`level_programs`; varsayılan dışı programlar — Tematik Spor — yalnız böyle
seçilir) yeni nesle kendiliğinden GEÇMEZ: program uyarır, idareci matristen
değiştirir. Eski dosyanın kürasyon notuna kaldıran karar yazılır.

**19.09.2026 TTKB liste denetimi (TTK 02.09.2026/102-104).** Spor'da önceki
nesil boşluğu 2026-2027 için kapandı: 2026/102-103 tüm sınıf seviyelerine
girer; Spor 2023/42 · 2024/47 ve Tematik Spor 2024/48 yalnız GEÇMİŞ 2025-2026
yılının 11-12. sınıfları için eksiktir. Listeye 09.09.2026'da yeni bir çizelge
eklendi ve AKTARILMADI: **Özel Program Uygulayan Hazırlık Sınıfı Bulunan
Anadolu Lisesi** (TTK 02.09.2026 tarihli ve 104 sayılı karar; önceki kararı
yok). Kapsamı: "2026-2027 eğitim ve öğretim yılından itibaren hazırlık
sınıfından başlamak üzere kademeli"; Açıklamalar md. 1'e göre uygulanacağı
"proje protokolü kapsamındaki okullar ve sınıf seviyeleri ilgili Genel Müdürlük
tarafından belirlenir" (okul listesi kararda yok); haftalık 45 saat, iki
tematik alan (Temel Bilimler / Sosyal Bilimler) + çok yönlü gelişim
seçmelileri. Aktarılırsa iki not: (1) çizelge yalnız protokollü okullarda
uygulandığından ÖP Fen/SBL gibi `varsayilan: hayır` olmalıdır — varsayılana
girerse her hazırlıklı Anadolu Lisesi'nin havuzuna karışır; (2) mevcut kademe
kuralı bu kararı İFADE EDEMEZ: `CatalogProgram.covers`
`kademeli_ilk_seviyeler`de 9 ve üstü yoksa tavanı 9 sayar, yani "yalnız
hazırlıktan başlar" yazılsa bile 2026-2027'de 9. sınıfı da kapsar (doğrusu
2027-2028) — önce o kural ve testi düzeltilir. Ham PDF ve döküm:
`data/raw/ttkb-2026-104-ozel-program-al-hazirlik.*`.

Aktarılmayanlar (bilinçli boşluk, `docs/teknik-borc.md` TB2): ÖP hazırlıklı
Anadolu Lisesi (2026/104 — üstteki paragraf), GSL'nin önceki nesil çizelgeleri
(2023/41, 2024/46 — 2026-2027'de yalnız 12. sınıf
ortak dersleri; program en yeni çizelgeyi yedek kullanır ve uyarır), MTAL
seçmeli dersler tablosu ve hazırlıklı MTAL çizelgesi (resmî PDF taranmış
görüntü), MTAL alan/dal meslek dersleri (56 alan — okul elle ekler), Özel
Program Uygulayan Fen/SBL (2025/24-25; ÖP SBL nüshası "TASLAK" ibareli).

**AİHL program/proje dosyaları (B grubu).** Kararın B grubu tablosu yedi
programa ayrılır; her biri ayrı, varsayılan dışı dosyadır ve okul yalnız
uyguladığını ana çizelgenin YANINA işaretler (tek dosyayken yedi programın 74
dersi birden havuza giriyordu). Her dosya ayrıca 10. seviyede SEÇMELİ bir
"Osmanlı Türkçesi" satırı taşır: kararın açıklamaları gereği program/proje
okulunda ders zorunlu değildir ve birleştirme kuralı (tür çatışmasında SEÇMELİ
kazanır) ana çizelgedeki ORTAK kaydı o okulda seçmeliye çevirir — kod
değişikliği olmadan.
Yalnız A grubundan seçen iki programın (Fen ve Sosyal Bilimler; Arapça/İngilizce
dışı dilde hazırlık) dosyası yoktur; onlarda ders ORTAK görünür.

## Yeni çizelge nasıl eklenir

1. Kaynak PDF'i `data/raw/` altına koy (git dışı; ad kalıbı
   `ttkb-<yıl>-<karar sayısı>-<konu>.pdf`), metnini çıkar:
   `docker compose run --rm backend python /repo/scripts/cizelge_pdf_metni.py /repo/data/raw/<dosya>.pdf`
   (`<dosya>.txt` yanına yazılır; döndürülmüş tablo — MTAL ÇÖP'leri — için
   `--dondurulmus`). `data/raw/` git dışı olduğundan worktree'de YOKTUR: ana
   deponun dizini `-v <ana depo>/data/raw:/repo/data/raw` ile bağlanır.
2. `docker compose run --rm backend python /repo/scripts/cizelge_metninden_tablo.py <txt> --md`
   taslağını al; satırları kaynakla karşılaştır, adları kanonik yaz, sınav
   sütununu kürasyon notlarıyla doldur, meta bloğunu ve dayanağı ekle.
   Karşılaştırma SATIR SAYISIYLA yapılır: betik özet satırlarını ("… TOPLAMI",
   "PROGRAM DIŞI ETKİNLİKLER") süzer ve süzgeç bir ders adını yutabilir
   (19.09.2026: "Müzik ve Dramatik Etkinlikler Atölyesi" böyle düşmüştü). `--md`
   olmadan alınan döküm, atladığı değerli satırları tablonun sonunda listeler.
   Sol sütunda grup etiketi olan tablolarda (AİHL B grubu) grup sınırı metinden
   ÇÖZÜLMEZ: etiket kendi grubunun dikey ortasına basılıdır; pypdf
   `extract_text(visitor_text=…)` ile satır ve etiket y koordinatları alınıp
   ilk-son satır ortası etiketle karşılaştırılır.
3. Testler her dosyayı hatasız ayrıştırmayı ve okul türü seçeneklerini
   denetler (`apps/dersler/tests/test_catalog.py`). Kod değişikliği gerekmez;
   yeni okul türü için yalnız `okul.SchoolType`'a satır eklenir.

**Program anahtarı kaldırmak ya da yeniden adlandırmak veri göçü İSTER.** Dosya
İÇERİĞİ değişikliği göç gerektirmez (damga senkronu tetikler) ama anahtar
`SchoolConfig.level_programs` içinde kayıtlıdır: bayat anahtar planda uyarıya
düşer, `validate_level_programs` onu reddettiği için Okul Bilgileri
kaydedilemez ve çizelge matrisi onu kaldıracak kutu çizmez. Emsal:
`okul/migrations/0007_aihl_b_grubu_program_anahtarlari.py` (eski anahtar yeni
anahtarlara AÇILIR, havuz aynı kalır; anahtarlar göçte inline kopyadır).

`ders-adi-takma-adlari.md` katalog değildir: e-Okul yazımlarını kanonik ada
bağlayan seed takma adlarıdır (`ensure_course_aliases`).

## Aktarım tuzakları (19.09.2026, TTK 2026/102-104'te yaşandı)

- **Yeni karar = yeni dosya.** Var olan bir çizelgenin yeni kararı "Program
  dosyaları" bölümündeki kurala göre YENİ dosyadır; gerçek dosya testi
  (`test_catalog_programs.py`) yeni yürürlüğe göre güncellenir.
- **"Metin yok" göründü diye taranmış sanmayın.** 09.2026'dan itibaren TTKB
  PDF'leri DYS çıktısıdır: özgün sayfa tek bir Form XObject'e sarılı, sayfanın
  kendi akışında yalnız çapraz indirme filigranı (rakam dizisi) var. pypdf'in
  düzen kipi forma inmez ve yalnız filigranı döker. `cizelge_pdf_metni.py` bunu
  kendisi çözer ("DYS sarmalı" satırını basar); gerçekten taranmış PDF'te
  "harf çıkmadı" uyarısı verir.
- **Bağlantı değişti ≠ yeniden dizgi.** TTKB listesinde bir çizelgenin adresi
  değiştiyse önce karar sayfasına (s. 1: Sayı, Tarih, "Önceki Kararın Tarih ve
  Sayısı", yürürlük cümlesi) bakın; 2026'da Spor bağlantıları yeni KARARA
  (2026/102-103) çıktı, eski adresler de yayında kaldı.
- **Taslak betiği yardımcıdır, hakem değil.** DYS dizgisinde düzen kipi bazı
  satırların hücrelerini sola sıkıştırır; betik çakışmayı görünce ve satırda
  sütun sayısı kadar hücre varsa hücreleri SIRAYLA eşler ("konum kaydı" notu),
  sol grup etiketinin böldüğü satırı birleştirir ("değerler alt satırdan
  alındı" notu). Notlu her satır kaynakla tek tek karşılaştırılır. Sağlama:
  ORTAK bloktaki hücrelerin sütun toplamı çizelgenin kendi "Ortak Ders Saati
  Toplamı" satırını vermelidir (2026/102-103'te 37-37-35-31) — tutmuyorsa bir
  ortak ders satırı kaçmış ya da kaymıştır. Seçmelilerde toplam yoktur; orada
  güvence her satırın sütun sayısı kadar hücre taşımasıdır (boş hücre "-").
