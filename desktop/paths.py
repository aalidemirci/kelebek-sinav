"""Veri dizini çözümü — platform farkı TEK yerde, test edilebilir (tasarım §5.3).

Kural: **veri exe'nin DIŞINDA** durur. Windows'ta `%LOCALAPPDATA%` seçilir,
`%APPDATA%` (Roaming) seçilMEZ: gezici profil/OneDrive senkronu açık bir SQLite
dosyasını kopyalamaya kalkarsa veritabanı bozulur (risk kütüğü §9). Linux'ta XDG
ayrımı korunur: veri `~/.local/share`, log `~/.local/state`, önbellek `~/.cache`.

Tüm çözüm saf `os.environ` okumasıyla yapılır (`platformdirs` KULLANILMADI):
böylece Linux'taki testler Windows yerleşimini de doğrulayabilir ve paketlenmiş
uygulamaya bir bağımlılık daha girmez.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

# Dizin adı — tasarım §2.3 kimlik sabitleri: veri dizini adı KelebekSinav.
# (Ad değişirse YALNIZ bu iki sabit değişir; DD şablonundaki karşılıklarıyla
# çakışmaması F0 kapısında sınanır — iki uygulama aynı makinede veri karıştırmaz.)
APP_DIR_NAME_WINDOWS = "KelebekSinav"
APP_DIR_NAME_XDG = "kelebek-sinav"

# Tüm yerleşimi tek hamlede geçersiz kılar (test, CI, `--autotest`, taşınabilir kip).
ENV_APP_HOME = "KS_APP_HOME"
# Django kodunun bulunduğu dizin (paket içinde exe'nin yanında).
ENV_BACKEND_DIR = "KS_BACKEND_DIR"

DB_FILE_NAME = "db.sqlite3"
LOCK_FILE_NAME = "instance.lock"
VERSION_STAMP_FILE_NAME = "surum.json"

# Bulut/gezici profil senkronu belirtileri — SQLite dosyasını bozabilir.
_SYNC_MARKERS = (
    "onedrive",
    "dropbox",
    "google drive",
    "googledrive",
    "yandex.disk",
    "yandexdisk",
    "icloud",
    "mega",
    "appdata/roaming",
    "appdata\\roaming",
)


@dataclass(frozen=True)
class AppPaths:
    """Uygulamanın kullandığı tüm dizinler (hiçbiri kurulum dizininin içinde değildir)."""

    root: Path
    data: Path
    backups: Path
    logs: Path
    cache: Path

    @property
    def db_path(self) -> Path:
        return self.data / DB_FILE_NAME

    @property
    def lock_path(self) -> Path:
        return self.root / LOCK_FILE_NAME

    @property
    def version_stamp_path(self) -> Path:
        return self.data / VERSION_STAMP_FILE_NAME

    @property
    def webview_storage_path(self) -> Path:
        """Pencere motorunun profil dizini — önbellekte (silinebilir, veri değil)."""
        return self.cache / "webview"

    def ensure(self) -> None:
        """Dizinleri oluşturur; var olanlara dokunmaz."""
        for directory in (self.root, self.data, self.backups, self.logs, self.cache):
            directory.mkdir(parents=True, exist_ok=True)


def _home(environ: Mapping[str, str]) -> Path:
    raw = environ.get("HOME") or environ.get("USERPROFILE")
    return Path(raw) if raw else Path.home()


def _under(environ: Mapping[str, str], key: str, fallback: Path) -> Path:
    raw = environ.get(key)
    return Path(raw) if raw else fallback


def resolve_app_paths(
    *,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
) -> AppPaths:
    """Platforma uygun veri/yedek/log/önbellek dizinlerini döndürür (oluşturmaz)."""
    env = os.environ if environ is None else environ
    system = sys.platform if platform is None else platform

    override = env.get(ENV_APP_HOME)
    if override:
        root = Path(override)
        return AppPaths(
            root=root,
            data=root / "data",
            backups=root / "backups",
            logs=root / "logs",
            cache=root / "cache",
        )

    if system.startswith("win"):
        local = _under(env, "LOCALAPPDATA", _home(env) / "AppData" / "Local")
        root = local / APP_DIR_NAME_WINDOWS
        return AppPaths(
            root=root,
            data=root / "data",
            backups=root / "backups",
            logs=root / "logs",
            cache=root / "cache",
        )

    home = _home(env)
    share = _under(env, "XDG_DATA_HOME", home / ".local" / "share")
    state = _under(env, "XDG_STATE_HOME", home / ".local" / "state")
    cache = _under(env, "XDG_CACHE_HOME", home / ".cache")
    root = share / APP_DIR_NAME_XDG
    return AppPaths(
        root=root,
        data=root / "data",
        backups=root / "backups",
        logs=state / APP_DIR_NAME_XDG / "logs",
        cache=cache / APP_DIR_NAME_XDG,
    )


def check_sync_hazard(path: Path) -> str | None:
    """Veri dizini buluta/gezici profile denk geliyorsa Türkçe uyarı döndürür.

    Engellemez (kullanıcı bilinçli taşımış olabilir) — yalnız günlüğe yazılır.
    """
    lowered = str(path).lower().replace("\\", "/")
    for marker in _SYNC_MARKERS:
        if marker.replace("\\", "/") in lowered:
            return (
                f"Veri dizini bulut/gezici profil ile eşitlenen bir konumda görünüyor: {path}. "
                "Eşitleme açık veritabanı dosyasını bozabilir; verinizi eşitlenmeyen bir "
                "klasöre almanız ve düzenli yedek almanız önerilir."
            )
    return None


def resource_root() -> Path:
    """Paketlenmiş kaynakların kökü (PyInstaller'da `sys._MEIPASS`, depoda kök dizin)."""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(str(bundle))
    return Path(__file__).resolve().parent.parent


def resolve_backend_dir(*, environ: Mapping[str, str] | None = None) -> Path:
    """Django kodunun (config/apps/shared) bulunduğu dizini bulur."""
    env = os.environ if environ is None else environ

    adaylar: list[Path] = []
    override = env.get(ENV_BACKEND_DIR)
    if override:
        adaylar.append(Path(override))
    adaylar.append(resource_root() / "backend")
    adaylar.append(Path(__file__).resolve().parent.parent / "backend")

    for aday in adaylar:
        if (aday / "config" / "settings.py").is_file():
            return aday
    raise FileNotFoundError(
        "Program dosyaları bulunamadı (config/settings.py yok). Kurulum bozuk olabilir; "
        "programı yeniden kurun."
    )
