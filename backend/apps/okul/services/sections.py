"""Şube kataloğu yazma işlemleri (ClassSection + ClassSectionGroup).

İnce servis katmanı — doğrulama serializer'da (seviye kümesi, şube katlaması,
mükerrer denetimi), yazma burada. Toplu tohum `imports._ensure_class_sections`.

Şube kümesi (SAY/EA/DİL) YALNIZ seçim kolaylığıdır: küme kimliği hiçbir oturum
kaydına yazılmaz, sihirbaz kümeyi yazma anında somut şube pk'lerine açar.
Toplu atama (`assign_section_group`) asıl maliyet düşürücüdür — şube tek tek
düzenlenmez.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.okul.models import ClassSection, ClassSectionGroup


@transaction.atomic
def create_class_section(**fields: Any) -> ClassSection:
    section: ClassSection = ClassSection.objects.create(**fields)
    return section


@transaction.atomic
def delete_class_section(section: ClassSection) -> None:
    section.delete()  # soft delete (BaseModel)


# --------------------------------------------------------------------------- #
# Şube kümeleri (seçim kolaylığı)
# --------------------------------------------------------------------------- #


@transaction.atomic
def create_section_group(**fields: Any) -> ClassSectionGroup:
    group: ClassSectionGroup = ClassSectionGroup.objects.create(**fields)
    return group


@transaction.atomic
def update_section_group(group: ClassSectionGroup, **fields: Any) -> ClassSectionGroup:
    """Yalnız DEĞİŞEN alanları yazar; `updated_at` elle eklenir (auto_now tuzağı)."""
    changed = [name for name, value in fields.items() if getattr(group, name) != value]
    if changed:
        for name in changed:
            setattr(group, name, fields[name])
        group.save(update_fields=[*changed, "updated_at"])
    return group


@transaction.atomic
def delete_section_group(group: ClassSectionGroup) -> None:
    """Kümeyi soft-siler. Üye şubeler SET_NULL ile kümesiz kalır, SİLİNMEZ."""
    group.sections.update(group=None)
    group.delete()  # soft delete (BaseModel)


@transaction.atomic
def assign_section_group(*, section_ids: list[int], group_id: int | None) -> int:
    """Verilen şubeleri kümeye alır (`group_id=None` → kümeden çıkarır).

    Toplu iştir: ikili eğitimde onlarca şube tek tek düzenlenemez. Dönüş
    etkilenen satır sayısıdır. Bilinmeyen pk sessizce düşer (idempotent toplu
    işlem deseni — `fill_calendar_pool` emsali).
    """
    if group_id is not None and not ClassSectionGroup.objects.filter(pk=group_id).exists():
        raise ValidationError("Şube kümesi bulunamadı.")
    if not section_ids:
        return 0
    return int(ClassSection.objects.filter(pk__in=section_ids).update(group_id=group_id))
