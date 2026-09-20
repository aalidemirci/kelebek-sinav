"""Mazeret takvimi yerleştiricisi — saf birim testleri (ORM yok).

Kurallar `makeup_schedule` modül başında: öğrenci çakışması ve günlük sınır SERT,
asıl takvim sırası kesin ya da (gevşek kipte) öğrenci bazında korunur, sabitlere
dokunulmaz, üst makam sınavı sabitlenmedikçe yerleşmez.
"""

from __future__ import annotations

from datetime import date, time

from apps.sinav.makeup_schedule import (
    NO_SLOTS_LEFT,
    NOT_AUTO,
    STUDENT_LIMITS,
    PlanGroup,
    audit,
    minimum_days,
    plan_days,
    plan_slots,
    schedule,
)

PZT = date(2026, 11, 16)  # Pazartesi
SAL = date(2026, 11, 17)
CAR = date(2026, 11, 18)


def grup(
    key: int, gun: int, ogrenciler: set[int], *, saat: int = 9, level: int = 9, **kwargs: object
) -> PlanGroup:
    """Asıl sınavı Kasım'ın `gun`. günü `saat`te yapılmış sınav."""
    return PlanGroup(
        key=key,
        order=(date(2026, 11, gun), time(saat, 0)),
        students=frozenset(ogrenciler),
        level=level,
        **kwargs,  # type: ignore[arg-type]
    )


def test_gunler_hafta_sonunu_atlar() -> None:
    assert plan_days(date(2026, 11, 20), 3) == [
        date(2026, 11, 20),
        date(2026, 11, 23),
        date(2026, 11, 24),
    ]
    assert plan_days(date(2026, 11, 21), 1) == [date(2026, 11, 23)]  # Cumartesi → Pazartesi
    assert plan_slots(PZT, 1, [3, 2, 2]) == [(PZT, 2), (PZT, 3)]  # saatler tekil ve sıralı


def test_ayrik_ogrenciler_ayni_saate_konur_tek_oturum_olur() -> None:
    sonuc = schedule(
        [grup(1, 2, {1, 2}), grup(2, 3, {3}), grup(3, 4, {4, 5})],
        plan_slots(PZT, 2, [2, 3]),
        max_per_day=2,
    )
    assert set(sonuc.placements.values()) == {(PZT, 2)}
    assert sonuc.complete


def test_ayni_ogrenci_ayni_saatte_iki_sinava_girmez_ve_gunluk_sinir_asilmaz() -> None:
    sonuc = schedule(
        [grup(1, 2, {1}), grup(2, 3, {1}), grup(3, 4, {1})],
        plan_slots(PZT, 2, [2, 3, 4]),
        max_per_day=2,
    )
    # Üçüncü sınav aynı gün 4. saatte boş yer olsa da ERTESİ güne gider (günlük sınır 2).
    assert sonuc.placements == {1: (PZT, 2), 2: (PZT, 3), 3: (SAL, 2)}


def test_kesin_sira_sonraki_dersi_one_cekmez_gevsek_kip_ceker() -> None:
    gruplar = [grup(1, 2, {1}), grup(2, 3, {1}), grup(3, 4, {1}), grup(4, 5, {9})]
    slots = plan_slots(PZT, 2, [2, 3])
    kesin = schedule(gruplar, slots, max_per_day=2, strict_order=True)
    # 4. sınavın öğrencisi boşta ama asıl takvimde SONRA: 3. sınavdan önceye konmaz.
    assert kesin.placements[3] == (SAL, 2) and kesin.placements[4] == (SAL, 2)
    gevsek = schedule(gruplar, slots, max_per_day=2, strict_order=False)
    assert gevsek.placements[4] == (PZT, 2)  # boş saate öne çekildi
    assert gevsek.placements[3] == (SAL, 2)  # öğrencinin kendi sırası yine korunur


def test_asil_takvimde_ayni_saatteki_sinavlar_birbirini_itmez() -> None:
    gruplar = [grup(1, 2, {1}), grup(2, 3, {1}, saat=10), grup(3, 3, {2}, saat=10)]
    sonuc = schedule(gruplar, plan_slots(PZT, 2, [2, 3]), max_per_day=1)
    assert sonuc.placements[2] == (SAL, 2)  # öğrenci 1'in günlük sınırı doldu
    # Aynı asıl saatli 3. sınav, 2.'nin ertesi güne kaymasından ETKİLENMEZ.
    assert sonuc.placements[3] == (PZT, 2)


