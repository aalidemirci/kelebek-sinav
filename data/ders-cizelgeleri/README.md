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
| `hazirlik` | hayır | `evet`: hazırlık sınıfı bulunan okul çizelgesi. Bölüm grubunda okulun bayrağıyla eşleşen varyant seçilir; tek varyant varsa her iki okul da onu kullanır (AİHL tek çizelgedir, 0. seviye satırları hazırlıksız okulda okul seviye kümesince düşer). |
| `bolum` | hayır | Bölüm/varyant etiketi (GSL: Görsel Sanatlar/Tiyatro/Müzik/Türk Müziği; Spor: Tematik program; AİHL: B grubu). Aynı türün farklı bölümleri varsayılanda BİRLEŞİR. |
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

## Program dosyaları (03.09.2026)

| Dosya | Karar | Yürürlük |
|---|---|---|
| `anadolu-lisesi-2025.md` · `anadolu-lisesi-hazirlik-2025.md` | TTK 09.05.2025/5 | 2025-2026, tüm seviyeler |
| `fen-lisesi-2025.md` · `fen-lisesi-hazirlik-2025.md` | TTK 09.05.2025/5 | 2025-2026, tüm seviyeler |
| `sosyal-bilimler-lisesi-2025.md` · `sosyal-bilimler-lisesi-hazirlik-2025.md` | TTK 09.05.2025/5 | 2025-2026, tüm seviyeler |
| `anadolu-imam-hatip-lisesi-2025.md` (+ `…-program-proje-2025.md`, varsayılan dışı) | TTK 23.07.2025/26 | 2025-2026, tüm seviyeler |
| `guzel-sanatlar-lisesi-{gorsel-sanatlar,tiyatro}-2025.md` | TTK 09.05.2025/6 | 2025-2026, ortak dersler hazırlık-9-10'dan kademeli |
| `guzel-sanatlar-lisesi-{muzik,turk-muzigi}-2025.md` | TTK 09.05.2025/7 | 2025-2026, ortak dersler kademeli |
| `spor-lisesi-2025.md` (+ `spor-lisesi-tematik-2025.md`, varsayılan dışı) | TTK 09.05.2025/9, /10 | 2025-2026, ortak dersler kademeli |
| `mesleki-ve-teknik-anadolu-lisesi-2023.md` (yalnız ortak dersler) | TTK 2023/40 · 2024/41 · 2026/85 | 2023-2024'ten itibaren; üç neslin ortak bloğu aynı |

Aktarılmayanlar (bilinçli boşluk, `docs/teknik-borc.md` TB2): GSL/Spor'un
önceki nesil çizelgeleri (2023/41-42, 2024/46-47 — 2026-2027'de yalnız 12. sınıf
ortak dersleri; program en yeni çizelgeyi yedek kullanır ve uyarır), MTAL
seçmeli dersler tablosu ve hazırlıklı MTAL çizelgesi (resmî PDF taranmış
görüntü), MTAL alan/dal meslek dersleri (56 alan — okul elle ekler), Özel
Program Uygulayan Fen/SBL (2025/24-25; ÖP SBL nüshası "TASLAK" ibareli).

## Yeni çizelge nasıl eklenir

1. Kaynak PDF'i `data/raw/` altına koy (git dışı), metnini çıkar:
   `docker compose run --rm backend python -c "…pypdf extract_text(extraction_mode='layout')…"`
   (döndürülmüş tablo — MTAL ÇÖP'leri — için `extract_text(orientations=(0,90,180,270))`).
2. `docker compose run --rm backend python /repo/scripts/cizelge_metninden_tablo.py <txt> --md`
   taslağını al; satırları kaynakla karşılaştır, adları kanonik yaz, sınav
   sütununu kürasyon notlarıyla doldur, meta bloğunu ve dayanağı ekle.
3. Testler her dosyayı hatasız ayrıştırmayı ve okul türü seçeneklerini
   denetler (`apps/dersler/tests/test_catalog.py`). Kod değişikliği gerekmez;
   yeni okul türü için yalnız `okul.SchoolType`'a satır eklenir.

`ders-adi-takma-adlari.md` katalog değildir: e-Okul yazımlarını kanonik ada
bağlayan seed takma adlarıdır (`ensure_course_aliases`).
