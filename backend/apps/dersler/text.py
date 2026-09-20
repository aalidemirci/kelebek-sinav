"""Ders adı metin yardımcıları — saf, Türkçe-duyarlı (OYS'den AYNEN kesit).

Python'un çıplak `.upper()/.lower()`'ı Türkçe İ/I dönüşümünü bozar; buradaki
çeviri tabloları bunu elle yapar (CLAUDE.md §2 tuzağı). Bu anahtarlar YALNIZ
eşleştirme/karşılaştırma içindir — kullanıcıya veya evraka basılacak metne
uygulanmaz (titlecase_tr hariç: o, görünen katalog adını üretir).
"""

from __future__ import annotations

from django.core.exceptions import ValidationError

from apps.dersler.models import PREP_COURSE_LEVEL
from shared.text import tr_lower as _shared_tr_lower
from shared.text import tr_title as _shared_tr_title
from shared.text import tr_upper as _shared_tr_upper


def level_label(level: int) -> str:
    """Sınıf düzeyi ETİKETİ — tek doğruluk kaynağı: 0 → "Hazırlık", n → "9. Sınıf".

    Eskiden iki kopya vardı (`services.level_label` "9. Sınıf", `catalog.level_label`
    "9. sınıf") ve aynı ekranda iki yazım çıkıyordu. Etiket/değer olarak büyük
    "S" kullanılır (docs/sozluk.md); cümle içinde küçük yazım ayrı yazılır.
    """
    return "Hazırlık" if level == PREP_COURSE_LEVEL else f"{level}. Sınıf"


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


#: Türkçe-duyarlı büyük harf (i→İ, ı→I) — tek uygulama `shared/text.py`'dedir;
#: bu ad içe aktaranlar kırılmasın diye burada da dışa açıktır (üç kopya vardı).
tr_upper = _shared_tr_upper


#: Türkçe-duyarlı küçük harf (I→ı, İ→i) — tek uygulama `shared/text.py`'dedir.
tr_lower = _shared_tr_lower


def titlecase_tr(name: str) -> str:
    """Ders adını Türkçe-duyarlı başlık biçimine getirir.

    Listeler seçmelileri TAMAMEN BÜYÜK HARFLE yazar ('SEÇMELİ SANAT EĞİTİMİ');
    katalog düzeni başlık biçimidir ('Seçmeli Sanat Eğitimi'). Bağlaçlar kelime
    başında değilse küçük kalır. Kural `shared.text.tr_title`dadır (20.09.2026 —
    zümre adları da aynı kuralı kullanır); burada yalnız boş ad reddi eklenir.
    """
    return _shared_tr_title(normalize_course_name(name))


def normalize_course_name(name: str) -> str:
    """Ders adındaki kenar/iç fazla boşlukları temizle; boşsa Türkçe hata."""
    cleaned = " ".join(name.split())
    if not cleaned:
        raise ValidationError("Ders adı boş olamaz.")
    return cleaned
