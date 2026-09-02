"""Sınav salonu servis + API testleri — CRUD + koltuk uçları + şube otomasyonu.

OYS `test_room_api.py` + `test_seed_rooms.py`'den KS'ye uyarlandı: RBAC/anonim
senaryoları düştü (authsuz tek kullanıcı), `core.Section` yerine F1 şube
kataloğu (`okul.ClassSection`), boş plan PDF'i testleri F4'te gelir.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.okul.models import ClassSection, SchoolYear, Student
from apps.sinav import layout, selectors, services
from apps.sinav.models import DeskType, ExamRoom, NumberingScheme

pytestmark = pytest.mark.django_db

URL = "/api/v1/exam-rooms/"

PLAN_2X2: dict[str, Any] = {
    "grid": {"rows": 3, "cols": 3},
    "desks": [
        {"row": 0, "col": 0, "type": DeskType.DOUBLE},
        {"row": 1, "col": 0, "type": DeskType.DOUBLE},
        {"row": 0, "col": 2, "type": DeskType.SINGLE},
    ],
    "furniture": [{"kind": "TEACHER_DESK", "row": 2, "col": 2}],
}


def _aktif_yil() -> SchoolYear:
    yil: SchoolYear = SchoolYear.objects.create(
        name="2026-2027",
        start_date=date(2026, 9, 1),
        end_date=date(2027, 6, 30),
        is_active=True,
    )
    return yil


def _sube(yil: SchoolYear, class_level: int, class_section: str, students: int = 0) -> ClassSection:
    sube: ClassSection = ClassSection.objects.create(
        school_year=yil, class_level=class_level, class_section=class_section
    )
    for i in range(students):
        Student.objects.create(
            first_name=f"AD{i}",
            last_name="SOYAD",
            student_number=str(500 + i + class_level * 100),
            class_level=class_level,
            class_section=class_section,
        )
    return sube


# ===========================================================================
# Service
# ===========================================================================


def test_create_room_default_plan_and_duplicate() -> None:
    room = services.create_exam_room(name="  D-204 ")
    assert room.name == "D-204"
    assert services.room_capacity(room) == 0  # varsayılan plan boş
    with pytest.raises(ValidationError, match="zaten kayıtlı"):
        services.create_exam_room(name="D-204")


def test_create_room_invalid_plan_rejected() -> None:
    with pytest.raises(ValidationError):
        services.create_exam_room(name="Lab", layout_plan={"grid": {"rows": 0, "cols": 1}})
    assert selectors.exam_rooms(include_inactive=True).count() == 0  # kayıt yazılmadı


def test_update_room_plan_revalidated() -> None:
    room = services.create_exam_room(name="D-204", layout_plan=PLAN_2X2)
    with pytest.raises(ValidationError):
        services.update_exam_room(room, layout_plan={"grid": {"rows": 1}})
    room.refresh_from_db()
    assert services.room_capacity(room) == 5  # eski plan korunur


def test_update_room_linked_section_sentinel() -> None:
    yil = _aktif_yil()
    section = _sube(yil, 11, "C")
    room = services.create_exam_room(name="11-C Dersliği", linked_section_id=section.pk)
    assert room.linked_section_id == section.pk
    # Sentinel (...): dokunma.
    services.update_exam_room(room, block="A Blok")
    assert room.linked_section_id == section.pk
    # None: açıkça kaldır.
    services.update_exam_room(room, linked_section_id=None)
    assert room.linked_section_id is None
    # Olmayan şube: hata.
    with pytest.raises(ValidationError, match="bulunamadı"):
        services.update_exam_room(room, linked_section_id=99999)


def test_room_seats_uses_scheme() -> None:
    room = services.create_exam_room(name="D-204", layout_plan=PLAN_2X2)
    s_seats = services.room_seats(room)
    assert [s.seat_no for s in s_seats] == [1, 2, 3, 4, 5]
    services.update_exam_room(room, numbering_scheme=NumberingScheme.STRAIGHT)
    straight = services.room_seats(room)
    assert len(straight) == 5
    # Öğretmen masası (2,2) arka-sağda: rota sağ kolondan, arkadan öne başlar.
    assert (s_seats[0].desk_col, s_seats[0].desk_row) == (2, 0)


# ===========================================================================
# API
# ===========================================================================


def test_crud_ve_kapasite() -> None:
    client = APIClient()
    resp = client.post(
        URL,
        {"name": "D-204", "layout_plan": PLAN_2X2, "block": "A Blok"},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["capacity"] == 5
    assert resp.data["numbering_scheme"] == NumberingScheme.S_PATTERN

    room_id = resp.data["id"]
    resp = client.patch(f"{URL}{room_id}/", {"is_active": False}, format="json")
    assert resp.status_code == 200
    assert resp.data["is_active"] is False

    # Pasif salon varsayılan listede görünmez; include_inactive ile görünür.
    assert client.get(URL).data["count"] == 0
    assert client.get(f"{URL}?include_inactive=true").data["count"] == 1

    # Silme ucu bilinçle yok (pasifleştirme deseni).
    assert client.delete(f"{URL}{room_id}/").status_code == 405


def test_api_invalid_plan_400_turkce() -> None:
    resp = APIClient().post(
        URL,
        {
            "name": "Lab",
            "layout_plan": {
                "grid": {"rows": 1, "cols": 1},
                "desks": [{"row": 5, "col": 0, "type": "SINGLE"}],
            },
        },
        format="json",
    )
    assert resp.status_code == 400


def test_api_linked_section_label() -> None:
    yil = _aktif_yil()
    section = _sube(yil, 11, "C")
    client = APIClient()
    resp = client.post(
        URL, {"name": "11-C Dersliği", "linked_section_id": section.pk}, format="json"
    )
    assert resp.status_code == 201
    assert resp.data["linked_section_label"] == "11/C"

    bad = client.post(URL, {"name": "Hayalet", "linked_section_id": 99999}, format="json")
    assert bad.status_code == 400


def test_api_seats_endpoint() -> None:
    room = services.create_exam_room(name="D-204", layout_plan=PLAN_2X2)
    resp = APIClient().get(f"{URL}{room.pk}/seats/")
    assert resp.status_code == 200
    assert resp.data["capacity"] == 5
    assert [s["seat_no"] for s in resp.data["seats"]] == [1, 2, 3, 4, 5]
    assert {"desk_row", "desk_col", "desk_type", "slot", "x", "y"} <= set(resp.data["seats"][0])


def test_api_preview_seats() -> None:
    """Kaydedilmemiş plan önizlemesi: kapasite + seat_no döner, kayıt yazılmaz."""
    client = APIClient()
    resp = client.post(
        f"{URL}preview-seats/",
        {"layout_plan": PLAN_2X2, "numbering_scheme": NumberingScheme.STRAIGHT},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["capacity"] == 5
    assert [s["seat_no"] for s in resp.data["seats"]] == [1, 2, 3, 4, 5]
    assert selectors.exam_rooms().count() == 0  # önizleme hiçbir şey kaydetmez

    # Geçersiz plan Türkçe 400; geçersiz düzen de 400.
    bad = client.post(
        f"{URL}preview-seats/",
        {"layout_plan": {"grid": {"rows": 0, "cols": 1}}},
        format="json",
    )
    assert bad.status_code == 400
    bad_scheme = client.post(
        f"{URL}preview-seats/",
        {"layout_plan": PLAN_2X2, "numbering_scheme": "ZIGZAG"},
        format="json",
    )
    assert bad_scheme.status_code == 400


# ===========================================================================
# Şube salonları otomasyonu
# ===========================================================================


def test_generate_section_rooms_idempotent_and_orphan() -> None:
    """Servis: her şube için salon (öğrencisiz dahil); ikinci koşu üretmez; orphan raporu."""
    yil = _aktif_yil()
    _sube(yil, 9, "A", 10)
    empty = _sube(yil, 12, "Z", 0)

    first = services.generate_section_rooms()
    assert set(first["created"]) == {"9/A Dersliği", "12/Z Dersliği"}
    assert first["sections_total"] == 2
    room = ExamRoom.objects.get(name="9/A Dersliği")
    assert room.linked_section_id is not None
    assert selectors.section_rooms_for_levels({9})[0].pk == room.pk

    # İkinci koşu: linked_section'a bağlı olduğundan atlanır.
    second = services.generate_section_rooms()
    assert second["created"] == []
    assert set(second["skipped"]) == {"9/A Dersliği", "12/Z Dersliği"}

    # Şube soft-delete → orphan raporu (salon canlı+aktif kalır).
    empty.delete()
    third = services.generate_section_rooms()
    assert "12/Z Dersliği" in third["orphan_rooms"]


def test_generate_kalabalik_sube_satir_buyutur() -> None:
    """40'ı aşan şubede satır sayısı büyür — kapasite hatası önlenir (44 → 6 satır)."""
    yil = _aktif_yil()
    _sube(yil, 10, "B", 44)
    services.generate_section_rooms()
    room = ExamRoom.objects.get(name="10/B Dersliği")
    assert services.room_capacity(room) == 48  # 6 satır × 4 sütun × 2 koltuk


