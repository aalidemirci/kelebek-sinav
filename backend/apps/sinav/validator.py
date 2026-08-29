"""Bağımsız yerleşim doğrulayıcı — sert kısıtlar + mesafe metrikleri (T5).

MOTORDAN AYRI yazılmıştır (ADR-0016 karar 3): engine.py'dan hiçbir şey import
etmez; sert kısıtları sıfırdan denetler ve R8 raporunun mesafe metriklerini
üretir. Test omurgası budur — motorun her çıktısı buradan geçer.

Kısıt modeli (K8):
- SERT: aynı çakışma grubundan iki öğrenci aynı sırada (desk) oturamaz.
  Denetim MESAFEDEN DEĞİL (desk_row, desk_col) kimliğinden yapılır — aynı-sıra
  ve komşu-sıra koltuk araları çakışabilir (T3 testiyle belgelendi).
- KATI MOD: birinci halka da sert sayılır — komşu sıra grupları
  (Chebyshev mesafe ≤ 1: yan/ön/arka/çapraz) aynı gruptan öğrenci içeremez.
- ESNEK: toplam yakınlık skoru Σ 1/d² (aynı-grup çiftleri; d = Öklid, grid
  birimi) minimize edilmesi hedeflenir; doğrulayıcı yalnız ölçer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlacedStudent:
    """Doğrulayıcı girdisi — tek yerleşmiş öğrenci (motor-bağımsız)."""

    student_id: int
    conflict_group: str
    room_id: int
    desk_row: int
    desk_col: int
    slot: int
    x: float
    y: float
    # Şube etiketi ("9/A") — FAZ K1 gözlemlenebilirlik: GROUPS-tipi farklı-grup
    # aynı-şube komşuluğu metriği için. Varsayılanlı (geriye uyumlu — eski
    # çağıranlar/testler etiketsiz kurabilir; boş etiket metriğe girmez).
    section_label: str = ""


@dataclass
class SeatingReport:
    """Doğrulama sonucu + R8 mesafe metrikleri."""

    hard_violations: list[str] = field(default_factory=list)
    # Birinci halkada (komşu sıra, Chebyshev ≤1) aynı-grup çift sayısı.
    first_ring_same_group_pairs: int = 0
    # Grup başına en yakın aynı-grup komşu mesafesi (Öklid; tek üyeli grup hariç).
    min_same_group_distance: dict[str, float] = field(default_factory=dict)
    # Toplam yakınlık skoru Σ 1/d² (aynı-grup çiftleri; aynı sıra hariç —
    # onlar sert ihlaldir ve ayrıca listelenir).
    proximity_score: float = 0.0
    # FAZ K1 (Tur 645) gözlemlenebilirlik — ihlal DEĞİL, sayaç:
    # Aynı şubeden (section_label eşit, boş değil) FARKLI çakışma grubundan iki
    # öğrencinin 1. halka komşuluğu — GROUPS-tipi ayrım açık ucu (farklı kitapçık
    # → kopya riski düşük; metrik sahada anlamlı sayı üretirse V2'de
    # separate_sections yumuşak cezası değerlendirilir, ADR-0044).
    cross_group_same_section_first_ring_pairs: int = 0
    # Salon başına yerleşen öğrenci sayısı (doluluk gözlemi; her düzende dolar).
    room_counts: dict[int, int] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return not self.hard_violations


def _same_desk(a: PlacedStudent, b: PlacedStudent) -> bool:
    return a.room_id == b.room_id and a.desk_row == b.desk_row and a.desk_col == b.desk_col


def _first_ring(a: PlacedStudent, b: PlacedStudent) -> bool:
    """Komşu sıra grubu mu (aynı salon, farklı sıra, Chebyshev ≤ 1)?"""
    if a.room_id != b.room_id or _same_desk(a, b):
        return False
    return max(abs(a.desk_row - b.desk_row), abs(a.desk_col - b.desk_col)) <= 1


def validate_seating(
    placed: list[PlacedStudent],
    *,
    strict: bool = False,
    enforce_group_separation: bool = True,
) -> SeatingReport:
    """Sert kısıtları sıfırdan denetler ve mesafe metriklerini üretir.

    `enforce_group_separation=False` KLASİK düzen içindir (kendi dersliğinde —
    K3): tüm şube aynı çakışma grubudur ve bitişik oturma beklenen durumdur;
    yalnız bütünlük (çifte koltuk / çifte öğrenci) denetlenir, ayrışma
    metrikleri üretilmez. O(n²) çift taraması — salon ölçeğinde yeterli;
    motorun artımlı hesabından bilinçli olarak BAĞIMSIZ tutulmuştur.
    """
    report = SeatingReport()

    # Aynı koltuğa çift yerleşim / aynı öğrenci iki koltukta — temel bütünlük.
    seat_keys: dict[tuple[int, int, int, int], int] = {}
    student_seen: set[int] = set()
    for p in placed:
        key = (p.room_id, p.desk_row, p.desk_col, p.slot)
        if key in seat_keys:
            report.hard_violations.append(
                f"Koltuk çifte dolu: salon {p.room_id} sıra ({p.desk_row},{p.desk_col}) "
                f"pozisyon {p.slot}."
            )
        seat_keys[key] = p.student_id
        if p.student_id in student_seen:
            report.hard_violations.append(f"Öğrenci iki koltukta: id={p.student_id}.")
        student_seen.add(p.student_id)
        # Doluluk sayacı (K1) — her düzende dolar (klasik dahil).
        report.room_counts[p.room_id] = report.room_counts.get(p.room_id, 0) + 1

    if not enforce_group_separation:
        return report  # klasik düzen: yalnız bütünlük denetimi

    # K1: GROUPS-tipi açık uç sayacı — aynı şube, FARKLI grup, 1. halka komşu.
    # Salon bazlı O(n²) çift taraması (grup-içi döngüler bu çiftleri görmez).
    by_room: dict[int, list[PlacedStudent]] = {}
    for p in placed:
        by_room.setdefault(p.room_id, []).append(p)
    for members_in_room in by_room.values():
        for i in range(len(members_in_room)):
            for j in range(i + 1, len(members_in_room)):
                a, b = members_in_room[i], members_in_room[j]
                if (
                    a.section_label
                    and a.section_label == b.section_label
                    and a.conflict_group != b.conflict_group
                    and _first_ring(a, b)
                ):
                    report.cross_group_same_section_first_ring_pairs += 1

    by_group: dict[str, list[PlacedStudent]] = {}
    for p in placed:
        by_group.setdefault(p.conflict_group, []).append(p)

    for group, members in by_group.items():
        min_dist = math.inf
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                if a.room_id != b.room_id:
                    continue
                if _same_desk(a, b):
                    report.hard_violations.append(
                        f"Bitişik masa ihlali: '{group}' grubundan iki öğrenci aynı sırada "
                        f"(salon {a.room_id}, sıra ({a.desk_row},{a.desk_col}))."
                    )
                    continue
                dist = math.dist((a.x, a.y), (b.x, b.y))
                min_dist = min(min_dist, dist)
                report.proximity_score += 1.0 / (dist * dist)
                if _first_ring(a, b):
                    report.first_ring_same_group_pairs += 1
                    if strict:
                        report.hard_violations.append(
                            f"Katı mod ihlali: '{group}' grubundan iki öğrenci komşu sırada "
                            f"(salon {a.room_id}, ({a.desk_row},{a.desk_col}) ↔ "
                            f"({b.desk_row},{b.desk_col}))."
                        )
        if len(members) > 1 and math.isfinite(min_dist):
            report.min_same_group_distance[group] = round(min_dist, 4)

    return report
