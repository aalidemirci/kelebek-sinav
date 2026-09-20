"""Ders akışı → zil çizelgesi testleri (20.09.2026).

Kapı: (1) varsayılan akış ESKİ sabit listeyi birebir üretir — ders saatleri
ayarlanabilir hâle gelirken mevcut okulların çizelgesi kaymamalıdır; (2) blok
düzeni ve uzun ara doğru yerde; (3) ikili eğitimde öğleden sonra oturumu
sabahın GERÇEK bitişinden türer; (4) elle düzenlenen liste doğrulanır.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from apps.okul import bell
from apps.okul.models import EducationModel, SchoolConfig
from apps.okul.services import setup as setup_service

pytestmark = pytest.mark.django_db


def _saatler(flow: bell.LessonFlow) -> list[str]:
    return [str(p["start"]) for p in bell.periods_from_flow(flow)]


# ===========================================================================
# Saf hesap (DB gerekmez)
# ===========================================================================


@pytest.mark.django_db(transaction=False)
def test_varsayilan_akis_eski_sabit_listeyi_uretir() -> None:
    """REGRESYON KİLİDİ: 08:30'dan 50'şer dakika — eski DEFAULT_BELL_SCHEDULE."""
    assert _saatler(bell.LessonFlow(lesson_count=8)) == [
        "08:30",
        "09:20",
        "10:10",
        "11:00",
        "11:50",
        "12:40",
        "13:30",
        "14:20",
    ]


def test_blok_icinde_teneffus_yok_bloklar_arasinda_var() -> None:
    """(2,2,2,2): blok içindeki ikinci ders ARA VERMEDEN başlar."""
    akis = bell.LessonFlow(
        first_lesson="08:00",
        lesson_count=8,
        lesson_minutes=40,
        break_minutes=10,
        block_sizes=(2, 2, 2, 2),
    )
    saatler = _saatler(akis)
    assert saatler[0] == "08:00" and saatler[1] == "08:40"  # blok içi: 40 dk sonra
    assert saatler[2] == "09:30"  # blok sonrası: +40 ders +10 teneffüs


def test_uzun_ara_konumuna_gore_kayar() -> None:
    """4. dersten sonra 45 dakikalık uzun ara: 5. ders o kadar gecikir."""
    kisa = bell.LessonFlow(first_lesson="08:00", lesson_count=6, block_sizes=(2, 2, 2))
    uzun = bell.LessonFlow(
        first_lesson="08:00",
        lesson_count=6,
        block_sizes=(2, 2, 2),
        long_break_after=4,
        long_break_minutes=45,
    )
    assert _saatler(kisa)[4] != _saatler(uzun)[4]
    assert _saatler(uzun)[4] == "11:35"  # 08:00 +2×40 +10 +2×40 +45


def test_uzun_ara_blok_ortasina_konamaz() -> None:
    akis = bell.LessonFlow(lesson_count=8, block_sizes=(2, 2, 2, 2), long_break_after=3)
    assert any("blok" in h for h in akis.errors())


def test_blok_toplami_ders_sayisina_esit_olmali() -> None:
    assert any("toplamı" in h for h in bell.LessonFlow(lesson_count=8, block_sizes=(2, 2)).errors())


def test_ogleden_sonra_onerisi_sabahin_gercek_bitisinden_turer() -> None:
    """Uzun ara ve bloklar hesaba girer — 'son ders + süre' kestirmesi yanlış olurdu."""
    sabah = bell.LessonFlow(
        first_lesson="08:00",
        lesson_count=8,
        lesson_minutes=40,
        break_minutes=10,
        long_break_after=4,
        long_break_minutes=45,
        block_sizes=(2, 2, 2, 2),
    )
    assert bell.flow_end_time(sabah) == "14:25"
    # +20 dk geçiş payı, beşer dakikaya yuvarlanır.
    assert bell.suggest_next_start(sabah) == "14:45"


def test_normalize_periods_artan_saat_ister() -> None:
    with pytest.raises(ValueError, match="artan sırada"):
        bell.normalize_periods(
            [{"no": 1, "start": "09:00"}, {"no": 2, "start": "08:00"}], label="Liste"
        )


def test_normalize_periods_ardisik_numara_ister() -> None:
    with pytest.raises(ValueError, match="ardışık"):
        bell.normalize_periods([{"no": 1, "start": "08:00"}, {"no": 3, "start": "09:00"}])


def test_normalize_periods_bos_saate_izin_verir() -> None:
    """Saati bilinmeyen ders saati ADIYLA durur — zaman basılmaz, satır kaybolmaz."""
    temiz = bell.normalize_periods([{"no": 1, "start": ""}, {"no": 2, "start": "09:00"}])
    assert temiz[0] == {"no": 1, "name": "1. Ders", "start": ""}
    assert temiz[1]["start"] == "09:00"


# ===========================================================================
# Ayar servisi
# ===========================================================================


def test_ayar_elle_girilen_cizelge_gunluk_ders_saatini_belirler() -> None:
    """Elle girilen çizelge kazanır: sayı ona çekilir, sınav saatleri kırpılır."""
    SchoolConfig.objects.create(
        pk=SchoolConfig.SINGLETON_PK, daily_period_count=10, exam_period_nos=[1, 9, 10]
    )
    config = setup_service.update_school_config(
        fields={
            "bell_schedule": [
                {"no": i, "name": f"{i}. Ders", "start": f"{7 + i:02d}:00"} for i in range(1, 7)
            ]
        }
    )
    assert config.daily_period_count == 6
    assert config.exam_period_nos == [1]  # 9 ve 10 artık yok


def test_ayar_bozuk_cizelgeyi_reddeder() -> None:
    with pytest.raises(ValidationError) as exc:
        setup_service.update_school_config(
            fields={"bell_schedule": [{"no": 1, "start": "yirmi dokuz"}]}
        )
    assert "bell_schedule" in exc.value.message_dict


def test_ayar_bozuk_akisi_reddeder() -> None:
    with pytest.raises(ValidationError) as exc:
        setup_service.update_school_config(fields={"bell_flow": {"lesson_minutes": 0}})
    assert "bell_flow" in exc.value.message_dict


def test_ayar_egitim_modeli_ve_ogle_cizelgesi() -> None:
    config = setup_service.update_school_config(
        fields={
            "education_model": EducationModel.DUAL,
            "afternoon_bell_schedule": [{"no": 1, "name": "1. Ders", "start": "13:00"}],
        }
    )
    assert config.education_model == EducationModel.DUAL
    assert config.afternoon_bell_schedule[0]["start"] == "13:00"


def test_ayar_gecersiz_egitim_modeli_reddedilir() -> None:
    with pytest.raises(ValidationError):
        setup_service.update_school_config(fields={"education_model": "YARIM_GUN"})
