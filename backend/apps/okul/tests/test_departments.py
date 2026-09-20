"""Zümre kataloğu testleri (SubjectDepartment).

Kapsam: teklik kısıtının soft-delete koşulu, Türk alfabesi sıralaması (zümre
adı düz metin ama SQLite karşılaştırması BINARY), başkanın ŞİFRELİ addan
çözülmesi ve API sözleşmesi (Türkçe teklik mesajı — DRF'in İngilizcesi değil).
"""

from __future__ import annotations

import pytest
from django.db.utils import IntegrityError
from rest_framework.test import APIClient

from apps.okul import selectors
from apps.okul.models import Personnel, SubjectDepartment
from apps.okul.services import departments

pytestmark = pytest.mark.django_db


def test_zumre_adi_canli_kayitlarda_tekil() -> None:
    SubjectDepartment.objects.create(name="Sosyal Bilimler")
    with pytest.raises(IntegrityError):
        SubjectDepartment.objects.create(name="Sosyal Bilimler")


def test_silinen_zumrenin_adi_yeniden_kullanilabilir() -> None:
    zumre = SubjectDepartment.objects.create(name="Matematik")
    zumre.delete()  # soft delete — koşullu kısıt canlıları sayar
    yeni = SubjectDepartment.objects.create(name="Matematik")
    assert yeni.pk != zumre.pk
    assert SubjectDepartment.objects.count() == 1


def test_baskan_sifreli_addan_cozulur() -> None:
    baskan = Personnel.objects.create(first_name="Ayşe", last_name="ÇELİK")
    zumre = SubjectDepartment.objects.create(name="Coğrafya", head=baskan)
    zumre.refresh_from_db()
    assert zumre.head is not None and zumre.head.get_full_name() == "Ayşe ÇELİK"


def test_siralama_turk_alfabesine_gore() -> None:
    """Kod noktası sırasında Ç/Ş 'Z'den sonraya düşerdi — selector Python'da sıralar."""
    for ad in ("Din Kültürü", "Çevre", "Sosyal Bilimler", "Şube Rehberliği"):
        SubjectDepartment.objects.create(name=ad)
    assert [d.name for d in selectors.subject_departments_sorted()] == [
        "Çevre",
        "Din Kültürü",
        "Sosyal Bilimler",
        "Şube Rehberliği",
    ]


def test_kurul_uyeligi_suzgeci() -> None:
    SubjectDepartment.objects.create(name="Matematik")
    SubjectDepartment.objects.create(name="Görsel Sanatlar", is_board_member=False)
    kurul = selectors.subject_departments_sorted(board_only=True)
    assert [d.name for d in kurul] == ["Matematik"]


def test_api_zumre_crud_sozlesmesi() -> None:
    baskan = Personnel.objects.create(first_name="Ayşe", last_name="ÇELİK", branch="Coğrafya")
    client = APIClient()

    olustur = client.post(
        "/api/v1/subject-departments/",
        {"name": "  Sosyal   Bilimler  ", "head": baskan.pk},
        format="json",
    )
    assert olustur.status_code == 201
    assert olustur.data["name"] == "Sosyal Bilimler"  # fazla boşluk katlanır
    assert olustur.data["head_name"] == "Ayşe ÇELİK"
    assert olustur.data["is_board_member"] is True
    dept_id = olustur.data["id"]

    tekrar = client.post("/api/v1/subject-departments/", {"name": "Sosyal Bilimler"}, format="json")
    assert tekrar.status_code == 400
    assert "zaten kayıtlı" in str(tekrar.data)  # Türkçe mesaj

    guncelle = client.patch(
        f"/api/v1/subject-departments/{dept_id}/", {"is_board_member": False}, format="json"
    )
    assert guncelle.status_code == 200 and guncelle.data["is_board_member"] is False

    # Başkanı boş zümrenin PATCH yanıtında da `head_name` ANAHTARI bulunmalı:
    # `CharField(source=..., default="")` partial serializer'da SkipField atıp
    # anahtarı düşürürdü (FE tipi bu alanı zorunlu sayıyor).
    baskansiz = client.post("/api/v1/subject-departments/", {"name": "Matematik"}, format="json")
    assert baskansiz.status_code == 201 and baskansiz.data["head_name"] == ""
    yama = client.patch(
        f"/api/v1/subject-departments/{baskansiz.data['id']}/",
        {"is_board_member": False},
        format="json",
    )
    assert yama.status_code == 200 and yama.data["head_name"] == ""

    listele = client.get("/api/v1/subject-departments/?board_only=true")
    assert listele.status_code == 200
    kayitlar = listele.data["results"] if isinstance(listele.data, dict) else listele.data
    assert kayitlar == []

    assert client.delete(f"/api/v1/subject-departments/{dept_id}/").status_code == 204
    assert SubjectDepartment.objects.filter(pk=dept_id).first() is None


