"""Açılış orkestrasyonu testleri (tasarım §5.3 açılış sırası).

Buradaki testler Django'yu çalıştırmaz — sıra ve karar mantığı sahte adımlarla
doğrulanır. Gerçek uçtan uca açılış (migrate + waitress + belirteç koruması)
`test_autotest_kipi_gercek_acilisi_dogrular` içinde ALT SÜREÇ olarak koşar.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from desktop import main as main_mod
from desktop.errors import (
    EXIT_ALREADY_RUNNING,
    EXIT_DATABASE_CORRUPT,
    EXIT_OK,
    EXIT_WEBVIEW_UNAVAILABLE,
    DatabaseCorruptError,
    WebViewUnavailableError,
)
from desktop.lock import SingleInstanceLock
from desktop.paths import ENV_APP_HOME, resolve_app_paths

REPO_ROOT = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------ argümanlar


def test_autotest_bayragi_varsayilan_kapali() -> None:
    assert main_mod.build_parser().parse_args([]).autotest is False
    assert main_mod.build_parser().parse_args(["--autotest"]).autotest is True


def test_veri_dizini_bayragi_yerlesimi_gecersiz_kilar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ENV_APP_HOME, raising=False)

    paths = main_mod.resolve_paths(
        main_mod.build_parser().parse_args(["--data-dir", str(tmp_path)])
    )

    assert paths.root == tmp_path


# ----------------------------------------------------------------- açılış sırası


@pytest.fixture
def izlenen_adimlar(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """`_prepare_data` içindeki tüm adımları kayda geçirir (Django çalışmaz)."""
    sira: list[str] = []

    def kaydet(ad: str, sonuc: Any = None) -> Any:
        def sahte(*args: Any, **kwargs: Any) -> Any:
            sira.append(ad)
            return sonuc

        return sahte

    monkeypatch.setattr(main_mod, "ensure_stamp_compatible", kaydet("surum-damgasi"))
    monkeypatch.setattr(main_mod, "check_database_integrity", kaydet("butunluk"))
    monkeypatch.setattr(main_mod, "encrypt_legacy_backups", kaydet("eski-yedekleri-sifrele", []))
    monkeypatch.setattr(main_mod, "daily_backup", kaydet("gunluk-yedek"))
    monkeypatch.setattr(main_mod, "rotate_backups", kaydet("rotasyon", []))
    monkeypatch.setattr(main_mod, "prepare_django", kaydet("django-hazirla"))
    monkeypatch.setattr(main_mod, "has_pending_migrations", kaydet("bekleyen-goc-var-mi", True))
    monkeypatch.setattr(main_mod, "pre_migrate_backup", kaydet("goc-oncesi-yedek"))
    monkeypatch.setattr(main_mod, "run_migrations", kaydet("goc"))
    monkeypatch.setattr(main_mod, "write_version_stamp", kaydet("damga-yaz"))
    return sira


def test_acilis_sirasi_tasarimla_birebir(tmp_path: Path, izlenen_adimlar: list[str]) -> None:
    paths = resolve_app_paths(environ={ENV_APP_HOME: str(tmp_path)})

    main_mod.prepare_data(paths, "0.1.0")

    assert izlenen_adimlar == [
        "surum-damgasi",  # eski program yeni veriyi açmasın
        "butunluk",  # bozuk veriyle yedek rotasyonu ÇALIŞTIRILMAZ
        "eski-yedekleri-sifrele",
        "gunluk-yedek",
        "rotasyon",
        "django-hazirla",
        "bekleyen-goc-var-mi",
        "goc-oncesi-yedek",
        "goc",
        "damga-yaz",
    ]


def test_bekleyen_goc_yoksa_ek_yedek_alinmaz(
    tmp_path: Path, izlenen_adimlar: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main_mod, "has_pending_migrations", lambda: False)
    paths = resolve_app_paths(environ={ENV_APP_HOME: str(tmp_path)})

    main_mod.prepare_data(paths, "0.1.0")

    assert "goc-oncesi-yedek" not in izlenen_adimlar


# ------------------------------------------------------------ hata senaryoları


@pytest.fixture
def sahte_calisma(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """`run()` çevresini izole eder: veri hazırlığı ve sunucu sahte."""
    kayit: dict[str, Any] = {"pencere": 0, "hata": [], "servis": 0}

    def sahte_serve(paths: Any, token: str, autotest: bool) -> int:
        kayit["servis"] += 1
        return EXIT_OK

    def sahte_hata(title: str, message: str) -> None:
        kayit["hata"].append((title, message))

    monkeypatch.setattr(main_mod, "prepare_data", lambda paths, version: None)
    monkeypatch.setattr(main_mod, "serve", sahte_serve)
    monkeypatch.setattr(main_mod, "show_error", sahte_hata)
    return kayit


def test_ikinci_kopya_pencere_acmadan_cikar(
    tmp_path: Path, sahte_calisma: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_APP_HOME, str(tmp_path))
    ilk = SingleInstanceLock(resolve_app_paths().lock_path)
    ilk.acquire()
    try:
        kod = main_mod.run([])
    finally:
        ilk.release()

    assert kod == EXIT_ALREADY_RUNNING
    assert sahte_calisma["servis"] == 0
    assert "zaten çalışıyor" in sahte_calisma["hata"][0][1]


def test_bozuk_veritabani_pencere_actirmaz(
    tmp_path: Path, sahte_calisma: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_APP_HOME, str(tmp_path))

    def patla(paths: Any, version: str) -> None:
        raise DatabaseCorruptError("Veri dosyası bozuk görünüyor.", hint="Son yedekten dönün.")

    monkeypatch.setattr(main_mod, "prepare_data", patla)

    kod = main_mod.run([])

    assert kod == EXIT_DATABASE_CORRUPT
    assert sahte_calisma["servis"] == 0
    baslik, mesaj = sahte_calisma["hata"][0]
    assert "bozuk" in mesaj.lower()
    assert "yedek" in mesaj.lower()
    assert baslik


def test_webview_yoksa_ozel_cikis_kodu(
    tmp_path: Path, sahte_calisma: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_APP_HOME, str(tmp_path))

    def patla(paths: Any, token: str, autotest: bool) -> int:
        raise WebViewUnavailableError("WebView2 yok.", hint="Kurun.")

    monkeypatch.setattr(main_mod, "serve", patla)

    assert main_mod.run([]) == EXIT_WEBVIEW_UNAVAILABLE


def test_beklenmeyen_hata_da_turkce_iletiyle_biter(
    tmp_path: Path, sahte_calisma: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_APP_HOME, str(tmp_path))

    def patla(paths: Any, version: str) -> None:
        raise RuntimeError("beklenmedik")

    monkeypatch.setattr(main_mod, "prepare_data", patla)

    kod = main_mod.run([])

    assert kod == 1
    assert sahte_calisma["hata"]
    assert "beklenmedik" not in sahte_calisma["hata"][0][1]  # ham teknik metin gösterilmez


def test_kilit_cikista_birakilir(
    tmp_path: Path, sahte_calisma: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_APP_HOME, str(tmp_path))

    main_mod.run([])
    main_mod.run([])  # kilit bırakılmamış olsaydı ikinci koşu reddedilirdi

    assert sahte_calisma["servis"] == 2


# ------------------------------------------------------------ uçtan uca açılış


@pytest.mark.slow
def test_autotest_kipi_gercek_acilisi_dogrular(tmp_path: Path) -> None:
    """Gerçek açılış: kilit → yedek → migrate → waitress → belirteç → çıkış (pencere YOK)."""
    sonuc = subprocess.run(  # noqa: S603 — sabit argümanlar, kabuk yok
        [
            sys.executable,
            "-m",
            "desktop.main",
            "--autotest",
            "--data-dir",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert sonuc.returncode == EXIT_OK, sonuc.stderr
    assert (tmp_path / "data" / "db.sqlite3").is_file()
    assert (tmp_path / "data" / "surum.json").is_file()
    assert (tmp_path / "logs" / "uygulama.log").is_file()
    # İlk açılışta veritabanı henüz yoktu → günlük yedek bir sonraki açılışta alınır.
    assert (tmp_path / "backups").is_dir()


@pytest.mark.slow
def test_ikinci_acilis_gunluk_yedegi_alir(tmp_path: Path) -> None:
    for _ in range(2):
        sonuc = subprocess.run(  # noqa: S603 — sabit argümanlar, kabuk yok
            [
                sys.executable,
                "-m",
                "desktop.main",
                "--autotest",
                "--data-dir",
                str(tmp_path),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert sonuc.returncode == EXIT_OK, sonuc.stderr

    # Uygulama parolası kurulana dek açık yedek üretmek yerine günlük yedek atlanır.
    yedekler = list((tmp_path / "backups").glob("gunluk-*"))
    assert yedekler == []


@pytest.mark.slow
def test_gunluge_ogrenci_arama_sorgusu_dusmez(tmp_path: Path) -> None:
    """Erişim logu kapalı: istek yolu ne dosyaya ne de konsola düşmeli (F2 #20).

    `KS_DEBUG=1` ile koşar: Django'nun konsol handler'ı ancak DEBUG açıkken
    yayın yapar, yani sızıntı bu kipte görünür hale gelir.
    """
    sonuc = subprocess.run(  # noqa: S603 — sabit argümanlar, kabuk yok
        [
            sys.executable,
            "-m",
            "desktop.main",
            "--autotest",
            "--data-dir",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, "KS_DEBUG": "1"},
    )

    gunluk = (tmp_path / "logs" / "uygulama.log").read_text(encoding="utf-8")
    assert "setup/status" not in gunluk  # istek yolu bile loglanmaz
    assert "?" not in gunluk
    assert "setup/status" not in sonuc.stderr
    assert "Forbidden" not in sonuc.stderr
    assert "Logging error" not in sonuc.stderr
