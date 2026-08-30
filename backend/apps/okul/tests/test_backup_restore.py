"""Yedekten geri yükleme çekirdeği (services.backup_restore) testleri.

Senaryolar K9 iki kipi izler: parolasız kipte düz `.ksbak`, parolalı kipte
X25519+AES-GCM kapsayıcı. Çekirdeğin sözleşmesi gereği testler ORM'e HİÇ
dokunmaz — geri yükleme bozuk bir veritabanıyla da çalışabilmelidir
(`django_db` işareti bilinçli olarak yoktur).

Argon2id kasten yavaştır; `test_app_password` ile aynı gerekçeyle
`crypto.DEFAULT_KDF` ucuz profile indirilir (yalnız maliyet parametresi,
biçim üretimdekiyle birebir aynı).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from io import StringIO
from pathlib import Path
from typing import Any, cast

import pytest
from desktop.backup_crypto import encrypt_bytes, ensure_public_config, private_key_from_data_key
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.okul.services import app_password, backup_restore
from shared import crypto

PAROLA = "Deneme-Parola-1"


@pytest.fixture(autouse=True)
def veri_dizini(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Her test kendi veri dizini + ucuz KDF profiliyle koşar."""
    veri = tmp_path / "veri"
    veri.mkdir()
    monkeypatch.setenv(app_password.ENV_SECURITY_DIR, str(veri))
    monkeypatch.setenv(app_password.ENV_BACKUP_DIR, str(tmp_path / "yedekler"))
    monkeypatch.setattr(
        crypto, "DEFAULT_KDF", crypto.KdfParams(time_cost=1, memory_cost=8, parallelism=1)
    )
    monkeypatch.setattr(app_password, "FAILURE_DELAYS", (0.0,))
    return veri


def _sqlite_baytlari(dizin: Path, isaret: str) -> bytes:
    """`isaret` değerini taşıyan gerçek bir SQLite dosyasının baytları."""
    yol = dizin / f"kaynak-{isaret}.sqlite3"
    with closing(sqlite3.connect(yol)) as baglanti:
        baglanti.execute("CREATE TABLE kayit (deger TEXT)")
        baglanti.execute("INSERT INTO kayit VALUES (?)", (isaret,))
        baglanti.commit()
    return yol.read_bytes()


def _dek_ile_durum(parola: str, kurtarma: str | None = None) -> tuple[bytes, dict[str, Any]]:
    dek = crypto.new_data_key()
    durum = app_password._build_state(
        dek, password=parola, recovery_key=kurtarma or app_password.generate_recovery_key()
    )
    durum["gecis"] = app_password.TRANSITION_DONE
    return dek, durum


def _sifreli_kapsayici(icerik: bytes, dek: bytes, durum: dict[str, Any] | None) -> bytes:
    baslik = json.dumps(durum, ensure_ascii=False).encode("utf-8") if durum is not None else b""
    acik = private_key_from_data_key(dek).public_key()
    # desktop.* backend mypy koşusunda çözümlenmez (Any) → dönüş tipi sabitlenir.
    return cast("bytes", encrypt_bytes(icerik, acik, recovery_header=baslik))


# ---------------------------------------------------------------------------
# Düz kip (parolasız — K9)
# ---------------------------------------------------------------------------
def test_duz_yedek_geri_yuklenir(tmp_path: Path, veri_dizini: Path) -> None:
    db = veri_dizini / "db.sqlite3"
    db.write_bytes(_sqlite_baytlari(tmp_path, "eski"))
    (veri_dizini / "db.sqlite3-wal").write_bytes(b"wal-kalintisi")
    (veri_dizini / "db.sqlite3-shm").write_bytes(b"shm-kalintisi")
    (veri_dizini / "surum.json").write_text("{}", encoding="utf-8")
    yeni = _sqlite_baytlari(tmp_path, "yeni")
    yedek = tmp_path / "gunluk-2026-08-01.ksbak"
    yedek.write_bytes(yeni)

    sonuc = backup_restore.restore_database(yedek, db)

    assert db.read_bytes() == yeni
    assert sonuc.encrypted is False
    assert sonuc.state_written is False
    # Eski veritabanı SİLİNMEZ, kenara alınır; WAL/SHM de onun yanına taşınır.
    assert sonuc.old_db_path is not None
    assert sonuc.old_db_path.name.startswith("db-onceki-")
    assert b"eski" in sonuc.old_db_path.read_bytes()
    yan_wal = sonuc.old_db_path.with_name(sonuc.old_db_path.name + "-wal")
    assert yan_wal.read_bytes() == b"wal-kalintisi"
    assert not (veri_dizini / "db.sqlite3-wal").exists()
    assert not (veri_dizini / "db.sqlite3-shm").exists()
    # Damga artık geri yüklenen veriyi tarif etmiyor → silinir (eksik damga engel değil).
    assert not (veri_dizini / "surum.json").exists()


