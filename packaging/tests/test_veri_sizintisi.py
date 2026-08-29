from __future__ import annotations

import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

BETIK = Path(__file__).parents[1] / "veri_sizintisi.py"
MODUL = runpy.run_path(str(BETIK))
YASAK_DOSYALARI_BUL = cast(
    Callable[[Path], list[Path]],
    MODUL["yasak_dosyalari_bul"],
)
GUVENLI_METIN = cast(Callable[[str, str | None], str], MODUL["guvenli_metin"])


def test_temiz_paket_kabul_edilir(tmp_path: Path) -> None:
    dosya = tmp_path / "_internal" / "templates" / "bos-form.pdf"
    dosya.parent.mkdir(parents=True)
    dosya.touch()

    assert YASAK_DOSYALARI_BUL(tmp_path) == []


def test_backend_veritabani_reddedilir(tmp_path: Path) -> None:
    dosya = tmp_path / "_internal" / "backend" / "data" / "db.sqlite3"
    dosya.parent.mkdir(parents=True)
    dosya.touch()

    assert YASAK_DOSYALARI_BUL(tmp_path) == [Path("_internal/backend/data/db.sqlite3")]


def test_excel_dosyasi_reddedilir(tmp_path: Path) -> None:
    dosya = tmp_path / "yanlislikla-eklenen-liste.xlsx"
    dosya.touch()

    assert YASAK_DOSYALARI_BUL(tmp_path) == [Path("yanlislikla-eklenen-liste.xlsx")]


def test_medya_klasoru_reddedilir(tmp_path: Path) -> None:
    dosya = tmp_path / "_internal" / "backend" / "media" / "ifade.pdf"
    dosya.parent.mkdir(parents=True)
    dosya.touch()

    assert YASAK_DOSYALARI_BUL(tmp_path) == [Path("_internal/backend/media/ifade.pdf")]


def test_windows_cp1252_konsolunda_turkce_mesaj_derlemeyi_kirmaz() -> None:
    sonuc = GUVENLI_METIN("Denetim başarılı.", "cp1252")

    assert sonuc == r"Denetim ba\u015far\u0131l\u0131."
