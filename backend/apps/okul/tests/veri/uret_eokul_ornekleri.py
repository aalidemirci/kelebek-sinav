"""Sentetik e-Okul .xls örneklerini üretir (testlerin ikili fixture'ları).

KVKK: Bu betik gerçek bir e-Okul dosyasını OKUMAZ, maskelemez, dönüştürmez —
yerleşimi sıfırdan kurar ve tüm adlar UYDURMADIR. Depoya giren tek ikili budur;
gerçek ihraçlar `.gitignore` ile engellenir (`*.xls`, `*.XLS`).

Yerleşim, 30.08.2026'da gerçek iki rapor incelenerek çıkarıldı:

* ``OOG01001R020`` (Sınıf/Şube Öğrenci Listesi) — tek sayfada şube şube bloklar;
  sınıf/şube bilgisi YALNIZ blok başlığındadır. Örnekte bilinçli olarak **I ve İ
  şubeleri yan yana** durur: Türk alfabesinde ayrı iki harftir ve ASCII'ye
  katlayan bir normalize edici iki sınıfı tek şubeye çökertir (bkz.
  `normalize.tr_upper`).
* ``OOK01001R1`` (Personel Listesi) — düz tablo + ``Toplam Personel Sayısı``
  dipnotu + tarih/saat seri numaralarından oluşan sayfa altı satırı.

Yeniden üretmek için (xlwt yalnız burada gerekir, projenin bağımlılığı DEĞİLDİR):

    docker compose run --rm backend sh -c \\
        "pip install -q xlwt==1.3.0 && python apps/okul/tests/veri/uret_eokul_ornekleri.py"
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import xlwt
except ImportError:  # pragma: no cover — yalnız fixture üretiminde çalışır
    sys.exit("Bu betik xlwt gerektirir: pip install xlwt==1.3.0")

BURASI = Path(__file__).resolve().parent

KURUM_BASLIGI = (
    "T.C.\n"
    "ÖRNEK VALİLİĞİ\n"
    "Örnek İlçe / Örnek Anadolu Lisesi Müdürlüğü\n"
    "AL - {sinif}. Sınıf / {sube} Şubesi (ALANI YOK) Sınıf Listesi "
)

# Uydurma adlar — gerçek hiçbir kişiye ait değildir.
SUBE_OGRENCILERI: dict[str, list[tuple[int, str, str, str]]] = {
    "I": [
        (13, "ALTAY", "GÖKMEN", "Erkek"),
        (19, "NAZLI SU", "IŞIKÇI", "Kız"),
        (204, "BERKAY", "ÖZDEMİRCİ", "Erkek"),
    ],
    "İ": [
        (7, "ELİF NAZ", "ÇINARLI", "Kız"),
        (88, "TUNAHAN", "ŞAHBAZ", "Erkek"),
        (145, "İREM", "ULUDAĞLI", "Kız"),
    ],
}

PERSONEL = [
    ("SELMA YURTSEVEN", "Müdür", "KADROLU", "Tarih"),
    ("KEREM DALGIÇ", "Müdür Yardımcısı", "KADROLU", "Coğrafya"),
    ("NURAY IŞIKÇI", "Öğretmen", "KADROLU", "Matematik"),
    ("İLKAY ÖZGÜNEŞ", "Sözleşmeli Öğretmen(657 S.K. 4/B)", "SÖZLEŞMELİ", "İngilizce"),
]


def _yaz(sh: xlwt.Worksheet, satir: int, hucreler: dict[int, object]) -> None:
    for sutun, deger in hucreler.items():
        sh.write(satir, sutun, deger)


def sinif_listesi(hedef: Path) -> None:
    """OOG01001R020 yerleşimini kurar (iki şube bloğu: 10/I ve 10/İ)."""
    wb = xlwt.Workbook(encoding="utf-8")
    sh = wb.add_sheet("Sheet1")
    r = 0
    for sube, ogrenciler in SUBE_OGRENCILERI.items():
        _yaz(sh, r, {0: KURUM_BASLIGI.format(sinif=10, sube=sube)})
        _yaz(sh, r + 1, {0: "Sınıf Öğretmeni: ", 7: "Sınıf Başkanı:"})
        _yaz(sh, r + 2, {0: "Sınıf Müdür Yrd: KEREM DALGIÇ", 7: "Sınıf Başkan Yrd:"})
        _yaz(
            sh,
            r + 3,
            {
                0: "S.No",
                1: "Öğrenci No",
                3: "Adı",
                7: "Soyadı",
                11: "Cinsiyeti",
                13: "Pansiyon Durum",
            },
        )
        for i, (no, ad, soyad, cinsiyet) in enumerate(ogrenciler, start=1):
            _yaz(sh, r + 3 + i, {0: i, 1: no, 3: ad, 7: soyad, 11: cinsiyet})
        kiz = sum(1 for o in ogrenciler if o[3] == "Kız")
        _yaz(
            sh,
            r + 4 + len(ogrenciler),
            {
                0: "Kız Öğrenci Sayısı        :",
                4: kiz,
                5: "Erkek Öğrenci Sayısı    :",
                9: len(ogrenciler) - kiz,
                11: "Toplam Öğrenci Sayısı    :",
                14: len(ogrenciler),
            },
        )
        r += 5 + len(ogrenciler)
    # Sayfa altı: tarih/saat seri numaraları + rapor kodu (e-Okul imzası).
    _yaz(sh, r, {11: 46261.0, 12: 0.755370370367018, 14: 1})
    _yaz(sh, r + 1, {1: "OOG01001R020"})
    wb.save(str(hedef))


def personel_listesi(hedef: Path) -> None:
    """OOK01001R1 yerleşimini kurar (düz tablo + sayaç dipnotu + tarih satırı)."""
    wb = xlwt.Workbook(encoding="utf-8")
    sh = wb.add_sheet("Sheet1")
    _yaz(sh, 0, {0: "ADI SOYADI", 6: "GÖREVİ", 8: "KADRO DURUMU", 10: "BRANŞI"})
    for i, (ad_soyad, gorev, kadro, brans) in enumerate(PERSONEL, start=1):
        _yaz(sh, i, {0: ad_soyad, 6: gorev, 8: kadro, 10: brans})
    _yaz(sh, len(PERSONEL) + 1, {0: f"Toplam Personel Sayısı: {len(PERSONEL)}"})
    _yaz(sh, len(PERSONEL) + 2, {12: 46260.0, 14: 0.898055555553583})
    wb.save(str(hedef))


if __name__ == "__main__":
    sinif_listesi(BURASI / "eokul_sinif_listesi.xls")
    personel_listesi(BURASI / "eokul_personel_listesi.xls")
    print("Sentetik e-Okul örnekleri üretildi:", BURASI)