def test_hedef_yokken_calisir_ve_basibos_wal_temizlenir(tmp_path: Path, veri_dizini: Path) -> None:
    db = veri_dizini / "db.sqlite3"
    (veri_dizini / "db.sqlite3-wal").write_bytes(b"basibos")
    yeni = _sqlite_baytlari(tmp_path, "yeni")
    yedek = tmp_path / "gunluk.ksbak"
    yedek.write_bytes(yeni)

    sonuc = backup_restore.restore_database(yedek, db)

    assert db.read_bytes() == yeni
    assert sonuc.old_db_path is None
    assert not (veri_dizini / "db.sqlite3-wal").exists()


def test_gecersiz_dosya_reddedilir(tmp_path: Path, veri_dizini: Path) -> None:
    yedek = tmp_path / "bozuk.ksbak"
    yedek.write_bytes(b"HERHANGI BIR ICERIK")

    with pytest.raises(backup_restore.BackupRestoreError, match="geçerli bir"):
        backup_restore.restore_database(yedek, veri_dizini / "db.sqlite3")


# ---------------------------------------------------------------------------
# Şifreli kip
# ---------------------------------------------------------------------------
def test_sifreli_yedek_parola_ile_acilir_ve_guvenlik_dosyasi_yazilir(
    tmp_path: Path, veri_dizini: Path
) -> None:
    """guvenlik.json kayıp senaryosu: gömülü başlık hem DEK'i verir hem dosyayı onarır."""
    dek, durum = _dek_ile_durum(PAROLA)
    icerik = _sqlite_baytlari(tmp_path, "gizli")
    yedek = tmp_path / "gunluk.ksbak"
    yedek.write_bytes(_sifreli_kapsayici(icerik, dek, durum))
    db = veri_dizini / "db.sqlite3"

    sonuc = backup_restore.restore_database(yedek, db, password=PAROLA)

    assert db.read_bytes() == icerik
    assert sonuc.encrypted is True
    assert sonuc.state_written is True
    yazilan = json.loads((veri_dizini / "guvenlik.json").read_text(encoding="utf-8"))
    assert yazilan["parola"] == durum["parola"]


def test_sifreli_yedek_kurtarma_anahtari_ile_acilir(tmp_path: Path, veri_dizini: Path) -> None:
    kurtarma = app_password.generate_recovery_key()
    dek, durum = _dek_ile_durum(PAROLA, kurtarma)
    icerik = _sqlite_baytlari(tmp_path, "gizli")
    yedek = tmp_path / "gunluk.ksbak"
    yedek.write_bytes(_sifreli_kapsayici(icerik, dek, durum))
    db = veri_dizini / "db.sqlite3"

    sonuc = backup_restore.restore_database(yedek, db, recovery_key=kurtarma)

    assert db.read_bytes() == icerik
    assert sonuc.state_written is True


def test_yanlis_parola_hedefe_dokunmaz(tmp_path: Path, veri_dizini: Path) -> None:
    dek, durum = _dek_ile_durum(PAROLA)
    orijinal = _sqlite_baytlari(tmp_path, "orijinal")
    db = veri_dizini / "db.sqlite3"
    db.write_bytes(orijinal)
    yedek = tmp_path / "gunluk.ksbak"
    yedek.write_bytes(_sifreli_kapsayici(_sqlite_baytlari(tmp_path, "gizli"), dek, durum))

    with pytest.raises(backup_restore.BackupRestoreError, match="açılamadı"):
        backup_restore.restore_database(yedek, db, password="Yanlis-Parola-9")

    assert db.read_bytes() == orijinal
    assert not list(veri_dizini.glob("db-onceki-*"))


def test_sifreli_yedek_sir_olmadan_acilmaz(tmp_path: Path, veri_dizini: Path) -> None:
    dek, durum = _dek_ile_durum(PAROLA)
    yedek = tmp_path / "gunluk.ksbak"
    yedek.write_bytes(_sifreli_kapsayici(_sqlite_baytlari(tmp_path, "gizli"), dek, durum))

    with pytest.raises(backup_restore.BackupRestoreError, match="şifreli"):
        backup_restore.restore_database(yedek, veri_dizini / "db.sqlite3")