def test_generate_hazirlik_etiketi() -> None:
    """Hazırlık şubesi 'Hazırlık/A Dersliği' adını alır (okul türü seviye etiketi)."""
    from apps.okul.models import SchoolConfig

    SchoolConfig.objects.create(pk=SchoolConfig.SINGLETON_PK, has_prep_class=True)
    yil = _aktif_yil()
    _sube(yil, 0, "A")
    result = services.generate_section_rooms()
    assert result["created"] == ["Hazırlık/A Dersliği"]


def test_section_rooms_for_levels_filters_by_level_and_alive() -> None:
    """Selector yalnız aktif + canlı şubeli + istenen seviye salonlarını döner."""
    yil = _aktif_yil()
    _sube(yil, 9, "A", 5)
    _sube(yil, 11, "C", 5)
    services.generate_section_rooms()

    names_9 = {r.name for r in selectors.section_rooms_for_levels({9})}
    assert names_9 == {"9/A Dersliği"}
    names_both = {r.name for r in selectors.section_rooms_for_levels({9, 11})}
    assert names_both == {"9/A Dersliği", "11/C Dersliği"}
    # linked_section'sız serbest salon dahil edilmez.
    services.create_exam_room(name="Serbest Salon")
    assert "Serbest Salon" not in {r.name for r in selectors.section_rooms_for_levels({9, 11})}


