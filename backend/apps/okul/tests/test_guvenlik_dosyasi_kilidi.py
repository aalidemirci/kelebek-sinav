"""Güvenlik dosyası kilidi — "parola kurulu mu?" dosyanın VARLIĞINA bağlı değildir.

Cevap: güvenlik dosyası (`guvenlik.json`) VAR **ya da** DB'deki anahtar parmak izi
DOLU. Parola isteğe bağlıdır ve parolasız kip meşrudur; ama parolasız kip yalnız
ikisinin de yokluğudur. Kanıtlanan maddeler:

* kilitliyken dosya silinir, yeniden adlandırılır ya da bozulursa program
  "parolasız" sanılmaz: durum "kayıp" olur, veri uçları 423
  `guvenlik_dosyasi_kayip` döner, yalnız durum/sıfırlama/yedek uçları açıktır;
* parmak izi doluyken `enable()` yeni parola KURMAZ;
* yedekten geri yükleme dosyayı yedeğin kurtarma başlığından yeniden yazar;
* yalnız parmak izi BOŞKEN okunamayan dosya sıfırlanabilir (arşivlenir);
* masaüstü yedek katmanının okuduğu tablo/sütun adları modelle aynıdır.

Veritabanına ham SQL ile değil servis/uç üzerinden bakılır; güvenlik dosyası
her test için ayrı dizindedir (`conftest.guvenlik_ortami`).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, cast

import pytest
from desktop.backup import KEY_FINGERPRINT_COLUMN, KEY_FINGERPRINT_TABLE
from desktop.backup_crypto import (
    config_path,
    encrypt_to_path,
    load_public_key,
    usable_recovery_header,
)
from rest_framework.test import APIClient

from apps.okul.models import SchoolConfig, Student
from apps.okul.services import app_password, backup_restore
from shared import crypto

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("guvenlik_ortami")]

PAROLA = "Deneme-Parola-1"

# Kullanılamayan dosya biçimleri (tek kural: backup_crypto.is_usable_security_state).
KULLANILAMAYAN_ICERIKLER = [
    b"",
    b"{bozuk",
    b"[]",
    b'{"kdf":{},"parola":{"salt":"","sarmal":"x"},"kurtarma":{}}',
]
KULLANILAMAYAN_ADLAR = ["bos", "bozuk-json", "sozluk-degil", "sarmal-eksik"]


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _ogrenci() -> Student:
    return cast(
        "Student",
        Student.objects.create(
            first_name="EMRE",
            last_name="YILMAZ",
            student_number="101",
            class_level=10,
            class_section="A",
        ),
    )


def _kur_ve_kilitle() -> str:
    """Parola kurar (kayıt şifrelenir, parmak izi yazılır) ve kilitler."""
    _ogrenci()
    kurtarma = app_password.enable(password=PAROLA)
    app_password.lock()
    return kurtarma


# ---------------------------------------------------------------------------
# Durum sorgusu
# ---------------------------------------------------------------------------
class TestDurum:
    def test_parolasiz_kipte_kilit_yok(self) -> None:
        _ogrenci()
        assert app_password.is_password_set() is False
        assert app_password.security_file_missing() is False
        assert app_password.gate_state() == app_password.GATE_OPEN
        durum = app_password.status()
        assert durum["password_set"] is False
        assert durum["locked"] is False
        assert durum["security_file_missing"] is False
        assert durum["reset_available"] is False

    def test_kilitliyken_dosya_silinirse_parolasiz_sanilmaz(self) -> None:
        _kur_ve_kilitle()
        app_password.state_path().unlink()

        assert app_password.is_password_set() is True
        assert app_password.is_locked() is True
        assert app_password.security_file_missing() is True
        assert app_password.gate_state() == app_password.GATE_MISSING
        durum = app_password.status()
        assert durum["password_set"] is True
        assert durum["locked"] is True
        assert durum["security_file_missing"] is True
        assert durum["reset_available"] is False

    def test_dosya_yeniden_adlandirilirsa_da_kayip_sayilir(self) -> None:
        _kur_ve_kilitle()
        yol = app_password.state_path()
        yol.rename(yol.with_name("guvenlik.json.bak"))

        assert app_password.security_file_missing() is True
        assert app_password.status()["password_set"] is True

    @pytest.mark.parametrize("icerik", KULLANILAMAYAN_ICERIKLER, ids=KULLANILAMAYAN_ADLAR)
    def test_kullanilamayan_dosya_kayip_sayilir_durum_ucu_hata_vermez(self, icerik: bytes) -> None:
        _kur_ve_kilitle()
        app_password.state_path().write_bytes(icerik)

        assert app_password.security_file_missing() is True
        durum = app_password.status()  # eskiden bozuk dosyada istisna yükseliyordu
        assert durum["security_file_missing"] is True
        assert durum["locked"] is True

    def test_anahtar_bellekteyken_dosya_kaybolsa_da_kapi_kapanir(self) -> None:
        _ogrenci()
        app_password.enable(password=PAROLA)  # kilit açık
        app_password.state_path().unlink()

        assert crypto.is_unlocked() is True
        assert app_password.gate_state() == app_password.GATE_MISSING

    def test_dosya_geri_konunca_olagan_kilide_donulur(self) -> None:
        _kur_ve_kilitle()
        yol = app_password.state_path()
        kopya = yol.read_bytes()
        yol.unlink()
        assert app_password.gate_state() == app_password.GATE_MISSING

        yol.write_bytes(kopya)

        assert app_password.gate_state() == app_password.GATE_LOCKED
        app_password.unlock(password=PAROLA)
        assert app_password.gate_state() == app_password.GATE_OPEN


# ---------------------------------------------------------------------------
# Kayıpken yapılamayanlar
# ---------------------------------------------------------------------------
class TestKayipkenReddedilenler:
    def test_parmak_izi_doluyken_yeni_parola_kurulamaz(self) -> None:
        _kur_ve_kilitle()
        parmak_izi = SchoolConfig.load().app_password_hash
        app_password.state_path().unlink()

        with pytest.raises(app_password.AppPasswordError, match="daha önce kurulmuş"):
            app_password.enable(password="Yeni-Parola-2")

        assert not app_password.state_path().exists()
        assert SchoolConfig.load().app_password_hash == parmak_izi

    def test_bozuk_dosyanin_ustune_parola_kurulamaz(self) -> None:
        _kur_ve_kilitle()
        app_password.state_path().write_bytes(b"{bozuk")

        with pytest.raises(app_password.AppPasswordError, match="bozuk"):
            app_password.enable(password="Yeni-Parola-2")

    def test_kilit_acma_ve_kurtarma_kayip_iletisiyle_durur(self) -> None:
        kurtarma = _kur_ve_kilitle()
        app_password.state_path().unlink()

        with pytest.raises(app_password.AppPasswordError, match="bulunamadı"):
            app_password.unlock(password=PAROLA)
        with pytest.raises(app_password.AppPasswordError, match="bulunamadı"):
            app_password.unlock_with_recovery(recovery_key=kurtarma, new_password="Yeni-Parola-2")

    def test_parolasiz_kipte_ileti_kurulu_degil_der(self) -> None:
        with pytest.raises(app_password.AppPasswordError, match="kurulu değil"):
            app_password.unlock(password=PAROLA)


# ---------------------------------------------------------------------------
# Kilit kapısı (ara katman)
# ---------------------------------------------------------------------------
class TestKilitKapisi:
    def test_kayipken_veri_uclari_423_guvenlik_dosyasi_kayip(self, client: APIClient) -> None:
        _kur_ve_kilitle()
        app_password.state_path().unlink()

        resp = client.get("/api/v1/students/")

        assert resp.status_code == 423
        assert resp.json()["code"] == "guvenlik_dosyasi_kayip"

    def test_kayipken_yalniz_izinli_uclar_acik(self, client: APIClient) -> None:
        _kur_ve_kilitle()
        app_password.state_path().unlink()

        durum = client.get("/api/v1/security/status/")
        assert durum.status_code == 200
        assert durum.json()["security_file_missing"] is True
        assert client.get("/api/v1/setup/status/").status_code == 200
        assert client.get("/api/v1/backups/").status_code == 200
        # Geri yükleme ucu kapıdan geçer (burada bellek içi DB yüzünden 400 döner).
        assert client.post("/api/v1/backups/restore/", {"name": "yok.ksbak"}).status_code != 423

        for yol, govde in (
            ("/api/v1/security/unlock/", {"password": PAROLA}),
            ("/api/v1/security/enable/", {"password": "Yeni-Parola-2"}),
            ("/api/v1/security/recover/", {"recovery_key": "x", "new_password": "y"}),
            ("/api/v1/security/lock/", {}),
        ):
            resp = client.post(yol, govde, format="json")
            assert resp.status_code == 423, yol
            assert resp.json()["code"] == "guvenlik_dosyasi_kayip"
        assert client.get("/api/v1/updates/latest/").status_code == 423

    def test_anahtar_bellekteyken_de_kapi_kapanir(self, client: APIClient) -> None:
        _ogrenci()
        app_password.enable(password=PAROLA)
        app_password.state_path().unlink()

        assert client.get("/api/v1/students/").status_code == 423

    def test_parolasiz_kipte_kapi_acik(self, client: APIClient) -> None:
        _ogrenci()
        assert client.get("/api/v1/students/").status_code == 200


# ---------------------------------------------------------------------------
# Çıkış yolu: yedekten geri yükleme
# ---------------------------------------------------------------------------
def _sifreli_yedek(guvenlik_dizini: Path, hedef: Path) -> Path:
    """Güncel güvenlik dosyasını başlığında taşıyan küçük bir şifreli yedek yazar."""
    kaynak = hedef.with_suffix(".kaynak.sqlite3")
    with sqlite3.connect(kaynak) as baglanti:
        baglanti.execute("CREATE TABLE deneme (deger TEXT)")
        baglanti.execute("INSERT INTO deneme VALUES ('uydurma')")
    baslik = usable_recovery_header(guvenlik_dizini)
    assert baslik is not None
    encrypt_to_path(
        kaynak.read_bytes(), hedef, load_public_key(guvenlik_dizini), recovery_header=baslik
    )
    return hedef


class TestGeriYukleme:
    def test_kayipken_geri_yukleme_guvenlik_dosyasini_yeniden_yazar(
        self, guvenlik_ortami: Path, tmp_path: Path
    ) -> None:
        _kur_ve_kilitle()
        yedek = _sifreli_yedek(guvenlik_ortami, tmp_path / "gunluk-2026-09-01.ksbak")
        baslik = app_password.state_path().read_bytes()
        app_password.state_path().unlink()
        assert app_password.security_file_missing() is True

        sonuc = backup_restore.restore_database(
            yedek, tmp_path / "hedef" / "db.sqlite3", password=PAROLA
        )

        assert sonuc.state_written is True
        assert app_password.state_path().read_bytes() == baslik
        assert app_password.security_file_missing() is False

    @pytest.mark.parametrize("icerik", KULLANILAMAYAN_ICERIKLER, ids=KULLANILAMAYAN_ADLAR)
    def test_kullanilamayan_guncel_dosya_arsivlenir_gomulu_baslik_yazilir(
        self, guvenlik_ortami: Path, tmp_path: Path, icerik: bytes
    ) -> None:
        _kur_ve_kilitle()
        yedek = _sifreli_yedek(guvenlik_ortami, tmp_path / "gunluk-2026-09-01.ksbak")
        baslik = app_password.state_path().read_bytes()
        app_password.state_path().write_bytes(icerik)

        sonuc = backup_restore.restore_database(
            yedek, tmp_path / "hedef" / "db.sqlite3", password=PAROLA
        )

        assert sonuc.state_written is True
        assert app_password.state_path().read_bytes() == baslik
        arsivler = list(guvenlik_ortami.glob(f"{app_password.STATE_ARCHIVE_PREFIX}*.json"))
        assert [a.read_bytes() for a in arsivler] == [icerik]  # silinmedi, kenara alındı


# ---------------------------------------------------------------------------
# Sıfırlama: yalnız korunan satır yokken
# ---------------------------------------------------------------------------
class TestSifirlama:
    URL = "/api/v1/security/state/reset/"

    def test_parmak_izi_bosken_okunamayan_dosya_sifirlanir(
        self, client: APIClient, guvenlik_ortami: Path
    ) -> None:
        """Parolasız kurulumda bozuk bir guvenlik.json: satırlar düzdür, dosya hiçbir
        şeyi korumuyor. Sıfırlama dosyayı ARŞİVLER ve parolasız kipe döner."""
        _ogrenci()
        app_password.state_path().write_bytes(b"{bozuk")
        (guvenlik_ortami / "yedekleme.json").write_text("{}", encoding="utf-8")
        assert app_password.status()["reset_available"] is True
        assert client.get("/api/v1/students/").status_code == 423

        resp = client.post(self.URL)

        assert resp.status_code == 200
        assert resp.json()["password_set"] is False
        assert resp.json()["security_file_missing"] is False
        assert not app_password.state_path().exists()
        assert not config_path(guvenlik_ortami).exists()
        arsiv = list(guvenlik_ortami.glob(f"{app_password.STATE_ARCHIVE_PREFIX}*.json"))
        assert [a.read_bytes() for a in arsiv] == [b"{bozuk"]
        assert len(list(guvenlik_ortami.glob("yedekleme-arsiv-*.json"))) == 1
        assert client.get("/api/v1/students/").status_code == 200

    def test_parmak_izi_doluyken_sifirlanamaz(self, client: APIClient) -> None:
        _kur_ve_kilitle()
        app_password.state_path().write_bytes(b"{bozuk")
        assert app_password.status()["reset_available"] is False

        resp = client.post(self.URL)

        assert resp.status_code == 409
        assert resp.json()["code"] == "sifirlama_uygun_degil"
        assert app_password.state_path().read_bytes() == b"{bozuk"

    def test_dosya_yokken_sifirlanacak_bir_sey_yok(self, client: APIClient) -> None:
        _kur_ve_kilitle()
        app_password.state_path().unlink()

        assert client.post(self.URL).status_code == 409
        with pytest.raises(app_password.StateResetNotAllowed):
            app_password.reset_unusable_state()

    def test_saglam_dosya_sifirlanamaz(self, client: APIClient) -> None:
        _kur_ve_kilitle()
        # Kilitliyken `security/` ön eki açıktır; uç koşulu kendisi reddeder.
        assert client.post(self.URL).status_code == 409
        assert app_password.state_path().is_file()


# ---------------------------------------------------------------------------
# Masaüstü sözleşmesi
# ---------------------------------------------------------------------------
def test_masaustu_parmak_izi_adlari_modelle_ayni() -> None:
    """`desktop.backup` Django'yu import etmez; okuduğu tablo/sütun burada sınanır."""
    alan = SchoolConfig._meta.get_field("app_password_hash")
    assert SchoolConfig._meta.db_table == KEY_FINGERPRINT_TABLE
    assert cast("Any", alan).column == KEY_FINGERPRINT_COLUMN
