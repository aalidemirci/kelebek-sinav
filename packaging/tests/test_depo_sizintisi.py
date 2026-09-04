"""`packaging/depo_sizintisi.py` — depo sızıntı kapısının davranış testleri.

Sağlamalı örnek numara ÇALIŞMA ANINDA üretilir, kaynağa düz yazılmaz: aksi
hâlde betik kendi test dosyasını tarayıp bulgu verirdi (kapı kendi kendini
kırardı) — ve deponun içinde gerçek biçimde duran bir numara, uydurma bile
olsa, tam olarak engellemeye çalıştığımız şeydir.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import depo_sizintisi  # noqa: E402


def _saglamali_numara(ilk_dokuz: str = "123456789") -> str:
    """TCKN sağlamasına UYAN uydurma numara üretir (son iki hane hesaplanır)."""
    hane = [int(k) for k in ilk_dokuz]
    tek = hane[0] + hane[2] + hane[4] + hane[6] + hane[8]
    cift = hane[1] + hane[3] + hane[5] + hane[7]
    onuncu = (tek * 7 - cift) % 10
    return f"{ilk_dokuz}{onuncu}{(sum(hane) + onuncu) % 10}"


# --------------------------------------------------------------------------- #
# TCKN sağlaması
# --------------------------------------------------------------------------- #


def test_saglamali_numara_gecerli_sayilir() -> None:
    assert depo_sizintisi.tckn_gecerli_mi(_saglamali_numara()) is True


def test_github_kosu_numarasi_yanlis_pozitif_uretmez() -> None:
    """Çıplak `\\d{11}` deseni bu depoda koşu numaralarını yakalıyordu."""
    assert depo_sizintisi.tckn_gecerli_mi("33257833345") is False


@pytest.mark.parametrize("deger", ["0123456789", "01234567890", "1234567890", "abcdefghijk"])
def test_bicimsiz_degerler_elenir(deger: str) -> None:
    """Kısa/uzun, sıfırla başlayan ve rakam olmayan girdiler TCKN sayılmaz."""
    assert depo_sizintisi.tckn_gecerli_mi(deger) is False


# --------------------------------------------------------------------------- #
# Yol ve uzantı denetimi
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "yol",
    [
        "docs/liste.xls",
        "docs/LISTE.XLS",  # e-Okul ihraçları BÜYÜK harfli iner
        "bir/yer/ogrenciler.xlsx",
        "bir/yer/kayit.csv",
        "yedek/okul.ksbak",
        "backend/data/ks.sqlite3",
        "backend/data/media/foto.txt",
        "media/ekran.txt",
    ],
)
def test_riskli_yollar_yakalanir(yol: str) -> None:
    assert depo_sizintisi.yol_riskli_mi(yol) is True


def test_sentetik_fixturelar_muaf() -> None:
    """Sentetik e-Okul örnekleri ADIYLA muaftır (joker kullanılmaz)."""
    for yol in depo_sizintisi.MUAF_YOLLAR:
        assert depo_sizintisi.yol_riskli_mi(yol) is False


@pytest.mark.parametrize("yol", ["backend/apps/okul/models.py", "README.md", "data/ders.md"])
def test_masum_yollar_gecer(yol: str) -> None:
    assert depo_sizintisi.yol_riskli_mi(yol) is False


# --------------------------------------------------------------------------- #
# Uçtan uca: denetle() + main()
# --------------------------------------------------------------------------- #


def _depo_kur(tmp_path: Path, dosyalar: dict[str, str]) -> Path:
    for goreli, icerik in dosyalar.items():
        hedef = tmp_path / goreli
        hedef.parent.mkdir(parents=True, exist_ok=True)
        hedef.write_text(icerik, encoding="utf-8")
    return tmp_path


def test_metinde_gecen_numara_satiriyla_raporlanir(tmp_path: Path) -> None:
    numara = _saglamali_numara()
    kok = _depo_kur(tmp_path, {"docs/not.md": f"ilk satır\nöğrenci {numara} kaydı\n"})

    riskli, tckn = depo_sizintisi.denetle(kok, ["docs/not.md"])

    assert riskli == []
    assert tckn == ["docs/not.md:2"]


def test_ikili_ve_muaf_dosyalar_taranmaz(tmp_path: Path) -> None:
    numara = _saglamali_numara()
    kok = _depo_kur(
        tmp_path,
        {
            "frontend/package-lock.json": f'{{"hash": "{numara}"}}',
            "docs/kapak.pdf": f"%PDF sahte {numara}",
        },
    )

    _, tckn = depo_sizintisi.denetle(kok, ["frontend/package-lock.json", "docs/kapak.pdf"])

    assert tckn == []


def test_cikti_numaranin_kendisini_BASMAZ(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """KVKK: hata çıktısı da sızıntı kanalıdır — yalnız konum yazılır."""
    numara = _saglamali_numara()
    kok = _depo_kur(tmp_path, {"docs/not.md": f"öğrenci {numara}\n"})
    liste = tmp_path / "liste"
    liste.write_bytes(b"docs/not.md\0")

    kod = depo_sizintisi.main(["--kok", str(kok), "--liste", str(liste)])

    cikti = capsys.readouterr().out
    assert kod == 1
    assert "docs/not.md:1" in cikti
    assert numara not in cikti


def test_temiz_depo_sifir_doner(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    kok = _depo_kur(tmp_path, {"README.md": "# Kelebek Sınav\n"})
    liste = tmp_path / "liste"
    liste.write_bytes(b"README.md\0")

    kod = depo_sizintisi.main(["--kok", str(kok), "--liste", str(liste)])

    assert kod == 0
    assert "başarılı" in capsys.readouterr().out


def test_bos_liste_hata_verir(tmp_path: Path) -> None:
    """Liste üretilemediyse kapı SESSİZCE geçmez (fail-closed)."""
    liste = tmp_path / "liste"
    liste.write_bytes(b"")

    assert depo_sizintisi.main(["--kok", str(tmp_path), "--liste", str(liste)]) == 2
