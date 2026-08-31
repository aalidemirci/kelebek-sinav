"""Kelebek dağıtım motoru — iki fazlı, deterministik (T5; ADR-0016 karar 3).

Girdi: çakışma grupları (K7 — participants.resolve_session çıktısı) + seçili
salonların numaralandırılmış koltukları (T3 layout.numbered_seats). Çıktı:
koltuk atamaları (saf veri — DB yazımı services.distribute_session'da).

Algoritma:
- Faz 0 — üç kademe (Tur 243, talep 6): (1) salon kotaları kapasiteler
  oranında en-büyük-kalan ile (E2 doluluk dengesi); (2) her çakışma grubunun
  mevcudu salon kotalarına oranla bölünür; (3) grup içi ŞUBELER first-fit-
  decreasing ile salonlara bütün olarak paketlenir — şube başına salon sayısı
  asgariye iner ("kaynaşma" riski; eski global dilimleme şubeyi 4-6 salona
  serpiyordu). Salon-içi karışım `_deal_order` harmanıyla korunur.
- Faz 1 — kurucu: koltuklar S-ROTA sırasında gezilir; her koltuğa, akışta
  uygun ilk öğrenci (kuyruk rotasyonu) yerleştirilir. Komşuluk denetimi rota
  sırasından DEĞİL 2D geometriden yapılır (kritik tuzak: rotada uzak iki
  koltuk fiziksel komşu olabilir). Uygun aday yoksa en az ceza üreten aday
  yerleştirilir (kalan ihlal Faz 2 + doğrulayıcıya kalır).
- Faz 2 — yerel arama: `random.Random(seed)` ile beslenen, sabit iterasyon
  bütçeli salon-içi ikili takas; skor Σ 1/d² (aynı-grup çiftleri; AYNI SIRA =
  sonsuz ceza ⇒ sert kısıt asla geri gelmez). Aynı seed → aynı sonuç.

Kenar durumlar:
- TEK grup + kapasite ≥ 2×N → satranç modu: sıra başına tek koltuk kullanılır
  (bitişik masa matematiksel olarak imkânsızlaşır).
- Baskın grup (> toplam kapasitenin yarısı) → uyarı (ihlalsiz çözüm garanti
  edilemez; en iyi skor + açık ihlal listesi).

Doğrulama BURADA DEĞİL: bağımsız `validator.validate_seating` motorun her
çıktısını sıfırdan denetler (test omurgası).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from apps.sinav.layout import Seat
from apps.sinav.participants import Participant

#: Yerel arama iterasyon bütçesi katsayısı (koltuk başına) ve tavanı.
_SWAP_BUDGET_PER_SEAT = 40
_SWAP_BUDGET_MAX = 6000

#: Kurucu fazda kuyruk rotasyonunda denenecek azami aday sayısı.
_LOOKAHEAD = 24

#: Ceza demeti: (birincil, ikincil). Birincil = sert/yumuşak yakınlık cezası
#: (bugünkü skaler); ikincil = kaçınılmaz komşu çiftlerin odağa uzaklığı.
#: Karşılaştırma Python'un doğal leksikografik demet karşılaştırmasıdır.
Penalty = tuple[float, float]

_ZERO_PENALTY: Penalty = (0.0, 0.0)


def _add(a: Penalty, b: Penalty) -> Penalty:
    return (a[0] + b[0], a[1] + b[1])


@dataclass(frozen=True)
class RoomSeats:
    """Motor girdisi: bir salonun kullanılabilir koltukları (rota sıralı).

    `focus` salonun ODAK noktasıdır — öğretmen masası (yoksa tahta, yoksa
    (0,0)) — ve EKSEN SIRASI koltuk koordinatlarıyla aynıdır: (x=sütun,
    y=satır). `layout.reference_cell` (satır, sütun) döndürür; çeviriyi
    çağıran yapar. Varsayılan (0.0, 0.0) mobilyasız planların bugünkü
    davranışını korur.
    """

    room_id: int
    seats: tuple[Seat, ...]
    focus: tuple[float, float] = (0.0, 0.0)


@dataclass(frozen=True)
class Placement:
    """Motor çıktısı: tek atama (saf veri)."""

    participant: Participant
    room_id: int
    seat: Seat


@dataclass
class DistributionResult:
    placements: list[Placement] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checkerboard: bool = False
    seed: int = 0


def _deal_order(participants: list[Participant]) -> list[Participant]:
    """Gruplar büyükten küçüğe ağırlıklı round-robin akışı (Faz 0 karışımı).

    Deterministik: grup sırası (boyut azalan, anahtar artan); grup içi sıra
    çözümleyicinin verdiği sıradır (şube + okul no).
    """
    groups: dict[str, list[Participant]] = {}
    for p in participants:
        groups.setdefault(p.conflict_group, []).append(p)
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    queues = [list(members) for _, members in ordered]
    stream: list[Participant] = []
    while any(queues):
        for queue in queues:
            if queue:
                stream.append(queue.pop(0))
    return stream


def _room_quotas(stream_len: int, capacities: list[int]) -> list[int]:
    """En-büyük-kalan yöntemiyle salon kotaları (E2 doluluk dengesi)."""
    total = sum(capacities)
    raw = [stream_len * cap / total for cap in capacities]
    quotas = [math.floor(r) for r in raw]
    remainder = stream_len - sum(quotas)
    # Kalanlar en büyük kesirli paya; kapasitesi dolan salon atlanır.
    order = sorted(range(len(raw)), key=lambda i: raw[i] - quotas[i], reverse=True)
    idx = 0
    while remainder > 0:
        i = order[idx % len(order)]
        if quotas[i] < capacities[i]:
            quotas[i] += 1
            remainder -= 1
        idx += 1
    return quotas


def _group_room_quotas(group_sizes: dict[str, int], quotas: list[int]) -> dict[str, list[int]]:
    """Her çakışma grubunun salon bazlı kotaları (Tur 243, talep 6 — Faz 0 kademe 2).

    Gruplar büyükten küçüğe (anahtar artan tie-break) işlenir; her grup kalan
    salon kotalarına oranla en-büyük-kalan ile bölünür. Toplamlar salon
    kotalarına TAM eşitlenir (Σgrup = Σkota olduğundan fizibilite garanti).
    Deterministik — rng yok.
    """
    remaining = list(quotas)
    out: dict[str, list[int]] = {}
    for key in sorted(group_sizes, key=lambda k: (-group_sizes[k], k)):
        size = group_sizes[key]
        total_rem = sum(remaining)
        raw = [size * r / total_rem if total_rem else 0.0 for r in remaining]
        alloc = [math.floor(x) for x in raw]
        leftover = size - sum(alloc)
        order = sorted(range(len(raw)), key=lambda i: raw[i] - alloc[i], reverse=True)
        idx = 0
        while leftover > 0:
            i = order[idx % len(order)]
            if alloc[i] < remaining[i]:
                alloc[i] += 1
                leftover -= 1
            idx += 1
        out[key] = alloc
        remaining = [r - a for r, a in zip(remaining, alloc, strict=True)]
    return out


def _pack_section_chunks(
    participants: list[Participant],
    group_quotas: dict[str, list[int]],
    room_count: int,
) -> list[list[Participant]]:
    """Şube-hizalı salon parçaları (Tur 243, talep 6 — Faz 0 kademe 3).

    Eski akış (global round-robin akışından sıralı dilim) bir şubeyi 4-6
    salona serpiyordu — tekrarlanan sınavlarda seviye genelinde "kaynaşma"
    (tanışıklık → kopya riski) doğuruyordu. Yeni akış her grubun içini
    ŞUBELERE ayırır ve şubeleri first-fit-decreasing ile salonlara BÜTÜN
    olarak paketler (sığmazsa artık bir sonraki en boş salona taşar) —
    şube başına salon sayısı tipik girdide 1-2'ye düşer. Şube içi okul no
    sırası (çözümleyici sırası) korunur; deterministik.
    """
    chunks: list[list[Participant]] = [[] for _ in range(room_count)]
    by_group: dict[str, list[Participant]] = {}
    for p in participants:
        by_group.setdefault(p.conflict_group, []).append(p)
    for key in sorted(by_group, key=lambda k: (-len(by_group[k]), k)):
        members = by_group[key]
        remaining = list(group_quotas[key])
        by_section: dict[tuple[int, str], list[Participant]] = {}
        for p in members:
            by_section.setdefault((p.class_level, p.class_section), []).append(p)
        for skey in sorted(by_section, key=lambda s: (-len(by_section[s]), s)):
            students = by_section[skey]
            i = 0
            while i < len(students):
                # Bu grup için en çok boş kotası kalan salon (eşitlikte düşük indeks).
                j = max(range(room_count), key=lambda r: (remaining[r], -r))
                take = min(remaining[j], len(students) - i)
                if take == 0:
                    break  # kota tükendi — Σalloc = Σgrup garantisiyle erişilmez
                chunks[j].extend(students[i : i + take])
                remaining[j] -= take
                i += take
    return chunks


#: Birinci halka (komşu sıra) iç ceza ağırlığı — E1 hedefi "1. halka = 0"
#: olduğundan arama bu çiftleri yok etmeye güçlü biçimde yönlendirilir.
#: Bağımsız doğrulayıcı bu ağırlığı KULLANMAZ (saf 1/d² metriği raporlar).
_FIRST_RING_WEIGHT = 10.0

#: Önceki oturumla AYNI sıraya düşme iç cezası (T6 "önceki oturum farklılığı":
#: aynı seviyedeki öğrenci her sınavda farklı yerde otursun). Yumuşak kısıt —
#: sert kısıtların ve 1. halka hedefinin altında kalır.
_PREV_SEAT_WEIGHT = 5.0

#: Önceki koltuk haritası tipi: student_id → (room_id, desk_row, desk_col).
PrevSeats = dict[int, tuple[int, int, int]]


def _prev_penalty(student: Participant, room_id: int, seat: Seat, prev_seats: PrevSeats) -> float:
    """Öğrenci önceki oturumdaki sırasına dönüyorsa yumuşak ceza."""
    prev = prev_seats.get(student.student_id)
    if prev is not None and prev == (room_id, seat.desk_row, seat.desk_col):
        return _PREV_SEAT_WEIGHT
    return 0.0


def _pair_penalty(a_seat: Seat, b_seat: Seat, focus: tuple[float, float]) -> Penalty:
    """Aynı-grup çifti İÇ cezası — LEKSİKOGRAFİK İKİLİ (birincil, ikincil).

    BİRİNCİL bugünkü skalerin BİTİ BİTİNE aynısıdır: aynı sıra = ∞ (sert
    kısıt); 1. halka ağır; diğer 1/d². Sert kısıt gevşetilmez, doğrulayıcıya
    yeni ihlal eklenmez.

    İKİNCİL yalnız KOMŞU çiftlerde (Chebyshev ≤ 1, aynı masa dâhil) devreye
    girer ve çiftin odağa (öğretmen masası) toplam uzaklığıdır. Kullanıcı
    isteği (31.08.2026): "öğrenci sayıları karmaya müsait değilse aynı sınava
    girip yanyana oturanlar ön sıralarda ve öğretmen masasına yakın olsun."

    Demet karşılaştırması doğal leksikografiktir: ikincil ancak birincil TAM
    EŞİTKEN karar verir. Bu yüzden bugün kabul edilen her hamle hâlâ kabul
    edilir ve ihlal sayısı (birincilin ∞ olduğu çift sayısı) YAPISAL OLARAK
    artamaz.
    """
    dr = abs(a_seat.desk_row - b_seat.desk_row)
    dc = abs(a_seat.desk_col - b_seat.desk_col)
    komsu = max(dr, dc) <= 1
    ikincil = (
        math.dist((a_seat.x, a_seat.y), focus) + math.dist((b_seat.x, b_seat.y), focus)
        if komsu
        else 0.0
    )
    if dr == 0 and dc == 0:
        return (math.inf, ikincil)
    d2 = (a_seat.x - b_seat.x) ** 2 + (a_seat.y - b_seat.y) ** 2
    base = 1.0 / d2 if d2 > 0 else math.inf
    if komsu:
        return (base + _FIRST_RING_WEIGHT, ikincil)
    return (base, 0.0)


def _placement_penalty(
    seat: Seat,
    group: str,
    occupied: list[tuple[Seat, str]],
    *,
    strict: bool,
    focus: tuple[float, float],
) -> Penalty:
    """Koltuğa bu gruptan öğrenci koymanın mevcut yerleşime göre ceza demeti."""
    penalty: Penalty = _ZERO_PENALTY
    for other_seat, other_group in occupied:
        if other_group != group:
            continue
        p = _pair_penalty(seat, other_seat, focus)
        if strict and math.isfinite(p[0]):
            ring = max(
                abs(seat.desk_row - other_seat.desk_row),
                abs(seat.desk_col - other_seat.desk_col),
            )
            if ring <= 1:
                return (math.inf, p[1])
        penalty = _add(penalty, p)
        if math.isinf(penalty[0]):
            return penalty
    return penalty


def _constructive_fill(
    room: RoomSeats,
    students: list[Participant],
    *,
    strict: bool,
    warnings: list[str],
    fixed: list[tuple[Seat, str]] | None = None,
    prev_seats: PrevSeats | None = None,
) -> list[Placement]:
    """Faz 1 — kuyruk rotasyonlu kurucu yerleştirme (deterministik).

    `fixed`: salondaki SABİT (kural pinli) yerleşimler — koltukları kullanılmaz,
    komşuluk/ceza hesabına girerler ama asla taşınmazlar (T6).
    """
    queue = list(students)
    occupied: list[tuple[Seat, str]] = list(fixed or [])
    fixed_keys = {(s.desk_row, s.desk_col, s.slot) for s, _ in occupied}
    prev = prev_seats or {}
    placements: list[Placement] = []
    for seat in room.seats:
        if (seat.desk_row, seat.desk_col, seat.slot) in fixed_keys:
            continue  # koltuk sabit yerleşimde dolu
        if not queue:
            break
        chosen_idx: int | None = None
        best_idx: int = 0
        best_penalty: Penalty = (math.inf, math.inf)
        for idx in range(min(len(queue), _LOOKAHEAD)):
            penalty = _add(
                _placement_penalty(
                    seat, queue[idx].conflict_group, occupied, strict=strict, focus=room.focus
                ),
                (_prev_penalty(queue[idx], room.room_id, seat, prev), 0.0),
            )
            if penalty[0] == 0.0:
                chosen_idx = idx
                break
            if penalty < best_penalty:
                best_idx, best_penalty = idx, penalty
        if chosen_idx is None:
            chosen_idx = best_idx
            if math.isinf(best_penalty[0]):
                warnings.append(
                    f"Salon {room.room_id}: ({seat.desk_row},{seat.desk_col}) sırasında "
                    f"sert kısıt kaçınılmaz oldu (kuyrukta uygun aday yok)."
                )
        student = queue.pop(chosen_idx)
        occupied.append((seat, student.conflict_group))
        placements.append(Placement(participant=student, room_id=room.room_id, seat=seat))
    if queue:
        warnings.append(f"Salon {room.room_id}: {len(queue)} öğrenci koltuk bulamadı (kota aşımı).")
    return placements


def _student_penalty_at(
    placements: list[Placement],
    idx: int,
    seat: Seat,
    *,
    fixed: list[tuple[Seat, str]] | None = None,
    room_id: int = 0,
    prev_seats: PrevSeats | None = None,
    focus: tuple[float, float] = (0.0, 0.0),
) -> Penalty:
    """idx'teki öğrencinin `seat`e taşınması hâlinde toplam ceza demeti.

    Hareketli diğer öğrenciler + SABİT yerleşimler (taşınamazlar ama ceza
    üretirler) + önceki-oturum aynı-sıra terimi hesaba katılır.
    """
    student = placements[idx].participant
    me = student.conflict_group
    total: Penalty = (_prev_penalty(student, room_id, seat, prev_seats or {}), 0.0)
    for k, other in enumerate(placements):
        if k == idx or other.participant.conflict_group != me:
            continue
        total = _add(total, _pair_penalty(seat, other.seat, focus))
        if math.isinf(total[0]):
            return total
    for fixed_seat, fixed_group in fixed or []:
        if fixed_group != me:
            continue
        total = _add(total, _pair_penalty(seat, fixed_seat, focus))
        if math.isinf(total[0]):
            return total
    return total


def _local_search(
    placements: list[Placement],
    *,
    room: RoomSeats,
    rng: random.Random,
    fixed: list[tuple[Seat, str]] | None = None,
    prev_seats: PrevSeats | None = None,
) -> None:
    """Faz 2 — salon-içi yerel arama: ikili takas + BOŞ koltuğa taşınma.

    Boş koltuk hamlesi kritik: kapasite > öğrenci sayısıyken kurucu faz rota
    başına yığar; yayılma ancak boş koltuklara taşınmayla mümkün olur. SABİT
    yerleşimler hamle uzayında YOKTUR (taşınmaz/takas edilmez) ama cezaya
    girer. Yalnız iyileştiren hamle kabul edilir (deterministik, seed'li rng).
    """
    n = len(placements)
    if n == 0:
        return
    fixed = list(fixed or [])
    fixed_keys = {(s.desk_row, s.desk_col, s.slot) for s, _ in fixed}
    used = {(p.seat.desk_row, p.seat.desk_col, p.seat.slot) for p in placements} | fixed_keys
    free_seats = [s for s in room.seats if (s.desk_row, s.desk_col, s.slot) not in used]
    budget = min(_SWAP_BUDGET_MAX, _SWAP_BUDGET_PER_SEAT * max(n, len(room.seats)))

    def penalty_at(i: int, seat: Seat) -> Penalty:
        return _student_penalty_at(
            placements,
            i,
            seat,
            fixed=fixed,
            room_id=room.room_id,
            prev_seats=prev_seats,
            focus=room.focus,
        )

    for _ in range(budget):
        if free_seats and (n < 2 or rng.random() < 0.5):
            # Taşınma: rastgele öğrenci → rastgele boş koltuk.
            i = rng.randrange(n)
            f = rng.randrange(len(free_seats))
            current, candidate = placements[i], free_seats[f]
            if penalty_at(i, candidate) < penalty_at(i, current.seat):
                placements[i] = Placement(
                    participant=current.participant, room_id=current.room_id, seat=candidate
                )
                free_seats[f] = current.seat
            continue
        if n < 2:
            continue
        i, j = rng.randrange(n), rng.randrange(n)
        if i == j:
            continue
        a, b = placements[i], placements[j]
        if a.participant.conflict_group == b.participant.conflict_group:
            continue  # aynı grubun takası skoru değiştirmez (prev terimi hariç — ihmal)
        before = _add(penalty_at(i, a.seat), penalty_at(j, b.seat))
        # Takas sonrası (birbirlerine cezaları her iki yönde de hesaba girer;
        # çifte sayım her iki tarafta simetrik olduğundan karşılaştırma doğru).
        after = _add(penalty_at(i, b.seat), penalty_at(j, a.seat))
        if after < before:
            placements[i] = Placement(participant=a.participant, room_id=a.room_id, seat=b.seat)
            placements[j] = Placement(participant=b.participant, room_id=b.room_id, seat=a.seat)


def _checkerboard_seats(room: RoomSeats) -> RoomSeats:
    """Satranç modu: sıra (desk) başına TEK koltuk — bitişik masa imkânsız."""
    seen_desks: set[tuple[int, int]] = set()
    picked: list[Seat] = []
    for seat in room.seats:
        key = (seat.desk_row, seat.desk_col)
        if key in seen_desks:
            continue
        seen_desks.add(key)
        picked.append(seat)
    # focus TAŞINMALI — yeniden kurulan RoomSeats'te düşerse satranç modunda
    # odak sessizce (0,0)'a döner ve ikincil ceza yanlış ucu seçer.
    return RoomSeats(room_id=room.room_id, seats=tuple(picked), focus=room.focus)


def distribute_butterfly(
    participants: list[Participant],
    rooms: list[RoomSeats],
    *,
    seed: int,
    strict: bool = False,
    preplaced: list[Placement] | None = None,
    previous_seats: PrevSeats | None = None,
) -> DistributionResult:
    """Kelebek dağıtımı — iki fazlı, seed'li deterministik.

    `preplaced` (T6): kural pinli yerleşimler — koltukları kullanım dışıdır,
    komşuluk cezasına girerler, motor onları ASLA taşımaz; sonuç listesine
    DAHİL EDİLMEZLER (çağıran birleştirir). `previous_seats` (T6): öğrencinin
    önceki oturumdaki sırası — aynı sıraya dönüş yumuşak cezayla caydırılır.
    Kapasite yetersizse ValueError (Türkçe) fırlatır; çağıran (servis) bunu
    ValidationError'a çevirir.
    """
    result = DistributionResult(seed=seed)
    pinned = list(preplaced or [])
    prev = previous_seats or {}
    if not participants and not pinned:
        result.warnings.append("Dağıtılacak katılımcı yok.")
        return result

    group_sizes: dict[str, int] = {}
    for p in participants:
        group_sizes[p.conflict_group] = group_sizes.get(p.conflict_group, 0) + 1

    # Sabit yerleşimlerin koltukları kullanılamaz; salon bazında ayrıştır.
    fixed_by_room: dict[int, list[tuple[Seat, str]]] = {}
    for pl in pinned:
        fixed_by_room.setdefault(pl.room_id, []).append((pl.seat, pl.participant.conflict_group))

    def _available(room: RoomSeats) -> int:
        return len(room.seats) - len(fixed_by_room.get(room.room_id, []))

    total_capacity = sum(_available(r) for r in rooms)
    n = len(participants)
    if n > total_capacity:
        raise ValueError(
            f"Kapasite yetersiz: {n} öğrenci / {total_capacity} koltuk. Salon ekleyin."
        )

    # Tek grup + bol kapasite → satranç modu (sıra başına tek koltuk).
    # Sabit yerleşim varken satranç koltuk seçimi pinli koltuklarla çakışabilir;
    # bu durumda mod atlanır (pin > satranç önceliği).
    if not pinned and len(group_sizes) == 1 and total_capacity >= 2 * n:
        candidate = [_checkerboard_seats(r) for r in rooms]
        if sum(len(r.seats) for r in candidate) >= n:
            rooms = candidate
            result.checkerboard = True
            result.warnings.append(
                "Tek çakışma grubu: satranç düzeni uygulandı (sıra başına tek öğrenci)."
            )

    dominant = [g for g, size in group_sizes.items() if size > total_capacity / 2]
    for g in dominant:
        result.warnings.append(
            f"Baskın grup '{g}' ({group_sizes[g]} öğrenci) salon kapasitesinin yarısını "
            f"aşıyor; ihlalsiz çözüm garanti edilemez."
        )

    # Faz 0 (Tur 243, talep 6): salon kotaları → grup-salon kotaları →
    # şube-hizalı paketleme. Eski "global akıştan sıralı dilim" yaklaşımı
    # bir şubeyi 4-6 salona serpiyordu; yeni kademeler şubeyi olabildiğince
    # az salonda toplar. Salon-içi grup karışımı _deal_order ile korunur —
    # kelebek ayrışma fizibilitesi değişmez.
    quotas = _room_quotas(n, [_available(r) for r in rooms]) if n else [0] * len(rooms)
    group_quotas = _group_room_quotas(group_sizes, quotas)
    chunks = _pack_section_chunks(participants, group_quotas, len(rooms))

    rng = random.Random(seed)  # noqa: S311 — kripto değil; seed'li deterministik arama
    for room, chunk in zip(rooms, chunks, strict=True):
        fixed = fixed_by_room.get(room.room_id, [])
        placements = _constructive_fill(
            room,
            _deal_order(chunk),  # salon-içi harman — gruplar koltuk akışında serpilir
            strict=strict,
            warnings=result.warnings,
            fixed=fixed,
            prev_seats=prev,
        )
        _local_search(placements, room=room, rng=rng, fixed=fixed, prev_seats=prev)
        result.placements.extend(placements)
    return result


def distribute_home_classroom(
    participants: list[Participant],
    section_room_map: dict[str, RoomSeats],
) -> DistributionResult:
    """Klasik düzen: öğrenci kendi şubesinin dersliğine, okul no sırasında.

    `section_room_map`: "9/A" → RoomSeats. Eşlenmemiş şube ValueError (Türkçe;
    'klasikte derslik eşleme uyarısı' kabul kriteri).
    """
    result = DistributionResult()
    by_section: dict[str, list[Participant]] = {}
    for p in participants:
        by_section.setdefault(f"{p.class_level}/{p.class_section}", []).append(p)

    missing = sorted(set(by_section) - set(section_room_map))
    if missing:
        raise ValueError(
            "Derslik eşlemesi eksik: " + ", ".join(missing) + ". Salon tanımında "
            "'bağlı şube' alanını doldurun veya oturuma salon ekleyin."
        )

    def _number_key(p: Participant) -> tuple[int, int | str, str]:
        num = p.student_number
        return (0, int(num), "") if num.isdigit() else (1, 0, num)

    for label, students in sorted(by_section.items()):
        room = section_room_map[label]
        ordered = sorted(students, key=_number_key)
        if len(ordered) > len(room.seats):
            raise ValueError(
                f"{label} dersliği ({room.room_id}) kapasitesi yetersiz: "
                f"{len(ordered)} öğrenci / {len(room.seats)} koltuk."
            )
        for seat, student in zip(room.seats, ordered, strict=False):
            result.placements.append(
                Placement(participant=student, room_id=room.room_id, seat=seat)
            )
    return result
