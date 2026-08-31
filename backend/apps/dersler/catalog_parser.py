"""MEB ders çizelgesi dosyası ayrıştırıcısı (K6, ADR-0016).

V1 desteklenen format: **markdown tablo** (`data/ders-cizelgeleri/README.md`).
Beklenen sütunlar: `| Ders | Seviyeler | Tür | Sınav |`
- Seviyeler: virgüllü liste ve/veya aralık — `9, 10` / `9-12` / `9, 11-12`
- Tür: `ORTAK` veya `SECMELI` (Türkçe; dosya insan elinden çıkar)
- Sınav: `YAZILI` / `UYGULAMA` / `YOK` — **isteğe bağlı 4. sütun**; yoksa ya da
  boşsa `YAZILI` varsayılır. Üç sütunlu dosyalar (`cerceveler/*.md`) böylece
  bozulmadan okunur.

PDF/XLSX çizelgeler gerçek dosyalar temin edildiğinde eklenir (ADR-0016
riskler). Hatalı satırlar sonucu durdurmaz; satır numarasıyla raporlanır.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from apps.dersler.models import CourseExamMode, CourseType
from apps.dersler.services import CourseRow

# Dosyadaki Türkçe tür etiketi (normalize edilmiş: büyük harf, Ç→C, İ→I) → enum.
_TYPE_MAP: dict[str, str] = {
    "ORTAK": CourseType.COMMON,
    "SECMELI": CourseType.ELECTIVE,
}

# Sınav biçimi etiketi — AYNI normalize kalıbıyla ('Yazılı'.upper() → 'YAZILI',
# ı→I zaten doğru; kalıp `_TYPE_MAP` ile birebir tutuluyor ki sonraki okuyucu
# iki sütunu farklı sansın diye durup düşünmesin).
_EXAM_MODE_MAP: dict[str, str] = {
    "YAZILI": CourseExamMode.WRITTEN,
    "UYGULAMA": CourseExamMode.PRACTICE,
    "YOK": CourseExamMode.NONE,
}


@dataclass
class ParsedCatalog:
    """Tek dosyanın ayrıştırma sonucu."""

    rows: list[CourseRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _parse_levels(raw: str) -> tuple[int, ...]:
    """'9, 10' / '9-12' / '9, 11-12' → (9, 10) / (9, 10, 11, 12) / (9, 11, 12).

    Sayısal olmayan parça ``ValueError`` fırlatır (çağıran satır no ile raporlar).
    Değer aralığı doğrulaması services.normalize_levels'a bırakılır.
    """
    levels: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, _, end_s = part.partition("-")
            start, end = int(start_s.strip()), int(end_s.strip())
            if end < start:
                raise ValueError(f"aralık ters: {part!r}")
            levels.extend(range(start, end + 1))
        else:
            levels.append(int(part))
    if not levels:
        raise ValueError("seviye bulunamadı")
    return tuple(sorted(set(levels)))


def _is_separator_row(cells: list[str]) -> bool:
    """Markdown tablo ayraç satırı mı (`|---|---|---|`)?"""
    return all(set(cell) <= {"-", ":", " "} and cell.strip() for cell in cells)


def parse_markdown_catalog(text: str, *, source_name: str = "") -> ParsedCatalog:
    """Markdown metnindeki tablo satırlarını ``CourseRow`` listesine çevir.

    Tablo dışı satırlar (başlık, açıklama) sessizce atlanır. Başlık satırı,
    ilk hücresi 'Ders' olan satırdır ve veri sayılmaz.
    """
    result = ParsedCatalog()
    prefix = f"{source_name}: " if source_name else ""
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if _is_separator_row(cells):
            continue
        if cells and cells[0].casefold() == "ders":  # başlık satırı
            continue
        if len(cells) < 3:
            result.errors.append(
                f"{prefix}satır {line_no}: en az 3 sütun bekleniyor (Ders | Seviyeler | Tür)."
            )
            continue
        name, levels_raw, type_raw = cells[0], cells[1], cells[2]
        # 4. sütun isteğe bağlı — üç sütunlu eski çizelgeler aynen çalışır.
        exam_raw = cells[3] if len(cells) > 3 else ""
        if not name:
            result.errors.append(f"{prefix}satır {line_no}: ders adı boş.")
            continue
        try:
            levels = _parse_levels(levels_raw)
        except ValueError as exc:
            result.errors.append(f"{prefix}satır {line_no}: seviyeler okunamadı ({exc}).")
            continue
        course_type = _TYPE_MAP.get(type_raw.upper().replace("İ", "I").replace("Ç", "C"))
        if course_type is None:
            result.errors.append(
                f"{prefix}satır {line_no}: bilinmeyen tür {type_raw!r} (ORTAK veya SECMELI bekleniyor)."
            )
            continue
        # Boş hücre = "belirtilmemiş" → YAZILI. Dolu ama tanınmayan etiket
        # sessizce YAZILI'ya düşmez: yazım hatası havuzu sessizce şişirirdi.
        exam_mode: str = CourseExamMode.WRITTEN
        if exam_raw:
            eslesen = _EXAM_MODE_MAP.get(exam_raw.upper().replace("İ", "I").replace("Ç", "C"))
            if eslesen is None:
                result.errors.append(
                    f"{prefix}satır {line_no}: bilinmeyen sınav biçimi {exam_raw!r} "
                    "(YAZILI, UYGULAMA veya YOK bekleniyor)."
                )
                continue
            exam_mode = eslesen
        result.rows.append(
            CourseRow(
                name=name,
                levels=levels,
                course_type=course_type,
                exam_mode=exam_mode,
            )
        )
    return result


@dataclass
class ParsedAliasTable:
    """Takma ad tablosu ayrıştırma sonucu (Tur 565)."""

    rows: list[tuple[str, str]] = field(default_factory=list)  # (takma ad, kanonik ad)
    errors: list[str] = field(default_factory=list)


def parse_alias_table(text: str, *, source_name: str = "") -> ParsedAliasTable:
    """`| Takma ad | Kanonik ad |` markdown tablosunu ayrıştır (Tur 565).

    `data/ders-cizelgeleri/ders-adi-takma-adlari.md` bu formattadır. Katalog
    ayrıştırıcısıyla aynı toleranslar: tablo dışı satırlar atlanır, hatalı
    satır sonucu durdurmaz (satır numarasıyla raporlanır).
    """
    result = ParsedAliasTable()
    prefix = f"{source_name}: " if source_name else ""
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if _is_separator_row(cells):
            continue
        if cells and cells[0].casefold() in ("takma ad", "takma adı"):  # başlık
            continue
        if len(cells) < 2 or not cells[0] or not cells[1]:
            result.errors.append(
                f"{prefix}satır {line_no}: 'Takma ad | Kanonik ad' biçiminde 2 sütun bekleniyor."
            )
            continue
        result.rows.append((cells[0], cells[1]))
    return result
