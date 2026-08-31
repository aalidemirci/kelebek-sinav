"""F7 gözetmen görevlendirme testleri — OYS T9b çekirdeğinin KS kabulü.

Kapı (tasarım §12 F7): elle atama; salon başına 1 + yedek; R6; yeniden
dağıtımda sıfırlama; ayar kapalıyken R6 üretilmez/paketlenmez (katalog
filtresi FE testinde — EvrakPaneli.test.tsx). U2/TB4: oto-atama YOK —
muafiyet ve aynı-pencere çakışması elle atamada da SERTTİR.
"""

from __future__ import annotations

import io
import zipfile
from datetime import time
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.okul.models import Personnel, SchoolConfig
from apps.sinav import services
from apps.sinav.models import (
    ExamSession,
    ExamSessionStatus,
    ProctorAssignment,
    ProctorRole,
    RuleScope,
)
from apps.sinav.tests.oturum_yardim import dagitilmis_oturum, oturum

pytestmark = pytest.mark.django_db

TURKCE_DUMAN = "ĞÜŞİÖÇ ığüşiöç"


def _ogretmen(ad: str = "Ayşe", soyad: str = "ÖĞRETMEN", **kwargs: Any) -> Personnel:
    hoca: Personnel = Personnel.objects.create(first_name=ad, last_name=soyad, **kwargs)
    return hoca


def _gozetmenli_oturum(**kwargs: Any) -> ExamSession:
    return dagitilmis_oturum(proctors_enabled=True, **kwargs)


def _kabuk(**kwargs: Any) -> ExamSession:
    """Yerleşimsiz DAĞITILDI kabuğu — guard sırası yerleşimden ÖNCE işleyen
    denetimler (modül kapalı, pencere çakışması, R6 ön koşulu) için yeterli;
    sube/salon tekliklerine dokunmadan aynı testte ikinci oturum kurar."""
    session = oturum(**kwargs)
    session.status = ExamSessionStatus.DISTRIBUTED
    session.save(update_fields=["status"])
    return session


def _salon_id(session: ExamSession) -> int:
    from apps.sinav.models import SeatAssignment

    room_id = (
        SeatAssignment.objects.filter(session=session)
        .values_list("room_id", flat=True)
        .distinct()
        .first()
    )
    assert room_id is not None
    return int(room_id)


# ===========================================================================
# Elle atama kuralları (U2)
# ===========================================================================


def test_assign_proctor_ve_yedek() -> None:
    session = _gozetmenli_oturum()
    hoca = _ogretmen()
    yedek_hoca = _ogretmen("Mehmet", "YEDEK")
    room_id = _salon_id(session)

    atama = services.assign_proctor(session, teacher_id=hoca.pk, room_id=room_id)
    assert atama.role == ProctorRole.PROCTOR
    assert atama.teacher_name == "Ayşe ÖĞRETMEN"  # snapshot (şifreli alan çözülür)
    assert atama.acknowledged is False

    yedek = services.assign_proctor(session, teacher_id=yedek_hoca.pk, role=ProctorRole.RESERVE)
    assert yedek.room_id is None

    # Salon başına TAM 1 gözetmen; aynı öğretmene ikinci görev yok.
    ucuncu = _ogretmen("Ali", "ÜÇÜNCÜ")
    with pytest.raises(ValidationError, match="zaten bir gözetmen var"):
        services.assign_proctor(session, teacher_id=ucuncu.pk, room_id=room_id)
    with pytest.raises(ValidationError, match="zaten görevli"):
        services.assign_proctor(session, teacher_id=hoca.pk, role=ProctorRole.RESERVE)
    # Yedek salona bağlanmaz; gözetmen salonsuz olamaz.
    with pytest.raises(ValidationError, match="salona bağlanmaz"):
        services.assign_proctor(
            session, teacher_id=ucuncu.pk, role=ProctorRole.RESERVE, room_id=room_id
        )
    with pytest.raises(ValidationError, match="salon seçin"):
        services.assign_proctor(session, teacher_id=ucuncu.pk)
    with pytest.raises(ValidationError, match="yerleşiminde kullanılmıyor"):
        services.assign_proctor(session, teacher_id=ucuncu.pk, room_id=999999)


def test_assign_kapali_modul_ve_durum_kapisi() -> None:
    kapali = _kabuk(name="Kapalı Oturum")  # proctors_enabled=False
    hoca = _ogretmen()
    with pytest.raises(ValidationError, match="kapalı"):
        services.assign_proctor(kapali, teacher_id=hoca.pk, room_id=1)

    onayli = _gozetmenli_oturum(name="Onaylı Oturum")
    room_id = _salon_id(onayli)
    services.approve_session(onayli, approved_by_name="Örnek MÜDÜR")
    with pytest.raises(ValidationError, match="dağıtılmış"):
        services.assign_proctor(onayli, teacher_id=hoca.pk, room_id=room_id)


