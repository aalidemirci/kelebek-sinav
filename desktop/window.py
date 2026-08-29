"""pywebview penceresi + pencere motoru denetimi (tasarım §5.1/§5.2).

**MSHTML düşüşü KODLA ENGELLİDİR.** pywebview, Windows'ta EdgeChromium (WebView2)
bulamazsa sessizce eski MSHTML (Internet Explorer) motoruna düşer; React 18 orada
çalışmaz ve kullanıcı boş beyaz bir pencere görür. Bu yüzden:
  1. Açılışta WebView2 runtime'ı kayıt defterinden aranır, yoksa Türkçe yönlendirme
     verilir ve pencere hiç açılmaz;
  2. `webview.start()` çağrısına GUI motoru AÇIKÇA verilir (`gui="edgechromium"`),
     böylece pywebview'ın kendi düşüş mantığı devreye giremez.

pywebview TEMBEL içe aktarılır: paket kurulu olmayan geliştirme/test ortamında bu
modül yine de import edilebilir ve testler koşar.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from desktop.errors import WebViewUnavailableError
from desktop.paths import resource_root

logger = logging.getLogger("kelebek_sinav.window")

WINDOW_TITLE = "Kelebek Sınav"
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 860
WINDOW_MIN_SIZE = (1024, 700)
WINDOW_ICON_FILE = "kelebek-sinav.ico"
WINDOW_APP_ID = "KelebekSinav.Desktop"

# Microsoft Edge WebView2 Runtime'ın sabit ürün kimliği (Evergreen).
WEBVIEW2_CLIENT_ID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
_WEBVIEW2_KEYS = (
    ("HKLM", rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT_ID}"),
    ("HKLM", rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT_ID}"),
    ("HKCU", rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT_ID}"),
)
# "0.0.0.0" burada bir IP değil, kaldırılmış runtime'ın bıraktığı SÜRÜM damgasıdır.
_EMPTY_VERSIONS = {"", "0.0.0.0"}  # noqa: S104

RegistryReader = Callable[[str, str, str], "str | None"]
DwmSetter = Callable[[int, int, bool], int]

_WEBVIEW2_MESSAGE = "Pencere açılamadı: Microsoft Edge WebView2 Çalışma Zamanı bulunamadı."
_WEBVIEW2_HINT = (
    "Programın kurulum klasöründeki 'MicrosoftEdgeWebView2Setup.exe' dosyasını çalıştırıp "
    "WebView2'yi kurun, sonra programı yeniden açın. Kurulum yetkiniz yoksa okul bilişim "
    "sorumlusundan 'WebView2 Runtime' kurulumunu isteyin."
)


def _read_registry_value(hive: str, subkey: str, value_name: str) -> str | None:
    """Windows kayıt defterinden tek bir değer okur (Windows dışında None)."""
    if sys.platform != "win32":
        return None
    import winreg

    hives = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}
    try:
        with winreg.OpenKey(hives[hive], subkey) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
    except OSError:
        return None
    return str(value)


def webview2_installed(*, registry_reader: RegistryReader | None = None) -> bool:
    """WebView2 Runtime kurulu mu? (Evergreen kaydındaki `pv` sürümüne bakar)"""
    reader = registry_reader or _read_registry_value
    for hive, subkey in _WEBVIEW2_KEYS:
        version = reader(hive, subkey, "pv")
        if version and version.strip() not in _EMPTY_VERSIONS:
            return True
    return False


def gui_backend_for(platform: str) -> str:
    """Platforma göre AÇIK GUI motoru — pywebview'ın sessiz düşüşünü engeller."""
    if platform.startswith("win"):
        return "edgechromium"  # asla "mshtml"
    if platform == "darwin":
        return "cocoa"
    return "qt"  # Pardus/Linux: PyQt5 + QtWebEngine (tasarım §5.2)


def require_window_runtime(
    *,
    platform: str | None = None,
    registry_reader: RegistryReader | None = None,
) -> None:
    """Pencere motoru yoksa açılışı durdurur (Windows/WebView2)."""
    system = sys.platform if platform is None else platform
    if not system.startswith("win"):
        return
    if not webview2_installed(registry_reader=registry_reader):
        raise WebViewUnavailableError(_WEBVIEW2_MESSAGE, hint=_WEBVIEW2_HINT)


def _import_webview() -> Any:
    import webview

    return webview


def _native_window_handle(window: Any) -> int | None:
    """pywebview/WinForms penceresinin HWND değerini güvenle çözer."""
    native = getattr(window, "native", None)
    handle = getattr(native, "Handle", None)
    if handle is None:
        return None
    try:
        return int(handle.ToInt64())
    except AttributeError:
        try:
            return int(handle)
        except (TypeError, ValueError):
            return None


def _dwm_set_titlebar(hwnd: int, attribute: int, dark: bool) -> int:
    """DWM başlık çubuğu temasını ayarlar; dönüş değeri Windows HRESULT'tur."""
    import ctypes
    from ctypes import wintypes

    enabled = wintypes.BOOL(bool(dark))
    return int(
        ctypes.windll.dwmapi.DwmSetWindowAttribute(  # type: ignore[attr-defined]
            wintypes.HWND(hwnd),
            wintypes.DWORD(attribute),
            ctypes.byref(enabled),
            ctypes.sizeof(enabled),
        )
    )


