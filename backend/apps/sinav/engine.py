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
  serpiyordu). Seçimlik "şubeler salonlara dağıtılır" kipinde (3) tersine
  döner: her şube salonlara payı oranında DAĞITILIR (`_spread_section_chunks`).
  Salon-içi karışım `_deal_order` harmanıyla korunur.
- HARMAN (06.11.2026, her dağıtımda açık, kapısı yok): girdi önce kanonik sıraya
  dizilir (`_input_key`, salonlar kimlik sırasına), sonra şube içi sıra ve salon payının
  grup içi sırası dağıtım numarasından türeyen karıştırmayla bozulur
  (`_blend_section_order`, `_blend_room_order`). Yerleşim böylece çözümleyicinin okul
  no sırasını taşımaz: iki sınavlı tam salonda bütün sıra deseni aynı kaldığı için
  öğrenci eskiden her numarada aynı koltuğa dönüyordu. Harman yalnız AYNI grup içinde
  kimin kimin yerine geçtiğini değiştirir: ayrışma kapalıyken ve önceki koltuk yokken grup
  deseni, ceza ve ihlal sayısı harmansız hâliyle birebirdir. Önceki koltuk varsa cezalı
  sıra öğrenciye bağlı olduğu için desen ve yakınlık skoru DEĞİŞİR; o durumda ihlal sayısı
  için güvence yoktur, yalnız ölçümde değişmedi.
- Faz 1 — kurucu: koltuklar S-ROTA sırasında gezilir; her koltuğa, akışta
  uygun ilk öğrenci (kuyruk rotasyonu) yerleştirilir. Komşuluk denetimi rota
  sırasından DEĞİL 2D geometriden yapılır (kritik tuzak: rotada uzak iki
  koltuk fiziksel komşu olabilir). Uygun aday yoksa en az ceza üreten aday
  yerleştirilir (kalan ihlal Faz 2 + doğrulayıcıya kalır).
- Faz 2 — yerel arama: `random.Random(seed)` ile beslenen, sabit iterasyon
  bütçeli salon-içi ikili takas; skor Σ 1/d² (aynı-grup çiftleri; AYNI SIRA =
  sonsuz ceza). Sonsuz ceza ihlal SAYMAZ: iki taraf da sonsuzken karşılaştırma
  ikincile düşer, yani bu yol ihlalsiz yerleşimi bozmaz ama ihlalli yerleşimde
  ihlal sayısını koruma güvencesi vermez. Aynı seed → aynı sonuç.
- SAYILI YOL (06.11.2026, `_uses_counted_path`): iki farklı ayrışma anahtarı ya da
  üçlü sıra varken sonsuz yerine ihlal SAYILIR — `(ayrışma, aynı sıra, yumuşak,
  odak)` demeti, takasta iki öğrenci birbirinin hesabından çıkarılır. Salonlar
  arası anahtar dengesi (`_balance_separation`) ve salon içi yeniden kurma
  (`_rebuild`) yalnız bu yolda vardır. Anahtarsız ikili yol eski koddan geçer. Sabit
  öğrencinin sırası kendi anahtarına kilitlidir (`separation_locks`): Faz 0 boş kalan
  koltuğu serbest tekli sıra saymaz.

Kenar durumlar:
- TEK grup + kapasite ≥ 2×N → satranç modu: sıra başına tek koltuk kullanılır
  (bitişik masa matematiksel olarak imkânsızlaşır).
- Sıra bütçesi yetmiyor (`butterfly_fit`: bir sıra her sınavdan en çok bir
  öğrenci alır) → uyarı, kaç öğrencinin yan yana kalacağı SAYIYLA (ihlalsiz
  çözüm matematiksel olarak imkânsız; en iyi skor + açık ihlal listesi).

Doğrulama BURADA DEĞİL: bağımsız `validator.validate_seating` motorun her
çıktısını sıfırdan denetler (test omurgası).
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from apps.sinav.layout import Seat, desk_position_label
from apps.sinav.participants import Participant

#: Yerel arama iterasyon bütçesi katsayısı (koltuk başına) ve tavanı.
_SWAP_BUDGET_PER_SEAT = 40
_SWAP_BUDGET_MAX = 6000

#: Kurucu fazda kuyruk rotasyonunda denenecek azami aday sayısı.
_LOOKAHEAD = 24

#: Motor sürümü: aynı dağıtım numarasının aynı yerleşimi verdiği birim. Aynı girdi +
#: aynı numara başka yerleşim verecekse bu değer ARTIRILIR; dağıtımda
#: `distribution_params["engine_version"]`a yazılır ve doğrulama raporuna basılır.
#: Alanı olmayan eski dağıtım 1. sürümle yapılmıştır (06.11.2026 öncesi).
#: 2. sürüm hiç yayımlanmadan genişledi, tek sürüm olarak şunları kapsar: sayılı yol
#: (kız/erkek ve üçlü sıra), girdinin kanonik sırası (katılımcı, grup, salon), şube içi
#: ve salon içi harman, aynı grup içinde önceki koltuk takası, sabit öğrenci sıra kilidi ve
#: çok hedefli salon anahtar dengesi. Eski sürümün numarası bu
#: sürümde başka plan verir: basılmış evrak yalnız kendi sürümüyle yeniden üretilir.
#: Seçimlik yakınlık kipi sürüm artırmaz: kapalıyken plan değişmez, kip dağıtımın
#: girdisidir ve `distribution_params["proximity_mode"]`a yazılır.
ENGINE_VERSION = 2

#: Ceza demeti: (birincil, ikincil). Birincil = sert/yumuşak yakınlık cezası
#: (bugünkü skaler); ikincil = kaçınılmaz komşu çiftlerin odağa uzaklığı.
#: Karşılaştırma Python'un doğal leksikografik demet karşılaştırmasıdır.
Penalty = tuple[float, float]

_ZERO_PENALTY: Penalty = (0.0, 0.0)

#: Sıra başına çakışma uyarısının SONU (`_desk_conflict_warnings`). R8 bu satırları
#: uyarı bölümüne basmaz: aynı bilgiyi doğrulayıcının güncel ihlal listesi verir.
#: Metin NEDEN iddia etmez: çakışma sıra bütçesinden olabileceği gibi salon kotasından
#: ya da aramanın takılmasından da olabilir ("kaçınılmaz" hepsinde doğru değildi).
#: Matematiksel açığı `distribute_butterfly`nin sıra bütçesi uyarısı ayrıca söyler.
DESK_CONFLICT_WARNING_TAIL = "bu dağıtımda önlenemedi."

#: 06.11.2026 öncesi kayıtlı dağıtımların aynı satırının sonu: R8 onları da ayıklar.
LEGACY_DESK_CONFLICT_WARNING_TAIL = "kaçınılmaz oldu (yerleştirilecek başka uygun öğrenci kalmadı)."


def _add(a: Penalty, b: Penalty) -> Penalty:
    return (a[0] + b[0], a[1] + b[1])


#: Yerleşimde tutulan tek koltuk kaydı: (koltuk, çakışma grubu, ayrışma anahtarı).
#: Ayrışma anahtarı 20.09.2026'da eklendi; boş değer JOKER'dir (kurala girmez).
Occupant = tuple[Seat, str, str]


@dataclass(frozen=True)
class RoomSeats:
    """Motor girdisi: bir salonun kullanılabilir koltukları (rota sıralı).

    `focus` salonun ODAK noktasıdır — öğretmen masası (yoksa tahta, yoksa
    (0,0)) — ve EKSEN SIRASI koltuk koordinatlarıyla aynıdır: (x=sütun,
    y=satır). `layout.reference_cell` (satır, sütun) döndürür; çeviriyi
    çağıran yapar. Varsayılan (0.0, 0.0) mobilyasız planların bugünkü
    davranışını korur.

    `label` salonun ADIDIR (servis verir): uyarı metinleri idareciye kimlikle
    ("Salon 3") değil adla konuşur. Varsayılanı boştur — etiketsiz kuran eski
    çağıranlar/testler değişmeden çalışır (`focus` ile aynı genişletme deseni).
    """

    room_id: int
    seats: tuple[Seat, ...]
    focus: tuple[float, float] = (0.0, 0.0)
    label: str = ""


def _room_text(room: RoomSeats) -> str:
    """Uyarı metnindeki salon adı; etiketsiz çağrıda kimliğe düşer."""
    return room.label or f"Salon {room.room_id}"


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


@dataclass(frozen=True)
class ButterflyFit:
    """Bir dağıtımın SIRA bütçesi — saf hesap (DB yok, kimlik yok, ad yok).

    Kelebek düzeninin sert kısıtı koltukta değil SIRADADIR: bir sıraya aynı
    çakışma grubundan iki öğrenci oturamaz (validator.py K8). Yani her sıra,
    her sınavdan EN ÇOK BİR öğrenci alır — salon yeterliliği koltukla ölçülürse
    ikili sıralarda sistematik olarak iki kat fazla görünür.

    `deficit` kaçınılmaz ihlal sayısıdır: kurala uyarak yerleştirilemeyen
    öğrenci. 0 ise ihlalsiz bir yerleşim MATEMATİKSEL OLARAK mümkündür (motorun
    onu bulacağı ayrı konudur); 0'dan büyükse hiçbir motor kurtaramaz.
    """

    students: int
    seats: int
    desks: int
    largest_group: int
    deficit: int

    @property
    def fits(self) -> bool:
        return self.deficit == 0


def desk_sizes(
    rooms: Iterable[RoomSeats], occupied: Mapping[int, Iterable[Occupant]] | None = None
) -> dict[int, int]:
    """Salonların sıra ölçüsü histogramı: {sıra başına kullanılabilir koltuk: kaç sıra}.

    `occupied` salon kimliğine göre SABİT (kural pinli) yerleşimlerdir; o koltuklar
    sıranın kullanılabilir ölçüsünden DÜŞÜLÜR — tek koltuğu pinli ikili sıra artık
    tekli sıra gibi davranır.
    """
    olculer: dict[int, int] = {}
    for room in rooms:
        dolu = {
            (seat.desk_row, seat.desk_col, seat.slot)
            for seat, _grup, _ayrisma in (occupied or {}).get(room.room_id, ())
        }
        sira_basi: dict[tuple[int, int], int] = {}
        for seat in room.seats:
            if (seat.desk_row, seat.desk_col, seat.slot) in dolu:
                continue
            key = (seat.desk_row, seat.desk_col)
            sira_basi[key] = sira_basi.get(key, 0) + 1
        for adet in sira_basi.values():
            olculer[adet] = olculer.get(adet, 0) + 1
    return olculer