def test_generate_section_rooms_endpoint() -> None:
    yil = _aktif_yil()
    _sube(yil, 10, "B", 8)
    resp = APIClient().post(f"{URL}generate-section-rooms/", {}, format="json")
    assert resp.status_code == 200, resp.data
    assert resp.data["created"] == ["10/B Dersliği"]


def test_default_section_plan_shape() -> None:
    """Varsayılan şablon (02.09.2026): öğretmen masası SOL-ÖN, KAPI YOK, 40 koltuk.

    Kapı bilinçli olarak yoktur: yeri okuldan okula değişir, numaralandırmaya
    girmez ve yanlış yerde basılırsa resmî krokide yanlış bilgi olur.
    """
    plan = layout.validate_layout_plan(layout.default_section_plan())
    assert plan.capacity == 40
    assert (plan.rows, plan.cols) == (6, 4)  # 1 ön cephe bandı + 5 sıra
    furniture = {f.kind: (f.row, f.col) for f in plan.furniture}
    assert furniture == {"TEACHER_DESK": (0, 0)}


def test_default_plan_endpoint_sablonu_verir() -> None:
    """`default-plan` ucu: şablonun tek doğruluk kaynağı backend (editör tüketir)."""
    resp = APIClient().get(f"{URL}default-plan/")
    assert resp.status_code == 200, resp.data
    assert resp.data["capacity"] == 40
    assert resp.data["layout_plan"]["grid"] == {"rows": 6, "cols": 4}
    assert resp.data["layout_plan"]["furniture"] == [{"kind": "TEACHER_DESK", "row": 0, "col": 0}]


def test_default_plan_endpoint_olcu_alir_ve_dogrular() -> None:
    """Ölçü parametreleri okullar arası farkı karşılar; geçersizi Türkçe 400."""
    resp = APIClient().get(f"{URL}default-plan/?desk_rows=6&cols=5")
    assert resp.status_code == 200, resp.data
    assert resp.data["capacity"] == 60
    assert resp.data["layout_plan"]["grid"] == {"rows": 7, "cols": 5}

    assert APIClient().get(f"{URL}default-plan/?desk_rows=0").status_code == 400
    assert APIClient().get(f"{URL}default-plan/?cols=abc").status_code == 400


def test_salon_listesi_turk_alfabesine_gore_siralanir() -> None:
    """`10/I` sonrası `10/İ` gelir — SQLite BINARY sırası 'İ'yi 'Z'den sonraya atardı.

    Saha bulgusu (31.08.2026): derslik kümeleri diyaloğunda sıra
    "10/I · 10/J · 10/K · 10/İ" görünüyordu.
    """
    for harf in ("I", "J", "K", "İ", "H"):
        services.create_exam_room(name=f"10/{harf} Dersliği")

    adlar = [r.name for r in selectors.exam_rooms_sorted()]
    assert adlar == [
        "10/H Dersliği",
        "10/I Dersliği",
        "10/İ Dersliği",
        "10/J Dersliği",
        "10/K Dersliği",
    ]

    client = APIClient()
    yanit = client.get("/api/v1/exam-rooms/?limit=200")
    assert yanit.status_code == 200
    satirlar = yanit.data["results"] if isinstance(yanit.data, dict) else yanit.data
    assert [r["name"] for r in satirlar] == adlar