def test_muafiyet_serttir_ve_kalici_kapsam() -> None:
    session = _gozetmenli_oturum()
    hoca = _ogretmen()
    services.create_proctor_exemption(teacher_id=hoca.pk)  # kalıcı
    with pytest.raises(ValidationError, match="muaf"):
        services.assign_proctor(session, teacher_id=hoca.pk, room_id=_salon_id(session))
    # Aynı kapsamda ikinci muafiyet reddedilir.
    with pytest.raises(ValidationError, match="zaten canlı"):
        services.create_proctor_exemption(teacher_id=hoca.pk)
    # Oturum kapsamı oturum ister; onaylı oturuma eklenemez.
    with pytest.raises(ValidationError, match="Oturum kapsamı"):
        services.create_proctor_exemption(teacher_id=hoca.pk, scope=RuleScope.SESSION)


def test_ayni_pencere_cakismasi_serttir() -> None:
    """Aynı tarihte zaman penceresi çakışan başka oturumdaki görevli atanamaz."""
    session1 = _gozetmenli_oturum()
    hoca = _ogretmen()
    services.assign_proctor(session1, teacher_id=hoca.pk, room_id=_salon_id(session1))

    # Aynı gün, saat penceresi kesişen ikinci oturum (09:00 + 60 dk ∩ 09:30).
    # Çakışma denetimi salon çözümünden ÖNCE işler — kabuk oturum yeterli.
    session2 = _kabuk(name="İkinci Oturum", start_time=time(9, 30), proctors_enabled=True)
    with pytest.raises(ValidationError, match="çakışan başka oturumda"):
        services.assign_proctor(session2, teacher_id=hoca.pk, room_id=1)
    # Kesişmeyen pencere (11:00) serbest — YEDEK ataması salon istemez.
    session3 = _kabuk(name="Üçüncü Oturum", start_time=time(11, 0), proctors_enabled=True)
    atama = services.assign_proctor(session3, teacher_id=hoca.pk, role=ProctorRole.RESERVE)
    assert atama.pk is not None


def test_tebellug_akisi() -> None:
    session = _gozetmenli_oturum()
    hoca = _ogretmen()
    atama = services.assign_proctor(session, teacher_id=hoca.pk, room_id=_salon_id(session))

    atama = services.acknowledge_proctor(atama)
    assert atama.acknowledged is True and atama.acknowledged_at is not None
    with pytest.raises(ValidationError, match="zaten tebellüğ"):
        services.acknowledge_proctor(atama)

    # Onaydan SONRA da işlenebilir; arşivde kapalı.
    hoca2 = _ogretmen("Kemal", "SONRADAN")
    atama2 = services.assign_proctor(session, teacher_id=hoca2.pk, role=ProctorRole.RESERVE)
    services.approve_session(session, approved_by_name="Örnek MÜDÜR")
    atama2 = services.acknowledge_proctor(atama2)
    assert atama2.acknowledged is True
    services.archive_session(session)
    atama3 = ProctorAssignment.objects.get(pk=atama.pk)
    atama3.acknowledged = False
    atama3.save(update_fields=["acknowledged"])
    with pytest.raises(ValidationError, match="dağıtılmış veya onaylı"):
        services.acknowledge_proctor(atama3)


def test_yeniden_dagitim_gorevlendirmeleri_sifirlar() -> None:
    """F7 kapısı: yeniden dağıtım atamaları soft-siler ve uyarı üretir."""
    session = _gozetmenli_oturum()
    hoca = _ogretmen()
    services.assign_proctor(session, teacher_id=hoca.pk, room_id=_salon_id(session))
    assert ProctorAssignment.objects.filter(session=session).count() == 1

    _session, result, _report = services.distribute_session(session, seed=99)
    assert ProctorAssignment.objects.filter(session=session).count() == 0
    assert any("sıfırlandı" in w for w in result.warnings)


def test_proctor_candidates_bayraklari() -> None:
    session = _gozetmenli_oturum()
    gorevli = _ogretmen("Görevli", "HOCA")
    muaf = _ogretmen("Muaf", "HOCA")
    _ogretmen("Pasif", "HOCA", is_active=False)  # havuza girmemeli
    bos = _ogretmen("Boşta", "HOCA")
    services.assign_proctor(session, teacher_id=gorevli.pk, room_id=_salon_id(session))
    services.create_proctor_exemption(teacher_id=muaf.pk)

    adaylar = {c["teacher_name"]: c for c in services.proctor_candidates(session)}
    assert "Pasif HOCA" not in adaylar  # havuz = aktif personel
    assert adaylar["Görevli HOCA"]["is_assigned"] is True
    assert adaylar["Muaf HOCA"]["is_exempt"] is True
    assert adaylar["Boşta HOCA"] == {
        "teacher_id": bos.pk,
        "teacher_name": "Boşta HOCA",
        "is_exempt": False,
        "is_busy": False,
        "is_assigned": False,
    }


# ===========================================================================
# R6 + ZIP + R9 (K2 kapısının backend yarısı)
# ===========================================================================