def separation_locks(
    rooms: Iterable[RoomSeats], occupied: Mapping[int, Iterable[Occupant]]
) -> dict[str, dict[int, int]]:
    """Sabit öğrencinin anahtarına kilitli sıralar: {anahtar: {boş koltuk: kaç sıra}}.

    `desk_sizes` sabit koltuğu sıradan düşer, kalan koltuk tekli sıra gibi görünür. Ama o
    koltuk serbest değildir: yanındaki sabit öğrencinin anahtarına bağlıdır. Sıra ölçüsü
    `desk_sizes` ile aynı histogramdır, kilitli sıralar onun ALT kümesidir. Jokerin ya da
    iki ayrı anahtarın sabitlendiği sıra kilitlenmez (ikincisi zaten karışıktır).
    """
    kilitler: dict[str, dict[int, int]] = {}
    for room in rooms:
        dolu: set[tuple[int, int, int]] = set()
        sabit: dict[tuple[int, int], set[str]] = {}
        for seat, _grup, ayrisma in occupied.get(room.room_id, ()):
            dolu.add((seat.desk_row, seat.desk_col, seat.slot))
            sabit.setdefault((seat.desk_row, seat.desk_col), set()).add(ayrisma)
        bos: dict[tuple[int, int], int] = {}
        for seat in room.seats:
            if (seat.desk_row, seat.desk_col, seat.slot) not in dolu:
                sira = (seat.desk_row, seat.desk_col)
                bos[sira] = bos.get(sira, 0) + 1
        for sira, anahtarlar in sabit.items():
            if len(anahtarlar) == 1 and "" not in anahtarlar and bos.get(sira):
                (anahtar,) = anahtarlar
                tablo = kilitler.setdefault(anahtar, {})
                tablo[bos[sira]] = tablo.get(bos[sira], 0) + 1
    return kilitler


def occupants_by_room(placements: Iterable[Placement]) -> dict[int, list[Occupant]]:
    """Sabit yerleşimlerin salon bazında koltuk kayıtları (`desk_sizes`, `separation_locks`)."""
    by_room: dict[int, list[Occupant]] = {}
    for pl in placements:
        by_room.setdefault(pl.room_id, []).append(
            (pl.seat, pl.participant.conflict_group, pl.participant.separation_key)
        )
    return by_room


def butterfly_fit(group_sizes: Iterable[int], desk_sizes: Mapping[int, int]) -> ButterflyFit:
    """Kelebek sıra bütçesi — TAM hesap, yaklaşık değil.

    `group_sizes` çakışma grubu mevcutları (sıra önemsiz), `desk_sizes` sıra
    ölçüsü → o ölçüde kaç sıra var ({2: 135} = 135 ikili sıra). Histogram
    kullanılır çünkü otomatik yerleştirici bunu aday × slot kombinasyonu kadar
    çağırır; sıra sıra dolaşmak O(sıra) olurdu, histogram O(grup).

    Hesap (iki-taraflı akış fizibilitesinin Gale-Ryser biçimi): her sıra her
    gruptan en çok bir öğrenci aldığına göre, EN KALABALIK t grup toplamı
    Σ min(sıra koltuğu, t) sınırını aşamaz. Açık bu sınırların en büyük
    aşımıdır.

    İkili sıralarda formül şuna iner: t=1 → en kalabalık sınav ≤ sıra sayısı;
    t≥2 → toplam ≤ koltuk sayısı. Yani "hiçbir sınav, o saatte sınava girenlerin
    yarısını geçemez" kuralı bunun özel hâlidir.
    """
    gruplar = sorted((int(g) for g in group_sizes if int(g) > 0), reverse=True)
    olculer = {int(c): int(n) for c, n in desk_sizes.items() if int(c) > 0 and int(n) > 0}
    sira = sum(olculer.values())
    koltuk = sum(c * n for c, n in olculer.items())
    acik = 0
    onek = 0
    for t, grup in enumerate(gruplar, start=1):
        onek += grup
        # t koltuktan fazlasını alamayan sıra t'de doyar; t ≥ en büyük ölçü
        # olduğunda sınır koltuk sayısına eşitlenir ve artık büyümez.
        sinir = sum(min(c, t) * n for c, n in olculer.items())
        acik = max(acik, onek - sinir)
    return ButterflyFit(
        students=sum(gruplar),
        seats=koltuk,
        desks=sira,
        largest_group=gruplar[0] if gruplar else 0,
        deficit=max(acik, 0),
    )


def separation_desk_gap(
    key_counts: Iterable[int],
    sizes: Mapping[int, int],
    locked: tuple[Mapping[int, int], Mapping[int, int]] | None = None,
) -> int:
    """ "Aynı sıraya oturtma" kuralının tutması için EKSİK sıra sayısı — saf hesap.

    Bir sıra tek anahtara ayrılır: sıraların bir kümesi birinci anahtarın öğrencilerini,
    kalanı ikincininkini taşımalıdır. Yalnız ikili sırada bu Σ ceil(n/2) ≤ sıra sayısı
    demektir: bütün sıraları ikili, tam dolu ve jokersiz salonda tek sayılı mevcut bir sırayı
    karışık bırakır ve hiçbir motor bunu çözemez. Tekli sıra bu zorunluluğu kaldırabilir.
    Jokerler (anahtarı boş) `key_counts`a GİRMEZ: boş kalan koltuğa otururlar.

    `key_counts` anahtar başına yalnız SAYIDIR; hangi anahtarın hangisi olduğu bu hesaba
    girmez, sonuç eksik SIRA sayısıdır — çağıran kız/erkek sayısını söylemez. İki anahtar
    dışındaki kurulumda ya da koltuk zaten yetmiyorsa 0 döner (o açığı kapasite denetimi
    söyler). Eklenen sıranın ölçüsü salondaki en büyük sıradır.

    `locked` sabit öğrencilerin sıralarıdır (`separation_locks`), `key_counts`la AYNI
    sıradadır: verilince sayılardan biri sıfır olsa da konumunu korur. Kilitli sıra kendi
    anahtarının tarafında kalır, bölüşüm yalnız serbest sıralarda aranır.
    """
    counts = [int(c) for c in key_counts]
    if locked is None:
        counts = [c for c in counts if c > 0]
    olculer = {int(c): int(n) for c, n in sizes.items() if int(c) > 0 and int(n) > 0}
    if len(counts) != 2 or not olculer:
        return 0
    first, second = counts
    if first + second > sum(c * n for c, n in olculer.items()):
        return 0
    first_lock, second_lock = locked if locked is not None else ({}, {})
    free = {
        size: count - first_lock.get(size, 0) - second_lock.get(size, 0)
        for size, count in olculer.items()
    }
    first_base = sum(size * count for size, count in first_lock.items())
    second_base = sum(size * count for size, count in second_lock.items())
    free_seats = sum(size * count for size, count in free.items())
    reachable = 1  # bit k: birinci anahtara tam k koltukluk serbest sıra kümesi ayrılabilir
    for size, count in free.items():
        for _ in range(count):
            reachable |= reachable << size
    largest = max(olculer)
    low = max(first - first_base, 0)
    extra = 0
    while True:
        high = free_seats + second_base - second
        if high >= low and (reachable >> low) & ((1 << (high - low + 1)) - 1):
            return extra
        reachable |= reachable << largest
        free_seats += largest
        extra += 1


