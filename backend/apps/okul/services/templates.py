"""İndirilebilir içe aktarma şablonları (tasarım §4.7/2).

Başlıklar parser sinonimleriyle bire bir tanınır — ayrı bir "şablon kod yolu"
YOKTUR; kullanıcı şablonu doldurup aynı import ucuna yükler.
"""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

STUDENT_TEMPLATE_HEADERS: tuple[str, ...] = (
    "Sınıf",
    "Okul Numarası",
    "Öğrenci Adı",
    "Öğrenci Soyadı",
)

PERSONNEL_TEMPLATE_HEADERS: tuple[str, ...] = ("Adı", "Soyadı", "Görevi", "Branşı")


def _workbook_bytes(headers: tuple[str, ...], example: tuple[str, ...]) -> bytes:
    wb = Workbook()
    ws: Worksheet = wb.active
    ws.append(list(headers))
    ws.append(list(example))
    for column_cells in ws.columns:
        letter = column_cells[0].column_letter
        ws.column_dimensions[letter].width = 18
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


def student_template_xlsx() -> bytes:
    """Örnek satırlı öğrenci şablonu (örnek veriler sahtedir, silinip doldurulur)."""
    return _workbook_bytes(
        STUDENT_TEMPLATE_HEADERS,
        (
            "9/A",
            "1001",
            "ÖRNEK",
            "ÖĞRENCİ",
        ),
    )


def personnel_template_xlsx() -> bytes:
    """Örnek satırlı personel şablonu."""
    return _workbook_bytes(
        PERSONNEL_TEMPLATE_HEADERS,
        ("ÖRNEK", "ÖĞRETMEN", "Öğretmen", "Matematik"),
    )
