"""Bütünlük denetimi + sürüm damgası testleri (tasarım §5.3)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from desktop.errors import DatabaseCorruptError, SchemaTooNewError
from desktop.integrity import check_database_integrity
from desktop.version import (
    ensure_stamp_compatible,
    get_app_version,
    read_version_stamp,
    version_key,
    write_version_stamp,
)


def _db_olustur(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        conn.executemany("INSERT INTO t (v) VALUES (?)", [(f"satır {i}",) for i in range(200)])
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------- bütünlük


def test_saglam_veritabani_gecer(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite3"
    _db_olustur(db)

    check_database_integrity(db)  # hata yükseltmemeli


def test_veritabani_yoksa_gecer(tmp_path: Path) -> None:
    """İlk açılış: dosya henüz yok, migrate onu üretecek."""
    check_database_integrity(tmp_path / "yok.sqlite3")


def test_bozuk_dosya_turkce_hata_ile_reddedilir(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite3"
    _db_olustur(db)
    with db.open("r+b") as f:  # SQLite başlığını boz → "file is not a database"
        f.seek(0)
        f.write(b"BOZUKBOZUK")

    with pytest.raises(DatabaseCorruptError) as hata:
        check_database_integrity(db, backup_dir=tmp_path / "backups")

    assert "bozuk" in str(hata.value).lower()
    assert "backups" in hata.value.hint


def test_bozuk_sayfa_integrity_check_ile_yakalanir(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite3"
    _db_olustur(db)
    boyut = db.stat().st_size
    with db.open("r+b") as f:  # ikinci sayfanın ortasını çöple doldur
        f.seek(min(4096 + 64, boyut - 64))
        f.write(b"\xde\xad\xbe\xef" * 16)

    with pytest.raises(DatabaseCorruptError):
        check_database_integrity(db)


def test_bos_dosya_bozuk_sayilmaz(tmp_path: Path) -> None:
    """0 baytlık dosya SQLite'ta geçerli boş veritabanıdır (migrate dolduracak)."""
    db = tmp_path / "db.sqlite3"
    db.write_bytes(b"")

    check_database_integrity(db)


# ------------------------------------------------------------------ sürüm damgası


@pytest.mark.parametrize(
    ("dusuk", "yuksek"),
    [
        ("0.1.0", "0.2.0"),
        ("0.9.0", "1.0.0"),
        ("1.0.0-dev", "1.0.0"),  # ön-sürüm, kesin sürümden ÖNCE gelir
        ("1.0.0", "1.0.1"),
        ("1.2.0", "1.10.0"),  # sayısal karşılaştırma (metin değil)
    ],
)
def test_surum_siralamasi(dusuk: str, yuksek: str) -> None:
    assert version_key(dusuk) < version_key(yuksek)


def test_damga_yazilir_ve_okunur(tmp_path: Path) -> None:
    yol = tmp_path / "surum.json"

    write_version_stamp(yol, "0.3.0")
    damga = read_version_stamp(yol)

    assert damga is not None
    assert damga.app_version == "0.3.0"
    assert damga.written_at
    assert json.loads(yol.read_text(encoding="utf-8"))["app_version"] == "0.3.0"


def test_eski_program_yeni_semali_veriyi_acmaz(tmp_path: Path) -> None:
    yol = tmp_path / "surum.json"
    write_version_stamp(yol, "0.9.0")

    with pytest.raises(SchemaTooNewError) as hata:
        ensure_stamp_compatible(yol, "0.5.0")

    assert "0.9.0" in str(hata.value)
    assert "güncel" in hata.value.hint.lower()


def test_ayni_veya_eski_damga_gecer(tmp_path: Path) -> None:
    yol = tmp_path / "surum.json"
    write_version_stamp(yol, "0.5.0")

    ensure_stamp_compatible(yol, "0.5.0")
    ensure_stamp_compatible(yol, "0.6.0")


def test_damga_yoksa_gecer(tmp_path: Path) -> None:
    """İlk açılış veya elle geri yüklenmiş yedek — damga eksikliği engel değildir."""
    ensure_stamp_compatible(tmp_path / "surum.json", "0.5.0")


def test_bozuk_damga_programi_kilitlemez(tmp_path: Path) -> None:
    yol = tmp_path / "surum.json"
    yol.write_text("{bozuk", encoding="utf-8")

    ensure_stamp_compatible(yol, "0.5.0")
    assert read_version_stamp(yol) is None


def test_damga_yazimi_dizini_olusturur(tmp_path: Path) -> None:
    yol = tmp_path / "yeni" / "surum.json"

    write_version_stamp(yol, "0.1.0")

    assert yol.is_file()


def test_uygulama_surumu_env_ile_gecersiz_kilinir() -> None:
    assert get_app_version(environ={"KS_APP_VERSION": "9.9.9"}) == "9.9.9"


def test_uygulama_surumu_version_dosyasindan_okunur() -> None:
    surum = get_app_version(environ={})

    assert surum
    assert surum[0].isdigit()
