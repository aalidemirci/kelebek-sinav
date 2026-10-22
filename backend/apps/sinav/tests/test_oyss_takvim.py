"""OYSS uygulama takvimi testleri (22.10.2026).

Bakanlığın "Okul Geneli Ortak Yazılı Sınav Uygulama Takvimi" (Ortak Yazılı Sınav
Sistemi, 2026-2027 1. dönem 1. yazılı) sınav GÜNÜNÜ ve ders saati KURALINI verir:
günde tek sınav 2. ders saatinde, iki sınav 2. ve 4. ders saatlerinde; 10 Kasım'da
4. ders saati. Program sınavı resmî gün + saate SABİTLER, girdi OKUL sınavı kalır
(ülke geneli sınavdan farkı), saati idareci değiştirir. Metin:
docs/mevzuat/meb-2026-2027-oyss.md.
"""

from __future__ import annotations

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.dersler.models import Course, CourseType
from apps.okul.models import ClassSection, SchoolConfig
from apps.sinav import services_calendar as takvim
from apps.sinav.models import (
    ExamAuthority,
    ExamCalendar,
    ExamCalendarEntry,
    ParticipantType,
)
from apps.sinav.official_windows import official_window, oyss_schedule
from apps.sinav.tests.oturum_yardim import ders, donem, sube

pytestmark = pytest.mark.django_db

#: Bakanlığın 1. yazılı haftası (ÖDSHGM 10.09.2026) — OYSS günleri bunun içinde.
HAFTA = (date(2026, 11, 2), date(2026, 11, 13))


def _okul(*duzeyler: int) -> dict[int, ClassSection]:
    """Anadolu lisesi ayarı (sınav saatleri 1-6) + her düzeyde öğrencili bir şube."""
    SchoolConfig.objects.create(pk=SchoolConfig.SINGLETON_PK, exam_period_nos=[1, 2, 3, 4, 5, 6])
    return {duzey: sube(duzey, "A", students=2, start_no=duzey * 100) for duzey in duzeyler}


def _takvim(pencere: tuple[date, date] = HAFTA, round_: int = 1) -> ExamCalendar:
    """1. dönem takvimi — yaratılırken havuz tohumlanır ve Bakanlık takvimleri uygulanır."""
    bas, bit = pencere
    return takvim.create_exam_calendar(
        semester_id=donem().pk, round=round_, start_date=bas, end_date=bit
    )


def _yer(calendar: ExamCalendar, course: Course, level: int) -> tuple[date | None, int | None]:
    girdi = ExamCalendarEntry.objects.get(calendar=calendar, course=course, level=level)
    return girdi.placed_date, girdi.period_no


def _plan(calendar: ExamCalendar) -> dict[tuple[int, str], dict[str, object]]:
    return {(s["level"], s["course_name"]): s for s in takvim.oyss_plan(calendar)}


def test_oyss_verisi_uygulama_takvimiyle_birebir() -> None:
    oyss = oyss_schedule(2026, 1, 1)
    assert oyss is not None
    lise = [(e.course_name, e.on_date.day) for e in oyss.exams if e.levels == (9, 10, 11)]
    assert lise == [  # Tablo 2 — sıra korunur (aynı gün iki sınavda ilk satır 2. saate)
        ("Biyoloji", 3),
        ("Kimya", 4),
        ("Tarih", 4),
        ("Matematik", 5),
        ("Fizik", 6),
        ("Felsefe", 6),
        ("Coğrafya", 10),
        ("Türk Dili ve Edebiyatı", 11),
        ("Din Kültürü ve Ahlak Bilgisi", 11),
        ("İngilizce", 13),
    ]
    ortaokul = [(e.course_name, e.on_date.day) for e in oyss.exams if e.levels == (5, 6, 7)]
    assert ortaokul == [
        ("Fen Bilimleri", 3),
        ("Matematik", 5),
        ("Sosyal Bilgiler", 6),
        ("Türkçe", 10),
        ("İngilizce", 12),
        ("Din Kültürü ve Ahlak Bilgisi", 13),
    ]
    assert all(e.on_date.year == 2026 and e.on_date.month == 11 for e in oyss.exams)
    assert oyss.excluded == {(7, "İngilizce"), (11, "İngilizce")}
    assert oyss.periods_for(date(2026, 11, 3), 1) == (2,)
    assert oyss.periods_for(date(2026, 11, 4), 2) == (2, 4)
    assert oyss.periods_for(date(2026, 11, 10), 1) == (4,)  # "4. ders saatinde uygulanabilecektir"
    assert oyss.duration_minutes == 40
    assert (oyss.makeup_start, oyss.makeup_end) == (date(2026, 11, 23), date(2026, 11, 27))
    # Bütün günler Bakanlığın ilan ettiği haftada ve hafta içinde.
    hafta = official_window(2026, 1, 1)
    assert hafta is not None
    assert all(hafta.start <= e.on_date <= hafta.end for e in oyss.exams)
    assert all(e.on_date.weekday() < 5 for e in oyss.exams)
    # Öteki turların takvimi yayımlanmadı.
    assert oyss_schedule(2026, 1, 2) is None
    assert oyss_schedule(2027, 1, 1) is None