def test_cozulen_icerik_sqlite_degilse_reddedilir(tmp_path: Path, veri_dizini: Path) -> None:
    dek, durum = _dek_ile_durum(PAROLA)
    yedek = tmp_path / "gunluk.ksbak"
    yedek.write_bytes(_sifreli_kapsayici(b"duz metin, veritabani degil", dek, durum))
    db = veri_dizini / "db.sqlite3"

    with pytest.raises(backup_restore.BackupRestoreError, match="SQLite"):
        backup_restore.restore_database(yedek, db, password=PAROLA)

    assert not db.exists()


def test_parola_degisse_de_guncel_dosya_ile_acilir(tmp_path: Path, veri_dizini: Path) -> None:
    """Yedek eski parolayla alınmış; kullanıcı YENİ parolasını bilir.

    DEK parola değişiminde değişmediği için güncel guvenlik.json yeni parolayla
    aynı DEK'i verir → yedek açılır ve güncel dosyaya DOKUNULMAZ (en yeni
    sarmalı taşıyan odur)."""
    dek = crypto.new_data_key()
    kurtarma = app_password.generate_recovery_key()
    eski_durum = app_password._build_state(dek, password="Eski-Parola-1", recovery_key=kurtarma)
    eski_durum["gecis"] = app_password.TRANSITION_DONE
    yeni_durum = app_password._build_state(dek, password="Yeni-Parola-2", recovery_key=kurtarma)
    yeni_durum["gecis"] = app_password.TRANSITION_DONE
    (veri_dizini / "guvenlik.json").write_text(
        json.dumps(yeni_durum, ensure_ascii=False), encoding="utf-8"
    )
    icerik = _sqlite_baytlari(tmp_path, "gizli")
    yedek = tmp_path / "eski-donem.ksbak"
    yedek.write_bytes(_sifreli_kapsayici(icerik, dek, eski_durum))
    db = veri_dizini / "db.sqlite3"

    sonuc = backup_restore.restore_database(yedek, db, password="Yeni-Parola-2")

    assert db.read_bytes() == icerik
    assert sonuc.state_written is False
    guncel = json.loads((veri_dizini / "guvenlik.json").read_text(encoding="utf-8"))
    assert guncel["parola"] == yeni_durum["parola"]


def test_yabanci_guvenlik_dosyasi_arsivlenip_gomulu_baslik_yazilir(
    tmp_path: Path, veri_dizini: Path
) -> None:
    """Veri klasöründe BAŞKA kuruluma ait dosya: sarmal aynı parolayla açılır ama
    DEK yanlıştır; AES-GCM reddeder → gömülü başlık kazanır, yabancı dosya
    silinmeden arşivlenir."""
    _yabanci_dek, yabanci_durum = _dek_ile_durum(PAROLA)
    (veri_dizini / "guvenlik.json").write_text(
        json.dumps(yabanci_durum, ensure_ascii=False), encoding="utf-8"
    )
    dek, durum = _dek_ile_durum(PAROLA)
    icerik = _sqlite_baytlari(tmp_path, "gizli")
    yedek = tmp_path / "gunluk.ksbak"
    yedek.write_bytes(_sifreli_kapsayici(icerik, dek, durum))
    db = veri_dizini / "db.sqlite3"

    sonuc = backup_restore.restore_database(yedek, db, password=PAROLA)

    assert db.read_bytes() == icerik
    assert sonuc.state_written is True
    arsivler = list(veri_dizini.glob("guvenlik-arsiv-*.json"))
    assert len(arsivler) == 1
    arsiv = json.loads(arsivler[0].read_text(encoding="utf-8"))
    assert arsiv["parola"] == yabanci_durum["parola"]
    guncel = json.loads((veri_dizini / "guvenlik.json").read_text(encoding="utf-8"))
    assert guncel["parola"] == durum["parola"]


def test_capraz_dek_geri_yukleme_yedekleme_json_u_da_esitler(
    tmp_path: Path, veri_dizini: Path
) -> None:
    """Birleşme incelemesi bulgusu: yalnız guvenlik.json onarılıp kardeş
    yedekleme.json bayat kalsaydı kilit açma "anahtar eşleşmiyor" hatasına
    düşer, açılıştaki günlük yedek de İÇERİĞİ eski anahtarla mühürleyip
    başlığa yeni durumu gömerdi — o yedek bir daha açılamazdı."""
    from desktop.backup_crypto import load_public_key, public_key_bytes

    yerli_dek, yerli_durum = _dek_ile_durum(PAROLA)
    (veri_dizini / "guvenlik.json").write_text(
        json.dumps(yerli_durum, ensure_ascii=False), encoding="utf-8"
    )
    ensure_public_config(veri_dizini, yerli_dek, replace=True)  # bayat kalacak aday
    dek, durum = _dek_ile_durum(PAROLA)
    yedek = tmp_path / "gunluk.ksbak"
    yedek.write_bytes(_sifreli_kapsayici(_sqlite_baytlari(tmp_path, "gizli"), dek, durum))

    backup_restore.restore_database(yedek, veri_dizini / "db.sqlite3", password=PAROLA)

    from cryptography.hazmat.primitives import serialization

    guncel_acik = load_public_key(veri_dizini).public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    assert guncel_acik == public_key_bytes(dek)  # üçlü (db, guvenlik, yedekleme) tutarlı