def _deal_order(participants: list[Participant]) -> list[Participant]:
    """Gruplar büyükten küçüğe ağırlıklı round-robin akışı (Faz 0 karışımı).

    Deterministik: grup sırası (boyut azalan, anahtar artan); grup içi sıra verilen
    sıradır (`distribute_butterfly`de harmanlanmış salon payı, okul no sırası değil).
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


def _input_key(p: Participant) -> tuple[str, int, str, int, str, int]:
    """Katılımcının kanonik sıra anahtarı: girdi sırası plana hiç sızmasın.

    Ders satırı sırası, çözümleyicinin dizimi ya da sorgunun dönüş sırası değişince
    aynı numara aynı planı vermelidir (CLAUDE.md §3). Okul no önce UZUNLUĞA göre gelir:
    "9" "10"dan önce. Sonuncu alan öğrenci kimliğidir, sıra toplamdır.
    """
    return (
        p.conflict_group,
        p.class_level,
        p.class_section,
        len(p.student_number),
        p.student_number,
        p.student_id,
    )


def _blend_section_order(participants: list[Participant], seed: int) -> list[Participant]:
    """Şube içi harman: Faz 0'ın sayımları değişmez, bölünen şubede kimin nereye düştüğü.

    Şube mevcutları, grup kotaları ve şube-salon paketi sayıma bakar; karıştırma yalnız
    şubenin hangi öğrencisinin hangi salon payına gireceğini değiştirir. Ana rng'ye
    dokunmaz: yerel aramanın sayı akışı harmandan etkilenmez.
    """
    blended = list(participants)
    random.Random(f"sube|{seed}").shuffle(blended)  # noqa: S311 — kripto değil
    return blended


def _blend_room_order(students: list[Participant], seed: int, room_id: int) -> list[Participant]:
    """Salon içi harman: salon payının grup içi sırası numaradan türeyen karıştırmayla bozulur.

    Grup mevcutları ve grup sırası aynı kaldığı için `_deal_order`ın ürettiği GRUP dizisi
    harmansız hâliyle birebirdir. Karıştırıcı salon kimliğine bağlıdır: salon sırası
    değişse de aynı salon aynı akışı alır.
    """
    rng = random.Random(f"harman|{seed}|{room_id}")  # noqa: S311 — kripto değil
    groups: dict[str, list[Participant]] = {}
    for p in students:
        groups.setdefault(p.conflict_group, []).append(p)
    blended: list[Participant] = []
    for key in sorted(groups):
        members = groups[key]
        rng.shuffle(members)
        blended.extend(members)
    return blended


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
    şube başına salon sayısı tipik girdide 1-2'ye düşer. Şube içi sıra girdinin
    sırasıdır: `distribute_butterfly` buraya harmanlanmış liste verir, yani bölünen
    şubede salona düşen öğrenci okul no sırasıyla seçilmez. Sayım deterministiktir.
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


def _spread_section_chunks(
    participants: list[Participant],
    group_quotas: dict[str, list[int]],
    room_count: int,
) -> list[list[Participant]]:
    """Şubeleri salonlara DAĞITAN Faz 0 kademe 3 (seçimlik kip, 25.10.2026).

    `_pack_section_chunks`ın tersi — kullanıcı isteği: bazı okullar şubelerin
    salonlarda olabildiğince karışmasını ister. Her grubun içinde şube mevcutları,
    grubun salon kotalarına oranla en-büyük-kalan ile bölünür (`_group_room_quotas`
    ın aynısı, anahtar şube): her şube her salona payı kadar öğrenci verir, salon ve
    grup kotaları TAM korunur (kelebek fizibilitesi değişmez). Şube içi sıra girdinin
    sırasıdır: `distribute_butterfly` buraya harmanlanmış liste verir, salon payları
    okul no dilimi değildir. Burada rng yok, sayım deterministiktir.
    """
    chunks: list[list[Participant]] = [[] for _ in range(room_count)]
    by_group: dict[str, list[Participant]] = {}
    for p in participants:
        by_group.setdefault(p.conflict_group, []).append(p)
    for key in sorted(by_group, key=lambda k: (-len(by_group[k]), k)):
        by_section: dict[str, list[Participant]] = {}
        for p in by_group[key]:
            by_section.setdefault(f"{p.class_level}/{p.class_section}", []).append(p)
        shares = _group_room_quotas(
            {skey: len(students) for skey, students in by_section.items()}, group_quotas[key]
        )
        for skey in sorted(by_section):
            students = by_section[skey]
            start = 0
            for j, count in enumerate(shares[skey]):
                chunks[j].extend(students[start : start + count])
                start += count
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


def _closest_neighbour(a_seat: Seat, b_seat: Seat) -> bool:
    """Çift, seçimlik yakınlık kipinin ağırlık verdiği en yakın komşu mu?

    Tam ön-arka ile iç çapraz (aynı sıra sütunu, bitişik sıra satırı) ve koridor karşısı
    (aynı sıra satırı, bitişik sütun, koltuklar en çok yarım sütun aralıklı: ikili ve üçlü
    sıraların yakın koltukları; bir yanı tek kişilik olan çift eşiği aşar). Koridor çaprazı
    ve koridorun uzak koltukları dışarıda kalır. Ölçü ızgara birimidir: bu ayrım metre
    bilgisine değil sınırlı kanıta dayanan bir yön sıralamasına, +10 ise varsayıma dayanır.
    """
    dr = abs(a_seat.desk_row - b_seat.desk_row)
    dc = abs(a_seat.desk_col - b_seat.desk_col)
    return (dr == 1 and dc == 0) or (dr == 0 and dc == 1 and abs(a_seat.x - b_seat.x) <= 0.5 + 1e-9)


def _pair_penalty(
    a_seat: Seat, b_seat: Seat, focus: tuple[float, float], narrow: bool = False
) -> Penalty:
    """Aynı-grup çifti İÇ cezası — LEKSİKOGRAFİK İKİLİ (birincil, ikincil).

    BİRİNCİL bugünkü skalerin BİTİ BİTİNE aynısıdır: aynı sıra = ∞ (sert
    kısıt); 1. halka ağır; diğer 1/d². Sert kısıt gevşetilmez, doğrulayıcıya
    yeni ihlal eklenmez.

    İKİNCİL yalnız KOMŞU çiftlerde (Chebyshev ≤ 1, aynı masa dâhil) devreye
    girer ve çiftin odağa (öğretmen masası) toplam uzaklığıdır. Kullanıcı
    isteği (31.08.2026): "öğrenci sayıları karmaya müsait değilse aynı sınava
    girip yanyana oturanlar ön sıralarda ve öğretmen masasına yakın olsun."

    Demet karşılaştırması doğal leksikografiktir: ikincil ancak birincil TAM
    EŞİTKEN karar verir, yani birincili sonlu bir hamleyi ikincil değiştirmez.
    Birincil iki tarafta da ∞ ise eşitlik ikincile düşer ve ihlal SAYILMADIĞI için
    bu yolda ihlal sayısı artabilir; ihlalin sayıldığı yol `_RoomState`tir.

    `narrow` seçimlik yakınlık kipidir: birinci halka ağırlığı yalnız `_closest_neighbour`
    çiftine verilir, öteki komşu çift 1/d² ile kalır. Yalnız birincil değişir; ikincil ve
    aynı sıra sonsuzu olduğu gibidir. Kapalıyken (varsayılan) sonuç bit bit aynıdır.
    Doğrulayıcının ölçüsüne dokunmaz: R8 yine bütün komşu sıra çiftlerini sayar.
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
        if narrow and not _closest_neighbour(a_seat, b_seat):
            return (base, ikincil)
        return (base + _FIRST_RING_WEIGHT, ikincil)
    return (base, 0.0)


def _separation_conflict(a_seat: Seat, b_seat: Seat, a_key: str, b_key: str) -> bool:
    """Aynı SIRADA iki farklı (boş olmayan) ayrışma anahtarı var mı? (Sert kısıt.)

    Motor ayrışmanın NE olduğunu bilmez — yalnız "iki anahtar farklı mı" diye
    sorar (20.09.2026, kız/erkek ayrışması; tasarım §"Ayrışma anahtarı"). Boş
    anahtar JOKER'dir: kurala girmez, herkesin yanına oturabilir.

    Denetim koltuk KİMLİĞİNDENDİR (desk_row, desk_col) — mesafeden değil;
    aynı-grup sert kısıtıyla aynı ölçüt (CLAUDE.md §3).
    """
    if not a_key or not b_key or a_key == b_key:
        return False
    return a_seat.desk_row == b_seat.desk_row and a_seat.desk_col == b_seat.desk_col


def _placement_penalty(
    seat: Seat,
    group: str,
    occupied: list[Occupant],
    *,
    strict: bool,
    focus: tuple[float, float],
    separation: str = "",
    narrow: bool = False,
) -> Penalty:
    """Koltuğa bu gruptan öğrenci koymanın mevcut yerleşime göre ceza demeti."""
    penalty: Penalty = _ZERO_PENALTY
    for other_seat, other_group, other_separation in occupied:
        # Ayrışma denetimi grup denetiminden ÖNCEDİR: çift FARKLI gruptan da
        # olabilir (ikili sırada yan yana oturanlar zaten farklı derstendir).
        if _separation_conflict(seat, other_seat, separation, other_separation):
            return (math.inf, 0.0)
        if other_group != group:
            continue
        p = _pair_penalty(seat, other_seat, focus, narrow)
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
    fixed: list[Occupant] | None = None,
    prev_seats: PrevSeats | None = None,
    narrow: bool = False,
) -> list[Placement]:
    """Faz 1 — kuyruk rotasyonlu kurucu yerleştirme (deterministik).

    `fixed`: salondaki SABİT (kural pinli) yerleşimler — koltukları kullanılmaz,
    komşuluk/ceza hesabına girerler ama asla taşınmazlar (T6).
    """
    queue = list(students)
    occupied: list[Occupant] = list(fixed or [])
    fixed_keys = {(s.desk_row, s.desk_col, s.slot) for s, _, _ in occupied}
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
                    seat,
                    queue[idx].conflict_group,
                    occupied,
                    strict=strict,
                    focus=room.focus,
                    separation=queue[idx].separation_key,
                    narrow=narrow,
                ),
                (_prev_penalty(queue[idx], room.room_id, seat, prev), 0.0),
            )
            if penalty[0] == 0.0:
                chosen_idx = idx
                break
            if penalty < best_penalty:
                best_idx, best_penalty = idx, penalty
        if chosen_idx is None:
            # Sert çakışma burada UYARILMAZ: yerel arama (Faz 2) çifti çoğu kez
            # ayırır. Uyarı son yerleşimden üretilir — `_desk_conflict_warnings`.
            chosen_idx = best_idx
        student = queue.pop(chosen_idx)
        occupied.append((seat, student.conflict_group, student.separation_key))
        placements.append(Placement(participant=student, room_id=room.room_id, seat=seat))
    if queue:
        warnings.append(
            f"{_room_text(room)}: {len(queue)} öğrenci koltuk bulamadı (salonun payı doldu)."
        )
    return placements


