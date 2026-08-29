"""Şube kataloğu yazma işlemleri (ClassSection).

İnce servis katmanı — doğrulama serializer'da (seviye kümesi, şube katlaması,
mükerrer denetimi), yazma burada. Toplu tohum `imports._ensure_class_sections`.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.okul.models import ClassSection


@transaction.atomic
def create_class_section(**fields: Any) -> ClassSection:
    section: ClassSection = ClassSection.objects.create(**fields)
    return section


@transaction.atomic
def delete_class_section(section: ClassSection) -> None:
    section.delete()  # soft delete (BaseModel)
