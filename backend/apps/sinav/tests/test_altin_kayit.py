"""ALTIN KAYIT — motor çıktısının bit bit regresyon kilidi (20.09.2026).

Kız/erkek ayrışması motoru değiştirmeden ÖNCE alındı: kural KAPALIYKEN
(varsayılan) dağıtım, bu dosyadaki sabit senaryolarda ve sabit seed'lerde
BİREBİR aynı yerleşimi üretmeye devam etmelidir. "Aynı seed → aynı dağıtım"
sözleşmesi (CLAUDE.md §3) yalnız çalıştırmalar arasında değil, SÜRÜMLER
arasında da geçerlidir: idareci bir oturumu dağıtım numarasıyla yeniden
üretebildiğini varsayar ve basılmış evrakla karşılaştırır.

Bu test kırmızıya dönerse iki olasılık vardır:
  1. motorda istenmeyen bir davranış değişikliği oldu (düzeltin), ya da
  2. değişiklik BİLİNÇLİ (ör. ceza demetine yeni bileşen) — o zaman kaydı
     yenilemek AYRI bir karardır ve commit mesajında gerekçesiyle anılır.
Kayıt yenilemek için `_altin_kayit_uret` yardımcısını çalıştırın (aşağıda).

DB GEREKMEZ — motor saf veri üzerinde çalışır.
"""

from __future__ import annotations

import pytest

from apps.sinav import engine
from apps.sinav.layout import numbered_seats, validate_layout_plan
from apps.sinav.models import DeskType, NumberingScheme
from apps.sinav.participants import Participant


def _participant(sid: int, group: str, *, level: int = 9, section: str = "A") -> Participant:
    return Participant(
        student_id=sid,
        full_name=f"Öğrenci {sid}",
        student_number=str(100 + sid),
        class_level=level,
        class_section=section,
        course_id=int(group.split(":")[0]),
        course_name=f"Ders {group}",
        conflict_group=group,
    )


def _room(room_id: int, rows: int, cols: int, desk_type: str = DeskType.DOUBLE) -> engine.RoomSeats:
    plan = validate_layout_plan(
        {
            "grid": {"rows": rows, "cols": cols},
            "desks": [
                {"row": r, "col": c, "type": desk_type} for r in range(rows) for c in range(cols)
            ],
            "furniture": [],
        }
    )
    return engine.RoomSeats(
        room_id=room_id, seats=tuple(numbered_seats(plan, NumberingScheme.S_PATTERN))
    )


def _kayit(result: engine.DistributionResult) -> list[str]:
    """Yerleşimi okunur ve karşılaştırılabilir bir dizgeye indirger.

    Biçim: "<öğrenci>:<salon>/<sıra satırı>,<sıra sütunu>,<sıra içi>#<koltuk no>"
    — kırıldığında hangi öğrencinin nereye kaydığı gözle görülür.
    """
    return [
        f"{pl.participant.student_id}:{pl.room_id}"
        f"/{pl.seat.desk_row},{pl.seat.desk_col},{pl.seat.slot}#{pl.seat.seat_no}"
        for pl in sorted(result.placements, key=lambda p: p.participant.student_id)
    ]


# ---------------------------------------------------------------------------
# Senaryolar — çağrı girdileri TEK yerde; hem test hem kayıt üretici kullanır.
# ---------------------------------------------------------------------------
def _senaryo_iki_grup_tek_salon() -> tuple[list[Participant], list[engine.RoomSeats], int]:
    katilimcilar = [_participant(i, "10:9") for i in range(1, 9)] + [
        _participant(i, "10:10", level=10, section="B") for i in range(9, 17)
    ]
    return katilimcilar, [_room(1, 3, 3)], 42


def _senaryo_uc_grup_iki_salon() -> tuple[list[Participant], list[engine.RoomSeats], int]:
    katilimcilar = (
        [_participant(i, "10:9") for i in range(1, 7)]
        + [_participant(i, "10:10", level=10, section="B") for i in range(7, 13)]
        + [_participant(i, "11:11", level=11, section="C") for i in range(13, 19)]
    )
    return katilimcilar, [_room(1, 2, 3), _room(2, 2, 2)], 7


def _senaryo_tek_grup_satranc() -> tuple[list[Participant], list[engine.RoomSeats], int]:
    return [_participant(i, "10:9") for i in range(1, 7)], [_room(1, 3, 3)], 99


def _senaryo_pinli() -> tuple[list[Participant], list[engine.RoomSeats], int]:
    katilimcilar = [_participant(i, "10:9") for i in range(1, 7)] + [
        _participant(i, "10:10", level=10, section="B") for i in range(7, 13)
    ]
    return katilimcilar, [_room(1, 2, 4)], 5


