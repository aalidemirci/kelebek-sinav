"""Şifreli alan kapısı — parola kuruluyken anahtarsız düz yazım YOK, parolasız kip korunur.

`shared.crypto.EncryptedTextField.get_prep_value` anahtar bellekte değilken
değeri düz yazar; bu yalnız PAROLASIZ kipte meşrudur. Parola kuruluyken
(güvenlik dosyası var ya da DB'de anahtar parmak izi dolu) anahtar yoksa yazım
`KeyMissingError` ile durur. Kanıtlar ORM'e güvenmez: sütun ham SQL ile okunur
(şifreli alan kendini çözer, test yalan söylerdi).

İkinci konu, eski düz metin KALINTISIDIR: parola kurulurken satırlar yerinde
yeniden yazılır, SQLite eski sürümü boş sayfalarda ve WAL'da bırakabilir.
Bağlantılar `secure_delete=ON` açılır ve geçiş sonunda WAL sıfırlanıp VACUUM
koşulur (`app_password.scrub_free_pages`); gerçek bir SQLite dosyasında sınanır.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any, cast
from unittest import mock

import pytest
from django.db import DatabaseError, connection, transaction
from rest_framework.test import APIClient

from apps.okul.models import Student
from apps.okul.services import app_password
from shared import crypto

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("guvenlik_ortami")]

PAROLA = "Deneme-Parola-1"
AD = "EMRE CAN"


def _ogrenci(numara: str = "101", ad: str = AD) -> Student:
    return cast(
        "Student",
        Student.objects.create(
            first_name=ad,
            last_name="YILMAZ",
            student_number=numara,
            class_level=10,
            class_section="A",
        ),
    )


def _ham_ad(student_id: int) -> str:
    with connection.cursor() as cursor:
        cursor.execute("SELECT first_name FROM okul_student WHERE id = %s", [student_id])
        satir = cursor.fetchone()
    return str(satir[0])


def _ogrenci_sayisi() -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM okul_student")
        return int(cursor.fetchone()[0])


# ---------------------------------------------------------------------------
# Kapı: parolalı + anahtarsız = yazım yok
# ---------------------------------------------------------------------------
class TestAnahtarsizYazim:
    def test_yoklayici_uygulama_acilisinda_baglanir(self) -> None:
        assert crypto._key_required_probe is app_password.is_password_set

    def test_kilit_acikken_sutun_token_olarak_yazilir(self) -> None:
        app_password.enable(password=PAROLA)
        ogrenci = _ogrenci()
        assert _ham_ad(ogrenci.pk).startswith("gAAAA")
        assert AD not in _ham_ad(ogrenci.pk)

    def test_kilitliyken_yeni_kayit_yazilamaz(self) -> None:
        app_password.enable(password=PAROLA)
        app_password.lock()
        onceki = _ogrenci_sayisi()

        # Savepoint: hata test işlemini bozmasın, ardından sayım yapılabilsin.
        with pytest.raises(crypto.KeyMissingError), transaction.atomic():
            _ogrenci(numara="102")

        assert _ogrenci_sayisi() == onceki

    def test_kilitliyken_mevcut_kayit_duz_metinle_ezilemez(self) -> None:
        ogrenci = _ogrenci()
        app_password.enable(password=PAROLA)
        token = _ham_ad(ogrenci.pk)
        app_password.lock()

        kilitli = Student.objects.get(pk=ogrenci.pk)
        kilitli.first_name = "DEGISTI"
        with pytest.raises(crypto.KeyMissingError), transaction.atomic():
            kilitli.save()

        assert _ham_ad(ogrenci.pk) == token

    def test_guvenlik_dosyasi_kayipken_de_yazilamaz(self) -> None:
        """Dosya silinse bile parmak izi doludur: kurulum parolalıdır, düz yazım yok."""
        app_password.enable(password=PAROLA)
        app_password.lock()
        app_password.state_path().unlink()

        with pytest.raises(crypto.KeyMissingError), transaction.atomic():
            _ogrenci(numara="102")

    def test_sifreli_olmayan_alanlar_kilitliyken_de_yazilir(self) -> None:
        ogrenci = _ogrenci()
        app_password.enable(password=PAROLA)
        app_password.lock()

        kilitli = Student.objects.get(pk=ogrenci.pk)
        kilitli.class_section = "B"
        kilitli.save(update_fields=["class_section"])

        assert Student.objects.get(pk=ogrenci.pk).class_section == "B"

    def test_bos_deger_kilitliyken_de_yazilir(self) -> None:
        """Boş dize "veri yok" hâlidir, şifrelenmez — kapı onu durdurmaz."""
        ogrenci = _ogrenci()
        app_password.enable(password=PAROLA)
        app_password.lock()

        kilitli = Student.objects.get(pk=ogrenci.pk)
        kilitli.gender = ""
        kilitli.save(update_fields=["gender"])


# ---------------------------------------------------------------------------
# Parolasız kip korunur
# ---------------------------------------------------------------------------
class TestParolasizKip:
    def test_parolasiz_kipte_duz_yazim_surer(self) -> None:
        ogrenci = _ogrenci()
        assert _ham_ad(ogrenci.pk) == AD

    def test_parola_kaldirildiktan_sonra_duz_yazim_surer(self) -> None:
        app_password.enable(password=PAROLA)
        app_password.disable(password=PAROLA)

        ogrenci = _ogrenci(numara="102", ad="ZEYNEP")

        assert _ham_ad(ogrenci.pk) == "ZEYNEP"

    def test_parola_kaldirma_gecisi_kilit_acikken_duz_yazar(self) -> None:
        """Bilinçli `plaintext_writes()` (kilit AÇIK) kapıya takılmaz."""
        ogrenci = _ogrenci()
        app_password.enable(password=PAROLA)
        assert _ham_ad(ogrenci.pk).startswith("gAAAA")

        app_password.disable(password=PAROLA)

        assert _ham_ad(ogrenci.pk) == AD


# ---------------------------------------------------------------------------
# API: istek sürerken kilitlenme yarışı 500 değil 423 döner
# ---------------------------------------------------------------------------
def test_api_yazim_yarisinda_423_doner_ve_islem_geri_alinir() -> None:
    app_password.enable(password=PAROLA)
    app_password.lock()
    onceki = _ogrenci_sayisi()

    # Ara katman kararını verdikten SONRA kilitlenmiş gibi: kapı "açık" der.
    with mock.patch.object(app_password, "gate_state", return_value=app_password.GATE_OPEN):
        resp = APIClient().post(
            "/api/v1/students/",
            {
                "first_name": "ZEYNEP",
                "last_name": "KAYA",
                "student_number": "205",
                "class_level": 10,
                "class_section": "A",
            },
            format="json",
        )

    assert resp.status_code == 423
    govde = resp.json()
    assert govde["code"] == "locked"
    assert "ZEYNEP" not in resp.content.decode("utf-8")
    assert _ogrenci_sayisi() == onceki


# ---------------------------------------------------------------------------
# Eski düz metin kalıntısı
# ---------------------------------------------------------------------------
class TestKalintiTemizligi:
    def test_baglantilar_secure_delete_ile_acilir(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA secure_delete")
            assert int(cursor.fetchone()[0]) == 1

    def test_temizlik_eski_duz_metni_dosyadan_ve_waldan_siler(self, tmp_path: Path) -> None:
        """Gerçek dosya: `secure_delete` KAPALIYKEN bile geçiş sonu temizliği düz
        metni hem ana dosyadan hem WAL'dan kaldırır (önkoşul: temizlikten önce oradaydı)."""
        db = tmp_path / "db.sqlite3"
        wal = tmp_path / "db.sqlite3-wal"
        duz = "EMRE CAN ÖZTÜRK".encode()

        conn = sqlite3.connect(db, isolation_level=None)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA secure_delete=OFF")
            conn.execute("PRAGMA wal_autocheckpoint=0")
            conn.execute("CREATE TABLE ogrenci (id INTEGER PRIMARY KEY, ad TEXT)")
            conn.executemany(
                "INSERT INTO ogrenci (ad) VALUES (?)",
                [("EMRE CAN ÖZTÜRK",)] + [(f"Dolgu {i}",) for i in range(200)],
            )
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")  # düz sürüm ana dosyada
            token = crypto._fernet_for(b"k" * 32).encrypt(duz).decode("ascii")
            conn.execute("UPDATE ogrenci SET ad = ? WHERE id = 1", (token,))
            conn.execute("DELETE FROM ogrenci WHERE id > 150")

            def _disk() -> bytes:
                return db.read_bytes() + (wal.read_bytes() if wal.exists() else b"")

            assert duz in _disk()  # önkoşul: kalıntı gerçekten var

            assert app_password.scrub_free_pages(conn.cursor()) is True

            assert duz not in _disk()
            assert not wal.exists() or wal.stat().st_size == 0
            assert conn.execute("SELECT ad FROM ogrenci WHERE id = 1").fetchone()[0] == token
        finally:
            conn.close()

    def test_sifreleme_gecisi_temizligi_islem_kapaninca_kosar(
        self, django_capture_on_commit_callbacks: Any, tmp_path: Path
    ) -> None:
        _ogrenci()
        casus = mock.Mock(return_value=True)
        with (
            mock.patch.object(app_password, "database_file", return_value=tmp_path / "db"),
            mock.patch.object(app_password, "scrub_free_pages", casus),
            django_capture_on_commit_callbacks(execute=True),
        ):
            app_password.enable(password=PAROLA)

        assert casus.call_count == 1

    def test_temizlik_hatasi_gecisi_bozmaz(
        self,
        django_capture_on_commit_callbacks: Any,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        ogrenci = _ogrenci()
        with (
            mock.patch.object(app_password, "database_file", return_value=tmp_path / "db"),
            mock.patch.object(
                app_password, "scrub_free_pages", side_effect=DatabaseError("meşgul")
            ),
            django_capture_on_commit_callbacks(execute=True),
            caplog.at_level(logging.WARNING, logger="kelebek_sinav.guvenlik"),
        ):
            app_password.enable(password=PAROLA)

        assert _ham_ad(ogrenci.pk).startswith("gAAAA")
        assert "temizlenemedi" in caplog.text

    def test_bellek_ici_veritabaninda_temizlik_atlanir(self) -> None:
        with mock.patch.object(app_password, "scrub_free_pages") as casus:
            app_password.enable(password=PAROLA)
        casus.assert_not_called()
