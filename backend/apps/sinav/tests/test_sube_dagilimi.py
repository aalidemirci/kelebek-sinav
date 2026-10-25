"""Şube dağılımı — seçimlik "şubeler salonlara dağıtılır" kipi (25.10.2026 kullanıcı isteği).

Motor birimi `test_engine.py`de (Faz 0 üçüncü kademe), varsayılan kipin bit bit
kilidi `test_altin_kayit.py`de. Burada UÇTAN UCA sözleşme sınanır: kip okul
varsayılanından gelir, oturumda (yalnız taslakken) değiştirilir, klasik düzende
uygulanmaz, dağıtım anındaki değeri `distribution_params`a yazılır ve R8 kipin
ADINI basar (iç kod basılmaz).

KVKK: bütün adlar ve numaralar uydurmadır.
"""

from __future__ import annotations

import io
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.okul.models import SchoolConfig, SectionSpreadMode
from apps.sinav import services
from apps.sinav.models import ExamSession, LayoutMode, ParticipantType, SeatAssignment
from apps.sinav.tests.oturum_yardim import ders, oturum, salon, sube

pytestmark = pytest.mark.django_db


def _oturum(*, layout_mode: str = LayoutMode.BUTTERFLY, **kwargs: Any) -> ExamSession:
    """İki seviye × üç şube × 4 öğrenci (iki çakışma grubu), üç salon × 8 koltuk.

    Salonlar tam dolar: her salona her sınavdan 4 öğrenci düşer. "Bir arada"
    kipinde 4 kişilik şube tek salona sığar; "dağıtılır" kipinde üç salona yayılır.
    """
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


def _r8_metni(session: ExamSession) -> str:
    pdf = services.render_session_report(session, "r8").content
    sayfalar = PdfReader(io.BytesIO(pdf)).pages
    return " ".join(" ".join(s.extract_text() or "" for s in sayfalar).split())


# ===========================================================================
# Varsayılan: şubeler bir arada (bugünkü davranış)
# ===========================================================================


def test_varsayilan_bir_arada_sube_tek_salonda_kalir() -> None:
    session = _oturum()
    assert session.section_spread == SectionSpreadMode.TOGETHER

    session, _result, report = services.distribute_session(session, seed=42)

    assert report.is_valid, report.hard_violations
    params = session.distribution_params
    assert params["section_spread"] == SectionSpreadMode.TOGETHER
    assert params["rooms_per_section"]["max"] == 1


def test_okul_varsayilani_yeni_oturuma_gecer() -> None:
    """Okul bir kez seçer; açıkça verilen oturum değeri varsayılanı EZER."""
    SchoolConfig.objects.create(
        pk=SchoolConfig.SINGLETON_PK, default_section_spread=SectionSpreadMode.SPREAD
    )
    assert oturum(name="Varsayılandan Doğan").section_spread == SectionSpreadMode.SPREAD
    ozel = oturum(name="Elle Seçilen", section_spread=SectionSpreadMode.TOGETHER)
    assert ozel.section_spread == SectionSpreadMode.TOGETHER


# ===========================================================================
# Şubeler salonlara dağıtılır
# ===========================================================================


def test_dagitma_kipi_subeyi_her_salona_yayar() -> None:
    session = _oturum(section_spread=SectionSpreadMode.SPREAD)

    session, _result, report = services.distribute_session(session, seed=42)

    assert report.is_valid, report.hard_violations
    params = session.distribution_params
    assert params["section_spread"] == SectionSpreadMode.SPREAD
    # Altı şubenin her biri üç salonun üçünde de var.
    assert set(params["rooms_per_section"]["sections"].values()) == {3}


def test_ayni_numara_ayni_dagitimi_verir() -> None:
    """Determinizm sözleşmesi dağıtma kipinde de geçerlidir (CLAUDE.md §3)."""

    def koltuklar(session: ExamSession) -> list[tuple[Any, ...]]:
        return sorted(
            (a.student_id, a.room_id, a.desk_row, a.desk_col, a.slot)
            for a in SeatAssignment.objects.filter(session=session)
        )

    session = _oturum(section_spread=SectionSpreadMode.SPREAD)
    session, _r, _rep = services.distribute_session(session, seed=7)
    ilk = koltuklar(session)
    session, _r, _rep = services.distribute_session(session, seed=7)
    assert koltuklar(session) == ilk


def test_klasik_duzende_uygulanmaz() -> None:
    """Kendi dersliğinde düzeninde şube zaten kendi dersliğindedir."""
    session = oturum(layout_mode=LayoutMode.HOME_CLASSROOM, section_spread=SectionSpreadMode.SPREAD)
    assert services.effective_section_spread(session) == SectionSpreadMode.TOGETHER


def test_kip_yalniz_taslakta_degisir() -> None:
    session = _oturum()
    session, _r, _rep = services.distribute_session(session, seed=42)
    with pytest.raises(ValidationError):
        services.update_exam_session(session, section_spread=SectionSpreadMode.SPREAD)


# ===========================================================================
# R8 — kipin ADI basılır
# ===========================================================================


def test_r8_kipin_adini_basar() -> None:
    session = _oturum(section_spread=SectionSpreadMode.SPREAD)
    session, _r, _rep = services.distribute_session(session, seed=42)

    metin = _r8_metni(session)
    assert "Şube dağılımı Şubeler salonlara dağıtılır" in metin
    for yasak in ("SPREAD", "TOGETHER", "section_spread"):
        assert yasak not in metin


def test_kipsiz_eski_dagitim_bir_arada_okunur() -> None:
    """Bu sürümden önce dağıtılmış oturumun parametresinde kip yoktur; o dağıtım
    motorun o zamanki tek davranışıyla (bir arada) yapılmıştır."""
    session = _oturum()
    session, _r, _rep = services.distribute_session(session, seed=42)
    session.distribution_params.pop("section_spread")
    session.save(update_fields=["distribution_params"])

    assert "Şube dağılımı Şubeler bir arada" in _r8_metni(session)


# ===========================================================================
# API
# ===========================================================================


def test_api_oturumda_kip_secilir_gecersiz_deger_reddedilir() -> None:
    session = oturum()
    client = APIClient()
    url = f"/api/v1/exam-sessions/{session.pk}/"

    yanit = client.patch(url, {"section_spread": "SPREAD"}, format="json")
    assert yanit.status_code == 200
    assert yanit.data["section_spread"] == SectionSpreadMode.SPREAD

    assert client.patch(url, {"section_spread": "KARISIK"}, format="json").status_code == 400


def test_api_okul_varsayilani_kaydedilir() -> None:
    client = APIClient()
    url = "/api/v1/setup/school-config/"

    yanit = client.put(
        url, {"school_name": "Örnek Lisesi", "default_section_spread": "SPREAD"}, format="json"
    )
    assert yanit.status_code == 200
    assert SchoolConfig.load().default_section_spread == SectionSpreadMode.SPREAD

    gecersiz = client.put(
        url, {"school_name": "Örnek Lisesi", "default_section_spread": "X"}, format="json"
    )
    assert gecersiz.status_code == 400