SENARYOLAR = {
    "iki_grup_tek_salon": _senaryo_iki_grup_tek_salon,
    "uc_grup_iki_salon": _senaryo_uc_grup_iki_salon,
    "tek_grup_satranc": _senaryo_tek_grup_satranc,
    "pinli": _senaryo_pinli,
}


def _calistir(ad: str) -> engine.DistributionResult:
    katilimcilar, salonlar, seed = SENARYOLAR[ad]()
    if ad == "pinli":
        # Kuralla sabitlenmiş bir öğrenci: koltuğu kullanılmaz, komşuluk cezasına girer.
        sabit = engine.Placement(participant=katilimcilar[0], room_id=1, seat=salonlar[0].seats[0])
        return engine.distribute_butterfly(katilimcilar[1:], salonlar, seed=seed, preplaced=[sabit])
    return engine.distribute_butterfly(katilimcilar, salonlar, seed=seed)


#: Motor çıktısının 20.09.2026'da (kız/erkek ayrışmasından ÖNCE) donmuş hâli.
#: Yenilemek AYRI bir karardır — `_altin_kayit_uret()` çıktısını buraya yazın.
ALTIN_KAYIT: dict[str, list[str]] = {
    "iki_grup_tek_salon": [
        "1:1/0,0,1#2",
        "2:1/2,2,1#18",
        "3:1/2,0,1#6",
        "4:1/2,1,1#8",
        "5:1/1,0,0#3",
        "6:1/0,1,1#12",
        "7:1/0,2,1#14",
        "8:1/1,2,0#15",
        "9:1/0,0,0#1",
        "10:1/2,2,0#17",
        "11:1/2,0,0#5",
        "12:1/2,1,0#7",
        "13:1/1,0,1#4",
        "14:1/0,1,0#11",
        "15:1/0,2,0#13",
        "16:1/1,2,1#16",
    ],
    "uc_grup_iki_salon": [
        "1:1/0,0,0#1",
        "2:1/1,0,1#4",
        "3:1/0,1,1#8",
        "4:1/1,2,0#11",
        "5:2/1,0,0#3",
        "6:2/1,1,1#6",
        "7:1/0,0,1#2",
        "8:1/1,0,0#3",
        "9:1/0,2,0#9",
        "10:1/1,2,1#12",
        "11:2/0,0,1#2",
        "12:2/1,1,0#5",
        "13:1/1,1,1#6",
        "14:1/0,1,0#7",
        "15:1/0,2,1#10",
        "16:2/0,0,0#1",
        "17:2/1,0,1#4",
        "18:2/0,1,1#8",
    ],
    "tek_grup_satranc": [
        "1:1/0,0,0#1",
        "2:1/0,2,0#13",
        "3:1/2,0,0#5",
        "4:1/2,1,0#7",
        "5:1/2,2,0#17",
        "6:1/0,1,0#11",
    ],
    "pinli": [
        "2:1/0,3,0#15",
        "3:1/1,0,1#4",
        "4:1/1,3,1#14",
        "5:1/0,1,1#8",
        "6:1/1,2,0#11",
        "7:1/0,0,1#2",
        "8:1/1,0,0#3",
        "9:1/0,3,1#16",
        "10:1/1,3,0#13",
        "11:1/0,2,0#9",
        "12:1/1,1,1#6",
    ],
}


def _altin_kayit_uret() -> None:  # pragma: no cover — elle çalıştırılır
    """Kaydı yeniden üretir (bilinçli davranış değişikliğinden SONRA).

    Kabuk: `pytest apps/sinav/tests/test_altin_kayit.py -s --no-cov` içinden
    çağırın; çıktı doğrudan `ALTIN_KAYIT` gövdesine yapıştırılabilir.
    """
    for ad in SENARYOLAR:
        print(f'    "{ad}": {_kayit(_calistir(ad))!r},')


@pytest.mark.parametrize("ad", sorted(SENARYOLAR))
def test_dagitim_altin_kayitla_birebir_ayni(ad: str) -> None:
    """Kural KAPALIYKEN motor çıktısı değişmemelidir (sürümler arası determinizm)."""
    assert _kayit(_calistir(ad)) == ALTIN_KAYIT[ad]


def test_altin_kayit_senaryolari_eksiksiz() -> None:
    """Senaryo eklenip kaydı unutulursa test sessizce zayıflamasın."""
    assert set(ALTIN_KAYIT) == set(SENARYOLAR)
