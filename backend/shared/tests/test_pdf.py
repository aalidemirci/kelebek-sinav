"""`shared.pdf` — WeasyPrint'in tek kapısı (19.09.2026 çöküş tanısı).

Sabitlenen üç şey: (1) basımlar süreç genelinde SIRAYLA koşar — eşzamanlı basım
Pango/fontconfig katmanında yerel belleği bozuyordu; (2) yazı tipi yapılandırması
belgeler arasında PAYLAŞILIR; (3) uygulama kodunda WeasyPrint'e bu kapı dışından
gidilmez — yeni bir PDF yolu kilidi sessizce atlayamasın.
"""

from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from shared import pdf

BACKEND = Path(__file__).resolve().parents[2]


def test_gercek_pdf_uretir_ve_yazi_tipi_yapilandirmasini_paylasir() -> None:
    ilk = pdf.html_to_pdf("<p>Türkçe metin: ĞÜŞİÖÇ ığüşiöç</p>")
    yapilandirma = pdf._font_config
    ikinci = pdf.html_to_pdf("<p>İkinci belge</p>")

    assert ilk.startswith(b"%PDF-") and ikinci.startswith(b"%PDF-")
    assert yapilandirma is not None
    assert pdf._font_config is yapilandirma, "her belgede yeni FontConfiguration kuruldu"


def test_ayni_anda_en_fazla_bir_basim(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dört iş parçacığı aynı anda basar; WeasyPrint'e aynı anda tek çağrı düşer."""
    import weasyprint

    kilit = threading.Lock()
    durum = {"etkin": 0, "en_cok": 0, "cagri": 0}

    class SahteHTML:
        def __init__(self, string: str) -> None:
            self.string = string

        def write_pdf(self, **_kwargs: Any) -> bytes:
            with kilit:
                durum["etkin"] += 1
                durum["cagri"] += 1
                durum["en_cok"] = max(durum["en_cok"], durum["etkin"])
            time.sleep(0.02)  # çakışma penceresi: kilitsiz kodda mutlaka örtüşür
            with kilit:
                durum["etkin"] -= 1
            return b"%PDF-sahte"

    monkeypatch.setattr(weasyprint, "HTML", SahteHTML)
    monkeypatch.setattr(pdf, "_font_config", object())  # gerçek fontconfig kurulmasın

    def isci() -> None:
        for _ in range(3):
            assert pdf.html_to_pdf("<p>x</p>") == b"%PDF-sahte"

    ipler = [threading.Thread(target=isci) for _ in range(4)]
    for ip in ipler:
        ip.start()
    for ip in ipler:
        ip.join()

    assert durum["cagri"] == 12
    assert durum["en_cok"] == 1, "iki PDF aynı anda basıldı — kilit atlanmış"


# WeasyPrint'e doğrudan giden kod kalıpları (yorum/belge dizesi değil, çağrı).
_YASAK = (
    re.compile(r"\bwrite_pdf\s*\("),
    re.compile(r"^\s*(from\s+weasyprint\b|import\s+weasyprint\b)", re.MULTILINE),
)


def test_weasyprint_yalniz_shared_pdf_kapisindan() -> None:
    """Uygulama kodunda WeasyPrint çağrısı yalnız `shared/pdf.py`de olabilir.

    Testler kapsam dışıdır (tek iş parçacığında koşar, sahte PDF üretir).
    """
    ihlaller: list[str] = []
    for kok in ("apps", "shared", "config"):
        for yol in sorted((BACKEND / kok).rglob("*.py")):
            goreli = yol.relative_to(BACKEND).as_posix()
            if "/tests/" in f"/{goreli}" or goreli == "shared/pdf.py":
                continue
            metin = yol.read_text(encoding="utf-8")
            for desen in _YASAK:
                for eslesme in desen.finditer(metin):
                    satir = metin.count("\n", 0, eslesme.start()) + 1
                    ihlaller.append(f"{goreli}:{satir}")
    assert ihlaller == [], (
        "WeasyPrint'e shared.pdf.html_to_pdf dışından gidiliyor (eşzamanlı basım "
        f"kilidini atlar — 19.09.2026 çöküşü): {ihlaller}"
    )
