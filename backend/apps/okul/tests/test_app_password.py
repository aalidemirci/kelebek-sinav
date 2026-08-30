"""Opsiyonel uygulama parolası (DD F5-D5 kalıbı, tasarım §5) — uçtan uca davranış testleri.

Buradaki en önemli iddia şudur: **parola konduktan sonra veritabanı dosyasında
öğrenci/personel AD-SOYADI düz metin olarak ARANAMAZ** (KS şifreleme kapsamı —
DD'den fark: DD ad-soyadı düz bırakıyordu, KS U3 kararıyla şifreler; okul no ve
sınıf/şube takma-adlı oldukları için düz kalır). Testler ORM'e güvenmez, ham SQL
ile sütunu okur (`connection.cursor()`), aksi hâlde şifreli alan kendini çözer
ve test yalan söylerdi.

Argon2id kasten yavaştır (varsayılan profil ~0,2 sn); test koşusu her kilit
açmada bunu ödemesin diye `crypto.DEFAULT_KDF` ucuz profile indirilir. Bu YALNIZ
maliyet parametresidir — algoritma, zarf yapısı ve dosya biçimi üretimdekiyle
birebir aynıdır.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterator
from io import StringIO
from pathlib import Path
from typing import Any, cast
from unittest import mock

import pytest
from desktop.backup_crypto import decrypt_bytes, ensure_public_config
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from rest_framework.test import APIClient

from apps.okul import selectors
from apps.okul.models import Personnel, SchoolConfig, Student
from apps.okul.services import app_password
from shared import crypto

PAROLA = "Deneme-Parola-1"
YENI_PAROLA = "Baska-Parola-2"

OGRENCI_AD = "EMRE CAN"
OGRENCI_SOYAD = "YILMAZ"
OKUL_NO = "101"


@pytest.fixture(autouse=True)
def guvenlik_ortami(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Her test kendi güvenlik dosyası + yedek dizini ile koşar; anahtar sıfırlanır."""
    monkeypatch.setenv(app_password.ENV_SECURITY_DIR, str(tmp_path / "veri"))
    monkeypatch.setenv(app_password.ENV_BACKUP_DIR, str(tmp_path / "yedek"))
    (tmp_path / "veri").mkdir()
    # Ucuz Argon2 profili (bkz. modül başlığı). memory_cost >= 8 * parallelism.
    monkeypatch.setattr(
        crypto, "DEFAULT_KDF", crypto.KdfParams(time_cost=1, memory_cost=8, parallelism=1)
    )
    # Gecikme merdiveni gerçek `sleep` çağırmasın (davranışı ayrı test doğrular).
    monkeypatch.setattr(app_password, "FAILURE_DELAYS", (0.0,))
    crypto.unload_key()
    yield
    crypto.unload_key()


def ogrenci_olustur(**fazlasi: Any) -> Student:
    veri: dict[str, Any] = {
        "first_name": OGRENCI_AD,
        "last_name": OGRENCI_SOYAD,
        "student_number": OKUL_NO,
        "class_level": 10,
        "class_section": "A",
    }
    veri.update(fazlasi)
    return cast("Student", Student.objects.create(**veri))


