"""Sayılı yol — kız/erkek ve üçlü sıra motorunun kalite kilitleri (06.11.2026).

`test_altin_kayit.py` anahtarsız ikili yolu kilitler; o yol bu koddan GEÇMEZ. Eski
testler de yeni yolun kalitesini sınamaz: kabul koşulu ters çevrilmiş motor 681/681
geçmişti. Bu dosya o yüzden "motor çöktü mü" değil "planı onaylanabilir mi" diye sorar.
Sayılar sabit senaryoya aittir; kopya değil, oturma geometrisi ölçülür.

Bir test kırmızıya dönerse iki olasılık vardır (`test_altin_kayit.py` kuralı):
  1. motor bozuldu (düzeltin), ya da
  2. değişiklik BİLİNÇLİ — o zaman `engine.ENGINE_VERSION` artırılır, kilit yenilenir.
Kilit yenilemek için `_kilit_ozeti` çıktısını yazın. Kilitler aynı motor sürümünde
geçerlidir: 06.11.2026'da 2. sürüm (yayımlanmadı) harmanla yeniden üretildi.

KVKK: bütün veri uydurmadır, cinsiyet anahtarı koddan kurulur.
"""

from __future__ import annotations

import hashlib
import io
import math
import random
from collections import Counter
from collections.abc import Callable
from dataclasses import replace
from datetime import date
from typing import Any, cast

import pytest
from django.core.exceptions import ValidationError
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.okul.models import SeparationMode, Student
from apps.sinav import engine, services, validator
from apps.sinav.layout import (
    Seat,
    default_section_plan,
    numbered_seats,
    reference_cell,
    validate_layout_plan,
)
from apps.sinav.models import (
    DeskType,
    ExamSession,
    NumberingScheme,
    ParticipantType,
    RuleType,
    SeatAssignment,
)
from apps.sinav.participants import Participant
from apps.sinav.tests.oturum_yardim import dagitilmis_oturum, ders, oturum, salon, sube


def _salon(
    room_id: int, rows: int = 5, cols: int = 4, tip: str = DeskType.DOUBLE
) -> engine.RoomSeats:
    """Varsayılan şablondan salon: öğretmen masası önde, sıralar tek tip."""
    plan = default_section_plan(rows, cols)
    for sira in cast(list[dict[str, Any]], plan["desks"]):
        sira["type"] = tip
    dogrulanmis = validate_layout_plan(plan)
    satir, sutun = reference_cell(dogrulanmis)
    return engine.RoomSeats(
        room_id=room_id,
        seats=tuple(numbered_seats(dogrulanmis, NumberingScheme.S_PATTERN)),
        focus=(float(sutun), float(satir)),
        label=f"S{room_id}",
    )


def _katilimci(sid: int, grup: str, seviye: int, sube_adi: str) -> Participant:
    return Participant(
        student_id=sid,
        full_name=f"Öğrenci {sid}",
        student_number=str(1000 + sid),
        class_level=seviye,
        class_section=sube_adi,
        course_id=int(grup.split(":")[0]),
        course_name=f"Ders {grup}",
        conflict_group=grup,
    )


def _katilimcilar(rng: random.Random, mevcutlar: list[int]) -> list[Participant]:
    """Grup mevcutlarından liste; her grup 24-36'lık şubelere bölünür."""
    out: list[Participant] = []
    sid = 0
    for gi, mevcut in enumerate(mevcutlar):
        seviye = 9 + gi % 4
        kalan = mevcut
        sira = 0
        while kalan > 0:
            al = min(kalan, rng.randint(24, 36))
            for _ in range(al):
                sid += 1
                out.append(_katilimci(sid, f"{gi + 1}:{seviye}", seviye, f"{chr(65 + sira)}{gi}"))
            kalan -= al
            sira += 1
    return out


def _bagimsiz(katilimcilar: list[Participant], rng: random.Random) -> list[Participant]:
    return [replace(p, separation_key=rng.choice("KE")) for p in katilimcilar]


def _kumeli(
    katilimcilar: list[Participant], rng: random.Random, yuksek: float
) -> list[Participant]:
    """Şube içi kümelenme: bir şube `yuksek` oranda K, sonraki 1-yuksek."""
    out: list[Participant] = []
    sira: dict[str, dict[tuple[int, str], int]] = {}
    bas: dict[str, int] = {}
    for p in katilimcilar:
        grup, sube_adi = p.conflict_group, (p.class_level, p.class_section)
        bas.setdefault(grup, rng.randrange(2))
        sira.setdefault(grup, {})
        sira[grup].setdefault(sube_adi, len(sira[grup]))
        oran = yuksek if (sira[grup][sube_adi] + bas[grup]) % 2 == 0 else 1 - yuksek
        out.append(replace(p, separation_key="K" if rng.random() < oran else "E"))
    return out


def _say(placements: list[engine.Placement]) -> tuple[int, int]:
    """Bağımsız sayım: (aynı sıra aynı sınav çifti, aynı sıra farklı anahtar çifti)."""
    masa: dict[tuple[int, int, int], list[Participant]] = {}
    for pl in placements:
        masa.setdefault((pl.room_id, pl.seat.desk_row, pl.seat.desk_col), []).append(pl.participant)
    grup = ayrisma = 0
    for uyeler in masa.values():
        for i, a in enumerate(uyeler):
            for b in uyeler[i + 1 :]:
                grup += a.conflict_group == b.conflict_group
                ayrisma += bool(
                    a.separation_key and b.separation_key and a.separation_key != b.separation_key
                )
    return grup, ayrisma


def _onaylanir(placements: list[engine.Placement]) -> bool:
    """Bağımsız doğrulayıcıya göre plan (gerekirse kabulle) onaylanabilir mi?"""
    yerlesim = [
        validator.PlacedStudent(
            student_id=pl.participant.student_id,
            conflict_group=pl.participant.conflict_group,
            room_id=pl.room_id,
            desk_row=pl.seat.desk_row,
            desk_col=pl.seat.desk_col,
            slot=pl.seat.slot,
            x=pl.seat.x,
            y=pl.seat.y,
            separation_key=pl.participant.separation_key,
        )
        for pl in placements
    ]
    return validator.validate_seating(yerlesim, separation=validator.SEPARATION_DESK).acceptable


def _sinir_izin_verir(katilimcilar: list[Participant], salonlar: list[engine.RoomSeats]) -> bool:
    """Motordan bağımsız sınır (ikili sıra): Σ ceil(n_k/2) ≤ sıra sayısı."""
    sayilar = Counter(p.separation_key for p in katilimcilar if p.separation_key)
    siralar = sum(len({(s.desk_row, s.desk_col) for s in r.seats}) for r in salonlar)
    return sum(math.ceil(v / 2) for v in sayilar.values()) <= siralar


def _kilit_ozeti(result: engine.DistributionResult) -> str:
    """Yerleşimin kısa özeti: girdi sırasından bağımsız, her koltuğu kapsar."""
    satirlar = sorted(
        f"{pl.participant.student_id}:{pl.room_id}/{pl.seat.desk_row},{pl.seat.desk_col},"
        f"{pl.seat.slot}"
        for pl in result.placements
    )
    return hashlib.sha256("|".join(satirlar).encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Onay: "aynı sıraya oturtma" kipinde onaylanabilir plan matematiksel sınıra eşit
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("mevcutlar", "beklenen"),
    [
        ([72, 72], 30),  # eski motor 1/30
        ([76, 76], 30),  # eski motor 0/30
        ([80, 80], 14),  # eski motor 0/30; kalan 16 numarada kız sayısı tek
        ([40, 40, 40, 40], 14),
        ([60, 50, 50], 16),
        ([36, 36, 36, 36], 30),
    ],
)
def test_ikili_salonda_onay_matematiksel_sinira_esit(mevcutlar: list[int], beklenen: int) -> None:
    """Tam ya da neredeyse tam salon, bağımsız K/E: sınırın izin verdiği her planı bulur."""
    salonlar = [_salon(i + 1) for i in range(4)]
    onay = 0
    for tohum in range(500, 530):
        rng = random.Random(tohum)  # noqa: S311 — test senaryosu üretimi
        katilimcilar = _bagimsiz(_katilimcilar(rng, mevcutlar), rng)
        sonuc = engine.distribute_butterfly(
            katilimcilar, salonlar, seed=rng.randrange(10**6)
        ).placements
        assert len(sonuc) == len(katilimcilar)
        assert _onaylanir(sonuc) == _sinir_izin_verir(katilimcilar, salonlar), f"tohum {tohum}"
        onay += _onaylanir(sonuc)
    assert onay == beklenen


@pytest.mark.parametrize("yuksek", [0.8, 1.0])
@pytest.mark.parametrize("mevcutlar", [[72, 72], [76, 76], [60, 50, 50]])
def test_sube_kumeli_kiz_erkekte_de_onay_sinira_esit(mevcutlar: list[int], yuksek: float) -> None:
    """Şube içinde cinsiyet kümeliyse salon içi çözüm yetmez: salonlar arası denge gerekir."""
    salonlar = [_salon(i + 1) for i in range(4)]
    for tohum in range(500, 515):
        rng = random.Random(tohum)  # noqa: S311 — test senaryosu üretimi
        katilimcilar = _kumeli(_katilimcilar(rng, mevcutlar), rng, yuksek)
        sonuc = engine.distribute_butterfly(katilimcilar, salonlar, seed=rng.randrange(10**6))
        assert _onaylanir(sonuc.placements) == _sinir_izin_verir(katilimcilar, salonlar), tohum


def test_denge_salonlar_arasi_anahtar_kumesini_cozer() -> None:
    """Salon payı tek sayılı kız/erkek taşıyorsa takas öğrencileri korur, hedefi düşürür."""

    def grup(no: str, anahtar: str, ilk: int, adet: int) -> list[Participant]:
        return [
            replace(_katilimci(i, f"{no}:9", 9, "A"), separation_key=anahtar)
            for i in range(ilk, ilk + adet)
        ]

    # 7 ikili sıralı iki salon, 14'er öğrenci. Her salonda K ve E tek sayılıdır: birer
    # sıra karışık kalır. Bir takas iki salonu da çift sayıya getirir.
    parcalar = [
        grup("1", "K", 1, 4) + grup("1", "E", 5, 3) + grup("2", "K", 8, 3) + grup("2", "E", 11, 4),
        grup("1", "K", 15, 3)
        + grup("1", "E", 18, 4)
        + grup("2", "K", 22, 4)
        + grup("2", "E", 26, 3),
    ]
    hist = [{2: 7}, {2: 7}]
    kimlikler = sorted(p.student_id for c in parcalar for p in c)
    once = [_hedef(c, h) for c, h in zip(parcalar, hist, strict=True)]

    sonra_parcalar = engine._balance_separation([list(c) for c in parcalar], hist)

    sonra = [_hedef(c, h) for c, h in zip(sonra_parcalar, hist, strict=True)]
    assert sum(h[0] for h in once) > 0
    assert sum(h[0] for h in sonra) < sum(h[0] for h in once)
    assert sorted(p.student_id for c in sonra_parcalar for p in c) == kimlikler
    assert [len(c) for c in sonra_parcalar] == [14, 14]


def _hedef(parca: list[Participant], hist: dict[int, int]) -> tuple[int, int]:
    sayim = Counter((p.conflict_group, p.separation_key) for p in parca)
    return engine._room_floor(sayim, hist)[0]


# ---------------------------------------------------------------------------
# Üçlü sıra ve karma salon
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("mevcutlar", "beklenen"),
    [([20, 12, 4], 8), ([26, 10], 16), ([18, 14, 4], 8)],  # eski motor 14,07 / 23,47 / 12,30
)
def test_uclu_sirada_ihlal_cift_tabanina_iner(mevcutlar: list[int], beklenen: int) -> None:
    """12 üçlü sıra: grup sıralara en eşit yayılınca oluşan çift sayısının üstüne çıkmaz."""
    salonlar = [_salon(1, 3, 4, DeskType.TRIPLE)]
    assert engine._pair_floor(mevcutlar, 12) == beklenen
    for tohum in range(30):
        katilimcilar = _katilimcilar(random.Random(8000 + tohum), mevcutlar)  # noqa: S311
        sonuc = engine.distribute_butterfly(katilimcilar, salonlar, seed=tohum)
        assert _say(sonuc.placements)[0] == beklenen, f"tohum {tohum}"


