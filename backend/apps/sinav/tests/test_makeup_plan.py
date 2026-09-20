"""Mazeret sınav takvimi — servis, belge ve API testleri (20.09.2026).

Yerleştiricinin saf kuralları `test_makeup_schedule.py`dedir; burada kayıtların takvime
bağlanması, elle düzeltme, uyarılar, onay → oturum üretimi ve iki belge sınanır.
Senaryo: 9/A (101-106) ve 10/B (201-206); üç gün üst üste ikişer dersli sınav.
Öğrenci 101 üç sınava da girmemiştir (takvimi sürükleyen "yoğun" öğrenci).
"""

from __future__ import annotations

import io
from datetime import date, time

import pytest
from django.core.exceptions import ValidationError
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.okul.models import SchoolConfig
from apps.sinav import participants, services, services_makeup
from apps.sinav import services_makeup_plan as plans
from apps.sinav.models import (
    ExamAttendanceRecord,
    ExamRoom,
    ExamSession,
    ExamSessionCourse,
    ExamSessionType,
    ExcuseStatus,
    MakeupPlan,
    MakeupPlanItem,
    MakeupPlanStatus,
    ParticipantType,
    SeatAssignment,
)
from apps.sinav.tests.oturum_yardim import ders, donem, oturum, salon, sube

pytestmark = pytest.mark.django_db

URL = "/api/v1/makeup-plans/"
PZT, SAL, CAR = date(2026, 11, 23), date(2026, 11, 24), date(2026, 11, 25)


# ---------------------------------------------------------------------------
# Kurulum
# ---------------------------------------------------------------------------
def _sinav(ad9: str, ad10: str, gun: int, room: ExamRoom, **kwargs: object) -> ExamSession:
    """9. ve 10. sınıftan birer dersli, dağıtılmış ve ONAYLI oturum (Kasım `gun`)."""
    c9, c10 = ders(ad9, levels=[9]), ders(ad10, levels=[10])
    session = oturum(name=f"{ad9} / {ad10}", exam_date=date(2026, 11, gun), **kwargs)
    for course, level in ((c9, 9), (c10, 10)):
        services.add_session_course(
            session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=level
        )
    services.set_session_rooms(session, [{"room_id": room.pk}])
    session, _sonuc, rapor = services.distribute_session(session, seed=11)
    assert rapor.is_valid
    return services.approve_session(session)


def _girmedi(
    session: ExamSession, numara: str, durum: str = ExcuseStatus.EXCUSED
) -> ExamAttendanceRecord:
    koltuk = next(
        s for s in SeatAssignment.objects.filter(session=session) if s.student_number == numara
    )
    return services.mark_absent(session, seat_assignment_id=koltuk.pk, excuse_status=durum)


def _senaryo() -> dict[str, ExamAttendanceRecord]:
    sube(9, "A", students=6, start_no=101)
    sube(10, "B", students=6, start_no=201)
    room = salon("D-201", plan=services.default_room_plan()[0])  # 40 koltuk
    s1 = _sinav("Coğrafya", "Fizik", 16, room)
    s2 = _sinav("Matematik", "Kimya", 17, room)
    s3 = _sinav("Tarih", "Biyoloji", 18, room)
    return {
        "cog101": _girmedi(s1, "101"),
        "fiz201": _girmedi(s1, "201"),
        "mat101": _girmedi(s2, "101"),
        "kim202": _girmedi(s2, "202"),
        "tar101": _girmedi(s3, "101"),
    }


def _plan(**kwargs: object) -> MakeupPlan:
    params: dict[str, object] = {
        "semester_id": donem().pk,
        "start_date": PZT,
        "day_count": 2,
        "max_per_day": 2,
        "period_nos": [2, 3],
    }
    params.update(kwargs)
    return plans.create_plan(**params)  # type: ignore[arg-type]


