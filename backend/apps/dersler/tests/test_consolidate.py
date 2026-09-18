"""Mükerrer ders birleştirme — sınav/takvim/kapsam referansları (A3, 18.09.2026).

Çakışma grubu anahtarı ders kimliğini taşır (`"<course_id>:<level>"`); eskiden
birleştirme `ExamSessionCourse.course`'u durum kapısı olmadan taşıyor,
`SeatAssignment.conflict_group` eski kimlikte kalıyor ve kitapçık üretimi her
öğrenci için "soru dosyası eksik" diyordu. Takvim girdileri ve seçmeli şube
kapsamları ise hiç taşınmıyor, silinmiş derse bakan yetim kayıt oluyordu.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.dersler import services
from apps.dersler.models import Course, CourseSectionOffering, CourseType
from apps.sinav import services as sinav_services
from apps.sinav import services_calendar
from apps.sinav.models import (
    BookletRunStatus,
    ExamCalendarEntry,
    ExamSession,
    ExamSessionStatus,
    ParticipantType,
    SeatAssignment,
)
from apps.sinav.tests.oturum_yardim import aktif_yil, ders, donem, oturum, salon, sube

pytestmark = pytest.mark.django_db


def _dagitilmis(kopya: Course, *, canonical: Course | None = None) -> ExamSession:
    """Kopya dersle (istenirse kanonikle birlikte) dağıtılmış 9+10 oturumu."""
    sube(9, "A", students=3, start_no=101)
    sube(10, "A", students=3, start_no=201)
    session = oturum()
    sinav_services.add_session_course(
        session, course_id=kopya.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    other = canonical or ders("Fizik", levels=[10])
    sinav_services.add_session_course(
        session, course_id=other.pk, participant_type=ParticipantType.LEVEL, level=10
    )
    sinav_services.set_session_rooms(session, [{"room_id": salon("D-201").pk}])
    session, _result, report = sinav_services.distribute_session(session, seed=5)
    assert report.is_valid
    return session


def test_dagitilmis_oturumda_grup_anahtari_da_tasinir() -> None:
    kopya = ders("Seçmeli Coğrafya", levels=[9])
    kanonik = ders("Coğrafya", levels=[9, 10])
    session = _dagitilmis(kopya)
    assert SeatAssignment.objects.filter(session=session, conflict_group=f"{kopya.pk}:9").exists()

    sonuc = services.consolidate_duplicate_course(duplicate=kopya, canonical=kanonik)

    assert sonuc["exams"] == 1 and sonuc["dropped_exams"] == 0
    keys = set(
        SeatAssignment.objects.filter(session=session).values_list("conflict_group", flat=True)
    )
    assert f"{kanonik.pk}:9" in keys and not any(k.startswith(f"{kopya.pk}:") for k in keys)
    # Asıl belirti: kitapçık üretimi "soru dosyası eksik" demez — anahtarlar eşleşir.
    from apps.sinav.tests.test_booklets import _question_pdf

    for sc in session.courses.all():
        sinav_services.upload_question_document(sc, file_bytes=_question_pdf(1))
    run = sinav_services.request_booklet_run(session)
    assert run.status == BookletRunStatus.COMPLETED


def test_iki_ders_ayni_dagitilmis_oturumdaysa_reddedilir() -> None:
    kopya = ders("Seçmeli Coğrafya", levels=[9])
    kanonik = ders("Coğrafya", levels=[9, 10])
    session = _dagitilmis(kopya, canonical=kanonik)
    assert session.status == ExamSessionStatus.DISTRIBUTED

    with pytest.raises(ValidationError, match="aynı oturumda birlikte"):
        services.consolidate_duplicate_course(duplicate=kopya, canonical=kanonik)
    # Ret hiçbir şeye dokunmaz: kopya canlı, yerleşim anahtarları yerinde.
    assert Course.objects.filter(pk=kopya.pk).exists()
    assert SeatAssignment.objects.filter(session=session, conflict_group=f"{kopya.pk}:9").exists()


def test_taslak_oturumda_cakisan_satir_duser_bayrak_kardese_uyar() -> None:
    kopya = ders("Seçmeli Coğrafya", levels=[9, 10])
    kanonik = ders("Coğrafya", levels=[9, 10])
    session = oturum()
    sinav_services.add_session_course(
        session,
        course_id=kanonik.pk,
        participant_type=ParticipantType.LEVEL,
        level=9,
        shared_booklet=True,
    )
    for level in (9, 10):
        sinav_services.add_session_course(
            session, course_id=kopya.pk, participant_type=ParticipantType.LEVEL, level=level
        )

    sonuc = services.consolidate_duplicate_course(duplicate=kopya, canonical=kanonik)

    assert sonuc["exams"] == 1 and sonuc["dropped_exams"] == 1  # 9 çakıştı, 10 taşındı
    rows = list(session.courses.order_by("level"))
    assert [(r.course_id, r.level) for r in rows] == [(kanonik.pk, 9), (kanonik.pk, 10)]
    assert all(r.shared_booklet for r in rows), "taşınan satır kardeşin bayrağını almalı"


def test_takvim_girdisi_ve_secmeli_kapsami_tasinir() -> None:
    yil = aktif_yil()
    section = sube(11, "A")
    kopya = ders("Seçmeli Mantık", levels=[11], course_type=CourseType.ELECTIVE)
    kanonik = ders("Mantık", levels=[11], course_type=CourseType.ELECTIVE)
    services.set_course_sections(
        course_id=kopya.pk,
        school_year_id=yil.pk,
        offerings=[{"level": 11, "section_ids": [section.pk]}],
    )
    calendar = services_calendar.create_exam_calendar(
        semester_id=donem(yil).pk,
        round=3,  # 3. turda havuz tohumlanmaz — girdi elle eklenir
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 13),
    )
    entry = services_calendar.add_calendar_entry(calendar=calendar, course_id=kopya.pk, level=11)

    sonuc = services.consolidate_duplicate_course(duplicate=kopya, canonical=kanonik)

    assert sonuc["calendar_entries"] == 1 and sonuc["offerings"] == 1
    entry.refresh_from_db()
    assert entry.course_id == kanonik.pk
    offering = CourseSectionOffering.objects.get(course=kanonik, school_year=yil, level=11)
    assert offering.section_ids == [section.pk]
    assert not ExamCalendarEntry.objects.filter(course=kopya).exists()
