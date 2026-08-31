"""Derslik kümesi testleri (ExamRoomGroup) — Sabah/Öğle seçim kolaylığı.

Gerekçe (kullanıcı, 31.08.2026): ikili eğitimde `generate_section_rooms` her
şube için bir derslik üretir; sihirbazda tek tek işaretlemek zorlaşır.

Kapsam: teklik kısıtının soft-delete koşulu, Türk alfabesi sıralaması, TOPLU
atama ucu, kümenin silinmesinin salonu SİLMEMESİ ve kümenin `block` alanından
BAĞIMSIZ olması (blok resmî evraka basılır, küme basılmaz).
"""

from __future__ import annotations

import pytest
from django.db.utils import IntegrityError
from rest_framework.test import APIClient

from apps.sinav import selectors, services
from apps.sinav.models import ExamRoom, ExamRoomGroup

pytestmark = pytest.mark.django_db


def _salon(ad: str, block: str = "") -> ExamRoom:
    return services.create_exam_room(name=ad, block=block)


def test_kume_adi_canli_kayitlarda_tekil() -> None:
    ExamRoomGroup.objects.create(name="Sabah")
    with pytest.raises(IntegrityError):
        ExamRoomGroup.objects.create(name="Sabah")


def test_silinen_kumenin_adi_yeniden_kullanilabilir() -> None:
    kume = ExamRoomGroup.objects.create(name="Öğle")
    kume.delete()  # soft delete
    yeni = ExamRoomGroup.objects.create(name="Öğle")
    assert yeni.pk != kume.pk and ExamRoomGroup.objects.count() == 1


def test_siralama_once_sira_sonra_turk_alfabesi() -> None:
    ExamRoomGroup.objects.create(name="Öğle", order=1)
    ExamRoomGroup.objects.create(name="Sabah", order=0)
    ExamRoomGroup.objects.create(name="Çatı Katı", order=1)
    assert [g.name for g in selectors.exam_room_groups_sorted()] == [
        "Sabah",  # order=0
        "Çatı Katı",  # order=1 içinde Türk alfabesi: Ç < Ö
        "Öğle",
    ]


def test_kume_silinince_salon_kumesiz_kalir_ama_silinmez() -> None:
    kume = ExamRoomGroup.objects.create(name="Sabah")
    salon = _salon("D-101")
    services.assign_room_group(room_ids=[salon.pk], group_id=kume.pk)
    salon.refresh_from_db()
    assert salon.group_id == kume.pk

    services.delete_room_group(kume)
    salon.refresh_from_db()
    assert salon.group_id is None
    assert ExamRoom.objects.filter(pk=salon.pk).exists()  # salon DURUYOR


def test_kume_blok_alanindan_bagimsiz() -> None:
    """Blok resmî salon evrakına basılır; küme YALNIZ seçim aracıdır."""
    kume = ExamRoomGroup.objects.create(name="Öğle")
    salon = _salon("D-102", block="A Blok 2. Kat")
    services.assign_room_group(room_ids=[salon.pk], group_id=kume.pk)
    salon.refresh_from_db()
    assert salon.block == "A Blok 2. Kat"  # küme ataması bloğa DOKUNMAZ
    assert salon.group is not None and salon.group.name == "Öğle"


def test_toplu_atama_ve_kumeden_cikarma() -> None:
    kume = ExamRoomGroup.objects.create(name="Sabah")
    salonlar = [_salon(f"D-10{i}") for i in range(3)]

    assert services.assign_room_group(room_ids=[s.pk for s in salonlar], group_id=kume.pk) == 3
    assert ExamRoom.objects.filter(group=kume).count() == 3

    assert services.assign_room_group(room_ids=[salonlar[0].pk], group_id=None) == 1
    assert ExamRoom.objects.filter(group=kume).count() == 2
    assert services.assign_room_group(room_ids=[], group_id=kume.pk) == 0


def test_api_kume_crud_ve_toplu_atama() -> None:
    salonlar = [_salon("D-201"), _salon("D-202")]
    client = APIClient()

    olustur = client.post("/api/v1/exam-room-groups/", {"name": "  Sabah  "}, format="json")
    assert olustur.status_code == 201
    assert olustur.data["name"] == "Sabah" and olustur.data["room_count"] == 0
    kume_id = olustur.data["id"]

    tekrar = client.post("/api/v1/exam-room-groups/", {"name": "Sabah"}, format="json")
    assert tekrar.status_code == 400 and "zaten kayıtlı" in str(tekrar.data)

    ata = client.post(
        "/api/v1/exam-room-groups/assign/",
        {"room_ids": [s.pk for s in salonlar], "group": kume_id},
        format="json",
    )
    assert ata.status_code == 200 and ata.data["updated"] == 2

    liste = client.get("/api/v1/exam-room-groups/")
    kayitlar = liste.data["results"] if isinstance(liste.data, dict) else liste.data
    assert kayitlar[0]["room_count"] == 2

    # Salon listesi küme adını çözülü döndürür (sihirbaz çipleri bunu kullanır).
    salon_yanit = client.get("/api/v1/exam-rooms/")
    satirlar = (
        salon_yanit.data["results"] if isinstance(salon_yanit.data, dict) else salon_yanit.data
    )
    assert {r["group_name"] for r in satirlar} == {"Sabah"}

    assert client.delete(f"/api/v1/exam-room-groups/{kume_id}/").status_code == 204
    assert ExamRoom.objects.filter(group_id=kume_id).count() == 0