def ham_satir(student_id: int) -> tuple[str, str]:
    """ORM'i BYPASS ederek ad-soyad sütunlarını olduğu gibi okur (şifre çözülmez)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT first_name, last_name FROM okul_student WHERE id = %s",
            [student_id],
        )
        satir = cursor.fetchone()
    return (str(satir[0]), str(satir[1]))


# ---------------------------------------------------------------------------
# Parola kurma → şifreleme
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestEnable:
    def test_ad_soyad_dbde_duz_metin_olarak_bulunamaz(self) -> None:
        ogrenci = ogrenci_olustur()
        app_password.enable(password=PAROLA)

        ad, soyad = ham_satir(ogrenci.pk)
        assert OGRENCI_AD not in ad
        assert OGRENCI_SOYAD not in soyad
        # Fernet token'ı 'gAAAA' ile başlar — gerçekten şifrelenmiş.
        assert ad.startswith("gAAAA")

    def test_personel_adi_da_sifrelenir(self) -> None:
        kisi = Personnel.objects.create(
            first_name="AYŞE", last_name="ÖĞRETMEN", title="Öğretmen", branch="Coğrafya"
        )
        app_password.enable(password=PAROLA)
        with connection.cursor() as cursor:
            cursor.execute("SELECT first_name, branch FROM okul_personnel WHERE id = %s", [kisi.pk])
            ad, brans = cursor.fetchone()
        assert str(ad).startswith("gAAAA")
        assert brans == "Coğrafya"  # branş kapsam dışı — süzgeçler DB tarafında

    def test_okul_no_ve_sinif_kapsam_disidir(self) -> None:
        """Tasarım kararı (§5): motor/sıralama/teklik alanları şifrelenMEZ."""
        ogrenci = ogrenci_olustur()
        app_password.enable(password=PAROLA)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT student_number, class_level, class_section, status "
                "FROM okul_student WHERE id = %s",
                [ogrenci.pk],
            )
            numara, seviye, sube, durum = cursor.fetchone()
        assert numara == OKUL_NO
        assert int(seviye) == 10
        assert sube == "A"
        assert durum == "ACTIVE"

    def test_kilit_acikken_orm_duz_metin_dondurur(self) -> None:
        ogrenci = ogrenci_olustur()
        app_password.enable(password=PAROLA)
        tazelenmis = Student.objects.get(pk=ogrenci.pk)
        assert tazelenmis.first_name == OGRENCI_AD
        assert tazelenmis.full_name == f"{OGRENCI_AD} {OGRENCI_SOYAD}"

    def test_silinmis_ogrencinin_alanlari_da_sifrelenir(self) -> None:
        ogrenci = ogrenci_olustur()
        ogrenci.delete()  # soft-delete
        app_password.enable(password=PAROLA)
        ad, _ = ham_satir(ogrenci.pk)
        assert ad.startswith("gAAAA")

    def test_gecis_oncesi_yedek_sifrelemeden_ONCE_alinir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Yedek çağrısı, satırlara DOKUNULMADAN önce olmalı (yoksa yedek de şifreli olurdu)."""
        ogrenci = ogrenci_olustur()
        anlar: list[str] = []

        def yedek_casusu(label: str) -> None:
            anlar.append(f"{label}:{ham_satir(ogrenci.pk)[0]}")

        monkeypatch.setattr(app_password, "take_transition_backup", yedek_casusu)
        app_password.enable(password=PAROLA)
        assert anlar == [f"acilis:{OGRENCI_AD}"]

    def test_dosya_tabanli_veritabaninda_gercek_kopya_alinir(self, tmp_path: Path) -> None:
        """Kopyalama mantığının kendisi (gerçek dosya + gerçek SQLite yedek API'si)."""
        veri_anahtari = b"k" * 32
        ensure_public_config(app_password._data_dir(), veri_anahtari)
        kaynak = tmp_path / "db.sqlite3"
        with sqlite3.connect(kaynak) as baglanti:
            baglanti.execute("CREATE TABLE deneme (ad TEXT)")
            baglanti.execute("INSERT INTO deneme VALUES ('EMRE')")
        with mock.patch.object(app_password, "database_file", return_value=kaynak):
            hedef = app_password.take_transition_backup("acilis")
        assert hedef is not None
        assert hedef.name.startswith("pre-parola-acilis-")
        geri_yuklenen = tmp_path / "geri-yuklenen.sqlite3"
        geri_yuklenen.write_bytes(decrypt_bytes(hedef.read_bytes(), veri_anahtari))
        with sqlite3.connect(geri_yuklenen) as kopya:
            assert kopya.execute("SELECT ad FROM deneme").fetchone() == ("EMRE",)

    def test_ikinci_kez_kurulamaz(self) -> None:
        app_password.enable(password=PAROLA)
        with pytest.raises(app_password.AppPasswordError, match="zaten kurulu"):
            app_password.enable(password=PAROLA)

    def test_kisa_parola_reddedilir(self) -> None:
        with pytest.raises(app_password.AppPasswordError, match="en az 8"):
            app_password.enable(password="kisa")
        assert app_password.read_state() is None

    def test_parmak_izi_dbye_yazilir(self) -> None:
        app_password.enable(password=PAROLA)
        assert SchoolConfig.load().app_password_hash.startswith("v1:")