def _yerler(plan: MakeupPlan) -> dict[str, tuple[date | None, int | None]]:
    return {
        i.course.name: (i.placed_date, i.period_no) for i in plan.items.select_related("course")
    }


def _kalem(plan: MakeupPlan, ders_adi: str) -> MakeupPlanItem:
    return plan.items.get(course__name=ders_adi)


# ---------------------------------------------------------------------------
# Kurma + yerleştirme
# ---------------------------------------------------------------------------
def test_takvim_asil_sirayi_korur_ve_ogrenci_sinirini_asmaz() -> None:
    kayitlar = _senaryo()
    plan = _plan()
    assert plan.status == MakeupPlanStatus.DRAFT and plan.name == plans.DEFAULT_PLAN_NAME
    assert _yerler(plan) == {
        "Coğrafya": (PZT, 2),
        "Fizik": (PZT, 2),  # asıl takvimde aynı saatte, öğrencileri ayrık → aynı oturum
        "Matematik": (PZT, 3),  # 101 aynı saatte iki sınava giremez
        "Kimya": (PZT, 2),  # aynı asıl saatli sınav, Matematik'in kaymasından etkilenmez
        "Tarih": (SAL, 2),  # 101'in günlük sınırı (2) doldu → ertesi gün
    }
    # Kayıt takvime bağlandı: elle mazeret sınavına SEÇİLEMEZ ama hâlâ sınav bekliyor.
    satir = next(
        r
        for r in services_makeup.absence_rows(donem().pk)
        if r["record_id"] == kayitlar["tar101"].pk
    )
    assert satir["can_makeup"] is False and satir["awaiting_makeup"] is True
    assert satir["plan_id"] == plan.pk and satir["plan_date"] == SAL.isoformat()
    with pytest.raises(ValidationError, match="mazeret takvimine alınmış") as exc:
        services_makeup.create_makeup_session(
            record_ids=[kayitlar["tar101"].pk], exam_date=CAR, start_time=time(10, 0)
        )
    assert "Okul No 101" in str(exc.value) and "AD0" not in str(exc.value)


def test_sigmayan_sinav_gerekcesiyle_kalir_ve_en_az_gun_soylenir() -> None:
    _senaryo()
    plan = _plan(max_per_day=1)
    tarih = _kalem(plan, "Tarih")
    assert tarih.placed_date is None
    assert "Okul No 101" in tarih.note and "sığmadı" in tarih.note
    veri = plans.plan_payload(plan)
    assert veri["min_days"] == 3  # 101: üç sınav, günde bir → üç gün

    plan = plans.replan(plan, day_count=3)
    assert _yerler(plan)["Tarih"] == (CAR, 2) and _kalem(plan, "Tarih").note == ""
    assert plans.plan_payload(plan)["min_days"] is None


def test_gevsek_kip_bos_saate_one_ceker() -> None:
    _senaryo()
    # Biyoloji asıl takvimin SON günündedir ve öğrencisi (203) boştadır. Kesin kipte önceki
    # günün sınavlarının ulaştığı saatten (Matematik: PZT 3) ÖNCEYE konmaz; gevşek kipte
    # ilk boş saate çekilir.
    s3 = ExamSession.objects.get(name="Tarih / Biyoloji")
    _girmedi(s3, "203")
    kesin = _plan()
    assert _yerler(kesin)["Biyoloji"] == (PZT, 3)
    gevsek = plans.replan(kesin, strict_order=False)
    assert _yerler(gevsek)["Biyoloji"] == (PZT, 2)
    assert _yerler(gevsek)["Tarih"] == (SAL, 2)  # 101'in kendi sırası yine korunur


def test_parametreler_mevzuat_sinirinda_denetlenir() -> None:
    _senaryo()
    with pytest.raises(ValidationError, match="en çok 3 sınava"):
        _plan(max_per_day=4)
    with pytest.raises(ValidationError, match="Gün sayısı 1 ile"):
        _plan(day_count=0)
    with pytest.raises(ValidationError, match="zil çizelgesinde yok"):
        _plan(period_nos=[99])
    assert not MakeupPlan.objects.exists()


