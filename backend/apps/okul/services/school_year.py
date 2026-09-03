"""Ders yılı yaşam döngüsü — oluşturma + tek-aktif kuralı (F1-T6).

Tek-aktif kuralı iki katmanlıdır: burada "önce eskisini kapat" sırası, DB'de
`uq_schoolyear_single_active` koşullu kısıtı (yarış/hata sigortası).
"""

from __future__ import annotations

from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.okul.models import SchoolYear


@transaction.atomic
def create_school_year(
    *, name: str, start_date: date, end_date: date, activate: bool = False
) -> SchoolYear:
    """Yeni ders yılı açar; `activate=True` ise tek-aktif kuralıyla aktifleştirir."""
    year: SchoolYear = SchoolYear.objects.create(
        name=name.strip(), start_date=start_date, end_date=end_date
    )
    if activate:
        activate_school_year(year)
    return year


@transaction.atomic
def activate_school_year(year: SchoolYear) -> SchoolYear:
    """Verilen yılı aktifleştirir; diğer aktif yıllar ÖNCE kapatılır (kısıt sırası)."""
    SchoolYear.objects.filter(is_active=True).exclude(pk=year.pk).update(
        is_active=False, updated_at=timezone.now()
    )
    if not year.is_active:
        year.is_active = True
        year.save(update_fields=["is_active", "updated_at"])
    # Ders yılı, çizelge yürürlük kuralının girdisidir (kademeli çizelgelerde
    # hangi seviyenin hangi nesli okuduğu yıla bağlı): yıl devrinde katalog
    # aynı işlemde yeniden türetilir (damga farklıysa).
    from apps.okul.services import setup as setup_service

    setup_service.sync_course_catalog()
    return year
