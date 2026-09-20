"""Mazeret takvimi yerleştiricisi — SAF modül (ORM yok; `engine`/`validator` deseni).

Girdi öğrenci kümeleridir: her sınav (ders + sınıf düzeyi) için o sınava girecek
öğrencilerin kimlikleri. Olağan takvim sınıf düzeyi/şube kapsamıyla YAKLAŞIK hesap
yapar; burada kayıt öğrenci öğrenci bilindiğinden kurallar KESİN denetlenir:

- SERT: aynı öğrenci aynı saatte iki sınavda olamaz.
- SERT: bir öğrenci bir günde en çok `max_per_day` sınava girer (idarecinin
  parametresi; Yönerge md. 5/1-s gereği 2 esastır, 3 zorunlu hâldir).
- SIRA (kullanıcı kararı, 20.09.2026): kesin kipte bir sınav, asıl takvimde
  kendinden önce gelen hiçbir sınavdan ÖNCEYE konmaz (aynı saate konabilir —
  öğrencileri ayrıksa). Asıl takvimde AYNI saatte yapılmış sınavlar arasında sıra
  yoktur; birlikte ele alınırlar. Gevşek kipte yalnız her ÖĞRENCİNİN kendi sırası
  korunur; sınavlar boş saatlere öne çekilir ve takvim daha az güne sığar.

Aynı saate düşen sınavlar tek mazeret oturumunda toplanır (tek salon, tek
gözetmen) — yerleştirici bu yüzden en erken uygun saati seçer, yaymaz.

Sabit (elle konmuş) sınavlara DOKUNULMAZ: yalnız doluluk sayılırlar ve sıra
kuralının dışındadırlar (idarecinin kararı sırayı bilerek bozmuş olabilir —
`audit` bunu uyarı olarak söyler). `auto=False` sınavlar (ülke/il/ilçe geneli:
tarihi il/ilçe MEM ilan eder, Yönerge md. 5/1-aa, bb) sabitlenmedikçe yerleşmez.

Aynı girdi → aynı çıktı (rastgelelik yok); eşitlik `tie`, sonra `key` ile bozulur.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time, timedelta
from itertools import groupby

#: (gün, ders saati no) — kronolojik sıralama demetin doğal sırasıdır.
Slot = tuple[date, int]

#: Yerleşemeyen sınavın gerekçe kodları (metni servis kurar — okul no ile).
NO_SLOTS_LEFT = "NO_SLOTS_LEFT"
STUDENT_LIMITS = "STUDENT_LIMITS"
NOT_AUTO = "NOT_AUTO"


@dataclass(frozen=True)
class PlanGroup:
    """Takvimin tek sınavı — yerleştiricinin gördüğü kadarıyla."""

    key: int
    order: tuple[date, time]  # asıl sınavın zamanı — takvim sırası
    students: frozenset[int]
    level: int
    tie: str = ""  # aynı zamanlı sınavlar arasında kararlı sıra (ders etiketi)
    fixed: Slot | None = None
    auto: bool = True


@dataclass(frozen=True)
class Unplaced:
    reason: str
    #: Uygun saat bulunmasını engelleyen öğrenciler (çakışma ya da günlük sınır).
    blockers: tuple[int, ...] = ()


@dataclass
class ScheduleResult:
    placements: dict[int, Slot] = field(default_factory=dict)
    unplaced: dict[int, Unplaced] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        """Otomatik yerleşmesi beklenen her sınav yerleşti mi? (NOT_AUTO sayılmaz.)"""
        return all(u.reason == NOT_AUTO for u in self.unplaced.values())


def plan_days(start_date: date, day_count: int) -> list[date]:
    """`start_date`ten başlayarak `day_count` HAFTA İÇİ gün (hafta sonu atlanır).

    Programda resmî tatil verisi yoktur (mazeret bildirim süresiyle aynı sınır);
    tatile denk gelen gün elle taşınır.
    """
    days: list[date] = []
    gun = start_date
    while len(days) < day_count:
        if gun.weekday() < 5:
            days.append(gun)
        gun += timedelta(days=1)
    return days


def plan_slots(start_date: date, day_count: int, period_nos: list[int]) -> list[Slot]:
    saatler = sorted(set(period_nos))
    return [(gun, no) for gun in plan_days(start_date, day_count) for no in saatler]


class _Occupancy:
    """Öğrenci doluluğu: hangi saatte dolu, hangi gün kaç sınavı var."""

    def __init__(self) -> None:
        self.busy: dict[int, set[Slot]] = {}
        self.daily: dict[tuple[int, date], int] = {}

    def add(self, students: frozenset[int], slot: Slot) -> None:
        for s in students:
            self.busy.setdefault(s, set()).add(slot)
            self.daily[(s, slot[0])] = self.daily.get((s, slot[0]), 0) + 1

    def blockers(self, students: frozenset[int], slot: Slot, max_per_day: int) -> set[int]:
        return {
            s
            for s in students
            if slot in self.busy.get(s, ()) or self.daily.get((s, slot[0]), 0) >= max_per_day
        }


def schedule(
    groups: list[PlanGroup],
    slots: list[Slot],
    *,
    max_per_day: int,
    strict_order: bool = True,
    blocked_days: frozenset[tuple[date, int]] = frozenset(),
) -> ScheduleResult:
    """Sınavları saatlere yerleştirir. `blocked_days`: (gün, düzey) — o gün o düzeye
    sınav konmaz (üst makam sınavı günü; Yönerge md. 5/1-s)."""
    result = ScheduleResult()
    doluluk = _Occupancy()
    for g in groups:
        if g.fixed is not None:
            result.placements[g.key] = g.fixed
            doluluk.add(g.students, g.fixed)

    sira = sorted((g for g in groups if g.fixed is None), key=lambda g: (g.order, g.tie, g.key))
    pointer = 0  # kesin kip: önceki kümelerin ulaştığı en ileri saat indisi
    son_indis: dict[int, int] = {}  # gevşek kip: öğrencinin son yerleşen sınavının indisi
    for _zaman, kume in groupby(sira, key=lambda g: g.order):
        kume_ucu = pointer
        for g in kume:
            if not g.auto:
                result.unplaced[g.key] = Unplaced(NOT_AUTO)
                continue
            if strict_order:
                start = pointer
            else:
                start = max((son_indis[s] + 1 for s in g.students if s in son_indis), default=0)
            engelleyen: set[int] = set()
            yer: int | None = None
            for i in range(start, len(slots)):
                slot = slots[i]
                if (slot[0], g.level) in blocked_days:
                    continue
                kim = doluluk.blockers(g.students, slot, max_per_day)
                if kim:
                    engelleyen |= kim
                    continue
                yer = i
                break
            if yer is None:
                reason = STUDENT_LIMITS if engelleyen else NO_SLOTS_LEFT
                result.unplaced[g.key] = Unplaced(reason, tuple(sorted(engelleyen)))
                continue
            result.placements[g.key] = slots[yer]
            doluluk.add(g.students, slots[yer])
            kume_ucu = max(kume_ucu, yer)
            for s in g.students:
                son_indis[s] = yer
        # Aynı zamanlı sınavlar birbirini İTMEZ; sonraki küme hepsinin ardından başlar.
        pointer = kume_ucu
    return result


def minimum_days(
    groups: list[PlanGroup],
    start_date: date,
    period_nos: list[int],
    *,
    max_per_day: int,
    strict_order: bool,
    blocked_days: frozenset[tuple[date, int]] = frozenset(),
    limit: int = 40,
) -> int | None:
    """Bu kurallarla her sınavın yerleştiği EN AZ gün sayısı (bulunamazsa None)."""
    for day_count in range(1, limit + 1):
        sonuc = schedule(
            groups,
            plan_slots(start_date, day_count, period_nos),
            max_per_day=max_per_day,
            strict_order=strict_order,
            blocked_days=blocked_days,
        )
        if sonuc.complete:
            return day_count
    return None


@dataclass
class Audit:
    """Yerleşmiş takvimin denetimi — elle taşımalar kuralları bozmuş olabilir."""

    #: Aynı saatte ortak öğrencisi olan sınav çiftleri: (key_a, key_b, öğrenciler).
    clashes: list[tuple[int, int, tuple[int, ...]]] = field(default_factory=list)
    #: Günlük sınırı aşan (öğrenci, gün, sınav sayısı).
    over_limit: list[tuple[int, date, int]] = field(default_factory=list)
    #: Asıl sırada ÖNCE olup takvimde SONRAYA düşen çiftler: (önceki_key, sonraki_key).
    order_breaks: list[tuple[int, int]] = field(default_factory=list)


def audit(placed: list[tuple[PlanGroup, Slot]], *, max_per_day: int, strict_order: bool) -> Audit:
    """Çakışma (sert), günlük sınır ve sıra denetimi — sabitler DAHİL."""
    rapor = Audit()
    gunluk: dict[tuple[int, date], int] = {}
    for g, slot in placed:
        for s in g.students:
            gunluk[(s, slot[0])] = gunluk.get((s, slot[0]), 0) + 1
    rapor.over_limit = sorted(
        (s, gun, adet) for (s, gun), adet in gunluk.items() if adet > max_per_day
    )
    sirali = sorted(placed, key=lambda item: (item[0].order, item[0].tie, item[0].key))
    for i, (a, slot_a) in enumerate(sirali):
        for b, slot_b in sirali[i + 1 :]:
            ortak = a.students & b.students
            if slot_a == slot_b and ortak:
                rapor.clashes.append((a.key, b.key, tuple(sorted(ortak))))
            # `a` asıl takvimde ÖNCE; mazeret takviminde `b`den SONRAYA düşmüşse sıra
            # bozulmuştur. Gevşek kipte yalnız ortak öğrencisi olan çiftler sayılır.
            if a.order < b.order and slot_a > slot_b and (strict_order or ortak):
                rapor.order_breaks.append((a.key, b.key))
    return rapor
