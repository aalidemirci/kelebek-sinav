"""Gömülü sunucu testleri (tasarım §5.3 — 127.0.0.1 + boş port, erişim logu YOK)."""

from __future__ import annotations

import socket
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from typing import Any

import pytest

from desktop.errors import ServerStartError
from desktop.server import BackgroundServer, check_health, find_free_port


class _SahteSunucu:
    """waitress sunucusu yerine geçen kayıt tutucu (gerçek soket açmaz)."""

    def __init__(self, effective_port: int | str = 54321) -> None:
        self.effective_port = effective_port
        self.effective_host = "127.0.0.1"
        self.calisti = False
        self.kapandi = False

    def run(self) -> None:
        self.calisti = True

    def close(self) -> None:
        self.kapandi = True


def test_bos_port_bulunur_ve_baglanabilir() -> None:
    port = find_free_port()

    assert 1024 < port < 65536
    with socket.socket() as s:  # port gerçekten serbest olmalı
        s.bind(("127.0.0.1", port))


def test_sunucu_sabit_port_kullanmaz() -> None:
    """Sabit port YOK: başka bir program 8000'i tutuyorsa açılış patlamamalı."""
    cagri: dict[str, Any] = {}

    def fabrika(app: object, **kwargs: Any) -> _SahteSunucu:
        cagri.update(kwargs)
        return _SahteSunucu(effective_port=54321)

    sunucu = BackgroundServer(lambda environ, start_response: [], server_factory=fabrika)
    sunucu.start()
    try:
        assert cagri["port"] == 0  # işletim sistemi boş port seçsin
        assert cagri["host"] == "127.0.0.1"
        assert sunucu.port == 54321
        assert sunucu.base_url == "http://127.0.0.1:54321"
    finally:
        sunucu.stop()


def test_port_tam_sayiya_cevrilir() -> None:
    """waitress `effective_port`'u METİN döndürür; `%d` biçimlemesi patlamasın."""
    sunucu = BackgroundServer(
        lambda environ, start_response: [],
        server_factory=lambda app, **kwargs: _SahteSunucu(effective_port="54321"),
    )
    sunucu.start()
    try:
        assert sunucu.port == 54321
        assert isinstance(sunucu.port, int)
        assert sunucu.base_url == "http://127.0.0.1:54321"
    finally:
        sunucu.stop()


def test_sunucu_arka_plan_thread_inde_kosar_ve_durdurulur() -> None:
    sahte = _SahteSunucu()

    sunucu = BackgroundServer(
        lambda environ, start_response: [],
        server_factory=lambda app, **kwargs: sahte,
    )
    sunucu.start()
    sunucu.wait_until_started(timeout=2.0)

    assert sahte.calisti
    assert sunucu.thread is not None and sunucu.thread.daemon

    sunucu.stop()
    assert sahte.kapandi
    assert sunucu.thread is None


def test_sunucu_ayaga_kalkmazsa_turkce_hata(monkeypatch: pytest.MonkeyPatch) -> None:
    def patla(app: object, **kwargs: Any) -> _SahteSunucu:
        raise OSError("adres kullanımda")

    sunucu = BackgroundServer(lambda environ, start_response: [], server_factory=patla)

    with pytest.raises(ServerStartError) as hata:
        sunucu.start()

    assert "başlat" in str(hata.value).lower()


def test_gercek_waitress_yalniz_yerel_arayuzde_dinler() -> None:
    """Bütünleşik denetim: gerçek waitress + boş port + 127.0.0.1 bağlanması."""
    waitress = pytest.importorskip("waitress")
    assert waitress

    def uygulama(environ: dict[str, Any], start_response: Callable[..., Any]) -> Iterable[bytes]:
        start_response("200 OK", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"tamam"]

    sunucu = BackgroundServer(uygulama)
    sunucu.start()
    try:
        sunucu.wait_until_ready(timeout=10.0)
        assert sunucu.port != 0
        assert isinstance(sunucu.port, int)
        with urllib.request.urlopen(sunucu.base_url + "/", timeout=5) as yanit:  # noqa: S310
            assert yanit.status == 200
            assert yanit.read() == b"tamam"
    finally:
        sunucu.stop()


def test_saglik_denetimi_belirtecsiz_istegin_reddini_dogrular() -> None:
    """`--autotest`: belirteçsiz istek 403 DÖNMELİ, belirteçli istek 200."""
    pytest.importorskip("waitress")
    gorulen: list[str] = []

    def uygulama(environ: dict[str, Any], start_response: Callable[..., Any]) -> Iterable[bytes]:
        gorulen.append(environ.get("QUERY_STRING", ""))
        if "gizli" in environ.get("QUERY_STRING", ""):
            start_response("200 OK", [("Content-Type", "application/json")])
            return [b'{"setup_completed": false}']
        start_response("403 Forbidden", [("Content-Type", "application/json")])
        return [b'{"code": "forbidden"}']

    sunucu = BackgroundServer(uygulama)
    sunucu.start()
    try:
        sunucu.wait_until_ready(timeout=10.0)
        check_health(sunucu.base_url, "gizli", path="/api/v1/setup/status/", timeout=5.0)
    finally:
        sunucu.stop()

    assert len(gorulen) == 2  # biri belirteçsiz (403 beklenir), biri belirteçli


def test_saglik_denetimi_korumasiz_sunucuyu_reddeder() -> None:
    """Belirteçsiz istek 200 dönüyorsa koruma çalışmıyordur → açılış durur."""
    pytest.importorskip("waitress")

    def uygulama(environ: dict[str, Any], start_response: Callable[..., Any]) -> Iterable[bytes]:
        start_response("200 OK", [("Content-Type", "application/json")])
        return [b"{}"]

    sunucu = BackgroundServer(uygulama)
    sunucu.start()
    try:
        sunucu.wait_until_ready(timeout=10.0)
        with pytest.raises(ServerStartError) as hata:
            check_health(sunucu.base_url, "gizli", path="/api/v1/setup/status/", timeout=5.0)
    finally:
        sunucu.stop()

    assert "koruma" in str(hata.value).lower()


def test_saglik_denetimi_sunucu_hatasini_yakalar() -> None:
    pytest.importorskip("waitress")

    def uygulama(environ: dict[str, Any], start_response: Callable[..., Any]) -> Iterable[bytes]:
        if "gizli" in environ.get("QUERY_STRING", ""):
            start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
            return [b"patladi"]
        start_response("403 Forbidden", [("Content-Type", "application/json")])
        return [b"{}"]

    sunucu = BackgroundServer(uygulama)
    sunucu.start()
    try:
        sunucu.wait_until_ready(timeout=10.0)
        with pytest.raises(ServerStartError):
            check_health(sunucu.base_url, "gizli", path="/api/v1/setup/status/", timeout=5.0)
    finally:
        sunucu.stop()


def test_ulasilamayan_sunucu_turkce_hata_verir() -> None:
    kapali_port = find_free_port()

    with pytest.raises(ServerStartError):
        check_health(f"http://127.0.0.1:{kapali_port}", "gizli", timeout=1.0)


def test_urlopen_hata_kodunu_yutmaz() -> None:
    """Yardımcı: 403 bir istisna değil, sonuç olarak dönmeli."""
    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen("http://127.0.0.1:1/", timeout=1)
