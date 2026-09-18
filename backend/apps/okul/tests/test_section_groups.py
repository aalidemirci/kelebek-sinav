"""Şube kümesi testleri (ClassSectionGroup) — SAY/EA/DİL seçim kolaylığı.

Kapsam: teklik kısıtının soft-delete koşulu, Türk alfabesi sıralaması, TOPLU
atama ucu (asıl maliyet düşürücü) ve kümenin silinmesinin şubeyi SİLMEMESİ.
Sözleşme: küme YALNIZ seçim aracıdır — hiçbir oturum kaydına küme kimliği
yazılmaz; bu dosyada da oturum tarafına hiç dokunulmaz.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.okul import selectors
from apps.okul.models import ClassSection, ClassSectionGroup, SchoolYear
from apps.okul.services import sections as section_service

pytestmark = pytest.mark.django_db


def _yil() -> SchoolYear:
    yil: SchoolYear = SchoolYear.objects.create(
        name="2026-2027",
        start_date="2026-09-01",
        end_date="2027-06-30",
        is_active=True,
    )
    return yil


def _sube(yil: SchoolYear, level: int, harf: str) -> ClassSection:
    sube: ClassSection = ClassSection.objects.create(
        school_year=yil, class_level=level, class_section=harf
    )
    return sube


def test_kume_adi_canli_kayitlarda_tekil() -> None:
    ClassSectionGroup.objects.create(name="Sayısal")
    with pytest.raises(IntegrityError):
        ClassSectionGroup.objects.create(name="Sayısal")


def test_silinen_kumenin_adi_yeniden_kullanilabilir() -> None:
    kume = ClassSectionGroup.objects.create(name="Dil")
    kume.delete()  # soft delete
    yeni = ClassSectionGroup.objects.create(name="Dil")
    assert yeni.pk != kume.pk and ClassSectionGroup.objects.count() == 1


def test_siralama_once_sira_sonra_turk_alfabesi() -> None:
    ClassSectionGroup.objects.create(name="Çocuk Gelişimi", order=1)
    ClassSectionGroup.objects.create(name="Sayısal", order=0)
    ClassSectionGroup.objects.create(name="Şube Rehberliği", order=1)
    ClassSectionGroup.objects.create(name="Dil", order=1)
    assert [g.name for g in selectors.class_section_groups_sorted()] == [
        "Sayısal",  # order=0 önce
        "Çocuk Gelişimi",  # order=1 içinde Türk alfabesi: Ç < D < Ş
        "Dil",
        "Şube Rehberliği",
    ]


def test_kume_silinince_sube_kumesiz_kalir_ama_silinmez() -> None:
    yil = _yil()
    kume = ClassSectionGroup.objects.create(name="Eşit Ağırlık")
    sube = _sube(yil, 11, "A")
    section_service.assign_section_group(section_ids=[sube.pk], group_id=kume.pk)
    sube.refresh_from_db()
    assert sube.group_id == kume.pk

    section_service.delete_section_group(kume)
    sube.refresh_from_db()
    assert sube.group_id is None
    assert ClassSection.objects.filter(pk=sube.pk).exists()  # şube DURUYOR


def test_toplu_atama_ve_kumeden_cikarma() -> None:
    yil = _yil()
    kume = ClassSectionGroup.objects.create(name="Sayısal")
    subeler = [_sube(yil, 11, harf) for harf in ("A", "B", "C")]

    etkilenen = section_service.assign_section_group(
        section_ids=[s.pk for s in subeler], group_id=kume.pk
    )
    assert etkilenen == 3
    assert ClassSection.objects.filter(group=kume).count() == 3

    # group_id=None → kümeden çıkarır (aynı uç, ters yön).
    assert section_service.assign_section_group(section_ids=[subeler[0].pk], group_id=None) == 1
    assert ClassSection.objects.filter(group=kume).count() == 2
    # Boş liste hiçbir şey yapmaz (idempotent toplu işlem).
    assert section_service.assign_section_group(section_ids=[], group_id=kume.pk) == 0


def test_api_kume_crud_ve_toplu_atama() -> None:
    yil = _yil()
    subeler = [_sube(yil, 12, harf) for harf in ("A", "B")]
    client = APIClient()

    olustur = client.post(
        "/api/v1/class-section-groups/", {"name": "  Eşit   Ağırlık  "}, format="json"
    )
    assert olustur.status_code == 201
    assert olustur.data["name"] == "Eşit Ağırlık"  # fazla boşluk katlanır
    assert olustur.data["section_count"] == 0
    kume_id = olustur.data["id"]

    tekrar = client.post("/api/v1/class-section-groups/", {"name": "Eşit Ağırlık"}, format="json")
    assert tekrar.status_code == 400 and "zaten kayıtlı" in str(tekrar.data)

    ata = client.post(
        "/api/v1/class-section-groups/assign/",
        {"section_ids": [s.pk for s in subeler], "group": kume_id},
        format="json",
    )
    assert ata.status_code == 200 and ata.data["updated"] == 2

    liste = client.get("/api/v1/class-section-groups/")
    kayitlar = liste.data["results"] if isinstance(liste.data, dict) else liste.data
    assert kayitlar[0]["section_count"] == 2

    # Şube listesi küme adını çözülü döndürür (FE çipleri bunu kullanır).
    subeler_yanit = client.get("/api/v1/class-sections/")
    satirlar = (
        subeler_yanit.data["results"]
        if isinstance(subeler_yanit.data, dict)
        else subeler_yanit.data
    )
    assert {r["group_name"] for r in satirlar} == {"Eşit Ağırlık"}

    assert client.delete(f"/api/v1/class-section-groups/{kume_id}/").status_code == 204
    assert ClassSection.objects.filter(group_id=kume_id).count() == 0


# ---------------------------------------------------------------------------
# Küme düzenleme + toplu atamanın ret/eksik girdi dalları
# ---------------------------------------------------------------------------


def _eskit(kume: ClassSectionGroup) -> datetime:
    """`updated_at`'i geçmişe çeker → sonraki yazmanın damgayı yenilediği ölçülebilir."""
    eski = timezone.now() - timedelta(days=3)
    ClassSectionGroup.objects.filter(pk=kume.pk).update(updated_at=eski)
    kume.refresh_from_db()
    return eski


