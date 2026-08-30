"""e-Okul rapor önişleyicisi — blok düzenli ihraçları düz matrise indirger.

Neden gerekli? e-Okul'un "Excel" ihraçları uygulama şablonuna BENZEMEZ:

* **Sınıf listesi (OOG01001R020)** tek sayfada ŞUBE ŞUBE bloklar hâlinde gelir.
  Her blok: çok satırlı kurum başlığı (``AL - 10. Sınıf / A Şubesi (ALANI YOK)
  Sınıf Listesi``) → sınıf öğretmeni/başkanı satırları → sütun başlığı (``S.No |
  Öğrenci No | Adı | Soyadı | Cinsiyeti | Pansiyon Durum``) → veri satırları →
  ``Kız/Erkek/Toplam Öğrenci Sayısı`` dipnotu. **Sınıf/şube için sütun YOKTUR** —
  bilgi yalnız blok başlığındadır; ham matris doğrudan ayrıştırıcıya verilirse
  "Zorunlu sütun bulunamadı: class" hatasıyla reddedilir.
* **Personel listesi (OOK01001R1)** düz tablodur ama sonunda ``Toplam Personel
  Sayısı: N`` dipnotu ve tarih/saat seri numaralarından oluşan bir satır vardır;
  bunlar temizlenmezse dipnot satırı personel kaydı olarak yazılır.

Bu modül SAFTIR (DB'siz, Django'suz) ve **satır sayısını korur**: gürültü
satırları silinmez, BOŞALTILIR. Böylece rapordaki "satır 47 atlandı" uyarıları
kullanıcının Excel'de gördüğü satır numarasıyla aynı kalır.
"""

from __future__ import annotations

import re
from typing import Any

from apps.okul.excel_ogrenci import normalize_header
from apps.okul.normalize import _ascii_upper

#: Düzleştirmede matrisin başına eklenen sentetik sütunun başlığı. Ayrıştırıcının
#: `COLUMN_SYNONYMS["class"]` listesindeki 'sinif sube' ile eşleşir.
SINIF_SUTUN_BASLIGI = "Sınıf/Şube"

#: Blok başlığı: '10. Sınıf / A Şubesi' (ASCII'ye katlanmış metinde aranır).
_BLOK_RE = re.compile(r"(\d{1,2})\s*\.?\s*SINIF\s*/\s*([^\s/()]+)\s*SUBESI")
#: Hazırlık bloğu: 'Hazırlık Sınıfı / A Şubesi'.
_HAZ_BLOK_RE = re.compile(r"HAZIRLIK\s*SINIF\w*\s*/\s*([^\s/()]+)\s*SUBESI")
#: Dipnot: 'Toplam Öğrenci Sayısı : 35', 'Toplam Personel Sayısı: 103'.
_DIPNOT_RE = re.compile(r"(OGRENCI|PERSONEL|TOPLAM)\s*\w*\s*SAYISI")
#: e-Okul rapor kodu ('OOG01001R020', 'OOK01001R1') — sayfa altı imzası.
_RAPOR_KODU_RE = re.compile(r"\bOO[A-Z]\d+R\d+\b")