def test_sabit_sinava_dokunulmaz_ust_makam_sabitlenmeden_yerlesmez() -> None:
    gruplar = [
        grup(1, 2, {1}, fixed=(CAR, 5)),
        grup(2, 3, {1}),
        grup(3, 4, {7}, auto=False),
    ]
    sonuc = schedule(gruplar, plan_slots(PZT, 1, [2]), max_per_day=2)
    assert sonuc.placements == {1: (CAR, 5), 2: (PZT, 2)}
    assert sonuc.unplaced[3].reason == NOT_AUTO
    assert sonuc.complete  # üst makam sınavı "sığmadı" sayılmaz

    # Sabit sınav doluluk sayılır: aynı saate aynı öğrenci konmaz.
    dolu = schedule(
        [grup(1, 2, {1}, fixed=(PZT, 2)), grup(2, 3, {1})],
        plan_slots(PZT, 1, [2, 3]),
        max_per_day=2,
    )
    assert dolu.placements[2] == (PZT, 3)


def test_ust_makam_gunu_o_duzeye_kapalidir() -> None:
    sonuc = schedule(
        [grup(1, 2, {1}, level=10), grup(2, 3, {2}, level=9)],
        plan_slots(PZT, 2, [2]),
        max_per_day=2,
        blocked_days=frozenset({(PZT, 10)}),
    )
    assert sonuc.placements == {1: (SAL, 2), 2: (SAL, 2)}  # kesin sıra 2.'yi de taşır


def test_sigmayan_sinav_gerekcesiyle_raporlanir_ve_en_az_gun_bulunur() -> None:
    gruplar = [grup(i, i + 1, {1}) for i in range(1, 6)]  # tek öğrenci, beş sınav
    sonuc = schedule(gruplar, plan_slots(PZT, 2, [2, 3, 4]), max_per_day=2)
    assert sorted(sonuc.placements) == [1, 2, 3, 4]
    assert sonuc.unplaced[5].reason == STUDENT_LIMITS and sonuc.unplaced[5].blockers == (1,)
    assert not sonuc.complete
    assert minimum_days(gruplar, PZT, [2, 3, 4], max_per_day=2, strict_order=True) == 3
    assert minimum_days(gruplar, PZT, [2, 3, 4], max_per_day=1, strict_order=True) == 5

    bos = schedule([grup(1, 2, {1})], [], max_per_day=2)
    assert bos.unplaced[1].reason == NO_SLOTS_LEFT


def test_ayni_girdi_ayni_cikti() -> None:
    gruplar = [grup(i, 2 + (i % 4), {i % 3, 10 + i}) for i in range(1, 12)]
    slots = plan_slots(PZT, 4, [2, 3])
    ilk = schedule(gruplar, slots, max_per_day=2)
    assert schedule(list(reversed(gruplar)), slots, max_per_day=2).placements == ilk.placements


def test_denetim_cakisma_sinir_ve_sira() -> None:
    a, b, c = grup(1, 2, {1, 2}), grup(2, 3, {2}), grup(3, 4, {9})
    rapor = audit([(a, (SAL, 2)), (b, (SAL, 2)), (c, (PZT, 2))], max_per_day=1, strict_order=True)
    assert rapor.clashes == [(1, 2, (2,))]
    assert rapor.over_limit == [(2, SAL, 2)]
    # 1 ve 2 asıl takvimde 3'ten ÖNCE ama takvimde sonraya düşmüş.
    assert rapor.order_breaks == [(1, 3), (2, 3)]
    # Gevşek kipte yalnız ORTAK öğrencisi olan çiftler sıra ihlalidir — burada yok.
    gevsek = audit([(a, (SAL, 2)), (b, (SAL, 3)), (c, (PZT, 2))], max_per_day=2, strict_order=False)
    assert gevsek.order_breaks == [] and gevsek.clashes == []
