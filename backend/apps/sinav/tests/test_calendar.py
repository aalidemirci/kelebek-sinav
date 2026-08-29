"""F6 sınav takvimi testleri — OYS takvim çekirdeğinin KS kabulü.

Kapı (tasarım §12 F6): PENCERE HESABI senaryoları (ayın son Pazartesisi + 11
gün; dönem sınırına kırpma; tur 3 = son iki hafta) + ÖĞRENCİ-BAZLI GÜNLÜK
LİMİT senaryoları (3. sınav = uyarı, ≥4 = sert hata; kayıt verisi olmayan
ders seviyenin tamamı — konservatif düşüş, risk #4). Ek: durum makinesi +
damgalar (B12/risk #10), slot→oturum, havuz doldurma, A4 YATAY PDF + TASLAK
filigranı + TR duman.
"""

from __future__ import annotations

import io
from datetime import date, time
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.okul.models import SchoolConfig, SchoolTerm
from apps.sinav import services_calendar as takvim
from apps.sinav.models import (
    ExamCalendar,
    ExamCalendarEntry,
    ExamCalendarStatus,
    ExamSessionStatus,
)
from apps.sinav.tests.oturum_yardim import aktif_yil, ders, donem, salon, sube

pytestmark = pytest.mark.django_db

TURKCE_DUMAN = "ĞÜŞİÖÇ ığüşiöç"


def _guz(start: date = date(2026, 9, 8), end: date = date(2027, 1, 15)) -> SimpleNamespace:
    """Pencere hesabı için saf dönem nesnesi (DB gerekmez — duck typing)."""
    return SimpleNamespace(sequence=1, start_date=start, end_date=end)


def _bahar(start: date = date(2027, 2, 8), end: date = date(2027, 6, 30)) -> SimpleNamespace:
    return SimpleNamespace(sequence=2, start_date=start, end_date=end)


# ===========================================================================
# Pencere hesabı (F6 kapısı) — Ölçme ve Değ. Yön. md. 5/1-ç
# ===========================================================================


def test_statutory_window_guz_turlari() -> None:
    """1D1S Ekim, 1D2S Aralık — ayın son Pazartesisi + 11 gün."""
    # Ekim 2026'nın son Pazartesisi 26'sı; +11 gün = 6 Kasım.
    assert takvim.statutory_window(_guz(), 1) == (date(2026, 10, 26), date(2026, 11, 6))
    # Aralık 2026'nın son Pazartesisi 28'i; +11 gün = 8 Ocak 2027 (dönem içinde).
    assert takvim.statutory_window(_guz(), 2) == (date(2026, 12, 28), date(2027, 1, 8))


def test_statutory_window_bahar_turlari() -> None:
    """2D1S Mart, 2D2S Mayıs — yıl dönemin KENDİ yılından (start_date.year)."""
    assert takvim.statutory_window(_bahar(), 1) == (date(2027, 3, 29), date(2027, 4, 9))
    assert takvim.statutory_window(_bahar(), 2) == (date(2027, 5, 31), date(2027, 6, 11))


def test_statutory_window_donem_sonuna_kirpilir() -> None:
    """Pencere dönem bitişini aşarsa bitişe kırpılır."""
    guz = _guz(end=date(2027, 1, 4))  # 8 Ocak penceresinden önce biter
    start, end = takvim.statutory_window(guz, 2)
    assert start == date(2026, 12, 28) and end == date(2027, 1, 4)


def test_statutory_window_ters_cevrilirse_donem_basina_duser() -> None:
    """Kırpma pencereyi ters çevirirse başlangıç dönem başı + 11 gün olur."""
    kisa = _guz(start=date(2026, 9, 8), end=date(2026, 10, 20))  # Ekim penceresinden önce biter
    start, end = takvim.statutory_window(kisa, 1)
    assert start == date(2026, 9, 8)
    assert end == date(2026, 9, 19)  # start + 11 gün (dönem bitişinden küçük)


def test_statutory_window_tur3_son_iki_hafta() -> None:
    """Tur 3'ün statutory penceresi yok — dönemin son iki haftası (elle düzenlenir)."""
    guz = _guz()
    start, end = takvim.statutory_window(guz, 3)
    assert end == guz.end_date
    assert start == date(2027, 1, 2)  # end - 13 gün
    assert (end - start).days == 13


# ===========================================================================
# Ön tanımlı takvim üretimi + havuz
# ===========================================================================