def _desk_conflict_warnings(
    room: RoomSeats,
    placements: list[Placement],
    *,
    strict: bool,
    fixed: list[Occupant] | None = None,
) -> list[str]:
    """SON yerleşimde hâlâ duran sert çakışmalar — sıra başına bir uyarı.

    Kurucu faz (Faz 1) çakışmayı koyduğu anda uyarıyordu; yerel arama (Faz 2)
    çifti sonra ayırsa da uyarı listede kalıyor ve R8'e "KURAL İHLALİ YOKTUR"
    ile yan yana bayat bir "kaçınılmaz oldu" basılıyordu (24.10.2026, 47 şubelik
    gerçek okul kurulumu: ihlalsiz 18 oturumun hepsinde 16-73 satır). Ölçüt
    kurucu fazınkiyle AYNIDIR (`_placement_penalty`'nin sonsuz cezası: aynı
    sırada aynı sınav ya da farklı ayrışma anahtarı; `strict`te 1. halka da).
    Uyarının sebebi çakışmanın türüdür: `strict`in komşu sıra çakışması "aynı sıra"
    diye söylenmez. Yalnız motorun yerleştirdiği öğrenciler denetlenir — sabit (pinli) iki
    öğrencinin çakışmasını servis kendi pin uyarısıyla söyler.
    """
    fixed_occupants = list(fixed or [])
    occupants: list[Occupant] = [
        (p.seat, p.participant.conflict_group, p.participant.separation_key) for p in placements
    ]
    warned: set[tuple[int, int]] = set()
    out: list[str] = []
    for i, (seat, group, separation) in enumerate(occupants):
        desk = (seat.desk_row, seat.desk_col)
        if desk in warned:
            continue
        others = fixed_occupants + occupants[:i] + occupants[i + 1 :]
        penalty = _placement_penalty(
            seat, group, others, strict=strict, focus=room.focus, separation=separation
        )
        if not math.isinf(penalty[0]):
            continue
        # İhlalin TÜRÜ söylenir: ayrışma mı, aynı sınav mı, katı dağıtımın komşu sırası
        # mı? Motor ayrışmanın ne olduğunu bilmediği için metin nötrdür (CLAUDE.md §3).
        ayrisma = any(
            _separation_conflict(seat, o_seat, separation, o_sep) for o_seat, _g, o_sep in others
        )
        ayni_sira = any(
            o_group == group and (o_seat.desk_row, o_seat.desk_col) == desk
            for o_seat, o_group, _s in others
        )
        if ayrisma:
            sebep = "ayrı oturması gereken iki öğrencinin aynı sıraya oturması"
        elif ayni_sira:
            sebep = "aynı sınava giren iki öğrencinin aynı sıraya oturması"
        else:
            sebep = "aynı sınava giren iki öğrencinin komşu sıralara oturması"
        out.append(
            f"{_room_text(room)}, {desk_position_label(seat.desk_row, seat.desk_col)}: "
            f"{sebep} {DESK_CONFLICT_WARNING_TAIL}"
        )
        warned.add(desk)
    return out


def _student_penalty_at(
    placements: list[Placement],
    idx: int,
    seat: Seat,
    *,
    fixed: list[Occupant] | None = None,
    room_id: int = 0,
    prev_seats: PrevSeats | None = None,
    focus: tuple[float, float] = (0.0, 0.0),
    narrow: bool = False,
) -> Penalty:
    """idx'teki öğrencinin `seat`e taşınması hâlinde toplam ceza demeti.

    Hareketli diğer öğrenciler + SABİT yerleşimler (taşınamazlar ama ceza
    üretirler) + önceki-oturum aynı-sıra terimi hesaba katılır. Ayrışma burada
    sorulmaz: bu fonksiyonu yalnız eski yol çağırır, iki farklı anahtar varsa
    sayılı yol koşar (`_uses_counted_path`).
    """
    student = placements[idx].participant
    me = student.conflict_group
    total: Penalty = (_prev_penalty(student, room_id, seat, prev_seats or {}), 0.0)
    for k, other in enumerate(placements):
        if k == idx:
            continue
        if other.participant.conflict_group != me:
            continue
        total = _add(total, _pair_penalty(seat, other.seat, focus, narrow))
        if math.isinf(total[0]):
            return total
    for fixed_seat, fixed_group, _fixed_separation in fixed or []:
        if fixed_group != me:
            continue
        total = _add(total, _pair_penalty(seat, fixed_seat, focus, narrow))
        if math.isinf(total[0]):
            return total
    return total


