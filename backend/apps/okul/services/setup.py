"""Kurum yapılandırması (SchoolConfig singleton) — okuma + yazma + antet çözümleme.

OYS `core.services.school_config` ikamesi (F1-T3). Farklar: env (`OYS_*`)
fallback YOK — tek doğruluk kaynağı DB satırıdır; `principal_name` Müdür
hesabından değil doğrudan yapılandırmadan gelir (login'siz program).
`setup_completed` yalnız `mark_setup_completed` ile değişir — sihirbaz kapısının
düz alan güncellemesiyle yanlışlıkla açılması/kapanması önlenir.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.okul.models import SchoolConfig

# Ayar/sihirbaz ekranından güncellenebilir alanlar (whitelist — başka alan yazılamaz).
UPDATABLE_FIELDS: tuple[str, ...] = (
    "school_name",
    "province",
    "district",
    "principal_name",
    "school_type",
    "has_prep_class",
    "level_programs",
)

#: Değişince ders kataloğunun çizelgeye yeniden çekilmesini gerektiren alanlar.
CATALOG_FIELDS: frozenset[str] = frozenset({"school_type", "has_prep_class", "level_programs"})


def get_school_config() -> SchoolConfig:
    """Singleton satırı; yoksa kaydedilmemiş varsayılan (okuma DB'ye yazmaz)."""
    return SchoolConfig.load()


def sync_course_catalog() -> None:
    """Ders kataloğunu okulun yürürlükteki çizelgesine çeker (damga farklıysa).

    `dersler` servisine köprü: okul türü/hazırlık/seviye ataması/ders yılı
    değişince havuz aynı işlemde güncellensin, idareci Ders Havuzu ekranını
    açmadan takvim havuzunu doldurursa eski çizelge çekilmesin. Çizelge dosyası
    yoksa sessizce atlar (TB2).
    """
    from apps.dersler import services as ders_services

    ders_services.ensure_catalog_synced()
    ders_services.ensure_course_aliases()


@transaction.atomic
def update_school_config(*, fields: dict[str, Any]) -> SchoolConfig:
    """Kurum yapılandırmasını günceller (whitelist alanları). Satır yoksa oluşturur.

    Çizelgeyi etkileyen alan değiştiyse katalog aynı işlemde senkronlanır.
    """
    config: SchoolConfig
    config, _created = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
    update_fields: list[str] = ["updated_at"]
    for name in UPDATABLE_FIELDS:
        if name in fields:
            setattr(config, name, fields[name])
            update_fields.append(name)
    config.save(update_fields=update_fields)
    if CATALOG_FIELDS & set(update_fields):
        sync_course_catalog()
    return config


@transaction.atomic
def mark_setup_completed() -> SchoolConfig:
    """Kurulum sihirbazını tamamlanmış işaretler (satır yoksa oluşturur).

    Katalog burada da senkronlanır: sihirbaz okul türünü 1. adımda yazar, ders
    yılını 2. adımda aktifleştirir — tamamlama anında ikisi de bellidir.
    """
    config: SchoolConfig
    config, _created = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
    config.setup_completed = True
    config.save(update_fields=["setup_completed", "updated_at"])
    sync_course_catalog()
    return config


def get_letterhead_identity() -> dict[str, str]:
    """Resmî evrak antedi için kurum kimliği (evrak motoru F3'te bunu tüketir).

    Döner: `school_name`, `district`, `province`, `principal_name` — hepsi düz
    metin. Okul adı boşsa OYS paritesiyle 'Okul' yer tutucusu; ilçe/müdür boş
    kalabilir (antet şablonu yer tutucu basar).
    """
    config = get_school_config()
    return {
        "school_name": config.school_name.strip() or "Okul",
        "district": config.district.strip(),
        "province": config.province.strip(),
        "principal_name": config.principal_name.strip(),
    }
