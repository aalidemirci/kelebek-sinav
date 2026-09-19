"""Öğrenci/Personel elle kayıt işlemleri (F1-T6; tasarım §4.7/6).

İnce servis katmanı — doğrulama/normalize serializer'da (TCKN checksum, telefon
biçimi), yazma burada. View ORM çağırmaz (katman disiplini).
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.okul.models import Personnel, Student, StudentStatus
from apps.okul.services import photos


@transaction.atomic
def create_student(**fields: Any) -> Student:
    student: Student = Student.objects.create(**fields)
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
        photos.delete_student_photo(student.pk)
    return student


@transaction.atomic
def delete_student(student: Student) -> None:
    student.delete()  # soft delete (BaseModel)
    # Kayıt gizlenir ama fotoğraf KATI silinir — kişisel veri artığı kalmasın.
    photos.delete_student_photo(student.pk)


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
