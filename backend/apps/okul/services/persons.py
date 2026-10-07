"""Öğrenci/Personel elle kayıt işlemleri (F1-T6; tasarım §4.7/6).

İnce servis katmanı — doğrulama/normalize serializer'da (TCKN checksum, telefon
biçimi), yazma burada. View ORM çağırmaz (katman disiplini).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.db import transaction

from apps.okul.models import Personnel, Student, StudentStatus
from apps.okul.services import photos

#: Ayrılan/silinen öğrencinin OKUL DIŞI uygulamalardaki kişisel verisini silen
#: kancalar (20.09.2026). Bağımlılık yönü sinav → okul'dur; okul sinav'ı import
#: etmez — sinav kendi temizliğini `AppConfig.ready` içinde buraya kaydeder
#: (BEP kaydı + bireysel soru dosyaları: `sinav.services_individual.forget_student`).
#: Kanca AYNI işlemde koşar: hata verirse durum değişikliği de geri sarılır.
_forget_hooks: list[Callable[[int], None]] = []


def register_student_forget_hook(hook: Callable[[int], None]) -> None:
    """Öğrenci pasifleşince/silinince `hook(student_id)` çağrılsın (idempotent kayıt)."""
    if hook not in _forget_hooks:
        _forget_hooks.append(hook)


def _forget_student_data(student_id: int) -> None:
    """KVKK: ayrılan öğrencinin fotoğrafı ve kancalı verileri KATI silinir."""
    photos.delete_student_photo(student_id)
    for hook in _forget_hooks:
        hook(student_id)


#: Şube değişikliği sayılan alanlar — `status` da girer: yeniden aktifleşen
#: öğrencinin seçmeli listesi ayrılırken silinmişti, yeni gelen gibi sorulur.
_SECTION_FIELDS = frozenset({"class_level", "class_section", "status"})


def notify_student_section_changes(student_ids: list[int]) -> int:
    """Şubesi değişen / yeni gelen öğrenciyi seçmeli listelerine yansıtır (07.10.2026).

    `dersler` köprüsüdür (`setup.sync_course_catalog` emsali): okul, ders havuzunun
    iç kuralını bilmez, yalnız "bu öğrencilerin şubesi değişti" der. Eski şubedeki
    liste satırları silinir; yeni şube seçmeliyi bölünerek okutuyorsa öğrenci
    seçim bekler. Dönüş: seçim bekleyen öğrenci SAYISI (aktarım raporu basar).
    """
    if not student_ids:
        return 0
    from apps.dersler import services as ders_services

    return ders_services.handle_student_section_changes(student_ids).pending


@transaction.atomic
def create_student(**fields: Any) -> Student:
    student: Student = Student.objects.create(**fields)
    if student.status == StudentStatus.ACTIVE:
        notify_student_section_changes([student.pk])
    return student


@transaction.atomic
def update_student(student: Student, **fields: Any) -> Student:
    changed = [name for name, value in fields.items() if getattr(student, name) != value]
    if changed:
        for name in changed:
            setattr(student, name, fields[name])
        student.save(update_fields=[*changed, "updated_at"])
    if student.status != StudentStatus.ACTIVE:
        # KVKK: ayrılan öğrencinin fotoğrafı tutulmaz (StudentPhoto docstring'i).
        _forget_student_data(student.pk)
    elif _SECTION_FIELDS.intersection(changed):
        notify_student_section_changes([student.pk])
    return student


@transaction.atomic
def delete_student(student: Student) -> None:
    student.delete()  # soft delete (BaseModel)
    # Kayıt gizlenir ama fotoğraf KATI silinir — kişisel veri artığı kalmasın.
    _forget_student_data(student.pk)


@transaction.atomic
def create_personnel(**fields: Any) -> Personnel:
    person: Personnel = Personnel.objects.create(**fields)
    return person


@transaction.atomic
def update_personnel(person: Personnel, **fields: Any) -> Personnel:
    changed = [name for name, value in fields.items() if getattr(person, name) != value]
    if changed:
        for name in changed:
            setattr(person, name, fields[name])
        person.save(update_fields=[*changed, "updated_at"])
    return person


@transaction.atomic
def delete_personnel(person: Personnel) -> None:
    person.delete()  # soft delete (BaseModel)
