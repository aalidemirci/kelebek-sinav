"""Öğrenci içe aktarımı için saf (DB'siz) normalize ediciler.

DD `apps/okul/normalize.py` (OYS kökenli) dosyasından SADELEŞTİRİLEREK alındı:
TCKN/telefon/doğum tarihi/cinsiyet normalize edicileri KALDIRILDI — kelebek bu
verileri hiç toplamaz (tasarım §5). Sınıf/şube ayrıştırması okul türünden gelen
seviye kümesiyle PARAMETRİKTİR (U4 — sabit 9-12 yok; DD/OYS'den bilinçli sapma).

Saf fonksiyonlardır — kolay test edilir (tests/test_normalize). DB eşleştirme
ve yazma `services/imports.py`'dadır.
"""

from __future__ import annotations

import re
from collections.abc import Collection

# Türkçe karakter → ASCII büyük (şube harfi katlaması ve eşleme karşılaştırmaları).
_TR_UPPER_MAP = str.maketrans(
    {
        "ş": "S",
        "Ş": "S",
        "ı": "I",
        "İ": "I",
        "ğ": "G",
        "Ğ": "G",
        "ü": "U",
        "Ü": "U",
        "ö": "O",
        "Ö": "O",
        "ç": "C",
        "Ç": "C",
    }
)

#: Hazırlık sınıfını metinden tanıma deseni ('HAZIRLIK/A', 'HAZ A', 'HZ-B'…).
_PREP_RE = re.compile(r"\bHA?Z(IRLIK)?\b")


def _ascii_upper(value: str) -> str:
    """Türkçe karakterleri ASCII'ye indirip büyük harfe çevirir (eşleme için)."""
    return value.translate(_TR_UPPER_MAP).upper()


def normalize_class_section(
    value: object, *, valid_levels: Collection[int] = (9, 10, 11, 12)
) -> tuple[int, str] | None:
    """'10/A', '10-A', '10 A' → (10, 'A'); küme dışı seviye veya çözümsüz → None.

    `valid_levels` okul türünden türetilir (`SchoolConfig.grade_levels`).
    0 (Hazırlık) kümede ise 'HAZIRLIK/A', 'HZ A' gibi metinler (0, 'A') çözülür.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    levels = frozenset(int(v) for v in valid_levels)
    folded = _ascii_upper(s)
    if 0 in levels and _PREP_RE.search(folded):
        section_m = re.search(r"[A-Z]+$", re.sub(r"[^A-Z]", " ", _PREP_RE.sub(" ", folded)).strip())
        if section_m is None:
            return None
        return 0, section_m.group()
    level_m = re.search(r"\d{1,2}", s)
    section_m2 = re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", s)
    if level_m is None or section_m2 is None:
        return None
    level = int(level_m.group())
    if level not in levels:
        return None
    section = _ascii_upper(section_m2.group())
    return level, section


def split_full_name(value: object) -> tuple[str, str]:
    """'EMRE CAN YILMAZ' → ('EMRE CAN', 'YILMAZ'); tek kelime → (kelime, '').

    Son kelime soyad kabul edilir. Title Case uygulanmaz — ham bırakılır
    (görüntü biçimi sistemin başka katmanında uygulanır; TR büyük harf tuzağı).
    """
    if value is None:
        return "", ""
    parts = str(value).split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]
