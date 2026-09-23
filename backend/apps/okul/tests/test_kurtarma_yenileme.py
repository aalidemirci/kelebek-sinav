"""Kurtarma anahtarını yenileme — görev devrinde eski kâğıt bu kurulumu artık açmaz.

`POST security/recovery-key/renew/ {password}`. Kanıtlanan maddeler:

* yanlış parola reddedilir (kademeli gecikme), hiçbir dosya değişmez; başka
  kurulumun güvenlik dosyasıyla (parolası bilinse bile) yenileme yapılamaz;
* yeni anahtar yanıtla BİR KEZ döner (`Cache-Control: no-store`); eski anahtar
  artık bu kurulumun kilidini açmaz, yeni anahtar açar;
* DEK DEĞİŞMEZ: kayıtlar yeniden şifrelenmez, parola ve yedek anahtarı aynen
  çalışır; önceki `guvenlik.json` `guvenlik-arsiv-<damga>.json` olarak saklanır;
* yedekler (arayüz ve kılavuzdaki DÜRÜST metnin kanıtı): yenilemeden ÖNCE
  alınmış yedek, güncel güvenlik dosyası yokken yalnız ESKİ anahtarla açılır; bu
  bilgisayarda (güncel dosya yerindeyken) yeni anahtarla da açılır. Arşiv dosyası
  da eski anahtarla açılır — yenileme ele geçmiş bir anahtara karşı tam koruma
  değildir;
* anahtar hiçbir günlüğe düşmez; kilitliyken ve güvenlik dosyası kayıpken 423.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from desktop.backup import daily_backup
from desktop.backup_crypto import config_path, embedded_recovery_metadata
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.okul.models import SchoolConfig, Student
from apps.okul.services import app_password, backup_restore
from shared import crypto

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("guvenlik_ortami")]

URL = "/api/v1/security/recovery-key/renew/"
PAROLA = "Deneme-Parola-1"
ANAHTAR_BICIMI = re.compile(r"^[A-Z2-7]{4}(-[A-Z2-7]{4}){7}$")


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _ogrenci() -> Student:
    ogrenci: Student = Student.objects.create(
        first_name="EMRE",
        last_name="YILMAZ",
        student_number="101",
        class_level=10,
        class_section="A",
    )
    return ogrenci


def _ham_ad(student_id: int) -> str:
    """ORM'i atlayarak sütunu olduğu gibi okur (şifreli alan kendini çözmesin)."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT first_name FROM okul_student WHERE id = %s", [student_id])
        return str(cursor.fetchone()[0])


def _arsivler(dizin: Path) -> list[Path]:
    return sorted(dizin.glob(f"{app_password.STATE_ARCHIVE_PREFIX}*.json"))


def _yenile(client: APIClient, parola: str = PAROLA) -> Any:
    return client.post(URL, {"password": parola}, format="json")


# ---------------------------------------------------------------------------
# Yenileme
# ---------------------------------------------------------------------------
def test_yeni_anahtar_bir_kez_doner_ve_onbellege_alinmaz(client: APIClient) -> None:
    eski = app_password.enable(password=PAROLA)

    resp = _yenile(client)

    assert resp.status_code == 200
    assert resp["Cache-Control"] == "no-store"
    yeni = resp.json()["recovery_key"]
    assert ANAHTAR_BICIMI.match(yeni)
    assert yeni != eski
    assert resp.json()["password_set"] is True and resp.json()["locked"] is False
    # Sunucu anahtarı saklamaz: güvenlik dosyasında düz hâli yoktur.
    assert yeni not in app_password.state_path().read_text(encoding="utf-8")


def test_eski_anahtar_artik_acmaz_yeni_anahtar_acar() -> None:
    eski = app_password.enable(password=PAROLA)
    yeni = app_password.renew_recovery_key(password=PAROLA)
    app_password.lock()

    with pytest.raises(app_password.AppPasswordError, match="Kurtarma anahtarı hatalı"):
        app_password.unlock_with_recovery(recovery_key=eski, new_password="Yeni-Parola-2")
    assert app_password.is_locked() is True

    app_password.unlock_with_recovery(recovery_key=yeni, new_password="Yeni-Parola-2")
    assert app_password.is_locked() is False


def test_parola_degistirmek_kurtarma_anahtarini_yenilemez() -> None:
    """Görev devrinde parola değişimi TEK BAŞINA yetmez — yenileme ayrı işlemdir."""
    eski = app_password.enable(password=PAROLA)
    app_password.change_password(current_password=PAROLA, new_password="Yeni-Parola-2")
    app_password.lock()

    app_password.unlock_with_recovery(recovery_key=eski, new_password="Ucuncu-Parola-3")
    assert app_password.is_locked() is False


