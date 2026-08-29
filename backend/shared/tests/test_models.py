"""`shared.models.BaseModel` soft-delete davranışı testleri.

`BaseModel` soyut (abstract) olduğundan gerçek bir tabloya ihtiyaç var; F0'da
`apps.okul` hâlâ boş iskelet (modeller F1'de gelir), bu
yüzden burada `django.test.utils.isolate_apps` ile testin ömrü kadar var olan
GEÇİCİ somut bir model tanımlanır ve `schema_editor` ile tablosu açılıp/kapatılır.
Davranış OYS'den AYNEN devralındığı için burada SABİTLENİR, değiştirilmez.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from django.db import connection, models
from django.test.utils import isolate_apps

from shared.models import BaseModel


@contextmanager
def _gecici_model() -> Iterator[type[BaseModel]]:
    """Testin ömrü kadar var olan somut bir `BaseModel` alt sınıfı + tablosu."""
    with isolate_apps("shared"):

        class Kayit(BaseModel):
            ad = models.CharField(max_length=50)

            class Meta:
                app_label = "shared"

        with connection.schema_editor() as editor:
            editor.create_model(Kayit)
        try:
            yield Kayit
        finally:
            with connection.schema_editor() as editor:
                editor.delete_model(Kayit)


@pytest.mark.django_db(transaction=True)
def test_yeni_kayit_silinmemis_gorunur() -> None:
    with _gecici_model() as Kayit:
        obj = Kayit.objects.create(ad="test")
        assert obj.is_deleted is False
        assert Kayit.objects.filter(pk=obj.pk).exists()
        assert Kayit.all_objects.filter(pk=obj.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_delete_soft_delete_yapar_satiri_silmez() -> None:
    with _gecici_model() as Kayit:
        obj = Kayit.objects.create(ad="test")
        count, _ = obj.delete()

        assert count == 1
        assert obj.is_deleted is True
        assert obj.deleted_at is not None
        # objects (varsayılan manager) artık görmez, all_objects hâlâ görür.
        assert not Kayit.objects.filter(pk=obj.pk).exists()
        assert Kayit.all_objects.filter(pk=obj.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_restore_soft_delete_i_geri_alir() -> None:
    with _gecici_model() as Kayit:
        obj = Kayit.objects.create(ad="test")
        obj.delete()

        obj.restore()

        assert obj.is_deleted is False
        assert obj.deleted_at is None
        assert Kayit.objects.filter(pk=obj.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_hard_delete_satiri_gercekten_siler() -> None:
    with _gecici_model() as Kayit:
        obj = Kayit.objects.create(ad="test")
        pk = obj.pk

        obj.hard_delete()

        assert not Kayit.all_objects.filter(pk=pk).exists()


@pytest.mark.django_db(transaction=True)
def test_queryset_toplu_delete_ve_alive_dead() -> None:
    with _gecici_model() as Kayit:
        Kayit.objects.create(ad="bir")
        Kayit.objects.create(ad="iki")

        count, _ = Kayit.objects.all().delete()

        assert count == 2
        assert Kayit.objects.count() == 0
        assert Kayit.all_objects.count() == 2
        assert Kayit.all_objects.get_queryset().dead().count() == 2
        assert Kayit.all_objects.get_queryset().alive().count() == 0