def test_api_zumre_yeniden_adlandirma_teklik_kendini_saymaz() -> None:
    """PATCH'te teklik denetimi kaydın KENDİSİNİ dışlar; başka zümrenin adı yine reddedilir.

    Kendini dışlamayan denetim, adı değişmeyen her düzenlemeyi (başkan atama dâhil)
    "zaten kayıtlı" diye reddederdi.
    """
    baskan = Personnel.objects.create(first_name="DENEME", last_name="ÖĞRETMEN")
    sosyal = SubjectDepartment.objects.create(name="Sosyal Bilimler")
    SubjectDepartment.objects.create(name="Matematik")
    client = APIClient()
    url = f"/api/v1/subject-departments/{sosyal.pk}/"

    ayni_ad = client.patch(url, {"name": "Sosyal Bilimler", "head": baskan.pk}, format="json")
    assert ayni_ad.status_code == 200
    assert ayni_ad.json()["head_name"] == "DENEME ÖĞRETMEN"

    cakisan = client.patch(url, {"name": " Matematik  "}, format="json")
    assert cakisan.status_code == 400
    assert "zaten kayıtlı" in str(cakisan.json()["fields"]["name"])
    sosyal.refresh_from_db()
    assert sosyal.name == "Sosyal Bilimler"


def test_api_zumre_baskani_sicilde_olmayan_personel_olamaz() -> None:
    """Silinmiş (soft) personel başkan seçilemez — evrakta boş imza çizgisi doğardı."""
    ayrilan = Personnel.objects.create(first_name="AYRILAN", last_name="ÖĞRETMEN")
    ayrilan.delete()

    yanit = APIClient().post(
        "/api/v1/subject-departments/", {"name": "Coğrafya", "head": ayrilan.pk}, format="json"
    )

    assert yanit.status_code == 400
    assert "head" in yanit.json()["fields"]
    assert not SubjectDepartment.objects.exists()


# ---------------------------------------------------------------------------
# Branştan zümre üretimi + başkan adaylarının branşa göre süzülmesi (20.09.2026)
# ---------------------------------------------------------------------------


def _ogretmen(ad: str, brans: str, *, aktif: bool = True) -> Personnel:
    kayit: Personnel = Personnel.objects.create(
        first_name=ad, last_name="ÖĞRETMEN", branch=brans, is_active=aktif
    )
    return kayit


def test_brans_anahtari_yazim_farklarini_katlar() -> None:
    anahtar = departments.branch_key("Coğrafya")
    assert anahtar == departments.branch_key("COĞRAFYA") == departments.branch_key(" coğrafya  ")
    # Şapka farkı aynı branştır; ayrı branşlar ayrı kalır.
    assert departments.branch_key("Din Kültürü ve Ahlâk Bilgisi") == departments.branch_key(
        "DİN KÜLTÜRÜ VE AHLAK BİLGİSİ"
    )
    assert departments.branch_key("Fizik") != departments.branch_key("Kimya")
    assert departments.branch_key("") == "" and departments.branch_key(None) == ""


