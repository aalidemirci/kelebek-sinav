"""Bakanlığın ilan ettiği ortak yazılı sınav haftaları (19.09.2026).

Ölçme ve Değerlendirme Yönetmeliği md. 5/1-ç sınav zamanını AY düzeyinde verir;
program bunu "ayın son pazartesisinden itibaren iki hafta" diye hesaplar
(`services_calendar.statutory_window`). Bakanlık ise her ders yılı için tarihleri
ayrıca ilan eder ve ilan kural hesabından farklı olabilir: 2026-2027'de 1. dönem
1. yazılı kural hesabıyla 26 Ekim-6 Kasım, ilanla 2-13 Kasım'dır. İlan edilmiş
yılda varsayılan pencere İLANDIR; ilan yoksa kural hesabı çalışır.

VARSAYILANDIR, KISIT DEĞİL (kullanıcı kararı 19.09.2026): takvim tarihleri
idarecinin kararıdır ve her zaman düzenlenebilir. Buradaki tarihler yalnız yeni
takvimin ön değeri ve takvim sayfasındaki öneridir; hiçbir yerleştirme bunlara
göre reddedilmez. Yeni yılın ilanı gelince tabloya bir yıl eklenir ve yazının
metni `docs/mevzuat/` altına girer (atıf depodaki metinden doğrulanır).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class OfficialWindow:
    """Bir dönem + sınav turu için ilan edilmiş sınav haftaları."""

    start: date
    end: date
    #: Kullanıcıya gösterilen dayanak (yazının tarihi ve sayısı).
    source: str


_YAZI_2026 = (
    "MEB Ölçme, Değerlendirme ve Sınav Hizmetleri Genel Müdürlüğünün 10.09.2026 "
    "tarihli ve E-26614336-480.99-168561496 sayılı yazısı"
)

#: Ders yılının başladığı takvim yılı → (dönem, sınav turu) → ilan edilen pencere.
#: Metin: docs/mevzuat/meb-2026-2027-ortak-yazili-sinavlar.md.
OFFICIAL_WINDOWS: dict[int, dict[tuple[int, int], OfficialWindow]] = {
    2026: {
        (1, 1): OfficialWindow(date(2026, 11, 2), date(2026, 11, 13), _YAZI_2026),
        (1, 2): OfficialWindow(date(2027, 1, 4), date(2027, 1, 15), _YAZI_2026),
        (2, 1): OfficialWindow(date(2027, 3, 29), date(2027, 4, 9), _YAZI_2026),
        (2, 2): OfficialWindow(date(2027, 6, 7), date(2027, 6, 18), _YAZI_2026),
    },
}


def official_window(school_year_start: int, donem: int, round_: int) -> OfficialWindow | None:
    """İlan edilmiş pencere; o yıl, dönem ya da tur için ilan yoksa None."""
    return OFFICIAL_WINDOWS.get(int(school_year_start), {}).get((int(donem), int(round_)))
