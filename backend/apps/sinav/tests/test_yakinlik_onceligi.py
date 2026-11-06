"""Yakınlık önceliği — seçimlik "en yakın komşular öncelikli" kipi (06.11.2026 kullanıcı kararı).

Kip, birinci halka ağırlığını yalnız önündeki sıraya, iç çapraza ve koridor karşısına
verir. Yön sıralaması sınırlı kanıta, ağırlığın sayısı varsayıma dayanır; bu testler
kipin bir sonuç sağladığını değil SÖZLEŞMESİNİ sınar: varsayılan kapalıdır ve plan
değişmez, katı dağıtımda ve klasik düzende etkisizdir, iki arama yolu aynı ölçüyü
kullanır, doğrulayıcı ölçüsü kipten bağımsızdır, R8 kipin ADINI basar.

KVKK: bütün adlar ve numaralar uydurmadır.
"""

from __future__ import annotations

import io
import math
import random
import sys
from dataclasses import dataclass, replace
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.okul.models import ProximityMode, SchoolConfig, SectionSpreadMode, SeparationMode
from apps.sinav import engine, services
from apps.sinav.layout import Seat, numbered_seats, validate_layout_plan
from apps.sinav.management.commands import evrak_ornek
from apps.sinav.models import (
    DeskType,
    ExamSession,
    LayoutMode,
    NumberingScheme,
    ParticipantType,
    SeatAssignment,
)
from apps.sinav.participants import Participant
from apps.sinav.tests.oturum_yardim import ders, oturum, salon, sube
from apps.sinav.tests.test_ayrisma import _cinsiyet_ata
from apps.sinav.tests.test_ayrisma import _oturum as ayrisma_oturumu


def _salon(room_id: int = 1, rows: int = 5, cols: int = 4) -> engine.RoomSeats:
    plan = validate_layout_plan(
        {
            "grid": {"rows": rows, "cols": cols},
            "desks": [
                {"row": r, "col": c, "type": DeskType.DOUBLE}
                for r in range(rows)
                for c in range(cols)
            ],
            "furniture": [],
        }
    )
    return engine.RoomSeats(
        room_id=room_id, seats=tuple(numbered_seats(plan, NumberingScheme.S_PATTERN))
    )


def _katilimcilar(mevcutlar: list[int], *, anahtarli: bool = False) -> list[Participant]:
    """Her grup bir sınav; `anahtarli` iki ayrışma anahtarı verir (sayılı yol açılır)."""
    out: list[Participant] = []
    sid = 0
    for grup, mevcut in enumerate(mevcutlar, start=1):
        for _ in range(mevcut):
            sid += 1
            out.append(
                Participant(
                    student_id=sid,
                    full_name=f"Öğrenci {sid}",
                    student_number=str(1000 + sid),
                    class_level=9,
                    class_section="ABCD"[grup % 4],
                    course_id=grup,
                    course_name=f"Ders {grup}",
                    conflict_group=f"{grup}:9",
                )
            )
    if anahtarli:
        rng = random.Random(7)  # noqa: S311 — kripto değil; sentetik veri
        out = [replace(p, separation_key=rng.choice("KE")) for p in out]
    return out


def _imza(sonuc: engine.DistributionResult) -> list[tuple[int, int, int, int, int]]:
    return sorted(
        (p.participant.student_id, p.room_id, p.seat.desk_row, p.seat.desk_col, p.seat.slot)
        for p in sonuc.placements
    )


def _en_yakin_cift(sonuc: engine.DistributionResult) -> int:
    """Aynı sınavdan, kipin ağırlık verdiği en yakın komşu çift sayısı (aynı sıra hariç)."""
    uyeler = sonuc.placements
    return sum(
        1
        for i, a in enumerate(uyeler)
        for b in uyeler[i + 1 :]
        if a.room_id == b.room_id
        and a.participant.conflict_group == b.participant.conflict_group
        and engine._closest_neighbour(a.seat, b.seat)
    )


def _ayni_sira_ihlali(sonuc: engine.DistributionResult) -> int:
    uyeler = sonuc.placements
    return sum(
        1
        for i, a in enumerate(uyeler)
        for b in uyeler[i + 1 :]
        if a.room_id == b.room_id
        and a.participant.conflict_group == b.participant.conflict_group
        and (a.seat.desk_row, a.seat.desk_col) == (b.seat.desk_row, b.seat.desk_col)
    )


