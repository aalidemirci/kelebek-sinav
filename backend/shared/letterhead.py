"""Resmî evrak antedi (letterhead) — OYS shared/letterhead.py'den UYARLA (F6).

documents/base.html ortak resmî antedi kullanır:

    T.C.
    <İLÇE> KAYMAKAMLIĞI
    <OKUL ADI>
    <BİRİM>

KS uyarlaması: OYS'deki ``settings.OYS_*`` env geri-düşüşleri atıldı — kimlik
tek kaynaktan (``apps.okul.models.SchoolConfig``) çözülür ve buraya parametre
olarak geçer; ``shared`` (altyapı) katmanı model import etmez (katman kuralı
korunur). İlçe boşsa antette yer-tutucu noktalar görünür.
"""

from __future__ import annotations


def letterhead_authority(district: str | None = None) -> str:
    """Antedin ikinci satırı: '<İLÇE> KAYMAKAMLIĞI' (ilçe yoksa yer-tutucu)."""
    name = (district or "").strip()
    return f"{name} KAYMAKAMLIĞI" if name else "…………… KAYMAKAMLIĞI"


def letterhead_context(
    *,
    school_name: str,
    unit: str = "",
    district: str | None = None,
    principal_name: str | None = None,
) -> dict[str, str]:
    """PDF şablonları için ortak antet bağlamı (T.C. + kaymakamlık + okul + birim).

    `principal_name` UYGUNDUR/imza bloklarında kullanılır.
    """
    return {
        "tc": "T.C.",
        "authority": letterhead_authority(district),
        "school_name": school_name,
        "unit": unit,
        "principal_name": (principal_name or "").strip(),
    }
