"""Öğrenci içe aktarımı için saf (DB'siz) normalize ediciler.

DD `apps/okul/normalize.py` (OYS kökenli) dosyasından SADELEŞTİRİLEREK alındı:
TCKN/telefon/doğum tarihi/cinsiyet normalize edicileri KALDIRILDI — kelebek bu
verileri hiç toplamaz (tasarım §5). Sınıf/şube ayrıştırması okul türünden gelen
seviye kümesiyle PARAMETRİKTİR (U4 — sabit 9-12 yok; DD/OYS'den bilinçli sapma).

Saf fonksiyonlardır — kolay test edilir (tests/test_normalize). DB eşleştirme
ve yazma `services/imports.py`'dadır.
"""

from __future__ import annotations

import re
from collections.abc import Collection

# Türkçe karakter → ASCII büyük. YALNIZ anahtar kelime eşlemesi içindir
# ('HAZIRLIK' tanıma); şube harfine UYGULANMAZ — bkz. `_ascii_upper` / `tr_upper`.
_TR_UPPER_MAP = str.maketrans(
    {
        "ş": "S",
        "Ş": "S",
        "ı": "I",
        "İ": "I",
        "ğ": "G",
        "Ğ": "G",
        "ü": "U",
        "Ü": "U",
        "ö": "O",
        "Ö": "O",
        "ç": "C",
        "Ç": "C",
    }
)

#: Hazırlık sınıfını metinden tanıma deseni ('HAZIRLIK/A', 'HAZ A', 'HZ-B'…).
_PREP_RE = re.compile(r"\bHA?Z(IRLIK)?\b")

#: Şube harfi için Türkçe büyük harf tablosu: 'i' → 'İ', 'ı' → 'I'.
#: (Python'un çıplak `.upper()` değeri 'i'yi 'I' yapar — Türkçede yanlıştır.)
_TR_TITLE_MAP = str.maketrans({"i": "İ", "ı": "I"})

#: Şube harfi olabilecek karakterler (Türk alfabesi + ASCII).
_SECTION_CHARS = r"A-Za-zÇĞİÖŞÜçğıöşü"


def _ascii_upper(value: str) -> str:
    """Türkçe karakterleri ASCII'ye indirip büyük harfe çevirir (ANAHTAR KELİME eşlemesi).

    YALNIZ anahtar kelime araması içindir ('HAZIRLIK' tanıma gibi). Şube harfi
    için KULLANILMAZ: 'İ' ile 'I'yı tek harfe katlar — bkz. `tr_upper`.
    """
    return value.translate(_TR_UPPER_MAP).upper()


def tr_upper(value: str) -> str:
    """Türkçeye uygun büyük harf ('10/i' → '10/İ', '9/ş' → '9/Ş').

    ŞUBE HARFİ KATLAMASININ TEK DOĞRU YOLU BUDUR. `_ascii_upper` ile katlamak
    (30.08.2026 öncesi davranış) Türk alfabesinin ayrı harflerini birleştirir:
    e-Okul sınıf listesi şubeleri Türk alfabesi sırasıyla açar (…G, H, I, İ,
    J, K…), yani orta ölçekli bir okulda **hem 10/I hem 10/İ** bulunur. ASCII
    katlaması bu iki şubeyi tek şubeye çökertip iki ayrı sınıfın öğrencilerini
    sessizce aynı şubeye yazardı — gerçek bir e-Okul ihracında yakalandı.
    """
    return value.translate(_TR_TITLE_MAP).upper()


#: Türk alfabesi sırası — şube harfi artık katlanmadığı için sıralama da
#: Türkçeleşmek ZORUNDA: kod noktası sırasında Ç/Ğ/İ/Ö/Ş/Ü harfleri 'Z'den
#: BÜYÜKTÜR, yani '10/Ç' ile '10/İ' basılan evrakta listenin sonuna düşer ve
#: '10/I' ile '10/İ' iki uca ayrılırdı.
_TR_ALFABE = "0123456789ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ"
_TR_SIRA = {harf: sira for sira, harf in enumerate(_TR_ALFABE)}


def tr_sort_key(value: object) -> tuple[tuple[int, int], ...]:
    """Türk alfabesine göre sıralama anahtarı ('C' < 'Ç' < 'D', 'I' < 'İ' < 'J').

    Yalnız şube harfi için değil, salon adı gibi ÇOK KELİMELİ metinler için de
    kullanılır. Bu yüzden her karakter (öncelik, değer) ikilisine açılır:
    alfabe dışı karakterler (boşluk, '/', '-') 0 önceliğiyle harflerden ÖNCE
    gelir — ASCII sezgisiyle aynı ('A Salonu' < 'AB Salonu'), aksi hâlde ayraç
    sınırındaki adlar birbirine karışırdı. Karşılaştırma büyük harf üzerinden
    yapılır (`tr_upper`).
    """
    buyuk = tr_upper("" if value is None else str(value))
    return tuple(
        (1, _TR_SIRA[ch]) if ch in _TR_SIRA else (0, ord(ch))  #
        for ch in buyuk
    )


def normalize_class_section(
    value: object, *, valid_levels: Collection[int] = (9, 10, 11, 12)
) -> tuple[int, str] | None:
    """'10/A', '10-A', '10 A' → (10, 'A'); küme dışı seviye veya çözümsüz → None.

    `valid_levels` okul türünden türetilir (`SchoolConfig.grade_levels`).
    0 (Hazırlık) kümede ise 'HAZIRLIK/A', 'HZ A' gibi metinler (0, 'A') çözülür.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    levels = frozenset(int(v) for v in valid_levels)
    folded = _ascii_upper(s)
    prep = _PREP_RE.search(folded) if 0 in levels else None
    if prep is not None:
        # Anahtar kelime KATLANMIŞ metinde bulunur, şube harfi HAM metinden
        # alınır — 'Hazırlık/İ' şubesi 'I'ya çökmesin (tr_upper gerekçesi).
        if len(folded) == len(s):  # translate+upper 1:1 kaldıysa konumlar eşleşir
            kalan = s[: prep.start()] + " " + s[prep.end() :]
        else:  # savunma dalı: katlama uzunluğu değiştirdiyse ASCII'ye düş
            kalan = _PREP_RE.sub(" ", folded)
        harfler = re.sub(rf"[^{_SECTION_CHARS}]", " ", kalan).split()
        if not harfler:
            return None
        return 0, tr_upper(harfler[-1])
    level_m = re.search(r"\d{1,2}", s)
    section_m2 = re.search(rf"[{_SECTION_CHARS}]+", s)
    if level_m is None or section_m2 is None:
        return None
    level = int(level_m.group())
    if level not in levels:
        return None
    section = tr_upper(section_m2.group())
    return level, section


def split_full_name(value: object) -> tuple[str, str]:
    """'EMRE CAN YILMAZ' → ('EMRE CAN', 'YILMAZ'); tek kelime → (kelime, '').

    Son kelime soyad kabul edilir. Title Case uygulanmaz — ham bırakılır
    (görüntü biçimi sistemin başka katmanında uygulanır; TR büyük harf tuzağı).
    """
    if value is None:
        return "", ""
    parts = str(value).split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]