# ===========================================================================
# Ceza: hangi çift ağırlık alır
# ===========================================================================


def _koltuk(row: int, col: int, slot: int) -> Seat:
    """İkili sıra koltuğu: `numbered_seats` ile aynı x (sütun + yarım sıra payı)."""
    return Seat(
        desk_row=row,
        desk_col=col,
        desk_type=DeskType.DOUBLE,
        slot=slot,
        seat_no=0,
        x=col + (slot - 0.5) / 2,
        y=float(row),
    )


@pytest.mark.parametrize(
    ("ad", "karsi", "agirlikli"),
    [
        ("tam ön", _koltuk(1, 1, 0), True),
        ("iç çapraz", _koltuk(1, 1, 1), True),
        ("koridor karşısı", _koltuk(2, 0, 1), True),
        ("koridor uzak koltuk", _koltuk(2, 0, 0), False),
        ("koridor çaprazı", _koltuk(1, 0, 1), False),
        ("uzak köşegen", _koltuk(1, 2, 1), False),
    ],
)
def test_agirlik_yalniz_en_yakin_komsuya_gider(ad: str, karsi: Seat, agirlikli: bool) -> None:
    koltuk = _koltuk(2, 1, 0)
    odak = (0.0, 0.0)
    acik = engine._pair_penalty(koltuk, karsi, odak, True)
    kapali = engine._pair_penalty(koltuk, karsi, odak)

    d2 = (koltuk.x - karsi.x) ** 2 + (koltuk.y - karsi.y) ** 2
    assert kapali[0] == 1.0 / d2 + engine._FIRST_RING_WEIGHT, ad
    assert acik[0] == (kapali[0] if agirlikli else 1.0 / d2), ad
    # İkincil (masaya uzaklık) kipten bağımsızdır: yalnız birincil daralır.
    assert acik[1] == kapali[1], ad


def _yan_yana(sol: DeskType, sag: DeskType) -> tuple[list[Seat], list[Seat]]:
    """Aynı satırda iki bitişik sıranın koltukları, gerçek numaralandırmanın x'leriyle."""
    plan = validate_layout_plan(
        {
            "grid": {"rows": 1, "cols": 2},
            "desks": [{"row": 0, "col": 0, "type": sol}, {"row": 0, "col": 1, "type": sag}],
            "furniture": [],
        }
    )
    koltuklar = numbered_seats(plan, NumberingScheme.S_PATTERN)
    return (
        sorted((k for k in koltuklar if k.desk_col == 0), key=lambda k: k.x),
        sorted((k for k in koltuklar if k.desk_col == 1), key=lambda k: k.x),
    )


@pytest.mark.parametrize(
    ("sol", "sag", "agirlikli"),
    [
        (DeskType.DOUBLE, DeskType.DOUBLE, True),
        (DeskType.TRIPLE, DeskType.TRIPLE, True),
        (DeskType.DOUBLE, DeskType.TRIPLE, True),
        (DeskType.TRIPLE, DeskType.DOUBLE, True),
        (DeskType.SINGLE, DeskType.DOUBLE, False),
        (DeskType.DOUBLE, DeskType.SINGLE, False),
        (DeskType.SINGLE, DeskType.TRIPLE, False),
        (DeskType.SINGLE, DeskType.SINGLE, False),
    ],
)
def test_koridor_karsisi_ikili_ve_uclu_sirada_agirlik_alir_tek_kisilikte_almaz(
    sol: DeskType, sag: DeskType, agirlikli: bool
) -> None:
    """Kullanıcı metni "ikili ve üçlü sıralarda" der: sıra türü başına kilit.

    Yalnız koridora bakan iki koltuk ağırlık alır; öteki bütün çiftler eşiğin dışındadır.
    """
    sol_koltuklar, sag_koltuklar = _yan_yana(sol, sag)
    assert engine._closest_neighbour(sol_koltuklar[-1], sag_koltuklar[0]) is agirlikli
    uzak_ciftler = [
        (a, b)
        for a in sol_koltuklar
        for b in sag_koltuklar
        if (a, b) != (sol_koltuklar[-1], sag_koltuklar[0])
    ]
    assert not any(engine._closest_neighbour(a, b) for a, b in uzak_ciftler)