def test_bekleyen_kayit_yoksa_takvim_kurulmaz() -> None:
    donem()
    with pytest.raises(ValidationError, match="Takvime alınacak öğrenci yok"):
        _plan()


# ---------------------------------------------------------------------------
# Üst makam sınavı + elle düzeltme
# ---------------------------------------------------------------------------
def test_ust_makam_sinavi_otomatik_yerlesmez_elle_sabitlenir() -> None:
    _senaryo()
    room = ExamRoom.objects.get(name="D-201")
    ulke = _sinav(
        "Felsefe", "Türk Dili ve Edebiyatı", 12, room, session_type=ExamSessionType.NATIONAL
    )
    _girmedi(ulke, "101")  # Felsefe 9 — ülke geneli
    plan = _plan()
    felsefe = _kalem(plan, "Felsefe")
    assert felsefe.external and felsefe.placed_date is None
    assert "il/ilçe millî eğitim müdürlüğü ilan eder" in felsefe.note

    # İl MEM'in ilan ettiği saat Coğrafya'nın saatiyle aynıysa 101 çakışır → RET.
    with pytest.raises(ValidationError, match="aynı anda iki sınavda olamaz") as exc:
        plans.move_item(felsefe, placed_date=PZT, period_no=2)
    assert "Okul No 101" in str(exc.value)

    uyarilar = plans.move_item(felsefe, placed_date=PZT, period_no=4)
    felsefe.refresh_from_db()
    assert felsefe.is_pinned and felsefe.note == ""
    # 101'in o gün üç sınavı oldu (sınır 2) → uyarı, ret değil.
    assert any("Okul No 101" in u and "3 mazeret sınavı" in u for u in uyarilar)

    # Yeniden yerleştirme sabite dokunmaz ve onu DOLULUK sayar: 101'in günlük sınırı.
    plans.auto_place(plan)
    assert _yerler(plan)["Felsefe"] == (PZT, 4)
    assert _yerler(plan)["Matematik"] == (SAL, 2)  # PZT'de 101'in iki sınavı zaten var


def test_elle_tasima_sira_disi_uyarir_ve_takvim_disina_alinir() -> None:
    _senaryo()
    plan = _plan(day_count=3)
    cografya = _kalem(plan, "Coğrafya")
    uyarilar = plans.move_item(cografya, placed_date=CAR, period_no=3)
    assert any("asıl takvimde" in u and "sonraya düştü" in u for u in uyarilar)

    plans.unplace_item(cografya)
    cografya.refresh_from_db()
    assert cografya.placed_date is None and not cografya.is_pinned
    with pytest.raises(ValidationError, match="sabitlenemez"):
        plans.set_item_pinned(cografya, is_pinned=True)


def test_uyarilar_donem_disi_olagan_takvim_ve_bekleyen_karar() -> None:
    from apps.sinav.models import ExamCalendar

    _senaryo()
    s2 = ExamSession.objects.get(name="Matematik / Kimya")
    _girmedi(s2, "204", ExcuseStatus.PENDING)
    ExamCalendar.objects.create(
        semester=donem(),
        round=1,
        name="1. Dönem 1. Sınav Takvimi",
        start_date=date(2026, 11, 16),
        end_date=date(2026, 11, 27),
    )
    plan = _plan(max_per_day=3)
    plans.move_item(_kalem(plan, "Tarih"), placed_date=date(2027, 2, 1), period_no=2)
    metin = " ".join(plans.plan_warnings(plan))
    assert "yalnız zorunlu hâlde" in metin
    assert "dönem dışında" in metin and "md. 48" in metin
    assert "olağan sınav takviminin günleri içinde" in metin
    assert "1 kaydın mazeret kararı hâlâ “Beklemede”" in metin
    assert plans.plan_errors(plan) == []  # uyarı onayı engellemez