def test_kume_guncelleme_degisen_alani_yazar_ve_damgayi_yeniler() -> None:
    """`save(update_fields=…)` `auto_now`'ı kendiliğinden yazmaz — damga elle eklenir."""
    kume = section_service.create_section_group(name="Sayısal", order=2)
    eski = _eskit(kume)

    section_service.update_section_group(kume, name="Sayısal (MF)")

    kume.refresh_from_db()
    assert (kume.name, kume.order) == ("Sayısal (MF)", 2)
    assert kume.updated_at > eski


def test_kume_guncelleme_degisiklik_yoksa_yazmaz() -> None:
    kume = section_service.create_section_group(name="Dil", order=1)
    eski = _eskit(kume)

    section_service.update_section_group(kume, name="Dil", order=1)

    kume.refresh_from_db()
    assert kume.updated_at == eski


def test_toplu_atama_olmayan_kumeyi_reddeder() -> None:
    """Küme yoksa (ya da SİLİNMİŞSE) şubeler yetim bir kimliğe bağlanmaz."""
    yil = _yil()
    sube = _sube(yil, 11, "A")
    silinmis = ClassSectionGroup.objects.create(name="Dil")
    silinmis.delete()

    for kume_id in (999_999, silinmis.pk):
        with pytest.raises(ValidationError, match="Şube kümesi bulunamadı"):
            section_service.assign_section_group(section_ids=[sube.pk], group_id=kume_id)

    sube.refresh_from_db()
    assert sube.group_id is None


def test_toplu_atama_bilinmeyen_subeyi_sessizce_atlar() -> None:
    """İdempotent toplu iş deseni: dönüş ETKİLENEN satır sayısıdır, gönderilen değil."""
    yil = _yil()
    kume = ClassSectionGroup.objects.create(name="Sayısal")
    sube = _sube(yil, 11, "A")

    etkilenen = section_service.assign_section_group(
        section_ids=[sube.pk, 999_999], group_id=kume.pk
    )

    assert etkilenen == 1


def test_sube_baska_kumeye_alininca_eskisinden_cikar() -> None:
    """Üyelik TEKTİR: şube en çok bir kümededir, ikinci atama taşımadır."""
    yil = _yil()
    sayisal = ClassSectionGroup.objects.create(name="Sayısal")
    esit = ClassSectionGroup.objects.create(name="Eşit Ağırlık")
    sube = _sube(yil, 11, "A")
    section_service.assign_section_group(section_ids=[sube.pk], group_id=sayisal.pk)

    section_service.assign_section_group(section_ids=[sube.pk], group_id=esit.pk)

    assert list(sayisal.sections.all()) == []
    assert [s.pk for s in esit.sections.all()] == [sube.pk]


def test_api_kume_yeniden_adlandirma_teklik_kendini_saymaz() -> None:
    """PATCH'te teklik denetimi kaydın KENDİSİNİ dışlar; başka kümenin adı yine reddedilir."""
    client = APIClient()
    sayisal = ClassSectionGroup.objects.create(name="Sayısal")
    ClassSectionGroup.objects.create(name="Dil")
    url = f"/api/v1/class-section-groups/{sayisal.pk}/"

    ayni_ad = client.patch(url, {"name": "Sayısal", "order": 3}, format="json")
    assert ayni_ad.status_code == 200 and ayni_ad.json()["order"] == 3

    cakisan = client.patch(url, {"name": "  Dil "}, format="json")
    assert cakisan.status_code == 400
    assert "zaten kayıtlı" in str(cakisan.json()["fields"]["name"])

    yeni_ad = client.patch(url, {"name": "Sayısal  (MF)"}, format="json")
    assert yeni_ad.status_code == 200 and yeni_ad.json()["name"] == "Sayısal (MF)"


def test_api_toplu_atama_gecersiz_govdeyi_reddeder() -> None:
    """Olmayan küme ve liste olmayan şube alanı 400'dür; hiçbir şube değişmez."""
    yil = _yil()
    sube = _sube(yil, 12, "A")
    client = APIClient()
    url = "/api/v1/class-section-groups/assign/"

    olmayan = client.post(url, {"section_ids": [sube.pk], "group": 999_999}, format="json")
    assert olmayan.status_code == 400 and "group" in olmayan.json()["fields"]

    bozuk = client.post(url, {"section_ids": "hepsi", "group": None}, format="json")
    assert bozuk.status_code == 400 and "section_ids" in bozuk.json()["fields"]

    sube.refresh_from_db()
    assert sube.group_id is None


def test_api_toplu_atama_null_kume_subeyi_kumeden_cikarir() -> None:
    yil = _yil()
    kume = ClassSectionGroup.objects.create(name="Sayısal")
    sube = _sube(yil, 12, "A")
    section_service.assign_section_group(section_ids=[sube.pk], group_id=kume.pk)

    yanit = APIClient().post(
        "/api/v1/class-section-groups/assign/",
        {"section_ids": [sube.pk], "group": None},
        format="json",
    )

    assert yanit.status_code == 200 and yanit.json() == {"updated": 1}
    sube.refresh_from_db()
    assert sube.group_id is None
