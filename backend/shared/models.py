"""Ortak temel model ve soft-delete altyapısı.

OYS'nin (Okul Yönetim Sistemi) `shared/models.py` dosyasından türetilmiştir.
OYS'deki `created_by`/`deleted_by` FK alanları BİLİNÇLİ OLARAK ÇIKARILDI: bu
program tek kullanıcılı bir masaüstü uygulamasıdır, "kim yaptı" bilgisi anlamsız
(tek kullanıcı var). `created_at/updated_at/deleted_at` + soft-delete davranışı
(`SoftDeleteManager`/`AllObjectsManager` + `delete()/hard_delete()/restore()`)
AYNEN korundu.

Tüm modeller `BaseModel`'i miras alır. Silme yoktur; `delete()` soft-delete yapar.
"""

from __future__ import annotations

from typing import Any

from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):  # type: ignore[type-arg]  # jenerik param yok; Any davranışı korunur
    """Soft-delete farkında queryset."""

    def delete(self) -> tuple[int, dict[str, int]]:
        """Toplu soft-delete: deleted_at damgasını günceller, satırı silmez."""
        count = self.update(deleted_at=timezone.now())
        return count, {}

    def hard_delete(self) -> tuple[int, dict[str, int]]:
        """Gerçek silme — yalnızca özel durumlarda (ör. veri temizliği)."""
        return super().delete()

    def alive(self) -> SoftDeleteQuerySet:
        return self.filter(deleted_at__isnull=True)

    def dead(self) -> SoftDeleteQuerySet:
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager):  # type: ignore[type-arg]  # Any davranışı korunur
    """Varsayılan olarak yalnızca silinmemiş kayıtları döndüren manager."""

    def get_queryset(self) -> SoftDeleteQuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db).alive()


class AllObjectsManager(models.Manager):  # type: ignore[type-arg]  # Any davranışı korunur
    """Silinmişler dahil tüm kayıtlara erişim (geri yükleme için)."""

    def get_queryset(self) -> SoftDeleteQuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db)


class BaseModel(models.Model):
    """Tüm modeller için ortak alanlar ve soft-delete davranışı."""

    created_at = models.DateTimeField("oluşturulma", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("güncellenme", auto_now=True)
    deleted_at = models.DateTimeField("silinme", null=True, blank=True, db_index=True)

    # objects: yalnızca canlı kayıtlar | all_objects: silinmişler dahil
    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def delete(self, using: Any = None, keep_parents: bool = False) -> tuple[int, dict[str, int]]:
        """Soft-delete: satırı silmez, deleted_at damgalar."""
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])
        return 1, {self._meta.label: 1}

    def hard_delete(
        self, using: Any = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        """Gerçek silme — özel durumlar için."""
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self) -> None:
        """Soft-delete'i geri al."""
        self.deleted_at = None
        self.save(update_fields=["deleted_at", "updated_at"])
