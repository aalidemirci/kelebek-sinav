"""Kalıcı sınav tedbirleri (07.10.2026) — "BEP ve tedbirler" listesi.

Kullanıcı isteği: "Özel eğitim ihtiyacı olan öğrencilerin okul numaralarını girerek
hangi tedbirlerin uygulanacağını seçebilsek (ayrı salon, ek süre, kendi sınıfında,
okuyucu desteği, yazıcı desteği vb.)". Kararlar (07.10.2026): tedbir YALNIZ idare
özetinde basılır (salon evrakına öğrenci notu yok); okuyucu/yazıcı görevlisini program
atamaz; liste gerekçeyle herkesi kapsar (BEP / engel durumu / sağlık / diğer).

Güvenceler: yer tedbiri her oturumda yerleştirme kuralı olarak uygulanır ve oturum
kuralı onu ezer; süre/destek yerleşimi değiştirmez ama çakışma denetimleri ek süreyi
hesaba katar; salon evrakında, doğrulama raporunda ve uyarı metinlerinde öğrenciyi
ayıran iz yoktur. Veri sentetiktir.
"""

from __future__ import annotations

import io
from datetime import date, time
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.okul.models import ClassSection, Student, StudentStatus
from apps.okul.services import persons
from apps.sinav import participants, services, services_individual
from apps.sinav import services_calendar as takvim
from apps.sinav.models import (
    ExamCalendarEntry,
    ExamRoom,
    ExamSession,
    IepStudent,
    IndividualQuestionDocument,
    LayoutMode,
    ParticipantType,
    RuleReason,
    RuleScope,
    RuleType,
    SeatAssignment,
    SeatStatus,
)
from apps.sinav.tests.oturum_yardim import ders, oturum, salon, sube
from apps.sinav.tests.test_booklets import PLAN_3X2_DOUBLE
from apps.sinav.tests.test_calendar import _havuzlu_takvim

pytestmark = pytest.mark.django_db


def _no(number: str) -> int:
    return int(Student.objects.get(student_number=number).pk)