def test_ayni_sira_ve_uzak_cift_kipten_etkilenmez() -> None:
    odak = (0.0, 0.0)
    assert math.isinf(engine._pair_penalty(_koltuk(1, 1, 0), _koltuk(1, 1, 1), odak, True)[0])
    uzak = _koltuk(4, 3, 0)
    assert engine._pair_penalty(_koltuk(0, 0, 0), uzak, odak, True) == engine._pair_penalty(
        _koltuk(0, 0, 0), uzak, odak
    )


def test_sayili_yolun_ceza_matrisi_ayni_olcuyu_kullanir() -> None:
    oda = _salon(rows=3, cols=3)
    yerlesim = [
        engine.Placement(participant=p, room_id=1, seat=koltuk)
        for p, koltuk in zip(_katilimcilar([6]), oda.seats, strict=False)
    ]
    durum = engine._RoomState(oda, yerlesim, [], None, True)
    for a, sol in enumerate(durum.seats):
        for b, sag in enumerate(durum.seats):
            if durum.desk[a] != durum.desk[b]:
                assert durum.pen[a][b] == engine._pair_penalty(sol, sag, oda.focus, True)[0]


# ===========================================================================
# Motor: kapalıyken değişmez, açıkken iki yol da uygular, katıda etkisizdir
# ===========================================================================

_YOLLAR = [False, True]


@pytest.mark.parametrize("anahtarli", _YOLLAR)
def test_kapaliyken_plan_varsayilanla_bit_bit_ayni(anahtarli: bool) -> None:
    kisiler = _katilimcilar([40, 40, 40, 40], anahtarli=anahtarli)
    salonlar = [_salon(1), _salon(2), _salon(3), _salon(4)]
    assert _imza(engine.distribute_butterfly(kisiler, salonlar, seed=11)) == _imza(
        engine.distribute_butterfly(kisiler, salonlar, seed=11, narrow_ring=False)
    )


@pytest.mark.parametrize("anahtarli", _YOLLAR)
def test_acikken_en_yakin_cift_azalir_kural_ihlali_artmaz(anahtarli: bool) -> None:
    kisiler = _katilimcilar([34, 34, 34, 34], anahtarli=anahtarli)
    salonlar = [_salon(1), _salon(2), _salon(3), _salon(4)]
    kapali_yakin = acik_yakin = kapali_ihlal = acik_ihlal = 0
    for numara in range(1, 6):
        kapali = engine.distribute_butterfly(kisiler, salonlar, seed=numara)
        acik = engine.distribute_butterfly(kisiler, salonlar, seed=numara, narrow_ring=True)
        kapali_yakin += _en_yakin_cift(kapali)
        acik_yakin += _en_yakin_cift(acik)
        kapali_ihlal += _ayni_sira_ihlali(kapali)
        acik_ihlal += _ayni_sira_ihlali(acik)
    assert acik_yakin < kapali_yakin
    assert acik_ihlal <= kapali_ihlal


@pytest.mark.parametrize("anahtarli", _YOLLAR)
def test_ayni_numara_ve_kip_ayni_plani_verir(anahtarli: bool) -> None:
    kisiler = _katilimcilar([30, 30, 30], anahtarli=anahtarli)
    salonlar = [_salon(1), _salon(2), _salon(3)]
    ilk = engine.distribute_butterfly(kisiler, salonlar, seed=5, narrow_ring=True)
    ikinci = engine.distribute_butterfly(kisiler, salonlar, seed=5, narrow_ring=True)
    assert _imza(ilk) == _imza(ikinci)


@pytest.mark.parametrize("anahtarli", _YOLLAR)
def test_kati_dagitimda_kip_etkisizdir(anahtarli: bool) -> None:
    kisiler = _katilimcilar([30, 30, 30, 30], anahtarli=anahtarli)
    salonlar = [_salon(1), _salon(2), _salon(3), _salon(4)]
    for numara in (1, 2, 3):
        assert _imza(
            engine.distribute_butterfly(
                kisiler, salonlar, seed=numara, strict=True, narrow_ring=True
            )
        ) == _imza(engine.distribute_butterfly(kisiler, salonlar, seed=numara, strict=True))


