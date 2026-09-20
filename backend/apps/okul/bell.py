"""Ders akışı → zil çizelgesi — SAF hesap (DB yok, Django yok).

Kardeş depo `okulzili`nin `SessionSchedule`/`suggest_next_session_start`
mantığından UYARLA: orada amaç zil ÇALDIRMAK olduğu için öğrenci zili farkı,
tören katmanı ve blok geçiş zilleri var; burada gereken tek şey her DERS
SAATİNİN başlangıç saatidir (sınav takvimi ve oturum saati onu okur). Uyarlama
sırasında alınmayanlar: ses/zil alanları, haftalık şema, tarih kuralları.

Çizelge öğesinin şekli OYS sözleşmesiyle birebirdir: ``{"no", "name", "start"}``
(`services_calendar._bell_periods` bunu tüketir) — alan EKLENEBİLİR, şekil
değişmez.

İkili eğitim: iki ayrı akış tutulur (sabah + öğleden sonra). Öğleden sonranın
başlangıcı `suggest_next_start` ile sabahın GERÇEK bitişinden türetilir; blok
düzeni ve uzun ara hesaba katıldığı için "son ders + süre" kestirmesi yanlış
sonuç verirdi.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any

#: Ayarlanabilir sınırlar — arayüz ve servis aynı sayıları kullanır.
MIN_LESSON_MINUTES = 1
MAX_LESSON_MINUTES = 180
MAX_BREAK_MINUTES = 240
#: İki oturum arası en az geçiş payı (öğleden sonra önerisi bunu ekler).
DEFAULT_SHIFT_GAP_MINUTES = 20

#: Varsayılan akış — eski sabit listeyle (08:30'dan 50'şer dakika) BİREBİR aynı
#: çizelgeyi üretir; `default_bell_schedule` regresyon testi bunu kilitler.
DEFAULT_FIRST_LESSON = "08:30"
DEFAULT_LESSON_MINUTES = 40
DEFAULT_BREAK_MINUTES = 10


@dataclass(frozen=True)
class LessonFlow:
    """Bir oturumun ders akışı: saatler bundan HESAPLANIR, elle girilmez.

    `block_sizes` ardışık ders bloklarıdır: (2, 2, 2, 2) = ikişer ders blok
    hâlinde, blok İÇİNDE teneffüs yok, bloklar arasında var. Boş bırakılırsa
    her ders tek başına bir bloktur (klasik düzen).

    `long_break_after` uzun aranın kaçıncı dersten SONRA olduğudur (0 = yok) ve
    bir blok sınırına denk gelmelidir — blok ortasına uzun ara konamaz.
    """

    first_lesson: str = DEFAULT_FIRST_LESSON
    lesson_count: int = 8
    lesson_minutes: int = DEFAULT_LESSON_MINUTES
    break_minutes: int = DEFAULT_BREAK_MINUTES
    long_break_after: int = 0
    long_break_minutes: int = 0
    block_sizes: tuple[int, ...] = ()

    @property
    def effective_blocks(self) -> tuple[int, ...]:
        return self.block_sizes or (1,) * self.lesson_count

    def block_boundaries(self) -> list[int]:
        """Blokların bittiği ders numaraları — uzun ara yalnız bunlara konabilir."""
        sinirlar: list[int] = []
        toplam = 0
        for size in self.effective_blocks:
            toplam += size
            sinirlar.append(toplam)
        return sinirlar

    def errors(self, *, prefix: str = "") -> list[str]:
        """Türkçe doğrulama iletileri (boş liste = geçerli)."""
        sorunlar: list[str] = []
        if _parse_clock(self.first_lesson) is None:
            sorunlar.append(f"{prefix}İlk ders saati SS:DD biçiminde olmalı.")
        if not 1 <= self.lesson_count <= 20:
            sorunlar.append(f"{prefix}Ders sayısı 1 ile 20 arasında olmalı.")
        if not MIN_LESSON_MINUTES <= self.lesson_minutes <= MAX_LESSON_MINUTES:
            sorunlar.append(
                f"{prefix}Ders süresi {MIN_LESSON_MINUTES}-{MAX_LESSON_MINUTES} dakika olmalı."
            )
        if not 0 <= self.break_minutes <= MAX_BREAK_MINUTES:
            sorunlar.append(f"{prefix}Teneffüs 0-{MAX_BREAK_MINUTES} dakika olmalı.")
        if not 0 <= self.long_break_minutes <= MAX_BREAK_MINUTES:
            sorunlar.append(f"{prefix}Uzun ara 0-{MAX_BREAK_MINUTES} dakika olmalı.")
        bloklar = self.effective_blocks
        if any(size < 1 for size in bloklar) or sum(bloklar) != self.lesson_count:
            sorunlar.append(f"{prefix}Blok düzeninin toplamı ders sayısına eşit olmalı.")
        elif self.long_break_after:
            if not 0 < self.long_break_after <= self.lesson_count:
                sorunlar.append(f"{prefix}Uzun ara konumu ders sayısını aşamaz.")
            elif self.long_break_after not in self.block_boundaries():
                sorunlar.append(
                    f"{prefix}Uzun ara bir ders bloğunun ortasına konamaz; blok sınırı seçin."
                )
        return sorunlar

    def to_dict(self) -> dict[str, Any]:
        return {
            "first_lesson": self.first_lesson,
            "lesson_count": self.lesson_count,
            "lesson_minutes": self.lesson_minutes,
            "break_minutes": self.break_minutes,
            "long_break_after": self.long_break_after,
            "long_break_minutes": self.long_break_minutes,
            "block_sizes": list(self.block_sizes),
        }

    @classmethod
    def from_dict(cls, raw: Any) -> LessonFlow:
        """Sözlükten akış; eksik/bozuk alan VARSAYILANA düşer (hata fırlatmaz).

        Doğrulama `errors()` ile AYRI yapılır: burada amaç ham JSON'u tipli
        hâle getirmektir, reddetmek değil — servis katmanı reddeder.
        """
        veri = raw if isinstance(raw, dict) else {}
        return cls(
            first_lesson=str(veri.get("first_lesson") or DEFAULT_FIRST_LESSON),
            lesson_count=_int_or(veri.get("lesson_count"), 8),
            lesson_minutes=_int_or(veri.get("lesson_minutes"), DEFAULT_LESSON_MINUTES),
            break_minutes=_int_or(veri.get("break_minutes"), DEFAULT_BREAK_MINUTES),
            long_break_after=_int_or(veri.get("long_break_after"), 0),
            long_break_minutes=_int_or(veri.get("long_break_minutes"), 0),
            block_sizes=tuple(
                _int_or(x, 1) for x in (veri.get("block_sizes") or []) if _int_or(x, 0) > 0
            ),
        )


def _int_or(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _parse_clock(raw: Any) -> time | None:
    """'SS:DD' → time; tanınmayan değer None (çağıran karar verir)."""
    metin = str(raw or "").strip()
    if not metin:
        return None
    try:
        parcalar = metin.split(":")
        if len(parcalar) < 2:
            return None
        return time(int(parcalar[0]), int(parcalar[1]))
    except (TypeError, ValueError):
        return None


def _fmt(moment: datetime) -> str:
    return moment.strftime("%H:%M")


def _cursor(start: time) -> datetime:
    """Saat aritmetiği için sabit bir güne oturtulmuş imleç (tarih önemsiz)."""
    return datetime(2000, 1, 1, start.hour, start.minute)


def periods_from_flow(flow: LessonFlow) -> list[dict[str, Any]]:
    """Akıştan ders saati listesi: ``[{"no", "name", "start"}, ...]``.

    Blok içindeki dersler ARKA ARKAYA başlar (teneffüs yok); teneffüs ve uzun
    ara yalnız blok sınırlarında eklenir. Gün gece yarısını aşarsa saat sarar —
    engellenmez (atölye/akşam programı), yalnız hesap doğal kalır.
    """
    baslangic = _parse_clock(flow.first_lesson) or _parse_clock(DEFAULT_FIRST_LESSON)
    assert baslangic is not None  # DEFAULT_FIRST_LESSON sabittir
    imlec = _cursor(baslangic)
    satirlar: list[dict[str, Any]] = []
    no = 0
    tamamlanan = 0
    bloklar = flow.effective_blocks
    for index, size in enumerate(bloklar):
        for _ in range(size):
            no += 1
            satirlar.append({"no": no, "name": f"{no}. Ders", "start": _fmt(imlec)})
            imlec += timedelta(minutes=flow.lesson_minutes)
        tamamlanan += size
        if index < len(bloklar) - 1:
            ara = (
                flow.long_break_minutes
                if flow.long_break_after and tamamlanan == flow.long_break_after
                else flow.break_minutes
            )
            imlec += timedelta(minutes=ara)
    return satirlar


def flow_end_time(flow: LessonFlow) -> str:
    """Akışın son dersinin BİTİŞ saati ('SS:DD')."""
    satirlar = periods_from_flow(flow)
    if not satirlar:
        return flow.first_lesson
    son = _parse_clock(satirlar[-1]["start"])
    assert son is not None
    return _fmt(_cursor(son) + timedelta(minutes=flow.lesson_minutes))


def suggest_next_start(flow: LessonFlow, *, gap_minutes: int = DEFAULT_SHIFT_GAP_MINUTES) -> str:
    """Sabah oturumunun bitişinden öğleden sonra oturumunun başlangıcını önerir.

    Geçiş payı eklenir ve saat BEŞER dakikaya yukarı yuvarlanır (okulzili
    `suggest_next_session_start` deseni: idareci yuvarlak saat bekler).
    """
    bitis = _parse_clock(flow_end_time(flow))
    assert bitis is not None
    imlec = _cursor(bitis) + timedelta(minutes=max(gap_minutes, 0))
    dakika = ((imlec.minute + 4) // 5) * 5
    imlec = (
        imlec.replace(minute=0) + timedelta(hours=1)
        if dakika == 60
        else imlec.replace(minute=dakika)
    )
    return _fmt(imlec)


def normalize_periods(raw: Any, *, label: str = "Ders saati listesi") -> list[dict[str, Any]]:
    """Elle düzenlenmiş ders saati listesini doğrular ve normalleştirir.

    Kabul edilen: ``[{"no": 1, "name": "1. Ders", "start": "08:30"}, ...]``.
    `no` 1'den başlayarak ARDIŞIK olmalı (ızgara ve hücre anahtarı saat
    numarasına göre çalışır, boşluk kabul etmez); `start` boş bırakılabilir —
    o zaman o saat için zaman BASILMAZ (saatsiz çalışan okul).

    Türkçe `ValueError` fırlatır; servis katmanı `ValidationError`a çevirir.
    """
    if raw in (None, ""):
        return []
    if not isinstance(raw, list | tuple):
        raise ValueError(f"{label} liste olmalı.")
    temiz: list[dict[str, Any]] = []
    for sira, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"{label}: her satır sözlük olmalı.")
        no = _int_or(item.get("no"), 0)
        if no != sira:
            raise ValueError(f"{label}: ders saati numaraları 1'den başlayıp ardışık olmalı.")
        ham_saat = str(item.get("start") or "").strip()
        if ham_saat and _parse_clock(ham_saat) is None:
            raise ValueError(f"{label}: {sira}. ders saati SS:DD biçiminde olmalı.")
        saat = _parse_clock(ham_saat)
        ad = str(item.get("name") or "").strip() or f"{sira}. Ders"
        temiz.append({"no": sira, "name": ad, "start": _fmt(_cursor(saat)) if saat else ""})
    # Saatler artan olmalı: 3. ders 2.den önce başlayamaz. Boş saatler atlanır
    # (bilgi yokluğu sıralama hatası değildir).
    dolu = [(r["no"], _parse_clock(r["start"])) for r in temiz if r["start"]]
    for (onceki_no, onceki), (_no, simdiki) in zip(dolu, dolu[1:], strict=False):
        if onceki is not None and simdiki is not None and simdiki <= onceki:
            raise ValueError(
                f"{label}: {onceki_no}. dersten sonraki saat daha geç olmalı "
                "(saatler artan sırada girilir)."
            )
    return temiz
