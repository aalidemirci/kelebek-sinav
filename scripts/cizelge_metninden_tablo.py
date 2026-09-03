"""TTKB haftalık ders çizelgesi PDF'inin düzen-korumalı metninden katalog taslağı üretir.

Kürasyon YARDIMCISIDIR, veri üreticisi değildir: çıktı elle gözden geçirilip
`data/ders-cizelgeleri/<program>.md` dosyasına işlenir (evrakmotoru'nun
"koordinat tabanlı çıkarım + elle teyit" usulü). Girdi, pypdf'in
`extract_text(extraction_mode="layout")` çıktısıdır — sütun hizası korunur, bu
yüzden bir hücrenin hangi sınıf seviyesine ait olduğu BAŞLIK SATIRINDAKİ sütun
merkezine en yakın konumdan bulunur (boş hücreler "-" bile olmayabilir; AİHL
çizelgesinde boş hücre tamamen boştur, konum olmadan seviye çözülemez).

Kullanım (Docker'da; host'a Python kurulmaz — CLAUDE.md §1/5):

    docker compose run --rm backend python /repo/scripts/cizelge_metninden_tablo.py \
        /repo/data/raw/ttkb-2025-05.txt            # satır dökümü (denetim)
    docker compose run --rm backend python /repo/scripts/cizelge_metninden_tablo.py \
        /repo/data/raw/ttkb-2025-05.txt --md       # markdown katalog taslağı

Metin dosyası şöyle üretilir (pypdf konteynerde kuruludur):

    from pypdf import PdfReader
    for i, p in enumerate(PdfReader(pdf).pages, 1):
        print(f"===== SAYFA {i} =====")
        print(p.extract_text(extraction_mode="layout"))

Sınav sütunu (YAZILI/UYGULAMA/YOK) burada YALNIZ ad kalıbıyla önerilir
(`_SINAV_ONERISI`); nihai sınıflama tasarım §7.1 gereği kürasyondur, dosyaya
işlenirken teyit edilir.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

PAGE_RE = re.compile(r"^===== SAYFA (\d+) =====$")
# Başlık satırındaki seviye etiketleri: 'HAZIRLIK', '9', '9.', '9. SINIF' ...
HEADER_TOKEN_RE = re.compile(r"HAZIRLIK(?:\s+SINIFI)?|\b(?:9|10|11|12)\b\.?(?:\s*SINIF)?")
# Hücre: '(1) (2)' / '(1)(2)(4)' / '5' / '-'
CELL_RE = re.compile(r"\(\d+\)(?:\s?\(\d+\))*|(?<![\w(])\d{1,2}(?![\w)])|(?<=\s)-(?=\s|$)")
# Satır SONUNDAKİ "(n)" (kaç kez alınabileceği) ve dipnot yıldızları ada dahil değildir.
NAME_SUFFIX_RE = re.compile(r"(\s*\(\d+\))+\s*$|\s*\*+\s*$|\s*\(\*+\)\s*$")

#: Sol sütundaki grup/bölüm etiketleri (ada dahil değildir).
_ETIKETLER = {
    "ORTAK DERSLER",
    "SEÇMELİ DERSLER",
    "MESLEK DERSLERİ",
    "AKADEMİK",
    "ÇALIŞMALAR",
    "AKADEMİK ÇALIŞMALAR",
    "İNSAN, TOPLUM",
    "İNSAN, TOPLUM VE",
    "İNSAN, TOPLUM VE BİLİM",
    "VE BİLİM",
    "BİLİM",
    "DİN, AHLAK VE",
    "DİN, AHLAK VE DEĞER",
    "DEĞER",
    "KÜLTÜR, SANAT",
    "KÜLTÜR, SANAT VE SPOR",
    "VE SPOR",
    "TEMEL İSLAM BİLİMLERİ",
    "ALAN DERSLERİ",
    "DAL DERSLERİ",
}
#: Sol etiketin ders adına TEK boşlukla yapıştığı bilinen durumlar (AL çizelgesi).
_YAPISIK_ONEKLER = ("İNSAN, TOPLUM VE ", "İNSAN, TOPLUM ", "KÜLTÜR, SANAT VE ", "DİN, AHLAK VE ")
#: Bölüm sınırı / özet satırları — ders değildir.
_OZET_KALIPLARI = (
    "TOPLAMI",
    "SEÇİLEBİLECEK",
    "TOPLAM DERS SAATİ",
    "PROGRAM DIŞI",
    "ETKİNLİKLER",
    "SOSYAL SORUMLULUK",
    "HAYAT BOYU",
    "SERTİFİKASYON",
)

# Sınav biçimi ÖNERİSİ — ad anahtarına göre (nihai karar kürasyon, tasarım §7.1).
_UYGULAMA_ANAHTARLARI = (
    "BEDEN EĞİTİMİ",
    "GÖRSEL SANATLAR",
    "MÜZİK",
    "SPOR EĞİTİMİ",
    "SANAT EĞİTİMİ",
    "HİTABET VE MESLEKİ UYGULAMA",
)
_SINAVSIZ_ANAHTARLARI = ("REHBERLİK VE YÖNLENDİRME", "HEDEF TEMELLİ DESTEK EĞİTİMİ")

_TR_UPPER = str.maketrans("iıçğöşüâîû", "İIÇĞÖŞÜÂÎÛ")
_TR_LOWER = str.maketrans("İIÇĞÖŞÜÂÎÛ", "iıçğöşüâîû")
_KUCUK_KALAN = {"ve", "ile", "veya", "ya", "da", "de"}


def tr_upper(s: str) -> str:
    return s.translate(_TR_UPPER).upper()


def tr_lower(s: str) -> str:
    return s.translate(_TR_LOWER).lower()


def titlecase_tr(name: str) -> str:
    """'SEÇMELİ TÜRK DİLİ VE EDEBİYATI' → 'Seçmeli Türk Dili ve Edebiyatı' (TR-duyarlı)."""

    def kelime(w: str, ilk: bool) -> str:
        if w.upper() == "T.C.":
            return "T.C."
        low = tr_lower(w)
        if not ilk and low in _KUCUK_KALAN:
            return low
        # Tire sonrası ek küçük kalır: KUR’AN-I → Kur'an-ı
        parcalar = low.split("-")
        bas = parcalar[0]
        bas = tr_upper(bas[:1]) + bas[1:] if bas else bas
        return "-".join([bas, *parcalar[1:]])

    name = name.replace("’", "'").replace("–", "-")
    sonuc: list[str] = []
    for i, w in enumerate(name.split(" ")):
        if not w:
            continue
        # Bölü ile bitişik alt adlar ayrı ayrı büyütülür: GÖRSEL SANATLAR/MÜZİK
        sonuc.append("/".join(kelime(p, i == 0 or True) for p in w.split("/")))
    # 'Ve' gibi küçük kalması gerekenler ilk kelime değilse küçültülür.
    out: list[str] = []
    for i, w in enumerate(sonuc):
        out.append(tr_lower(w) if i > 0 and tr_lower(w) in _KUCUK_KALAN else w)
    return " ".join(out)


@dataclass
class Satir:
    sayfa: int
    grup: str
    ad: str
    hucreler: dict[int, str]  # seviye → ham hücre
    bolum: str  # ORTAK / SECMELI / <etiket>
    uyari: str = ""


@dataclass
class Tablo:
    sayfa: int
    baslik: str
    seviyeler: list[int]
    satirlar: list[Satir] = field(default_factory=list)


def _sayfalar(metin: str) -> list[tuple[int, list[str]]]:
    sayfalar: list[tuple[int, list[str]]] = []
    for line in metin.splitlines():
        m = PAGE_RE.match(line.strip())
        if m:
            sayfalar.append((int(m.group(1)), []))
        elif sayfalar:
            sayfalar[-1][1].append(line.rstrip("\n"))
    return sayfalar


def _baslik_sutunlari(line: str) -> dict[int, float] | None:
    """Başlık satırındaki seviye → sütun merkezi; 9-12'nin hepsi yoksa None."""
    merkezler: dict[int, float] = {}
    for m in HEADER_TOKEN_RE.finditer(line):
        tok = m.group(0)
        seviye = 0 if tok.startswith("HAZIRLIK") else int(re.match(r"\d+", tok).group(0))
        # 'HAZIRLIK SINIFI' / '9. SINIF' etiketinin merkezi hücre hizasını verir.
        merkezler.setdefault(seviye, (m.start() + m.end()) / 2)
    return merkezler if {9, 10, 11, 12} <= set(merkezler) else None


