"""Bağımsız yerleşim doğrulayıcı — sert kısıtlar + mesafe metrikleri (T5).

MOTORDAN AYRI yazılmıştır (ADR-0016 karar 3): engine.py'dan hiçbir şey import
etmez; sert kısıtları sıfırdan denetler ve R8 raporunun mesafe metriklerini
üretir. Test omurgası budur — motorun her çıktısı buradan geçer.

Kısıt modeli (K8):
- SERT: aynı çakışma grubundan iki öğrenci aynı sırada (desk) oturamaz.
  Denetim MESAFEDEN DEĞİL (desk_row, desk_col) kimliğinden yapılır — aynı-sıra
  ve komşu-sıra koltuk araları çakışabilir (T3 testiyle belgelendi).
- SERT (20.09.2026, kız/erkek ayrışması — `separation` parametresi): AYRIŞMA
  anahtarı farklı iki öğrenci aynı sırada (DESK kipi) ya da aynı salonda (ROOM
  kipi) bulunamaz. Doğrulayıcı anahtarın NE olduğunu bilmez (motorla aynı
  soyutlama); kullanıcıya görünen sözcük isteğe bağlı ETİKETTEN gelir. Boş
  anahtar JOKER'dir: denetime hiç girmez.
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
    # İhlal metninin İDARECİ DİLİ (18.09.2026): salon adı, sıra konumu ("3. sıra,
    # 1. sütun"), ders etiketi ve okul numarası. Doğrulayıcı saf kalır — etiketleri
    # servis verir; hiçbiri denetime GİRMEZ (denetim kimlik ve koordinattandır).
    # Etiketsiz kurulumda metinler eski ham biçimine düşer (motor testleri).
    room_label: str = ""
    desk_label: str = ""
    group_label: str = ""
    student_number: str = ""
    #: Ayrışma anahtarı ("K"/"E"/boş) ve onun İDARECİ DİLİNDEKİ karşılığı
    #: ("kız"/"erkek"). Anahtar DENETİME, etiket yalnız METNE girer.
    separation_key: str = ""
    separation_label: str = ""


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
    # separate_sections yumuşak cezası değerlendirilir, ADR-0044). 19.09.2026'dan
    # beri seçmeli ders öğrenci listesiyle sahada oluşur (9/A'nın bir grubu
    # Kur'an-ı Kerim, kalanı Peygamberimizin Hayatı — aynı şube, iki grup).
    cross_group_same_section_first_ring_pairs: int = 0
    # Salon başına yerleşen öğrenci sayısı (doluluk gözlemi; her düzende dolar).
    room_counts: dict[int, int] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return not self.hard_violations


def _where(p: PlacedStudent) -> str:
    """İhlalin yeri: "Salon 101, 3. sıra, 1. sütun" (etiketsizse ham koordinat)."""
    room = p.room_label or f"salon {p.room_id}"
    desk = p.desk_label or f"sıra ({p.desk_row},{p.desk_col})"
    return f"{room}, {desk}"


def _exam_text(p: PlacedStudent) -> str:
    """İhlalin konusu: ders etiketi (etiketsizse ham çakışma grubu anahtarı)."""
    return f"“{p.group_label}”" if p.group_label else f"'{p.conflict_group}' grubu"


def _same_desk(a: PlacedStudent, b: PlacedStudent) -> bool:
    return a.room_id == b.room_id and a.desk_row == b.desk_row and a.desk_col == b.desk_col


def _first_ring(a: PlacedStudent, b: PlacedStudent) -> bool:
    """Komşu sıra grubu mu (aynı salon, farklı sıra, Chebyshev ≤ 1)?"""
    if a.room_id != b.room_id or _same_desk(a, b):
        return False
    return max(abs(a.desk_row - b.desk_row), abs(a.desk_col - b.desk_col)) <= 1


#: `separation` kipleri — `sinav.models.SeparationMode` ile AYNI değerler.
#: Doğrulayıcı saf kalsın diye models import EDİLMEZ (motor-bağımsızlık deseni).
SEPARATION_NONE = "NONE"
SEPARATION_DESK = "DESK"
SEPARATION_ROOM = "ROOM"


def _separation_text(p: PlacedStudent) -> str:
    """Ayrışma anahtarının idareci dilindeki karşılığı (etiketsizse ham anahtar)."""
    return p.separation_label or p.separation_key


def _who(p: PlacedStudent) -> str:
    """İhlal metninde öğrenci: KVKK gereği ad değil okul numarası."""
    return f"okul no {p.student_number}" if p.student_number else f"id={p.student_id}"


def _check_separation(placed: list[PlacedStudent], report: SeatingReport, *, mode: str) -> None:
    """Ayrışma kuralının sert denetimi — aynı sıra (DESK) / aynı salon (ROOM).

    Anahtarı boş olan öğrenci JOKER'dir ve hiçbir çifte girmez (K4 kullanıcı
    kararı: cinsiyeti bilinmeyen öğrenci dağıtımı durdurmaz). Her kapsam için
    YALNIZ BİR ihlal satırı yazılır: 40 kişilik bir salonda ROOM kipi
    yüzlerce çift üretirdi, idareciye sayfalarca aynı cümle basılmaz.
    """
    kapsamlar: dict[tuple[int, int, int] | tuple[int], list[PlacedStudent]] = {}
    for p in placed:
        if not p.separation_key:
            continue
        anahtar = (p.room_id, p.desk_row, p.desk_col) if mode == SEPARATION_DESK else (p.room_id,)
        kapsamlar.setdefault(anahtar, []).append(p)

    for uyeler in kapsamlar.values():
        farkli = {u.separation_key for u in uyeler}
        if len(farkli) < 2:
            continue
        a = uyeler[0]
        b = next(u for u in uyeler if u.separation_key != a.separation_key)
        if mode == SEPARATION_DESK:
            report.hard_violations.append(
                f"Ayrı oturma ihlali: {_separation_text(a)} ve {_separation_text(b)} öğrenci "
                f"aynı sırada oturuyor ({_where(a)}; {_who(a)} ve {_who(b)})."
            )
        else:
            salon = a.room_label or f"salon {a.room_id}"
            report.hard_violations.append(
                f"Ayrı salon ihlali: {salon} salonunda hem {_separation_text(a)} hem "
                f"{_separation_text(b)} öğrenci var ({len(uyeler)} öğrenci)."
            )


def validate_seating(
    placed: list[PlacedStudent],
    *,
    strict: bool = False,
    enforce_group_separation: bool = True,
    separation: str = SEPARATION_NONE,
) -> SeatingReport:
    """Sert kısıtları sıfırdan denetler ve mesafe metriklerini üretir.

    `enforce_group_separation=False` KLASİK düzen içindir (kendi dersliğinde —
    K3): tüm şube aynı çakışma grubudur ve bitişik oturma beklenen durumdur;
    yalnız bütünlük (çifte koltuk / çifte öğrenci) denetlenir, ayrışma
    metrikleri üretilmez. O(n²) çift taraması — salon ölçeğinde yeterli;
    motorun artımlı hesabından bilinçli olarak BAĞIMSIZ tutulmuştur.

    `separation` AYRIŞMA ANAHTARI kuralıdır (kız/erkek — 20.09.2026) ve
    yukarıdakinden BAĞIMSIZ bir kısıttır: "DESK" aynı sırayı, "ROOM" aynı
    salonu yasaklar. Klasik düzende hiç uygulanmaz (K6 kullanıcı kararı) —
    fonksiyon `enforce_group_separation=False` dalında zaten erken döner.
    """
    report = SeatingReport()

    # Aynı koltuğa çift yerleşim / aynı öğrenci iki koltukta — temel bütünlük.
    seat_keys: dict[tuple[int, int, int, int], int] = {}
    student_seen: set[int] = set()
    for p in placed:
        key = (p.room_id, p.desk_row, p.desk_col, p.slot)
        if key in seat_keys:
            report.hard_violations.append(
                f"Koltuk çifte dolu: {_where(p)}, {p.slot + 1}. koltuğa iki öğrenci yazılmış."
            )
        seat_keys[key] = p.student_id
        if p.student_id in student_seen:
            # KVKK: ihlal metninde öğrenci ADI geçmez; okul numarası yeter.
            report.hard_violations.append(f"Öğrenci iki koltukta: {_who(p)}.")
        student_seen.add(p.student_id)
        # Doluluk sayacı (K1) — her düzende dolar (klasik dahil).
        report.room_counts[p.room_id] = report.room_counts.get(p.room_id, 0) + 1

    if not enforce_group_separation:
        # Klasik düzen (kendi dersliğinde): kız/erkek ayrışması da UYGULANMAZ
        # (K6 kullanıcı kararı) — herkes kendi şubesinde, okul no sırasında.
        return report  # klasik düzen: yalnız bütünlük denetimi

    if separation in (SEPARATION_DESK, SEPARATION_ROOM):
        _check_separation(placed, report, mode=separation)

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
                        f"Bitişik masa ihlali: {_exam_text(a)} sınavına giren iki öğrenci "
                        f"aynı sırada oturuyor ({_where(a)})."
                    )
                    continue
                dist = math.dist((a.x, a.y), (b.x, b.y))
                min_dist = min(min_dist, dist)
                report.proximity_score += 1.0 / (dist * dist)
                if _first_ring(a, b):
                    report.first_ring_same_group_pairs += 1
                    if strict:
                        other = b.desk_label or f"({b.desk_row},{b.desk_col})"
                        report.hard_violations.append(
                            f"Katı dağıtım ihlali: {_exam_text(a)} sınavına giren iki öğrenci "
                            f"komşu sıralarda oturuyor ({_where(a)} ↔ {other})."
                        )
        if len(members) > 1 and math.isfinite(min_dist):
            report.min_same_group_distance[group] = round(min_dist, 4)

    return report
