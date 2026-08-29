"""Standart API hata yanıtı — `{code, message, fields}` sözleşmesi (tasarım §4.3).

OYS `shared/exceptions.py`'den uyarlandı: AccessLog/yetki-reddi bölümleri
KALDIRILDI (tek kullanıcılı authsuz program — izin katmanı yok); gövde dönüşümü
AYNEN. FE `lib/api.ts` bu biçimi bekler:

    { "code": "validation_error", "message": "Türkçe açıklama", "fields": {...} }
"""

from __future__ import annotations

from typing import Any

from django.http import Http404
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

# Django/DRF'in kayıt-bulunamadı metinleri İngilizcedir ve model adını sızdırır
# ("No ExamSession matches the given query."). Sözleşme Türkçe mesaj
# ister; view'ın kendi verdiği Türkçe detay ("Kayıt bulunamadı.") korunur.
_GENERIC_NOT_FOUND = "Kayıt bulunamadı."


def _is_default_not_found_detail(message: str) -> bool:
    """Mesaj, kullanıcıya gösterilmeyecek DRF/Django varsayılanı mı?"""
    return message.startswith("No ") or message in {"Not found.", str(NotFound.default_detail)}


def ks_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """DRF varsayılan hata gövdesini sözleşme biçimine dönüştürür."""
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    data = response.data
    # Http404 bir APIException değildir → `default_code` taşımaz; DRF onu içeride
    # NotFound'a çevirdiği için sözleşme kodunu burada elle veriyoruz.
    code = "not_found" if isinstance(exc, Http404) else getattr(exc, "default_code", "error")
    # DRF doğrulama hatalarının generic kodu "invalid"; sözleşme `validation_error`
    # ister. Özel exception'ların kendi kodu (not_found, parse_error vb.) korunur.
    if code == "invalid":
        code = "validation_error"
    fields: dict[str, Any] = {}
    message = "İşlem gerçekleştirilemedi."

    if isinstance(data, dict):
        if "detail" in data:
            message = str(data["detail"])
            if code == "not_found" and _is_default_not_found_detail(message):
                message = _GENERIC_NOT_FOUND
        else:
            # Alan-bazlı doğrulama hataları
            fields = data
            message = "Gönderilen veride hatalar var."
    elif isinstance(data, list):
        message = "; ".join(str(item) for item in data)

    response.data = {"code": code, "message": message, "fields": fields}
    return response
