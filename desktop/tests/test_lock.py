"""Tek-instance kilidi testleri (tasarım §5.3 — ikinci kopya pencere AÇMAZ)."""

from __future__ import annotations

from pathlib import Path

import pytest

from desktop.errors import AlreadyRunningError
from desktop.lock import SingleInstanceLock


def test_kilit_alinir_ve_dosya_olusur(tmp_path: Path) -> None:
    lock = SingleInstanceLock(tmp_path / "alt" / "instance.lock")

    lock.acquire()
    try:
        assert (tmp_path / "alt" / "instance.lock").is_file()
    finally:
        lock.release()


def test_ikinci_kopya_reddedilir_turkce_mesajla(tmp_path: Path) -> None:
    ilk = SingleInstanceLock(tmp_path / "instance.lock")
    ikinci = SingleInstanceLock(tmp_path / "instance.lock")

    ilk.acquire()
    try:
        with pytest.raises(AlreadyRunningError) as hata:
            ikinci.acquire()
    finally:
        ilk.release()

    assert "zaten çalışıyor" in str(hata.value)


def test_birakildiktan_sonra_yeniden_alinabilir(tmp_path: Path) -> None:
    ilk = SingleInstanceLock(tmp_path / "instance.lock")
    ilk.acquire()
    ilk.release()

    ikinci = SingleInstanceLock(tmp_path / "instance.lock")
    ikinci.acquire()
    ikinci.release()


def test_context_manager_cikista_birakir(tmp_path: Path) -> None:
    yol = tmp_path / "instance.lock"

    with SingleInstanceLock(yol):
        with pytest.raises(AlreadyRunningError):
            SingleInstanceLock(yol).acquire()

    # `with` bloğu bitti → kilit serbest
    SingleInstanceLock(yol).acquire()


def test_release_kilit_alinmadan_cagrilabilir(tmp_path: Path) -> None:
    SingleInstanceLock(tmp_path / "instance.lock").release()


def test_ikinci_acquire_dosya_tanitici_sizdirmaz(tmp_path: Path) -> None:
    """Reddedilen kilit denemesi açık dosyayı kapatmalı (Windows'ta dosya kilidi kalır)."""
    ilk = SingleInstanceLock(tmp_path / "instance.lock")
    ilk.acquire()
    ikinci = SingleInstanceLock(tmp_path / "instance.lock")
    try:
        for _ in range(50):
            with pytest.raises(AlreadyRunningError):
                ikinci.acquire()
            assert ikinci.handle is None
    finally:
        ilk.release()