def _iki_donem() -> tuple[SchoolTerm, SchoolTerm]:
    """Aktif yıl + güz (sequence 1) ve bahar (sequence 2) dönemleri."""
    yil = aktif_yil()
    guz = donem(yil, sequence=1)
    bahar: SchoolTerm | None = SchoolTerm.objects.filter(school_year=yil, sequence=2).first()
    if bahar is None:
        bahar = SchoolTerm.objects.create(
            school_year=yil,
            sequence=2,
            start_date=date(2027, 2, 8),
            end_date=date(2027, 6, 30),
        )
    return guz, bahar


def test_generate_default_calendars_idempotent() -> None:
    """2 dönem × 2 tur = 4 taslak takvim; ikinci çağrı hiçbir şey üretmez."""
    yil = aktif_yil()
    _iki_donem()
    created = takvim.generate_default_calendars(school_year_id=yil.pk)
    assert len(created) == 4
    assert {(c.semester.sequence, c.round) for c in created} == {
        (1, 1),
        (1, 2),
        (2, 1),
        (2, 2),
    }
    assert all(c.status == ExamCalendarStatus.DRAFT for c in created)
    assert all(c.description_text == takvim.DEFAULT_CALENDAR_DESCRIPTION for c in created)
    # Tur 3 hiç üretilmez; idempotentlik.
    assert takvim.generate_default_calendars(school_year_id=yil.pk) == []
    assert ExamCalendar.objects.count() == 4


def test_fill_pool_katalogdan_ogrencili_seviyelerle() -> None:
    """Havuz = aktif katalog × (ders seviyeleri ∩ öğrencisi olan seviyeler); idempotent."""
    guz, _ = _iki_donem()
    sube(9, "A", students=2, start_no=101)  # yalnız 9. seviyede öğrenci var
    course = ders("Coğrafya", levels=[9, 10])
    calendar = takvim.create_exam_calendar(
        semester_id=guz.pk, round=1, start_date=date(2026, 10, 26), end_date=date(2026, 11, 6)
    )
    result = takvim.fill_calendar_pool(calendar)
    labels = result["created"]
    assert any("Coğrafya" in etiket and "9. Sınıf" in etiket for etiket in labels)
    assert not any("10. Sınıf" in etiket for etiket in labels)  # 10'da öğrenci yok
    assert ExamCalendarEntry.objects.filter(calendar=calendar, course=course, level=9).exists()
    # İdempotent: ikinci koşuda aynı çift existed'a düşer.
    tekrar = takvim.fill_calendar_pool(calendar)
    assert tekrar["created"] == [] and len(tekrar["existed"]) == len(labels)


def test_fill_pool_round3_reddedilir() -> None:
    guz, _ = _iki_donem()
    calendar = takvim.create_exam_calendar(
        semester_id=guz.pk, round=3, start_date=date(2027, 1, 2), end_date=date(2027, 1, 15)
    )
    with pytest.raises(ValidationError, match="elle doldurulur"):
        takvim.fill_calendar_pool(calendar)


# ===========================================================================
# Öğrenci-bazlı günlük limit (F6 kapısı) — OKY md. 45 esası
# ===========================================================================


def _havuzlu_takvim(course_count: int = 4) -> ExamCalendar:
    """9. seviyede öğrencili, `course_count` dersli taslak takvim."""
    guz, _ = _iki_donem()
    sube(9, "A", students=3, start_no=101)
    calendar = takvim.create_exam_calendar(
        semester_id=guz.pk, round=1, start_date=date(2026, 10, 26), end_date=date(2026, 11, 6)
    )
    for i in range(course_count):
        course = ders(f"Ders {i + 1}", levels=[9])
        takvim.add_calendar_entry(calendar=calendar, course_id=course.pk, level=9)
    return calendar


def test_gunluk_limit_uc_sinav_uyari_dort_sert_hata() -> None:
    """Aynı gün 3. sınav uyarı verir (yerleşir); 4. sınav SERT reddedilir.

    KS v1'de ders kayıt verisi yok → her ders 'seviyenin tamamını kapsar'
    sayılır (konservatif düşüş) ve yük o günkü ders sayısıdır.
    """
    calendar = _havuzlu_takvim(course_count=4)
    entries = list(ExamCalendarEntry.objects.filter(calendar=calendar).order_by("id"))
    gun = date(2026, 10, 27)

    r1 = takvim.place_entry(entries[0], on_date=gun, period_no=1)
    r2 = takvim.place_entry(entries[1], on_date=gun, period_no=2)
    assert r1.warnings == [] and r2.warnings == []

    r3 = takvim.place_entry(entries[2], on_date=gun, period_no=3)
    assert any("3. sınav" in w and "OKY md. 45" in w for w in r3.warnings)
    entries[2].refresh_from_db()
    assert entries[2].placed_date == gun  # uyarıyla YERLEŞİR, engellenmez

    with pytest.raises(ValidationError, match="4 sınava"):
        takvim.place_entry(entries[3], on_date=gun, period_no=4)
    entries[3].refresh_from_db()
    assert entries[3].placed_date is None  # sert hata — yerleşmedi