# ---------------------------------------------------------------------------
# Kilit açma / kilitleme
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestUnlock:
    def test_dogru_parola_acar(self) -> None:
        ogrenci = ogrenci_olustur()
        app_password.enable(password=PAROLA)
        app_password.lock()
        assert app_password.is_locked() is True
        # Kilitliyken okuma çöp (token) döner — patlamaz.
        assert Student.objects.get(pk=ogrenci.pk).first_name.startswith("gAAAA")

        app_password.unlock(password=PAROLA)
        assert app_password.is_locked() is False
        assert Student.objects.get(pk=ogrenci.pk).first_name == OGRENCI_AD

    def test_yanlis_parola_reddedilir(self) -> None:
        app_password.enable(password=PAROLA)
        app_password.lock()
        with pytest.raises(app_password.AppPasswordError, match="Parola hatalı"):
            app_password.unlock(password="yanlis-parola")
        assert app_password.is_locked() is True

    def test_yanlis_parola_kademeli_gecikme_uygular(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Kalıcı kilit YOK; art arda hatada süreç-içi gecikme artar (bkz. modül notu)."""
        monkeypatch.setattr(app_password, "FAILURE_DELAYS", (0.0, 0.5))
        beklemeler: list[float] = []
        monkeypatch.setattr(time, "sleep", beklemeler.append)
        app_password.enable(password=PAROLA)
        app_password.lock()
        for _ in range(3):
            with pytest.raises(app_password.AppPasswordError):
                app_password.unlock(password="yanlis")
        assert beklemeler == [0.5, 0.5]  # ilk deneme gecikmesiz, sonrakiler tavanda
        # Doğru parola sayacı sıfırlar.
        app_password.unlock(password=PAROLA)
        beklemeler.clear()
        app_password.lock()
        with pytest.raises(app_password.AppPasswordError):
            app_password.unlock(password="yanlis")
        assert beklemeler == []

    def test_parola_kurulu_degilken_acilamaz(self) -> None:
        with pytest.raises(app_password.AppPasswordError, match="kurulu değil"):
            app_password.unlock(password=PAROLA)

    def test_baska_veritabaninin_guvenlik_dosyasi_reddedilir(self) -> None:
        """Parmak izi uyuşmazlığı → sessiz bozulma yerine açık ret."""
        app_password.enable(password=PAROLA)
        app_password.lock()
        config = SchoolConfig.objects.get(pk=SchoolConfig.SINGLETON_PK)
        config.app_password_hash = "v1:" + "0" * 64
        config.save(update_fields=["app_password_hash"])
        with pytest.raises(app_password.AppPasswordError, match="ait değil"):
            app_password.unlock(password=PAROLA)


# ---------------------------------------------------------------------------
# Kurtarma anahtarı
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestRecovery:
    def test_kurtarma_anahtariyla_acilir_ve_parola_yenilenir(self) -> None:
        ogrenci = ogrenci_olustur()
        kurtarma = app_password.enable(password=PAROLA)
        app_password.lock()

        app_password.unlock_with_recovery(recovery_key=kurtarma, new_password=YENI_PAROLA)
        assert Student.objects.get(pk=ogrenci.pk).first_name == OGRENCI_AD

        # Eski parola artık geçersiz, yenisi geçerli.
        app_password.lock()
        with pytest.raises(app_password.AppPasswordError):
            app_password.unlock(password=PAROLA)
        app_password.unlock(password=YENI_PAROLA)

    def test_kurtarma_anahtari_bicimden_bagimsiz_kabul_edilir(self) -> None:
        kurtarma = app_password.enable(password=PAROLA)
        app_password.lock()
        bozuk_bicim = kurtarma.replace("-", " ").lower()
        app_password.unlock_with_recovery(recovery_key=bozuk_bicim, new_password=YENI_PAROLA)
        assert app_password.is_locked() is False

    def test_yanlis_kurtarma_anahtari_reddedilir(self) -> None:
        app_password.enable(password=PAROLA)
        app_password.lock()
        with pytest.raises(app_password.AppPasswordError, match="Kurtarma anahtarı hatalı"):
            app_password.unlock_with_recovery(
                recovery_key="AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-GGGG-HHHH",
                new_password=YENI_PAROLA,
            )

    def test_kurtarma_anahtari_parola_degisince_gecerli_kalir(self) -> None:
        """Zarf şifreleme: parola sarmalı değişir, kurtarma sarmalı DEĞİŞMEZ."""
        kurtarma = app_password.enable(password=PAROLA)
        app_password.change_password(current_password=PAROLA, new_password=YENI_PAROLA)
        app_password.lock()
        app_password.unlock_with_recovery(recovery_key=kurtarma, new_password="Ucuncu-Parola-3")
        assert app_password.is_locked() is False


# ---------------------------------------------------------------------------
# Parola değiştirme
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestChangePassword:
    def test_veri_yeniden_sifrelenmez_ama_okunur_kalir(self) -> None:
        ogrenci = ogrenci_olustur()
        app_password.enable(password=PAROLA)
        onceki_token, _ = ham_satir(ogrenci.pk)

        app_password.change_password(current_password=PAROLA, new_password=YENI_PAROLA)
        sonraki_token, _ = ham_satir(ogrenci.pk)
        # Veri anahtarı değişmediği için satırlara DOKUNULMAZ (eski yedekler de açılabilir kalır).
        assert sonraki_token == onceki_token

        app_password.lock()
        app_password.unlock(password=YENI_PAROLA)
        assert Student.objects.get(pk=ogrenci.pk).first_name == OGRENCI_AD

    def test_yanlis_mevcut_parola_reddedilir(self) -> None:
        app_password.enable(password=PAROLA)
        with pytest.raises(app_password.AppPasswordError, match="Parola hatalı"):
            app_password.change_password(current_password="yanlis", new_password=YENI_PAROLA)


# ---------------------------------------------------------------------------
# Parola kaldırma
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestDisable:
    def test_alanlar_duz_metne_doner(self) -> None:
        ogrenci = ogrenci_olustur()
        app_password.enable(password=PAROLA)
        app_password.disable(password=PAROLA)

        ad, soyad = ham_satir(ogrenci.pk)
        assert ad == OGRENCI_AD
        assert soyad == OGRENCI_SOYAD
        assert app_password.is_password_set() is False
        assert SchoolConfig.load().app_password_hash == ""

    def test_guvenlik_dosyasi_silinmez_arsivlenir(self) -> None:
        """Eski yedekler eski anahtarla şifrelidir; arşiv onları kurtarılabilir tutar."""
        ogrenci_olustur()
        app_password.enable(password=PAROLA)
        app_password.disable(password=PAROLA)
        arsiv = list(app_password.state_path().parent.glob("guvenlik-arsiv-*.json"))
        assert len(arsiv) == 1
        assert "kurtarma" in json.loads(arsiv[0].read_text(encoding="utf-8"))

    def test_yedek_acik_anahtari_kaldirilir(self) -> None:
        """K9 iki kip: parolasız kipe dönüşte `yedekleme.json` kalkar — sonraki
        günlük yedekler düz alınır; dosya kalsaydı yedekler yalnız ESKİ parolayla
        açılabilen bir anahtarla şifrelenmeye devam ederdi."""
        ogrenci_olustur()
        app_password.enable(password=PAROLA)
        yedek_ayari = app_password.state_path().parent / "yedekleme.json"
        assert yedek_ayari.is_file()

        app_password.disable(password=PAROLA)

        assert not yedek_ayari.exists()

    def test_gecis_oncesi_yedek_cozmeden_ONCE_alinir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ogrenci = ogrenci_olustur()
        app_password.enable(password=PAROLA)
        anlar: list[str] = []

        def yedek_casusu(label: str) -> None:
            anlar.append(f"{label}:{ham_satir(ogrenci.pk)[0][:5]}")

        monkeypatch.setattr(app_password, "take_transition_backup", yedek_casusu)
        app_password.disable(password=PAROLA)
        assert anlar == ["kaldirma:gAAAA"]  # yedek alınırken satırlar hâlâ şifreli

    def test_yanlis_parolayla_kaldirilamaz(self) -> None:
        ogrenci = ogrenci_olustur()
        app_password.enable(password=PAROLA)
        with pytest.raises(app_password.AppPasswordError):
            app_password.disable(password="yanlis-parola")
        assert ham_satir(ogrenci.pk)[0].startswith("gAAAA")


# ---------------------------------------------------------------------------
# Yarım kalan geçiş (elektrik kesintisi senaryosu)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestInterruptedTransition:
    def test_sifreleme_yarida_kalirsa_acilista_tamamlanir(self) -> None:
        """Dosya yazıldı, satırlar yazılamadan kesildi → veri okunur, geçiş tamamlanır."""
        ogrenci = ogrenci_olustur()

        # `monkeypatch.undo()` KULLANILMAZ: `monkeypatch` fikstürü autouse
        # fikstürüyle AYNI nesnedir, undo çağrısı güvenlik dizini env'ini de
        # geri alır (bu tuzak DD'de testi bir kez sessizce yanlış yeşile boyadı).
        with (
            mock.patch.object(app_password, "_rewrite_rows", side_effect=RuntimeError("kesinti")),
            pytest.raises(RuntimeError),
        ):
            app_password.enable(password=PAROLA)
        crypto.unload_key()  # program kapandı/elektrik kesildi

        # Kesinti sonrası tablo hâlâ DÜZ, dosya var ve geçiş yarım işaretli.
        assert ham_satir(ogrenci.pk)[0] == OGRENCI_AD
        durum = app_password.status()
        assert durum["password_set"] is True
        assert durum["transition_pending"] is True

        # Kilit açma geçişi kaldığı yerden tamamlar.
        app_password.unlock(password=PAROLA)
        assert ham_satir(ogrenci.pk)[0].startswith("gAAAA")
        assert app_password.status()["transition_pending"] is False

    def test_yarim_sifreli_tablo_okunabilir_ve_tekrar_kosulabilir(self) -> None:
        """Satırların YARISI şifreli kalsa bile okuma patlamaz, ikinci koşu düzeltir."""
        sifreli = ogrenci_olustur()
        duz = ogrenci_olustur(student_number="102", first_name="ZEYNEP", last_name="KAYA")
        app_password.enable(password=PAROLA)
        # İkinci satırı elle düz metne çevirerek "yarım geçiş" üret.
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE okul_student SET first_name = %s WHERE id = %s", ["ZEYNEP", duz.pk]
            )

        okunan = {o.pk: o.first_name for o in Student.objects.all()}
        assert okunan[sifreli.pk] == OGRENCI_AD  # şifreli satır çözüldü
        assert okunan[duz.pk] == "ZEYNEP"  # düz satır olduğu gibi geldi

        # Damga "tamam" olduğundan geçiş kendiliğinden koşmaz; destek eli `force`.
        sonuc = app_password.resume_pending(force=True)
        assert sonuc["resumed"] is True
        assert ham_satir(duz.pk)[0].startswith("gAAAA")
        # Fikirdeşlik: zaten şifreli satır ÇİFT şifrelenmez.
        assert Student.objects.get(pk=sifreli.pk).first_name == OGRENCI_AD

    def test_cozme_yarida_kalirsa_tamamlanir(self) -> None:
        ogrenci = ogrenci_olustur()
        app_password.enable(password=PAROLA)

        with (
            mock.patch.object(app_password, "_rewrite_rows", side_effect=RuntimeError("kesinti")),
            pytest.raises(RuntimeError),
        ):
            app_password.disable(password=PAROLA)
        crypto.unload_key()

        assert app_password.status()["transition_pending"] is True
        assert ham_satir(ogrenci.pk)[0].startswith("gAAAA")

        app_password.unlock(password=PAROLA)  # yarım kaldırma işlemini tamamlar
        assert ham_satir(ogrenci.pk)[0] == OGRENCI_AD
        assert app_password.is_password_set() is False

    def test_bozuk_guvenlik_dosyasi_turkce_hata_verir(self) -> None:
        app_password.enable(password=PAROLA)
        app_password.state_path().write_text("bu json değil", encoding="utf-8")
        with pytest.raises(app_password.AppPasswordError, match="bozuk"):
            app_password.read_state()


# ---------------------------------------------------------------------------
# Eşleştirme / arama davranışı (KS: ad şifreli, okul no düz — TB3)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestLookupBehaviour:
    def test_numara_eslesmesi_sifreli_kipte_db_filtresiyle_calisir(self) -> None:
        """DD'den fark: KS upsert anahtarı okul no DÜZ alandır — dolambaç gerekmez."""
        ogrenci = ogrenci_olustur()
        app_password.enable(password=PAROLA)
        assert selectors.find_student_by_number(OKUL_NO) == ogrenci
        assert Student.objects.filter(student_number=OKUL_NO).first() == ogrenci

    def test_ad_filtresi_orm_ile_CALISMAZ(self) -> None:
        """Şifreli alanda DB filtresi daima boş döner — yeni ad sorgusu ORM'e yazılmaz (TB3)."""
        ogrenci_olustur()
        app_password.enable(password=PAROLA)
        assert Student.objects.filter(first_name=OGRENCI_AD).first() is None

    def test_ad_aramasi_selector_uzerinden_bozulmaz(self) -> None:
        ogrenci_olustur()
        app_password.enable(password=PAROLA)
        bulunan = selectors.student_list(search="yilmaz")
        assert [o.student_number for o in bulunan] == [OKUL_NO]

    def test_personel_ad_siralamasi_python_tarafinda(self) -> None:
        Personnel.objects.create(first_name="ZEYNEP", last_name="ÇELİK")
        Personnel.objects.create(first_name="AHMET", last_name="AK")
        app_password.enable(password=PAROLA)
        sirali = selectors.personnel_sorted()
        assert [p.first_name for p in sirali] == ["AHMET", "ZEYNEP"]

    def test_parolasiz_kipte_alanlar_duz_kalir(self) -> None:
        ogrenci = ogrenci_olustur()
        assert ham_satir(ogrenci.pk)[0] == OGRENCI_AD
        assert app_password.status()["password_set"] is False


# ---------------------------------------------------------------------------
# API + kilit kapısı
# ---------------------------------------------------------------------------
@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
class TestSecurityApi:
    def test_durum_ucu(self, client: APIClient) -> None:
        resp = client.get("/api/v1/security/status/")
        assert resp.status_code == 200
        veri = resp.json()
        assert veri["password_set"] is False
        assert "ad" in veri["protected_fields"]

    def test_kurma_kilitleme_acma_akisi(self, client: APIClient) -> None:
        ogrenci = ogrenci_olustur()

        resp = client.post("/api/v1/security/enable/", {"password": PAROLA}, format="json")
        assert resp.status_code == 201
        kurtarma = resp.json()["recovery_key"]
        assert len(kurtarma.split("-")) == 8

        assert client.post("/api/v1/security/lock/").json()["locked"] is True
        resp = client.post("/api/v1/security/unlock/", {"password": "yanlis"}, format="json")
        assert resp.status_code == 400
        assert resp.json()["code"] == "validation_error"

        resp = client.post("/api/v1/security/unlock/", {"password": PAROLA}, format="json")
        assert resp.status_code == 200
        assert resp.json()["locked"] is False
        assert Student.objects.get(pk=ogrenci.pk).first_name == OGRENCI_AD

    def test_kurtarma_ucu(self, client: APIClient) -> None:
        kurtarma = client.post(
            "/api/v1/security/enable/", {"password": PAROLA}, format="json"
        ).json()["recovery_key"]
        client.post("/api/v1/security/lock/")
        resp = client.post(
            "/api/v1/security/recover/",
            {"recovery_key": kurtarma, "new_password": YENI_PAROLA},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.json()["locked"] is False

    def test_kaldirma_ucu(self, client: APIClient) -> None:
        ogrenci = ogrenci_olustur()
        client.post("/api/v1/security/enable/", {"password": PAROLA}, format="json")
        resp = client.post("/api/v1/security/disable/", {"password": PAROLA}, format="json")
        assert resp.status_code == 200
        assert resp.json()["password_set"] is False
        assert ham_satir(ogrenci.pk)[0] == OGRENCI_AD

    def test_parola_degistirme_ucu(self, client: APIClient) -> None:
        client.post("/api/v1/security/enable/", {"password": PAROLA}, format="json")
        resp = client.post(
            "/api/v1/security/change-password/",
            {"current_password": PAROLA, "new_password": YENI_PAROLA},
            format="json",
        )
        assert resp.status_code == 200
        client.post("/api/v1/security/lock/")
        assert (
            client.post(
                "/api/v1/security/unlock/", {"password": YENI_PAROLA}, format="json"
            ).status_code
            == 200
        )


@pytest.mark.django_db
class TestLockMiddleware:
    """Kilit kapısı (`apps.okul.lock_middleware`) — settings'te varsayılan olarak bağlı."""

    def test_kilitliyken_veri_uclari_423_doner(self, client: APIClient) -> None:
        ogrenci_olustur()
        app_password.enable(password=PAROLA)
        app_password.lock()

        resp = client.get("/api/v1/students/")
        assert resp.status_code == 423
        assert resp.json()["code"] == "locked"

    def test_kilitliyken_acilis_saglik_ucu_calisir(self, client: APIClient) -> None:
        """`desktop/server.py` açılışta bu ucu çağırır; 423 dönseydi program AÇILMAZDI."""
        app_password.enable(password=PAROLA)
        app_password.lock()
        resp = client.get("/api/v1/setup/status/")
        assert resp.status_code == 200
        # Kurulum sihirbazının YAZMA uçları yine kapalı.
        assert client.post("/api/v1/setup/complete/").status_code == 423

    def test_kilitliyken_guvenlik_uclari_calisir(self, client: APIClient) -> None:
        app_password.enable(password=PAROLA)
        app_password.lock()
        assert client.get("/api/v1/security/status/").status_code == 200
        assert (
            client.post("/api/v1/security/unlock/", {"password": PAROLA}, format="json").status_code
            == 200
        )
        # Kilit açıldıktan sonra veri uçları normale döner.
        assert client.get("/api/v1/students/").status_code == 200

    def test_parolasiz_kipte_kapi_devre_disidir(self, client: APIClient) -> None:
        assert client.get("/api/v1/students/").status_code == 200


# ---------------------------------------------------------------------------
# Konsol kurtarma aracı
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestManagementCommand:
    """`manage.py app_password …` — arayüz açılamadığında tek çıkış yolu."""

    def _kosu(self, *args: str, **secenekler: Any) -> str:
        cikti = StringIO()
        call_command("app_password", *args, stdout=cikti, **secenekler)
        return cikti.getvalue()

    def test_durum_ozet_basar(self) -> None:
        cikti = self._kosu("status")
        assert "Parola kurulu    : hayır" in cikti
        assert "ad" in cikti

    def test_kur_ve_kaldir(self) -> None:
        ogrenci = ogrenci_olustur()
        cikti = self._kosu("enable", password=PAROLA)
        assert "KURTARMA ANAHTARI" in cikti
        assert ham_satir(ogrenci.pk)[0].startswith("gAAAA")

        self._kosu("disable", password=PAROLA)
        assert ham_satir(ogrenci.pk)[0] == OGRENCI_AD

    def test_kurtar_yeni_parola_belirler(self) -> None:
        cikti = self._kosu("enable", password=PAROLA)
        kurtarma = cikti.strip().splitlines()[-1].strip()
        app_password.lock()
        self._kosu("recover", recovery_key=kurtarma, new_password=YENI_PAROLA)
        assert app_password.is_locked() is False

    def test_yanlis_parola_command_error_verir(self) -> None:
        self._kosu("enable", password=PAROLA)
        app_password.lock()
        with pytest.raises(CommandError, match="Parola hatalı"):
            self._kosu("resume", password="yanlis-parola")

    def test_resume_force_yeniden_kosar(self) -> None:
        ogrenci = ogrenci_olustur()
        self._kosu("enable", password=PAROLA)
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE okul_student SET first_name = %s WHERE id = %s", [OGRENCI_AD, ogrenci.pk]
            )
        cikti = self._kosu("resume", password=PAROLA, force=True)
        assert "Geçiş tamamlandı" in cikti