def test_bassiz_yedek_guncel_guvenlik_dosyasiyla_acilir(tmp_path: Path, veri_dizini: Path) -> None:
    dek, durum = _dek_ile_durum(PAROLA)
    (veri_dizini / "guvenlik.json").write_text(
        json.dumps(durum, ensure_ascii=False), encoding="utf-8"
    )
    icerik = _sqlite_baytlari(tmp_path, "gizli")
    yedek = tmp_path / "bassiz.ksbak"
    yedek.write_bytes(_sifreli_kapsayici(icerik, dek, None))
    db = veri_dizini / "db.sqlite3"

    sonuc = backup_restore.restore_database(yedek, db, password=PAROLA)

    assert db.read_bytes() == icerik
    assert sonuc.state_written is False


def test_bassiz_yedek_guvenlik_dosyasi_yokken_yol_gosterir(
    tmp_path: Path, veri_dizini: Path
) -> None:
    dek, _durum = _dek_ile_durum(PAROLA)
    yedek = tmp_path / "bassiz.ksbak"
    yedek.write_bytes(_sifreli_kapsayici(_sqlite_baytlari(tmp_path, "gizli"), dek, None))

    with pytest.raises(backup_restore.BackupRestoreError, match="guvenlik.json"):
        backup_restore.restore_database(yedek, veri_dizini / "db.sqlite3", password=PAROLA)


# ---------------------------------------------------------------------------
# manage.py restore_backup komutu
# ---------------------------------------------------------------------------
def test_komut_duz_yedegi_geri_yukler(
    tmp_path: Path, veri_dizini: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = veri_dizini / "db.sqlite3"
    monkeypatch.setitem(settings.DATABASES["default"], "NAME", str(db))
    yeni = _sqlite_baytlari(tmp_path, "komut")
    yedek = tmp_path / "gunluk.ksbak"
    yedek.write_bytes(yeni)
    cikti = StringIO()

    call_command("restore_backup", str(yedek), "--yes", stdout=cikti)

    assert db.read_bytes() == yeni
    assert "tamamlandı" in cikti.getvalue()


def test_komut_sifreli_yedegi_parola_bayragiyla_acar(
    tmp_path: Path, veri_dizini: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = veri_dizini / "db.sqlite3"
    monkeypatch.setitem(settings.DATABASES["default"], "NAME", str(db))
    dek, durum = _dek_ile_durum(PAROLA)
    icerik = _sqlite_baytlari(tmp_path, "gizli")
    yedek = tmp_path / "gunluk.ksbak"
    yedek.write_bytes(_sifreli_kapsayici(icerik, dek, durum))
    cikti = StringIO()

    call_command("restore_backup", str(yedek), "--yes", "--password", PAROLA, stdout=cikti)

    assert db.read_bytes() == icerik
    assert "guvenlik.json" in cikti.getvalue()


def test_komut_onay_reddinde_dokunmaz(
    tmp_path: Path, veri_dizini: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = veri_dizini / "db.sqlite3"
    orijinal = _sqlite_baytlari(tmp_path, "orijinal")
    db.write_bytes(orijinal)
    monkeypatch.setitem(settings.DATABASES["default"], "NAME", str(db))
    monkeypatch.setattr("builtins.input", lambda *args: "h")
    yedek = tmp_path / "gunluk.ksbak"
    yedek.write_bytes(_sqlite_baytlari(tmp_path, "yeni"))
    cikti = StringIO()

    call_command("restore_backup", str(yedek), stdout=cikti)

    assert "iptal" in cikti.getvalue()
    assert db.read_bytes() == orijinal


def test_komut_bellek_ici_veritabanini_reddeder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(settings.DATABASES["default"], "NAME", ":memory:")
    yedek = tmp_path / "gunluk.ksbak"
    yedek.write_bytes(_sqlite_baytlari(tmp_path, "yeni"))

    with pytest.raises(CommandError, match="dosya tabanlı değil"):
        call_command("restore_backup", str(yedek), "--yes")


def test_komut_okunamayan_dosyada_turkce_hata_verir(tmp_path: Path) -> None:
    with pytest.raises(CommandError, match="okunamadı"):
        call_command("restore_backup", str(tmp_path / "yok.ksbak"), "--yes")
