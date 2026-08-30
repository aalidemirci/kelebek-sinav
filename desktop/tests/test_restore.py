"""`--geri-yukle` kipi testleri (desktop/restore.py).

Birim testleri backend çekirdeğini SAHTE servisle değiştirir: masaüstü testleri
asgari Django ayarlarıyla koşar ve `apps.okul` bu ortamda import edilemez
(bkz. conftest). Gerçek zincir (prepare_django → çekirdek → dosya değişimi)
sondaki yavaş alt-süreç testinde doğrulanır.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from desktop import main as main_mod
from desktop import restore as restore_mod
from desktop.backup_crypto import MAGIC
from desktop.errors import EXIT_ALREADY_RUNNING, EXIT_OK, EXIT_RESTORE_FAILED
from desktop.lock import SingleInstanceLock
from desktop.paths import ENV_APP_HOME, AppPaths, resolve_app_paths

REPO_ROOT = Path(__file__).resolve().parents[2]

SQLITE_MAGIC = b"SQLite format 3\x00"


# ------------------------------------------------------------------ argümanlar


def test_geri_yukle_bayragi_uc_bicimde_ayristirilir() -> None:
    parser = main_mod.build_parser()
    assert parser.parse_args([]).geri_yukle is None
    assert parser.parse_args(["--geri-yukle"]).geri_yukle == ""  # dosya yok → seçici
    assert parser.parse_args(["--geri-yukle", "x.ksbak"]).geri_yukle == "x.ksbak"

    args = parser.parse_args(
        ["--geri-yukle", "--parola", "p", "--kurtarma-anahtari", "k", "--evet"]
    )
    assert args.geri_yukle == ""
    assert args.parola == "p"
    assert args.kurtarma_anahtari == "k"
    assert args.evet is True


def test_geri_yukle_kipinde_normal_acilis_kosulmaz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_APP_HOME, str(tmp_path))
    cagri: dict[str, Any] = {}

    def sahte(paths: AppPaths, args: Any) -> int:
        cagri["paths"] = paths
        cagri["args"] = args
        return 42

    monkeypatch.setattr(main_mod, "run_restore", sahte)
    monkeypatch.setattr(
        main_mod, "prepare_data", lambda *a: pytest.fail("normal açılış koşulmamalı")
    )

    assert main_mod.run(["--geri-yukle"]) == 42
    assert cagri["args"].geri_yukle == ""
    assert cagri["paths"].root == tmp_path


# ------------------------------------------------------------------ tesisat


def _paths(tmp_path: Path) -> AppPaths:
    paths = resolve_app_paths(environ={ENV_APP_HOME: str(tmp_path)})
    paths.ensure()
    return paths


def test_program_acikken_geri_yukleme_reddedilir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    hatalar: list[str] = []
    monkeypatch.setattr(restore_mod, "show_error", lambda baslik, mesaj: hatalar.append(mesaj))
    monkeypatch.setattr(restore_mod, "_restore_flow", lambda *a: pytest.fail("akış koşulmamalı"))
    args = main_mod.build_parser().parse_args(["--geri-yukle"])

    ilk = SingleInstanceLock(paths.lock_path)
    ilk.acquire()
    try:
        kod = restore_mod.run_restore(paths, args)
    finally:
        ilk.release()

    assert kod == EXIT_ALREADY_RUNNING
    assert "kapatın" in hatalar[0]


def test_yedekler_en_yeniden_eskiye_listelenir(tmp_path: Path) -> None:
    dizin = tmp_path / "backups"
    dizin.mkdir()
    eski = dizin / "gunluk-2026-08-01.ksbak"
    eski.write_bytes(b"x")
    yeni = dizin / "gunluk-2026-08-20.ksbak"
    yeni.write_bytes(b"y")
    (dizin / "alakasiz.txt").write_bytes(b"z")  # yalnız .ksbak listelenir
    os.utime(eski, (1_000_000, 1_000_000))
    os.utime(yeni, (2_000_000, 2_000_000))

    assert restore_mod.list_backups(dizin) == [yeni, eski]
    assert restore_mod.list_backups(dizin / "yok") == []


def test_yedek_secici_gecersiz_girdiden_sonra_dogru_secer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    yedekler = [tmp_path / "a.ksbak", tmp_path / "b.ksbak"]
    for yol in yedekler:
        yol.write_bytes(SQLITE_MAGIC)
    girdiler = iter(["9", "2"])
    monkeypatch.setattr("builtins.input", lambda *args: next(girdiler))

    assert restore_mod._pick_backup(yedekler) == yedekler[1]
    assert "Geçersiz seçim" in capsys.readouterr().out


def test_yedek_secici_bos_girdiyle_vazgecer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    yedek = tmp_path / "a.ksbak"
    yedek.write_bytes(SQLITE_MAGIC)
    monkeypatch.setattr("builtins.input", lambda *args: "")

    assert restore_mod._pick_backup([yedek]) is None


# ------------------------------------------------------------------ akış (sahte servis)


class SahteServisHatasi(Exception):
    pass


def _sahte_servis(kayit: dict[str, Any], *, hata: str | None = None) -> Any:
    def restore_database(
        yedek: Path, db_path: Path, *, password: str | None = None, recovery_key: str | None = None
    ) -> Any:
        if hata is not None:
            raise SahteServisHatasi(hata)
        kayit["cagri"] = (yedek, db_path, password, recovery_key)
        return SimpleNamespace(
            encrypted=False, db_path=db_path, old_db_path=None, state_written=False
        )

    return SimpleNamespace(BackupRestoreError=SahteServisHatasi, restore_database=restore_database)


@pytest.fixture
def sahte_ortam(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Django hazırlığını ve backend çekirdeğini sahteler; çağrıları kaydeder."""
    kayit: dict[str, Any] = {}
    monkeypatch.setattr(restore_mod, "prepare_django", lambda *a, **k: None)
    monkeypatch.setattr(restore_mod, "_load_service", lambda: _sahte_servis(kayit))
    return kayit


