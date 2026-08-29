"""Türkçe metin yardımcıları (OYS shared/text.py'den UYARLA — F6).

CLAUDE.md kuralı: TR metne çıplak `.upper()/.lower()` uygulanmaz — Python
'i'.upper() 'I' basar (noktasız), 'İ' değil. `tr_upper` GÖRÜNTÜLEME amaçlı
güvenli büyük harfe çevirmedir (eşleştirme için `apps.okul.normalize`
yardımcıları kullanılır). Diğer Türkçe harfler (ğ→Ğ, ş→Ş, ö→Ö, ü→Ü, ç→Ç,
ı→I) Python upper()'ında zaten doğrudur; tek istisna 'i'dir.
"""

from __future__ import annotations


def tr_upper(value: str) -> str:
    """Türkçe-güvenli büyük harf: 'i'→'İ' düzeltmesiyle upper()."""
    return value.replace("i", "İ").upper()
