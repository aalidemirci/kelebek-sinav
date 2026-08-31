"""Zümre kataloğu yazma işlemleri (SubjectDepartment).

İnce servis katmanı — doğrulama serializer'da (ad boşluk katlaması, teklik),
yazma burada (`sections.py` emsali). İmza bloğu seçimi sinav tarafındadır
(`ExamCalendar.signatory_departments`); burada yalnız katalog tutulur.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.okul.models import SubjectDepartment


@transaction.atomic
def create_subject_department(**fields: Any) -> SubjectDepartment:
    department: SubjectDepartment = SubjectDepartment.objects.create(**fields)
    return department


@transaction.atomic
def update_subject_department(department: SubjectDepartment, **fields: Any) -> SubjectDepartment:
    """Yalnız DEĞİŞEN alanları yazar; `updated_at` elle eklenir (auto_now tuzağı)."""
    changed = [name for name, value in fields.items() if getattr(department, name) != value]
    if changed:
        for name in changed:
            setattr(department, name, fields[name])
        department.save(update_fields=[*changed, "updated_at"])
    return department


@transaction.atomic
def delete_subject_department(department: SubjectDepartment) -> None:
    department.delete()  # soft delete (BaseModel)