def _kurucu_cagrisi_kipsiz(monkeypatch: pytest.MonkeyPatch, *, anahtarli: bool) -> None:
    """Kurucu fazı kipsiz koştur: arama fazı kipi alır, başlangıç yerleşimi almaz."""
    ad = "_counted_fill" if anahtarli else "_constructive_fill"
    gercek = getattr(engine, ad)

    def kipsiz(*args: Any, **kwargs: Any) -> Any:
        return gercek(*args, **{**kwargs, "narrow": False})

    monkeypatch.setattr(engine, ad, kipsiz)


@pytest.mark.parametrize("anahtarli", _YOLLAR)
def test_kip_kurucu_faza_da_gider(monkeypatch: pytest.MonkeyPatch, anahtarli: bool) -> None:
    """Kurucu faz başlangıç yerleşimini kurar; kipi almazsa plan başka çıkar."""
    kisiler = _katilimcilar([30, 30, 30, 30], anahtarli=anahtarli)
    salonlar = [_salon(1), _salon(2), _salon(3), _salon(4)]
    tam = [
        _imza(engine.distribute_butterfly(kisiler, salonlar, seed=n, narrow_ring=True))
        for n in (1, 2, 3)
    ]
    _kurucu_cagrisi_kipsiz(monkeypatch, anahtarli=anahtarli)
    eksik = [
        _imza(engine.distribute_butterfly(kisiler, salonlar, seed=n, narrow_ring=True))
        for n in (1, 2, 3)
    ]
    assert all(a != b for a, b in zip(tam, eksik, strict=True))


def _cift_cezasi_casusu(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[bool]]:
    """Ceza hesabını çağıran işleve göre, kipin gelip gelmediğini kaydeder.

    Son yerleşimin uyarı taraması sayılmaz: o yalnız sonsuz cezaya bakar, kip onu değiştirmez.
    """
    gercek = engine._pair_penalty
    gorulen: dict[str, list[bool]] = {}

    def casus(
        a_seat: Seat, b_seat: Seat, focus: tuple[float, float], narrow: bool = False
    ) -> engine.Penalty:
        if sys._getframe(2).f_code.co_name != "_desk_conflict_warnings":
            arayan = sys._getframe(1).f_code.co_name
            gorulen.setdefault(arayan, []).append(narrow)
        return gercek(a_seat, b_seat, focus, narrow)

    monkeypatch.setattr(engine, "_pair_penalty", casus)
    return gorulen


