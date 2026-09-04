"""Depoya kişisel veri girmediğini doğrula — `veri_sizintisi.py`'nin depo eşi.

`veri_sizintisi.py` DAĞITIM PAKETİNİ denetler; bu betik aynı soruyu depo için
sorar: git'in izlediği dosyalar arasında öğrenci/personel verisi taşıyabilecek
bir şey var mı? `.gitignore` bunu ÖNLER ama denetlemez — `git add -f` ile
zorlanan, listede olmayan bir uzantıyla giren (`.csv`) ya da bir markdown'a
yapıştırılmış gerçek bir numara sessizce depoya girer ve bir kez girdiyse
`.gitignore` onu geçmişten çıkarmaz.

İki denetim var:

1. **Yol/uzantı** — veri dosyası biçimleri ve gerçek verinin yaşadığı dizinler.
   Sentetik test fixture'ları AÇIK LİSTEYLE muaftır; joker kullanılmaz, çünkü
   `veri/*.xls` deseni o klasöre bırakılan GERÇEK bir e-Okul ihracını da muaf
   tutardı (`.gitignore` içindeki aynı gerekçe).
2. **T.C. kimlik numarası** — 11 haneli her sayı değil, TCKN'nin kendi
   sağlama kuralına UYAN sayılar aranır. Çıplak `\\d{11}` deseni bu depoda
   GitHub Actions koşu numaralarını (ör. 33257833345) yakalıyordu; sağlama
   kuralı yanlış pozitifleri ~%99 eler.

Çıktı KİŞİSEL VERİ İÇERMEZ: bulgu satırında yalnız dosya yolu ve satır numarası
yazılır, eşleşen sayının kendisi asla basılmaz (veri_sizintisi.py'deki aynı
ilke — hata çıktısı da sızıntı kanalıdır).

Kullanım (dosya listesi NUL ayraçlıdır; `git ls-files -z` çıktısı):

    git ls-files -z > liste
    python packaging/depo_sizintisi.py --kok . --liste liste
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Iterable, Sequence
from pathlib import Path

#: Kişisel veri taşıyan dosya biçimleri. e-Okul ihraçları BÜYÜK harfli `.XLS`
#: iner; karşılaştırma casefold ile yapılır.
RISKLI_UZANTILAR = frozenset(
    {".xls", ".xlsx", ".xlsm", ".csv", ".sqlite", ".sqlite3", ".db", ".ksbak", ".ddbak"}
)

#: Gerçek verinin yaşadığı dizinler (`.gitignore` ile aynı liste).
RISKLI_DIZIN_ONEKLERI = ("backend/data/", "data/raw/", "media/")

#: Sentetik fixture'lar — adları TEK TEK yazılır (joker YOK; docstring'e bakın).
MUAF_YOLLAR = frozenset(
    {
        "backend/apps/okul/tests/veri/eokul_sinif_listesi.xls",
        "backend/apps/okul/tests/veri/eokul_personel_listesi.xls",
    }
)

#: TCKN taramasından muaf dosyalar: üretilmiş kilit/özet dosyaları uzun rakam
#: dizileri taşır ve elle yazılmadıkları için kişisel veri kanalı değildirler.
TCKN_MUAF_YOLLAR = frozenset({"frontend/package-lock.json", "coverage.xml"})

#: Metin sayılmayan uzantılar — TCKN taraması yalnız metinde anlamlıdır.
IKILI_UZANTILAR = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".pdf",
        ".zip",
        ".gz",
        ".xls",
        ".xlsx",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".exe",
        ".dll",
        ".deb",
    }
)

#: 1 MB üstü metin dosyası taranmaz (üretilmiş dosyalar; maliyet/fayda).
AZAMI_TARAMA_BAYTI = 1_048_576

_ONBIR_HANE = re.compile(r"(?<!\d)\d{11}(?!\d)")


def tckn_gecerli_mi(deger: str) -> bool:
    """T.C. kimlik numarası sağlama kuralı (MERNİS): rastgele sayıyı eler.

    Kural: 11 hane · ilk hane 0 olamaz · 10. hane
    ``((tek basamaklar toplamı × 7) − çift basamaklar toplamı) mod 10`` ·
    11. hane ilk on basamağın toplamının mod 10'u.
    """
    if len(deger) != 11 or not deger.isdigit() or deger[0] == "0":
        return False
    hane = [int(k) for k in deger]
    tek = hane[0] + hane[2] + hane[4] + hane[6] + hane[8]
    cift = hane[1] + hane[3] + hane[5] + hane[7]
    if (tek * 7 - cift) % 10 != hane[9]:
        return False
    return sum(hane[:10]) % 10 == hane[10]


def yol_riskli_mi(goreli_yol: str) -> bool:
    """Dosya yolu, biçimi ya da bulunduğu dizin yüzünden riskli mi?"""
    if goreli_yol in MUAF_YOLLAR:
        return False
    if goreli_yol.startswith(RISKLI_DIZIN_ONEKLERI):
        return True
    return Path(goreli_yol).suffix.casefold() in RISKLI_UZANTILAR


def tckn_satirlari(kok: Path, goreli_yol: str) -> list[int]:
    """Dosyada TCKN sağlamasına uyan sayıların SATIR numaraları (değerler DEĞİL)."""
    if goreli_yol in TCKN_MUAF_YOLLAR:
        return []
    if Path(goreli_yol).suffix.casefold() in IKILI_UZANTILAR:
        return []
    tam_yol = kok / goreli_yol
    try:
        if not tam_yol.is_file() or tam_yol.stat().st_size > AZAMI_TARAMA_BAYTI:
            return []
        icerik = tam_yol.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # Okunamayan ya da metin olmayan dosya: yol denetimi zaten kapsıyor.
        return []
    return [
        no
        for no, satir in enumerate(icerik.splitlines(), start=1)
        if any(tckn_gecerli_mi(m.group()) for m in _ONBIR_HANE.finditer(satir))
    ]


def denetle(kok: Path, yollar: Iterable[str]) -> tuple[list[str], list[str]]:
    """(riskli dosya yolları, 'yol:satır' biçiminde TCKN bulguları) döndürür."""
    riskli: list[str] = []
    tckn: list[str] = []
    for goreli_yol in sorted(set(yollar)):
        if not goreli_yol:
            continue
        if yol_riskli_mi(goreli_yol):
            riskli.append(goreli_yol)
            continue  # dosyayı ayrıca içerik için açmaya gerek yok
        tckn.extend(f"{goreli_yol}:{no}" for no in tckn_satirlari(kok, goreli_yol))
    return riskli, tckn


def liste_oku(liste_yolu: Path) -> list[str]:
    """`git ls-files -z` çıktısını okur (NUL ayraçlı)."""
    ham = liste_yolu.read_bytes().decode("utf-8", errors="surrogateescape")
    return [parca for parca in ham.split("\0") if parca]


def argumanlari_ayristir(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Depoya kişisel veri girmediğini denetler (git izlenen dosyalar)."
    )
    parser.add_argument("--kok", type=Path, default=Path("."), help="Depo kökü")
    parser.add_argument(
        "--liste",
        type=Path,
        required=True,
        help="`git ls-files -z` çıktısını taşıyan dosya (konteynerde git yoktur)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = argumanlari_ayristir(argv)
    kok: Path = args.kok
    if not kok.is_dir():
        print(f"HATA: depo kökü bulunamadı: {kok}")
        return 2
    if not args.liste.is_file():
        print(f"HATA: dosya listesi bulunamadı: {args.liste}")
        return 2

    yollar = liste_oku(args.liste)
    if not yollar:
        print("HATA: dosya listesi boş — `git ls-files -z` çıktısı üretilemedi.")
        return 2

    riskli, tckn = denetle(kok, yollar)
    if riskli or tckn:
        print("HATA: depoda kişisel veri olabilecek içerik bulundu:")
        for yol in riskli:
            print(f"  - veri dosyası: {yol}")
        for konum in tckn:
            # Yalnız konum; eşleşen sayı BASILMAZ.
            print(f"  - T.C. kimlik numarası olabilecek sayı: {konum}")
        print(
            "\nSentetik bir örnek eklediyseniz packaging/depo_sizintisi.py içindeki "
            "MUAF_YOLLAR listesine ADIYLA yazın (joker kullanmayın)."
        )
        return 1

    print(f"Depo veri denetimi başarılı: {len(yollar)} izlenen dosyada bulgu yok.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
