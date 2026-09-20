"""Öğrenci/personel ELLE kayıt işlemleri (F1-T6; tasarım §4.7/6) — servis + uç.

İçe aktarma yolu `test_imports.py`'da sınanır; burada sicil ekranının elle
ekleme/düzeltme/silme yolu sabitlenir. Üç sözleşme:

- Güncelleme YALNIZ değişen alanı yazar ve `updated_at`'i elle damgalar
  (`save(update_fields=…)` `auto_now` alanını kendiliğinden yazmaz).
- Silme SOFT'tur: kayıt arşiv evrakı için durur, canlı listeden düşer ve okul
  numarası yeniden kullanılabilir.
- Elle giriş içe aktarmayla AYNI katlamadan geçer: şube harfi Türkçe büyütülür
  ('i' → 'İ'), seviye okul türünün kümesine karşı doğrulanır (U4).

Tüm ad ve numaralar uydurmadır (KVKK).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.okul.models import Personnel, Student, StudentStatus, SubjectDepartment
from apps.okul.services import persons
from apps.okul.services import setup as setup_service

pytestmark = pytest.mark.django_db

OGRENCI_URL = "/api/v1/students/"
PERSONEL_URL = "/api/v1/personnel/"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _ogrenci(**alanlar: Any) -> Student:
    varsayilan: dict[str, Any] = {
        "first_name": "DENEME",
        "last_name": "ÖĞRENCİ",
        "student_number": "501",
        "class_level": 9,
        "class_section": "A",
    }
    varsayilan.update(alanlar)
    return persons.create_student(**varsayilan)


def _personel(**alanlar: Any) -> Personnel:
    varsayilan: dict[str, Any] = {
        "first_name": "DENEME",
        "last_name": "ÖĞRETMEN",
        "title": "Öğretmen",
        "branch": "Coğrafya",
    }
    varsayilan.update(alanlar)
    return persons.create_personnel(**varsayilan)


def _eskit(kayit: Student | Personnel) -> Any:
    """`updated_at`'i geçmişe çeker → sonraki yazmanın damgayı yenilediği ölçülebilir."""
    eski = timezone.now() - timedelta(days=3)
    type(kayit).objects.filter(pk=kayit.pk).update(updated_at=eski)
    kayit.refresh_from_db()
    return eski


def _sonuclar(yanit: Any) -> list[dict[str, Any]]:
    veri = yanit.json()
    return list(veri["results"]) if isinstance(veri, dict) else list(veri)


# ---------------------------------------------------------------------------
# Servis — öğrenci
# ---------------------------------------------------------------------------


def test_ogrenci_olusturulur_ve_evrak_etiketleri_turetilir() -> None:
    """Evrak sözleşmesi üç alandır: `full_name`, `student_number`, `class_label`."""
    ogrenci = _ogrenci()

    ogrenci.refresh_from_db()
    assert ogrenci.full_name == "DENEME ÖĞRENCİ"
    assert ogrenci.class_label == "9/A"
    assert ogrenci.status == StudentStatus.ACTIVE


def test_ogrenci_guncelleme_degisen_alani_yazar_ve_damgayi_yeniler() -> None:
    """`save(update_fields=…)` `auto_now`'ı kendiliğinden yazmaz — damga elle eklenir."""
    ogrenci = _ogrenci()
    eski = _eskit(ogrenci)

    persons.update_student(ogrenci, class_section="B")

    ogrenci.refresh_from_db()
    assert ogrenci.class_label == "9/B"
    assert ogrenci.updated_at > eski


def test_ogrenci_guncelleme_degisiklik_yoksa_yazmaz() -> None:
    """Aynı değerle gelen kayıt isteği veritabanına dokunmaz (damga eskide kalır)."""
    ogrenci = _ogrenci()
    eski = _eskit(ogrenci)

    persons.update_student(ogrenci, class_section="A", student_number="501")

    ogrenci.refresh_from_db()
    assert ogrenci.updated_at == eski


def test_ogrenci_guncelleme_dokunulmayan_alani_ezmez() -> None:
    """Yalnız DEĞİŞEN alan yazılır: bellekteki bayat kopya başka alanı geri sarmaz.

    Senaryo: sicil ekranı açıkken içe aktarma öğrenciyi "ayrıldı" yaptı; ekranda
    yalnız şubesi düzeltilip kaydedilince durum yeniden AKTİF'e dönmemeli.
    """
    ogrenci = _ogrenci()
    Student.objects.filter(pk=ogrenci.pk).update(status=StudentStatus.LEFT)

    persons.update_student(ogrenci, class_section="C")  # `ogrenci` bellekte hâlâ ACTIVE

    ogrenci.refresh_from_db()
    assert ogrenci.class_section == "C"
    assert ogrenci.status == StudentStatus.LEFT


