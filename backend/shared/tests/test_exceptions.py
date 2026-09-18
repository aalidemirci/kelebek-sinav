"""`{code, message, fields}` hata sözleşmesi testleri (tasarım §11 — FE api.ts eşi).

Sözleşme OYS/DD'den AYNEN devralındı; burada SABİTLENİR. FE `lib/api.ts`
`ApiError`'ı bu üç alandan kurar — alan adları değişirse arayüz hata
gösterimleri sessizce bozulur.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework.exceptions import NotFound, ValidationError

from shared.exceptions import ks_exception_handler


def _ctx() -> dict[str, Any]:
    return {"view": None, "args": (), "kwargs": {}, "request": None}


def test_dogrulama_hatasi_validation_error_koduna_cevrilir() -> None:
    yanit = ks_exception_handler(ValidationError({"name": ["Bu alan zorunlu."]}), _ctx())

    assert yanit is not None
    assert yanit.data["code"] == "validation_error"
    assert yanit.data["fields"] == {"name": ["Bu alan zorunlu."]}
    assert yanit.data["message"] == "Gönderilen veride hatalar var."


def test_http404_turkce_generic_mesaja_cevrilir() -> None:
    yanit = ks_exception_handler(Http404("No ExamSession matches the given query."), _ctx())

    assert yanit is not None
    assert yanit.data["code"] == "not_found"
    assert yanit.data["message"] == "Kayıt bulunamadı."
    assert yanit.data["fields"] == {}


def test_viewin_kendi_turkce_detayi_korunur() -> None:
    yanit = ks_exception_handler(NotFound("Salon bulunamadı."), _ctx())

    assert yanit is not None
    assert yanit.data["message"] == "Salon bulunamadı."


def test_drf_disi_hata_none_doner() -> None:
    assert ks_exception_handler(RuntimeError("beklenmedik"), _ctx()) is None


def test_cevrilmemis_django_dogrulama_hatasi_400_olur() -> None:
    """A5: view'ın çevirmeyi unuttuğu servis hatası 500 DEĞİL 400'dür."""
    yanit = ks_exception_handler(DjangoValidationError("Günlük ders saati 1-12 olmalı."), _ctx())

    assert yanit is not None and yanit.status_code == 400
    assert yanit.data == {
        "code": "validation_error",
        "message": "Günlük ders saati 1-12 olmalı.",
        "fields": {},
    }


def test_servis_alan_sozlugu_hatasinda_mesaj_gerekceyi_tasir() -> None:
    """Alan sözlüğüyle gelen SERVİS reddi snackbar'da görünür (genel cümle yutmaz)."""
    kaynak = DjangoValidationError({"on_date": "Yerleştirilemez: öğrenci aynı gün 4 sınava girer."})
    try:
        raise ValidationError(kaynak.message_dict) from kaynak
    except ValidationError as cevrilmis:
        yanit = ks_exception_handler(cevrilmis, _ctx())

    assert yanit is not None and yanit.status_code == 400
    assert yanit.data["fields"] == {
        "on_date": ["Yerleştirilemez: öğrenci aynı gün 4 sınava girer."]
    }
    assert yanit.data["message"] == "Yerleştirilemez: öğrenci aynı gün 4 sınava girer."