def test_takvim_yaratilinca_oyss_sinavlari_resmi_gun_ve_saate_sabitlenir() -> None:
    _okul(9, 10)
    biyoloji = ders("Biyoloji", levels=[9, 10])
    kimya = ders("Kimya", levels=[9, 10])
    tarih = ders("Tarih", levels=[9, 10, 11])

    calendar = _takvim()

    girdi = ExamCalendarEntry.objects.get(calendar=calendar, course=biyoloji, level=9)
    assert (girdi.placed_date, girdi.period_no) == (date(2026, 11, 3), 2)
    assert girdi.is_pinned is True
    assert girdi.authority == ExamAuthority.SCHOOL  # OYSS okul sınavıdır, üst makam değil
    assert girdi.note == takvim.OYSS_NOTE
    # 4 Kasım iki sınavlı gün: tablo sırasıyla Kimya 2., Tarih 4. ders saati.
    for duzey in (9, 10):
        assert _yer(calendar, kimya, duzey) == (date(2026, 11, 4), 2)
        assert _yer(calendar, tarih, duzey) == (date(2026, 11, 4), 4)
    plan = _plan(calendar)
    assert plan[(9, "Biyoloji")]["status"] == "placed"
    assert plan[(9, "Biyoloji")]["weekday_label"] == "Salı"
    assert plan[(9, "Matematik")]["status"] == "missing_course"  # havuzda yok
    assert (11, "Tarih") not in plan  # 11. sınıfta öğrenci yok


def test_dokuzuncu_sinifta_felsefe_yoksa_fizik_tek_sinav_sayilir() -> None:
    _okul(9, 10)
    fizik = ders("Fizik", levels=[9, 10])
    felsefe = ders("Felsefe", levels=[10, 11])

    calendar = _takvim()

    assert _yer(calendar, fizik, 9) == (date(2026, 11, 6), 2)  # tek sınav → 2. saat
    assert _yer(calendar, fizik, 10) == (date(2026, 11, 6), 2)
    assert _yer(calendar, felsefe, 10) == (date(2026, 11, 6), 4)  # iki sınav → 2. ve 4.


def test_10_kasimdaki_sinav_dorduncu_ders_saatine_konur() -> None:
    _okul(9)
    cografya = ders("Coğrafya", levels=[9, 10])

    calendar = _takvim()

    assert _yer(calendar, cografya, 9) == (date(2026, 11, 10), 4)
    notlar = takvim.oyss_band(calendar)["oyss_info"]["notes"]
    assert any(n.startswith("10.11.2026 Salı günkü sınav 4. ders saatinde") for n in notlar)