def _oturum(**kwargs: Any) -> tuple[ExamSession, dict[str, ClassSection]]:
    """9/A (4) + 10/A (4), iki ders, 12 koltuklu D-201 — dağıtılmamış."""
    subeler = {
        "9A": sube(9, "A", students=4, start_no=101),
        "10A": sube(10, "A", students=4, start_no=201),
    }
    c9 = ders("Coğrafya", levels=[9])
    c10 = ders("Fizik", levels=[10])
    session = oturum(**kwargs)
    services.add_session_course(
        session, course_id=c9.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    services.add_session_course(
        session, course_id=c10.pk, participant_type=ParticipantType.LEVEL, level=10
    )
    services.set_session_rooms(session, [{"room_id": salon("D-201", plan=PLAN_3X2_DOUBLE).pk}])
    return session, subeler


def _salonlari_ayarla(session: ExamSession, *rooms: ExamRoom) -> None:
    d201 = ExamRoom.objects.get(name="D-201")
    services.set_session_rooms(session, [{"room_id": r.pk} for r in (d201, *rooms)])


def _pdf_text(pdf_bytes: bytes) -> str:
    pages = PdfReader(io.BytesIO(pdf_bytes)).pages
    return " ".join(" ".join(page.extract_text() or "" for page in pages).split())


def _koltuk(session: ExamSession, number: str) -> SeatAssignment:
    kayit: SeatAssignment = SeatAssignment.objects.get(session=session, student_id=_no(number))
    return kayit


# ===========================================================================
# Liste — doğrulama, ekleme, düzenleme, toplu ekleme
# ===========================================================================


@pytest.mark.parametrize(
    ("veri", "metin"),
    [
        ({"placement": "SEPARATE_ROOM"}, "salon seçin"),
        ({"placement": "HOME_CLASSROOM", "target_room_id": 1}, "yalnız “Ayrı salon”"),
        ({"seat_preference": "BACK"}, "ön/arka tercihi"),
        ({"placement": "FRONT_ROW", "seat_preference": "BACK"}, "ön/arka tercihi"),
        ({"solo_desk": True}, "tek başına"),
        ({"extra_minutes": 121}, "0 ile 120"),
        ({"extra_minutes": "20"}, "tam sayı"),
        ({"reason_category": "HEALTH"}, "en az bir tedbir"),
        ({"reason_category": "X"}, "Geçersiz gerekçe"),
        ({"placement": "X"}, "Geçersiz yer"),
    ],
)
def test_tedbir_dogrulamasi(veri: dict[str, Any], metin: str) -> None:
    sube(9, "A", students=1, start_no=101)
    with pytest.raises(ValidationError, match=metin) as exc:
        services_individual.add_iep_student(_no("101"), veri)
    assert "AD0" not in str(exc.value)  # hata metni ad taşımaz
    assert not IepStudent.objects.exists()


def test_pasif_salon_ayri_salon_olamaz() -> None:
    sube(9, "A", students=1, start_no=101)
    rehber = salon("Rehberlik", plan=PLAN_3X2_DOUBLE)
    ExamRoom.objects.filter(pk=rehber.pk).update(is_active=False)
    with pytest.raises(ValidationError, match="bulunamadı ya da pasif"):
        services_individual.add_iep_student(
            _no("101"), {"placement": "SEPARATE_ROOM", "target_room_id": rehber.pk}
        )


def test_tedbir_ekle_duzenle_ve_ozet_metni() -> None:
    sube(9, "A", students=1, start_no=101)
    rehber = salon("Rehberlik", plan=PLAN_3X2_DOUBLE)
    row = services_individual.add_iep_student(
        _no("101"),
        {
            "reason_category": "DISABILITY",
            "placement": "SEPARATE_ROOM",
            "target_room_id": rehber.pk,
            "seat_preference": "FRONT",
            "solo_desk": True,
            "extra_minutes": 20,
            "reader": True,
        },
    )
    assert services_individual.measure_labels(row) == [
        "Ayrı salon (Rehberlik)",
        "ön sıra",
        "sırada tek başına",
        "Ek süre 20 dk",
        "Okuyucu desteği",
    ]
    # BEP'e özgü işler yalnız BEP gerekçesine açılır.
    assert services_individual.iep_student_ids() == set()

    services_individual.update_accommodation(row, {"reason_category": "HEALTH", "scribe": True})
    row.refresh_from_db()
    # Tam değiştirme: gönderilmeyen tedbir kapanır.
    assert row.placement == "NONE" and row.target_room_id is None
    assert not row.reader and row.scribe and row.extra_minutes == 0
    assert services_individual.measure_labels(row) == ["Yazıcı desteği"]
    [satir] = services_individual.iep_list()
    assert satir["reason_label"] == "Sağlık" and satir["measures"] == ["Yazıcı desteği"]


def test_tedbirsiz_bep_satiri_eski_davranistir() -> None:
    sube(9, "A", students=1, start_no=101)
    row = services_individual.add_iep_student(_no("101"))
    assert row.reason_category == RuleReason.IEP and services_individual.measure_labels(row) == []
    assert services_individual.iep_student_ids() == {_no("101")}


def test_bepten_cikan_satirin_bireysel_dosyasi_duser() -> None:
    session, _ = _oturum()
    services.distribute_session(session, seed=7)
    row = services_individual.add_iep_student(_no("101"))
    services_individual.select_individual(session, student_id=_no("101"))
    assert IndividualQuestionDocument.objects.filter(session=session).exists()

    services_individual.update_accommodation(
        row, {"reason_category": "DISABILITY", "extra_minutes": 10}
    )

    assert not IndividualQuestionDocument.all_objects.filter(session=session).exists()


def test_okul_numarasiyla_toplu_ekleme() -> None:
    sube(9, "A", students=3, start_no=101)
    services_individual.add_iep_student(_no("101"))

    sonuc = services_individual.add_by_numbers(
        ["101", "102", "103", "103", "999"], {"reason_category": "HEALTH", "extra_minutes": 15}
    )

    assert sonuc == {"added": 2, "already": 1, "not_found": ["999"]}
    rows = services_individual.accommodation_rows()
    assert rows[_no("102")].extra_minutes == 15
    assert rows[_no("102")].reason_category == RuleReason.HEALTH
    assert rows[_no("101")].reason_category == RuleReason.IEP  # var olan satıra dokunulmaz
    with pytest.raises(ValidationError, match="En az bir okul numarası"):
        services_individual.add_by_numbers(["  "])
    with pytest.raises(ValidationError, match="en az bir tedbir"):
        services_individual.add_by_numbers(["103"], {"reason_category": "OTHER"})


def test_ayrilan_ogrencinin_tedbiri_kati_silinir() -> None:
    sube(9, "A", students=1, start_no=101)
    services_individual.add_iep_student(
        _no("101"), {"reason_category": "HEALTH", "extra_minutes": 15}
    )
    persons.update_student(Student.objects.get(pk=_no("101")), status=StudentStatus.LEFT)
    assert not IepStudent.all_objects.exists()


# ===========================================================================
# Oturum — yer tedbiri yerleştirme kuralıdır
# ===========================================================================


def test_kendi_sinifinda_tedbiri_her_oturumda_uygulanir() -> None:
    session, subeler = _oturum()
    derslik = salon("9-A dersliği", plan=PLAN_3X2_DOUBLE, linked_section_id=subeler["9A"].pk)
    services_individual.add_iep_student(
        _no("101"),
        {
            "reason_category": "DISABILITY",
            "placement": "HOME_CLASSROOM",
            "seat_preference": "BACK",
            "solo_desk": True,
        },
    )

    for seed in (7, 8):
        session, _, rapor = services.distribute_session(session, seed=seed)
        assert rapor.is_valid
        koltuk = _koltuk(session, "101")
        assert koltuk.room_id == derslik.pk and koltuk.status == SeatStatus.PINNED
        # Sırada tek başına: sıra arkadaşı koltuğu kimseye verilmedi.
        assert not (
            SeatAssignment.objects.filter(
                session=session, room=derslik, desk_row=koltuk.desk_row, desk_col=koltuk.desk_col
            )
            .exclude(pk=koltuk.pk)
            .exists()
        )


def test_ayri_salon_tedbiri_salonu_kelebekten_ayirir() -> None:
    session, _ = _oturum()
    rehber = salon("Rehberlik", plan=PLAN_3X2_DOUBLE)
    _salonlari_ayarla(session, rehber)
    for number in ("101", "201"):
        services_individual.add_iep_student(
            _no(number),
            {
                "reason_category": "DISABILITY",
                "placement": "SEPARATE_ROOM",
                "target_room_id": rehber.pk,
            },
        )

    session, sonuc, _ = services.distribute_session(session, seed=7)

    oradakiler = set(
        SeatAssignment.objects.filter(session=session, room=rehber).values_list(
            "student_id", flat=True
        )
    )
    assert oradakiler == {_no("101"), _no("201")}
    assert any("“Ayrı salon” kuralıyla ayrıldı" in w for w in sonuc.warnings)


def test_on_sirada_tedbiri_on_siraya_oturtur() -> None:
    session, _ = _oturum()
    services_individual.add_iep_student(
        _no("102"), {"reason_category": "HEALTH", "placement": "FRONT_ROW"}
    )

    session, _, _ = services.distribute_session(session, seed=7)

    koltuk = _koltuk(session, "102")
    assert koltuk.status == SeatStatus.PINNED and koltuk.desk_row == 0


def test_oturum_kurali_tedbiri_ezer() -> None:
    session, subeler = _oturum()
    salon("9-A dersliği", plan=PLAN_3X2_DOUBLE, linked_section_id=subeler["9A"].pk)
    rehber = salon("Rehberlik", plan=PLAN_3X2_DOUBLE)
    services_individual.add_iep_student(
        _no("101"), {"reason_category": "DISABILITY", "placement": "HOME_CLASSROOM"}
    )
    services.create_placement_rule(
        student_id=_no("101"),
        rule_type=RuleType.FIXED_ROOM,
        reason_category=RuleReason.OTHER,
        scope=RuleScope.SESSION,
        session=session,
        target_room_id=rehber.pk,
    )

    session, _, _ = services.distribute_session(session, seed=7)

    assert _koltuk(session, "101").room_id == rehber.pk
    [panel] = services_individual.session_accommodations(session)
    assert panel["overridden"] is True and panel["room_name"] == "Rehberlik"


def test_sure_ve_destek_yerlesimi_degistirmez_ama_uyarir() -> None:
    session, _ = _oturum()
    services_individual.add_iep_student(
        _no("101"), {"reason_category": "DISABILITY", "extra_minutes": 20, "reader": True}
    )

    session, sonuc, _ = services.distribute_session(session, seed=7)

    assert _koltuk(session, "101").status != SeatStatus.PINNED
    assert "Bu oturumda ek süreli 1 öğrenci var" in " ".join(sonuc.warnings)
    assert any("desteği alan 1 öğrenci ayrı salonda değil" in w for w in sonuc.warnings)
    assert not any("101" in w or "AD0" in w for w in sonuc.warnings)
    # Uyarılar R8'e girmez — R8 "Tümünü indir" paketindedir (kullanıcı kararı).
    session.refresh_from_db()
    assert not any(
        "ek süre" in w or "desteği" in w for w in session.distribution_params["warnings"]
    )


def test_iki_destekli_ogrenci_ayni_salonda_uyarilir() -> None:
    session, _ = _oturum()
    rehber = salon("Rehberlik", plan=PLAN_3X2_DOUBLE)
    _salonlari_ayarla(session, rehber)
    for number in ("101", "102"):
        services_individual.add_iep_student(
            _no(number),
            {
                "reason_category": "DISABILITY",
                "placement": "SEPARATE_ROOM",
                "target_room_id": rehber.pk,
                "scribe": True,
            },
        )

    _, sonuc, _ = services.distribute_session(session, seed=7)

    assert any(
        "“Rehberlik” salonunda okuyucu ya da yazıcı desteği alan 2 öğrenci var" in w
        for w in sonuc.warnings
    )


def test_pasif_ayri_salon_dagitimi_tedbir_ekranina_yonlendirir() -> None:
    session, _ = _oturum()
    rehber = salon("Rehberlik", plan=PLAN_3X2_DOUBLE)
    services_individual.add_iep_student(
        _no("101"),
        {
            "reason_category": "DISABILITY",
            "placement": "SEPARATE_ROOM",
            "target_room_id": rehber.pk,
        },
    )
    ExamRoom.objects.filter(pk=rehber.pk).update(is_active=False)

    with pytest.raises(ValidationError, match="Kişiler → BEP ve tedbirler"):
        services.distribute_session(session, seed=7)


def test_kendi_dersliginde_duzeninde_ayri_salon_tedbiri_uyarilir() -> None:
    session, subeler = _oturum(layout_mode=LayoutMode.HOME_CLASSROOM)
    salon("9-A dersliği", plan=PLAN_3X2_DOUBLE, linked_section_id=subeler["9A"].pk)
    salon("10-A dersliği", plan=PLAN_3X2_DOUBLE, linked_section_id=subeler["10A"].pk)
    rehber = salon("Rehberlik", plan=PLAN_3X2_DOUBLE)
    services_individual.add_iep_student(
        _no("101"),
        {
            "reason_category": "DISABILITY",
            "placement": "SEPARATE_ROOM",
            "target_room_id": rehber.pk,
        },
    )

    _, sonuc, _ = services.distribute_session(session, seed=7)

    assert any("Ayrı salonda sınava girmesi gereken 1 öğrenci var" in w for w in sonuc.warnings)


# ===========================================================================
# Ek süre — oturum çakışması ve takvim
# ===========================================================================


def test_ek_sure_oturum_cakismasini_uzatir() -> None:
    sube(9, "A", students=2, start_no=101)
    cog = ders("Coğrafya", levels=[9])
    fiz = ders("Fizik", levels=[9])
    a = oturum(name="A", start_time=time(9, 0), duration_minutes=40)
    b = oturum(name="B", start_time=time(9, 50), duration_minutes=40)
    services.add_session_course(
        a, course_id=cog.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    services.add_session_course(
        b, course_id=fiz.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    assert participants.overlapping_session_conflicts(a) == []

    services_individual.add_iep_student(
        _no("101"), {"reason_category": "DISABILITY", "extra_minutes": 20}
    )

    assert participants.overlapping_session_conflicts(a) == [
        "'B' oturumuyla ek süreli 1 öğrencinin sınav süresi çakışıyor: ek süre öbür sınavın "
        "başlangıcına taşıyor."
    ]
    assert participants.overlapping_session_conflicts(b) == [
        "'A' oturumuyla ek süreli 1 öğrencinin sınav süresi çakışıyor: ek süre öbür sınavın "
        "başlangıcına taşıyor."
    ]


def test_takvim_ardisik_ders_saatinde_ek_sureliyi_uyarir() -> None:
    calendar = _havuzlu_takvim(course_count=3)
    girdiler = list(ExamCalendarEntry.objects.filter(calendar=calendar).order_by("id"))
    gun = date(2026, 10, 27)
    takvim.place_entry(girdiler[0], on_date=gun, period_no=1)
    takvim.place_entry(girdiler[1], on_date=gun, period_no=2)
    takvim.place_entry(girdiler[2], on_date=date(2026, 10, 28), period_no=1)
    assert not any("ek süreli" in w for w in takvim.calendar_validation(calendar)["warnings"])

    services_individual.add_iep_student(
        _no("101"), {"reason_category": "HEALTH", "extra_minutes": 15}
    )

    uyarilar = [w for w in takvim.calendar_validation(calendar)["warnings"] if "ek süreli" in w]
    assert uyarilar == [
        "9. Sınıf 27.10.2026: ek süreli 1 öğrenci 1. ve 2. ders saatindeki iki sınava da "
        "giriyor; ek süre teneffüse taşar, ikinci sınava geç başlayabilir."
    ]


# ===========================================================================
# Basılı bilgi — YALNIZ idare özeti (kullanıcı kararı 07.10.2026)
# ===========================================================================


def test_idare_ozeti_tedbirleri_basar_gerekceyi_basmaz() -> None:
    session, _ = _oturum()
    services_individual.add_iep_student(
        _no("102"), {"reason_category": "HEALTH", "extra_minutes": 20, "scribe": True}
    )
    services.distribute_session(session, seed=7)

    rapor = services_individual.render_iep_summary(session)

    metin = _pdf_text(rapor.content)
    assert rapor.filename.startswith("tedbir_idare_ozeti")
    assert "Sınav Tedbirleri ve BEP" in metin and "102" in metin
    assert "Ek süre 20 dk" in metin and "Yazıcı desteği" in metin
    assert "Sağlık" not in metin  # gerekçe kategorisi basılmaz
    assert "16/1" in metin and "6/3" not in metin
    assert "101" not in metin  # tedbiri olmayan öğrenci özete girmez


def test_dagitimdan_sonra_girilen_yer_tedbiri_uygulanmadi_der() -> None:
    """Özet "dağıtımda uygulandı" dememeli: tedbir dağıtımdan sonra girildiyse not düşer."""
    session, _ = _oturum()
    services.distribute_session(session, seed=7)
    services_individual.add_iep_student(
        _no("102"), {"reason_category": "HEALTH", "placement": "FRONT_ROW", "extra_minutes": 10}
    )

    [satir] = services_individual.summary_rows(session)
    assert satir["measures"].endswith(services_individual.PLACEMENT_NOT_APPLIED)
    [panel] = services_individual.session_accommodations(session)
    assert panel["placement_applied"] is False

    services.distribute_session(session, seed=7)

    [satir] = services_individual.summary_rows(session)
    assert services_individual.PLACEMENT_NOT_APPLIED not in satir["measures"]
    assert services_individual.session_accommodations(session)[0]["placement_applied"] is True


def test_salon_evrakinda_ve_dogrulama_raporunda_tedbir_izi_yok() -> None:
    session, _ = _oturum()
    rehber = salon("Rehberlik", plan=PLAN_3X2_DOUBLE)
    _salonlari_ayarla(session, rehber)
    services_individual.add_iep_student(
        _no("101"),
        {
            "reason_category": "DISABILITY",
            "placement": "SEPARATE_ROOM",
            "target_room_id": rehber.pk,
            "extra_minutes": 30,
            "reader": True,
            "scribe": True,
        },
    )
    services.distribute_session(session, seed=7)

    for code in ("r1", "r4", "r7", "r8"):
        metin = _pdf_text(services.render_session_report(session, code).content)
        for iz in ("Ek süre", "ek süre", "Okuyucu", "okuyucu", "Yazıcı", "yazıcı", "edbir"):
            assert iz not in metin, (code, iz)


# ===========================================================================
# API
# ===========================================================================


def test_api_ekle_duzenle_toplu_ve_oturum_paneli() -> None:
    session, _ = _oturum()
    rehber = salon("Rehberlik", plan=PLAN_3X2_DOUBLE)
    client = APIClient()

    ekle = client.post(
        "/api/v1/iep-students/",
        {
            "student_id": _no("101"),
            "reason_category": "DISABILITY",
            "placement": "SEPARATE_ROOM",
            "target_room_id": rehber.pk,
            "extra_minutes": 25,
        },
        format="json",
    )
    assert ekle.status_code == 201, ekle.json()
    satir_id = ekle.json()["id"]
    [satir] = client.get("/api/v1/iep-students/").json()["results"]
    assert satir["measures"] == ["Ayrı salon (Rehberlik)", "Ek süre 25 dk"]

    duzelt = client.put(
        f"/api/v1/iep-students/{satir_id}/",
        {"reason_category": "DISABILITY", "placement": "FRONT_ROW", "extra_minutes": 25},
        format="json",
    )
    assert duzelt.status_code == 200, duzelt.json()
    hatali = client.put(
        f"/api/v1/iep-students/{satir_id}/", {"placement": "SEPARATE_ROOM"}, format="json"
    )
    assert hatali.status_code == 400

    toplu = client.post(
        "/api/v1/iep-students/bulk/",
        {"student_numbers": "102, 103\n999", "reason_category": "HEALTH", "reader": True},
        format="json",
    )
    assert toplu.status_code == 200, toplu.json()
    assert toplu.json() == {"added": 2, "already": 0, "not_found": ["999"]}

    panel = client.get(f"/api/v1/iep-students/session/?session={session.pk}").json()["rows"]
    assert [r["student_number"] for r in panel] == ["101", "102", "103"]
    assert panel[0]["measures"] == ["Ön sırada", "Ek süre 25 dk"]
    assert client.get("/api/v1/iep-students/session/?session=x").status_code == 404