def test_branslardan_zumre_uretimi() -> None:
    _ogretmen("A", "Coğrafya")
    _ogretmen("B", "COĞRAFYA")  # aynı branş, farklı yazım → TEK zümre
    _ogretmen("C", "TÜRK DİLİ VE EDEBİYATI")  # tamamı büyük → başlık biçimi
    _ogretmen("D", "")  # branşsız (memur, hizmetli) aday üretmez
    _ogretmen("E", "Müzik", aktif=False)  # pasif öğretmenin branşı aday değildir

    adaylar = departments.branch_candidates()
    assert [(a.name, a.teacher_count, a.status) for a in adaylar] == [
        ("Coğrafya", 2, departments.STATUS_NEW),
        ("Türk Dili ve Edebiyatı", 1, departments.STATUS_NEW),
    ]

    sonuc = departments.generate_from_branches()
    assert sonuc == {"created": ["Coğrafya", "Türk Dili ve Edebiyatı"], "linked": [], "skipped": []}
    cografya = SubjectDepartment.objects.get(name="Coğrafya")
    assert cografya.branches == ["Coğrafya"] and cografya.is_board_member is True

    # İdempotent: ikinci koşu yeni zümre açmaz, adaylar "kapsanmış" görünür.
    assert departments.generate_from_branches()["created"] == []
    assert SubjectDepartment.objects.count() == 2
    assert {a.status for a in departments.branch_candidates()} == {departments.STATUS_COVERED}


def test_ayni_adli_zumre_yeniden_yaratilmaz_baglanir() -> None:
    """Elle açılmış "Coğrafya" zümresi üretimde BAĞLANIR — ad tekliği çiğnenmez."""
    _ogretmen("A", "Coğrafya")
    elle = SubjectDepartment.objects.create(name="Coğrafya")
    (aday,) = departments.branch_candidates()
    assert aday.status == departments.STATUS_LINKABLE and aday.department_id == elle.pk

    sonuc = departments.generate_from_branches()
    assert sonuc == {"created": [], "linked": ["Coğrafya"], "skipped": []}
    elle.refresh_from_db()
    assert elle.branches == ["Coğrafya"]
    assert SubjectDepartment.objects.count() == 1


def test_birlesik_zumre_branslari_kapsar_ve_secili_uretim() -> None:
    for brans in ("Tarih", "Coğrafya", "Felsefe", "Matematik"):
        _ogretmen(brans[0], brans)
    departments.create_subject_department(
        name="Sosyal Bilimler", branches=["Tarih", "Coğrafya", "Felsefe"]
    )
    durum = {a.name: (a.status, a.department_name) for a in departments.branch_candidates()}
    assert durum["Tarih"] == (departments.STATUS_COVERED, "Sosyal Bilimler")
    assert durum["Matematik"] == (departments.STATUS_NEW, "")

    # Yalnız SEÇİLEN branşlar üretilir (anahtar ya da ad verilebilir — ikisi de katlanır).
    sonuc = departments.generate_from_branches(["MATEMATİK", "Tarih"])
    assert sonuc == {"created": ["Matematik"], "linked": [], "skipped": ["Sosyal Bilimler"]}


def test_bir_brans_en_cok_bir_zumrede() -> None:
    from django.core.exceptions import ValidationError

    departments.create_subject_department(name="Sosyal Bilimler", branches=["Tarih"])
    with pytest.raises(ValidationError, match="Sosyal Bilimler"):
        departments.create_subject_department(name="Tarih", branches=["TARİH"])
    # Zümrenin KENDİ branşı güncellemede çakışma sayılmaz; liste anahtara göre tekilleşir.
    sosyal = SubjectDepartment.objects.get(name="Sosyal Bilimler")
    departments.update_subject_department(sosyal, branches=["Tarih", " tarih ", "Felsefe", ""])
    sosyal.refresh_from_db()
    assert sosyal.branches == ["Tarih", "Felsefe"]
    with pytest.raises(ValidationError, match="liste"):
        departments.clean_branches("Tarih")


def test_katalog_bosken_kendiliginden_uretim() -> None:
    _ogretmen("A", "Fizik")
    assert departments.generate_if_catalog_empty() == {
        "created": ["Fizik"],
        "linked": [],
        "skipped": [],
    }
    # Katalogda zümre varken dokunulmaz: kaldırılan zümre sessizce geri gelmesin.
    _ogretmen("B", "Kimya")
    assert departments.generate_if_catalog_empty() is None
    assert [d.name for d in SubjectDepartment.objects.all()] == ["Fizik"]