def _karisik_salon(room_id: int, rows: int = 5, cols: int = 4) -> engine.RoomSeats:
    """Aynı salonda ikili ve üçlü sıra (dönüşümlü): yerel aramanın takıldığı kurulum."""
    plan = default_section_plan(rows, cols)
    for i, sira in enumerate(cast(list[dict[str, Any]], plan["desks"])):
        sira["type"] = (DeskType.DOUBLE, DeskType.TRIPLE)[i % 2]
    dogrulanmis = validate_layout_plan(plan)
    satir, sutun = reference_cell(dogrulanmis)
    return engine.RoomSeats(
        room_id=room_id,
        seats=tuple(numbered_seats(dogrulanmis, NumberingScheme.S_PATTERN)),
        focus=(float(sutun), float(satir)),
    )


def test_ikili_uclu_karisik_salonda_yeniden_kurma_ayrismayi_sifirlar() -> None:
    """Tam dolu ikili+üçlü sıra: bir sırayı öteki anahtara çevirmek iki öğrenciyi birden
    taşır, ara adım ihlal olduğu için yerel arama oradan geçemez (yeniden kurmasız 0/20)."""
    salonlar = [_karisik_salon(i + 1) for i in range(3)]
    kapasite = sum(len(r.seats) for r in salonlar)
    mevcutlar = [kapasite // 2, kapasite - kapasite // 2]
    for tohum in range(9000, 9020):
        rng = random.Random(tohum)  # noqa: S311 — test senaryosu üretimi
        katilimcilar = _bagimsiz(_katilimcilar(rng, mevcutlar), rng)
        sonuc = engine.distribute_butterfly(katilimcilar, salonlar, seed=rng.randrange(10**6))
        assert _say(sonuc.placements)[1] == 0, f"tohum {tohum}"


def test_karma_salonda_kota_sira_sayisina_iner() -> None:
    """20 öğrencili sınav, 10 ikili + 10 tekli sıra: orantılı kota ikili salona 3 fazla yazıyordu."""
    salonlar = [_salon(1, 5, 2), _salon(2, 5, 2, DeskType.SINGLE)]
    for tohum in range(30):
        katilimcilar = _katilimcilar(random.Random(tohum), [20, 1])  # noqa: S311
        sonuc = engine.distribute_butterfly(katilimcilar, salonlar, seed=tohum)
        assert len(sonuc.placements) == 21
        assert _say(sonuc.placements)[0] == 0, f"tohum {tohum}"


def _karma_kurulum(ikili: int, tekli: int, sinav: int) -> tuple[list[int], list[dict[int, int]]]:
    """Baskın sınavlı tam dolu karma salonlar: mevcutlar + salon histogramları."""
    hists = [{2: 20} for _ in range(ikili)] + [{1: 20} for _ in range(tekli)]
    toplam = sum(c * n for h in hists for c, n in h.items())
    baskin = int(toplam * 0.62)
    kalan = toplam - baskin
    mevcutlar = [baskin] + [kalan // (sinav - 1)] * (sinav - 1)
    mevcutlar[1] += toplam - sum(mevcutlar)
    return mevcutlar, hists


def test_kota_duzeltmesi_acigi_kapatir_toplamlari_korur() -> None:
    """1200 öğrenci, 12 sınav: açık kapanır, grup mevcudu ve salon kapasitesi bozulmaz."""
    mevcutlar, hists = _karma_kurulum(20, 20, 12)
    kapasiteler = [sum(c * n for c, n in h.items()) for h in hists]
    gruplar = {f"{i + 1}:9": v for i, v in enumerate(mevcutlar)}
    kotalar = engine._group_room_quotas(gruplar, engine._room_quotas(sum(mevcutlar), kapasiteler))
    acik_once = sum(
        engine.butterfly_fit([v[j] for v in kotalar.values()], h).deficit
        for j, h in enumerate(hists)
    )
    assert acik_once > 0

    yeni = engine._fit_quotas_to_desks(kotalar, kapasiteler, hists)

    for j, h in enumerate(hists):
        assert engine.butterfly_fit([v[j] for v in yeni.values()], h).deficit == 0
        assert sum(v[j] for v in yeni.values()) <= kapasiteler[j]
    assert {k: sum(v) for k, v in yeni.items()} == gruplar
    assert yeni == engine._fit_quotas_to_desks(kotalar, kapasiteler, hists)  # deterministik


def test_kota_duzeltmesi_hesap_bedeli_sinirli(monkeypatch: pytest.MonkeyPatch) -> None:
    """Süre saatle değil hesap sayısıyla kilitlenir: ilk sürüm 1200 öğrencide 80 sn sürüyordu."""
    mevcutlar, hists = _karma_kurulum(20, 20, 12)
    kapasiteler = [sum(c * n for c, n in h.items()) for h in hists]
    gruplar = {f"{i + 1}:9": v for i, v in enumerate(mevcutlar)}
    kotalar = engine._group_room_quotas(gruplar, engine._room_quotas(sum(mevcutlar), kapasiteler))
    gercek = engine._bound_deficit
    cagri = 0

    def sayan(vector: list[int], bounds: list[int]) -> int:
        nonlocal cagri
        cagri += 1
        return gercek(vector, bounds)

    monkeypatch.setattr(engine, "_bound_deficit", sayan)
    engine._fit_quotas_to_desks(kotalar, kapasiteler, hists)
    assert cagri < 300_000


def test_acik_hesabi_butterfly_fit_ile_ayni() -> None:
    """Sıcak yol kardeşi tek kaynaktan ayrışmamalı: rastgele girdide aynı açık."""
    rng = random.Random(4)  # noqa: S311 — test senaryosu üretimi
    for _ in range(300):
        hist = {c: rng.randint(0, 12) for c in rng.sample([1, 2, 3], rng.randint(1, 3))}
        grup = [rng.randint(0, 30) for _ in range(rng.randint(1, 7))]
        beklenen = engine.butterfly_fit(grup, hist).deficit
        assert engine._bound_deficit(grup, engine._desk_bounds(hist, len(grup))) == beklenen


# ---------------------------------------------------------------------------
# Ceza ölçüsü: takas gerçek farkı ölçer, odak yalnız eşitlik bozar
# ---------------------------------------------------------------------------
def _durum(
    room: engine.RoomSeats, kisiler: list[tuple[str, str]], rng: random.Random
) -> tuple[engine._RoomState, list[engine.Placement]]:
    koltuklar = rng.sample(list(room.seats), len(kisiler))
    placements = [
        engine.Placement(
            participant=replace(_katilimci(i + 1, f"{g}:9", 9, "A"), separation_key=k),
            room_id=room.room_id,
            seat=koltuk,
        )
        for i, ((g, k), koltuk) in enumerate(zip(kisiler, koltuklar, strict=True))
    ]
    return engine._RoomState(room, placements, [], None), placements


@pytest.mark.parametrize("tip", [DeskType.DOUBLE, DeskType.TRIPLE])
def test_takas_olcusu_ihlal_farkini_tam_verir(tip: str) -> None:
    """Takasın ölçtüğü fark, salonun sıfırdan sayılan ihlal farkına HER çiftte eşit.

    Eski takas iki öğrencinin aralarındaki terimi iki kez sayıyordu; aynı sıradaki
    çift takasta değişmediği hâlde "iyileşti" görünüyordu.
    """
    rng = random.Random(11)  # noqa: S311 — test senaryosu üretimi
    room = _salon(1, 3, 4, tip)
    kisiler = [(str(1 + i % 3), "KE"[i % 2]) for i in range(len(room.seats) - 3)]
    state, _yerlesim = _durum(room, kisiler, rng)
    for _ in range(400):
        i, j = rng.sample(range(state.n), 2)
        once, sonra = state.swap_vectors(i, j)
        ayrisma0, grup0 = state.violations()
        state.apply_swap(i, j)
        ayrisma1, grup1 = state.violations()
        assert (sonra[0] - once[0], sonra[1] - once[1]) == (ayrisma1 - ayrisma0, grup1 - grup0)


def test_tasima_olcusu_ihlal_farkini_tam_verir() -> None:
    rng = random.Random(12)  # noqa: S311 — test senaryosu üretimi
    room = _salon(1, 3, 4)
    kisiler = [(str(1 + i % 2), "KE"[i % 2]) for i in range(len(room.seats) - 6)]
    state, _yerlesim = _durum(room, kisiler, rng)
    for _ in range(200):
        i = rng.randrange(state.n)
        hedef = rng.choice(state.free)
        once, sonra = state.cost(i, state.pos[i]), state.cost(i, hedef)
        ayrisma0, grup0 = state.violations()
        state.apply_move(i, hedef)
        ayrisma1, grup1 = state.violations()
        assert (sonra[0] - once[0], sonra[1] - once[1]) == (ayrisma1 - ayrisma0, grup1 - grup0)


def _koltuk(room: engine.RoomSeats, satir: int, slot: int) -> int:
    return next(
        i
        for i, s in enumerate(room.seats)
        if s.desk_row == satir and s.slot == slot and s.desk_col == room.seats[0].desk_col
    )


def _tek_sutun_durumu(
    dolu: list[tuple[int, int]], aday: tuple[int, int]
) -> tuple[engine.RoomSeats, engine._RoomState]:
    room = _salon(1, 6, 1)
    koltuklar = [room.seats[_koltuk(room, r, s)] for r, s in [*dolu, aday]]
    placements = [
        engine.Placement(participant=_katilimci(i + 1, "1:9", 9, "A"), room_id=1, seat=koltuk)
        for i, koltuk in enumerate(koltuklar)
    ]
    return room, engine._RoomState(room, placements, [], None)


def test_odak_yakinligi_gecemez() -> None:
    """Kullanıcı kararı: çift masaya ÇEKİLMEZ — yakınlık cezası farklıysa odak söz alamaz.

    Masaya yakın koltuk komşu sıraya da düştüğü için yumuşak cezası yüksektir; aday
    uzak sıraya gider, oradaki odak cezası çok daha büyük olsa bile.
    """
    room = _salon(1, 6, 1)
    ilk = room.seats[0].desk_row
    son = max(s.desk_row for s in room.seats)
    _room, state = _tek_sutun_durumu([(ilk, 0), (ilk + 1, 0), (son, 0)], (ilk + 2, 1))
    yakin, uzak = _koltuk(room, ilk, 1), _koltuk(room, son, 1)
    yakin_ceza, uzak_ceza = state.cost(state.n - 1, yakin), state.cost(state.n - 1, uzak)
    assert yakin_ceza[1] == uzak_ceza[1] == 1  # ikisi de aynı sıra ihlali
    assert yakin_ceza[2] > uzak_ceza[2]  # yakınlık: uzak koltuk iyi
    assert yakin_ceza[3] < uzak_ceza[3]  # odak: yakın koltuk iyi
    assert uzak_ceza < yakin_ceza  # karar yakınlığın


def test_odak_esitligi_bozar() -> None:
    """Yakınlık tam eşitse aynı sıra çifti masaya yakın olanı seçilir (ikincil sözleşme)."""
    room = _salon(1, 6, 1)
    ilk = room.seats[0].desk_row
    _room, state = _tek_sutun_durumu([(ilk, 0), (ilk + 1, 0)], (ilk + 3, 0))
    yakin, uzak = _koltuk(room, ilk, 1), _koltuk(room, ilk + 1, 1)
    yakin_ceza, uzak_ceza = state.cost(state.n - 1, yakin), state.cost(state.n - 1, uzak)
    assert yakin_ceza[:3] == uzak_ceza[:3]
    assert yakin_ceza < uzak_ceza


# ---------------------------------------------------------------------------
# Sözleşmeler: yol seçimi, pin, tekrar üretim
# ---------------------------------------------------------------------------
def test_yol_secimi() -> None:
    """Sayılı yol yalnız iki farklı anahtar ya da üçlü sıra varken açılır."""
    ikili, uclu = [_salon(1)], [_salon(1, tip=DeskType.TRIPLE)]
    duz = [_katilimci(1, "1:9", 9, "A"), _katilimci(2, "2:10", 10, "A")]
    tek_anahtar = [replace(p, separation_key="K") for p in duz]
    joker_ile = [tek_anahtar[0], duz[1]]
    iki_anahtar = [tek_anahtar[0], replace(duz[1], separation_key="E")]
    assert not engine._uses_counted_path(duz, [], ikili)
    assert not engine._uses_counted_path(tek_anahtar, [], ikili)
    assert not engine._uses_counted_path(joker_ile, [], ikili)
    assert engine._uses_counted_path(iki_anahtar, [], ikili)
    assert engine._uses_counted_path(duz, [], uclu)
    pinli = engine.Placement(
        participant=replace(duz[1], separation_key="E"), room_id=1, seat=ikili[0].seats[0]
    )
    assert engine._uses_counted_path(tek_anahtar[:1], [pinli], ikili)


def test_pinli_ogrenci_sayili_yolda_tasinmaz_ve_sonuca_girmez() -> None:
    rng = random.Random(21)  # noqa: S311 — test senaryosu üretimi
    salonlar = [_salon(1), _salon(2)]
    katilimcilar = _bagimsiz(_katilimcilar(rng, [30, 30]), rng)
    pinli = engine.Placement(participant=katilimcilar[0], room_id=1, seat=salonlar[0].seats[5])
    sonuc = engine.distribute_butterfly(katilimcilar[1:], salonlar, seed=9, preplaced=[pinli])
    assert katilimcilar[0].student_id not in {p.participant.student_id for p in sonuc.placements}
    dolu = {(p.room_id, p.seat.desk_row, p.seat.desk_col, p.seat.slot) for p in sonuc.placements}
    assert len(dolu) == len(sonuc.placements) == 59
    koltuk = salonlar[0].seats[5]
    assert (1, koltuk.desk_row, koltuk.desk_col, koltuk.slot) not in dolu


def test_salon_listesi_disindaki_pin_sayili_yolu_dusurmez() -> None:
    """Doğrudan çağıranın pini koltuk listesinde olmayabilir: ceza üretir, çökmez."""
    rng = random.Random(22)  # noqa: S311 — test senaryosu üretimi
    tam = _salon(1)
    dar = engine.RoomSeats(room_id=1, seats=tam.seats[1:], focus=tam.focus, label=tam.label)
    katilimcilar = _bagimsiz(_katilimcilar(rng, [12, 12]), rng)
    pinli = engine.Placement(participant=katilimcilar[0], room_id=1, seat=tam.seats[0])
    sonuc = engine.distribute_butterfly(katilimcilar[1:], [dar], seed=3, preplaced=[pinli])
    assert len(sonuc.placements) == 23


def test_ayni_numara_ayni_plan() -> None:
    """Sözleşme sayılı yolda da tutar; numara değişince plan değişir."""
    rng = random.Random(23)  # noqa: S311 — test senaryosu üretimi
    salonlar = [_salon(1), _salon(2, tip=DeskType.TRIPLE)]
    katilimcilar = _bagimsiz(_katilimcilar(rng, [50, 40, 10]), rng)
    a = engine.distribute_butterfly(katilimcilar, salonlar, seed=77)
    b = engine.distribute_butterfly(katilimcilar, salonlar, seed=77)
    c = engine.distribute_butterfly(katilimcilar, salonlar, seed=78)
    assert _kilit_ozeti(a) == _kilit_ozeti(b)
    assert _kilit_ozeti(a) != _kilit_ozeti(c)


def _kilit_uclu() -> engine.DistributionResult:
    katilimcilar = _katilimcilar(random.Random(8000), [20, 12, 4])  # noqa: S311
    return engine.distribute_butterfly(katilimcilar, [_salon(1, 3, 4, DeskType.TRIPLE)], seed=0)


def _kilit_kiz_erkek() -> engine.DistributionResult:
    rng = random.Random(500)  # noqa: S311 — test senaryosu üretimi
    katilimcilar = _bagimsiz(_katilimcilar(rng, [72, 72]), rng)
    salonlar = [_salon(i + 1) for i in range(4)]
    return engine.distribute_butterfly(katilimcilar, salonlar, seed=rng.randrange(10**6))


def _kilit_kumeli() -> engine.DistributionResult:
    rng = random.Random(501)  # noqa: S311 — test senaryosu üretimi
    katilimcilar = _kumeli(_katilimcilar(rng, [60, 50, 50]), rng, 0.8)
    salonlar = [_salon(i + 1) for i in range(4)]
    return engine.distribute_butterfly(katilimcilar, salonlar, seed=rng.randrange(10**6))


def _pinli_kurulum() -> tuple[engine.DistributionResult, list[engine.Placement]]:
    """Tam dolu salonda kız/erkek + dört pin: yeniden kurmayı pinli salonda da koşturur."""
    rng = random.Random(502)  # noqa: S311 — test senaryosu üretimi
    katilimcilar = _bagimsiz(_katilimcilar(rng, [76, 76]), rng)
    salonlar = [_salon(i + 1) for i in range(4)]
    secilen = rng.sample(katilimcilar, 4)
    yerler = rng.sample([(s.room_id, k) for s in salonlar for k in s.seats], 4)
    pinler = [
        engine.Placement(participant=kisi, room_id=salon_kimligi, seat=koltuk)
        for kisi, (salon_kimligi, koltuk) in zip(secilen, yerler, strict=True)
    ]
    kalan = [p for p in katilimcilar if p not in secilen]
    sonuc = engine.distribute_butterfly(
        kalan, salonlar, seed=rng.randrange(10**6), preplaced=pinler
    )
    return sonuc, pinler


def _kilit_pinli() -> engine.DistributionResult:
    return _pinli_kurulum()[0]


def _kilit_karma() -> engine.DistributionResult:
    katilimcilar = _katilimcilar(random.Random(5), [20, 1])  # noqa: S311
    salonlar = [_salon(1, 5, 2), _salon(2, 5, 2, DeskType.SINGLE)]
    return engine.distribute_butterfly(katilimcilar, salonlar, seed=5)


@pytest.mark.parametrize(
    ("kurulum", "beklenen"),
    [
        (_kilit_uclu, "353237853d67a7e9"),
        (_kilit_kiz_erkek, "03a00299a2f9e408"),
        (_kilit_kumeli, "190c6916c986041d"),
        (_kilit_karma, "affe6cb6d110d426"),
        (_kilit_pinli, "3fd43ce62066e198"),
    ],
)
def test_sayili_yol_kilidi(kurulum: Callable[[], engine.DistributionResult], beklenen: str) -> None:
    """Altın kaydın sayılı yol karşılığı: bit bit aynı plan (bkz. dosya başı)."""
    assert _kilit_ozeti(kurulum()) == beklenen


# ---------------------------------------------------------------------------
# Koruyucu dallar: bit kilidinden bağımsız DAVRANIŞ testleri
# ---------------------------------------------------------------------------
def _kisi(sid: int, grup: str, anahtar: str, sube_adi: str = "A") -> Participant:
    return replace(_katilimci(sid, f"{grup}:9", 9, sube_adi), separation_key=anahtar)


def _siralar(room: engine.RoomSeats) -> list[list[Seat]]:
    """Tek sütunlu salonun sıraları, önden arkaya."""
    satirlar = sorted({s.desk_row for s in room.seats})
    return [[s for s in room.seats if s.desk_row == satir] for satir in satirlar]


def _yerlesim(
    room: engine.RoomSeats, kisiler: list[tuple[Participant, Seat]]
) -> list[engine.Placement]:
    return [
        engine.Placement(participant=kisi, room_id=room.room_id, seat=koltuk)
        for kisi, koltuk in kisiler
    ]


def _plan_tutarli(durum: engine._RoomState) -> None:
    """Hareketli ve sabit her öğrenci tek koltukta; koltuk defteri konumla aynı."""
    assert len(set(durum.pos)) == len(durum.pos)
    assert all(pos >= 0 for pos in durum.pos)
    for ogrenci, koltuk in enumerate(durum.pos):
        assert durum.who[koltuk] == ogrenci
    assert sorted(durum.free) == [s for s, m in enumerate(durum.who) if m < 0]


def test_yeniden_kurma_sabit_ogrencinin_koltugunu_ezmez() -> None:
    room = _salon(1, 3, 1)
    ilk, ikinci, ucuncu = _siralar(room)
    durum = engine._RoomState(
        room,
        _yerlesim(
            room,
            [
                (_kisi(1, "1", "E"), ilk[1]),
                (_kisi(2, "1", "K"), ikinci[0]),
                (_kisi(3, "2", "E"), ikinci[1]),
                (_kisi(4, "2", "K"), ucuncu[0]),
            ],
        ),
        [(ilk[0], "9:9", "K")],
        None,
    )
    sabit_koltuk = durum.pos[4]
    engine._rebuild(durum, ("E", "K", {1: 0, 2: 1}))
    assert durum.pos[4] == sabit_koltuk
    assert durum.who[sabit_koltuk] == 4
    _plan_tutarli(durum)


def test_yeniden_kurma_sabit_ogrencinin_sirasini_onun_anahtarina_ayirir() -> None:
    """Sırada çoğunluk öbür anahtarda olsa da sabit öğrencinin tarafı kazanır."""
    tam = _salon(1, 2, 1)
    ilk, ikinci = _siralar(tam)
    room = engine.RoomSeats(room_id=1, seats=(ilk[0], ilk[1], ikinci[0]), focus=tam.focus)
    durum = engine._RoomState(
        room,
        _yerlesim(room, [(_kisi(1, "1", "E"), ilk[1]), (_kisi(2, "2", "K"), ikinci[0])]),
        [(ilk[0], "9:9", "K")],
        None,
    )
    assert durum.violations() == (1, 0)
    engine._rebuild(durum, ("E", "K", {1: 1}))
    assert durum.violations() == (0, 0)


def test_pinli_salonda_yeniden_kurma_kosar_pin_yerinde_kalir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gercek = engine._rebuild
    cagri: list[int] = []

    def sayan(durum: engine._RoomState, bolusum: engine.DeskSplit | None) -> None:
        cagri.append(len(durum.pos) - durum.n)
        gercek(durum, bolusum)

    monkeypatch.setattr(engine, "_rebuild", sayan)
    sonuc, pinler = _pinli_kurulum()
    assert any(sabit > 0 for sabit in cagri), "pinli salonda yeniden kurma koşmadı"
    dolu = {(p.room_id, p.seat.desk_row, p.seat.desk_col, p.seat.slot) for p in sonuc.placements}
    assert len(dolu) == len(sonuc.placements)
    assert not dolu & {(p.room_id, p.seat.desk_row, p.seat.desk_col, p.seat.slot) for p in pinler}
    assert _say([*sonuc.placements, *pinler])[1] == 0


@pytest.mark.parametrize("bolusum", [None, ("E", "K", {2: 2})])
def test_yeniden_kurma_jokerleri_de_koltuga_oturtur(bolusum: engine.DeskSplit | None) -> None:
    room = _salon(1, 4, 1)
    kisiler = [("1", "K"), ("1", "E"), ("2", ""), ("2", "K"), ("3", ""), ("3", "E")]
    durum, _yerlesimler = _durum(room, kisiler, random.Random(31))  # noqa: S311
    engine._rebuild(durum, bolusum)
    _plan_tutarli(durum)


def test_sabit_yerlesim_sayili_cezaya_girer() -> None:
    room = _salon(1, 3, 1)
    ilk, _orta, son = _siralar(room)
    durum = engine._RoomState(
        room,
        _yerlesim(room, [(_kisi(1, "1", "K"), son[0])]),
        [(ilk[0], "1:9", "E")],
        None,
    )
    yan = durum.seats.index(ilk[1])
    assert durum.cost(0, yan)[:2] == (1, 1)
    assert durum.cost(0, durum.pos[0])[:2] == (0, 0)


def test_onceki_sira_cezasi_salon_ve_sira_kimligiyle_sorulur() -> None:
    room = _salon(1, 3, 1)
    ilk, _orta, son = _siralar(room)

    def durum(salon_kimligi: int) -> engine._RoomState:
        onceki = {1: (salon_kimligi, ilk[0].desk_row, ilk[0].desk_col)}
        return engine._RoomState(room, _yerlesim(room, [(_kisi(1, "1", ""), son[0])]), [], onceki)

    ayni_salon, baska_salon = durum(1), durum(2)
    eski_koltuk, yeni_koltuk = ayni_salon.seats.index(ilk[1]), ayni_salon.pos[0]
    assert ayni_salon.cost(0, eski_koltuk)[2] == engine._PREV_SEAT_WEIGHT
    assert ayni_salon.cost(0, yeni_koltuk)[2] == 0.0
    assert baska_salon.cost(0, eski_koltuk)[2] == 0.0


def _ihlalli_kurulum() -> tuple[engine.RoomSeats, list[engine.Placement]]:
    """Bir aynı sıra ihlali olan dört kişilik salon."""
    room = _salon(1, 4, 1)
    koltuklar = [koltuk for sira in _siralar(room) for koltuk in sira]
    return room, _yerlesim(
        room,
        [
            (_kisi(1, "1", ""), koltuklar[0]),
            (_kisi(2, "1", ""), koltuklar[1]),
            (_kisi(3, "2", ""), koltuklar[2]),
            (_kisi(4, "3", ""), koltuklar[4]),
        ],
    )


def _koltuklar(placements: list[engine.Placement]) -> list[tuple[int, int, int]]:
    return [(p.seat.desk_row, p.seat.desk_col, p.seat.slot) for p in placements]


def _arama_yok(_durum: engine._RoomState, _rng: random.Random, _butce: int) -> None:
    return None


def _bir_cekis(_durum: engine._RoomState, rng: random.Random, _butce: int) -> None:
    rng.random()


@pytest.mark.parametrize(
    "bozuk_plan",
    [
        pytest.param([1, 0, 2, 4], id="aynı ihlal, başka koltuk"),
        pytest.param([0, 1, 4, 5], id="ihlal artar"),
    ],
)
def test_yeniden_kurma_ihlali_dusurmezse_geri_alinir(
    monkeypatch: pytest.MonkeyPatch, bozuk_plan: list[int]
) -> None:
    room, yerlesim = _ihlalli_kurulum()
    baslangic = _koltuklar(yerlesim)

    def bozan(durum: engine._RoomState, _bolusum: engine.DeskSplit | None) -> None:
        durum.who[:] = [-1] * len(durum.who)
        for ogrenci, koltuk in enumerate(bozuk_plan):
            durum.pos[ogrenci] = koltuk
            durum.who[koltuk] = ogrenci
        durum.free[:] = [s for s, m in enumerate(durum.who) if m < 0]

    monkeypatch.setattr(engine, "_rebuild", bozan)
    monkeypatch.setattr(engine, "_counted_search", _arama_yok)
    engine._counted_room(
        room,
        yerlesim,
        rng=random.Random(1),  # noqa: S311 — test senaryosu üretimi
        seed=1,
        fixed=[],
        prev_seats=None,
        hist={2: 4},
        locked={},
    )
    assert _koltuklar(yerlesim) == baslangic


def test_yeniden_kurma_sonraki_salonun_rng_akisini_kaydirmaz(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Yeniden kurma alt akış kullanır: ana akış salon başına aynı miktar ilerler."""
    gercek = engine._rebuild

    def kos(kurulsun: bool) -> tuple[object, int]:
        room, yerlesim = _ihlalli_kurulum()
        rng = random.Random(7)  # noqa: S311 — test senaryosu üretimi
        cagri = 0

        def sayan(durum: engine._RoomState, bolusum: engine.DeskSplit | None) -> None:
            nonlocal cagri
            cagri += 1
            gercek(durum, bolusum)

        with monkeypatch.context() as m:
            m.setattr(engine, "_rebuild", sayan)
            m.setattr(engine, "_counted_search", _bir_cekis)
            if not kurulsun:
                m.setattr(engine, "_room_floor", lambda *_a: ((99, 99), None))
            engine._counted_room(
                room,
                yerlesim,
                rng=rng,
                seed=1,
                fixed=[],
                prev_seats=None,
                hist={2: 4},
                locked={},
            )
        return rng.getstate(), cagri

    kuruldu, kurulmadi = kos(True), kos(False)
    assert (kuruldu[1], kurulmadi[1]) == (1, 0)
    assert kuruldu[0] == kurulmadi[0]


def test_ayni_sinavda_farkli_anahtarli_takas_denenir() -> None:
    """Karışık iki sırayı yalnız aynı sınavın iki öğrencisini takas etmek düzeltir."""
    room = _salon(1, 2, 1)
    ilk, ikinci = _siralar(room)
    durum = engine._RoomState(
        room,
        _yerlesim(
            room,
            [
                (_kisi(1, "1", "K"), ilk[0]),
                (_kisi(2, "2", "E"), ilk[1]),
                (_kisi(3, "1", "E"), ikinci[0]),
                (_kisi(4, "2", "K"), ikinci[1]),
            ],
        ),
        [],
        None,
    )
    assert durum.violations() == (2, 0)
    engine._counted_search(durum, random.Random(1), 400)  # noqa: S311 — test senaryosu
    assert durum.violations() == (0, 0)


def _tek_koltuk_doldur(
    adaylar: list[Participant],
    sabit: list[engine.Occupant],
    koltuk: Seat,
    *,
    strict: bool,
) -> int:
    room = engine.RoomSeats(room_id=1, seats=(koltuk,))
    sonuc = engine._counted_fill(room, adaylar, strict=strict, warnings=[], fixed=sabit)
    return sonuc[0].participant.student_id


def test_doldurma_ayrismayi_sayar() -> None:
    ilk = _siralar(_salon(1, 2, 1))[0]
    aday = _tek_koltuk_doldur(
        [_kisi(1, "1", "E"), _kisi(2, "2", "K")], [(ilk[0], "3:9", "K")], ilk[1], strict=False
    )
    assert aday == 2


@pytest.mark.parametrize(("kati", "beklenen"), [(False, 2), (True, 1)])
def test_kati_doldurma_komsu_sirayi_ihlal_sayar(kati: bool, beklenen: int) -> None:
    """Katıda iki komşu sıra çakışması, tek aynı sıra çakışmasından ağırdır."""
    ilk, orta, son = _siralar(_salon(1, 3, 1))
    sabit: list[engine.Occupant] = [
        (orta[0], "1:9", ""),  # aynı sırada 1. adayın grubu
        (ilk[0], "2:9", ""),  # ön ve arka sırada 2. adayın grubu
        (son[0], "2:9", ""),
    ]
    aday = _tek_koltuk_doldur([_kisi(1, "1", ""), _kisi(2, "2", "")], sabit, orta[1], strict=kati)
    assert aday == beklenen


def test_salon_hedefi_jokeri_anahtar_saymaz() -> None:
    sayim = {("1:9", "K"): 3, ("1:9", "E"): 3, ("2:9", ""): 2}
    _hedef_degeri, bolusum = engine._room_floor(sayim, {2: 4})
    assert bolusum is not None
    assert bolusum[:2] == ("E", "K")


def test_denge_takasi_sube_salon_ciftini_artirmayan_ogrenciyi_secer() -> None:
    parcalar = [
        [_kisi(1, "1", "K", "A"), _kisi(2, "1", "K", "B"), _kisi(3, "2", "K", "B")],
        [
            _kisi(4, "1", "E", "B"),
            _kisi(5, "1", "E", "C"),
            _kisi(6, "2", "E", "A"),
            _kisi(7, "2", "E", "C"),
        ],
    ]
    engine._swap_students(parcalar, 0, 1, ("1:9", "K"), ("1:9", "E"))
    assert [p.student_id for p in parcalar[0]] == [4, 2, 3]
    assert [p.student_id for p in parcalar[1]] == [1, 5, 6, 7]


def test_dev_salonda_bolusum_sayisi_butcelidir(monkeypatch: pytest.MonkeyPatch) -> None:
    gercek = engine._side_floor
    cagri = 0

    def sayan(gruplar: list[int], hist: dict[int, int]) -> tuple[int, int]:
        nonlocal cagri
        cagri += 1
        return gercek(gruplar, hist)

    monkeypatch.setattr(engine, "_side_floor", sayan)
    sayim = {("1:9", "K"): 200, ("1:9", "E"): 200, ("2:9", "K"): 100, ("2:9", "E"): 100}
    hist = {1: 200, 2: 100, 3: 300}
    _hedef_degeri, bolusum = engine._room_floor(sayim, hist)
    assert cagri <= 2 * engine._FLOOR_SPLIT_BUDGET
    assert bolusum is not None
    assert all(0 <= bolusum[2][olcu] <= adet for olcu, adet in hist.items())


def test_olagan_salonda_butun_bolusumler_denenir() -> None:
    secenek = engine._split_options({1: 19, 2: 19, 3: 19})
    assert {olcu: len(liste) for olcu, liste in secenek.items()} == {1: 20, 2: 20, 3: 20}


def test_seyreltilen_bolusum_iki_ucu_ve_en_kalabalik_olcuyu_tam_tarar() -> None:
    secenek = engine._split_options({1: 200, 2: 100, 3: 300})
    assert secenek[3] == list(range(301))
    for olcu, adet in ((1, 200), (2, 100)):
        assert secenek[olcu][0] == 0
        assert secenek[olcu][-1] == adet
    assert math.prod(len(liste) for liste in secenek.values()) <= engine._FLOOR_SPLIT_BUDGET


# ---------------------------------------------------------------------------
# Uyarı metni: neden iddia edilmez, tür doğru söylenir
# ---------------------------------------------------------------------------
def test_kati_dagitim_uyarisi_komsu_sirayi_soyler() -> None:
    """Katı dağıtımda aynı sıra çakışması yokken uyarı "aynı sıra" DEMEZ."""
    room = _salon(1, 3, 2, DeskType.SINGLE)
    students = [_katilimci(i, "1:9", 9, "A") for i in range(1, 5)] + [
        _katilimci(i, "2:10", 10, "A") for i in range(5, 7)
    ]
    result = engine.distribute_butterfly(students, [room], seed=1, strict=True)
    satirlar = [w for w in result.warnings if w.endswith(engine.DESK_CONFLICT_WARNING_TAIL)]
    assert satirlar
    assert all("komşu sıralara" in w and "aynı sıraya" not in w for w in satirlar)


def test_sira_cakismasi_uyarisi_neden_iddia_etmez() -> None:
    """Sıra bütçesi yeterken kalan çakışmaya "kaçınılmaz" denmez (kota da sebep olabilir)."""
    rng = random.Random(9)  # noqa: S311 — test senaryosu üretimi
    for _ in range(40):
        room = _salon(1, rng.randint(3, 5), rng.randint(2, 4))
        n = rng.randint(4, len(room.seats))
        students = [_katilimci(i, f"{i % 2 + 1}:9", 9, "A") for i in range(1, n + 1)]
        result = engine.distribute_butterfly(students, [room], seed=rng.randint(1, 999))
        assert not any("kaçınılmaz" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Parite uyarısı
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("sayilar", "olculer", "beklenen"),
    [
        ([80, 80], {2: 80}, 0),
        ([81, 79], {2: 80}, 1),  # tam dolu, tek sayı: bir sıra karışık kalır
        ([81, 78], {2: 80}, 0),  # bir joker: boş kalan koltuğa oturur
        ([79, 79], {2: 80}, 0),
        ([1, 1], {2: 1}, 1),
        ([5, 5], {1: 10}, 0),  # tekli sırada karışık sıra olmaz
        ([71, 69], {2: 60, 1: 20}, 0),  # tam dolu, tek sayı, ama tekli sıra bölüşümü açar
        ([4, 4], {3: 3}, 1),  # üçlü sırada koltuk yetse de bölünemez
        ([3, 6], {3: 3}, 0),
        ([160], {2: 80}, 0),  # tek anahtar: kural girmiyor
        ([90, 90], {2: 80}, 0),  # koltuk yetmiyor: o açığı kapasite söyler
        ([3, 3, 3], {2: 5}, 0),  # iki anahtar dışı: hesap yok
    ],
)
def test_ayrisma_sira_acigi(sayilar: list[int], olculer: dict[int, int], beklenen: int) -> None:
    assert engine.separation_desk_gap(sayilar, olculer) == beklenen


def _ayrisma_oturumu(mod: str) -> tuple[ExamSession, list[int]]:
    """8 öğrenci, 8 koltuk (4 ikili sıra): 5 kız + 3 erkek, sınavlar 4 + 4."""
    sube(9, "A", students=4, start_no=101)
    sube(10, "A", students=4, start_no=201)
    course = ders("Coğrafya", levels=[9, 10])
    session = oturum(separation_mode=mod)
    for level in (9, 10):
        services.add_session_course(
            session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=level
        )
    for i, ogrenci in enumerate(Student.objects.order_by("student_number")):
        ogrenci.gender = "K" if i < 5 else "E"
        ogrenci.save(update_fields=["gender"])
    secili = salon("D-201")
    services.set_session_rooms(session, [{"room_id": secili.pk}])
    return session, [secili.pk]


@pytest.mark.django_db
def test_api_tam_salonda_tek_sayiyi_dagitimdan_once_soyler() -> None:
    session, _salonlar = _ayrisma_oturumu(SeparationMode.DESK)
    resp = APIClient().get(f"/api/v1/exam-sessions/{session.pk}/butterfly-fit/")
    assert resp.status_code == 200
    assert resp.data["separation_extra_desks"] == 1
    assert "en az 1 sıra daha gerekir" in resp.data["separation_message"]
    # Yalnız eksik sıra söylenir: kız/erkek sayısı metne girmez.
    assert "5" not in resp.data["separation_message"]
    assert "3" not in resp.data["separation_message"]


@pytest.mark.django_db
def test_api_ek_salon_secilince_uyari_kalkar() -> None:
    session, salonlar = _ayrisma_oturumu(SeparationMode.DESK)
    hepsi = ",".join(str(pk) for pk in [*salonlar, salon("D-202").pk])
    resp = APIClient().get(f"/api/v1/exam-sessions/{session.pk}/butterfly-fit/?rooms={hepsi}")
    assert resp.data["separation_extra_desks"] == 0
    assert resp.data["separation_message"] == ""


@pytest.mark.django_db
@pytest.mark.parametrize("mod", [SeparationMode.NONE, SeparationMode.ROOM])
def test_api_baska_kipte_ayrisma_uyarisi_yok(mod: str) -> None:
    session, _salonlar = _ayrisma_oturumu(mod)
    resp = APIClient().get(f"/api/v1/exam-sessions/{session.pk}/butterfly-fit/")
    assert resp.data["separation_extra_desks"] == 0
    assert resp.data["separation_message"] == ""


@pytest.mark.django_db
def test_cinsiyete_gore_sayi_dagitim_kaydina_girmez() -> None:
    session, _salonlar = _ayrisma_oturumu(SeparationMode.DESK)
    session, _sonuc, _rapor = services.distribute_session(session, seed=5)
    anahtarlar = set(session.distribution_params)
    assert not {a for a in anahtarlar if "gender" in a or "gap" in a or "extra" in a}


# ---------------------------------------------------------------------------
# Motor sürümü
# ---------------------------------------------------------------------------
def _r8_metni(session: ExamSession) -> str:
    pdf = services.render_session_report(session, "r8").content
    metin = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)
    return " ".join(metin.split())


@pytest.mark.django_db
def test_motor_surumu_kayda_ve_r8e_yazilir() -> None:
    session = dagitilmis_oturum()
    assert session.distribution_params["engine_version"] == engine.ENGINE_VERSION
    assert f"Dağıtım yöntemi sürümü {engine.ENGINE_VERSION}" in _r8_metni(session)


@pytest.mark.django_db
def test_surumsuz_eski_dagitim_r8de_bozulmaz() -> None:
    """Alan yoksa satır basılmaz; eski kayıttaki "kaçınılmaz oldu" satırı da ayıklanır."""
    session = dagitilmis_oturum()
    params = dict(session.distribution_params)
    params.pop("engine_version")
    params["warnings"] = [
        "S1, 1. sıra, 1. sütun: aynı sınava giren iki öğrencinin aynı sıraya oturması "
        + engine.LEGACY_DESK_CONFLICT_WARNING_TAIL
    ]
    session.distribution_params = params
    session.save(update_fields=["distribution_params"])
    metin = _r8_metni(session)
    assert "Dağıtım yöntemi sürümü" not in metin
    assert "kaçınılmaz oldu" not in metin


# ---------------------------------------------------------------------------
# Girdi sırası ve harman (karar 2): plan girdi sırasını taşımaz, her dağıtımda harman
# ---------------------------------------------------------------------------
def _girdi_iki_sinav() -> tuple[list[Participant], list[engine.RoomSeats]]:
    katilimcilar = _katilimcilar(random.Random(601), [80, 80])  # noqa: S311
    return katilimcilar, [_salon(i + 1) for i in range(4)]


def _girdi_kiz_erkek() -> tuple[list[Participant], list[engine.RoomSeats]]:
    rng = random.Random(602)  # noqa: S311 — test senaryosu üretimi
    return _bagimsiz(_katilimcilar(rng, [64, 64, 20]), rng), [_salon(i + 1) for i in range(4)]


def _girdi_uclu() -> tuple[list[Participant], list[engine.RoomSeats]]:
    katilimcilar = _katilimcilar(random.Random(603), [50, 40, 30])  # noqa: S311
    return katilimcilar, [_salon(1), _salon(2, tip=DeskType.TRIPLE), _salon(3, 3, 4)]


@pytest.mark.parametrize("kurulum", [_girdi_iki_sinav, _girdi_kiz_erkek, _girdi_uclu])
@pytest.mark.parametrize("dagit", [False, True])
def test_girdi_sirasi_plani_degistirmez(
    kurulum: Callable[[], tuple[list[Participant], list[engine.RoomSeats]]], dagit: bool
) -> None:
    """Ders satırı, öğrenci, salon ve sabit yerleşim sırası değişince aynı numara aynı plan."""
    rng = random.Random(604)  # noqa: S311 — test senaryosu üretimi
    katilimcilar, salonlar = kurulum()
    # Sabitler aynı salonda: sıralarının etkisi ancak aynı salonun listesinde görünür.
    sabitler = [
        engine.Placement(participant=kisi, room_id=salonlar[0].room_id, seat=salonlar[0].seats[i])
        for i, kisi in enumerate(katilimcilar[:3])
    ]
    kalan = katilimcilar[3:]
    ters_ders = sorted(kalan, key=lambda p: (-p.course_id, p.student_id))
    karisik = rng.sample(kalan, len(kalan))
    beklenen = engine.distribute_butterfly(
        kalan, salonlar, seed=41, preplaced=sabitler, spread_sections=dagit
    )
    for liste, odalar, pinler in (
        (ters_ders, salonlar, sabitler),
        (karisik, salonlar[::-1], sabitler),
        (kalan, salonlar[1:] + salonlar[:1], sabitler[::-1]),
        (kalan, salonlar, sabitler[1:] + sabitler[:1]),
    ):
        sonuc = engine.distribute_butterfly(
            liste, odalar, seed=41, preplaced=pinler, spread_sections=dagit
        )
        assert _kilit_ozeti(sonuc) == _kilit_ozeti(beklenen)
        assert sonuc.warnings == beklenen.warnings


@pytest.mark.django_db
@pytest.mark.parametrize("mod", [SeparationMode.NONE, SeparationMode.DESK, SeparationMode.ROOM])
def test_servis_ders_satiri_ve_salon_sirasindan_bagimsizdir(mod: str) -> None:
    """Sihirbazda ders ya da salon başka sırayla seçilse de aynı numara aynı planı verir."""
    sube(9, "A", students=8, start_no=101)
    sube(10, "A", students=8, start_no=201)
    sube(11, "A", students=6, start_no=301)
    for i, ogrenci in enumerate(Student.objects.order_by("student_number")):
        ogrenci.gender = "KE"[i % 2]
        ogrenci.save(update_fields=["gender"])
    dersler = [
        (ders("Coğrafya", levels=[9]), 9),
        (ders("Tarih", levels=[10]), 10),
        (ders("Fizik", levels=[11]), 11),
    ]
    salonlar = [salon(f"D-20{i}").pk for i in range(1, 5)]
    # "Ön sıra" kuralı motordan ÖNCE salon listesini gezer: seçim sırası oradan da sızmasın.
    ilk = Student.objects.order_by("student_number").first()
    assert ilk is not None
    services.create_placement_rule(student_id=ilk.pk, rule_type=RuleType.FRONT_ROW)

    def _plan(gun: int, satirlar: list[tuple[Any, int]], odalar: list[int]) -> list[Any]:
        session = oturum(separation_mode=mod, exam_date=date(2026, 11, gun))
        for course, level in satirlar:
            services.add_session_course(
                session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=level
            )
        services.set_session_rooms(session, [{"room_id": pk} for pk in odalar])
        session, _sonuc, _rapor = services.distribute_session(session, seed=11)
        plan = sorted(
            SeatAssignment.objects.filter(session=session).values_list(
                "student_id", "room_id", "desk_row", "desk_col", "slot"
            )
        )
        services.revert_session_to_draft(session)  # sonraki oturum önceki koltuk görmesin
        return plan

    beklenen = _plan(16, dersler, salonlar)
    assert len(beklenen) == 22
    assert _plan(17, dersler[::-1], salonlar[::-1]) == beklenen
    assert _plan(18, dersler[1:] + dersler[:1], salonlar[2:] + salonlar[:2]) == beklenen


def _yakinlik(result: engine.DistributionResult) -> float:
    """Bağımsız sayım: salon içi aynı sınav çiftlerinin Σ 1/d² toplamı."""
    toplam = 0.0
    yerler = sorted(
        result.placements, key=lambda p: (p.room_id, p.seat.desk_row, p.seat.desk_col, p.seat.slot)
    )
    for i, a in enumerate(yerler):
        for b in yerler[i + 1 :]:
            if a.room_id != b.room_id:
                continue
            if a.participant.conflict_group == b.participant.conflict_group:
                toplam += 1.0 / ((a.seat.x - b.seat.x) ** 2 + (a.seat.y - b.seat.y) ** 2)
    return toplam


def _desen(result: engine.DistributionResult) -> dict[tuple[int, int, int, int], str]:
    """Koltuk → sınav: harmanın dokunmaması gereken şey budur, öğrenci değil."""
    return {
        (p.room_id, p.seat.desk_row, p.seat.desk_col, p.seat.slot): p.participant.conflict_group
        for p in result.placements
    }


def _sube_salon_sayimi(result: engine.DistributionResult) -> Counter[tuple[int, int, str]]:
    return Counter(
        (pl.room_id, pl.participant.class_level, pl.participant.class_section)
        for pl in result.placements
    )


def _harmani_kapat(patch: pytest.MonkeyPatch) -> None:
    patch.setattr(engine, "_blend_section_order", lambda katilimcilar, _seed: list(katilimcilar))
    patch.setattr(engine, "_blend_room_order", lambda ogrenciler, _seed, _salon: list(ogrenciler))


@pytest.mark.parametrize(
    ("mevcutlar", "salonlar", "dagit"),
    [
        ([80, 80], [(5, 4, DeskType.DOUBLE)] * 4, False),
        ([50, 45, 41], [(5, 4, DeskType.DOUBLE)] * 4, False),
        ([50, 45, 41], [(5, 4, DeskType.DOUBLE)] * 4, True),
        ([50, 35, 10], [(5, 4, DeskType.DOUBLE), (5, 4, DeskType.TRIPLE)], False),
        (
            [28, 20, 5],
            [(5, 2, DeskType.DOUBLE), (5, 4, DeskType.SINGLE), (4, 2, DeskType.DOUBLE)],
            False,
        ),
    ],
)
def test_harman_ayrisma_kapaliyken_ceza_ve_ihlali_degistirmez(
    mevcutlar: list[int],
    salonlar: list[tuple[int, int, str]],
    dagit: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Harman yalnız AYNI sınav içinde kimin nereye oturduğunu değiştirir."""
    for numara in range(6):
        katilimcilar = _katilimcilar(random.Random(700 + numara), mevcutlar)  # noqa: S311
        odalar = [_salon(i + 1, r, c, t) for i, (r, c, t) in enumerate(salonlar)]
        acik = engine.distribute_butterfly(katilimcilar, odalar, seed=numara, spread_sections=dagit)
        with monkeypatch.context() as patch:
            _harmani_kapat(patch)
            kapali = engine.distribute_butterfly(
                katilimcilar, odalar, seed=numara, spread_sections=dagit
            )
        assert _kilit_ozeti(acik) != _kilit_ozeti(kapali)  # harman gerçekten çalıştı
        assert _desen(acik) == _desen(kapali)
        assert _say(acik.placements) == _say(kapali.placements)
        assert _yakinlik(acik) == pytest.approx(_yakinlik(kapali))
        assert _sube_salon_sayimi(acik) == _sube_salon_sayimi(kapali)


def test_harman_iki_sinavli_tam_salonda_koltugu_numaraya_baglar() -> None:
    """Eskiden bu kurulumda her numara her öğrenciyi aynı koltuğa oturtuyordu (%100)."""
    katilimcilar, salonlar = _girdi_iki_sinav()
    a = engine.distribute_butterfly(katilimcilar, salonlar, seed=1)
    b = engine.distribute_butterfly(katilimcilar, salonlar, seed=2)
    yer = {pl.participant.student_id: (pl.room_id, pl.seat.seat_no) for pl in a.placements}
    ayni = sum(yer[p.participant.student_id] == (p.room_id, p.seat.seat_no) for p in b.placements)
    assert ayni < len(katilimcilar) * 0.15


def test_bolunen_subede_salon_payi_okul_no_dilimi_degildir() -> None:
    """Şube harmanı: iki salona bölünen şubede salona düşen öğrenciler numaraya bağlıdır."""
    sube_uyeleri = [_katilimci(i, "1:9", 9, "A") for i in range(1, 41)]
    oteki = [_katilimci(i, "2:10", 10, "B") for i in range(41, 81)]
    salonlar = [_salon(1), _salon(2)]

    def ilk_salondakiler(numara: int) -> set[int]:
        sonuc = engine.distribute_butterfly(sube_uyeleri + oteki, salonlar, seed=numara)
        return {
            pl.participant.student_id
            for pl in sonuc.placements
            if pl.room_id == 1 and pl.participant.class_section == "A"
        }

    a, b = ilk_salondakiler(1), ilk_salondakiler(2)
    assert len(a) == len(b) == 20
    assert a != set(range(1, 21))  # okul no sırasıyla ilk yirmi değil
    assert a != b


def test_salon_harmani_grup_dizisini_korur_grup_ici_sirayi_numaraya_baglar() -> None:
    ogrenciler = [_katilimci(i, "1:9", 9, "A") for i in range(1, 21)]
    ogrenciler += [_katilimci(i, "2:10", 10, "B") for i in range(21, 33)]

    def dizi(numara: int, salon_kimligi: int) -> list[Participant]:
        return engine._deal_order(engine._blend_room_order(list(ogrenciler), numara, salon_kimligi))

    temel = dizi(1, 1)
    assert [p.conflict_group for p in temel] == [
        p.conflict_group for p in engine._deal_order(ogrenciler)
    ]
    assert sorted(p.student_id for p in temel) == [p.student_id for p in ogrenciler]
    assert temel == dizi(1, 1)
    assert temel != dizi(2, 1)
    assert temel != dizi(1, 2)


def test_harman_her_dagitimda_her_salona_uygulanir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kapısı yoktur: doluluk, önceki koltuk ya da kipten bağımsız her dağıtımda koşar."""
    salon_cagrilari: list[tuple[int, int]] = []
    gercek = engine._blend_room_order

    def kaydet(ogrenciler: list[Participant], numara: int, kimlik: int) -> list[Participant]:
        salon_cagrilari.append((numara, kimlik))
        return gercek(ogrenciler, numara, kimlik)

    monkeypatch.setattr(engine, "_blend_room_order", kaydet)
    katilimcilar = _katilimcilar(random.Random(605), [20, 20])  # noqa: S311
    engine.distribute_butterfly(katilimcilar, [_salon(1), _salon(2)], seed=9)
    assert salon_cagrilari == [(9, 1), (9, 2)]


def _ayni_sinav_iki_sira() -> tuple[engine.RoomSeats, list[engine.Placement], engine.PrevSeats]:
    """Aynı sınavdan iki öğrenci, ikisi de önceki oturumdaki sırasında oturuyor."""
    salon_ = _salon(1, 1, 2, DeskType.SINGLE)
    birinci, ikinci = salon_.seats[0], salon_.seats[1]
    kisiler = [_katilimci(1, "1:9", 9, "A"), _katilimci(2, "1:9", 9, "A")]
    yerlesim = [
        engine.Placement(participant=kisiler[0], room_id=1, seat=birinci),
        engine.Placement(participant=kisiler[1], room_id=1, seat=ikinci),
    ]
    onceki = {
        1: (1, birinci.desk_row, birinci.desk_col),
        2: (1, ikinci.desk_row, ikinci.desk_col),
    }
    return salon_, yerlesim, onceki


def test_eski_yol_ayni_sinav_icinde_onceki_koltugu_takasla_bozar() -> None:
    salon_, yerlesim, onceki = _ayni_sinav_iki_sira()
    koltuklar = [pl.seat for pl in yerlesim]
    rng = random.Random(1)  # noqa: S311 — test senaryosu üretimi
    engine._local_search(yerlesim, room=salon_, rng=rng, prev_seats=onceki)
    assert [pl.seat for pl in yerlesim] == koltuklar[::-1]


def test_sayili_yol_ayni_sinav_icinde_onceki_koltugu_takasla_bozar() -> None:
    salon_, yerlesim, onceki = _ayni_sinav_iki_sira()
    durum = engine._RoomState(salon_, yerlesim, [], onceki)
    konum = list(durum.pos)
    engine._counted_search(durum, random.Random(1), 40)  # noqa: S311
    assert durum.pos == konum[::-1]


def test_onceki_koltuk_yoksa_ayni_sinav_takasi_yapilmaz() -> None:
    salon_, yerlesim, _onceki = _ayni_sinav_iki_sira()
    durum = engine._RoomState(salon_, yerlesim, [], None)
    konum = list(durum.pos)
    engine._counted_search(durum, random.Random(1), 40)  # noqa: S311
    assert durum.pos == konum


# ---------------------------------------------------------------------------
# Salon anahtar hedefi: tek takasın varamadığı ikili + üçlü salon uyumu
# ---------------------------------------------------------------------------
def test_anahtar_hedefi_ucu_birden_kaydirir() -> None:
    """Tek sayılı ikili salonun çözümü üçlü salondan üç öğrenci getirmektir."""
    hedefler = engine._key_targets(
        [19, 18, 30, 30], [40, 40, 60, 60], [{2: 20}, {2: 20}, {3: 20}, {3: 20}]
    )
    hedef = hedefler[0]
    assert sum(hedef) == 97
    assert all(k % 2 == 0 for k in hedef[:2])
    assert all(k % 3 == 0 for k in hedef[2:])
    assert sum(abs(a - b) for a, b in zip(hedef, [19, 18, 30, 30], strict=True)) == 6


def test_anahtar_hedefi_cozum_yoksa_bos_doner() -> None:
    assert engine._key_targets([21, 20], [40, 40], [{2: 20}, {2: 20}]) == []


def test_anahtar_hedefi_esit_kaydirmali_secenekleri_de_verir() -> None:
    """Tek hedef seçilseydi öteki yönün aynı grup takasıyla varılabildiği hiç sorulmazdı."""
    hedefler = engine._key_targets([3, 3], [6, 6], [{2: 3}, {2: 3}])
    assert hedefler[:2] == [[2, 4], [4, 2]]


def test_anahtar_hedefi_ilk_erisimin_otesini_de_arar() -> None:
    """Çözüm salon sayısını ilk kayma sınırından fazla oynatıyorsa hedef yine bulunur."""
    hedefler = engine._key_targets([10, 10], [20, 20], [{20: 1}, {20: 1}])
    assert hedefler[0] in ([0, 20], [20, 0])


def _ikili_uclu_tam(rng: random.Random) -> tuple[list[Participant], list[engine.RoomSeats]]:
    salonlar = [
        _salon(1),
        _salon(2),
        _salon(3, tip=DeskType.TRIPLE),
        _salon(4, tip=DeskType.TRIPLE),
    ]
    return _bagimsiz(_katilimcilar(rng, [67, 67, 66]), rng), salonlar


def test_ikili_uclu_tam_salonda_onay_sinira_esittir() -> None:
    """06.11.2026 ölçümü: bu kurulumda 30 numaranın 18'i tek karışık sırayla kalıyordu."""
    for numara in range(12):
        rng = random.Random(800 + numara)  # noqa: S311 — test senaryosu üretimi
        katilimcilar, salonlar = _ikili_uclu_tam(rng)
        sayilar = Counter(p.separation_key for p in katilimcilar)
        assert engine.separation_desk_gap(sayilar.values(), engine.desk_sizes(salonlar)) == 0
        sonuc = engine.distribute_butterfly(katilimcilar, salonlar, seed=numara)
        assert _say(sonuc.placements)[1] == 0


def test_anahtar_hedefi_karisik_sirayi_dusurmezse_geri_alinir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hedefe yürümek karışık sırayı düşürmezse takasın bulduğu dağılım yerinde kalır."""
    uyeler = [_katilimci(i, "1:9", 9, "A") for i in range(1, 13)]
    anahtarli = [replace(p, separation_key="K" if i < 7 else "E") for i, p in enumerate(uyeler)]
    # Tek sayılı iki salon değil, çözümsüz bir bölüşüm: 7 K + 5 E, ikişer koltuklu üç sıra.
    parcalar = [anahtarli[:6], anahtarli[6:]]
    once = [[p.student_id for p in parca] for parca in parcalar]
    # İlk anahtar "E"dir: 0 ve 5 olan sayılar yer değiştirilmek istenir, karışık sıra kalır.
    monkeypatch.setattr(engine, "_key_targets", lambda *_a: [[5, 0]])
    sonuc = engine._balance_separation(parcalar, [{2: 3}, {2: 3}])
    assert [[p.student_id for p in parca] for parca in sonuc] == once


# ---------------------------------------------------------------------------
# Şube içi tek cinsiyet: hedefe aynı grup takasıyla varılamayan kurulum
# ---------------------------------------------------------------------------
def _sube_tek_cinsiyet(katilimcilar: list[Participant], rng: random.Random) -> list[Participant]:
    """Her şube baştan sona tek anahtar: kız ya da erkek okulundan gelen şube gibi."""
    anahtar: dict[tuple[int, str], str] = {}
    out: list[Participant] = []
    for p in katilimcilar:
        sube_adi = (p.class_level, p.class_section)
        out.append(replace(p, separation_key=anahtar.setdefault(sube_adi, rng.choice("KE"))))
    return out


_TAM_KARMA = {
    "iki ikili iki üçlü": [DeskType.DOUBLE] * 2 + [DeskType.TRIPLE] * 2,
    "bir ikili üç üçlü": [DeskType.DOUBLE] + [DeskType.TRIPLE] * 3,
}


@pytest.mark.parametrize("tipler", _TAM_KARMA.values(), ids=_TAM_KARMA.keys())
@pytest.mark.parametrize("sinav", [2, 3])
def test_tek_cinsiyetli_subede_onay_sinira_esittir(tipler: list[str], sinav: int) -> None:
    """06.11.2026 ölçümü: bu kurulumlarda veri ne olursa olsun karışık sıra kalıyordu."""
    salonlar = [_salon(i + 1, tip=tip) for i, tip in enumerate(tipler)]
    koltuk = sum(len(r.seats) for r in salonlar)
    pay = [koltuk // sinav + (i < koltuk % sinav) for i in range(sinav)]
    denenen = 0
    for veri in range(10):
        rng = random.Random(4100 + veri)  # noqa: S311 — test senaryosu üretimi
        katilimcilar = _sube_tek_cinsiyet(_katilimcilar(rng, pay), rng)
        sayilar = Counter(p.separation_key for p in katilimcilar)
        if engine.separation_desk_gap(sayilar.values(), engine.desk_sizes(salonlar)):
            continue
        denenen += 1
        sonuc = engine.distribute_butterfly(katilimcilar, salonlar, seed=veri)
        assert _say(sonuc.placements)[1] == 0, veri
    assert denenen >= 5


@pytest.mark.parametrize("tipler", _TAM_KARMA.values(), ids=_TAM_KARMA.keys())
def test_kiz_erkek_etiketini_degistirmek_onayi_degistirmez(tipler: list[str]) -> None:
    """Motor anahtarın ne olduğunu bilmez: etiketler yer değiştirse de sonuç onaylanır."""
    salonlar = [_salon(i + 1, tip=tip) for i, tip in enumerate(tipler)]
    koltuk = sum(len(r.seats) for r in salonlar)
    ters = {"K": "E", "E": "K"}
    for veri in range(6):
        rng = random.Random(4200 + veri)  # noqa: S311 — test senaryosu üretimi
        katilimcilar = _sube_tek_cinsiyet(_katilimcilar(rng, [koltuk // 2, koltuk // 2]), rng)
        sayilar = Counter(p.separation_key for p in katilimcilar)
        if engine.separation_desk_gap(sayilar.values(), engine.desk_sizes(salonlar)):
            continue
        tersi = [replace(p, separation_key=ters[p.separation_key]) for p in katilimcilar]
        for girdi in (katilimcilar, tersi):
            sonuc = engine.distribute_butterfly(girdi, salonlar, seed=7)
            assert _say(sonuc.placements)[1] == 0, veri


def test_ayni_grupta_takas_kalmayinca_grup_kotasi_degisir() -> None:
    """Sınav A hep erkek, sınav B hep kız: salonun kız sayısı yalnız sınav takasıyla oynar."""
    parcalar = [
        [_kisi(i, "1", "E") for i in range(1, 4)] + [_kisi(i, "2", "K") for i in range(4, 7)],
        [_kisi(i, "1", "E") for i in range(7, 10)] + [_kisi(i, "2", "K") for i in range(10, 13)],
    ]
    olculer = [{2: 3}, {3: 2}]
    sonuc = engine._balance_separation(parcalar, olculer)
    karisik = [
        engine._room_floor(Counter((p.conflict_group, p.separation_key) for p in parca), olcu)[0][0]
        for parca, olcu in zip(sonuc, olculer, strict=True)
    ]
    assert karisik == [0, 0]
    assert sorted(p.student_id for parca in sonuc for p in parca) == list(range(1, 13))


def test_ayni_grup_takasi_yetiyorsa_grup_kotasi_degismez() -> None:
    """Grup kotası yalnız zorunlu kalınca bozulur: şube-salon düzeni boşuna dağılmaz."""
    rng = random.Random(4300)  # noqa: S311 — test senaryosu üretimi
    katilimcilar = _bagimsiz(_katilimcilar(rng, [100, 100]), rng)
    salonlar = [
        _salon(1),
        _salon(2),
        _salon(3, tip=DeskType.TRIPLE),
        _salon(4, tip=DeskType.TRIPLE),
    ]
    gercek = engine._swap_students
    gruplar: list[tuple[str, str]] = []

    def sayan(
        parcalar: list[list[Participant]],
        a: int,
        b: int,
        cikan: tuple[str, str],
        giren: tuple[str, str],
    ) -> None:
        gruplar.append((cikan[0], giren[0]))
        gercek(parcalar, a, b, cikan, giren)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(engine, "_swap_students", sayan)
        sonuc = engine.distribute_butterfly(katilimcilar, salonlar, seed=3)
    assert _say(sonuc.placements)[1] == 0
    assert gruplar
    assert all(cikan == giren for cikan, giren in gruplar)


# ---------------------------------------------------------------------------
# Sabit öğrencinin sırası: Faz 0 yanındaki koltuğu serbest saymaz
# ---------------------------------------------------------------------------
def _sira_koltuklari(room: engine.RoomSeats) -> list[list[Seat]]:
    """Salonun sıraları, her sıra kendi koltuklarıyla."""
    siralar: dict[tuple[int, int], list[Seat]] = {}
    for koltuk in room.seats:
        siralar.setdefault((koltuk.desk_row, koltuk.desk_col), []).append(koltuk)
    return [siralar[sira] for sira in sorted(siralar)]


def _sabit(koltuk: Seat, anahtar: str) -> engine.Occupant:
    return (koltuk, "1:9", anahtar)


def test_sira_kilidi_sabit_ogrencinin_anahtarini_tutar() -> None:
    oda = _salon(1, 2, 2, DeskType.TRIPLE)
    a, b, c, d = _sira_koltuklari(oda)
    kilit = engine.separation_locks(
        [oda],
        {
            1: [
                _sabit(a[0], "K"),  # iki boş koltuk K'ya bağlı
                _sabit(b[0], "E"),
                _sabit(b[1], "E"),  # bir boş koltuk E'ye bağlı
                _sabit(c[0], ""),  # joker bağlamaz
                _sabit(d[0], "K"),
                _sabit(d[1], "E"),  # zaten karışık: kilit anlamsız
            ]
        },
    )
    assert kilit == {"K": {2: 1}, "E": {1: 1}}


def test_sira_kilidi_dolu_sirayi_saymaz() -> None:
    oda = _salon(1, 1, 2)
    a, b = _sira_koltuklari(oda)
    kilit = engine.separation_locks(
        [oda], {1: [_sabit(a[0], "K"), _sabit(a[1], "K"), _sabit(b[0], "E")]}
    )
    assert kilit == {"E": {1: 1}}


@pytest.mark.parametrize(
    ("sayilar", "olculer", "kilit", "beklenen"),
    [
        ((1, 1), {1: 2}, ({1: 1}, {}), 0),  # K yanına K, kalan koltuğa E
        ((0, 2), {1: 2}, ({1: 1}, {}), 1),  # E iki koltuk ister, biri K'ya bağlı
        ((4, 1), {1: 3, 2: 1}, ({}, {1: 3}), 1),  # üç koltuk ikinciye bağlı, onda bir öğrenci
        ((1, 4), {1: 3, 2: 1}, ({1: 3}, {}), 1),  # aynı durum ters sırada
        ((3, 2), {1: 3, 2: 1}, ({1: 3}, {}), 0),
        ((3, 1), {1: 2, 2: 1}, ({1: 1}, {1: 1}), 0),  # serbest ikili sıra çoğunluğa kalır
        ((4, 0), {1: 2, 2: 1}, ({1: 1}, {1: 1}), 1),  # dört kişi, bir koltuk karşı tarafa bağlı
    ],
)
def test_ayrisma_sira_acigi_kilitli_siralari_tasimaz(
    sayilar: tuple[int, int],
    olculer: dict[int, int],
    kilit: tuple[dict[int, int], dict[int, int]],
    beklenen: int,
) -> None:
    assert engine.separation_desk_gap(sayilar, olculer, kilit) == beklenen


def test_kilit_verilmezse_acik_eski_hesaptir() -> None:
    for sayilar, olculer in (((21, 19), {2: 20}), ((20, 20), {2: 20}), ((7, 5), {3: 4})):
        assert engine.separation_desk_gap(sayilar, olculer) == engine.separation_desk_gap(
            sayilar, olculer, ({}, {})
        )


def test_salon_hedefi_kilitli_siraya_karsi_anahtari_oturtmaz() -> None:
    """Salonda hiç K öğrencisi kalmasa da K sabitinin yanına E oturursa sıra karışır."""
    hedef, bolusum = engine._room_floor({("1", "E"): 2}, {1: 2}, {"K": {1: 1}})
    assert hedef[0] == 1
    assert bolusum is not None
    assert engine._room_floor({("1", "E"): 2}, {1: 2})[0][0] == 0


def test_salon_hedefi_bolusumu_kilidi_kendi_tarafinda_tutar() -> None:
    _hedef, bolusum = engine._room_floor(
        {("1", "K"): 3, ("2", "E"): 3}, {1: 2, 2: 2}, {"K": {1: 1}, "E": {1: 1}}
    )
    assert bolusum is not None
    birinci, ikinci, sol = bolusum
    assert (birinci, ikinci) == ("E", "K")
    assert sol == {1: 1, 2: 1}


def _pinli_tam(
    tipler: list[str], pin_sayisi: int, rng: random.Random
) -> tuple[list[Participant], list[engine.RoomSeats], list[engine.Placement]]:
    """Tam dolu salonlar + kurallı öğrenciler; her sırada en çok bir sabit öğrenci."""
    salonlar = [_salon(i + 1, tip=tip) for i, tip in enumerate(tipler)]
    koltuk = sum(len(r.seats) for r in salonlar)
    pay = [koltuk // 3 + (i < koltuk % 3) for i in range(3)]
    katilimcilar = _bagimsiz(_katilimcilar(rng, pay), rng)
    secilen = rng.sample(katilimcilar, pin_sayisi)
    siralar = rng.sample(
        [(r.room_id, sira) for r in salonlar for sira in _sira_koltuklari(r)], pin_sayisi
    )
    pinler = [
        engine.Placement(participant=kisi, room_id=oda, seat=sira[0])
        for kisi, (oda, sira) in zip(secilen, siralar, strict=True)
    ]
    kimlikler = {p.student_id for p in secilen}
    return [p for p in katilimcilar if p.student_id not in kimlikler], salonlar, pinler


@pytest.mark.parametrize(
    "tipler",
    [[DeskType.DOUBLE] * 2 + [DeskType.TRIPLE] * 2, [DeskType.DOUBLE] * 4],
    ids=["iki ikili iki üçlü", "dört ikili"],
)
@pytest.mark.parametrize("pin_sayisi", [2, 6])
def test_pinli_tam_salonda_onay_sinira_esittir(tipler: list[str], pin_sayisi: int) -> None:
    """06.11.2026 ölçümü: 2 ikili + 2 üçlü tam salonda 6 pinde 30 verinin 3'ü onaylanıyordu."""
    denenen = 0
    for veri in range(10):
        rng = random.Random(4400 + veri)  # noqa: S311 — test senaryosu üretimi
        kalan, salonlar, pinler = _pinli_tam(tipler, pin_sayisi, rng)
        tum = [*kalan, *(pl.participant for pl in pinler)]
        sayilar = Counter(p.separation_key for p in tum)
        if engine.separation_desk_gap(sayilar.values(), engine.desk_sizes(salonlar)):
            continue
        denenen += 1
        sonuc = engine.distribute_butterfly(kalan, salonlar, seed=veri, preplaced=pinler)
        assert _say([*sonuc.placements, *pinler])[1] == 0, veri
    assert denenen >= 3


def _kural_koltugu(kisi: Student, oda: int, satir: int, sutun: int, slot: int = 0) -> None:
    services.create_placement_rule(
        student_id=kisi.pk,
        rule_type=RuleType.FIXED_SEAT,
        target_room_id=oda,
        target_desk_row=satir,
        target_desk_col=sutun,
        target_slot=slot,
    )


@pytest.mark.django_db
def test_sihirbaz_sabit_ogrencinin_sirasini_hesaba_katar() -> None:
    """4 kız + 4 erkek 4 sıraya sığar; üç kız üç ayrı sıraya sabitlenince sığmaz."""
    session, secili = _ayrisma_oturumu(SeparationMode.DESK)
    ogrenciler = list(Student.objects.order_by("student_number"))
    for i, ogrenci in enumerate(ogrenciler):
        ogrenci.gender = "K" if i < 4 else "E"
        ogrenci.save(update_fields=["gender"])
    assert services.session_separation_gap(session, room_ids=secili) == 0
    koltuklar = list(services._session_room_seats(session)[0].seats)
    siralar = sorted({(k.desk_row, k.desk_col) for k in koltuklar})
    for ogrenci, (satir, sutun) in zip(ogrenciler[:3], siralar, strict=False):
        _kural_koltugu(ogrenci, secili[0], satir, sutun)
    assert services.session_separation_gap(session, room_ids=secili) == 1


@pytest.mark.django_db
def test_sihirbaz_bozuk_kuralda_dusmez_sabitsiz_hesaplar() -> None:
    session, secili = _ayrisma_oturumu(SeparationMode.DESK)
    ogrenci = Student.objects.order_by("student_number").first()
    assert ogrenci is not None
    _kural_koltugu(ogrenci, secili[0], 1, 0)
    with pytest.MonkeyPatch.context() as patch:

        def bozuk(*_a: object) -> None:
            raise ValidationError("bozuk kural")

        patch.setattr(services, "_resolve_rule_pins", bozuk)
        assert services.session_separation_gap(session, room_ids=secili) == 1


# ---------------------------------------------------------------------------
# Sabit yerleşim sırası: pin listesi de girdi sırasıdır
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("anahtarli", [False, True], ids=["eski yol", "sayılı yol"])
def test_sabit_yerlesim_sirasi_plana_girmez(
    anahtarli: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pin cezası kayan nokta toplamıdır: toplama sırası değişirse plan kayabilir."""
    rng = random.Random(4500)  # noqa: S311 — test senaryosu üretimi
    salonlar = [_salon(1), _salon(2)]
    katilimcilar = _katilimcilar(rng, [38, 38])
    if anahtarli:
        katilimcilar = _bagimsiz(katilimcilar, rng)
    secilen = rng.sample(katilimcilar, 6)
    yerler = rng.sample([(r.room_id, k) for r in salonlar for k in r.seats], 6)
    pinler = [
        engine.Placement(participant=kisi, room_id=oda, seat=koltuk)
        for kisi, (oda, koltuk) in zip(secilen, yerler, strict=True)
    ]
    kalan = [p for p in katilimcilar if p not in secilen]
    gorulen: list[list[int]] = []
    gercek = {ad: getattr(engine, ad) for ad in ("_constructive_fill", "_counted_fill")}

    def izle(ad: str) -> Callable[..., list[engine.Placement]]:
        def sarmal(*a: Any, **k: Any) -> list[engine.Placement]:
            gorulen.append([koltuk.seat_no for koltuk, _g, _a in k["fixed"]])
            return cast(list[engine.Placement], gercek[ad](*a, **k))

        return sarmal

    for ad in gercek:
        monkeypatch.setattr(engine, ad, izle(ad))
    beklenen = engine.distribute_butterfly(kalan, salonlar, seed=2, preplaced=pinler)
    ilk_gorulen = list(gorulen)
    for karisik in (pinler[::-1], pinler[3:] + pinler[:3]):
        gorulen.clear()
        sonuc = engine.distribute_butterfly(kalan, salonlar, seed=2, preplaced=karisik)
        assert gorulen == ilk_gorulen  # motor pinleri aynı sırayla görür
        assert _kilit_ozeti(sonuc) == _kilit_ozeti(beklenen)


# ---------------------------------------------------------------------------
# Harman ve önceki koltuk: "birebir" cümlesinin sınırı
# ---------------------------------------------------------------------------
def test_onceki_koltuk_varken_harman_deseni_degistirir_ihlali_degistirmedi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Önceki koltuk öğrenciye bağlıdır: desen birebir KALMAZ, bu sabit veride ihlal aynıdır.

    İhlal eşitliği güvence değil ölçümdür; önceki koltuk yokken birebirlik ayrı testtedir.
    """
    salonlar = [_salon(i + 1) for i in range(4)]
    desen_farki = 0
    for numara in range(6):
        katilimcilar = _katilimcilar(random.Random(4600 + numara), [50, 45, 41])  # noqa: S311
        ilk = engine.distribute_butterfly(katilimcilar, salonlar, seed=numara + 500)
        onceki = {
            pl.participant.student_id: (pl.room_id, pl.seat.desk_row, pl.seat.desk_col)
            for pl in ilk.placements
        }
        acik = engine.distribute_butterfly(
            katilimcilar, salonlar, seed=numara, previous_seats=onceki
        )
        with monkeypatch.context() as patch:
            _harmani_kapat(patch)
            kapali = engine.distribute_butterfly(
                katilimcilar, salonlar, seed=numara, previous_seats=onceki
            )
        desen_farki += _desen(acik) != _desen(kapali)
        assert _say(acik.placements) == _say(kapali.placements)
    assert desen_farki > 0


# ---------------------------------------------------------------------------
# Kılavuzdaki iki cümlenin dayanağı (ölçülen oturma geometrisi, kopya değil)
# ---------------------------------------------------------------------------
def _salon_oranlari(katilimcilar: list[Participant]) -> list[float | None]:
    """Tam dolu dört salonda `önünde aynı sınav olan öğrenci` oranı (salon başına)."""
    sonuc = engine.distribute_butterfly(katilimcilar, [_salon(i + 1) for i in range(4)], seed=1)
    salonlar: dict[int, list[tuple[int, int, str]]] = {}
    for pl in sonuc.placements:
        salonlar.setdefault(pl.room_id, []).append(
            (pl.seat.desk_row, pl.seat.desk_col, pl.participant.conflict_group)
        )
    return [services._front_same_percent(salonlar[oda]) for oda in sorted(salonlar)]


def test_tam_dolu_iki_sinavda_herkesin_onunde_ayni_sinav_esit_mevcutta_guvencelidir() -> None:
    rng = random.Random(1)  # noqa: S311 — test senaryosu üretimi
    assert _salon_oranlari(_katilimcilar(rng, [80, 80])) == [100.0] * 4
    # Mevcut eşit değilse güvence kalkar, ama her salon altına inmek zorunda da değildir:
    # kılavuz bu yüzden aralık yazmaz. Tek bir salonun düşmesi yeter.
    rng = random.Random(1)  # noqa: S311 — test senaryosu üretimi
    assert min(oran or 0.0 for oran in _salon_oranlari(_katilimcilar(rng, [110, 50]))) < 100


def test_kiz_erkek_kurali_esit_mevcutta_da_herkesin_onunde_guvencesini_kaldirir() -> None:
    """Kılavuzdaki "kız/erkek kuralı kapalıysa" koşulunun dayanağı."""
    rng = random.Random(1)  # noqa: S311 — test senaryosu üretimi
    katilimcilar = _kumeli(_katilimcilar(rng, [80, 80]), rng, 1.0)

    assert min(oran or 0.0 for oran in _salon_oranlari(katilimcilar)) < 100


def test_otomatik_dagitim_tek_sayili_mevcutta_karisik_sira_birakir() -> None:
    """Kılavuz: ihlali elle düzeltme kadar dağıtımın kendisi de bırakabilir (parite sınırı)."""
    katilimcilar = _katilimcilar(random.Random(1), [80, 80])  # noqa: S311
    kizlar = set(random.Random(1).sample(range(len(katilimcilar)), 81))  # noqa: S311
    anahtarli = [
        replace(p, separation_key="K" if i in kizlar else "E") for i, p in enumerate(katilimcilar)
    ]

    sonuc = engine.distribute_butterfly(anahtarli, [_salon(i + 1) for i in range(4)], seed=1)

    assert len(sonuc.placements) == 160
    assert _say(sonuc.placements)[1] >= 1


# ---------------------------------------------------------------------------
# Numara sözü: önceki yerler de girdidir (R8 ve ekran metni bunu söyler)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_araya_giren_sinav_ayni_numaranin_planini_degistirebilir() -> None:
    """R8'deki cümlenin dayanağı: öğrencinin son yeri numaradan ayrı bir girdidir."""
    sube(9, "A", students=14, start_no=101)
    sube(9, "B", students=10, start_no=151)
    sube(10, "A", students=14, start_no=201)
    sube(11, "A", students=12, start_no=301)
    dersler = [
        (ders(ad, levels=[d]), d) for ad, d in (("Coğrafya", 9), ("Tarih", 10), ("Fizik", 11))
    ]
    salonlar = [salon(f"D-{i}").pk for i in range(1, 11)]

    def _yeni(gun: int) -> ExamSession:
        session = oturum(exam_date=date(2026, 11, gun))
        for course, level in dersler:
            services.add_session_course(
                session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=level
            )
        services.set_session_rooms(session, [{"room_id": pk} for pk in salonlar])
        return session

    def _plan(session: ExamSession) -> list[Any]:
        return sorted(
            SeatAssignment.objects.filter(session=session).values_list(
                "student_id", "room_id", "desk_row", "desk_col", "slot"
            )
        )

    ilk, _sonuc, _rapor = services.distribute_session(_yeni(2), seed=5)
    once = _plan(ilk)
    services.distribute_session(_yeni(3), seed=6)
    ilk, _sonuc, _rapor = services.distribute_session(ilk, seed=5)
    assert _plan(ilk) != once
    assert "son yerleri de girdidir" in _r8_metni(ilk)


def test_salon_ici_kurma_sabit_ogrencinin_kilidini_gorur(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Faz 0 kilidi bilip salon içi kurma bilmezse bölüşüm sabit öğrencinin sırasını kaybeder."""
    oda, yerlesim = _ihlalli_kurulum()
    kilit = {"K": {1: 1}}
    gorulen: list[object] = []
    gercek = engine._room_floor

    def izle(
        sayim: dict[tuple[str, str], int],
        olcu: dict[int, int],
        kilitli: dict[str, dict[int, int]] | None = None,
    ) -> tuple[tuple[int, int], engine.DeskSplit | None]:
        gorulen.append(kilitli)
        return gercek(sayim, olcu, kilitli)

    monkeypatch.setattr(engine, "_room_floor", izle)
    monkeypatch.setattr(engine, "_counted_search", _arama_yok)
    engine._counted_room(
        oda,
        yerlesim,
        rng=random.Random(1),  # noqa: S311 — test senaryosu üretimi
        seed=1,
        fixed=[],
        prev_seats=None,
        hist={2: 4},
        locked=kilit,
    )
    assert gorulen == [kilit]


def test_cozumsuz_salonlarda_hedef_aramasi_bastan_kesilir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tek sayılı tam salonda kayma sınırı katlanmaz: tek soru yetmeli."""
    sorular = 0
    gercek = engine.separation_desk_gap

    def sayan(*a: Any) -> int:
        nonlocal sorular
        sorular += 1
        return gercek(*a)

    monkeypatch.setattr(engine, "separation_desk_gap", sayan)
    assert engine._key_targets([21] + [20] * 19, [40] * 20, [{2: 20}] * 20) == []
    assert sorular == 1
