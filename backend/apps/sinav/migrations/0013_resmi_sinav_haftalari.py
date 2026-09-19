"""Bakanlığın 2026-2027 ortak yazılı sınav haftalarını DOKUNULMAMIŞ taslaklara uygular.

Dayanak: MEB ÖDSHGM 10.09.2026 tarihli ve E-26614336-480.99-168561496 sayılı yazı
(`apps.sinav.official_windows`, metin `docs/mevzuat/meb-2026-2027-ortak-yazili-sinavlar.md`).

"Ön tanımlı takvimleri üret" bu yazıdan önce tarihleri Yönetmelik kuralıyla
(ayın son pazartesisi + 11 gün) hesaplıyordu; 2026-2027'de ilan üç turda bu
hesaptan farklıdır. Yalnız şu takvimler güncellenir:

- TASLAK, 1. ya da 2. tur, ders yılı 2026'da başlıyor,
- tarihleri HÂLÂ eski kural hesabının ürettiği değerde (idareci elle değiştirmedi),
- hiç yerleştirilmiş sınavı yok (yerleşik girdi yeni aralığın dışında kalmasın).

Öbür takvimlere dokunulmaz: tarih idarecinin kararıdır (kullanıcı kararı
19.09.2026 — "katı bir kısıtlama olmasın"); takvim sayfası farkı gösterip
"Bakanlık tarihlerini kullan" önerir. Göç kendi kopyasıyla hesaplar (canlı koda
bağlanmaz); geri alma noop — elle verilmiş tarihler silinmesin.
"""

from __future__ import annotations

import calendar as _calmod
from datetime import date, timedelta
from typing import Any

from django.db import migrations

_KURAL_AYI = {(1, 1): 10, (1, 2): 12, (2, 1): 3, (2, 2): 5}
_ILAN_2026 = {
    (1, 1): (date(2026, 11, 2), date(2026, 11, 13)),
    (1, 2): (date(2027, 1, 4), date(2027, 1, 15)),
    (2, 1): (date(2027, 3, 29), date(2027, 4, 9)),
    (2, 2): (date(2027, 6, 7), date(2027, 6, 18)),
}


def _donem(donem_kaydi: Any) -> int:
    sira = int(getattr(donem_kaydi, "sequence", 0) or 0)
    if sira in (1, 2):
        return sira
    return 1 if donem_kaydi.start_date.month >= 8 else 2


def _eski_kural(donem_kaydi: Any, tur: int) -> tuple[date, date]:
    """19.09.2026 öncesi `statutory_window` hesabının birebir kopyası (tur 1-2)."""
    ay = _KURAL_AYI[(_donem(donem_kaydi), tur)]
    yil = donem_kaydi.start_date.year
    son_gun = date(yil, ay, _calmod.monthrange(yil, ay)[1])
    bas = son_gun - timedelta(days=son_gun.weekday())
    bit = bas + timedelta(days=11)
    bas = max(bas, donem_kaydi.start_date)
    bit = min(bit, donem_kaydi.end_date)
    if bas > bit:
        bas = donem_kaydi.start_date
        bit = min(donem_kaydi.end_date, bas + timedelta(days=11))
    return bas, bit


def uygula(apps: Any, schema_editor: Any) -> None:
    ExamCalendar = apps.get_model("sinav", "ExamCalendar")
    ExamCalendarEntry = apps.get_model("sinav", "ExamCalendarEntry")
    takvimler = ExamCalendar.objects.filter(
        status="DRAFT", round__in=[1, 2], deleted_at__isnull=True
    ).select_related("semester__school_year")
    for takvim in takvimler:
        donem_kaydi = takvim.semester
        if donem_kaydi.school_year.start_date.year != 2026:
            continue
        hedef = _ILAN_2026.get((_donem(donem_kaydi), int(takvim.round)))
        if hedef is None:
            continue
        if (takvim.start_date, takvim.end_date) != _eski_kural(donem_kaydi, int(takvim.round)):
            continue  # idareci tarihleri değiştirmiş — dokunulmaz
        if ExamCalendarEntry.objects.filter(
            calendar=takvim, placed_date__isnull=False, deleted_at__isnull=True
        ).exists():
            continue
        bas = max(hedef[0], donem_kaydi.start_date)
        bit = min(hedef[1], donem_kaydi.end_date)
        if bas > bit:
            continue
        takvim.start_date, takvim.end_date = bas, bit
        takvim.save(update_fields=["start_date", "end_date", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("sinav", "0012_katilimci_etiketleri"),
    ]

    operations = [
        migrations.RunPython(uygula, migrations.RunPython.noop),
    ]