def test_ogrenci_silme_softtur_ve_okul_numarasi_yeniden_kullanilir() -> None:
    """Arşiv evrakı için kayıt durur; numara teklik kısıtı yalnız CANLI kayıtları sayar."""
    ogrenci = _ogrenci(student_number="777")

    persons.delete_student(ogrenci)

    assert not Student.objects.filter(pk=ogrenci.pk).exists()
    assert Student.all_objects.get(pk=ogrenci.pk).deleted_at is not None
    yeni = _ogrenci(student_number="777", first_name="BAŞKA")
    assert yeni.pk != ogrenci.pk


# ---------------------------------------------------------------------------
# Servis — personel
# ---------------------------------------------------------------------------


def test_personel_olusturulur_ve_varsayilan_aktiftir() -> None:
    """Gözetmen havuzu aktif personelden türer — yeni kayıt havuza doğrudan girer."""
    kisi = _personel()

    kisi.refresh_from_db()
    assert kisi.full_name == "DENEME ÖĞRETMEN"
    assert kisi.is_active is True


def test_personel_guncelleme_degisen_alani_yazar_ve_damgayi_yeniler() -> None:
    kisi = _personel()
    eski = _eskit(kisi)

    persons.update_personnel(kisi, branch="Tarih", is_active=False)

    kisi.refresh_from_db()
    assert (kisi.branch, kisi.is_active) == ("Tarih", False)
    assert kisi.updated_at > eski


def test_personel_guncelleme_degisiklik_yoksa_yazmaz() -> None:
    kisi = _personel()
    eski = _eskit(kisi)

    persons.update_personnel(kisi, branch="Coğrafya", title="Öğretmen")

    kisi.refresh_from_db()
    assert kisi.updated_at == eski


def test_personel_guncelleme_dokunulmayan_alani_ezmez() -> None:
    """Bayat kopya üzerinden branş düzeltmek, pasifleştirmeyi geri almaz."""
    kisi = _personel()
    Personnel.objects.filter(pk=kisi.pk).update(is_active=False)

    persons.update_personnel(kisi, branch="Tarih")  # `kisi` bellekte hâlâ aktif

    kisi.refresh_from_db()
    assert (kisi.branch, kisi.is_active) == ("Tarih", False)


def test_zumre_baskani_personel_silinebilir() -> None:
    """Silme soft olduğundan `on_delete=PROTECT` TETİKLENMEZ: okuldan ayrılan zümre
    başkanı sicilden düşürülebilir (evrak yolu silinmiş başkanı ayrıca eler)."""
    baskan = _personel()
    zumre = SubjectDepartment.objects.create(name="Sosyal Bilimler", head=baskan)

    persons.delete_personnel(baskan)

    assert not Personnel.objects.filter(pk=baskan.pk).exists()
    assert Personnel.all_objects.filter(pk=baskan.pk).exists()
    zumre.refresh_from_db()
    assert zumre.head_id == baskan.pk  # bağ durur; canlılığı okuyan taraf denetler


# ---------------------------------------------------------------------------
# Uç — öğrenci
# ---------------------------------------------------------------------------


def test_api_ogrenci_ekleme_sube_harfini_turkce_buyutur(client: APIClient) -> None:
    """'i' → 'İ' (çıplak `.upper()` 'I' yapardı): 10/I ile 10/İ AYRI şubelerdir."""
    yanit = client.post(
        OGRENCI_URL,
        {
            "first_name": "DENEME",
            "last_name": "ÖĞRENCİ",
            "student_number": "601",
            "class_level": 10,
            "class_section": " i ",
        },
        format="json",
    )

    assert yanit.status_code == 201
    assert yanit.json()["class_section"] == "İ"
    assert yanit.json()["class_label"] == "10/İ"
    assert yanit.json()["full_name"] == "DENEME ÖĞRENCİ"
    assert Student.objects.get(student_number="601").class_section == "İ"