# ---------------------------------------------------------------------------
# Kayıt değişiklikleri
# ---------------------------------------------------------------------------
def test_sonradan_mazeretli_olan_kayit_eklenir_mazeretsiz_olan_duser() -> None:
    kayitlar = _senaryo()
    plan = _plan()
    s1 = ExamSession.objects.get(name="Coğrafya / Fizik")
    _girmedi(s1, "105")  # takvimden SONRA kabul edilen mazeret
    assert plans.unsynced_count(plan) == 1
    assert plans.sync_records(plan) == 1
    veri = plans.plan_payload(plan)
    cografya = next(i for i in veri["items"] if i["course_label"].startswith("Coğrafya"))
    assert [s["student_number"] for s in cografya["students"]] == ["101", "105"]
    assert veri["unsynced_count"] == 0

    # Mazereti geri alınan öğrenci sayımdan düşer; tek öğrencili sınav boş kalır.
    services.update_attendance_record(kayitlar["kim202"], excuse_status=ExcuseStatus.UNEXCUSED)
    plans.auto_place(plan)
    kimya = _kalem(plan, "Kimya")
    assert kimya.placed_date is None and "öğrencisi kalmadı" in kimya.note


def test_sinav_ve_takvim_cikarilinca_kayitlar_serbest_kalir() -> None:
    kayitlar = _senaryo()
    plan = _plan()
    plans.remove_item(_kalem(plan, "Tarih"))
    kayitlar["tar101"].refresh_from_db()
    assert kayitlar["tar101"].makeup_plan_item_id is None
    assert not plan.items.filter(course__name="Tarih").exists()

    plans.remove_plan(plan)
    assert not ExamAttendanceRecord.objects.filter(makeup_plan_item__isnull=False).exists()
    assert all(r["can_makeup"] for r in services_makeup.absence_rows(donem().pk))


# ---------------------------------------------------------------------------
# Onay + oturum üretimi
# ---------------------------------------------------------------------------
def test_cakisma_onayi_engeller() -> None:
    _senaryo()
    plan = _plan()
    # Elle taşıma çakışmayı reddeder; kusur yalnız veri sonradan değişirse doğar — benzetim.
    MakeupPlanItem.objects.filter(pk=_kalem(plan, "Matematik").pk).update(
        placed_date=PZT, period_no=2, is_pinned=True
    )
    hatalar = plans.plan_errors(plan)
    assert len(hatalar) == 1 and "Okul No 101" in hatalar[0] and "Coğrafya" in hatalar[0]
    with pytest.raises(ValidationError, match="aynı saatte hem"):
        plans.approve_plan(plan)


def test_onayli_takvimden_oturumlar_uretilir() -> None:
    SchoolConfig.objects.create(pk=SchoolConfig.SINGLETON_PK, principal_name="Şükrü Ağaoğlu")
    _senaryo()
    plan = _plan(name="1. Dönem 1. Sınav Mazeret Takvimi")
    with pytest.raises(ValidationError, match="ONAYLANMIŞ"):
        plans.create_sessions(plan)
    plan = plans.approve_plan(plan)
    assert plan.approved_by_name == "Şükrü Ağaoğlu"
    with pytest.raises(ValidationError, match="Onaylanmış mazeret takvimi değiştirilemez"):
        plans.auto_place(plan)

    sonuc = plans.create_sessions(plan)
    assert len(sonuc["created"]) == 3  # üç ayrı saat → üç oturum
    assert sonuc["created"][0] == "1. Dönem 1. Sınav Mazeret Takvimi — 23.11.2026 2. Ders"
    ilk = _kalem(plan, "Coğrafya").session
    assert ilk is not None and ilk.is_makeup and ilk.start_time == time(9, 20)
    # Aynı saatteki üç sınav TEK oturumda; katılımcılar yalnız o sınavların öğrencileri.
    assert _kalem(plan, "Fizik").session_id == ilk.pk == _kalem(plan, "Kimya").session_id
    satirlar = ExamSessionCourse.objects.filter(session=ilk)
    assert {s.participant_type for s in satirlar} == {ParticipantType.MAKEUP}
    cozum = participants.resolve_session(ilk)
    assert sorted(p.student_number for p in cozum.participants) == ["101", "201", "202"]
    assert not cozum.has_blocking_conflicts

    assert plans.create_sessions(plan)["created"] == []  # idempotent
    with pytest.raises(ValidationError, match="yeniden açılamaz"):
        plans.reopen_plan(plan)