def test_gunluk_limit_farkli_gunler_serbest() -> None:
    calendar = _havuzlu_takvim(course_count=4)
    entries = list(ExamCalendarEntry.objects.filter(calendar=calendar).order_by("id"))
    for i, entry in enumerate(entries):
        result = takvim.place_entry(entry, on_date=date(2026, 10, 26 + i), period_no=1)
        assert result.warnings == [] or all("3. sınav" not in w for w in result.warnings)


def test_calendar_validation_dort_sinav_hata_uretir() -> None:
    """Takvim geneli doğrulama: ≥4 sınavlık gün errors'a düşer (grid/onay bandı)."""
    calendar = _havuzlu_takvim(course_count=4)
    gun = date(2026, 10, 27)
    # place_entry 4.'yü engeller — doğrulamanın kendi başına yakaladığını görmek
    # için yerleşim ORM ile kurulur (bozuk veri senaryosu).
    for i, entry in enumerate(ExamCalendarEntry.objects.filter(calendar=calendar)):
        entry.placed_date = gun
        entry.period_no = i + 1
        entry.save(update_fields=["placed_date", "period_no"])
    validation = takvim.calendar_validation(calendar)
    assert any("4 sınav" in e and "üst sınır" in e for e in validation["errors"])


def test_hafta_sonu_ve_aralik_disi_uyarilari() -> None:
    calendar = _havuzlu_takvim(course_count=1)
    entry = ExamCalendarEntry.objects.filter(calendar=calendar).first()
    assert entry is not None
    cumartesi = date(2026, 10, 31)
    result = takvim.place_entry(entry, on_date=cumartesi, period_no=1)
    assert any("hafta sonu" in w for w in result.warnings)
    disari = takvim.place_entry(entry, on_date=date(2026, 11, 20), period_no=1)
    assert any("takvim aralığı dışında" in w for w in disari.warnings)
    with pytest.raises(ValidationError, match="listede tanımlı değil"):
        takvim.place_entry(entry, on_date=cumartesi, period_no=99)


# ===========================================================================
# Durum makinesi + damgalar (B12, risk #10)
# ===========================================================================


def test_onay_akisi_damgalari() -> None:
    SchoolConfig.objects.create(pk=SchoolConfig.SINGLETON_PK, principal_name="Örnek MÜDÜR")
    calendar = _havuzlu_takvim(course_count=1)

    calendar = takvim.submit_calendar(calendar)
    assert calendar.status == ExamCalendarStatus.SUBMITTED
    assert calendar.submitted_at is not None

    calendar = takvim.approve_calendar(calendar)
    assert calendar.status == ExamCalendarStatus.APPROVED
    assert calendar.approved_by_name == "Örnek MÜDÜR"  # boş ad → müdür damgası
    assert calendar.approved_at is not None

    # Onaylı takvim düzenlenemez (taslak kilidi).
    with pytest.raises(ValidationError, match="taslak"):
        takvim.update_exam_calendar(calendar, name="Yeni Ad")

    # Yeniden açma damgaları SİLMEZ (tarihçe — OYS ile birebir).
    calendar = takvim.reopen_calendar(calendar)
    assert calendar.status == ExamCalendarStatus.DRAFT
    assert calendar.approved_by_name == "Örnek MÜDÜR" and calendar.approved_at is not None


# ===========================================================================
# Slot → oturum üretimi
# ===========================================================================


def _onayli_yerlesik_takvim() -> tuple[ExamCalendar, date]:
    """2 dersi aynı slota yerleşik ONAYLI takvim (9. seviye, şube derslikli)."""
    calendar = _havuzlu_takvim(course_count=2)
    salon("9-A Dersliği")
    gun = date(2026, 10, 27)
    for entry in ExamCalendarEntry.objects.filter(calendar=calendar):
        takvim.place_entry(entry, on_date=gun, period_no=1)
    takvim.submit_calendar(calendar)
    takvim.approve_calendar(calendar)
    return calendar, gun


