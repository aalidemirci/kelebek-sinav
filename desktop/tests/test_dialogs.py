"""Hata iletisi testleri — pencere açılamadığında kullanıcıya ulaşan tek yol."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from desktop.dialogs import show_error
from desktop.logging_setup import LOG_FILE_NAME, configure_logging


def test_hata_her_durumda_gunluge_yazilir(tmp_path: Path) -> None:
    configure_logging(tmp_path)

    show_error("Başlık", "Veri dosyası bozuk.", platform="linux", runner=lambda argv: False)
    logging.shutdown()

    assert "Veri dosyası bozuk." in (tmp_path / LOG_FILE_NAME).read_text(encoding="utf-8")


def test_linux_te_zenity_ile_gosterilir(tmp_path: Path) -> None:
    configure_logging(tmp_path)
    cagrilar: list[list[str]] = []

    def kaydet(argv: list[str]) -> bool:
        cagrilar.append(argv)
        return True

    show_error("Başlık", "Veri dosyası bozuk.", platform="linux", runner=kaydet)

    assert cagrilar
    assert any("Veri dosyası bozuk." in parca for parca in cagrilar[0])


def test_gorsel_ileti_basarisizsa_patlamaz(tmp_path: Path) -> None:
    configure_logging(tmp_path)

    def patla(argv: list[str]) -> bool:
        raise OSError("zenity yok")

    show_error("Başlık", "Mesaj", platform="linux", runner=patla)


def test_windows_ta_mesaj_kutusu_kullanilir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_logging(tmp_path)
    import desktop.dialogs as dialogs_mod

    cagrilar: list[tuple[str, str]] = []

    def kutu(title: str, message: str) -> bool:
        cagrilar.append((title, message))
        return True

    monkeypatch.setattr(dialogs_mod, "_show_windows_message_box", kutu)

    show_error("Başlık", "Mesaj", platform="win32", runner=lambda argv: False)

    assert cagrilar == [("Başlık", "Mesaj")]


def test_gorsel_ileti_denenmeden_once_gunluk_yazilir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Diyalog patlasa bile iz kalmalı → önce günlük, sonra ileti."""
    configure_logging(tmp_path)
    sira: list[str] = []
    import desktop.dialogs as dialogs_mod

    gercek_logger = dialogs_mod.logger

    class _Izleyici:
        def error(self, *args: Any, **kwargs: Any) -> None:
            sira.append("gunluk")
            gercek_logger.error(*args, **kwargs)

    monkeypatch.setattr(dialogs_mod, "logger", _Izleyici())

    def kaydet(argv: list[str]) -> bool:
        sira.append("ileti")
        return True

    show_error("Başlık", "Mesaj", platform="linux", runner=kaydet)

    assert sira == ["gunluk", "ileti"]