def test_api_ogrenci_seviyesi_okul_turunun_kumesine_karsi_dogrulanir(client: APIClient) -> None:
    """Sabit 9-12 aralığı YOK (U4): küme okul yapılandırmasından gelir, mesaj onu sayar."""
    govde = {"first_name": "DENEME", "last_name": "ÖĞRENCİ", "class_section": "A"}

    ortaokul = client.post(OGRENCI_URL, {**govde, "class_level": 8}, format="json")
    assert ortaokul.status_code == 400
    assert "9, 10, 11, 12" in str(ortaokul.json()["fields"]["class_level"])

    # Hazırlık kapalıyken 0 da geçersizdir; açılınca kabul edilir ve etiketi "Hz/…" olur.
    assert client.post(OGRENCI_URL, {**govde, "class_level": 0}, format="json").status_code == 400
    setup_service.update_school_config(fields={"has_prep_class": True})
    hazirlik = client.post(OGRENCI_URL, {**govde, "class_level": 0}, format="json")
    assert hazirlik.status_code == 201
    assert hazirlik.json()["class_label"] == "Hz/A"

    hata = client.post(OGRENCI_URL, {**govde, "class_level": 8}, format="json")
    assert "Hazırlık, 9, 10, 11, 12" in str(hata.json()["fields"]["class_level"])


def test_api_sinifsiz_ogrenci_kaydedilebilir(client: APIClient) -> None:
    """Sınıfı henüz belli olmayan (nakil gelen) öğrenci sicile girebilir; etiketi boştur."""
    yanit = client.post(
        OGRENCI_URL,
        {"first_name": "DENEME", "last_name": "NAKİL", "class_level": None, "class_section": "  "},
        format="json",
    )

    assert yanit.status_code == 201
    assert yanit.json()["class_level"] is None
    assert yanit.json()["class_section"] == ""
    assert yanit.json()["class_label"] == ""


def test_api_aktif_ogrencide_okul_numarasi_tekildir(client: APIClient) -> None:
    """Numara içe aktarmanın UPSERT anahtarıdır: aktif iki kayıt aynı numarayı taşıyamaz.

    Çakışma 500 (IntegrityError) DEĞİL 400'dür; ayrılan öğrencinin numarası ise
    yeni öğrenciye verilebilir (kısıt yalnız AKTİF canlı kayıtları sayar).
    """
    _ogrenci(student_number="900")
    govde = {
        "first_name": "BAŞKA",
        "last_name": "ÖĞRENCİ",
        "student_number": "900",
        "class_level": 9,
        "class_section": "A",
    }

    cakisma = client.post(OGRENCI_URL, govde, format="json")
    assert cakisma.status_code == 400
    assert "student_number" in cakisma.json()["fields"]

    Student.objects.filter(student_number="900").update(status=StudentStatus.LEFT)
    assert client.post(OGRENCI_URL, govde, format="json").status_code == 201


def test_api_ogrenci_duzeltme_ve_silme(client: APIClient) -> None:
    ogrenci = _ogrenci()

    duzelt = client.patch(f"{OGRENCI_URL}{ogrenci.pk}/", {"class_section": "ç"}, format="json")
    assert duzelt.status_code == 200
    assert duzelt.json()["class_label"] == "9/Ç"
    assert duzelt.json()["student_number"] == "501"  # gönderilmeyen alan korunur

    assert client.delete(f"{OGRENCI_URL}{ogrenci.pk}/").status_code == 204
    assert _sonuclar(client.get(OGRENCI_URL)) == []
    kayip = client.get(f"{OGRENCI_URL}{ogrenci.pk}/")
    assert kayip.status_code == 404
    assert kayip.json() == {"code": "not_found", "message": "Kayıt bulunamadı.", "fields": {}}


def test_api_ogrenci_listesi_suzgecleri(client: APIClient) -> None:
    """Sicil ekranı ayrılanı da gösterir; `only_active` yalnız seçicilerin opt-in süzgecidir."""
    _ogrenci(student_number="101", class_section="Ş", first_name="IŞIL")
    _ogrenci(student_number="102", class_level=10, first_name="ÇAĞRI")
    ayrilan = _ogrenci(student_number="103", first_name="AYRILAN")
    Student.objects.filter(pk=ayrilan.pk).update(status=StudentStatus.LEFT)

    def numaralar(**params: str) -> set[str]:
        return {s["student_number"] for s in _sonuclar(client.get(OGRENCI_URL, params))}

    assert numaralar() == {"101", "102", "103"}
    assert numaralar(only_active="true") == {"101", "102"}
    assert numaralar(class_level="10") == {"102"}
    # Şube süzgeci kayıtla AYNI katlamadan geçer: küçük 'ş' ile aranan 'Ş' bulunur.
    assert numaralar(class_section="ş") == {"101"}
    # Ad şifreli → arama Python'da ve Türkçe katlamalı ('isil' → 'IŞIL').
    assert numaralar(search="isil") == {"101"}
    assert numaralar(search="102") == {"102"}

    bozuk = client.get(OGRENCI_URL, {"class_level": "dokuz"})
    assert bozuk.status_code == 400
    assert "sayısal" in str(bozuk.json()["fields"]["class_level"])


