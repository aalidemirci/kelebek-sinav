"""PyInstaller çalışma-zamanı kancası — paketlenmiş uygulamanın ortamını kurar.

BU DOSYADAKİ WINDOWS YOLU BU ORTAMDA DOĞRULANMADI — ilk Windows koşusunda
sınanacak. Linux yolu (`KS_FRONTEND_DIR`) debian:11 + debian:12 kurulum
provalarında koşturuldu.

Kanca, giriş betiğinden (`giris.py`) ÖNCE çalışır; yaptığı üç iş de "ilk
import'tan önce ortam değişkeni set etmek" gerektirdiği için başka bir yere
konulamaz:

1. **WeasyPrint DLL dizini (yalnız Windows).** WeasyPrint pango/harfbuzz/
   fontconfig kütüphanelerini çalışma anında `LoadLibrary` ile açar;
   paketleyici bunları statik çözümlemeyle göremediği için DLL'ler paket
   köküne ayrıca kopyalanır (`packaging/windows/dll_kapanisi.py`). WeasyPrint
   ≥60 `WEASYPRINT_DLL_DIRECTORIES` değişkenini resmen destekler ve bu değişken
   `weasyprint` import edilmeden ÖNCE dolu olmalıdır.

2. **Fontconfig yapılandırması (yalnız Windows).** Windows'ta sistem fontconfig
   yapılandırması yoktur; ayrıca sistem fontlarına güvenilmez (tasarım §5.1:
   yalnız gömülü DejaVu). Paketteki `fonts.conf.tmpl` şablonu, YAZILABİLİR bir
   önbellek dizini (`%LOCALAPPDATA%\\KelebekSinav\\cache\\fontconfig`) ve
   gömülü font dizini işlenerek kullanıcı veri dizinine yazılır;
   `FONTCONFIG_FILE` oraya bakar. Kurulum dizini salt-okunur olabileceği için
   şablon paketin içinde İŞLENMEZ.

3. **Frontend dizini (her platform).** Derlenmiş SPA paket içinde
   `frontend/dist` altındadır; Django tarafı bu yolu `KS_FRONTEND_DIR`
   değişkeninden okur.

Kancadaki hiçbir hata programı durdurmaz: eksik font yapılandırması PDF'i
bozar ama sınav kayıtlarına erişimi engellememeli. Sorunlar günlüğe değil
(günlük henüz kurulmadı) `KS_RTHOOK_UYARI` değişkenine yazılır.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ENV_WARNING = "KS_RTHOOK_UYARI"
ENV_FRONTEND_DIR = "KS_FRONTEND_DIR"
ENV_WEASYPRINT_DLL = "WEASYPRINT_DLL_DIRECTORIES"

_FONTS_CONF_TEMPLATE = "fonts.conf.tmpl"
_FONTS_CONF = "fonts.conf"


def _bundle_root() -> Path:
    """Paketlenmiş kaynakların kökü (`sys._MEIPASS`)."""
    bundle = getattr(sys, "_MEIPASS", None)
    return Path(str(bundle)) if bundle else Path(__file__).resolve().parent


def _warn(message: str) -> None:
    """Uyarıyı ortam değişkenine biriktirir (günlük henüz kurulmadı)."""
    current = os.environ.get(ENV_WARNING, "")
    os.environ[ENV_WARNING] = f"{current} | {message}" if current else message


def _cache_root() -> Path:
    """Yazılabilir önbellek dizini — masaüstü kabuğuyla AYNI yerleşim."""
    try:
        from desktop.paths import resolve_app_paths

        return resolve_app_paths().cache
    except Exception:  # noqa: BLE001 — kanca hiçbir koşulda açılışı durdurmaz
        fallback = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or "."
        return Path(fallback) / "KelebekSinav" / "cache"


def announce_frontend_dir(root: Path) -> None:
    """Derlenmiş SPA'nın yolunu `KS_FRONTEND_DIR` ile Django'ya bildirir."""
    dist = root / "frontend" / "dist"
    if dist.is_dir():
        os.environ.setdefault(ENV_FRONTEND_DIR, str(dist))
    else:
        _warn(f"Arayüz dosyaları bulunamadı: {dist}")


def announce_weasyprint_dll_dirs(root: Path) -> None:
    """WeasyPrint'in arayacağı DLL dizinlerini bildirir (Windows)."""
    candidates = [root, root / "dll"]
    existing = [str(path) for path in candidates if path.is_dir()]
    if existing:
        os.environ.setdefault(ENV_WEASYPRINT_DLL, os.pathsep.join(existing))


def setup_fontconfig(root: Path, cache_root: Path) -> Path | None:
    """Gömülü fontları gösteren `fonts.conf`'u yazılabilir dizine üretir (Windows).

    Şablondaki `@FONT_DIR@` ve `@CACHE_DIR@` yer tutucuları doldurulur. Dosya
    her açılışta yeniden yazılır: kurulum dizini değişmiş (taşınabilir zip başka
    bir klasöre açılmış) olabilir.
    """
    template = root / _FONTS_CONF_TEMPLATE
    if not template.is_file():
        _warn(f"Font yapılandırma şablonu bulunamadı: {template}")
        return None

    font_dir = root / "fonts"
    cache_dir = cache_root / "fontconfig"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        content = template.read_text(encoding="utf-8")
        content = content.replace("@FONT_DIR@", escape(font_dir.as_posix()))
        content = content.replace("@CACHE_DIR@", escape(cache_dir.as_posix()))
        target = cache_root / _FONTS_CONF
        target.write_text(content, encoding="utf-8")
    except OSError as error:
        _warn(f"Font yapılandırması yazılamadı: {error}")
        return None

    os.environ["FONTCONFIG_FILE"] = str(target)
    os.environ["FONTCONFIG_PATH"] = str(target.parent)
    return target


def setup() -> None:
    """Kancanın tüm adımları (test edilebilirlik için ayrı fonksiyon)."""
    root = _bundle_root()
    announce_frontend_dir(root)
    if sys.platform.startswith("win"):
        announce_weasyprint_dll_dirs(root)
        setup_fontconfig(root, _cache_root())


setup()
