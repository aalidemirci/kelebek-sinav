"""Resmî evrak antedi (letterhead) — OYS shared/letterhead.py'den UYARLA (F6).

documents/base.html ortak resmî antedi kullanır:

    T.C.
    <İLÇE> KAYMAKAMLIĞI          (kurum satırı TAMAMI büyük harf)
    <Okul Adı> Müdürlüğü          (birim satırı — Resmî Yazışma Usulü)

KS uyarlaması: OYS'deki ``settings.OYS_*`` env geri-düşüşleri atıldı — kimlik
tek kaynaktan (``apps.okul.models.SchoolConfig``) çözülür ve buraya parametre
olarak geçer; ``shared`` (altyapı) katmanı model import etmez (katman kuralı
korunur). İlçe boşsa antette yer-tutucu noktalar görünür.
"""

from __future__ import annotations

from shared.text import tr_upper


def letterhead_authority(district: str | None = None) -> str:
    """Antedin ikinci satırı: '<İLÇE> KAYMAKAMLIĞI' (ilçe yoksa yer-tutucu).

    İlçe adı TÜRKÇE büyük harfe çevrilir: ayarda "Sancaktepe" yazılıysa antet
    "Sancaktepe KAYMAKAMLIĞI" basıyordu (kurum satırı tamamı büyük harf olmalı).
    Çıplak `.upper()` kullanılmaz (i→I tuzağı).
    """
    name = (district or "").strip()
    return f"{tr_upper(name)} KAYMAKAMLIĞI" if name else "…………… KAYMAKAMLIĞI"


def letterhead_unit(school_name: str) -> str:
    """Antedin birim satırı: '<Okul Adı> Müdürlüğü' (ad boşsa yer-tutucu).

    Resmî yazışma usulünde okul ayrı, "Okul Müdürlüğü" ayrı satır DEĞİLDİR;
    birim satırı okul adıyla birlikte tek satırdır.
    """
    name = " ".join((school_name or "").split())
    if not name:
        return "…………… Müdürlüğü"
    return name if name.endswith("Müdürlüğü") else f"{name} Müdürlüğü"


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
        "unit_line": letterhead_unit(school_name),
        "principal_name": (principal_name or "").strip(),
    }
