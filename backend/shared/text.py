"""Türkçe metin yardımcıları (OYS shared/text.py'den UYARLA — F6).

CLAUDE.md kuralı: TR metne çıplak `.upper()/.lower()` uygulanmaz — Python
'i'.upper() 'I' basar (noktasız), 'İ' değil. `tr_upper` GÖRÜNTÜLEME amaçlı
güvenli büyük harfe çevirmedir (eşleştirme için `apps.okul.normalize`
yardımcıları kullanılır). Diğer Türkçe harfler (ğ→Ğ, ş→Ş, ö→Ö, ü→Ü, ç→Ç,
ı→I) Python upper()'ında zaten doğrudur; tek istisna 'i'dir.

`tr_lower` / `tr_title` (20.09.2026): başlık biçimi `apps.dersler.text`'te
yaşıyordu; zümre adları da (branştan üretim — `okul.services.departments`)
aynı kurala ihtiyaç duyunca TEK uygulama buraya taşındı — okul, dersler'i
import etmez (bağımlılık yönü dersler → okul).
"""

from __future__ import annotations

_LOWER_TABLE = str.maketrans("Iİ", "ıi")

#: Başlık biçiminde küçük kalan bağlaçlar (kelime başındaysa yine büyür).
_TITLE_LOWER_WORDS = frozenset({"ve", "ile", "veya", "ya"})


def tr_upper(value: str) -> str:
    """Türkçe-güvenli büyük harf: 'i'→'İ' düzeltmesiyle upper()."""
    return value.replace("i", "İ").upper()


def tr_lower(value: str) -> str:
    """Türkçe-duyarlı küçük harf (I→ı, İ→i)."""
    return value.translate(_LOWER_TABLE).lower()


def _tr_title_token(token: str) -> str:
    """Tek kelimeyi başlıklaştır; '/' parçalarını ayrı ayrı ('SPOR/GÖRSEL' → 'Spor/Görsel')."""
    return "/".join(
        tr_upper(part[0]) + tr_lower(part[1:]) if part else part for part in token.split("/")
    )


def tr_title(value: str) -> str:
    """Türkçe-duyarlı başlık biçimi: 'TÜRK DİLİ VE EDEBİYATI' → 'Türk Dili ve Edebiyatı'.

    Fazla boşluk katlanır; bağlaçlar (ve, ile, veya, ya) kelime başında değilse
    küçük kalır. Boş girdi boş döner (hata yükseltmez — doğrulama çağıranındır).
    """
    out: list[str] = []
    for index, token in enumerate(value.split()):
        low = tr_lower(token)
        out.append(low if index > 0 and low in _TITLE_LOWER_WORDS else _tr_title_token(token))
    return " ".join(out)