def test_dek_degismez_kayitlar_yeniden_sifrelenmez() -> None:
    ogrenci = _ogrenci()
    app_password.enable(password=PAROLA)
    token = _ham_ad(ogrenci.pk)
    parmak_izi = SchoolConfig.load().app_password_hash
    yedek_anahtari = config_path(app_password.state_path().parent).read_bytes()

    app_password.renew_recovery_key(password=PAROLA)

    assert _ham_ad(ogrenci.pk) == token
    assert SchoolConfig.load().app_password_hash == parmak_izi
    assert config_path(app_password.state_path().parent).read_bytes() == yedek_anahtari
    app_password.lock()
    app_password.unlock(password=PAROLA)  # parola aynen çalışır
    assert Student.objects.get(pk=ogrenci.pk).first_name == "EMRE"


def test_yalniz_kurtarma_bolumu_degisir() -> None:
    app_password.enable(password=PAROLA)
    onceki = app_password.read_state()
    assert onceki is not None

    app_password.renew_recovery_key(password=PAROLA)

    sonraki = app_password.read_state()
    assert sonraki is not None
    for alan in ("parola", "kdf", "gecis", "surum", "olusturma"):
        assert sonraki[alan] == onceki[alan], alan
    assert sonraki["kurtarma"]["salt"] != onceki["kurtarma"]["salt"]
    assert sonraki["kurtarma"]["sarmal"] != onceki["kurtarma"]["sarmal"]


def test_onceki_dosya_arsive_kopyalanir_ve_eski_anahtarla_acilir(
    guvenlik_ortami: Path,
) -> None:
    """Dürüst sınır: arşiv eski anahtarla DEK'i verir (DEK değişmediği için)."""
    eski = app_password.enable(password=PAROLA)
    onceki_baytlar = app_password.state_path().read_bytes()

    app_password.renew_recovery_key(password=PAROLA)

    arsivler = _arsivler(guvenlik_ortami)
    assert [a.read_bytes() for a in arsivler] == [onceki_baytlar]
    assert app_password.state_path().is_file()
    arsiv_durumu = json.loads(arsivler[0].read_text(encoding="utf-8"))
    dek = app_password._unwrap_with_recovery(arsiv_durumu, eski)
    assert crypto.key_fingerprint(dek) == crypto.active_fingerprint()


def test_ayni_saniyede_iki_yenileme_birbirinin_arsivini_ezmez(guvenlik_ortami: Path) -> None:
    app_password.enable(password=PAROLA)
    sabit = timezone.make_aware(datetime(2026, 9, 24, 10, 0, 0))
    with mock.patch("apps.okul.services.app_password.timezone.localtime", return_value=sabit):
        app_password.renew_recovery_key(password=PAROLA)
        app_password.renew_recovery_key(password=PAROLA)

    adlar = [a.name for a in _arsivler(guvenlik_ortami)]
    assert adlar == [
        "guvenlik-arsiv-2026-09-24-100000-2.json",
        "guvenlik-arsiv-2026-09-24-100000.json",
    ]


def test_yanlis_parola_reddedilir_hicbir_dosya_degismez(
    client: APIClient, guvenlik_ortami: Path
) -> None:
    app_password.enable(password=PAROLA)
    onceki = app_password.state_path().read_bytes()

    resp = _yenile(client, "yanlis-parola")

    assert resp.status_code == 400
    assert resp.json()["message"] == "Parola hatalı."
    assert app_password.state_path().read_bytes() == onceki
    assert _arsivler(guvenlik_ortami) == []


def test_baska_kurulumun_dosyasiyla_yenilenemez() -> None:
    """Parolası bilinen yabancı bir guvenlik.json konsa bile bellekteki anahtar tutmaz."""
    app_password.enable(password=PAROLA)
    yabanci = app_password._build_state(
        crypto.new_data_key(),
        password=PAROLA,
        recovery_key=app_password.generate_recovery_key(),
    )
    app_password._write_state(yabanci)

    with pytest.raises(app_password.AppPasswordError, match="Parola hatalı"):
        app_password.renew_recovery_key(password=PAROLA)


def test_kilitliyken_kilit_kapisi_keser(client: APIClient) -> None:
    app_password.enable(password=PAROLA)
    app_password.lock()

    resp = _yenile(client)

    assert resp.status_code == 423
    assert resp.json()["code"] == "locked"