def test_uretilen_oturumdan_cikarilan_kayit_takvimden_de_kopar() -> None:
    """Aksi hâlde kayıt elle seçilemez ve onaylı takvim açılamadığı için ortada kalırdı."""
    kayitlar = _senaryo()
    plan = plans.approve_plan(_plan())
    plans.create_sessions(plan)
    assert services_makeup.remove_from_makeup(record_ids=[kayitlar["tar101"].pk]) == 1
    kayitlar["tar101"].refresh_from_db()
    assert kayitlar["tar101"].makeup_plan_item_id is None
    satir = next(
        r
        for r in services_makeup.absence_rows(donem().pk)
        if r["record_id"] == kayitlar["tar101"].pk
    )
    assert satir["can_makeup"] is True and satir["plan_id"] is None


def test_oturum_uretilmeden_takvim_yeniden_acilir() -> None:
    _senaryo()
    plan = plans.approve_plan(_plan())
    plan = plans.reopen_plan(plan)
    assert plan.status == MakeupPlanStatus.DRAFT and plan.approved_at is None


# ---------------------------------------------------------------------------
# Belgeler — ilan nüshası ADSIZ
# ---------------------------------------------------------------------------
def _pdf_metni(dosya: object) -> str:
    reader = PdfReader(io.BytesIO(dosya.content))  # type: ignore[attr-defined]
    return " ".join(" ".join(p.extract_text() or "" for p in reader.pages).split())