def test_create_session_from_slot() -> None:
    calendar, gun = _onayli_yerlesik_takvim()
    session = takvim.create_session_from_slot(calendar, on_date=gun, period_no=1)

    assert session.status == ExamSessionStatus.DRAFT
    assert session.exam_date == gun
    assert session.start_time == time(8, 30)  # varsayılan ders saati listesi (B6)
    assert "1. Ders" in session.name and calendar.name in session.name
    assert session.courses.count() == 2
    assert set(session.courses.values_list("level", flat=True)) == {9}
    # Girdiler oturuma bağlandı; ikinci üretim reddedilir.
    assert ExamCalendarEntry.objects.filter(calendar=calendar, session=session).count() == 2
    with pytest.raises(ValidationError, match="zaten oturumlu"):
        takvim.create_session_from_slot(calendar, on_date=gun, period_no=1)


def test_create_session_yalniz_onayli_takvimden() -> None:
    calendar = _havuzlu_takvim(course_count=1)
    entry = ExamCalendarEntry.objects.filter(calendar=calendar).first()
    assert entry is not None
    gun = date(2026, 10, 27)
    takvim.place_entry(entry, on_date=gun, period_no=1)
    with pytest.raises(ValidationError, match="ONAYLANMIŞ"):
        takvim.create_session_from_slot(calendar, on_date=gun, period_no=1)


def test_kelebek_degil_girdi_oturuma_girmez() -> None:
    calendar, gun = _onayli_yerlesik_takvim()
    takvim.reopen_calendar(calendar)
    kd_ders = ders("Beden Eğitimi", levels=[9])
    kd = takvim.add_calendar_entry(
        calendar=calendar, course_id=kd_ders.pk, level=9, is_butterfly=False
    )
    takvim.place_entry(kd, on_date=gun, period_no=1)
    takvim.submit_calendar(calendar)
    takvim.approve_calendar(calendar)

    session = takvim.create_session_from_slot(calendar, on_date=gun, period_no=1)
    assert session.courses.count() == 2  # kelebek-değil hariç
    kd.refresh_from_db()
    assert kd.session_id is None


def test_uzun_takvim_adi_kirpilir() -> None:
    calendar, gun = _onayli_yerlesik_takvim()
    ExamCalendar.objects.filter(pk=calendar.pk).update(name="Ç" * 120)
    calendar.refresh_from_db()
    session = takvim.create_session_from_slot(calendar, on_date=gun, period_no=1)
    assert len(session.name) <= 120
    assert "…" in session.name


# ===========================================================================
# Izgara + PDF (A4 YATAY, TASLAK filigranı, TR duman)
# ===========================================================================


def test_calendar_grid_hucre_anahtari_sozlesmesi() -> None:
    calendar = _havuzlu_takvim(course_count=1)
    entry = ExamCalendarEntry.objects.filter(calendar=calendar).first()
    assert entry is not None
    gun = date(2026, 10, 27)
    takvim.place_entry(entry, on_date=gun, period_no=2)
    grid = takvim.calendar_grid(calendar)
    key = f"{gun.isoformat()}|2|9"  # "<iso_tarih>|<period_no>|<level>" — FE+PDF ortak
    assert key in grid["cells"] and grid["cells"][key][0]["entry_id"] == entry.pk
    assert grid["periods"][0] == {"no": 1, "name": "1. Ders", "start": "08:30"}
    assert any(d["is_weekend"] for d in grid["days"])  # aralıkta hafta sonu işaretli


def test_takvim_pdf_yatay_taslak_filigrani_ve_tr_duman() -> None:
    SchoolConfig.objects.create(
        pk=SchoolConfig.SINGLETON_PK,
        school_name=f"{TURKCE_DUMAN} Anadolu Lisesi",
        district="Sancaktepe",
        principal_name="Örnek MÜDÜR",
    )
    calendar = _havuzlu_takvim(course_count=2)
    gun = date(2026, 10, 27)
    for entry in ExamCalendarEntry.objects.filter(calendar=calendar):
        takvim.place_entry(entry, on_date=gun, period_no=1)

    taslak_pdf = takvim.render_calendar_pdf(calendar)
    assert taslak_pdf.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(taslak_pdf))
    page = reader.pages[0]
    # A4 YATAY: genişlik > yükseklik (~842×595 pt).
    assert float(page.mediabox.width) > float(page.mediabox.height)
    text = "\n".join(p.extract_text() or "" for p in reader.pages)
    assert "TASLAK" in text  # onaysız PDF filigranlı
    eksik = [h for h in TURKCE_DUMAN if h != " " and h not in text]
    assert not eksik, f"Takvim PDF'inde Türkçe glif kaybı: {eksik}"
    assert "SANCAKTEPE KAYMAKAMLIĞI" not in text  # antet ilçeyi olduğu gibi basar
    assert "Sancaktepe KAYMAKAMLIĞI" in text
    assert "Zümre Başkanı" in text  # boş imza çizgileri (B7)

    takvim.submit_calendar(calendar)
    takvim.approve_calendar(calendar)
    onayli_pdf = takvim.render_calendar_pdf(calendar)
    onayli_text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(onayli_pdf)).pages)
    assert "TASLAK" not in onayli_text