def _ad_ve_grup(ad_bolgesi: str) -> tuple[str, str]:
    parcalar = [p.strip() for p in re.split(r" {2,}", ad_bolgesi.strip()) if p.strip()]
    grup: list[str] = []
    while len(parcalar) > 1 and tr_upper(parcalar[0]) in _ETIKETLER:
        grup.append(parcalar.pop(0))
    ad = parcalar[-1] if parcalar else ""
    if len(parcalar) > 1:
        # Etiket listesinde olmayan sol parça: uyarı için grupta tut.
        grup.extend(parcalar[:-1])
    for onek in _YAPISIK_ONEKLER:
        if tr_upper(ad).startswith(onek) and len(ad) > len(onek):
            grup.append(ad[: len(onek)].strip())
            ad = ad[len(onek) :]
            break
    return NAME_SUFFIX_RE.sub("", ad).strip(), " ".join(grup)


def tablolari_cikar(metin: str) -> list[Tablo]:
    tablolar: list[Tablo] = []
    for sayfa_no, lines in _sayfalar(metin):
        baslik_satirlari: list[str] = []
        sutunlar: dict[int, float] | None = None
        tablo: Tablo | None = None
        bolum = "ORTAK"
        for line in lines:
            if sutunlar is None:
                cand = _baslik_sutunlari(line)
                if cand is not None and "DERSLER" in tr_upper(line) or (
                    cand is not None and len(cand) >= 4 and not CELL_RE.search(line[:20])
                ):
                    sutunlar = cand
                    baslik = " ".join(s.strip() for s in baslik_satirlari if s.strip())
                    tablo = Tablo(sayfa_no, baslik, sorted(sutunlar))
                    tablolar.append(tablo)
                    continue
                if line.strip():
                    baslik_satirlari.append(line)
                continue
            assert tablo is not None
            duz = line.strip()
            if not duz:
                continue
            ust = tr_upper(duz)
            if any(k in ust for k in _OZET_KALIPLARI):
                if "ORTAK DERS SAATİ TOPLAMI" in ust or "MESLEK DERS" in ust and "TOPLAM" in ust:
                    bolum = "SECMELI"
                continue
            if "SINIF" in ust and not CELL_RE.search(line):
                continue  # 'SINIF SINIF' başlık devamı
            # Ad bölgesi: ilk seviye sütununun sol sınırından önce kalan metin.
            ilk = min(sutunlar.values())
            ikinci = sorted(sutunlar.values())[1]
            sinir = ilk - (ikinci - ilk) / 2
            ad_bolgesi = line[: int(sinir)]
            deger_bolgesi = line[int(sinir) :]
            ad, grup = _ad_ve_grup(ad_bolgesi)
            hucreler: dict[int, str] = {}
            uyari = ""
            for m in CELL_RE.finditer(deger_bolgesi):
                merkez = int(sinir) + (m.start() + m.end()) / 2
                seviye = min(sutunlar, key=lambda lv: abs(sutunlar[lv] - merkez))
                if seviye in hucreler:
                    uyari = "aynı seviyeye iki hücre"
                hucreler[seviye] = m.group(0)
            if not ad:
                if hucreler:
                    uyari = "adsız satır (değer taşması?)"
                else:
                    continue
            if grup and tr_upper(grup) not in _ETIKETLER:
                uyari = (uyari + "; " if uyari else "") + f"bilinmeyen sol etiket: {grup!r}"
            tablo.satirlar.append(Satir(sayfa_no, grup, ad, hucreler, bolum, uyari))
    return tablolar