def _local_search(
    placements: list[Placement],
    *,
    room: RoomSeats,
    rng: random.Random,
    fixed: list[Occupant] | None = None,
    prev_seats: PrevSeats | None = None,
    narrow: bool = False,
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
    fixed_keys = {(s.desk_row, s.desk_col, s.slot) for s, _, _ in fixed}
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
            narrow=narrow,
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
            # Aynı grubun takası yakınlığı değiştirmez, yalnız önceki koltuk terimini; bu
            # yolda en çok bir ayrışma anahtarı vardır (`_uses_counted_path`), karşılaştırma
            # bilinçli olarak o terimle yapılır.
            if prev_seats and (
                _prev_penalty(a.participant, room.room_id, b.seat, prev_seats)
                + _prev_penalty(b.participant, room.room_id, a.seat, prev_seats)
                < _prev_penalty(a.participant, room.room_id, a.seat, prev_seats)
                + _prev_penalty(b.participant, room.room_id, b.seat, prev_seats)
            ):
                placements[i] = Placement(participant=a.participant, room_id=a.room_id, seat=b.seat)
                placements[j] = Placement(participant=b.participant, room_id=b.room_id, seat=a.seat)
            continue
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
    return RoomSeats(room_id=room.room_id, seats=tuple(picked), focus=room.focus, label=room.label)


def _uses_counted_path(
    participants: list[Participant], pinned: list[Placement], rooms: list[RoomSeats]
) -> bool:
    """Sayılı yol ne zaman açılır: iki farklı ayrışma anahtarı ya da üçlü (≥3) sıra."""
    keys = {p.separation_key for p in participants}
    keys |= {pl.participant.separation_key for pl in pinned}
    keys.discard("")
    if len(keys) >= 2:
        return True
    return any(size >= 3 for size in desk_sizes(rooms))


def _pair_floor(group_sizes: Iterable[int], desks: int) -> int:
    """Aynı sıra ÇİFTİ tabanı: grup sıralara en eşit yayılınca oluşan çift sayısı."""
    if desks <= 0:
        return 0
    total = 0
    for size in group_sizes:
        q, r = divmod(size, desks)
        total += r * (q + 1) * q // 2 + (desks - r) * q * (q - 1) // 2
    return total


def _side_floor(group_sizes: list[int], hist: dict[int, int]) -> tuple[int, int]:
    """Tek anahtar tarafı: (koltuğa sığmayan öğrenci, aynı sıra çift tabanı)."""
    fit = butterfly_fit(group_sizes, hist)
    overflow = max(0, fit.students - fit.seats)
    return overflow, max(fit.deficit - overflow, _pair_floor(group_sizes, fit.desks), 0)


#: Sıraların iki anahtara bölüşümü: (birinci anahtar, ikinci anahtar, birinciye düşen
#: sıra histogramı).
DeskSplit = tuple[str, str, dict[int, int]]


#: `_room_floor`un bir salonda deneyeceği en çok sıra bölüşümü. Sayı deterministiktir,
#: duvar saati kullanılmaz (aynı numara aynı plan). 60 sıralık üç ölçülü salon bu
#: bütçenin içinde kalır; üstünde kalan dev salonda bölüşümler seyreltilir.
_FLOOR_SPLIT_BUDGET = 10_000


def _split_options(sizes_of: Mapping[int, int]) -> dict[int, list[int]]:
    """Sıra ölçüsü başına denenecek "birinci anahtara düşen sıra" adetleri.

    Bölüşüm sayısı ölçü adetlerinin ÇARPIMIDIR: üç ölçülü salonda sıra sayısının küpü
    (30x30 ızgarada tek çağrı dakikalar sürüyordu). Bütçe aşılınca en kalabalık ölçü
    tam taranır, çünkü koltuk toplamını ince ayarlayan odur; ötekiler eşit aralıkla
    seyreltilir, iki uç hep denenir. Sonuç yalnız arama hedefini etkiler, doğruluğu değil.
    """
    full = {size: list(range(count + 1)) for size, count in sizes_of.items()}
    if math.prod(len(options) for options in full.values()) <= _FLOOR_SPLIT_BUDGET:
        return full
    widest = max(sizes_of, key=lambda size: (sizes_of[size], size))
    others = [size for size in sizes_of if size != widest]
    points = 2
    while (points + 1) ** len(others) * len(full[widest]) <= _FLOOR_SPLIT_BUDGET:
        points += 1
    for size in others:
        top = sizes_of[size]
        full[size] = sorted({step * top // (points - 1) for step in range(points)})
    return full


def _room_floor(
    counts: Mapping[tuple[str, str], int],
    hist: Mapping[int, int],
    locked: Mapping[str, Mapping[int, int]] | None = None,
) -> tuple[tuple[int, int], DeskSplit | None]:
    """Salonun arama hedefi (karışık sıra, aynı sıra grup çifti) ve sıra bölüşümü.

    Yalnız DURMA hedefidir, gerçek alt sınır değildir: tek sayılı anahtar kalabalığında
    grup tarafını yüksek tahmin edebilir. Bu yüzden kullanıcı metnine ("şu kadar ihlal
    olmak zorunda") ÇEVRİLMEZ.

    Sıralar iki anahtara bölüştürülür (`_split_options`: olağan salonda bütün bölüşümler
    denenir). Jokerler kısıtsız sayılır: iyimser taraf. `locked` sabit öğrencinin sıralarıdır
    (`separation_locks`): o sıralar kendi anahtarının tarafından çıkmaz, salonda karşı
    anahtardan hiç öğrenci olmasa bile bölüşüm sorulur.
    """
    locks = {key: table for key, table in (locked or {}).items() if any(table.values())}
    totals: dict[str, int] = {}
    per_key: dict[str, dict[str, int]] = {}
    for (group, key), count in counts.items():
        if count <= 0:
            continue
        totals[group] = totals.get(group, 0) + count
        if key:
            per_key.setdefault(key, {})
            per_key[key][group] = per_key[key].get(group, 0) + count
    sizes_of = {c: n for c, n in hist.items() if n > 0}
    overall = butterfly_fit(totals.values(), sizes_of)
    plain = max(overall.deficit, _pair_floor(totals.values(), overall.desks))
    keys = sorted(set(per_key) | set(locks))
    if len(keys) != 2 or not per_key:
        return (0, plain), None
    a, b = keys
    ga, gb = list(per_key.get(a, {}).values()), list(per_key.get(b, {}).values())
    sizes = sorted(sizes_of)
    options = _split_options(sizes_of)
    for size in sizes:
        low = locks.get(a, {}).get(size, 0)
        high = sizes_of[size] - locks.get(b, {}).get(size, 0)
        options[size] = sorted({min(max(count, low), high) for count in options[size]})
    best: tuple[int, int] | None = None
    best_left: dict[int, int] = {}

    def walk(idx: int, left: dict[int, int]) -> None:
        nonlocal best, best_left
        if idx == len(sizes):
            right = {c: sizes_of[c] - left.get(c, 0) for c in sizes}
            oa, pa = _side_floor(ga, left)
            ob, pb = _side_floor(gb, right)
            cand = (oa + ob, pa + pb)
            if best is None or cand < best:
                best = cand
                best_left = dict(left)
            return
        size = sizes[idx]
        for count in options[size]:
            left[size] = count
            walk(idx + 1, left)
        left.pop(size, None)

    walk(0, {})
    if best is None:  # yürüyüş en az bir yaprağa varır; tip denetimi için
        return (0, plain), None
    return (best[0], max(best[1], plain - best[0])), (a, b, best_left)


def _desk_bounds(hist: Mapping[int, int], group_count: int) -> list[int]:
    """`butterfly_fit` sınırlarının tablosu: t. eleman Σ min(sıra koltuğu, t+1)."""
    return [sum(min(c, t) * n for c, n in hist.items()) for t in range(1, group_count + 1)]


def _bound_deficit(vector: list[int], bounds: list[int]) -> int:
    """`butterfly_fit(...).deficit`in sıcak yol kardeşi: nesne ve sınır yeniden kurulmaz."""
    worst = prefix = 0
    for size, bound in zip(sorted(vector, reverse=True), bounds, strict=True):
        prefix += size
        if prefix - bound > worst:
            worst = prefix - bound
    return worst


def _fit_quotas_to_desks(
    group_quotas: dict[str, list[int]],
    capacities: list[int],
    hists: list[dict[int, int]],
) -> dict[str, list[int]]:
    """Grup kotasına sıra üst sınırı — YALNIZ salon içi sıra açığı varken değiştirir.

    Bir sıra her sınavdan en çok bir öğrenci aldığı için salonun açığı sıra bütçesiyle
    sorulur. Her adımda açığı en çok düşüren hamle yapılır: önce salon kotasını koruyan
    takas, olmazsa boş koltuğu olan salona taşıma (20/1 vakasında salon kotası değişmek
    ZORUNDADIR). Hamle sayısı toplam açıkla sınırlıdır: her hamle açığı en az 1 düşürür.

    Hesap artımlıdır: bir hamle yalnız iki salonun vektörünü değiştirir, salon başına
    "şu grup çıkar, şu grup girer" sonucu saklanır ve yalnız değişen salonda silinir.
    Açığı olmayan hedef salon kazanca artı yazamaz; o yüzden kaynak salonda açığı
    düşürmeyen hamle orada hiç denenmez. Rng ve saat yok: aynı girdi aynı sonuç.
    """
    keys = list(group_quotas)
    count = len(keys)
    rooms = range(len(capacities))
    table = [[group_quotas[k][j] for k in keys] for j in rooms]
    bounds = [_desk_bounds(hist, count) for hist in hists]
    deficits = [_bound_deficit(table[j], bounds[j]) for j in rooms]
    if not any(deficits):
        return group_quotas
    filled = [sum(table[j]) for j in rooms]
    memo: list[dict[tuple[int, int], int]] = [{} for _ in rooms]

    def after(j: int, out: int, into: int) -> int:
        """j salonundan `out` grubu bir öğrenci çıkar, `into` girerse kalan açık (-1 = yok)."""
        cached = memo[j].get((out, into))
        if cached is None:
            vector = list(table[j])
            if out >= 0:
                vector[out] -= 1
            if into >= 0:
                vector[into] += 1
            cached = memo[j][(out, into)] = _bound_deficit(vector, bounds[j])
        return cached

    while any(deficits):
        best: tuple[int, int, int, int, str, str] | None = None
        for r in rooms:
            if not deficits[r]:
                continue
            sources = [g for g in range(count) if table[r][g] > 0]
            swaps = [
                (g, h, deficits[r] - after(r, g, h))
                for g in sources
                for h in range(count)
                if h != g
            ]
            moves = [(g, deficits[r] - after(r, g, -1)) for g in sources]
            helpful_swaps = [item for item in swaps if item[2] > 0]
            helpful_moves = [item for item in moves if item[1] > 0]
            for r2 in rooms:
                if r2 == r:
                    continue
                other = deficits[r2]
                for g, h, here in swaps if other else helpful_swaps:
                    if table[r2][h] == 0:
                        continue
                    gain = here + other - after(r2, h, g)
                    if gain > 0:
                        cand = (-gain, 0, r, r2, keys[g], keys[h])
                        if best is None or cand < best:
                            best = cand
                if filled[r2] < capacities[r2]:
                    for g, here in moves if other else helpful_moves:
                        gain = here + other - after(r2, -1, g)
                        if gain > 0:
                            cand = (-gain, 1, r, r2, keys[g], "")
                            if best is None or cand < best:
                                best = cand
        if best is None:
            break
        _gain, kind, r, r2, g_key, h_key = best
        g = keys.index(g_key)
        table[r][g] -= 1
        table[r2][g] += 1
        if kind == 0:
            h = keys.index(h_key)
            table[r2][h] -= 1
            table[r][h] += 1
        else:
            filled[r] -= 1
            filled[r2] += 1
        for j in (r, r2):
            memo[j].clear()
            deficits[j] = _bound_deficit(table[j], bounds[j])
    return {k: [table[j][i] for j in rooms] for i, k in enumerate(keys)}


#: Anahtar hedefinde bir salonun sayısının ilk denenen kayma sınırı. İkili ve üçlü sıranın
#: birlikte çözüldüğü adım 6'dır (2 ile 3'ün en küçük ortak katı); çözüm çıkmazsa katlanır.
_KEY_TARGET_REACH = 6

#: `_key_targets`in döndürdüğü en çok hedef. Eşit kaydırmalı hedeflerden biri grup kotasını
#: değiştirmeyi gerektirirken öteki aynı grup takasıyla varılabilir: tek hedef seçilirse bu
#: ayrım hiç sorulmaz (06.11.2026 ölçümü). Sayı deterministiktir, süre sınırı değildir.
_KEY_TARGET_LIMIT = 8

#: Salonun iki anahtara göre kilitli sıraları: (birinci anahtar, ikinci anahtar).
KeyLocks = tuple[Mapping[int, int], Mapping[int, int]]


def _key_targets(
    current: list[int],
    totals: list[int],
    hists: list[dict[int, int]],
    locks: list[KeyLocks] | None = None,
) -> list[list[int]]:
    """Karışık sıra bırakmayan salon sayıları, az kaydırılandan çoğa; yoksa boş liste.

    `current` birinci anahtarın salon sayıları, `totals` salonun iki anahtar toplamı. Toplam
    değişmeden her salonu `separation_desk_gap` = 0 olan bir sayıya taşıyan en çok
    `_KEY_TARGET_LIMIT` hedef döner. Rng yok, aynı girdi aynı sonuç.

    Önce bütün salonlar tek salon gibi sorulur: salon çözümlerinin toplamı bütünün çözümüdür,
    yani bütün sığmıyorsa hiçbir hedef yoktur. Tek sayılı tam salonda kayma sınırını boşuna
    katlamak 1200 öğrencide dağıtımı 0,3 sn'den 2,2 sn'ye çıkarıyordu.
    """
    pairs = locks if locks is not None else [({}, {}) for _ in current]
    merged: dict[int, int] = {}
    merged_locks: tuple[dict[int, int], dict[int, int]] = ({}, {})
    for hist, lock in zip(hists, pairs, strict=True):
        for size, count in hist.items():
            merged[size] = merged.get(size, 0) + count
        for table, side in zip(merged_locks, lock, strict=True):
            for size, count in side.items():
                table[size] = table.get(size, 0) + count
    first = sum(current)
    if separation_desk_gap((first, sum(totals) - first), merged, merged_locks):
        return []
    reach = _KEY_TARGET_REACH
    while True:
        best: dict[int, list[tuple[int, tuple[int, ...]]]] = {0: [(0, ())]}
        for count, total, hist, lock in zip(current, totals, hists, pairs, strict=True):
            options = [
                shift
                for shift in range(-reach, reach + 1)
                if 0 <= count + shift <= total
                and separation_desk_gap((count + shift, total - count - shift), hist, lock) == 0
            ]
            step: dict[int, list[tuple[int, tuple[int, ...]]]] = {}
            for offset, paths in best.items():
                for moved, path in paths:
                    for shift in options:
                        step.setdefault(offset + shift, []).append(
                            (moved + abs(shift), (*path, shift))
                        )
            best = {o: sorted(paths)[:_KEY_TARGET_LIMIT] for o, paths in step.items()}
        finals = best.get(0, [])
        if finals or reach >= max(totals, default=0):
            return [
                [count + shift for count, shift in zip(current, path, strict=True)]
                for _moved, path in finals
            ]
        reach *= 2


#: `_balance_separation`ın geri dönüş noktası: (salon payları, sayımlar, hedefler).
Snapshot = tuple[list[list[Participant]], list[dict[tuple[str, str], int]], list[tuple[int, int]]]


def _balance_separation(
    chunks: list[list[Participant]],
    hists: list[dict[int, int]],
    locks: list[dict[str, dict[int, int]]] | None = None,
) -> list[list[Participant]]:
    """Faz 0 anahtar dengesi: aynı gruptan, farklı anahtarlı öğrenci salonlar arası takas.

    Salonların toplam (karışık sıra, aynı sıra çifti) hedefi leksikografik düşüyorsa
    takas yapılır; öğrenci, şube-salon çifti sayısını en az artıracak şubeden seçilir.

    Tek takas iki salonun sayısını birer oynatır; bu, çözümü birkaç öğrencilik kaydırma
    isteyen kurulumda yetmez. İkili ve üçlü salon birlikteyken ikili salon çift, üçlü salon
    3'ün katı sayı ister ve tek sayılı ikili salonu düzeltmek üçlü salondan ÜÇ öğrenci
    getirmektir: aradaki adımlar cezayı artırdığı için takas oraya varamaz (06.11.2026
    ölçümü: 30 numaranın 18'i tam bu durumda kaldı). Takas durunca salonlar
    `_key_targets`in hedeflerine sırayla yürütülür.

    Yürüyüş önce aynı gruptan takas arar; kalmadıysa iki ayrı grubun öğrencisini takas eder
    ve grup kotası değişir. Şube içi tek cinsiyette bu zorunludur: sınavın bir salondaki
    öğrencilerinin hepsi aynı cinsiyetse aynı grup takası o salonun sayısını oynatamaz.
    Kız/erkek ayrışması kabulle geçilemez, aynı sınavın yan yana gelmesi geçilir: öncelik
    sırası budur. En az karışık sıra, sonra en az aynı sıra çifti, sonra en az grup değişimi
    veren hedef seçilir; karışık sıra düşmezse her şey geri alınır. Rng yok, deterministik.
    """
    room_count = len(chunks)
    room_locks = locks if locks is not None else [{} for _ in chunks]
    counts: list[dict[tuple[str, str], int]] = []
    for chunk in chunks:
        table: dict[tuple[str, str], int] = {}
        for p in chunk:
            key = (p.conflict_group, p.separation_key)
            table[key] = table.get(key, 0) + 1
        counts.append(table)
    memo: dict[tuple[object, ...], tuple[int, int]] = {}

    def floor(j: int, table: dict[tuple[str, str], int]) -> tuple[int, int]:
        sig = (j, tuple(sorted((k, v) for k, v in table.items() if v > 0)))
        if sig not in memo:
            memo[sig] = _room_floor(table, hists[j], room_locks[j])[0]
        return memo[sig]

    costs = [floor(j, counts[j]) for j in range(room_count)]
    all_keys = sorted({k for table in counts for _g, k in table})
    real_keys = [k for k in all_keys if k]  # boş anahtar jokerdir: takasa girer, hedefe girmez

    def exchanged(a: int, b: int, out: tuple[str, str], back: tuple[str, str]) -> tuple[int, int]:
        """`out` a'dan b'ye, `back` b'den a'ya geçerse iki salonun toplam hedefi."""
        ta, tb = dict(counts[a]), dict(counts[b])
        ta[out] -= 1
        ta[back] = ta.get(back, 0) + 1
        tb[back] -= 1
        tb[out] = tb.get(out, 0) + 1
        fa, fb = floor(a, ta), floor(b, tb)
        return (fa[0] + fb[0], fa[1] + fb[1])

    def commit(a: int, b: int, out: tuple[str, str], back: tuple[str, str]) -> None:
        _swap_students(chunks, a, b, out, back)
        counts[a][out] -= 1
        counts[a][back] = counts[a].get(back, 0) + 1
        counts[b][back] -= 1
        counts[b][out] = counts[b].get(out, 0) + 1
        costs[a], costs[b] = floor(a, counts[a]), floor(b, counts[b])

    def descend() -> None:
        while True:
            best: tuple[int, int, int, int, str, str, str] | None = None
            for a in range(room_count):
                if costs[a] == (0, 0):
                    continue
                for b in range(room_count):
                    if a == b:
                        continue
                    base = (costs[a][0] + costs[b][0], costs[a][1] + costs[b][1])
                    for g, k in sorted(counts[a]):
                        if counts[a][(g, k)] <= 0:
                            continue
                        for k2 in all_keys:
                            if k2 == k or counts[b].get((g, k2), 0) <= 0:
                                continue
                            after = exchanged(a, b, (g, k), (g, k2))
                            if after < base:
                                cand = (after[0] - base[0], after[1] - base[1], a, b, g, k, k2)
                                if best is None or cand < best:
                                    best = cand
            if best is None:
                return
            _gain, _pairs, a, b, g, k, k2 = best
            commit(a, b, (g, k), (g, k2))

    def walk(first: str, second: str, current: list[int], targets: list[int]) -> int:
        """Salonları hedefe yürütür; grup kotası değiştiren takas sayısını döner."""
        crossed = 0
        while True:
            step: tuple[bool, tuple[int, int], int, int, str, str] | None = None
            for a in range(room_count):
                if current[a] <= targets[a]:
                    continue
                for b in range(room_count):
                    if current[b] >= targets[b]:
                        continue
                    for g, k in sorted(counts[a]):
                        if k != first or counts[a][(g, k)] <= 0:
                            continue
                        for h, k2 in sorted(counts[b]):
                            if k2 != second or counts[b][(h, k2)] <= 0:
                                continue
                            after = exchanged(a, b, (g, first), (h, second))
                            cand = (g != h, after, a, b, g, h)
                            if step is None or cand < step:
                                step = cand
            if step is None:
                return crossed
            cross, _after, a, b, g, h = step
            commit(a, b, (g, first), (h, second))
            crossed += cross
            current[a] -= 1
            current[b] += 1

    def restore(state: Snapshot) -> None:
        chunks[:] = [list(chunk) for chunk in state[0]]
        counts[:] = [dict(table) for table in state[1]]
        costs[:] = state[2]

    def retarget() -> None:
        first, second = real_keys
        current = [sum(v for (_g, k), v in t.items() if k == first) for t in counts]
        totals = [sum(v for (_g, k), v in t.items() if k) for t in counts]
        pairs: list[KeyLocks] = [(lock.get(first, {}), lock.get(second, {})) for lock in room_locks]
        mixed = sum(cost[0] for cost in costs)
        start: Snapshot = ([list(c) for c in chunks], [dict(t) for t in counts], list(costs))
        chosen = start
        best: tuple[int, int, int] | None = None
        for targets in _key_targets(current, totals, hists, pairs):
            restore(start)
            crossed = walk(first, second, list(current), targets)
            score = (sum(c[0] for c in costs), sum(c[1] for c in costs), crossed)
            if score[0] < mixed and (best is None or score < best):
                best = score
                chosen = ([list(c) for c in chunks], [dict(t) for t in counts], list(costs))
        restore(chosen)

    descend()
    if len(real_keys) == 2 and any(cost[0] for cost in costs):
        retarget()
        descend()
    return chunks


def _swap_students(
    chunks: list[list[Participant]],
    a: int,
    b: int,
    out: tuple[str, str],
    back: tuple[str, str],
) -> None:
    """a salonundaki `out` (grup, anahtar) öğrenciyle b'deki `back` öğrenciyi yer değiştir."""

    def section(p: Participant) -> tuple[int, str]:
        return (p.class_level, p.class_section)

    in_a: dict[tuple[int, str], int] = {}
    in_b: dict[tuple[int, str], int] = {}
    for p in chunks[a]:
        in_a[section(p)] = in_a.get(section(p), 0) + 1
    for p in chunks[b]:
        in_b[section(p)] = in_b.get(section(p), 0) + 1
    xs = [i for i, p in enumerate(chunks[a]) if (p.conflict_group, p.separation_key) == out]
    ys = [i for i, p in enumerate(chunks[b]) if (p.conflict_group, p.separation_key) == back]
    best: tuple[int, int, int] | None = None
    for i in xs:
        sx = section(chunks[a][i])
        for j in ys:
            sy = section(chunks[b][j])
            spread = (
                (in_b.get(sx, 0) == 0) + (in_a.get(sy, 0) == 0) - (in_a[sx] == 1) - (in_b[sy] == 1)
            )
            cand = (spread, -i, -j)
            if best is None or cand < best:
                best = cand
    if best is None:  # çağıran iki tarafta da öğrenci olduğunu sayımla bilir
        return
    i, j = -best[1], -best[2]
    chunks[a][i], chunks[b][j] = chunks[b][j], chunks[a][i]


def _counted_fill(
    room: RoomSeats,
    students: list[Participant],
    *,
    strict: bool,
    warnings: list[str],
    fixed: list[Occupant] | None = None,
    prev_seats: PrevSeats | None = None,
    narrow: bool = False,
) -> list[Placement]:
    """Faz 1'in sayılı kardeşi: sonsuz yerine (ayrışma, aynı sıra, yumuşak) demeti."""
    queue = list(students)
    occupied: list[Occupant] = list(fixed or [])
    fixed_keys = {(s.desk_row, s.desk_col, s.slot) for s, _, _ in occupied}
    prev = prev_seats or {}
    placements: list[Placement] = []
    for seat in room.seats:
        if (seat.desk_row, seat.desk_col, seat.slot) in fixed_keys:
            continue
        if not queue:
            break
        chosen = 0
        best: tuple[int, int, float] | None = None
        for idx in range(min(len(queue), _LOOKAHEAD)):
            student = queue[idx]
            group, key = student.conflict_group, student.separation_key
            sep = grp = 0
            soft = _prev_penalty(student, room.room_id, seat, prev)
            for o_seat, o_group, o_key in occupied:
                if _separation_conflict(seat, o_seat, key, o_key):
                    sep += 1
                if o_group != group:
                    continue
                pen = _pair_penalty(seat, o_seat, room.focus, narrow)[0]
                if math.isinf(pen):
                    grp += 1
                elif (
                    strict
                    and max(
                        abs(seat.desk_row - o_seat.desk_row), abs(seat.desk_col - o_seat.desk_col)
                    )
                    <= 1
                ):
                    grp += 1
                else:
                    soft += pen
            cand = (sep, grp, soft)
            if best is None or cand < best:
                best, chosen = cand, idx
            if cand == (0, 0, 0.0):
                break
        student = queue.pop(chosen)
        occupied.append((seat, student.conflict_group, student.separation_key))
        placements.append(Placement(participant=student, room_id=room.room_id, seat=seat))
    if queue:
        warnings.append(
            f"{_room_text(room)}: {len(queue)} öğrenci koltuk bulamadı (salonun payı doldu)."
        )
    return placements


#: Sayılı ceza demeti: (karışık sıra, aynı sıra aynı sınav, yumuşak, odak). Python'un
#: doğal leksikografik karşılaştırması: odak YALNIZ eşitlik bozar (CLAUDE.md §3 ceza
#: demeti sözleşmesi), yakınlığı artıran bir hamleyi hiçbir koşulda kabul ettiremez.
CountedCost = tuple[int, int, float, int]


class _RoomState:
    """Salonun sayılı arama durumu: koltuk matrisleri + grup/sıra üyelik listeleri.

    Hareketli öğrenciler 0..n-1, SABİT yerleşimler n.. — onlar da üyelik listelerinde
    durur (ceza üretirler), hamle uzayında yoktur. Takas/taşıma cezası TAM farktır:
    iki öğrenci birbirinin hesabından çıkarılır (`skip`) çünkü aralarındaki çiftin
    terimi takasta değişmez.
    """

    def __init__(
        self,
        room: RoomSeats,
        placements: list[Placement],
        fixed: list[Occupant],
        prev_seats: PrevSeats | None,
        narrow: bool = False,
    ) -> None:
        seats = list(room.seats)
        index = {(s.desk_row, s.desk_col, s.slot): i for i, s in enumerate(seats)}
        # Doğrudan çağıranın pini salonun koltuk listesi dışında kalabilir: ceza üretmeye
        # devam eder, koltuğu dolu olduğu için hamle uzayına girmez.
        for seat, _group, _key in fixed:
            spot = (seat.desk_row, seat.desk_col, seat.slot)
            if spot not in index:
                index[spot] = len(seats)
                seats.append(seat)
        self.seats = seats
        desk_ids: dict[tuple[int, int], int] = {}
        self.desk = [desk_ids.setdefault((s.desk_row, s.desk_col), len(desk_ids)) for s in seats]
        self.desk_seats: list[list[int]] = [[] for _ in desk_ids]
        for i, d in enumerate(self.desk):
            self.desk_seats[d].append(i)
        size = len(seats)
        focus = room.focus
        self.pen = [[0.0] * size for _ in range(size)]
        for a in range(size):
            row = self.pen[a]
            for b in range(a + 1, size):
                if self.desk[a] != self.desk[b]:
                    value = _pair_penalty(seats[a], seats[b], focus, narrow)[0]
                    row[b] = value
                    self.pen[b][a] = value
        #: Tamsayı: katman toplamı takas öncesi/sonrası yuvarlama farkı üretmesin.
        self.focus_cost = [round(math.dist((s.x, s.y), focus) * 1000) for s in seats]
        self.n = len(placements)
        groups: dict[str, int] = {}
        self.grp: list[int] = []
        self.key: list[str] = []
        self.pos: list[int] = []
        self.prev_desk: list[int] = []
        prev = prev_seats or {}
        for p in placements:
            self.grp.append(groups.setdefault(p.participant.conflict_group, len(groups)))
            self.key.append(p.participant.separation_key)
            self.pos.append(index[(p.seat.desk_row, p.seat.desk_col, p.seat.slot)])
            last = prev.get(p.participant.student_id)
            self.prev_desk.append(
                desk_ids.get((last[1], last[2]), -1)
                if last is not None and last[0] == room.room_id
                else -1
            )
        for seat, group, key in fixed:
            self.grp.append(groups.setdefault(group, len(groups)))
            self.key.append(key)
            self.pos.append(index[(seat.desk_row, seat.desk_col, seat.slot)])
            self.prev_desk.append(-1)
        self.members: list[list[int]] = [[] for _ in groups]
        for i, g in enumerate(self.grp):
            self.members[g].append(i)
        self.who = [-1] * size
        for i, s in enumerate(self.pos):
            self.who[s] = i
        self.free = [s for s in range(size) if self.who[s] < 0]

    def cost(self, i: int, s: int, skip: int = -1) -> CountedCost:
        """i öğrencisi s koltuğundayken ürettiği (ayrışma, grup, yumuşak, odak)."""
        desk = self.desk
        d = desk[s]
        pos = self.pos
        row = self.pen[s]
        focus_cost = self.focus_cost
        sep = grp = foc = 0
        soft = _PREV_SEAT_WEIGHT if d == self.prev_desk[i] else 0.0
        for m in self.members[self.grp[i]]:
            if m == i or m == skip:
                continue
            t = pos[m]
            if desk[t] == d:
                grp += 1
                foc += focus_cost[s] + focus_cost[t]
            else:
                soft += row[t]
        key = self.key[i]
        if key:
            who = self.who
            for t in self.desk_seats[d]:
                m = who[t]
                if t == s or m < 0 or m == i or m == skip:
                    continue
                other = self.key[m]
                if other and other != key:
                    sep += 1
        return sep, grp, soft, foc

    def swap_vectors(self, i: int, j: int) -> tuple[CountedCost, CountedCost]:
        """i ile j yer değiştirirse (önce, sonra) demeti — ikisinin ortak terimi dışarıda."""
        si, sj = self.pos[i], self.pos[j]
        a, b = self.cost(i, si, j), self.cost(j, sj, i)
        c, d = self.cost(i, sj, j), self.cost(j, si, i)
        before = (a[0] + b[0], a[1] + b[1], a[2] + b[2], a[3] + b[3])
        after = (c[0] + d[0], c[1] + d[1], c[2] + d[2], c[3] + d[3])
        return before, after

    def prev_swap_helps(self, i: int, j: int) -> bool:
        """Aynı grup ve anahtardaki i ile j takası önceki sıraya dönüşü azaltıyor mu?

        Bu takasta başka hiçbir terim değişmez; tam demet yerine yalnız bu terim
        karşılaştırılır, böylece kayan nokta gürültüsü takas kabul ettiremez.
        """
        desk_i, desk_j = self.desk[self.pos[i]], self.desk[self.pos[j]]
        prev_i, prev_j = self.prev_desk[i], self.prev_desk[j]
        return (prev_i == desk_j) + (prev_j == desk_i) < (prev_i == desk_i) + (prev_j == desk_j)

    def apply_swap(self, i: int, j: int) -> None:
        si, sj = self.pos[i], self.pos[j]
        self.pos[i], self.pos[j] = sj, si
        self.who[si], self.who[sj] = j, i

    def apply_move(self, i: int, target: int) -> None:
        s = self.pos[i]
        self.pos[i] = target
        self.who[s], self.who[target] = -1, i
        self.free[self.free.index(target)] = s

    def violations(self) -> tuple[int, int]:
        """Salondaki (karışık sıra çifti, aynı sıra aynı sınav çifti) sayısı."""
        sep = grp = 0
        for seats in self.desk_seats:
            people = [self.who[t] for t in seats if self.who[t] >= 0]
            for x in range(len(people)):
                for y in range(x + 1, len(people)):
                    a, b = people[x], people[y]
                    if self.grp[a] == self.grp[b]:
                        grp += 1
                    ka, kb = self.key[a], self.key[b]
                    if ka and kb and ka != kb:
                        sep += 1
        return sep, grp


def _counted_search(state: _RoomState, rng: random.Random, budget: int) -> None:
    """Faz 2'nin sayılı kardeşi: kabul demeti, gerçek takas, erken dönüş yok."""
    n = state.n
    free = state.free
    grp, key = state.grp, state.key
    has_prev = any(desk >= 0 for desk in state.prev_desk)
    for _ in range(budget):
        if free and (n < 2 or rng.random() < 0.5):
            i = rng.randrange(n)
            f = rng.randrange(len(free))
            current, candidate = state.pos[i], free[f]
            if state.cost(i, candidate) < state.cost(i, current):
                state.apply_move(i, candidate)
            continue
        if n < 2:
            continue
        i, j = rng.randrange(n), rng.randrange(n)
        if i == j:
            continue
        if grp[i] == grp[j] and key[i] == key[j]:
            if has_prev and state.prev_swap_helps(i, j):
                state.apply_swap(i, j)
            continue
        before, after = state.swap_vectors(i, j)
        if after < before:
            state.apply_swap(i, j)


def _rebuild(state: _RoomState, split: DeskSplit | None) -> None:
    """Sırayı anahtar tarafına ayırıp öğrencileri kat kat dağıtan deterministik kurulum.

    Tek hamleyle ulaşılamayan durum içindir: bir sırayı bir anahtardan ötekine çevirmek
    aynı anda iki öğrenciyi taşır, ara adım ayrışma ihlali olduğu için yerel arama oradan
    geçemez. Grup büyükten küçüğe, sıraların önce ilk koltuklarına sonra ikinci
    koltuklarına dizilir: sıra sayısını aşmayan grup aynı sıraya iki öğrenci düşürmez.

    SABİT yerleşimler yerinde kalır: koltukları dağıtıma girmez, sırayı kendi anahtarının
    tarafına çekerler (sabit öğrencinin sırası karşı tarafa düşerse ihlal baştan yazılır).
    """
    n = state.n
    open_seats = [[t for t in seats if state.who[t] < n] for seats in state.desk_seats]
    sizes = {d: len(seats) for d, seats in enumerate(open_seats) if seats}
    sides: list[list[int]]
    side_keys: list[str | None]
    if split is None:
        sides = [sorted(sizes)]
        side_keys = [None]
    else:
        key_a, key_b, left = split

        def lean(d: int) -> int:
            score = 0
            for t in state.desk_seats[d]:
                m = state.who[t]
                if m >= 0:
                    # Sabit öğrencinin sırası öğrencilerin çoğunluğuna bakılmadan onun yanında.
                    weight = 1 if m < n else n + 1
                    score += weight * ((state.key[m] == key_a) - (state.key[m] == key_b))
            return score

        side_a: list[int] = []
        side_b: list[int] = []
        for size in sorted(set(sizes.values())):
            desks = sorted((d for d in sizes if sizes[d] == size), key=lambda d: (-lean(d), d))
            take = left.get(size, 0)
            side_a += desks[:take]
            side_b += desks[take:]
        sides = [side_a, side_b]
        side_keys = [key_a, key_b]
    who = [m if m >= n else -1 for m in state.who]
    pos = [-1] * n
    rest: list[int] = []
    assigned: set[int] = set()
    for desks, key in zip(sides, side_keys, strict=True):
        students = [i for i in range(n) if key is None or state.key[i] == key]
        assigned.update(students)
        group_count: dict[int, int] = {}
        for i in students:
            group_count[state.grp[i]] = group_count.get(state.grp[i], 0) + 1
        students.sort(key=lambda i: (-group_count[state.grp[i]], state.grp[i], i))
        ordered = sorted(desks, key=lambda d: (-sizes[d], d))
        slots = [
            open_seats[d][level]
            for level in range(max((sizes[d] for d in ordered), default=0))
            for d in ordered
            if level < sizes[d]
        ]
        for i, s in zip(students, slots, strict=False):
            pos[i], who[s] = s, i
        rest.extend(students[len(slots) :])
    rest.extend(i for i in range(n) if i not in assigned)  # jokerler
    for i in rest:
        best_seat = -1
        best_cost: tuple[int, int, int] | None = None
        for s, occupant in enumerate(who):
            if occupant >= 0:
                continue
            sep = grp = 0
            for t in state.desk_seats[state.desk[s]]:
                m = who[t]
                if m < 0:
                    continue
                grp += state.grp[m] == state.grp[i]
                sep += bool(state.key[m] and state.key[i] and state.key[m] != state.key[i])
            cost = (sep, grp, s)
            if best_cost is None or cost < best_cost:
                best_seat, best_cost = s, cost
        pos[i], who[best_seat] = best_seat, i
    state.pos[:n] = pos
    state.who[:] = who
    state.free[:] = [s for s, m in enumerate(who) if m < 0]


def _counted_room(
    room: RoomSeats,
    placements: list[Placement],
    *,
    rng: random.Random,
    seed: int,
    fixed: list[Occupant],
    prev_seats: PrevSeats | None,
    hist: dict[int, int],
    locked: dict[str, dict[int, int]],
    narrow: bool = False,
) -> None:
    """Sayılı yerel arama + gerekirse yeniden kurma; `placements`ı yerinde günceller."""
    n = len(placements)
    if n == 0:
        return
    state = _RoomState(room, placements, fixed, prev_seats, narrow)
    budget = min(_SWAP_BUDGET_MAX, _SWAP_BUDGET_PER_SEAT * max(n, len(room.seats)))
    _counted_search(state, rng, budget)
    current = state.violations()
    if current != (0, 0):
        counts: dict[tuple[str, str], int] = {}
        for p in placements:
            key = (p.participant.conflict_group, p.participant.separation_key)
            counts[key] = counts.get(key, 0) + 1
        target, split = _room_floor(counts, hist, locked)
        if current > target:
            saved_pos, saved_who, saved_free = list(state.pos), list(state.who), list(state.free)
            _rebuild(state, split)
            # Ayrı alt-rng: ana rng akışı (sonraki salonlar) yeniden kurmadan etkilenmez.
            sub_rng = random.Random(seed * 1_000_003 + room.room_id)  # noqa: S311 — kripto değil
            _counted_search(state, sub_rng, budget)
            if state.violations() >= current:
                state.pos[:], state.who[:], state.free[:] = saved_pos, saved_who, saved_free
    for i, p in enumerate(placements):
        placements[i] = Placement(
            participant=p.participant, room_id=p.room_id, seat=state.seats[state.pos[i]]
        )


def distribute_butterfly(
    participants: list[Participant],
    rooms: list[RoomSeats],
    *,
    seed: int,
    strict: bool = False,
    preplaced: list[Placement] | None = None,
    previous_seats: PrevSeats | None = None,
    group_labels: Mapping[str, str] | None = None,
    spread_sections: bool = False,
    narrow_ring: bool = False,
) -> DistributionResult:
    """Kelebek dağıtımı — iki fazlı, seed'li deterministik.

    `spread_sections` (25.10.2026, seçimlik kip): Faz 0'da şubeler salonlara
    bütün paketlenmek yerine payları oranında DAĞITILIR (`_spread_section_chunks`).
    Varsayılan kapalıdır. Aynı motor sürümünde plan bit bit kilitlidir: anahtarsız ikili
    yol `test_altin_kayit`, sayılı yol `test_sayili_yol` ile.

    `narrow_ring` (06.11.2026, seçimlik kip): birinci halka ağırlığı yalnız en yakın
    komşulara verilir (`_closest_neighbour`), iki yolda da aynı ölçüyle. Varsayılan
    kapalıdır. Katı dağıtımda etkisizdir: orada bütün komşu sıralar yasaktır.

    Girdi sırası plana girmez: `participants`, `preplaced` ve `rooms` önce kanonik sıraya
    dizilir (`_input_key`, salon kimliği). Sonuç listesi de salon kimliği sırasındadır.

    `preplaced` (T6): kural pinli yerleşimler — koltukları kullanım dışıdır,
    komşuluk cezasına girerler, motor onları ASLA taşımaz; sonuç listesine
    DAHİL EDİLMEZLER (çağıran birleştirir). `previous_seats` (T6): öğrencinin
    önceki oturumdaki sırası — aynı sıraya dönüş yumuşak cezayla caydırılır.
    Kapasite yetersizse ValueError (Türkçe) fırlatır; çağıran (servis) bunu
    ValidationError'a çevirir.

    `group_labels` çakışma grubu anahtarını idareci diline çevirir ("12:10" →
    "Coğrafya — 10. Sınıf"); yalnız UYARI METNİNE girer, dağıtıma hiç girmez ve
    varsayılanlıdır — etiketsiz çağıran ham anahtara düşer (`focus`/`label` ile
    aynı genişletme deseni, CLAUDE.md §3).
    """
    result = DistributionResult(seed=seed)
    narrow = narrow_ring and not strict
    participants = sorted(participants, key=_input_key)
    rooms = sorted(rooms, key=lambda room: room.room_id)
    pinned = sorted(preplaced or [], key=lambda pl: _input_key(pl.participant))
    prev = previous_seats or {}
    if not participants and not pinned:
        result.warnings.append("Dağıtılacak katılımcı yok.")
        return result

    group_sizes: dict[str, int] = {}
    for p in participants:
        group_sizes[p.conflict_group] = group_sizes.get(p.conflict_group, 0) + 1

    # Sabit yerleşimlerin koltukları kullanılamaz; salon bazında ayrıştır.
    fixed_by_room = occupants_by_room(pinned)

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

    # Kelebek yeterliliği KOLTUKLA değil SIRAYLA ölçülür (bkz. `butterfly_fit`):
    # her sıra her sınavdan en çok bir öğrenci alır. Eski denetim "grup > kapasite/2"
    # idi — ikili sıralarda doğru cevabı veriyordu ama tekli/üçlü sıra karışınca
    # sapıyordu ve kaç öğrencinin sığmadığını SÖYLEMİYORDU. Sabit (pinli) yerleşimler
    # koltuklarını düşürür, gruplarına ise girmez: iyimser taraf, pin birkaç öğrencidir.
    uyum = butterfly_fit(group_sizes.values(), desk_sizes(rooms, fixed_by_room))
    if uyum.deficit > 0 and group_sizes:
        # En kalabalık grup: eşitlikte anahtar sırası (deterministik metin).
        en_kalabalik = min(group_sizes, key=lambda g: (-group_sizes[g], g))
        ad = (group_labels or {}).get(en_kalabalik, "") or f"'{en_kalabalik}' grubu"
        result.warnings.append(
            f"{ad} sınavına {group_sizes[en_kalabalik]} öğrenci giriyor; bu salonlarda "
            f"{uyum.desks} sıra var. Kelebek düzeninde bir sıraya aynı sınavdan iki öğrenci "
            f"oturamaz — {uyum.deficit} öğrenci aynı sınavla yan yana oturmak zorunda kalır. "
            "Salon ekleyin ya da bu saate yakın mevcutlu başka bir sınav koyun."
        )

    # Faz 0 (Tur 243, talep 6): salon kotaları → grup-salon kotaları →
    # şube-hizalı paketleme. Eski "global akıştan sıralı dilim" yaklaşımı
    # bir şubeyi 4-6 salona serpiyordu; yeni kademeler şubeyi olabildiğince
    # az salonda toplar. Salon-içi grup karışımı _deal_order ile korunur —
    # kelebek ayrışma fizibilitesi değişmez. Seçimlik kipte (spread_sections)
    # yalnız üçüncü kademe değişir: şube salonlara payı oranında dağılır.
    capacities = [_available(r) for r in rooms]
    quotas = _room_quotas(n, capacities) if n else [0] * len(rooms)
    group_quotas = _group_room_quotas(group_sizes, quotas)
    # Sayılı yol ve kota düzeltmesi yalnız gereken kurulumda açılır: anahtarsız ikili yol
    # onlardan geçmez. Pinler ham ölçüye sayılmaz: pinli ikili salon hâlâ ikilidir.
    counted = _uses_counted_path(participants, pinned, rooms)
    hists = [desk_sizes([r], fixed_by_room) for r in rooms]
    locks = [separation_locks([r], fixed_by_room) for r in rooms]
    if counted or any(size != 2 for size in desk_sizes(rooms)):
        group_quotas = _fit_quotas_to_desks(group_quotas, capacities, hists)
    pack = _spread_section_chunks if spread_sections else _pack_section_chunks
    chunks = pack(_blend_section_order(participants, seed), group_quotas, len(rooms))
    if counted and len({p.separation_key for p in participants} - {""}) >= 2:
        chunks = _balance_separation(chunks, hists, locks)

    rng = random.Random(seed)  # noqa: S311 — kripto değil; seed'li deterministik arama
    fill = _counted_fill if counted else _constructive_fill
    for room, chunk, hist, locked in zip(rooms, chunks, hists, locks, strict=True):
        fixed = fixed_by_room.get(room.room_id, [])
        placements = fill(
            room,
            # Salon-içi harman: gruplar koltuk akışında serpilir, grup içi sıra numaradan.
            _deal_order(_blend_room_order(chunk, seed, room.room_id)),
            strict=strict,
            warnings=result.warnings,
            fixed=fixed,
            prev_seats=prev,
            narrow=narrow,
        )
        if counted:
            _counted_room(
                room,
                placements,
                rng=rng,
                seed=seed,
                fixed=fixed,
                prev_seats=prev,
                hist=hist,
                locked=locked,
                narrow=narrow,
            )
        else:
            _local_search(
                placements, room=room, rng=rng, fixed=fixed, prev_seats=prev, narrow=narrow
            )
        result.warnings.extend(
            _desk_conflict_warnings(room, placements, strict=strict, fixed=fixed)
        )
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
                f"{label} dersliği ({_room_text(room)}) kapasitesi yetersiz: "
                f"{len(ordered)} öğrenci / {len(room.seats)} koltuk."
            )
        for seat, student in zip(room.seats, ordered, strict=False):
            result.placements.append(
                Placement(participant=student, room_id=room.room_id, seat=seat)
            )
    return result