def test_ingilizce_yabanci_dile_baglanir_11_haric_10_tde_ulke_geneline_kalir() -> None:
    _okul(9, 10, 11)
    dil = ders("Birinci Yabancı Dil", levels=[9, 10, 11, 12])
    tde = ders("Türk Dili ve Edebiyatı", levels=[9, 10, 11, 12])
    dkab = ders("Din Kültürü ve Ahlak Bilgisi", levels=[9, 10, 11, 12])

    calendar = _takvim()

    assert _yer(calendar, dil, 9) == (date(2026, 11, 13), 2)
    assert _yer(calendar, dil, 10) == (date(2026, 11, 13), 2)
    assert _yer(calendar, dil, 11) == (None, None)  # 11. sınıf İngilizce OYSS dışı
    # 11 Kasım: 9 ve 11'de TDE + DKAB iki sınav; 10'da TDE ülke geneli → DKAB tek sınav.
    for duzey in (9, 11):
        assert _yer(calendar, tde, duzey) == (date(2026, 11, 11), 2)
        assert _yer(calendar, dkab, duzey) == (date(2026, 11, 11), 4)
    assert _yer(calendar, dkab, 10) == (date(2026, 11, 11), 2)
    ulke = ExamCalendarEntry.objects.get(calendar=calendar, course=tde, level=10)
    assert ulke.authority == ExamAuthority.MINISTRY and ulke.placed_date == date(2026, 11, 12)

    band = takvim.oyss_band(calendar)
    anahtarlar = {(s["level"], s["course_name"]) for s in band["oyss"]}
    assert (11, "İngilizce") not in anahtarlar and (10, "Türk Dili ve Edebiyatı") not in anahtarlar
    satir = next(s for s in band["oyss"] if (s["level"], s["course_name"]) == (9, "İngilizce"))
    assert satir["pool_course_name"] == "Birinci Yabancı Dil"
    assert any(
        "İngilizce değilse OYSS kapsamında değildir" in n for n in band["oyss_info"]["notes"]
    )


def test_on_birinci_sinif_secmelisi_havuzda_yoksa_bekler_kapsamla_yerlesir() -> None:
    subeler = _okul(11)
    secmeli = ders("Seçmeli Matematik", levels=[11, 12], course_type=CourseType.ELECTIVE)
    calendar = _takvim()  # şube kapsamı yok → havuz doldurması seçmeliyi almaz

    satir = _plan(calendar)[(11, "Matematik")]
    assert (satir["status"], satir["pool_course_name"]) == ("needs_pool", "Seçmeli Matematik")
    sonuc = takvim.apply_oyss_schedule(calendar)
    assert any("seçmeli ders takvim havuzunda yok" in s for s in sonuc["skipped"])
    assert not ExamCalendarEntry.objects.filter(calendar=calendar, course=secmeli).exists()

    takvim.add_calendar_entry(
        calendar=calendar,
        course_id=secmeli.pk,
        level=11,
        participant_type=ParticipantType.SECTIONS,
        section_ids=[subeler[11].pk],
    )
    sonuc = takvim.apply_oyss_schedule(calendar)

    assert sonuc["placed"] == ["11. Sınıf Seçmeli Matematik (05.11.2026): 2. ders saati"]
    notlar = takvim.oyss_band(calendar)["oyss_info"]["notes"]
    assert any("seçmeli adıyla bağlandı" in n for n in notlar)


def test_yeniden_uygulama_idarecinin_sectigi_saate_dokunmaz() -> None:
    _okul(9)
    biyoloji = ders("Biyoloji", levels=[9, 10])
    calendar = _takvim()
    girdi = ExamCalendarEntry.objects.get(calendar=calendar, course=biyoloji, level=9)
    takvim.place_entry(girdi, on_date=date(2026, 11, 3), period_no=5)  # okul saati değiştirdi

    sonuc = takvim.apply_oyss_schedule(calendar)

    girdi.refresh_from_db()
    assert girdi.period_no == 5
    assert sonuc["placed"] == []
    assert sonuc["unchanged"] == ["9. Sınıf Biyoloji (03.11.2026)"]
    satir = _plan(calendar)[(9, "Biyoloji")]
    assert (satir["status"], satir["period_no"], satir["entry_period_no"]) == ("placed", 2, 5)


def test_takvimdeki_saat_doluysa_oteki_oyss_saatine_kayar_ve_soyler() -> None:
    _okul(9)
    calendar = _takvim()  # ders yok → uygulanacak bir şey yok
    diger = ders("Sağlık Bilgisi ve Trafik Kültürü", levels=[9])
    girdi = takvim.add_calendar_entry(calendar=calendar, course_id=diger.pk, level=9)
    takvim.place_entry(girdi, on_date=date(2026, 11, 3), period_no=2)
    ders("Biyoloji", levels=[9, 10])

    sonuc = takvim.apply_oyss_schedule(calendar)

    assert sonuc["placed"] == [
        "9. Sınıf Biyoloji (03.11.2026): 4. ders saati — takvimdeki 2. ders saati kullanılamadı"
    ]


