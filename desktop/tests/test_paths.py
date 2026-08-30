"""Veri dizini çözümü testleri (tasarım §5.3 — veri exe DIŞINDA)."""

from __future__ import annotations

from pathlib import Path

import pytest

from desktop import paths as paths_mod
from desktop.paths import AppPaths, check_sync_hazard, resolve_app_paths, resolve_backend_dir


def test_windows_yerlesimi_localappdata_altinda() -> None:
    """Windows'ta veri kökü %LOCALAPPDATA% — Roaming DEĞİL (profil senkronu tuzağı)."""
    result = resolve_app_paths(
        environ={"LOCALAPPDATA": r"C:\Users\ali\AppData\Local", "USERPROFILE": r"C:\Users\ali"},
        platform="win32",
    )

    root = Path(r"C:\Users\ali\AppData\Local") / paths_mod.APP_DIR_NAME_WINDOWS
    assert result.root == root
    assert result.data == root / "data"
    assert result.backups == root / "backups"
    assert result.logs == root / "logs"
    assert result.cache == root / "cache"
    assert "Roaming" not in str(result.root)


def test_windows_localappdata_yoksa_profilden_turetilir() -> None:
    result = resolve_app_paths(environ={"USERPROFILE": r"C:\Users\ali"}, platform="win32")

    assert result.root.parts[-3:] == ("AppData", "Local", paths_mod.APP_DIR_NAME_WINDOWS)


def test_linux_xdg_varsayilanlari() -> None:
    """Linux'ta XDG: veri ~/.local/share, log ~/.local/state, önbellek ~/.cache."""
    result = resolve_app_paths(environ={"HOME": "/home/ali"}, platform="linux")

    name = paths_mod.APP_DIR_NAME_XDG
    assert result.root == Path("/home/ali/.local/share") / name
    assert result.data == Path("/home/ali/.local/share") / name / "data"
    assert result.backups == Path("/home/ali/.local/share") / name / "backups"
    assert result.logs == Path("/home/ali/.local/state") / name / "logs"
    assert result.cache == Path("/home/ali/.cache") / name


def test_linux_xdg_env_degiskenleri_onceliklidir() -> None:
    result = resolve_app_paths(
        environ={
            "HOME": "/home/ali",
            "XDG_DATA_HOME": "/veri",
            "XDG_STATE_HOME": "/durum",
            "XDG_CACHE_HOME": "/onbellek",
        },
        platform="linux",
    )

    name = paths_mod.APP_DIR_NAME_XDG
    assert result.data == Path("/veri") / name / "data"
    assert result.logs == Path("/durum") / name / "logs"
    assert result.cache == Path("/onbellek") / name


def test_ks_app_home_tum_yerlesimi_gecersiz_kilar(tmp_path: Path) -> None:
    """Test/CI için tek env değişkeniyle tam override (`--autotest` bunu kullanır)."""
    result = resolve_app_paths(
        environ={paths_mod.ENV_APP_HOME: str(tmp_path), "HOME": "/home/ali"},
        platform="linux",
    )

    assert result.root == tmp_path
    assert result.data == tmp_path / "data"
    assert result.backups == tmp_path / "backups"
    assert result.logs == tmp_path / "logs"
    assert result.cache == tmp_path / "cache"


def test_ensure_dizinleri_olusturur_ve_tekrarlanabilir(tmp_path: Path) -> None:
    result = resolve_app_paths(environ={paths_mod.ENV_APP_HOME: str(tmp_path / "kok")})

    result.ensure()
    result.ensure()  # ikinci çağrı patlamamalı

    for directory in (result.root, result.data, result.backups, result.logs, result.cache):
        assert directory.is_dir()


def test_turetilmis_dosya_yollari(tmp_path: Path) -> None:
    result = resolve_app_paths(environ={paths_mod.ENV_APP_HOME: str(tmp_path)})

    assert result.db_path == tmp_path / "data" / "db.sqlite3"
    assert result.lock_path == tmp_path / "instance.lock"
    assert result.version_stamp_path == tmp_path / "data" / "surum.json"
    assert result.webview_storage_path == tmp_path / "cache" / "webview"


@pytest.mark.parametrize(
    "yol",
    [
        r"C:\Users\ali\OneDrive\Belgeler\KelebekSinav",
        r"C:\Users\ali\AppData\Roaming\KelebekSinav",
        "/home/ali/Dropbox/kelebek-sinav",
    ],
)
def test_senkron_dizin_uyarisi_verilir(yol: str) -> None:
    uyari = check_sync_hazard(Path(yol))

    assert uyari is not None
    assert "yedek" in uyari.lower() or "senkron" in uyari.lower()


def test_senkron_disi_dizin_uyari_vermez() -> None:
    assert check_sync_hazard(Path(r"C:\Users\ali\AppData\Local\KelebekSinav")) is None


def test_backend_dizini_depo_yerlesiminden_bulunur() -> None:
    backend = resolve_backend_dir()

    assert (backend / "config" / "settings.py").is_file()
    assert (backend / "manage.py").is_file()


def test_backend_dizini_env_ile_gecersiz_kilinir(tmp_path: Path) -> None:
    sahte = tmp_path / "backend"
    (sahte / "config").mkdir(parents=True)
    (sahte / "config" / "settings.py").write_text("", encoding="utf-8")

    assert resolve_backend_dir(environ={"KS_BACKEND_DIR": str(sahte)}) == sahte


def test_app_paths_degistirilemez(tmp_path: Path) -> None:
    result = resolve_app_paths(environ={paths_mod.ENV_APP_HOME: str(tmp_path)})

    with pytest.raises(AttributeError):
        result.root = tmp_path  # type: ignore[misc]

    assert isinstance(result, AppPaths)