def test_servis_kilitliyken_yenilemez() -> None:
    app_password.enable(password=PAROLA)
    app_password.lock()

    with pytest.raises(app_password.AppPasswordError, match="kilitli"):
        app_password.renew_recovery_key(password=PAROLA)


def test_guvenlik_dosyasi_kayipken_kapali(client: APIClient) -> None:
    app_password.enable(password=PAROLA)
    app_password.state_path().unlink()

    resp = _yenile(client)

    assert resp.status_code == 423
    assert resp.json()["code"] == "guvenlik_dosyasi_kayip"


def test_parolasiz_kipte_calismaz(client: APIClient) -> None:
    resp = _yenile(client)

    assert resp.status_code == 400
    assert "kurulu değil" in resp.json()["message"]


def test_anahtar_hicbir_gunluge_dusmez(client: APIClient, caplog: pytest.LogCaptureFixture) -> None:
    app_password.enable(password=PAROLA)
    with caplog.at_level(logging.DEBUG):
        yeni = _yenile(client).json()["recovery_key"]
        _yenile(client, "yanlis-parola")  # 4xx yanıtı da günlüğe yazılır

    sade = app_password.normalize_recovery_key(yeni)
    assert yeni not in caplog.text
    assert sade not in caplog.text
    assert PAROLA not in caplog.text
    assert "yenilendi" in caplog.text  # işlemin kendisi kayda geçer


# ---------------------------------------------------------------------------
# Yedekler — dürüst metnin kanıtı
# ---------------------------------------------------------------------------
class TestYedekler:
    """Günlük yedek, alındığı anın `guvenlik.json`'unu başlığında taşır."""

    @pytest.fixture
    def db(self, guvenlik_ortami: Path) -> Path:
        # `desktop.backup` veri dizinini kaynak dosyanın klasöründen okur.
        yol = guvenlik_ortami / "db.sqlite3"
        with sqlite3.connect(yol) as baglanti:
            baglanti.execute("CREATE TABLE deneme (deger TEXT)")
            baglanti.execute("INSERT INTO deneme VALUES ('uydurma')")
        return yol

    def _yedek(self, db: Path, tmp_path: Path, gun: int) -> Path:
        yedek = daily_backup(db, tmp_path / "yedekler", today=date(2026, 9, gun))
        assert yedek is not None
        return Path(yedek)

    def test_yenilemeden_sonra_alinan_yedek_yeni_basligi_tasir(
        self, db: Path, tmp_path: Path
    ) -> None:
        app_password.enable(password=PAROLA)
        app_password.renew_recovery_key(password=PAROLA)

        yedek = self._yedek(db, tmp_path, 2)

        baslik = json.loads(embedded_recovery_metadata(yedek.read_bytes()))
        guncel = app_password.read_state()
        assert guncel is not None
        assert baslik["kurtarma"] == guncel["kurtarma"]

    def test_eski_yedek_guvenlik_dosyasi_yokken_yalniz_eski_anahtarla_acilir(
        self, db: Path, tmp_path: Path
    ) -> None:
        """Başka bilgisayar ya da kayıp dosya: yalnız gömülü (eski) başlık kalır."""
        eski = app_password.enable(password=PAROLA)
        yedek = self._yedek(db, tmp_path, 1)
        yeni = app_password.renew_recovery_key(password=PAROLA)
        app_password.state_path().unlink()
        hedef = tmp_path / "hedef" / "db.sqlite3"

        with pytest.raises(backup_restore.BackupRestoreError, match="açılamadı"):
            backup_restore.restore_database(yedek, hedef, recovery_key=yeni)
        sonuc = backup_restore.restore_database(yedek, hedef, recovery_key=eski)

        assert sonuc.state_written is True

    def test_eski_yedek_bu_bilgisayarda_yeni_anahtarla_da_acilir(
        self, db: Path, tmp_path: Path
    ) -> None:
        """Güncel dosya yerindeyken önce o denenir; DEK aynı olduğu için yedek açılır."""
        app_password.enable(password=PAROLA)
        yedek = self._yedek(db, tmp_path, 1)
        yeni = app_password.renew_recovery_key(password=PAROLA)

        sonuc = backup_restore.restore_database(
            yedek, tmp_path / "hedef" / "db.sqlite3", recovery_key=yeni
        )

        assert sonuc.state_written is False  # güncel dosya dokunulmadan kaldı