# ---------------------------------------------------------------------------
# Uç — personel
# ---------------------------------------------------------------------------


def test_api_personel_ekleme_duzeltme_ve_silme(client: APIClient) -> None:
    ekle = client.post(
        PERSONEL_URL,
        {"first_name": "DENEME", "last_name": "ÖĞRETMEN", "branch": "Coğrafya"},
        format="json",
    )
    assert ekle.status_code == 201
    assert ekle.json()["full_name"] == "DENEME ÖĞRETMEN"
    assert ekle.json()["is_active"] is True
    kisi_id = ekle.json()["id"]

    # Pasifleştirme gözetmen havuzundan düşürür ama sicilde bırakır.
    pasif = client.patch(f"{PERSONEL_URL}{kisi_id}/", {"is_active": False}, format="json")
    assert pasif.status_code == 200 and pasif.json()["is_active"] is False
    assert [p["id"] for p in _sonuclar(client.get(PERSONEL_URL))] == [kisi_id]
    assert _sonuclar(client.get(PERSONEL_URL, {"only_active": "true"})) == []

    assert client.delete(f"{PERSONEL_URL}{kisi_id}/").status_code == 204
    assert _sonuclar(client.get(PERSONEL_URL)) == []
    assert Personnel.all_objects.filter(pk=kisi_id).exists()  # soft


def test_api_personel_ad_soyad_zorunludur(client: APIClient) -> None:
    yanit = client.post(PERSONEL_URL, {"branch": "Coğrafya"}, format="json")

    assert yanit.status_code == 400
    assert yanit.json()["code"] == "validation_error"
    assert set(yanit.json()["fields"]) == {"first_name", "last_name"}


def test_api_personel_aramasi_ad_unvan_ve_bransta_turkce_katlar(client: APIClient) -> None:
    _personel(first_name="ÇAĞLA", last_name="ÖRNEK", title="Müdür Yardımcısı", branch="Fizik")
    _personel(first_name="DENEME", last_name="ÖĞRETMEN", title="Öğretmen", branch="Coğrafya")

    def adlar(aranan: str) -> list[str]:
        return [p["first_name"] for p in _sonuclar(client.get(PERSONEL_URL, {"search": aranan}))]

    assert adlar("cagla") == ["ÇAĞLA"]
    assert adlar("mudur") == ["ÇAĞLA"]
    assert adlar("cografya") == ["DENEME"]
    assert adlar("olmayan") == []


# ---------------------------------------------------------------------------
# Unutma kancaları (20.09.2026) — okul DIŞI uygulamaların kişisel veri temizliği
# ---------------------------------------------------------------------------


def test_unutma_kancasi_pasiflesen_ve_silinen_ogrencide_calisir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bağımlılık yönü sinav → okul'dur: okul kancayı ÇAĞIRIR, kimin dinlediğini bilmez."""
    cagrilar: list[int] = []
    monkeypatch.setattr(persons, "_forget_hooks", [])
    persons.register_student_forget_hook(cagrilar.append)
    persons.register_student_forget_hook(cagrilar.append)  # idempotent kayıt

    aktif = _ogrenci(student_number="901")
    persons.update_student(aktif, class_section="B")
    assert cagrilar == [], "aktif öğrencinin düzeltmesi veri sildirmez"

    persons.update_student(aktif, status=StudentStatus.LEFT)
    assert cagrilar == [aktif.pk]

    silinecek = _ogrenci(student_number="902")
    persons.delete_student(silinecek)
    assert cagrilar == [aktif.pk, silinecek.pk]


def test_unutma_kancasi_hata_verirse_durum_degisikligi_geri_sarilir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kanca AYNI işlemde koşar: temizlik başarısızsa öğrenci de pasifleşmiş sayılmaz."""

    def _patla(_student_id: int) -> None:
        raise RuntimeError("temizlik başarısız")

    monkeypatch.setattr(persons, "_forget_hooks", [_patla])
    ogrenci = _ogrenci(student_number="903")
    with pytest.raises(RuntimeError):
        persons.update_student(ogrenci, status=StudentStatus.LEFT)
    ogrenci.refresh_from_db()
    assert ogrenci.status == StudentStatus.ACTIVE
