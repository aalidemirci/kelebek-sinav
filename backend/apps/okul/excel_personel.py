"""Personel Excel'ini okuma: başlık tespiti, esnek sütun eşleme, satır ayrıştırma.

OYS `apps/core/excel_personel.py` dosyasından SADELEŞTİRİLEREK alındı (tasarım
§3.5): e-posta ve Rol/Kapsam çiftleri KALDIRILDI — standalone'da personel login
olmaz; roller (Müdür, kurul üyelikleri) personel yüklendikten sonra ayrıca
tanımlanır. Fuzzy başlık eşleme kalıbı (excel_ogrenci deseni) aynen korunur.

Yeni şablon: | Adı | Soyadı | Görevi | Branşı |. Eski birleşik ``Ad Soyad``
biçimi de geriye uyum için kabul edilir.
DB yazımı `services/imports.py`'dadır (saf modül — DB'siz, test edilebilir).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.okul import normalize
from apps.okul.excel_ogrenci import ParserError, normalize_header, read_sheet

# Mantıksal alan → normalize edilmiş başlık anahtar kelimeleri (ilk eşleşen kazanır).
COLUMN_SYNONYMS: dict[str, list[str]] = {
    "full_name": ["ad soyad", "adi soyadi", "ad ve soyad", "adsoyad", "ad soyadi", "isim"],
    "last_name": ["personel soyadi", "soyadi"],
    "first_name": ["personel adi", "adi"],
    "title": ["unvan", "gorev", "gorevi"],
    "branch": ["brans", "bransi", "alan"],
}


@dataclass
class PersonnelColumnMapping:
    """Tespit edilen başlık satırı ve alan → kolon indeksi eşlemesi."""

    header_row: int
    fields: dict[str, int] = field(default_factory=dict)
    matched_headers: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def missing_critical(self) -> list[str]:
        has_combined_name = "full_name" in self.fields
        has_split_name = "first_name" in self.fields and "last_name" in self.fields
        return (
            [] if has_combined_name or has_split_name else ["full_name veya first_name+last_name"]
        )

    @property
    def is_usable(self) -> bool:
        return not self.missing_critical


@dataclass
class ParsedPersonnelRow:
    """Bir personel satırının çözümlenmiş hâli."""

    row_number: int  # 1-tabanlı Excel satır no
    raw_full_name: str = ""
    first_name: str = ""
    last_name: str = ""
    title: str = ""
    branch: str = ""


def _str(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def _match_field_for_header(norm: str) -> str | None:
    for fieldname, keywords in COLUMN_SYNONYMS.items():
        for kw in keywords:
            if kw == norm or kw in norm:
                return fieldname
    return None


def _map_header_row(cells: list[Any]) -> tuple[dict[str, int], dict[str, str], list[str]]:
    fields: dict[str, int] = {}
    matched: dict[str, str] = {}
    warnings: list[str] = []
    for idx, cell in enumerate(cells):
        norm = normalize_header(cell)
        if not norm:
            continue
        fieldname = _match_field_for_header(norm)
        if fieldname is None:
            continue
        if fieldname in fields:
            warnings.append(
                f"'{cell}' sütunu '{fieldname}' için yinelenen eşleşme; ilki kullanıldı."
            )
            continue
        fields[fieldname] = idx
        matched[fieldname] = str(cell).strip()
    return fields, matched, warnings


def detect_columns(rows: list[list[Any]], scan_limit: int = 10) -> PersonnelColumnMapping:
    """İlk satırlar içinde en iyi başlık satırını bulur ve sütunları eşler."""
    best: PersonnelColumnMapping | None = None
    for r in range(min(scan_limit, len(rows))):
        cells = rows[r]
        if all(c is None or str(c).strip() == "" for c in cells):
            continue
        fields, matched, warnings = _map_header_row(cells)
        if not fields:
            continue
        candidate = PersonnelColumnMapping(
            header_row=r, fields=fields, matched_headers=matched, warnings=warnings
        )
        if best is None or (candidate.is_usable, len(candidate.fields)) > (
            best.is_usable,
            len(best.fields),
        ):
            best = candidate
        if best.is_usable and best.header_row == r:
            break
    return best or PersonnelColumnMapping(header_row=0)


def _cell(cells: list[Any], idx: int | None) -> Any:
    if idx is None or idx >= len(cells):
        return None
    return cells[idx]


def parse_rows(rows: list[list[Any]], mapping: PersonnelColumnMapping) -> list[ParsedPersonnelRow]:
    """Başlık satırından sonraki veri satırlarını çözümler (boş satırlar atlanır)."""
    f = mapping.fields
    parsed: list[ParsedPersonnelRow] = []
    for r in range(mapping.header_row + 1, len(rows)):
        cells = rows[r]
        if all(c is None or str(c).strip() == "" for c in cells):
            continue

        raw_name = _str(_cell(cells, f.get("full_name")))
        if raw_name:
            first, last = normalize.split_full_name(raw_name)
        else:
            first = _str(_cell(cells, f.get("first_name")))
            last = _str(_cell(cells, f.get("last_name")))
            raw_name = f"{first} {last}".strip()
        parsed.append(
            ParsedPersonnelRow(
                row_number=r + 1,
                raw_full_name=raw_name,
                first_name=first,
                last_name=last,
                title=_str(_cell(cells, f.get("title"))),
                branch=_str(_cell(cells, f.get("branch"))),
            )
        )
    return parsed


def parse_workbook(file_bytes: bytes) -> tuple[PersonnelColumnMapping, list[ParsedPersonnelRow]]:
    """Baytlardan (mapping, satırlar) üretir; kritik sütun yoksa ParserError."""
    grid = read_sheet(file_bytes)
    mapping = detect_columns(grid)
    if not mapping.is_usable:
        eksik = ", ".join(mapping.missing_critical)
        raise ParserError(f"Zorunlu sütun(lar) bulunamadı: {eksik}.")
    return mapping, parse_rows(grid, mapping)


# read_sheet excel_ogrenci'den yeniden kullanılır (etkin sayfa, salt-okunur).
__all__ = [
    "ParsedPersonnelRow",
    "PersonnelColumnMapping",
    "detect_columns",
    "parse_rows",
    "parse_workbook",
    "read_sheet",
]
