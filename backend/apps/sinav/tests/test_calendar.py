"""F6 sınav takvimi testleri — OYS takvim çekirdeğinin KS kabulü.

Kapı (tasarım §12 F6): PENCERE HESABI senaryoları (ayın son Pazartesisi + 11
gün; dönem sınırına kırpma; tur 3 = son iki hafta) + ÖĞRENCİ-BAZLI GÜNLÜK
LİMİT senaryoları (3. sınav = uyarı, ≥4 = sert hata; kayıt verisi olmayan
ders seviyenin tamamı — konservatif düşüş, risk #4). Ek: durum makinesi +
damgalar (B12/risk #10), slot→oturum, havuz doldurma, A4 YATAY PDF + TASLAK
filigranı + TR duman. Ek (30.08.2026): hazırlayan makam ayrımı (üst makam
sınav gününe okul sınavı = uyarı), düzenlenebilir dipnot ve imza bloğunun
seçilen zümrelerden üretimi (B7 revizyonu).
"""

from __future__ import annotations

import io
import re
from datetime import date, time, timedelta
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.dersler.models import CourseExamMode, CourseType
from apps.okul.models import (
    ClassSection,
    Personnel,
    SchoolConfig,
    SchoolTerm,
    SubjectDepartment,
)
from apps.okul.services import sections
from apps.sinav import services_calendar as takvim
from apps.sinav.models import (
    ExamAuthority,
    ExamCalendar,
    ExamCalendarEntry,
    ExamCalendarStatus,
    ExamSession,
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


def _takvim(round_: int = 1, semester: SchoolTerm | None = None) -> ExamCalendar:
    """Takvim kurucusu — pencere sabit, tur değişken (tohumlama testleri için)."""
    guz = semester or _iki_donem()[0]
    return takvim.create_exam_calendar(
        semester_id=guz.pk,
        round=round_,
        start_date=date(2026, 10, 26),
        end_date=date(2026, 11, 6),
    )


def test_fill_pool_katalogdan_ogrencili_seviyelerle() -> None:
    """Havuz = ZORUNLU+YAZILI katalog × (ders seviyeleri ∩ öğrencisi olan seviyeler)."""
    guz, _ = _iki_donem()
    sube(9, "A", students=2, start_no=101)  # yalnız 9. seviyede öğrenci var
    course = ders("Coğrafya", levels=[9, 10])
    # Takvim yaratılırken havuz zaten tohumlanır; buradaki çağrı tohumun
    # İDEMPOTENT olduğunu ve süzgecin aynı çifti verdiğini gösterir.
    calendar = _takvim(round_=1, semester=guz)
    result = takvim.fill_calendar_pool(calendar)
    labels = result["existed"]
    assert result["created"] == []
    assert any("Coğrafya" in etiket and "9. Sınıf" in etiket for etiket in labels)
    assert not any("10. Sınıf" in etiket for etiket in labels)  # 10'da öğrenci yok
    assert ExamCalendarEntry.objects.filter(calendar=calendar, course=course, level=9).exists()


def test_fill_pool_yalniz_zorunlu_ve_yazili_dersleri_ceker() -> None:
    """Seçmeli · uygulama sınavı · sınavsız dersler otomatik havuza GİRMEZ.

    Kullanıcı geri bildirimi (31.08.2026): tüm katalog basılınca idareci
    ~175 satırdan ~30'a inene dek tek tek siliyordu. Süzgeç artık
    (COMMON, WRITTEN) ikilisidir; kalanlar seçim diyaloğundan ya da elle
    ekleme formundan gelir.
    """
    guz, _ = _iki_donem()
    sube(9, "A", students=2, start_no=101)
    ders("Matematik", levels=[9])  # zorunlu + yazılı → havuza girer
    ders("Astronomi ve Uzay Bilimleri", levels=[9], course_type=CourseType.ELECTIVE)
    ders("Beden Eğitimi ve Spor", levels=[9], exam_mode=CourseExamMode.PRACTICE)
    ders("Rehberlik ve Yönlendirme", levels=[9], exam_mode=CourseExamMode.NONE)

    calendar = _takvim(round_=1, semester=guz)
    adlar = set(
        ExamCalendarEntry.objects.filter(calendar=calendar).values_list("course__name", flat=True)
    )
    assert adlar == {"Matematik"}


def test_takvim_yaratilinca_havuz_tohumlanir_tur3_bos_kalir() -> None:
    """Round 1/2 havuzu kendiliğinden dolar; round 3 (elle doldurulan) BOŞ kalır."""
    guz, bahar = _iki_donem()
    sube(9, "A", students=2, start_no=101)
    ders("Matematik", levels=[9])

    birinci = _takvim(round_=1, semester=guz)
    assert ExamCalendarEntry.objects.filter(calendar=birinci).count() == 1

    ucuncu = _takvim(round_=3, semester=guz)
    assert ExamCalendarEntry.objects.filter(calendar=ucuncu).count() == 0
    assert bahar.pk is not None


def test_tohumlama_hatasi_takvim_yaratmayi_dusurmez(monkeypatch: pytest.MonkeyPatch) -> None:
    """Havuz tohumlama bir KOLAYLIKTIR: patlarsa takvim yine yaratılır (hata yutulur)."""
    guz, _ = _iki_donem()
    sube(9, "A", students=2, start_no=101)
    ders("Matematik", levels=[9])

    def _patla(_calendar: ExamCalendar) -> dict[str, object]:
        raise ValidationError("tohumlama patladı")

    monkeypatch.setattr(takvim, "fill_calendar_pool", _patla)
    calendar = _takvim(round_=1, semester=guz)
    assert calendar.pk is not None and calendar.status == ExamCalendarStatus.DRAFT
    assert ExamCalendarEntry.objects.filter(calendar=calendar).count() == 0


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

    # Ders takvimden SONRA yaratılır: takvim yaratılışında havuz zorunlu
    # derslerle kendiliğinden tohumlanıyor (bkz.
    # test_takvim_yaratilinca_havuz_tohumlanir_tur3_bos_kalir) — elle ekleme
    # yolu bu akışta ayrıca sınanmalı.
    course = ders("Coğrafya", levels=[9])
    ekle = client.post(
        f"/api/v1/exam-calendars/{cal_id}/entries/",
        {"course": course.pk, "level": 9},
        format="json",
    )
    assert ekle.status_code == 201
    assert ekle.data["participant_type"] == "LEVEL"
    assert ekle.data["participant_label"] == "Seviye geneli"
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


# ===========================================================================
# Hazırlayan makam + dipnot + imza zümreleri (F6 eki)
# ===========================================================================


def test_hazirlayan_makam_varsayilan_okul_ve_gecersiz_deger_reddedilir() -> None:
    calendar = _havuzlu_takvim(course_count=1)
    entry = ExamCalendarEntry.objects.filter(calendar=calendar).first()
    assert entry is not None and entry.authority == ExamAuthority.SCHOOL

    with pytest.raises(ValidationError, match="hazırlayan makam"):
        takvim.update_calendar_entry(entry, authority="BELEDIYE")

    course = ders("İl Geneli Matematik", levels=[9])
    with pytest.raises(ValidationError, match="hazırlayan makam"):
        takvim.add_calendar_entry(
            calendar=calendar, course_id=course.pk, level=9, authority="BELEDIYE"
        )


def test_makam_izgara_hucresine_ve_uyariya_dusuyor() -> None:
    """Üst makam sınavı hücrede görünür; aynı güne okul sınavı UYARI üretir."""
    calendar = _havuzlu_takvim(course_count=2)
    entries = list(ExamCalendarEntry.objects.filter(calendar=calendar).order_by("id"))
    takvim.update_calendar_entry(entries[0], authority=ExamAuthority.MINISTRY)
    gun = date(2026, 10, 27)

    takvim.place_entry(entries[0], on_date=gun, period_no=1)
    grid = takvim.calendar_grid(calendar)
    assert grid["cells"][f"{gun.isoformat()}|1|9"][0]["authority"] == "MINISTRY"

    # Okul sınavı aynı güne konunca uyarı (Yönerge md. 5) — yerleşir, engellenmez.
    sonuc = takvim.place_entry(entries[1], on_date=gun, period_no=2)
    assert any("üst makam" in w for w in sonuc.warnings)
    entries[1].refresh_from_db()
    assert entries[1].placed_date == gun
    # Aynı uyarı takvim doğrulamasının warnings kolunda da görünür.
    assert any("üst makam" in w for w in takvim.calendar_grid(calendar)["warnings"])


def test_dipnot_varsayilandan_kopyalanir_ve_duzenlenebilir() -> None:
    calendar = _havuzlu_takvim(course_count=1)
    assert calendar.footnote_text == takvim.DEFAULT_CALENDAR_FOOTNOTE
    assert "mazeret" in calendar.footnote_text and "kılavuz" in calendar.footnote_text

    takvim.update_exam_calendar(calendar, footnote_text="Kendi dipnotumuz.")
    calendar.refresh_from_db()
    assert calendar.footnote_text == "Kendi dipnotumuz."

    # Onaylı takvimde dipnot da kilitli (B12 — _ensure_draft tüm alanları kapsar).
    takvim.submit_calendar(calendar)
    takvim.approve_calendar(calendar)
    with pytest.raises(ValidationError, match="taslak"):
        takvim.update_exam_calendar(calendar, footnote_text="Sonradan değişmez.")


def test_imza_blogu_secilen_zumrelerden_basilir() -> None:
    """Zümre seçilirse başkan adları basılır; seçim yoksa B7 dalı (derslerden)."""
    SchoolConfig.objects.create(pk=SchoolConfig.SINGLETON_PK, principal_name="Örnek MÜDÜR")
    calendar = _havuzlu_takvim(course_count=1)

    def _pdf_metni() -> str:
        reader = PdfReader(io.BytesIO(takvim.render_calendar_pdf(calendar)))
        return "\n".join(p.extract_text() or "" for p in reader.pages)

    # Seçim yokken yedek dal: takvimdeki dersten imza çizgisi.
    assert "Ders 1 Zümre Başkanı" in _pdf_metni()

    baskan = Personnel.objects.create(first_name="Ayşe", last_name="ÇELİK", branch="Coğrafya")
    sosyal = SubjectDepartment.objects.create(name="Sosyal Bilimler", head=baskan)
    SubjectDepartment.objects.create(name="Çevre Bilimleri")
    calendar.signatory_departments.set(
        SubjectDepartment.objects.filter(name__in=["Sosyal Bilimler", "Çevre Bilimleri"])
    )

    imzalar = takvim._calendar_signatures(calendar)
    # Türk alfabesi sıralaması: 'Ç' < 'S' (kod noktası sırasında tersi olurdu).
    assert [c["role"] for c in imzalar["chairs"]] == [
        "Çevre Bilimleri Zümre Başkanı",
        "Sosyal Bilimler Zümre Başkanı",
    ]
    assert imzalar["chairs"][1]["name"] == "Ayşe ÇELİK"

    metin = _pdf_metni()
    assert "Sosyal Bilimler Zümre Başkanı" in metin and "Ayşe ÇELİK" in metin
    assert "Ders 1 Zümre Başkanı" not in metin  # seçim yedek dalı KAPATIR
    assert sosyal.head is not None


def test_pdf_makam_etiketi_ve_dipnotu_basiyor() -> None:
    SchoolConfig.objects.create(
        pk=SchoolConfig.SINGLETON_PK, school_name="Örnek Lisesi", principal_name="Örnek MÜDÜR"
    )
    calendar = _havuzlu_takvim(course_count=1)
    entry = ExamCalendarEntry.objects.filter(calendar=calendar).first()
    assert entry is not None
    takvim.update_calendar_entry(entry, authority=ExamAuthority.PROVINCIAL)
    takvim.place_entry(entry, on_date=date(2026, 10, 27), period_no=1)
    takvim.update_exam_calendar(calendar, footnote_text="Mazeret sınavları izleyen hafta yapılır.")

    reader = PdfReader(io.BytesIO(takvim.render_calendar_pdf(calendar)))
    metin = "\n".join(p.extract_text() or "" for p in reader.pages)
    assert "İL MEM SINAVI" in metin
    assert "DİPNOT" in metin and "Mazeret sınavları izleyen hafta yapılır." in metin
    assert "2026-2027 EĞİTİM ÖĞRETİM YILI" in metin  # dönem üzerinden ders yılı


def test_api_makam_dipnot_ve_imza_zumresi_sozlesmesi() -> None:
    guz, _ = _iki_donem()
    sube(9, "A", students=2, start_no=101)
    zumre = SubjectDepartment.objects.create(name="Sosyal Bilimler")
    client = APIClient()

    olustur = client.post(
        "/api/v1/exam-calendars/",
        {"semester": guz.pk, "round": 1, "start_date": "2026-10-26", "end_date": "2026-11-06"},
        format="json",
    )
    cal_id = olustur.data["id"]
    assert olustur.data["footnote_text"] == takvim.DEFAULT_CALENDAR_FOOTNOTE

    # Ders takvimden sonra: otomatik tohumlama aynı çifti önceden eklemesin.
    course = ders("Coğrafya", levels=[9])
    ekle = client.post(
        f"/api/v1/exam-calendars/{cal_id}/entries/",
        {"course": course.pk, "level": 9, "authority": "DISTRICT"},
        format="json",
    )
    assert ekle.status_code == 201 and ekle.data["authority"] == "DISTRICT"

    guncelle = client.patch(
        f"/api/v1/exam-calendars/{cal_id}/",
        {"footnote_text": "Yeni dipnot.", "signatory_departments": [zumre.pk]},
        format="json",
    )
    assert guncelle.status_code == 200
    assert guncelle.data["footnote_text"] == "Yeni dipnot."
    assert guncelle.data["signatory_departments"] == [zumre.pk]
    assert guncelle.data["signatory_department_names"] == ["Sosyal Bilimler"]

    varsayilan = client.get("/api/v1/exam-calendars/default-footnote/")
    assert varsayilan.status_code == 200 and "mazeret" in varsayilan.data["text"]


def test_iki_ust_makam_sinavi_ayni_gunde_uyari_uretmez() -> None:
    """Yönerge md. 5 yasağı OKUL–ÜST MAKAM çiftine ilişkin.

    İki Bakanlık/MEM sınavının aynı güne düşmesi maddenin konusu değildir —
    yerleştirme uyarısı ile doğrulama kolu bu noktada AYNI şeyi söylemelidir.
    """
    calendar = _havuzlu_takvim(course_count=2)
    entries = list(ExamCalendarEntry.objects.filter(calendar=calendar).order_by("id"))
    for entry in entries:
        takvim.update_calendar_entry(entry, authority=ExamAuthority.PROVINCIAL)
    gun = date(2026, 10, 27)

    takvim.place_entry(entries[0], on_date=gun, period_no=1)
    sonuc = takvim.place_entry(entries[1], on_date=gun, period_no=2)
    assert not any("üst makam" in w for w in sonuc.warnings)
    assert not any("üst makam" in w for w in takvim.calendar_grid(calendar)["warnings"])


def test_ayrilan_zumre_baskani_evrakta_basilmaz() -> None:
    """Personel silme SOFT'tur; ileri-FK süzgeç uygulamaz → ad elle elenir."""
    SchoolConfig.objects.create(pk=SchoolConfig.SINGLETON_PK, principal_name="Örnek MÜDÜR")
    calendar = _havuzlu_takvim(course_count=1)
    baskan = Personnel.objects.create(first_name="Ayşe", last_name="ÇELİK")
    zumre = SubjectDepartment.objects.create(name="Sosyal Bilimler", head=baskan)
    calendar.signatory_departments.set([zumre])
    assert takvim._calendar_signatures(calendar)["chairs"][0]["name"] == "Ayşe ÇELİK"

    baskan.delete()  # okuldan ayrıldı (soft delete)
    imzalar = takvim._calendar_signatures(calendar)
    assert imzalar["chairs"] == [{"name": "", "role": "Sosyal Bilimler Zümre Başkanı"}]
    reader = PdfReader(io.BytesIO(takvim.render_calendar_pdf(calendar)))
    metin = "\n".join(p.extract_text() or "" for p in reader.pages)
    assert "Sosyal Bilimler Zümre Başkanı" in metin and "Ayşe ÇELİK" not in metin


def test_cok_sayfali_takvim_ve_satir_bolunme_korumasi() -> None:
    """Çok sayfalı takvim bütün basılır + `tr { break-inside: avoid }` yerinde durur.

    Hücre içeriği makam etiketi için BLOK kutu oldu; blok kutular satır içinde
    sayfa kırılma noktası yaratır ve `documents/base.html`in `.doc-table`
    kuralında bu koruma YOKTUR (kardeş şablon `sinav/reports/base.html`de var).
    30.08.2026'da ÖLÇÜLDÜ: kural kaldırılınca 12 günlük/4 seviyeli bir takvimde
    ikinci sayfa, tarih sütunu boş kalmış bir ders satırıyla başlıyordu — sınav
    resmî evrakta tarihsiz görünüyordu.

    Bölünmenin hangi satıra denk geleceği sayfa aritmetiğine bağlı olduğundan
    davranış testi kırılgandır; koruma bu yüzden ŞABLON TARAMASIYLA sabitlenir
    (`test_reports.test_sablonlarda_text_transform_yasak` emsali). Ek olarak
    çok sayfalı belgenin bütünlüğü (her ders TAM BİR kez) burada denetlenir.
    """
    from pathlib import Path

    sablon = Path(__file__).resolve().parents[3] / "templates/sinav/calendar_pdf.html"
    assert re.search(
        r"\.doc-table\s+tr\s*\{[^}]*break-inside:\s*avoid", sablon.read_text("utf-8")
    ), (
        "calendar_pdf.html'de `.doc-table tr { break-inside: avoid }` kuralı yok — "
        "uzun takvimde satır sayfa sınırında bölünür."
    )

    SchoolConfig.objects.create(
        pk=SchoolConfig.SINGLETON_PK, school_name="Örnek Lisesi", principal_name="Örnek MÜDÜR"
    )
    calendar = _havuzlu_takvim(course_count=0)
    for lvl in (10, 11, 12):
        sube(lvl, "A", students=1, start_no=lvl * 100)
    adlar: list[str] = []
    for i in range(12):
        gun = date(2026, 10, 26) + timedelta(days=i)
        for lvl in (9, 10, 11, 12):
            for k in (1, 2):  # aynı hücrede iki sınav → hücre yükselir
                ad = f"Deneme {i}-{lvl}-{k}"
                adlar.append(ad)
                course = ders(ad, levels=[lvl])
                entry = takvim.add_calendar_entry(
                    calendar=calendar,
                    course_id=course.pk,
                    level=lvl,
                    authority=ExamAuthority.MINISTRY if k == 1 else ExamAuthority.SCHOOL,
                )
                takvim.place_entry(entry, on_date=gun, period_no=1)
    # İmza bloğu seçilen zümreden gelsin — yedek dal her ders için imza satırı basar.
    calendar.signatory_departments.set([SubjectDepartment.objects.create(name="Sosyal Bilimler")])

    reader = PdfReader(io.BytesIO(takvim.render_calendar_pdf(calendar)))
    assert len(reader.pages) >= 2, "senaryo çok sayfalı olmalı, aksi hâlde test bir şey ölçmez"
    metin = "\n".join(p.extract_text() or "" for p in reader.pages)
    eksik = [ad for ad in adlar if metin.count(ad) != 1]
    assert not eksik, f"Çok sayfalı takvimde bir kez basılmayan dersler: {eksik[:5]}"
    # Devam sayfaları tablo başlığından hemen sonra TARİHSİZ ders satırıyla başlamamalı.
    for sayfa_no, page in enumerate(reader.pages[1:], start=2):
        satirlar = [ln for ln in (page.extract_text() or "").splitlines() if ln.strip()]
        basliklar = [i for i, ln in enumerate(satirlar) if ln.startswith("Tarih / Ders Saati")]
        if not basliklar:
            continue  # tablo bitmiş (açıklama/dipnot/imza sayfası)
        ilk_govde = satirlar[basliklar[0] + 1]
        assert "Deneme" not in ilk_govde, (
            f"Sayfa {sayfa_no} tablo başlığından sonra tarihsiz ders satırıyla başlıyor "
            f"(satır bölünmüş): {ilk_govde!r}"
        )


# ===========================================================================
# Katılımcı kapsamı + toplu ekleme + seçmeli seçim (31.08.2026 sadeleştirmesi)
# ===========================================================================


def _secmeli_takvim() -> tuple[ExamCalendar, int, int]:
    """9/A + 9/B şubeli takvim + bir SEÇMELİ yazılı ders → (takvim, ders_pk, 9/A pk)."""
    guz, _ = _iki_donem()
    a = sube(9, "A", students=2, start_no=101)
    sube(9, "B", students=3, start_no=201)
    calendar = _takvim(round_=1, semester=guz)
    secmeli = ders("Astronomi ve Uzay Bilimleri", levels=[9], course_type=CourseType.ELECTIVE)
    return calendar, secmeli.pk, a.pk


def test_sube_kapsami_kaydedilir_ve_baska_seviyenin_subesi_reddedilir() -> None:
    """SECTIONS kapsamı somut şube pk'leriyle yazılır; seviye dışı şube REDDEDİLİR."""
    calendar, ders_pk, a_pk = _secmeli_takvim()
    onbir = sube(11, "A", students=2, start_no=301)

    entry = takvim.add_calendar_entry(
        calendar=calendar,
        course_id=ders_pk,
        level=9,
        participant_type="SECTIONS",
        section_ids=[a_pk, a_pk],  # yinelenen id sessizce teklenir
    )
    assert entry.participant_type == "SECTIONS" and entry.section_ids == [a_pk]

    # Başka seviyenin şubesi: Türkçe hata, girdi yazılmaz.
    baska = ders("Seçmeli Fizik", levels=[9], course_type=CourseType.ELECTIVE)
    with pytest.raises(ValidationError, match="seviyesinde değil"):
        takvim.add_calendar_entry(
            calendar=calendar,
            course_id=baska.pk,
            level=9,
            participant_type="SECTIONS",
            section_ids=[onbir.pk],
        )
    assert not ExamCalendarEntry.objects.filter(calendar=calendar, course=baska).exists()

    # Boş şube listesi de reddedilir (oturum tarafıyla aynı cümle).
    with pytest.raises(ValidationError, match="en az bir şube seçin"):
        takvim.add_calendar_entry(
            calendar=calendar,
            course_id=baska.pk,
            level=9,
            participant_type="SECTIONS",
            section_ids=[],
        )


def test_kapsam_guncellemesi_level_donusunde_sube_listesini_temizler() -> None:
    """Tip LEVEL'e döndürülünce eski şube seçimi kalıntı bırakmaz."""
    calendar, ders_pk, a_pk = _secmeli_takvim()
    entry = takvim.add_calendar_entry(
        calendar=calendar,
        course_id=ders_pk,
        level=9,
        participant_type="SECTIONS",
        section_ids=[a_pk],
    )
    takvim.update_calendar_entry(entry, participant_type="LEVEL")
    entry.refresh_from_db()
    assert entry.participant_type == "LEVEL" and entry.section_ids == []

    with pytest.raises(ValidationError, match="Geçersiz katılımcı tipi"):
        takvim.update_calendar_entry(entry, participant_type="GROUPS")


def test_bulk_entries_idempotent_ve_reddedileni_raporlar() -> None:
    """Toplu ekleme: yeni → created, var olan → existed, geçersiz → skipped."""
    calendar, ders_pk, a_pk = _secmeli_takvim()
    ikinci = ders("Seçmeli Kimya", levels=[9], course_type=CourseType.ELECTIVE)
    onbir = sube(11, "A", students=2, start_no=301)

    sonuc = takvim.add_calendar_entries_bulk(
        calendar,
        [
            {
                "course_id": ders_pk,
                "level": 9,
                "participant_type": "SECTIONS",
                "section_ids": [a_pk],
            },
            {"course_id": ikinci.pk, "level": 9},
            # Ders 11. seviyede okutulmuyor → skipped (koşunun kalanı sürer).
            {
                "course_id": ikinci.pk,
                "level": 11,
                "participant_type": "SECTIONS",
                "section_ids": [onbir.pk],
            },
            {"level": 9},  # ders kimliği yok
        ],
    )
    assert len(sonuc["created"]) == 2
    assert sonuc["existed"] == []
    assert len(sonuc["skipped"]) == 2
    assert any("okutulmuyor" in s for s in sonuc["skipped"])
    assert any("ders ve seviye zorunlu" in s for s in sonuc["skipped"])

    # İdempotent: aynı kalemler ikinci koşuda existed'a düşer, hata üretmez.
    tekrar = takvim.add_calendar_entries_bulk(
        calendar,
        [
            {
                "course_id": ders_pk,
                "level": 9,
                "participant_type": "SECTIONS",
                "section_ids": [a_pk],
            },
            {"course_id": ikinci.pk, "level": 9},
        ],
    )
    assert tekrar["created"] == [] and len(tekrar["existed"]) == 2


def test_elective_options_in_pool_bayragi_ve_tr_siralama() -> None:
    """Seçmeli seçenekleri seviye bazlı gelir; havuzdaki ders işaretli, sıra TR."""
    guz, _ = _iki_donem()
    sube(9, "A", students=2, start_no=101)
    calendar = _takvim(round_=1, semester=guz)
    ders("Zooloji", levels=[9], course_type=CourseType.ELECTIVE)
    cince = ders("Çince", levels=[9], course_type=CourseType.ELECTIVE)
    ders("Sosyoloji", levels=[9], course_type=CourseType.ELECTIVE)
    ders("Matematik", levels=[9])  # ZORUNLU — seçmeli listesinde görünmemeli
    ders(
        "Görsel Sanatlar",
        levels=[9],
        course_type=CourseType.ELECTIVE,
        exam_mode=CourseExamMode.PRACTICE,
    )  # uygulama sınavı — seçmeli listesinde görünmemeli

    seviyeler = takvim.elective_pool_options(calendar)
    assert [s["value"] for s in seviyeler] == [9]
    assert seviyeler[0]["display_label"] == "9. Sınıf"
    adlar = [c["name"] for c in seviyeler[0]["courses"]]
    # TR alfabesi: Ç < S < Z (BINARY sırada 'Çince' Z'den sonraya düşerdi).
    assert adlar == ["Çince", "Sosyoloji", "Zooloji"]
    assert all(c["in_pool"] is False for c in seviyeler[0]["courses"])

    takvim.add_calendar_entry(calendar=calendar, course_id=cince.pk, level=9)
    guncel = takvim.elective_pool_options(calendar)[0]["courses"]
    assert [c["in_pool"] for c in guncel if c["name"] == "Çince"] == [True]


def test_create_session_from_slot_kapsami_tasir() -> None:
    """Havuzdaki şube kapsamı üretilen ExamSessionCourse'a AYNEN geçer."""
    calendar, ders_pk, a_pk = _secmeli_takvim()
    salon("9-A Dersliği")
    entry = takvim.add_calendar_entry(
        calendar=calendar,
        course_id=ders_pk,
        level=9,
        participant_type="SECTIONS",
        section_ids=[a_pk],
    )
    gun = date(2026, 10, 27)
    takvim.place_entry(entry, on_date=gun, period_no=1)
    takvim.submit_calendar(calendar)
    takvim.approve_calendar(calendar)

    session = takvim.create_session_from_slot(calendar, on_date=gun, period_no=1)
    sc = session.courses.get(course_id=ders_pk)
    assert sc.participant_type == "SECTIONS"
    assert sc.section_ids == [a_pk]
    assert sc.level == 9


def _kapsami_silinmis_onayli_takvim() -> tuple[ExamCalendar, date, ExamCalendarEntry, int]:
    """Onaylı takvim: aynı slotta bir SEVİYE girdisi + şubesi SİLİNMİŞ bir ŞUBE girdisi."""
    calendar, ders_pk, a_pk = _secmeli_takvim()
    salon("9-A Dersliği")
    seviye_dersi = ders("Matematik", levels=[9])
    seviye_girdisi = takvim.add_calendar_entry(
        calendar=calendar, course_id=seviye_dersi.pk, level=9
    )
    sube_girdisi = takvim.add_calendar_entry(
        calendar=calendar,
        course_id=ders_pk,
        level=9,
        participant_type="SECTIONS",
        section_ids=[a_pk],
    )
    gun = date(2026, 10, 27)
    takvim.place_entry(seviye_girdisi, on_date=gun, period_no=1)
    takvim.place_entry(sube_girdisi, on_date=gun, period_no=1)
    takvim.submit_calendar(calendar)
    takvim.approve_calendar(calendar)
    # Onaydan SONRA şube silinir (soft) — girdi artık düzenlenemez.
    sections.delete_class_section(ClassSection.objects.get(pk=a_pk))
    return calendar, gun, sube_girdisi, seviye_dersi.pk


def test_silinmis_sube_slotun_tamamini_kilitlemez() -> None:
    """Kapsamı silinmiş girdi ATLANIR; slottaki sağlam ders yine üretilir."""
    calendar, gun, sube_girdisi, seviye_ders_pk = _kapsami_silinmis_onayli_takvim()

    session = takvim.create_session_from_slot(calendar, on_date=gun, period_no=1)

    assert [sc.course_id for sc in session.courses.all()] == [seviye_ders_pk]
    # Atlanan girdi oturuma BAĞLANMAZ: şube geri açılınca yeniden üretilebilir.
    sube_girdisi.refresh_from_db()
    assert sube_girdisi.session_id is None


def test_kapsami_tumuyle_silinmis_slotta_oksuz_oturum_kalmaz() -> None:
    """Tek girdi ve o da kapsamsızsa: Türkçe hata + geride ExamSession KALMAZ."""
    calendar, ders_pk, a_pk = _secmeli_takvim()
    salon("9-A Dersliği")
    entry = takvim.add_calendar_entry(
        calendar=calendar,
        course_id=ders_pk,
        level=9,
        participant_type="SECTIONS",
        section_ids=[a_pk],
    )
    gun = date(2026, 10, 27)
    takvim.place_entry(entry, on_date=gun, period_no=1)
    takvim.submit_calendar(calendar)
    takvim.approve_calendar(calendar)
    sections.delete_class_section(ClassSection.objects.get(pk=a_pk))

    with pytest.raises(ValidationError, match="şube kapsamı silinmiş"):
        takvim.create_session_from_slot(calendar, on_date=gun, period_no=1)
    assert ExamSession.objects.count() == 0
    entry.refresh_from_db()
    assert entry.session_id is None


def test_dogrulama_silinmis_kapsam_subesini_uyarir() -> None:
    """Kayıp şube sessizce düşmez: doğrulama kalıcı uyarı basar (önizleme 0 sayar)."""
    calendar, gun, sube_girdisi, _ = _kapsami_silinmis_onayli_takvim()

    uyarilar = takvim.calendar_validation(calendar)["warnings"]
    assert any("şube silinmiş" in u and "Astronomi ve Uzay Bilimleri" in u for u in uyarilar)
    # Uyarı ERRORS değildir — takvim bloklanmaz (idari düzeltme işi).
    assert takvim.calendar_validation(calendar)["errors"] == []
    assert takvim.entry_participant_preview(calendar)[sube_girdisi.pk]["student_count"] == 0


def test_katilimci_onizlemesi_sube_kapsamini_sayar() -> None:
    """SECTIONS girdide önizleme seçilen şubelerin öğrencisini sayar (seviyeyi DEĞİL)."""
    calendar, ders_pk, a_pk = _secmeli_takvim()  # 9/A: 2 öğrenci, 9/B: 3 öğrenci
    seviye_dersi = ders("Matematik", levels=[9])
    seviye_girdisi = takvim.add_calendar_entry(
        calendar=calendar, course_id=seviye_dersi.pk, level=9
    )
    sube_girdisi = takvim.add_calendar_entry(
        calendar=calendar,
        course_id=ders_pk,
        level=9,
        participant_type="SECTIONS",
        section_ids=[a_pk],
    )

    onizleme = takvim.entry_participant_preview(calendar)
    assert onizleme[sube_girdisi.pk]["student_count"] == 2
    assert onizleme[sube_girdisi.pk]["whole"] is False
    assert onizleme[sube_girdisi.pk]["groups"] == ["9/A (2)"]
    # Seviye geneli girdi eski davranışta: seviyenin tamamı (2 + 3).
    assert onizleme[seviye_girdisi.pk]["student_count"] == 5
    assert onizleme[seviye_girdisi.pk]["whole"] is True


def test_izgara_hucresi_kapsam_etiketini_tasir() -> None:
    """Hücre ANAHTARI biçimi sabit; hücre sözlüğüne kapsam alanları eklendi (§3)."""
    calendar, ders_pk, a_pk = _secmeli_takvim()
    entry = takvim.add_calendar_entry(
        calendar=calendar,
        course_id=ders_pk,
        level=9,
        participant_type="SECTIONS",
        section_ids=[a_pk],
    )
    gun = date(2026, 10, 27)
    takvim.place_entry(entry, on_date=gun, period_no=1)

    grid = takvim.calendar_grid(calendar)
    hucre = grid["cells"][f"{gun.isoformat()}|1|9"][0]
    assert hucre["participant_type"] == "SECTIONS"
    assert hucre["section_ids"] == [a_pk]
    assert hucre["participant_label"] == "1 şube"
    assert [s["display_label"] for s in grid["levels"] if s["value"] == 9] == ["9. Sınıf"]


def test_api_toplu_ekleme_ve_secmeli_secenekleri() -> None:
    """Yeni uçlar: POST bulk-entries + GET elective-options (url_path çakışması yok)."""
    guz, _ = _iki_donem()
    a = sube(9, "A", students=2, start_no=101)
    client = APIClient()
    olustur = client.post(
        "/api/v1/exam-calendars/",
        {"semester": guz.pk, "round": 1, "start_date": "2026-10-26", "end_date": "2026-11-06"},
        format="json",
    )
    cal_id = olustur.data["id"]
    secmeli = ders("Çince", levels=[9], course_type=CourseType.ELECTIVE)

    secenekler = client.get(f"/api/v1/exam-calendars/{cal_id}/elective-options/")
    assert secenekler.status_code == 200
    assert secenekler.data["results"][0]["courses"][0]["name"] == "Çince"
    assert secenekler.data["results"][0]["courses"][0]["in_pool"] is False

    toplu = client.post(
        f"/api/v1/exam-calendars/{cal_id}/bulk-entries/",
        {
            "items": [
                {
                    "course_id": secmeli.pk,
                    "level": 9,
                    "participant_type": "SECTIONS",
                    "section_ids": [a.pk],
                }
            ]
        },
        format="json",
    )
    assert toplu.status_code == 200 and len(toplu.data["created"]) == 1

    listesi = client.get(f"/api/v1/exam-calendars/{cal_id}/entries/")
    satir = listesi.data["results"][0]
    assert satir["participant_type"] == "SECTIONS"
    assert satir["section_ids"] == [a.pk]
    assert satir["participant_label"] == "1 şube"

    # PATCH ile kapsam seviye geneline döner (şube listesi temizlenir).
    duzelt = client.patch(
        f"/api/v1/exam-calendar-entries/{satir['id']}/",
        {"participant_type": "LEVEL"},
        format="json",
    )
    assert duzelt.status_code == 200
    assert duzelt.data["participant_type"] == "LEVEL"
    assert duzelt.data["section_ids"] == []
    assert duzelt.data["participant_label"] == "Seviye geneli"

    # Boş liste ile SECTIONS reddi 400 (500 değil) — Türkçe mesaj servisten.
    hata = client.patch(
        f"/api/v1/exam-calendar-entries/{satir['id']}/",
        {"participant_type": "SECTIONS", "section_ids": []},
        format="json",
    )
    assert hata.status_code == 400
