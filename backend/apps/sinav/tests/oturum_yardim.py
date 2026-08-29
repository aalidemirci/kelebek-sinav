"""F3 oturum testleri ortak kurucuları (OYS factories + _semester/_session UYARLA).

OYS'de factory-boy + auth kullanıcıları vardı; KS authsuz tek kullanıcı olduğu
için kurucular çıplak ORM/servis çağrılarıdır. Tüm F3 test dosyaları buradan
beslenir — oturum kurulumu değişirse TEK yer güncellenir.
"""

from __future__ import annotations

from datetime import date, time
from typing import Any

from apps.dersler import services as ders_services
from apps.dersler.models import Course
from apps.okul.models import ClassSection, SchoolTerm, SchoolYear, Student
from apps.sinav import services
from apps.sinav.models import DeskType, ExamRoom, ExamSession, ParticipantType

#: 8 koltuklu (4 ikili sıra, 2x2 yerleşim) standart test planı.
PLAN_8: dict[str, Any] = {
    "grid": {"rows": 2, "cols": 2},
    "desks": [
        {"row": 0, "col": 0, "type": DeskType.DOUBLE},
        {"row": 0, "col": 1, "type": DeskType.DOUBLE},
        {"row": 1, "col": 0, "type": DeskType.DOUBLE},
        {"row": 1, "col": 1, "type": DeskType.DOUBLE},
    ],
    "furniture": [],
}


def aktif_yil() -> SchoolYear:
    """Aktif ders yılı (idempotent — testte bir kez kurulur)."""
    yil: SchoolYear | None = SchoolYear.objects.filter(is_active=True).first()
    if yil is None:
        yeni: SchoolYear = SchoolYear.objects.create(
            name="2026-2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_active=True,
        )
        return yeni
    return yil


def donem(yil: SchoolYear | None = None, sequence: int = 1) -> SchoolTerm:
    """Aktif yılın dönemi (yoksa oluşturur)."""
    yil = yil or aktif_yil()
    term: SchoolTerm | None = SchoolTerm.objects.filter(school_year=yil, sequence=sequence).first()
    if term is None:
        yeni: SchoolTerm = SchoolTerm.objects.create(
            school_year=yil,
            sequence=sequence,
            start_date=date(2026, 9, 8),
            end_date=date(2027, 1, 15),
        )
        return yeni
    return term


def sube(
    class_level: int,
    class_section: str,
    *,
    students: int = 0,
    start_no: int | None = None,
    yil: SchoolYear | None = None,
) -> ClassSection:
    """Şube kaydı + istenirse n aktif öğrenci (okul no seviye+sıradan türetilir)."""
    kayit: ClassSection = ClassSection.objects.create(
        school_year=yil or aktif_yil(), class_level=class_level, class_section=class_section
    )
    base = start_no if start_no is not None else class_level * 1000 + ord(class_section[0]) * 10
    for i in range(students):
        Student.objects.create(
            first_name=f"AD{i}",
            last_name=f"SOYAD{class_level}{class_section}",
            student_number=str(base + i),
            class_level=class_level,
            class_section=class_section,
        )
    return kayit


def ders(name: str = "Matematik", levels: list[int] | None = None) -> Course:
    """Havuza ders ekler (varsa mevcut kaydı döndürür)."""
    mevcut: Course | None = Course.objects.filter(name=name).first()
    if mevcut is not None:
        return mevcut
    return ders_services.create_course(name=name, levels=levels or [9, 10, 11, 12])


def salon(
    name: str,
    *,
    plan: dict[str, Any] | None = None,
    linked_section_id: int | None = None,
) -> ExamRoom:
    """8 koltuklu (varsayılan plan) sınav salonu."""
    return services.create_exam_room(
        name=name,
        layout_plan=plan or PLAN_8,
        linked_section_id=linked_section_id,
    )


def oturum(**kwargs: Any) -> ExamSession:
    """TASLAK oturum — dönem verilmezse aktif yılın 1. dönemi kurulur."""
    defaults: dict[str, Any] = {
        "name": "1. Ortak Sınav",
        "exam_date": date(2026, 11, 16),
        "start_time": time(9, 0),
        "duration_minutes": 60,
    }
    defaults.update(kwargs)
    if "term_id" not in defaults:
        defaults["term_id"] = donem().pk
    return services.create_exam_session(**defaults)


def dagitilmis_oturum(
    *, rooms: int = 1, per_level: int = 3, seed: int = 42, **oturum_kwargs: Any
) -> ExamSession:
    """Dağıtılmış oturum: 9-10. seviyeden per_level öğrenci, `rooms` × 8 koltuk.

    İki çakışma grubu (aynı dersin iki seviyesi) kurulur — kelebek geçerli
    yerleşim üretebilsin; dönen oturum DAĞITILDI durumundadır ve İHLALSİZDİR.
    (F3 yaşam döngüsü + F4 evrak testlerinin ortak kurucusu.)
    """
    sube(9, "A", students=per_level, start_no=101)
    sube(10, "A", students=per_level, start_no=201)
    course = ders("Coğrafya", levels=[9, 10])
    session = oturum(**oturum_kwargs)
    for level in (9, 10):
        services.add_session_course(
            session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=level
        )
    salonlar = [salon(f"D-20{i}") for i in range(1, rooms + 1)]
    services.set_session_rooms(session, [{"room_id": s.pk} for s in salonlar])
    session, _result, report = services.distribute_session(session, seed=seed)
    assert report.is_valid, report.hard_violations
    return session