def test_api_brans_adaylari_uretim_ve_anahtarlar() -> None:
    ogretmen = _ogretmen("A", "COĞRAFYA")
    _ogretmen("B", "Fizik")
    client = APIClient()

    adaylar = client.get("/api/v1/subject-departments/branch-candidates/")
    assert adaylar.status_code == 200
    assert [a["name"] for a in adaylar.data["candidates"]] == ["Coğrafya", "Fizik"]
    assert set(adaylar.data["candidates"][0]) == {
        "key",
        "name",
        "teacher_count",
        "status",
        "department_id",
        "department_name",
    }

    fizik_anahtari = adaylar.data["candidates"][1]["key"]
    uret = client.post(
        "/api/v1/subject-departments/generate/", {"keys": [fizik_anahtari]}, format="json"
    )
    assert uret.status_code == 200 and uret.data["created"] == ["Fizik"]
    bozuk = client.post("/api/v1/subject-departments/generate/", {"keys": "Fizik"}, format="json")
    assert bozuk.status_code == 400

    # Zümre `branch_keys`, öğretmen `branch_key` taşır: arayüz yalnız EŞİTLİK karşılaştırır.
    zumreler = client.get("/api/v1/subject-departments/").data
    kayitlar = zumreler["results"] if isinstance(zumreler, dict) else zumreler
    assert kayitlar[0]["branches"] == ["Fizik"] and kayitlar[0]["branch_keys"] == [fizik_anahtari]
    personel = client.get(f"/api/v1/personnel/{ogretmen.pk}/").data
    assert personel["branch_key"] == departments.branch_key("Coğrafya")

    # Branşlar PATCH ile düzenlenir; başka zümredeki branş Türkçe gerekçeyle reddedilir.
    tumu = client.post("/api/v1/subject-departments/generate/", {}, format="json")
    assert tumu.data["created"] == ["Coğrafya"]
    cografya = SubjectDepartment.objects.get(name="Coğrafya")
    cakisan = client.patch(
        f"/api/v1/subject-departments/{cografya.pk}/",
        {"branches": ["Coğrafya", "Fizik"]},
        format="json",
    )
    assert cakisan.status_code == 400
    assert "Fizik" in str(cakisan.json())
    bosalt = client.patch(
        f"/api/v1/subject-departments/{cografya.pk}/", {"branches": []}, format="json"
    )
    assert bosalt.status_code == 200 and bosalt.data["branch_keys"] == []


def test_api_ogretmen_aktarimi_bos_katalogda_zumreleri_uretir() -> None:
    client = APIClient()
    satirlar = [
        "Adı\tSoyadı\tGörevi\tBranşı",
        "AYŞE\tÖĞRETMEN\tÖğretmen\tCoğrafya",
        "ALİ\tÖĞRETMEN\tÖğretmen\tFizik",
    ]
    metin = "\n".join(satirlar)

    # Önizleme üretim YAPMAZ.
    onizleme = client.post("/api/v1/imports/personnel/preview/", {"text": metin}, format="json")
    assert onizleme.status_code == 200
    assert SubjectDepartment.objects.count() == 0

    aktar = client.post("/api/v1/imports/personnel/commit/", {"text": metin}, format="json")
    assert aktar.status_code == 200
    assert aktar.data["departments_created"] == ["Coğrafya", "Fizik"]

    # Katalog doluyken ikinci aktarım zümre EKLEMEZ (elle kurulan düzene dokunulmaz).
    ikinci = "\n".join([*satirlar, "VELİ\tÖĞRETMEN\tÖğretmen\tKimya"])
    tekrar = client.post("/api/v1/imports/personnel/commit/", {"text": ikinci}, format="json")
    assert tekrar.status_code == 200 and tekrar.data["departments_created"] == []
    assert SubjectDepartment.objects.count() == 2
