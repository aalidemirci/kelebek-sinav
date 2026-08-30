"""K7 borcunun otomatik kapısı: spec hiddenimports ↔ backend/requirements.txt.

Backend pakete KAYNAK olarak kopyalanır; PyInstaller statik çözümleyicisi orayı
taramaz (spec docstring'i). Yeni bir üçüncü taraf bağımlılık spec'e elle
eklenmek ZORUNDADIR — unutulursa paket geliştirmede çalışır, sahada çöker
(CLAUDE.md §2 hiddenimports tuzağı). Bu test unutmayı kapıya bağlar: DD'de de
emsali yoktu, F9 denetim bulgusuyla eklendi.

Ayrıca `giris.py` teşhis kipinin sözleşmesi sabitlenir: bayrak adı, çıkış kodu
(desktop/errors.py ile ikiz) ve hedef dosya ayrıştırması — üç paket betiği
(build.ps1, build.sh, kap-ici-test.sh) bu sözleşmeye dışarıdan bağlıdır.
"""

from __future__ import annotations

import re
import runpy
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "packaging" / "pyinstaller" / "kelebek_sinav.spec"
REQUIREMENTS = REPO / "backend" / "requirements.txt"

#: PyPI dağıtım adı → import (modül) adı. Yeni bağımlılıkta buraya satır eklenir;
#: eşleme yoksa test bilinçli KIRILIR (sessiz kapsam kaybındansa gürültü iyidir).
DAGITIM_IMPORT_ESLEME = {
    "django": "django",
    "djangorestframework": "rest_framework",
    "argon2-cffi": "argon2",
    "cryptography": "cryptography",
    "openpyxl": "openpyxl",
    "pillow": "PIL",
    "weasyprint": "weasyprint",
    "pypdf": "pypdf",
    "whitenoise": "whitenoise",
    "waitress": "waitress",
}

_PIN = re.compile(r"^([A-Za-z0-9_.\-]+)==", re.MULTILINE)


def _gereksinimler() -> list[str]:
    return [ad.casefold() for ad in _PIN.findall(REQUIREMENTS.read_text(encoding="utf-8"))]


def test_her_backend_bagimliligi_spec_kapsaminda() -> None:
    spec_metni = SPEC.read_text(encoding="utf-8")
    eksik: list[str] = []
    for dagitim in _gereksinimler():
        modul = DAGITIM_IMPORT_ESLEME.get(dagitim)
        assert modul is not None, (
            f"requirements.txt'e yeni bağımlılık girmiş: {dagitim!r}. "
            "Önce DAGITIM_IMPORT_ESLEME'ye eşlemesini, sonra spec hiddenimports'a "
            "modülünü ekleyin (K7 — CLAUDE.md §2)."
        )
        kapsandi = f'collect_submodules("{modul}")' in spec_metni or f'"{modul}"' in spec_metni
        if not kapsandi:
            eksik.append(f"{dagitim} → {modul}")
    assert eksik == [], f"spec hiddenimports şu bağımlılıkları kapsamıyor: {eksik}"


# ---------------------------------------------------------------------------
# giris.py teşhis kipi sözleşmesi
# ---------------------------------------------------------------------------
_GIRIS = runpy.run_path(str(REPO / "packaging" / "pyinstaller" / "giris.py"))
_ERRORS = runpy.run_path(str(REPO / "desktop" / "errors.py"))


def test_pdf_duman_bayragi_ve_cikis_kodu_sozlesmesi() -> None:
    assert _GIRIS["PDF_SMOKE_FLAG"] == "--pdf-duman"  # build.ps1 / build.sh / kap-ici-test
    assert _GIRIS["EXIT_PDF_SMOKE_FAILED"] == _ERRORS["EXIT_PDF_SMOKE_FAILED"] == 8


def test_pdf_duman_hedef_dosya_ayristirmasi() -> None:
    smoke_target = _GIRIS["_smoke_target"]
    assert smoke_target(["--pdf-duman", "cikti.pdf"]) == Path("cikti.pdf")
    # Dosya verilmezse (veya sonraki öğe başka bayraksa) geçici dizine düşer.
    varsayilan = smoke_target(["--pdf-duman"])
    assert varsayilan == Path(tempfile.gettempdir()) / "kelebek-sinav-pdf-duman.pdf"
    assert smoke_target(["--pdf-duman", "--autotest"]) == varsayilan