def test_eski_yolda_her_ceza_kipi_alir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kurucu ceza ve aramanın sabit öğrenci dalı: ikisi de kipi alır."""
    gorulen = _cift_cezasi_casusu(monkeypatch)
    kisiler = _katilimcilar([20, 20])
    salonlar = [_salon(1), _salon(2)]
    sabit = engine.Placement(participant=kisiler[0], room_id=1, seat=salonlar[0].seats[0])

    engine.distribute_butterfly(kisiler[1:], salonlar, seed=4, preplaced=[sabit], narrow_ring=True)

    assert {"_placement_penalty", "_student_penalty_at"} <= set(gorulen)
    assert all(all(deger) for deger in gorulen.values())


def test_sayili_yolda_her_ceza_kipi_alir(monkeypatch: pytest.MonkeyPatch) -> None:
    gorulen = _cift_cezasi_casusu(monkeypatch)
    engine.distribute_butterfly(
        _katilimcilar([20, 20], anahtarli=True),
        [_salon(1), _salon(2)],
        seed=4,
        narrow_ring=True,
    )

    assert {"_counted_fill", "__init__"} <= set(gorulen)  # kurucu faz ve `_RoomState`
    assert all(all(deger) for deger in gorulen.values())


# ===========================================================================
# Oturum sözleşmesi
# ===========================================================================


def _oturum(*, layout_mode: str = LayoutMode.BUTTERFLY, **kwargs: Any) -> ExamSession:
    """İki seviye × üç şube × 4 öğrenci, üç salon × 8 koltuk (`test_sube_dagilimi` kurulumu)."""
    for level, start in ((9, 100), (10, 200)):
        for i, harf in enumerate("ABC"):
            sube(level, harf, students=4, start_no=start + i * 10)
    course = ders("Coğrafya", levels=[9, 10])
    session = oturum(layout_mode=layout_mode, **kwargs)
    for level in (9, 10):
        services.add_session_course(
            session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=level
        )
    salonlar = [salon(f"D-20{i}") for i in range(1, 4)]
    services.set_session_rooms(session, [{"room_id": s.pk} for s in salonlar])
    return session


def _ayri_salon_oturumu(*, rooms: int) -> ExamSession:
    """Kız/erkek için ayrı salon kuralı ve yakınlık önceliği açık oturum."""
    session = ayrisma_oturumu(separation=SeparationMode.ROOM, rooms=rooms, per_level=4)
    session.proximity_mode = ProximityMode.CLOSEST
    session.save(update_fields=["proximity_mode"])
    return session


def _r8_metni(session: ExamSession) -> str:
    pdf = services.render_session_report(session, "r8").content
    sayfalar = PdfReader(io.BytesIO(pdf)).pages
    return " ".join(" ".join(s.extract_text() or "" for s in sayfalar).split())


def _motora_giden(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    gercek = engine.distribute_butterfly
    gorulen: list[bool] = []

    def casus(*args: Any, **kwargs: Any) -> engine.DistributionResult:
        gorulen.append(kwargs["narrow_ring"])
        return gercek(*args, **kwargs)

    monkeypatch.setattr(engine, "distribute_butterfly", casus)
    return gorulen


@pytest.mark.django_db
def test_varsayilan_kapalidir_ve_oturum_okul_varsayilanindan_gelir() -> None:
    assert oturum(name="Olağan").proximity_mode == ProximityMode.STANDARD

    SchoolConfig.objects.create(
        pk=SchoolConfig.SINGLETON_PK, default_proximity_mode=ProximityMode.CLOSEST
    )
    assert oturum(name="Varsayılandan").proximity_mode == ProximityMode.CLOSEST
    ozel = oturum(name="Elle Seçilen", proximity_mode=ProximityMode.STANDARD)
    assert ozel.proximity_mode == ProximityMode.STANDARD


@pytest.mark.django_db
def test_oteki_kipler_verilse_de_yakinlik_okul_varsayilanindan_gelir() -> None:
    """Üç seçim birbirinden bağımsızdır: yalnız yakınlık boş gelirse de varsayılan okunur."""
    SchoolConfig.objects.create(
        pk=SchoolConfig.SINGLETON_PK, default_proximity_mode=ProximityMode.CLOSEST
    )
    session = oturum(
        name="Yalnız Yakınlık Boş",
        separation_mode=SeparationMode.NONE,
        section_spread=SectionSpreadMode.TOGETHER,
    )
    assert session.proximity_mode == ProximityMode.CLOSEST


@pytest.mark.django_db
def test_dagitim_anindaki_kip_kaydedilir_ve_motora_gider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gorulen = _motora_giden(monkeypatch)
    session = _oturum(proximity_mode=ProximityMode.CLOSEST)
    session, _r, _rep = services.distribute_session(session, seed=42)

    assert gorulen == [True]
    assert session.distribution_params["proximity_mode"] == ProximityMode.CLOSEST


@pytest.mark.django_db
def test_kapaliyken_motora_kapali_gider(monkeypatch: pytest.MonkeyPatch) -> None:
    gorulen = _motora_giden(monkeypatch)
    session, _r, _rep = services.distribute_session(_oturum(), seed=42)

    assert gorulen == [False]
    assert session.distribution_params["proximity_mode"] == ProximityMode.STANDARD


@pytest.mark.django_db
def test_kati_dagitimda_kayit_da_kapalidir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Oturum kipi açık kalsa da yapılmayan iş R8'e yapılmış gibi yazılmaz."""
    gorulen = _motora_giden(monkeypatch)
    session = _oturum(proximity_mode=ProximityMode.CLOSEST)
    session, _r, _rep = services.distribute_session(session, seed=42, strict=True)

    assert gorulen == [False]
    assert session.distribution_params["proximity_mode"] == ProximityMode.STANDARD
    assert session.proximity_mode == ProximityMode.CLOSEST
    assert "Yakınlık önceliği Bütün komşu sıralar" in _r8_metni(session)


