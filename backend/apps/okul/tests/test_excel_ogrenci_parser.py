"""`apps.okul.excel_ogrenci` — başlık tespiti, fuzzy sütun eşleme, satır ayrıştırma.

Saf parser testleri (DB'siz). e-Okul ihracı ve uygulama şablonu aynı boru
hattından geçer; seviye kümesi parametriktir (U4 — okul türü + hazırlık).
"""

from __future__ import annotations

from typing import Any

from apps.okul import normalize
from apps.okul.excel_ogrenci import ColumnMapping, detect_columns, parse_rows


def _grid(*rows: list[Any]) -> list[list[Any]]:
    return [list(r) for r in rows]


class TestDetectColumns:
    def test_standart_sablon_basliklari_eslesir(self) -> None:
        grid = _grid(["Sınıf", "Okul Numarası", "Öğrenci Adı", "Öğrenci Soyadı"])
        mapping = detect_columns(grid)
        assert mapping.is_usable
        assert mapping.fields == {"class": 0, "number": 1, "student_first": 2, "student_last": 3}

    def test_eokul_bicimi_birlesik_ad_soyad(self) -> None:
        grid = _grid(["Sınıf", "Numa", "Adı Soyadı"])
        mapping = detect_columns(grid)
        assert mapping.is_usable
        assert mapping.fields == {"class": 0, "number": 1, "student_name": 2}

    def test_baslik_ilk_10_satirda_aranir(self) -> None:
        grid = _grid(
            ["", "", ""],
            ["OKUL LİSTESİ", "", ""],
            ["Sınıf", "Okul No", "Adı Soyadı"],
            ["9/A", "101", "ALİ VELİ"],
        )
        mapping = detect_columns(grid)
        assert mapping.header_row == 2

    def test_kritik_sutun_eksikse_kullanilamaz(self) -> None:
        mapping = detect_columns(_grid(["Sınıf", "Adı Soyadı"]))
        assert not mapping.is_usable
        assert "number" in mapping.missing_critical

    def test_ad_sutunu_tamamen_eksikse_kullanilamaz(self) -> None:
        mapping = detect_columns(_grid(["Sınıf", "Okul No"]))
        assert not mapping.is_usable
        assert any("student_name" in eksik for eksik in mapping.missing_critical)

    def test_yinelenen_baslik_uyari_dusurur(self) -> None:
        mapping = detect_columns(_grid(["Sınıf", "Şube", "Okul No", "Adı Soyadı"]))
        assert mapping.warnings  # 'Şube' → class için ikinci eşleşme


class TestParseRows:
    def _mapping(self) -> tuple[list[list[Any]], ColumnMapping]:
        grid = _grid(
            ["Sınıf", "Okul No", "Adı Soyadı"],
            ["10/A", "101", "EMRE CAN YILMAZ"],
            ["", "", ""],
            ["10-B", 2612.0, "ZEYNEP KAYA"],
        )
        return grid, detect_columns(grid)

    def test_satirlar_cozulur_bos_satir_atlanir(self) -> None:
        grid, mapping = self._mapping()
        rows = parse_rows(grid, mapping)
        assert len(rows) == 2
        assert rows[0].class_level == 10
        assert rows[0].class_section == "A"
        assert rows[0].student_first == "EMRE CAN"
        assert rows[0].student_last == "YILMAZ"
        assert rows[0].row_number == 2

    def test_excel_float_numarasi_temizlenir(self) -> None:
        grid, mapping = self._mapping()
        rows = parse_rows(grid, mapping)
        assert rows[1].student_number == "2612"

    def test_kume_disi_seviye_cozulmez(self) -> None:
        grid = _grid(["Sınıf", "Okul No", "Adı Soyadı"], ["8/A", "101", "ALİ VELİ"])
        rows = parse_rows(grid, detect_columns(grid), valid_levels=(9, 10, 11, 12))
        assert rows[0].class_level is None

    def test_hazirlik_sinifi_kumede_varsa_cozulur(self) -> None:
        grid = _grid(
            ["Sınıf", "Okul No", "Adı Soyadı"],
            ["HAZIRLIK/A", "101", "ALİ VELİ"],
            ["Hz-B", "102", "AYŞE FATMA ÖZ"],
        )
        rows = parse_rows(grid, detect_columns(grid), valid_levels=(0, 9, 10, 11, 12))
        assert (rows[0].class_level, rows[0].class_section) == (0, "A")
        assert (rows[1].class_level, rows[1].class_section) == (0, "B")

    def test_hazirlik_kumede_yoksa_cozulmez(self) -> None:
        grid = _grid(["Sınıf", "Okul No", "Adı Soyadı"], ["HAZIRLIK/A", "101", "ALİ VELİ"])
        rows = parse_rows(grid, detect_columns(grid), valid_levels=(9, 10, 11, 12))
        assert rows[0].class_level is None

    def test_turkce_sube_harfi_korunur(self) -> None:
        grid = _grid(["Sınıf", "Okul No", "Adı Soyadı"], ["9/Ş", "101", "ALİ VELİ"])
        rows = parse_rows(grid, detect_columns(grid))
        assert rows[0].class_section == "Ş"


class TestNormalizeHelpers:
    def test_class_section_bicimleri(self) -> None:
        for ham in ("10/A", "10-A", "10 A"):
            assert normalize.normalize_class_section(ham) == (10, "A")
        assert normalize.normalize_class_section("çözülemez") is None
        assert normalize.normalize_class_section(None) is None

    def test_split_full_name(self) -> None:
        assert normalize.split_full_name("EMRE CAN YILMAZ") == ("EMRE CAN", "YILMAZ")
        assert normalize.split_full_name("YILMAZ") == ("YILMAZ", "")
        assert normalize.split_full_name("") == ("", "")