def _seviyeler(satir: Satir) -> list[int]:
    return sorted(lv for lv, v in satir.hucreler.items() if v != "-")


def _sinav_onerisi(ad: str) -> str:
    ust = tr_upper(ad)
    if any(k in ust for k in _SINAVSIZ_ANAHTARLARI):
        return "YOK"
    if any(k in ust for k in _UYGULAMA_ANAHTARLARI):
        return "UYGULAMA"
    return "YAZILI"


def _seviye_metni(seviyeler: list[int]) -> str:
    """[9,10,11,12] → '9-12'; [0,9,10] → '0, 9, 10'; [10,11,12] → '10-12'."""
    if not seviyeler:
        return "-"
    parcalar: list[str] = []
    i = 0
    while i < len(seviyeler):
        j = i
        while j + 1 < len(seviyeler) and seviyeler[j + 1] == seviyeler[j] + 1 and seviyeler[i] != 0:
            j += 1
        parcalar.append(str(seviyeler[i]) if i == j else f"{seviyeler[i]}-{seviyeler[j]}")
        i = j + 1
    return ", ".join(parcalar)


def _kanonik_adlar(katalog_dizini: Path) -> dict[str, str]:
    """Mevcut katalog dosyalarındaki adlar — büyük/küçük harf farkı olmadan eşleştirme."""
    adlar: dict[str, str] = {}
    for md in sorted(katalog_dizini.glob("*.md")):
        for line in md.read_text(encoding="utf-8").splitlines():
            if not line.startswith("|"):
                continue
            hucre = line.strip("|").split("|")[0].strip()
            if hucre and hucre.casefold() != "ders" and not set(hucre) <= {"-", ":", " "}:
                adlar.setdefault(tr_upper(hucre).replace("’", "'"), hucre)
    return adlar


