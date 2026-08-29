"""Ders adı metin yardımcıları — saf, Türkçe-duyarlı (OYS'den AYNEN kesit).

Python'un çıplak `.upper()/.lower()`'ı Türkçe İ/I dönüşümünü bozar; buradaki
çeviri tabloları bunu elle yapar (CLAUDE.md §2 tuzağı). Bu anahtarlar YALNIZ
eşleştirme/karşılaştırma içindir — kullanıcıya veya evraka basılacak metne
uygulanmaz (titlecase_tr hariç: o, görünen katalog adını üretir).
"""

from __future__ import annotations

from django.core.exceptions import ValidationError

_MATCH_TABLE = str.maketrans(
    {
        "İ": "i",
        "I": "ı",
        "Ş": "ş",
        "Ğ": "ğ",
        "Ü": "ü",
        "Ö": "ö",
        "Ç": "ç",
        # Şapkalı ünlüler — e-Okul 'AHLÂK', 'İNKILÂP' yazar; katalog şapkasız.
        "Â": "a",
        "â": "a",
        "Î": "i",
        "î": "i",
        "Û": "u",
        "û": "u",
    }
)


def course_match_key(name: str) -> str:
    """Ders adını eşleştirme anahtarına indirger (TR-duyarlı küçük harf + şapka + boşluk).

    'MATEMATİK' ile 'Matematik'i, 'AHLÂK' ile 'Ahlak'ı eşler. 'seçmeli' öneki
    KORUNUR (seçmeli/ortak ayrımı bozulmaz).
    """
    return " ".join(name.translate(_MATCH_TABLE).lower().split())


def canon_course_key(name: str) -> str:
    """Kanonik ders anahtarı — `course_match_key` + baştaki 'seçmeli ' öneki atılır.

    e-Okul TÜM seçmeli seçimlere 'SEÇMELİ' öneki ekler ('SEÇMELİ GİRİŞİMCİLİK'),
    MEB kataloğu çoğu dersi öneksiz tutar ('Girişimcilik') — mükerrer tespiti
    iki yandan da öneksiz karşılaştırır.
    """
    return course_match_key(name).removeprefix("seçmeli ")


def tr_upper(value: str) -> str:
    """Türkçe-duyarlı büyük harf (i→İ, ı→I)."""
    return value.translate(str.maketrans("iı", "İI")).upper()


def tr_lower(value: str) -> str:
    """Türkçe-duyarlı küçük harf (I→ı, İ→i)."""
    return value.translate(str.maketrans("Iİ", "ıi")).lower()


# Başlık biçiminde küçük kalan bağlaçlar (kelime başındaysa yine büyür).
_TITLE_LOWER_WORDS = frozenset({"ve", "ile", "veya", "ya"})


def _tr_title_token(token: str) -> str:
    """Tek kelimeyi başlıklaştır; '/' parçalarını ayrı ayrı ('SPOR/GÖRSEL' → 'Spor/Görsel')."""
    return "/".join(
        tr_upper(part[0]) + tr_lower(part[1:]) if part else part for part in token.split("/")
    )


def titlecase_tr(name: str) -> str:
    """Ders adını Türkçe-duyarlı başlık biçimine getirir.

    Listeler seçmelileri TAMAMEN BÜYÜK HARFLE yazar ('SEÇMELİ SANAT EĞİTİMİ');
    katalog düzeni başlık biçimidir ('Seçmeli Sanat Eğitimi'). Bağlaçlar kelime
    başında değilse küçük kalır.
    """
    tokens = normalize_course_name(name).split()
    out: list[str] = []
    for i, tok in enumerate(tokens):
        low = tr_lower(tok)
        out.append(low if i > 0 and low in _TITLE_LOWER_WORDS else _tr_title_token(tok))
    return " ".join(out)


def normalize_course_name(name: str) -> str:
    """Ders adındaki kenar/iç fazla boşlukları temizle; boşsa Türkçe hata."""
    cleaned = " ".join(name.split())
    if not cleaned:
        raise ValidationError("Ders adı boş olamaz.")
    return cleaned