# ===========================================================================
# Süreç takip
# ===========================================================================


def test_track_mark_ve_matris() -> None:
    SchoolConfig.objects.create(pk=SchoolConfig.SINGLETON_PK, principal_name="Örnek MÜDÜR")
    calendar = _havuzlu_takvim(course_count=1)
    entry = ExamCalendarEntry.objects.filter(calendar=calendar).first()
    assert entry is not None
    item = takvim.create_track_item(name="Soru teslimi", description="CA + kitapçık")

    mark = takvim.set_track_mark(entry=entry, item=item, status="DONE", note="teslim alındı")
    assert mark is not None and mark.marked_by_name == "Örnek MÜDÜR"

    # note=None mevcut notu KORUR (OYS Tur 644 sözleşmesi).
    mark = takvim.set_track_mark(entry=entry, item=item, status="NOT_APPLICABLE")
    assert mark is not None and mark.note == "teslim alındı"

    matrix = takvim.track_matrix(calendar)
    assert [i["name"] for i in matrix["items"]] == ["Soru teslimi"]
    hucre = matrix["rows"][0]["cells"][0]
    assert hucre["status"] == "NOT_APPLICABLE" and hucre["marked_by_name"] == "Örnek MÜDÜR"

    # status=None işareti kaldırır (soft-delete).
    assert takvim.set_track_mark(entry=entry, item=item, status=None) is None
    matrix = takvim.track_matrix(calendar)
    assert matrix["rows"][0]["cells"][0]["status"] is None


# ===========================================================================
# API uçları (duman)
# ===========================================================================


def test_api_takvim_akisi() -> None:
    guz, _ = _iki_donem()
    sube(9, "A", students=2, start_no=101)
    course = ders("Coğrafya", levels=[9])
    client = APIClient()

    olustur = client.post(
        "/api/v1/exam-calendars/",
        {"semester": guz.pk, "round": 1, "start_date": "2026-10-26", "end_date": "2026-11-06"},
        format="json",
    )
    assert olustur.status_code == 201
    cal_id = olustur.data["id"]
    assert olustur.data["name"] == "1. Dönem 1. Sınav Takvimi"
    assert olustur.data["school_year_name"] == "2026-2027"

    ekle = client.post(
        f"/api/v1/exam-calendars/{cal_id}/entries/",
        {"course": course.pk, "level": 9},
        format="json",
    )
    assert ekle.status_code == 201
    entry_id = ekle.data["id"]
    listesi = client.get(f"/api/v1/exam-calendars/{cal_id}/entries/")
    assert listesi.status_code == 200 and len(listesi.data["results"]) == 1

    yerlestir = client.post(
        f"/api/v1/exam-calendar-entries/{entry_id}/place/",
        {"date": "2026-10-27", "period_no": 1},
        format="json",
    )
    assert yerlestir.status_code == 200 and yerlestir.data["warnings"] == []

    grid = client.get(f"/api/v1/exam-calendars/{cal_id}/grid/")
    assert grid.status_code == 200 and "2026-10-27|1|9" in grid.data["cells"]

    pdf = client.get(f"/api/v1/exam-calendars/{cal_id}/pdf/")
    assert pdf.status_code == 200 and pdf["Content-Type"] == "application/pdf"

    assert client.post(f"/api/v1/exam-calendars/{cal_id}/submit/").status_code == 200
    onay = client.post(f"/api/v1/exam-calendars/{cal_id}/approve/", {}, format="json")
    assert onay.status_code == 200 and onay.data["status"] == "APPROVED"

    uret = client.post(
        f"/api/v1/exam-calendars/{cal_id}/create-session/",
        {"date": "2026-10-27", "period_no": 1},
        format="json",
    )
    assert uret.status_code == 201 and uret.data["session_id"] > 0