def dokum(tablolar: list[Tablo]) -> str:
    out: list[str] = []
    for t in tablolar:
        out.append(f"\n### SAYFA {t.sayfa} — {t.baslik}\nSeviyeler: {t.seviyeler}")
        for s in t.satirlar:
            hucre = "  ".join(f"{lv}:{s.hucreler.get(lv, '·')}" for lv in t.seviyeler)
            uy = f"   !! {s.uyari}" if s.uyari else ""
            grup = f" [{s.grup}]" if s.grup else ""
            out.append(f"{s.bolum:8} {s.ad}{grup} | {hucre}{uy}")
    return "\n".join(out)


def markdown(tablolar: list[Tablo], kanonik: dict[str, str]) -> str:
    out: list[str] = []
    for t in tablolar:
        out.append(f"\n## SAYFA {t.sayfa} — {t.baslik}\n")
        out.append("| Ders | Seviyeler | Tür | Sınav |")
        out.append("|---|---|---|---|")
        for s in t.satirlar:
            seviyeler = _seviyeler(s)
            if not seviyeler:
                continue
            key = tr_upper(s.ad).replace("’", "'")
            ad = kanonik.get(key) or titlecase_tr(s.ad)
            tur = "ORTAK" if s.bolum == "ORTAK" else "SECMELI"
            not_ = f"  <!-- {s.uyari} -->" if s.uyari else ""
            out.append(
                f"| {ad} | {_seviye_metni(seviyeler)} | {tur} | {_sinav_onerisi(ad)} |{not_}"
            )
    return "\n".join(out)


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    md = "--md" in argv
    yollar = [Path(a) for a in argv if not a.startswith("--")]
    katalog = Path(__file__).resolve().parent.parent / "data" / "ders-cizelgeleri"
    kanonik = _kanonik_adlar(katalog) if katalog.is_dir() else {}
    for yol in yollar:
        tablolar = tablolari_cikar(yol.read_text(encoding="utf-8"))
        print(f"\n===== {yol.name}: {len(tablolar)} tablo =====")
        print(markdown(tablolar, kanonik) if md else dokum(tablolar))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