@pytest.mark.django_db
def test_ayri_salon_yolu_kipi_her_bolume_gecirir(monkeypatch: pytest.MonkeyPatch) -> None:
    gorulen = _motora_giden(monkeypatch)
    bolumler = [
        ("K", _salon(1)),
        ("E", _salon(2)),
    ]
    kisiler = [
        replace(p, separation_key=bolumler[p.student_id % 2][0]) for p in _katilimcilar([6, 6])
    ]
    monkeypatch.setattr(
        services,
        "_allocate_rooms_by_separation",
        lambda _pool, _rooms, _pre: {anahtar: [oda] for anahtar, oda in bolumler},
    )
    services._distribute_separate_rooms(
        kisiler,
        [oda for _a, oda in bolumler],
        seed=3,
        strict=False,
        preplaced=[],
        previous={},
        group_labels={},
        narrow_ring=True,
    )
    assert gorulen == [True, True]


@pytest.mark.django_db
@pytest.mark.parametrize(("kati", "beklenen"), [(False, [True, True]), (True, [False, False])])
def test_ayri_salonlarda_kip_servisten_iki_bolume_gider(
    monkeypatch: pytest.MonkeyPatch, kati: bool, beklenen: list[bool]
) -> None:
    """Yardımcı işlevin değil, servis yolunun sözleşmesi: seçim motora kadar ulaşır."""
    gorulen = _motora_giden(monkeypatch)
    session = _ayri_salon_oturumu(rooms=2)
    _cinsiyet_ata()

    session, _r, _rep = services.distribute_session(session, seed=5, strict=kati)

    assert gorulen == beklenen
    assert session.distribution_params["proximity_mode"] == (
        ProximityMode.STANDARD if kati else ProximityMode.CLOSEST
    )


