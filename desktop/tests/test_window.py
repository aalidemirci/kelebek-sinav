"""Pencere katmanı testleri — WebView2 tespiti + MSHTML düşüşünün ENGELLİ olması."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from desktop.errors import WebViewUnavailableError
from desktop.window import (
    WINDOW_TITLE,
    gui_backend_for,
    open_window,
    require_window_runtime,
    set_windows_titlebar_theme,
    set_windows_window_icon,
    webview2_installed,
)


class _SahteWebview:
    """pywebview modülü yerine geçen kayıt tutucu."""

    def __init__(self) -> None:
        self.settings: dict[str, Any] = {"ALLOW_DOWNLOADS": False}
        self.pencereler: list[dict[str, Any]] = []
        self.start_kwargs: dict[str, Any] = {}

    def create_window(self, title: str, url: str, **kwargs: Any) -> object:
        self.pencereler.append({"title": title, "url": url, **kwargs})
        return object()

    def start(self, **kwargs: Any) -> None:
        self.start_kwargs = kwargs


def _kayit(bulunan: dict[tuple[str, str], str]) -> Any:
    def oku(hive: str, subkey: str, value: str) -> str | None:
        return bulunan.get((hive, value))

    return oku


# ------------------------------------------------------------------- WebView2


def test_webview2_hklm_kaydindan_bulunur() -> None:
    assert webview2_installed(registry_reader=_kayit({("HKLM", "pv"): "120.0.2210.91"}))


def test_webview2_kayit_yoksa_bulunmaz() -> None:
    assert not webview2_installed(registry_reader=_kayit({}))


def test_webview2_bos_surum_kurulu_sayilmaz() -> None:
    """Kaldırılmış runtime kaydı `pv=0.0.0.0` bırakır — kurulu DEĞİLDİR."""
    assert not webview2_installed(
        registry_reader=_kayit({("HKLM", "pv"): "0.0.0.0"})  # noqa: S104 — sürüm damgası
    )


def test_windows_disinda_webview2_aranmaz() -> None:
    require_window_runtime(platform="linux", registry_reader=_kayit({}))


def test_windows_ta_webview2_yoksa_turkce_yonlendirme() -> None:
    with pytest.raises(WebViewUnavailableError) as hata:
        require_window_runtime(platform="win32", registry_reader=_kayit({}))

    assert "WebView2" in str(hata.value)
    assert "kur" in hata.value.hint.lower()


def test_windows_ta_webview2_varsa_gecer() -> None:
    require_window_runtime(
        platform="win32", registry_reader=_kayit({("HKCU", "pv"): "120.0.2210.91"})
    )


# ------------------------------------------------------------------- pencere


def test_gui_motoru_platforma_gore_secilir() -> None:
    assert gui_backend_for("win32") == "edgechromium"
    assert gui_backend_for("linux") == "qt"
    assert gui_backend_for("darwin") == "cocoa"


def test_mshtml_asla_secilmez() -> None:
    """React 18 MSHTML'de çalışmaz; pywebview'ın sessiz düşüşü KODLA engellenir."""
    assert "mshtml" not in {gui_backend_for(p) for p in ("win32", "linux", "darwin")}


def test_pencere_turkce_baslikla_acilir(tmp_path: Path) -> None:
    sahte = _SahteWebview()

    open_window(
        "http://127.0.0.1:5051/?t=gizli",
        webview=sahte,
        platform="linux",
        storage_path=tmp_path / "webview",
    )

    assert sahte.pencereler[0]["title"] == WINDOW_TITLE
    assert WINDOW_TITLE == "Kelebek Sınav"
    assert sahte.pencereler[0]["url"] == "http://127.0.0.1:5051/?t=gizli"


def test_pencere_gui_motorunu_acikca_verir(tmp_path: Path) -> None:
    sahte = _SahteWebview()

    open_window("http://127.0.0.1:1/", webview=sahte, platform="win32", storage_path=tmp_path)

    assert sahte.start_kwargs["gui"] == "edgechromium"


def test_pencere_dosya_indirmelerine_izin_verir(tmp_path: Path) -> None:
    """Blob bağlantıları Excel/PDF/TXT dosyalarını masaüstünde kaydedebilmeli."""
    sahte = _SahteWebview()

    open_window("http://127.0.0.1:1/", webview=sahte, platform="win32", storage_path=tmp_path)

    assert sahte.settings["ALLOW_DOWNLOADS"] is True


def test_pencere_baslik_cubugu_tema_koprusunu_frontende_sunar(tmp_path: Path) -> None:
    sahte = _SahteWebview()

    open_window("http://127.0.0.1:1/", webview=sahte, platform="win32", storage_path=tmp_path)

    api = sahte.pencereler[0]["js_api"]
    assert callable(api.set_titlebar_theme)
    assert api.set_titlebar_theme(True) is False


def test_windows_baslik_cubugu_koyu_tema_ozelligini_uygular() -> None:
    class _Handle:
        def ToInt64(self) -> int:
            return 2468

    class _Native:
        Handle = _Handle()

    class _Window:
        native = _Native()

    calls: list[tuple[int, int, bool]] = []

    def setter(hwnd: int, attribute: int, dark: bool) -> int:
        calls.append((hwnd, attribute, dark))
        return 0

    assert set_windows_titlebar_theme(_Window(), True, platform="win32", setter=setter)
    assert calls == [(2468, 20, True)]


def test_windows_baslik_cubugu_eski_dwm_ozelligine_geri_doner() -> None:
    class _Window:
        native = type("Native", (), {"Handle": 1357})()

    calls: list[int] = []

    def setter(_hwnd: int, attribute: int, _dark: bool) -> int:
        calls.append(attribute)
        return 1 if attribute == 20 else 0

    assert set_windows_titlebar_theme(_Window(), False, platform="win32", setter=setter)
    assert calls == [20, 19]


def test_windows_pencere_ikonu_yerel_forma_uygulanir(tmp_path: Path) -> None:
    icon_path = tmp_path / "uygulama.ico"
    icon_path.write_bytes(b"ico")

    class _Native:
        Icon: Any | None = None

    class _Window:
        native = _Native()

    loaded: list[Path] = []
    marker = object()

    def loader(path: Path) -> object:
        loaded.append(path)
        return marker

    assert set_windows_window_icon(
        _Window(),
        platform="win32",
        icon_path=icon_path,
        loader=loader,
    )
    assert loaded == [icon_path]
    assert _Window.native.Icon is marker


def test_pencere_profil_dizini_veri_alaninda(tmp_path: Path) -> None:
    """Pencere motorunun profili kurulum dizinine değil, önbelleğe yazılır."""
    sahte = _SahteWebview()
    hedef = tmp_path / "cache" / "webview"

    open_window("http://127.0.0.1:1/", webview=sahte, platform="linux", storage_path=hedef)

    assert sahte.start_kwargs["storage_path"] == str(hedef)
    assert hedef.is_dir()


def test_pywebview_kurulu_degilse_turkce_hata(tmp_path: Path) -> None:
    def bulunamadi() -> Any:
        raise ImportError("No module named 'webview'")

    with pytest.raises(WebViewUnavailableError) as hata:
        open_window(
            "http://127.0.0.1:1/",
            webview=None,
            platform="linux",
            storage_path=tmp_path,
            importer=bulunamadi,
        )

    assert "pencere" in str(hata.value).lower()