def set_windows_app_id(*, platform: str | None = None) -> bool:
    """Görev çubuğu gruplaması ve ikon çözümü için kararlı Windows uygulama kimliği."""
    system = sys.platform if platform is None else platform
    if not system.startswith("win"):
        return False
    try:
        import ctypes

        result = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(  # type: ignore[attr-defined]
            ctypes.c_wchar_p(WINDOW_APP_ID)
        )
    except (OSError, AttributeError):
        logger.warning("Windows uygulama kimliği atanamadı.", exc_info=True)
        return False
    return int(result) == 0


def set_windows_window_icon(
    window: Any,
    *,
    platform: str | None = None,
    icon_path: Path | None = None,
    loader: Callable[[Path], Any] | None = None,
) -> bool:
    """WinForms ana penceresine paketlenmiş uygulama ikonunu doğrudan atar."""
    system = sys.platform if platform is None else platform
    if not system.startswith("win"):
        return False
    native = getattr(window, "native", None)
    if native is None:
        return False
    path = icon_path or (resource_root() / WINDOW_ICON_FILE)
    if icon_path is None and not path.is_file():
        path = resource_root() / "packaging" / "ikonlar" / WINDOW_ICON_FILE
    if not path.is_file():
        return False
    try:
        if loader is None:
            from System.Drawing import Icon

            icon = Icon(str(path))
        else:
            icon = loader(path)
        native.Icon = icon
    except (ImportError, OSError, AttributeError):
        logger.warning("Windows pencere ikonu uygulanamadı.", exc_info=True)
        return False
    return True


def set_windows_titlebar_theme(
    window: Any,
    dark: bool,
    *,
    platform: str | None = None,
    setter: DwmSetter | None = None,
) -> bool:
    """Windows başlık çubuğunu uygulamanın açık/koyu temasıyla eşitler."""
    system = sys.platform if platform is None else platform
    if not system.startswith("win"):
        return False
    hwnd = _native_window_handle(window)
    if hwnd is None:
        return False

    apply_attribute = setter or _dwm_set_titlebar
    # 20: Windows 10 20H1+; 19: daha eski Windows 10 yapıları için geri dönüş.
    for attribute in (20, 19):
        if apply_attribute(hwnd, attribute, dark) == 0:
            return True
    return False


class TitleBarApi:
    """Frontend temasını yerel Windows başlık çubuğuna taşıyan küçük JS köprüsü."""

    def __init__(self, *, platform: str) -> None:
        self._platform = platform
        self._window: Any | None = None
        self._icon_applied = False

    def bind_window(self, window: Any) -> None:
        self._window = window

    def set_titlebar_theme(self, dark: bool) -> bool:
        if self._window is None:
            return False
        try:
            if not self._icon_applied:
                self._icon_applied = set_windows_window_icon(
                    self._window,
                    platform=self._platform,
                )
            return set_windows_titlebar_theme(
                self._window,
                bool(dark),
                platform=self._platform,
            )
        except OSError:
            logger.warning("Windows başlık çubuğu teması uygulanamadı.", exc_info=True)
            return False


def open_window(
    url: str,
    *,
    title: str = WINDOW_TITLE,
    storage_path: Path,
    webview: Any | None = None,
    platform: str | None = None,
    importer: Callable[[], Any] | None = None,
) -> None:
    """Pencereyi açar ve kapanana kadar bloklar (pywebview'ın olay döngüsü)."""
    system = sys.platform if platform is None else platform
    module = webview
    if module is None:
        try:
            module = (importer or _import_webview)()
        except ImportError as exc:
            raise WebViewUnavailableError(
                "Pencere açılamadı: pencere bileşeni (pywebview) yüklü değil.",
                hint="Kurulum eksik görünüyor; programı yeniden kurun.",
            ) from exc

    storage_path.mkdir(parents=True, exist_ok=True)
    set_windows_app_id(platform=system)
    # pywebview 5.x dosya indirmelerini varsayılan olarak engeller. Frontend'in
    # ortak `saveBlob` akışı Excel şablonları, resmî PDF'ler, ekler ve kurtarma
    # anahtarı için `<a download>` kullandığından bu izin pencere oluşturulmadan
    # önce açılmalıdır; aksi hâlde tıklama hata vermeden sessizce yutulur.
    module.settings["ALLOW_DOWNLOADS"] = True
    titlebar_api = TitleBarApi(platform=system)
    window = module.create_window(
        title,
        url,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=WINDOW_MIN_SIZE,
        text_select=True,
        js_api=titlebar_api,
    )
    titlebar_api.bind_window(window)
    logger.info("Pencere açılıyor (%s).", gui_backend_for(system))
    module.start(
        gui=gui_backend_for(system),
        private_mode=False,  # oturum çerezi + taslaklar pencere ömrü boyunca kalsın
        storage_path=str(storage_path),
        debug=False,
    )