@pytest.mark.django_db
def test_ayri_salonlarda_tek_bolumde_kip_gider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Öğrencilerin hepsi tek anahtardaysa bölüşüm atlanır; kip o dalda da gider."""
    gorulen = _motora_giden(monkeypatch)
    session = _ayri_salon_oturumu(rooms=1)
    _cinsiyet_ata("K")

    services.distribute_session(session, seed=5)

    assert gorulen == [True]


@pytest.mark.django_db
def test_klasik_duzende_etkin_kip_kapalidir() -> None:
    session = oturum(layout_mode=LayoutMode.HOME_CLASSROOM, proximity_mode=ProximityMode.CLOSEST)
    assert services.effective_proximity_mode(session, strict=False) == ProximityMode.STANDARD


@pytest.mark.django_db
def test_kip_yalniz_taslakta_degisir() -> None:
    session = _oturum()
    session, _r, _rep = services.distribute_session(session, seed=42)
    with pytest.raises(ValidationError):
        services.update_exam_session(session, proximity_mode=ProximityMode.CLOSEST)


@pytest.mark.django_db
def test_r8_kipin_adini_basar_ic_kod_basmaz() -> None:
    session = _oturum(proximity_mode=ProximityMode.CLOSEST)
    session, _r, _rep = services.distribute_session(session, seed=42)

    metin = _r8_metni(session)
    assert "Yakınlık önceliği En yakın komşular öncelikli" in metin
    assert "komşu sıra çifti sayısı artabilir." in metin
    assert "Bu sayı en yakın komşuları ayrıca göstermez" in metin
    assert "tek başına kötüleşme sayılmaz, seçimin kazanç sağladığını da göstermez" in metin
    for yasak in ("CLOSEST", "STANDARD", "proximity", "halka"):
        assert yasak not in metin


@pytest.mark.django_db
def test_kip_kapaliyken_r8_notu_basilmaz() -> None:
    session, _r, _rep = services.distribute_session(_oturum(), seed=42)

    metin = _r8_metni(session)
    assert "Yakınlık önceliği Bütün komşu sıralar" in metin
    assert "kötüleşme sayılmaz" not in metin
    assert "Kural ihlali değildir" in metin


@pytest.mark.django_db
def test_kipsiz_eski_dagitim_varsayilan_okunur() -> None:
    """Bu sürümden önceki dağıtımın parametresinde kip yoktur: bütün komşu sıralarla
    yapılmıştır, oturumun sonradan aldığı değer eski evraka geçmez."""
    session = _oturum()
    session, _r, _rep = services.distribute_session(session, seed=42)
    session.distribution_params.pop("proximity_mode")
    session.proximity_mode = ProximityMode.CLOSEST
    session.save(update_fields=["distribution_params", "proximity_mode"])

    assert "Yakınlık önceliği Bütün komşu sıralar" in _r8_metni(session)


@dataclass(frozen=True)
class _Yazi:
    metin: str
    x: float
    y: float
    renk: tuple[float, ...]


@dataclass(frozen=True)
class _Bant:
    y_ust: float
    y_alt: float


def _r8_gorunumu(session: ExamSession) -> tuple[list[_Yazi], list[_Bant]]:
    """R8'in ilk sayfasındaki yazılar (konum, dolgu rengi) ve koyu bölüm bantları.

    PDF'ten çıkan metin görünümü söylemez: açık renkli yazı beyaz kâğıtta da "metin"dir.
    Konumlar sayfa koordinatıdır (y yukarı doğru artar).
    """
    pdf = services.render_session_report(session, "r8").content
    sayfa = PdfReader(io.BytesIO(pdf)).pages[0]
    renk: list[tuple[float, ...]] = [(0.0, 0.0, 0.0)]
    son_kutu: list[tuple[float, float] | None] = [None]
    yazilar: list[_Yazi] = []
    bantlar: list[_Bant] = []

    def once(op: bytes, args: Any, cm: Any, _tm: Any) -> None:
        if op == b"rg":
            renk[0] = tuple(round(float(a), 3) for a in args)
        elif op == b"re":
            y0 = float(args[1]) * cm[3] + cm[5]
            y1 = (float(args[1]) + float(args[3])) * cm[3] + cm[5]
            son_kutu[0] = (min(y0, y1), max(y0, y1))
        elif op in (b"f", b"f*") and son_kutu[0] is not None:
            if renk[0] == _BANT_RENGI:
                bantlar.append(_Bant(y_ust=son_kutu[0][1], y_alt=son_kutu[0][0]))
            son_kutu[0] = None

    def yaz(metin: str, cm: Any, tm: Any, _font: Any, _punto: Any) -> None:
        if metin.strip():
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            yazilar.append(_Yazi(metin=metin, x=x, y=y, renk=renk[0]))

    sayfa.extract_text(visitor_operand_before=once, visitor_text=yaz)
    return yazilar, bantlar


def _hex_renk(deger: str) -> tuple[float, ...]:
    return tuple(round(int(deger[i : i + 2], 16) / 255, 3) for i in (1, 3, 5))


#: `print/_design.css`: --pr-bar (bant dolgusu) ve --pr-bar-hint (bant üstü ipucu).
_BANT_RENGI = _hex_renk("#334155")
_BANT_IPUCU_RENGI = _hex_renk("#cbd5e1")


def _bantta(yazi: _Yazi, bantlar: list[_Bant]) -> bool:
    return any(b.y_alt <= yazi.y <= b.y_ust for b in bantlar)


def _bul(yazilar: list[_Yazi], parca: str) -> _Yazi:
    return next(y for y in yazilar if parca in y.metin)


@pytest.mark.django_db
@pytest.mark.parametrize("kip", list(ProximityMode))
def test_r8_acik_renkli_ipucu_yalniz_koyu_bant_icinde_basilir(kip: ProximityMode) -> None:
    """Uzun ipucu sarınca bandın altına, beyaz kâğıda düşüyordu (06.11.2026 denetim bulgusu)."""
    session = _oturum(proximity_mode=kip)
    session, _r, _rep = services.distribute_session(session, seed=42)

    yazilar, bantlar = _r8_gorunumu(session)
    ipuclari = [y for y in yazilar if y.renk == _BANT_IPUCU_RENGI]
    assert any("Kural ihlali değildir" in y.metin for y in ipuclari)
    assert bantlar
    disarida = [y.metin for y in ipuclari if not _bantta(y, bantlar)]
    assert disarida == []


@pytest.mark.django_db
def test_r8_dagitim_numarasi_notu_koyu_renkle_okunur() -> None:
    """Motor sürümü uzattığı bu not da banttan taşıyordu; her harmanlı dağıtımda basılır."""
    session, _r, _rep = services.distribute_session(_oturum(), seed=42)

    yazilar, bantlar = _r8_gorunumu(session)
    satir = _bul(yazilar, "Aynı dağıtım numarası")
    assert not _bantta(satir, bantlar)
    assert max(satir.renk) < 0.3


@pytest.mark.django_db
def test_r8_notu_bandin_altinda_koyu_renkle_okunur() -> None:
    session = _oturum(proximity_mode=ProximityMode.CLOSEST)
    session, _r, _rep = services.distribute_session(session, seed=42)

    yazilar, bantlar = _r8_gorunumu(session)
    baslik = _bul(yazilar, "YAKINLIK ÖLÇÜLERİ")
    bant = next(b for b in bantlar if b.y_alt <= baslik.y <= b.y_ust)
    tablo = _bul(yazilar, "Komşu sıralara düşen aynı sınav çifti")
    not_satirlari = [y for y in yazilar if tablo.y < y.y < bant.y_alt]

    assert "kötüleşme sayılmaz" in " ".join(" ".join(y.metin.split()) for y in not_satirlari)
    for satir in not_satirlari:
        assert not _bantta(satir, bantlar), satir.metin
        # Koyu yazı: tek kanalı bile orta tonun altındadır (beyaz kâğıtta okunur).
        assert max(satir.renk) < 0.3, satir.metin


def test_ornek_r8_kip_satirlarini_bos_birakmaz() -> None:
    """Şablon iki satırı koşulsuz basar: örnek evrak bağlamı değerleri de vermelidir."""
    baglam = evrak_ornek.Command()._dogrulama()
    assert isinstance(baglam["params"], dict)
    assert baglam["params"]["proximity_label"] == ProximityMode.STANDARD.label
    assert baglam["params"]["section_spread_label"] == SectionSpreadMode.TOGETHER.label


@pytest.mark.django_db
@pytest.mark.parametrize("kip", list(ProximityMode))
def test_r8_komsu_sira_sayimi_koltuklardan_sayilanla_ayni(kip: ProximityMode) -> None:
    """Kip motorun iç ağırlığıdır: doğrulayıcı ve R8 her kipte BÜTÜN komşu sıraları sayar."""
    session = _oturum(proximity_mode=kip)
    session, _r, rapor = services.distribute_session(session, seed=42)

    satirlar = list(SeatAssignment.objects.filter(session=session))
    sayim = sum(
        1
        for i, a in enumerate(satirlar)
        for b in satirlar[i + 1 :]
        if a.room_id == b.room_id
        and a.conflict_group == b.conflict_group
        and (a.desk_row, a.desk_col) != (b.desk_row, b.desk_col)
        and max(abs(a.desk_row - b.desk_row), abs(a.desk_col - b.desk_col)) <= 1
    )
    assert rapor.first_ring_same_group_pairs == sayim
    assert services._validation_report_context(session, [])["first_ring_pairs"] == sayim


@pytest.mark.django_db
def test_api_oturumda_kip_secilir_gecersiz_deger_reddedilir() -> None:
    session = _oturum()
    client = APIClient()
    url = f"/api/v1/exam-sessions/{session.pk}/"

    yanit = client.patch(url, {"proximity_mode": "CLOSEST"}, format="json")
    assert yanit.status_code == 200
    assert yanit.data["proximity_mode"] == ProximityMode.CLOSEST
    assert client.patch(url, {"proximity_mode": "YAKIN"}, format="json").status_code == 400


@pytest.mark.django_db
def test_api_okul_varsayilani_kaydedilir() -> None:
    client = APIClient()
    url = "/api/v1/setup/school-config/"
    yanit = client.put(
        url, {"school_name": "Örnek Lisesi", "default_proximity_mode": "CLOSEST"}, format="json"
    )
    assert yanit.status_code == 200
    assert SchoolConfig.load().default_proximity_mode == ProximityMode.CLOSEST
    assert (
        client.put(
            url, {"school_name": "Örnek Lisesi", "default_proximity_mode": "X"}, format="json"
        ).status_code
        == 400
    )
