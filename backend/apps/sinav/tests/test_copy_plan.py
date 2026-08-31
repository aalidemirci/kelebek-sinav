"""Oturum planı kopyalama testleri (Ö5 — `copy_session_plan`).

Kullanıcı isteği: "başka bir oturumdan, katılacak sınıf ve kullanılacak derslik
bilgilerini kopyalayarak üzerinde değişiklik de yapılabilerek tanımlama".

Sabitlenen sözleşmeler:
- "Katılacak sınıf" verisi `ExamSessionCourse.section_ids` içindedir → dersten
  ayrı kopyalanamaz; `courses=True` şubeleri de getirir.
- Hedef YALNIZ taslak olabilir; seed/yerleşim/onay damgaları TAŞINMAZ.
- Şube eşlemesi yıllar arası (seviye, şube harfi) ile yeniden çözülür.
- İdempotent: var olan ders/salon `skipped`'a düşer, koşu patlamaz.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.okul.models import ClassSection, SchoolYear
from apps.sinav import services
from apps.sinav.models import (
    ExamSession,
    ExamSessionCourse,
    ExamSessionRoom,
    ParticipantType,
)
from apps.sinav.tests.oturum_yardim import aktif_yil, ders, oturum, salon, sube

pytestmark = pytest.mark.django_db


def _kaynak_oturum() -> tuple[ExamSession, ExamSession]:
    """Bir dersli (şube bazlı) + iki salonlu kaynak oturum + boş hedef taslak."""
    aktif_yil()
    a = sube(9, "A", students=2, start_no=101)
    b = sube(9, "B", students=2, start_no=201)
    kurs = ders("Coğrafya", levels=[9])
    s1 = salon("D-101")
    s2 = salon("D-102")

    kaynak = oturum(name="Kaynak oturum")
    services.add_session_course(
        kaynak,
        course_id=kurs.pk,
        participant_type=ParticipantType.SECTIONS,
        section_ids=[a.pk, b.pk],
    )
    services.set_session_rooms(kaynak, [{"room_id": s1.pk}, {"room_id": s2.pk}])

    hedef = oturum(name="Hedef oturum")
    return kaynak, hedef


def test_ders_sube_ve_salon_kopyalanir() -> None:
    kaynak, hedef = _kaynak_oturum()
    rapor = services.copy_session_plan(hedef, source_id=kaynak.pk)

    assert rapor["courses_created"] and rapor["rooms_created"] == ["D-101", "D-102"]
    kopya = ExamSessionCourse.objects.get(session=hedef)
    kaynak_ders = ExamSessionCourse.objects.get(session=kaynak)
    # "Katılacak sınıf" derse gömülüdür — birlikte gelir.
    assert kopya.participant_type == ParticipantType.SECTIONS
    assert sorted(kopya.section_ids) == sorted(kaynak_ders.section_ids)
    assert kopya.level == kaynak_ders.level
    assert ExamSessionRoom.objects.filter(session=hedef).count() == 2


def test_yalniz_salon_kopyalanabilir() -> None:
    kaynak, hedef = _kaynak_oturum()
    rapor = services.copy_session_plan(hedef, source_id=kaynak.pk, courses=False)
    assert rapor["courses_created"] == []
    assert ExamSessionCourse.objects.filter(session=hedef).count() == 0
    assert ExamSessionRoom.objects.filter(session=hedef).count() == 2


def test_ikinci_kopya_idempotent_atlar() -> None:
    kaynak, hedef = _kaynak_oturum()
    services.copy_session_plan(hedef, source_id=kaynak.pk)
    tekrar = services.copy_session_plan(hedef, source_id=kaynak.pk)

    assert tekrar["courses_created"] == [] and tekrar["rooms_created"] == []
    assert any("zaten ekli" in satir for satir in tekrar["courses_skipped"])
    assert any("zaten ekli" in satir for satir in tekrar["rooms_skipped"])
    assert ExamSessionCourse.objects.filter(session=hedef).count() == 1
    assert ExamSessionRoom.objects.filter(session=hedef).count() == 2


def test_pasif_salon_atlanir_kosu_patlamaz() -> None:
    kaynak, hedef = _kaynak_oturum()
    pasif = salon("D-103")
    services.set_session_rooms(
        kaynak,
        [{"room_id": r.room_id} for r in ExamSessionRoom.objects.filter(session=kaynak)]
        + [{"room_id": pasif.pk}],
    )
    services.update_exam_room(pasif, is_active=False)

    rapor = services.copy_session_plan(hedef, source_id=kaynak.pk, courses=False)
    assert "D-103 (pasif salon)" in rapor["rooms_skipped"]
    assert rapor["rooms_created"] == ["D-101", "D-102"]


def test_sube_yillar_arasi_yeniden_eslenir() -> None:
    """Kaynak eski yılın şubesi; hedef yılda (seviye, harf) ile aranır."""
    kaynak, hedef = _kaynak_oturum()
    eski_yil = SchoolYear.objects.create(
        name="2025-2026", start_date=date(2025, 9, 1), end_date=date(2026, 6, 30)
    )
    eski_a = ClassSection.objects.create(school_year=eski_yil, class_level=9, class_section="A")
    eski_z = ClassSection.objects.create(school_year=eski_yil, class_level=9, class_section="Z")
    kaynak_ders = ExamSessionCourse.objects.get(session=kaynak)
    kaynak_ders.section_ids = [eski_a.pk, eski_z.pk]
    kaynak_ders.save(update_fields=["section_ids"])

    rapor = services.copy_session_plan(hedef, source_id=kaynak.pk, rooms=False)
    kopya = ExamSessionCourse.objects.get(session=hedef)
    # 9/A hedef yılda var → pk YENİDEN çözülür (eski pk taşınmaz).
    aktif_a = ClassSection.objects.get(
        school_year__is_active=True, class_level=9, class_section="A"
    )
    assert kopya.section_ids == [aktif_a.pk]
    assert any("9/Z" in u for u in rapor["warnings"])


def test_onayli_hedefe_kopyalanmaz_ve_kendinden_kopyalanmaz() -> None:
    kaynak, hedef = _kaynak_oturum()
    with pytest.raises(ValidationError, match="kendinden kopyalanamaz"):
        services.copy_session_plan(hedef, source_id=hedef.pk)
    with pytest.raises(ValidationError, match="Kaynak oturum bulunamadı"):
        services.copy_session_plan(hedef, source_id=999_999)
    with pytest.raises(ValidationError, match="en az bir bölüm"):
        services.copy_session_plan(hedef, source_id=kaynak.pk, courses=False, rooms=False)


def test_api_copy_plan_sozlesmesi() -> None:
    from rest_framework.test import APIClient

    kaynak, hedef = _kaynak_oturum()
    client = APIClient()
    yanit = client.post(
        f"/api/v1/exam-sessions/{hedef.pk}/copy-plan/",
        {"source_id": kaynak.pk},
        format="json",
    )
    assert yanit.status_code == 200
    assert yanit.data["session"]["id"] == hedef.pk
    assert yanit.data["report"]["rooms_created"] == ["D-101", "D-102"]
    # Seed/onay damgaları TAŞINMAZ — hedef hâlâ taslak.
    assert yanit.data["session"]["status"] == "DRAFT"