def test_ilan_nushasi_ogrenci_verisi_tasimaz_liste_tasir() -> None:
    SchoolConfig.objects.create(
        pk=SchoolConfig.SINGLETON_PK, school_name="Örnek Anadolu Lisesi", principal_name="Ali VELİ"
    )
    _senaryo()
    plan = _plan(name="Kasım Mazeret Sınav Takvimi")

    ilan = _pdf_metni(plans.render_plan_pdf(plan, kind="ilan"))
    for beklenen in (
        "KASIM MAZERET SINAV TAKVİMİ",
        "TASLAK",
        "23 Kasım 2026 Pazartesi",
        "Coğrafya — 9. Sınıf",
        "Coğrafya Zümre Başkanı",
        "Düzenleyen — Müdür Yardımcısı",
        "Örnek Anadolu Lisesi Müdürlüğü",
    ):
        assert beklenen in ilan, beklenen
    # KVKK: ilan nüshasında öğrenci adı da okul numarası da YOK.
    assert "SOYAD9A" not in ilan and "Okul No" not in ilan and " 101 " not in ilan

    liste = _pdf_metni(plans.render_plan_pdf(plan, kind="liste"))
    assert "AD0 SOYAD9A" in liste and "23.11.2026 09:20 · Coğrafya — 9. Sınıf" in liste
    assert "6698 sayılı Kanunun 5/2-ç" in liste
    # Sınıf düzeyi SAYISAL sıralanır: 9/A, 10/B'den önce (metin sıralaması tersini verirdi).
    assert liste.index("SOYAD9A") < liste.index("SOYAD10B")

    adsiz = _pdf_metni(plans.render_plan_pdf(plan, kind="liste", show_names=False))
    assert "SOYAD9A" not in adsiz and "101" in adsiz and "(okul numarasıyla)" in adsiz

    onayli = _pdf_metni(plans.render_plan_pdf(plans.approve_plan(plan), kind="ilan"))
    assert "TASLAK" not in onayli


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def test_api_akisi() -> None:
    _senaryo()
    client = APIClient()
    assert client.get(URL).data["plans"] == []

    ret = client.post(URL, {"semester_id": donem().pk, "day_count": 2}, format="json")
    assert ret.status_code == 400 and "start_date" in str(ret.data)

    yanit = client.post(
        URL,
        {
            "semester_id": donem().pk,
            "start_date": "2026-11-23",
            "day_count": 2,
            "max_per_day": 2,
            "period_nos": [2, 3],
        },
        format="json",
    )
    assert yanit.status_code == 201, yanit.data
    plan_id = yanit.data["id"]
    assert [d["date"] for d in yanit.data["days"]] == ["2026-11-23", "2026-11-24"]
    assert [p["no"] for p in yanit.data["periods"]] == [2, 3]
    assert len(yanit.data["items"]) == 5 and yanit.data["errors"] == []
    assert client.get(URL).data["plans"][0]["id"] == plan_id

    tarih = next(i for i in yanit.data["items"] if i["course_label"].startswith("Tarih"))
    tasi = client.patch(
        f"/api/v1/makeup-plan-items/{tarih['id']}/",
        {"placed_date": "2026-11-23", "period_no": 2},
        format="json",
    )
    assert tasi.status_code == 400 and "Okul No 101" in str(tasi.data)
    tasi = client.patch(
        f"/api/v1/makeup-plan-items/{tarih['id']}/",
        {"placed_date": "2026-11-24", "period_no": 3},
        format="json",
    )
    assert tasi.status_code == 200 and tasi.data["result"]["warnings"] == []
    assert next(i for i in tasi.data["items"] if i["id"] == tarih["id"])["is_pinned"] is True

    yeniden = client.patch(
        f"{URL}{plan_id}/", {"day_count": 3, "strict_order": False}, format="json"
    )
    assert yeniden.status_code == 200 and len(yeniden.data["days"]) == 3

    assert client.post(f"{URL}{plan_id}/replace/").status_code == 200
    assert client.post(f"{URL}{plan_id}/sync/").data["result"] == {"added": 0}
    assert client.post(f"{URL}{plan_id}/sessions/").status_code == 400  # onaysız
    onay = client.post(f"{URL}{plan_id}/approve/", {"approved_by_name": "Ali VELİ"}, format="json")
    assert onay.status_code == 200 and onay.data["status"] == "APPROVED"
    oturumlar = client.post(f"{URL}{plan_id}/sessions/")
    assert oturumlar.status_code == 200 and len(oturumlar.data["result"]["created"]) == 3
    assert all(i["session_id"] for i in oturumlar.data["items"])

    pdf = client.get(f"{URL}{plan_id}/pdf/?kind=ilan")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert f'filename="mazeret_takvimi_{plan_id}.pdf"' in pdf["Content-Disposition"]
    liste = client.get(f"{URL}{plan_id}/pdf/?kind=liste&names=0")
    assert f"mazeret_takvimi_{plan_id}_liste_adsiz.pdf" in liste["Content-Disposition"]
    assert client.get(f"{URL}{plan_id}/pdf/?kind=docx").status_code == 400
    assert client.delete(f"{URL}{plan_id}/").status_code == 400  # onaylı takvim silinmez


def test_api_taslak_silinir_ve_sinav_cikarilir() -> None:
    _senaryo()
    plan = _plan()
    client = APIClient()
    kimya = _kalem(plan, "Kimya")
    yanit = client.delete(f"/api/v1/makeup-plan-items/{kimya.pk}/")
    assert yanit.status_code == 200 and len(yanit.data["items"]) == 4
    assert client.delete(f"{URL}{plan.pk}/").status_code == 204
    assert not MakeupPlan.objects.exists()