def _atamali_oturum() -> tuple[ExamSession, Personnel]:
    SchoolConfig.objects.create(
        pk=SchoolConfig.SINGLETON_PK, school_name=f"{TURKCE_DUMAN} Anadolu Lisesi"
    )
    session = _gozetmenli_oturum()
    hoca = _ogretmen("Şükrü", "ĞÜVENÇ")
    services.assign_proctor(session, teacher_id=hoca.pk, room_id=_salon_id(session))
    services.assign_proctor(
        session, teacher_id=_ogretmen("Yedek", "İĞNECİ").pk, role=ProctorRole.RESERVE
    )
    return session, hoca


def test_r6_uretimi_ve_tr_duman() -> None:
    session, _hoca = _atamali_oturum()
    rf = services.render_session_report(session, "r6")
    assert rf.filename == f"r6_gozetmen_gorevlendirme_oturum_{session.pk}.pdf"
    text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(rf.content)).pages)
    assert "Şükrü ĞÜVENÇ" in text and "Yedek İĞNECİ" in text
    assert "Yedek" in text  # rol etiketi; yedek salonsuz satırda
    eksik = [h for h in TURKCE_DUMAN if h != " " and h not in text]
    assert not eksik, f"R6'da Türkçe glif kaybı: {eksik}"


def test_r6_zip_kosulu_ve_r1_gorevli_adi() -> None:
    session, hoca = _atamali_oturum()
    # ZIP artık r6 içerir (gözetmen açık + görevlendirme var).
    with zipfile.ZipFile(io.BytesIO(services.render_session_reports_zip(session).content)) as zf:
        assert f"r6_gozetmen_gorevlendirme_oturum_{session.pk}.pdf" in zf.namelist()
    # Gözetmen adı SALON EVRAKININ künyesinde basılı gelir: eski R9 teslim
    # tutanağının işi 30.08.2026 sadeleştirmesinde birleşik R1'e taşındı.
    r1_text = "\n".join(
        p.extract_text() or ""
        for p in PdfReader(io.BytesIO(services.render_session_report(session, "r1").content)).pages
    )
    assert hoca.get_full_name() in r1_text


def test_r6_kapali_ve_atamasiz_reddedilir() -> None:
    SchoolConfig.objects.create(pk=SchoolConfig.SINGLETON_PK, school_name="Örnek AL")
    kapali = _kabuk(name="Kapalı Oturum")
    with pytest.raises(ValidationError, match="kapalı"):
        services.render_session_report(kapali, "r6")
    acik = _gozetmenli_oturum(name="Atamasız Oturum")
    with pytest.raises(ValidationError, match="Görevlendirme yapılmamış"):
        services.render_session_report(acik, "r6")
    # Atamasız açık oturumun ZIP'inde r6 sessizce yer almaz.
    with zipfile.ZipFile(io.BytesIO(services.render_session_reports_zip(acik).content)) as zf:
        assert not any("r6_" in ad for ad in zf.namelist())


# ===========================================================================
# API uçları (duman)
# ===========================================================================


def test_api_gozetmen_akisi() -> None:
    session = _gozetmenli_oturum()
    hoca = _ogretmen()
    room_id = _salon_id(session)
    client = APIClient()

    bos_liste = client.get(f"/api/v1/exam-sessions/{session.pk}/proctors/")
    assert bos_liste.status_code == 200
    assert bos_liste.data["proctors_enabled"] is True and bos_liste.data["assignments"] == []

    olustur = client.post(
        f"/api/v1/exam-sessions/{session.pk}/proctors/",
        {"teacher_id": hoca.pk, "room_id": room_id},
        format="json",
    )
    assert olustur.status_code == 201
    atama_id = olustur.data["id"]
    assert olustur.data["teacher_name"] == "Ayşe ÖĞRETMEN"

    adaylar = client.get(f"/api/v1/exam-sessions/{session.pk}/proctor-candidates/")
    assert adaylar.status_code == 200
    assert adaylar.data["candidates"][0]["is_assigned"] is True

    tebellug = client.post(f"/api/v1/proctor-assignments/{atama_id}/acknowledge/")
    assert tebellug.status_code == 200 and tebellug.data["acknowledged"] is True

    muafiyet = client.post(
        "/api/v1/proctor-exemptions/",
        {"teacher_id": _ogretmen("Muaf", "HOCA").pk, "scope": "PERMANENT"},
        format="json",
    )
    assert muafiyet.status_code == 201
    listesi = client.get(f"/api/v1/proctor-exemptions/?session={session.pk}")
    assert listesi.status_code == 200 and listesi.data["count"] == 1
    assert client.delete(f"/api/v1/proctor-exemptions/{muafiyet.data['id']}/").status_code == 204

    assert client.delete(f"/api/v1/proctor-assignments/{atama_id}/").status_code == 204
    assert ProctorAssignment.objects.filter(session=session).count() == 0
