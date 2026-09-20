"""Soru PDF'i yükleme doğrulaması — ders dosyası ve bireysel dosya ORTAK kullanır.

`services.upload_question_document` içindeki denetimler buraya taşındı
(20.09.2026): bireysel soru dosyası (`services_individual`) AYNI kurallardan
geçmelidir — bant üst 4 cm sözleşmesi ikisinde de yalnız A4 DİKEY sayfada tutar.
Kurallar ve ret metinleri değişmedi.
"""

from __future__ import annotations

import io

from django.core.exceptions import ValidationError

from apps.sinav.models import ScoreMode

_PDF_MAGIC = b"%PDF-"
MAX_QUESTION_PDF_MB = 20
#: A4 nokta ölçüleri + tolerans (OYS Tur 646): Word'ün PDF ihracı 595.32×841.92
#: gibi küsurat üretir — ±6pt tolerans bunu kapsar, Letter'ı (612×792) reddeder.
_A4_W_PT, _A4_H_PT = 595.28, 841.89
_A4_TOL_PT = 6.0


def validate_question_pdf(file_bytes: bytes, *, score_mode: str, question_count: int | None) -> int:
    """Soru PDF'ini doğrular; SAYFA SAYISINI döndürür.

    Doğrulama: PDF magic bytes + boyut + sayfa sayısı (pypdf açabilmeli) + her
    sayfa A4 DİKEY ±6pt. NOT: üst bant içerik tespiti BİLİNÇLE yapılmaz — metin
    katmanı taranmış PDF'te kördür, güvenilir sinyal değil.
    """
    if not file_bytes:
        raise ValidationError("Boş dosya yüklenemez.")
    if not file_bytes.startswith(_PDF_MAGIC):
        raise ValidationError("Yalnız PDF kabul edilir (dosya imzası PDF değil).")
    if len(file_bytes) > MAX_QUESTION_PDF_MB * 1024 * 1024:
        raise ValidationError(f"Dosya çok büyük (üst sınır {MAX_QUESTION_PDF_MB} MB).")
    if score_mode == ScoreMode.QUESTION_TABLE and not question_count:
        raise ValidationError("Soru bazlı puan tablosu için soru sayısı girin.")

    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        page_count = len(reader.pages)
    except Exception as exc:  # pypdf çeşitli hatalar fırlatabilir
        raise ValidationError("PDF okunamadı; dosya bozuk olabilir.") from exc
    if page_count == 0:
        raise ValidationError("PDF sayfa içermiyor.")

    # /Rotate normalize edilir (90/270 taşıyan dikey mediabox fiilen YATAYdır).
    for page_no, page in enumerate(reader.pages, start=1):
        try:
            rotation = int(page.get("/Rotate") or 0) % 360
            box = page.mediabox
            width, height = float(box.width), float(box.height)
        except Exception as exc:
            raise ValidationError(f"PDF sayfa {page_no} okunamadı; dosya bozuk olabilir.") from exc
        if rotation in (90, 270):
            width, height = height, width
        if abs(width - _A4_W_PT) <= _A4_TOL_PT and abs(height - _A4_H_PT) <= _A4_TOL_PT:
            continue
        if abs(width - _A4_H_PT) <= _A4_TOL_PT and abs(height - _A4_W_PT) <= _A4_TOL_PT:
            raise ValidationError(
                f"Sayfa {page_no} YATAY (A4 yatay) — başlık bandı üst 4 cm sözleşmesi "
                "bozulur. Sayfaları A4 DİKEY yapın; panelden indirilen Word şablonunu "
                "kullanmanız önerilir."
            )
        raise ValidationError(
            f"Sayfa {page_no} A4 boyutunda değil ({width:.0f}×{height:.0f} pt; beklenen "
            "595×842). Belgeyi A4 dikey sayfa boyutuyla PDF'e aktarın; panelden "
            "indirilen Word şablonunu kullanmanız önerilir."
        )
    return page_count