def _metin(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bos_satir(cells: list[Any]) -> bool:
    return all(_metin(c) == "" for c in cells)


def blok_sinifi(cells: list[Any]) -> str | None:
    """Satır bir şube bloğunun başlığıysa kanonik sınıf metnini döndürür ('10/İ').

    Eşleşme ASCII'ye katlanmış metinde yapılır ('Sınıf' → 'SINIF'), ama **şube
    harfi HAM metinden kesilir**: 'İ' şubesi 'I'ya çökmemelidir (aynı okulda her
    ikisi de bulunur — `normalize.tr_upper` gerekçesi).
    """
    for cell in cells:
        ham = _metin(cell)
        if not ham:
            continue
        katli = _ascii_upper(ham)
        if len(katli) != len(ham):  # katlama 1:1 değilse konum kesme güvenli değil
            continue
        m = _BLOK_RE.search(katli)
        if m is not None:
            return f"{int(m.group(1))}/{ham[m.start(2) : m.end(2)]}"
        h = _HAZ_BLOK_RE.search(katli)
        if h is not None:
            return f"Hazırlık/{ham[h.start(1) : h.end(1)]}"
    return None


def _veri_basligi_mi(cells: list[Any]) -> bool:
    """Satır bir bloğun sütun başlığı mı? ('S.No | Öğrenci No | Adı | Soyadı')."""
    basliklar = {normalize_header(c) for c in cells if _metin(c)}
    numarali = any(b in {"ogrenci no", "okul no", "ogrenci numarasi"} for b in basliklar)
    adli = any(b in {"adi", "adi soyadi", "soyadi", "ogrenci adi soyadi"} for b in basliklar)
    return numarali and adli


def sayac_veya_kod_mu(cells: list[Any]) -> bool:
    """Satır METİNSEL bir rapor imzası mı? ('Toplam Öğrenci Sayısı', 'OOG01001R020')."""
    for cell in cells:
        ham = _metin(cell)
        if not ham:
            continue
        katli = _ascii_upper(ham)
        if _DIPNOT_RE.search(katli) or _RAPOR_KODU_RE.search(katli):
            return True
    return False


def _yalniz_sayi_satiri(cells: list[Any]) -> bool:
    """Satırın dolu hücrelerinin TAMAMI sayı mı? (e-Okul sayfa altı tarih/saat damgası)."""
    dolu = [c for c in cells if _metin(c) != ""]
    return bool(dolu) and all(_sayi_mi(c) for c in dolu)


def dipnot_mu(cells: list[Any]) -> bool:
    """Satır rapor gürültüsü mü? (sayaç dipnotu, rapor kodu, tarih/saat serisi)."""
    return sayac_veya_kod_mu(cells) or _yalniz_sayi_satiri(cells)


def _sayi_mi(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int | float):
        return True
    try:
        float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return False
    return True


def sinif_listesi_mi(grid: list[list[Any]]) -> bool:
    """Matris e-Okul sınıf listesi biçiminde mi? (en az bir şube bloğu başlığı)."""
    return any(blok_sinifi(cells) is not None for cells in grid)


def duzlestir_sinif_listesi(grid: list[list[Any]]) -> tuple[list[list[Any]], list[str]]:
    """Blok düzenli sınıf listesini tek başlıklı düz matrise indirger.

    Çıktı matrisi girdiyle **aynı satır sayısındadır**: başlık/dipnot/ara
    satırlar boşaltılır, veri satırlarının başına bloğun sınıf/şube değeri
    eklenir. İlk bloğun sütun başlığı korunur ve başına `SINIF_SUTUN_BASLIGI`
    yazılır; sonraki blokların başlık satırları boşaltılır.
    """
    cikti: list[list[Any]] = []
    notlar: list[str] = []
    sinif = ""
    basliktan_sonra = False
    ilk_baslik_yazildi = False
    blok_sayisi = 0
    veri_sayisi = 0
    sinifsiz_veri = 0

    for cells in grid:
        yeni_sinif = blok_sinifi(cells)
        if yeni_sinif is not None:
            sinif = yeni_sinif
            blok_sayisi += 1
            basliktan_sonra = False
            cikti.append([])
            continue
        if _veri_basligi_mi(cells):
            basliktan_sonra = True
            if ilk_baslik_yazildi:
                cikti.append([])  # tekrarlayan blok başlıkları veri sayılmasın
            else:
                ilk_baslik_yazildi = True
                cikti.append([SINIF_SUTUN_BASLIGI, *cells])
            continue
        # Blok İÇİNDE yalnız METİNSEL imza (sayaç/rapor kodu) bloğu bitirir.
        # "Tüm hücreleri sayı" kuralı burada UYGULANMAZ: adı boş kalmış bir
        # öğrenci satırı da yalnız sayılardan oluşur ve sessizce yutulmamalı —
        # veri satırı sayılıp `parse_rows` tarafından "adı boş" diye RAPORLANIR.
        if sayac_veya_kod_mu(cells) or (not basliktan_sonra and dipnot_mu(cells)):
            basliktan_sonra = False  # blok bitti; sonraki başlığa kadar veri yok
            # Sınıf da SIFIRLANIR: başlığı tanınmayan bir sonraki blok, bir
            # önceki bloğun şubesini DEVRALMAMALI (yoksa 12 bloğun birinde
            # başlık deseni tutmadığında o şubenin öğrencileri sessizce komşu
            # şubeye yazılırdı — sessiz veri bozulması).
            sinif = ""
            cikti.append([])
            continue
        if basliktan_sonra and not _bos_satir(cells):
            # `sinif` boşsa (bloğun başlığı çözülemedi) satır YİNE de veri
            # olarak geçer: sınıf hücresi boş kalır ve `parse_rows` bunu
            # satır numarasıyla "Sınıf/şube çözülemedi" diye RAPORLAR.
            # Sessizce düşürmek, eksiği ancak elle sayarak fark edilir kılardı.
            cikti.append([sinif, *cells])
            veri_sayisi += 1
            if not sinif:
                sinifsiz_veri += 1
            continue
        cikti.append([])

    if veri_sayisi == 0:
        # Blok başlığı görüldü ama veri çıkmadı: tanımadığımız bir rapor
        # varyantı olabilir — ham matrise dokunma, normal hata yolu işlesin.
        return grid, []

    notlar.append(
        f"e-Okul sınıf listesi biçimi algılandı: {blok_sayisi} şube bloğu "
        f"tek tabloya indirgendi ({veri_sayisi} öğrenci satırı); sınıf/şube "
        f"bilgisi blok başlıklarından okundu."
    )
    if sinifsiz_veri:
        notlar.append(
            f"{sinifsiz_veri} satırın bloğunda sınıf/şube başlığı çözülemedi; "
            f"bu satırlar atlananlar listesinde satır numarasıyla görünür."
        )
    return cikti, notlar


def temizle_rapor_dipnotlari(grid: list[list[Any]]) -> tuple[list[list[Any]], list[str]]:
    """Sayaç dipnotu / rapor kodu / tarih damgası satırlarını boşaltır.

    "Dolu hücrelerinin tamamı sayı" kuralı YALNIZ e-Okul imzası taşıyan
    matrislerde uygulanır (sayaç dipnotu ya da rapor kodu görülmüşse). Uygulama
    şablonunda ve pano yapıştırmasında böyle bir satır rapor gürültüsü değil,
    ADI EKSİK BİR VERİ SATIRIDIR: orada boşaltmak, `parse_rows`ın satır
    numarasıyla yazacağı "Sınıf/şube çözülemedi" uyarısını yok eder ve
    kullanıcıya sebebini yanlış söylerdi.
    """
    eokul_imzasi = any(sayac_veya_kod_mu(cells) for cells in grid)
    cikti: list[list[Any]] = []
    temizlenen = 0
    for cells in grid:
        if _bos_satir(cells):
            cikti.append(list(cells))
            continue
        gurultu = sayac_veya_kod_mu(cells) or (eokul_imzasi and _yalniz_sayi_satiri(cells))
        if gurultu:
            cikti.append([])
            temizlenen += 1
        else:
            cikti.append(list(cells))
    if temizlenen == 0:
        return grid, []
    return cikti, [f"e-Okul rapor dipnotu olarak {temizlenen} satır atlandı (sayaç/tarih satırı)."]


def hazirla_ogrenci_matrisi(grid: list[list[Any]]) -> tuple[list[list[Any]], list[str]]:
    """Öğrenci girdisini ayrıştırıcıya hazır hâle getirir (blok düzleştirme + dipnot)."""
    if sinif_listesi_mi(grid):
        return duzlestir_sinif_listesi(grid)
    return temizle_rapor_dipnotlari(grid)


def hazirla_personel_matrisi(grid: list[list[Any]]) -> tuple[list[list[Any]], list[str]]:
    """Personel girdisini ayrıştırıcıya hazır hâle getirir (dipnot temizliği)."""
    return temizle_rapor_dipnotlari(grid)


__all__ = [
    "SINIF_SUTUN_BASLIGI",
    "blok_sinifi",
    "dipnot_mu",
    "sayac_veya_kod_mu",
    "duzlestir_sinif_listesi",
    "hazirla_ogrenci_matrisi",
    "hazirla_personel_matrisi",
    "sinif_listesi_mi",
    "temizle_rapor_dipnotlari",
]
