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
