"""apps.okul.excel_personel — SADELEŞMİŞ personel parser testleri.

OYS şablonundan fark (tasarım §3.5): e-posta ve Rol/Kapsam çiftleri YOK —
standalone'da personel login olmaz, roller (kurul üyelikleri) personel
yüklendikten sonra ayrıca tanımlanır. Beklenen şablon: | Ad Soyad | Unvan | Branş |
(yalnız Ad Soyad kritik; fuzzy başlık eşleme OYS kalıbıyla aynı).
"""

from __future__ import annotations

from io import BytesIO

import pytest
from openpyxl import Workbook

from apps.okul import excel_personel
from apps.okul.excel_ogrenci import ParserError

STANDARD_HEADER = ["Ad Soyad", "Unvan", "Branş"]


def make_xlsx(
    rows: list[list[object]],
    header: list[object] | None = None,
    preamble: list[list[object]] | None = None,
) -> bytes:
    """Bellekte bir .xlsx üretir (header + satırlar)."""
    wb = Workbook()
    ws = wb.active
    for pre in preamble or []:
        ws.append(pre)
    ws.append(header if header is not None else STANDARD_HEADER)
    for r in rows:
        ws.append(r)
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


def test_standart_basliklar_eslenir() -> None:
    grid = excel_personel.read_sheet(make_xlsx([]))
    mapping = excel_personel.detect_columns(grid)
    assert mapping.is_usable
    assert mapping.fields["full_name"] == 0
    assert mapping.fields["title"] == 1
    assert mapping.fields["branch"] == 2


def test_fuzzy_baslik_varyasyonlari() -> None:
    header: list[object] = ["Adı Soyadı", "Görevi", "Alan"]
    grid = excel_personel.read_sheet(make_xlsx([], header=header))
    mapping = excel_personel.detect_columns(grid)
    assert mapping.is_usable
    assert mapping.fields["title"] == 1
    assert mapping.fields["branch"] == 2


def test_yeni_sablon_ayri_ad_soyad_okunur() -> None:
    header: list[object] = ["Adı", "Soyadı", "Görevi", "Branşı"]
    data = make_xlsx([["ALİ", "ÖRNEK", "Müdür", "Coğrafya"]], header=header)
    mapping, parsed = excel_personel.parse_workbook(data)
    assert mapping.is_usable
    assert parsed[0].first_name == "ALİ"
    assert parsed[0].last_name == "ÖRNEK"
    assert parsed[0].title == "Müdür"
    assert parsed[0].branch == "Coğrafya"


def test_yalniz_ad_soyad_da_yeterli() -> None:
    """Unvan/branş sütunsuz düz isim listesi de kabul edilir (kritik alan tek)."""
    grid = excel_personel.read_sheet(make_xlsx([], header=["Ad Soyad"]))
    mapping = excel_personel.detect_columns(grid)
    assert mapping.is_usable


def test_ad_soyad_yoksa_parser_error() -> None:
    data = make_xlsx([["Müdür", "Matematik"]], header=["Unvan", "Branş"])
    with pytest.raises(ParserError, match="full_name"):
        excel_personel.parse_workbook(data)


def test_satir_ayristirma() -> None:
    rows: list[list[object]] = [
        ["ALİ ÖRNEK", "Müdür", "Coğrafya"],
        ["AYŞE ÖĞRETMEN", "", "Matematik"],
    ]
    _mapping, parsed = excel_personel.parse_workbook(make_xlsx(rows))
    assert len(parsed) == 2
    assert parsed[0].first_name == "ALİ"
    assert parsed[0].last_name == "ÖRNEK"
    assert parsed[0].title == "Müdür"
    assert parsed[0].branch == "Coğrafya"
    assert parsed[1].title == ""


def test_bos_satir_atlanir() -> None:
    rows: list[list[object]] = [
        ["ALİ ÖRNEK", "Müdür", "Coğrafya"],
        [None, None, None],
    ]
    _mapping, parsed = excel_personel.parse_workbook(make_xlsx(rows))
    assert len(parsed) == 1


def test_preamble_atlanir() -> None:
    preamble: list[list[object]] = [["PERSONEL LİSTESİ"], []]
    grid = excel_personel.read_sheet(make_xlsx([], preamble=preamble))
    mapping = excel_personel.detect_columns(grid)
    assert mapping.header_row == 2
    assert mapping.is_usable