def test_gun_aralik_disindaysa_havuzda_bekler_baska_gun_dogrulamada_uyarilir() -> None:
    _okul(9)
    cografya = ders("Coğrafya", levels=[9, 10])
    biyoloji = ders("Biyoloji", levels=[9, 10])

    calendar = _takvim(pencere=(date(2026, 10, 26), date(2026, 11, 6)))  # eski kural haftası

    assert _yer(calendar, cografya, 9) == (None, None)
    assert _yer(calendar, biyoloji, 9) == (date(2026, 11, 3), 2)
    sonuc = takvim.apply_oyss_schedule(calendar)
    assert any(
        s.startswith("9. Sınıf Coğrafya (10.11.2026): gün takvim aralığı dışında")
        for s in sonuc["skipped"]
    )
    assert _plan(calendar)[(9, "Coğrafya")]["status"] == "pending"

    girdi = ExamCalendarEntry.objects.get(calendar=calendar, course=biyoloji, level=9)
    takvim.place_entry(girdi, on_date=date(2026, 11, 5), period_no=2)
    uyarilar = takvim.calendar_validation(calendar)["warnings"]
    assert any(
        "Biyoloji — 9. Sınıf: OYSS uygulama takviminde sınav günü 03.11.2026, takvimde "
        "05.11.2026" in u
        for u in uyarilar
    )
    satir = _plan(calendar)[(9, "Biyoloji")]
    assert (satir["status"], satir["entry_date"]) == ("pending", "2026-11-05")


def test_karsiligi_olmayan_satirlar_tek_ozet_satiriyla_raporlanir() -> None:
    _okul(9)
    calendar = _takvim()

    sonuc = takvim.apply_oyss_schedule(calendar)

    # 9. sınıf: on dersin hiçbiri havuzda yok (Felsefe zaten okutulmaz) — satır satır
    # değil, tek özet.
    assert sonuc["skipped"] == [
        "10 OYSS sınavının ders havuzunda o sınıf düzeyinde karşılığı yok — ders o "
        "düzeyde okutulmuyorsa işlem gerekmez"
    ]


def test_oyss_takvimi_olmayan_turda_bant_bostur() -> None:
    _okul(9)
    ders("Biyoloji", levels=[9, 10])
    calendar = _takvim(pencere=(date(2027, 1, 4), date(2027, 1, 15)), round_=2)

    assert takvim.oyss_band(calendar) == {"oyss": [], "oyss_info": None}
    assert takvim.apply_oyss_schedule(calendar) == {"placed": [], "unchanged": [], "skipped": []}


def test_api_bakanlik_bandi_oyss_satirlarini_ve_sonucunu_doner() -> None:
    _okul(9)
    calendar = _takvim()  # ders henüz yok
    ders("Biyoloji", levels=[9, 10])
    client = APIClient()
    url = f"/api/v1/exam-calendars/{calendar.pk}/national-exams/"

    oncesi = client.get(url)
    assert oncesi.status_code == 200
    satir = next(s for s in oncesi.data["oyss"] if s["course_name"] == "Biyoloji")
    assert (satir["level"], satir["status"], satir["period_no"]) == (9, "pending", 2)
    bilgi = oncesi.data["oyss_info"]
    assert "Uygulama Takvimi" in bilgi["source"]
    assert bilgi["notes"][0].startswith(
        "Günde tek sınav 2. ders saatinde, iki sınav 2. ve 4. ders saatlerinde uygulanır; "
        "süre 40 dakikadır."
    )
    assert any("23.11.2026 – 27.11.2026" in n for n in bilgi["notes"])

    cevap = client.post(url)
    assert cevap.status_code == 200
    assert cevap.data["oyss_result"]["placed"] == ["9. Sınıf Biyoloji (03.11.2026): 2. ders saati"]
    assert "result" in cevap.data  # ülke geneli sonucu da döner
    satir = next(s for s in cevap.data["oyss"] if s["course_name"] == "Biyoloji")
    assert (satir["status"], satir["entry_period_no"]) == ("placed", 2)

    takvim.submit_calendar(calendar)
    assert client.post(url).status_code == 400  # yalnız taslak