def test_akis_duz_yedegi_servise_iletir(
    tmp_path: Path, sahte_ortam: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    paths = _paths(tmp_path)
    yedek = paths.backups / "gunluk-2026-08-29.ksbak"
    yedek.write_bytes(SQLITE_MAGIC + b"\x00" * 16)
    args = main_mod.build_parser().parse_args(["--geri-yukle", str(yedek), "--evet"])

    kod = restore_mod._restore_flow(paths, args)

    assert kod == EXIT_OK
    hedef_yedek, hedef_db, parola, anahtar = sahte_ortam["cagri"]
    assert hedef_yedek == yedek
    assert hedef_db == paths.db_path
    assert parola is None and anahtar is None
    assert "tamamlandı" in capsys.readouterr().out


def test_akis_yalniz_dosya_adiyla_yedek_klasorunde_arar(
    tmp_path: Path, sahte_ortam: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    paths = _paths(tmp_path)
    yedek = paths.backups / "gunluk-2026-08-29.ksbak"
    yedek.write_bytes(SQLITE_MAGIC)
    args = main_mod.build_parser().parse_args(["--geri-yukle", yedek.name, "--evet"])

    assert restore_mod._restore_flow(paths, args) == EXIT_OK
    assert sahte_ortam["cagri"][0] == yedek


def test_akis_sifreli_yedekte_bayrak_sirlarini_kullanir(
    tmp_path: Path, sahte_ortam: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    paths = _paths(tmp_path)
    yedek = paths.backups / "gunluk.ksbak"
    yedek.write_bytes(MAGIC + b"\x00" * 64)
    args = main_mod.build_parser().parse_args(
        ["--geri-yukle", str(yedek), "--evet", "--parola", "Gizli-Parola-1"]
    )

    assert restore_mod._restore_flow(paths, args) == EXIT_OK
    assert sahte_ortam["cagri"][2] == "Gizli-Parola-1"


def test_bulunamayan_yedek_hata_koduyla_biter(
    tmp_path: Path, sahte_ortam: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    paths = _paths(tmp_path)
    args = main_mod.build_parser().parse_args(["--geri-yukle", "yok.ksbak", "--evet"])

    kod = restore_mod._restore_flow(paths, args)

    assert kod == EXIT_RESTORE_FAILED
    cikti = capsys.readouterr().out
    assert "HATA" in cikti
    assert "bulunamadı" in cikti


def test_servis_hatasi_kullaniciya_mesajla_doner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = _paths(tmp_path)
    yedek = paths.backups / "gunluk.ksbak"
    yedek.write_bytes(SQLITE_MAGIC)
    monkeypatch.setattr(restore_mod, "prepare_django", lambda *a, **k: None)
    monkeypatch.setattr(
        restore_mod, "_load_service", lambda: _sahte_servis({}, hata="Yedek anahtarı yanlış.")
    )
    args = main_mod.build_parser().parse_args(["--geri-yukle", str(yedek), "--evet"])

    kod = restore_mod._restore_flow(paths, args)

    assert kod == EXIT_RESTORE_FAILED
    assert "Yedek anahtarı yanlış." in capsys.readouterr().out


def test_onay_reddinde_servis_cagrilmaz(
    tmp_path: Path,
    sahte_ortam: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _paths(tmp_path)
    yedek = paths.backups / "gunluk.ksbak"
    yedek.write_bytes(SQLITE_MAGIC)
    monkeypatch.setattr("builtins.input", lambda *args: "h")
    args = main_mod.build_parser().parse_args(["--geri-yukle", str(yedek)])

    kod = restore_mod._restore_flow(paths, args)

    assert kod == EXIT_OK
    assert "cagri" not in sahte_ortam
    assert "iptal" in capsys.readouterr().out


# ------------------------------------------------------------------ uçtan uca


@pytest.mark.slow
def test_geri_yukleme_kipi_gercek_akista_calisir(tmp_path: Path) -> None:
    """Gerçek zincir: kilit → prepare_django → çekirdek → dosya değişimi (pencere YOK)."""
    veri = tmp_path / "data"
    veri.mkdir(parents=True)
    yedek_dizini = tmp_path / "backups"
    yedek_dizini.mkdir()

    def sqlite_yaz(yol: Path, isaret: str) -> None:
        with closing(sqlite3.connect(yol)) as baglanti:
            baglanti.execute("CREATE TABLE kayit (deger TEXT)")
            baglanti.execute("INSERT INTO kayit VALUES (?)", (isaret,))
            baglanti.commit()

    sqlite_yaz(veri / "db.sqlite3", "eski-icerik")
    (veri / "db.sqlite3-wal").write_bytes(b"wal-kalintisi")
    (veri / "surum.json").write_text("{}", encoding="utf-8")
    yedek = yedek_dizini / "gunluk-2026-08-29.ksbak"
    sqlite_yaz(yedek, "yeni-icerik")

    sonuc = subprocess.run(  # noqa: S603 — sabit argümanlar, kabuk yok
        [
            sys.executable,
            "-m",
            "desktop.main",
            "--data-dir",
            str(tmp_path),
            "--geri-yukle",
            str(yedek),
            "--evet",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert sonuc.returncode == EXIT_OK, sonuc.stderr
    assert b"yeni-icerik" in (veri / "db.sqlite3").read_bytes()
    onceki = list(veri.glob("db-onceki-*.sqlite3"))
    assert len(onceki) == 1
    assert b"eski-icerik" in onceki[0].read_bytes()
    assert (onceki[0].with_name(onceki[0].name + "-wal")).is_file()
    assert not (veri / "db.sqlite3-wal").exists()
    assert not (veri / "surum.json").exists()
    # Yedeğin kendisine dokunulmaz.
    assert yedek.is_file()
