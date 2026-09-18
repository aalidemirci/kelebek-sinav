"""Sınav takvimi UÇLARI (F6) — HTTP sözleşmesi ve hata dalları.

İş kuralları `test_calendar.py`'da servis düzeyinde sınanır; burada sabitlenen
şey view katmanının SÖZLEŞMESİDİR:

- Servis reddi 500 değil 400'dür ve Türkçe gerekçe `message` alanında taşınır
  (arayüz snackbar'ı onu basar); gövde doğrulaması (eksik/bozuk tarih, sayısal
  olmayan kimlik, liste olmayan kalem) servise ULAŞMADAN 400 olur.
- Reddedilen istek kaydı DEĞİŞTİRMEZ — her ret testinde durum ayrıca denetlenir.
- Onaya sunulmuş/onaylı takvim SALT OKUNURDUR: değiştiren her uç aynı taslak
  kilidine takılır (resmî evrak değeri — risk #10).
- Oturumu üretilmiş girdi taşınamaz/silinemez (takvim ile oturum ayrışmasın).

Öğrenci kayıtları `oturum_yardim.sube` ile üretilir — uydurma ad ve numaralar.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.dersler.models import CourseType
from apps.okul.models import SchoolConfig, SchoolTerm, SubjectDepartment
from apps.sinav import services
from apps.sinav import services_calendar as takvim
from apps.sinav.models import (
    ExamCalendar,
    ExamCalendarEntry,
    ExamCalendarStatus,
    ExamSession,
    ExamSessionStatus,
    ExamTrackItem,
    ExamTrackMark,
)
from apps.sinav.tests.oturum_yardim import aktif_yil, ders, donem, sube

pytestmark = pytest.mark.django_db

URL = "/api/v1/exam-calendars/"
GIRDI_URL = "/api/v1/exam-calendar-entries/"
KALEM_URL = "/api/v1/exam-track-items/"

PENCERE = {"start_date": "2026-10-26", "end_date": "2026-11-06"}
GUN = date(2026, 10, 27)  # Salı — pencere içinde, hafta içi
CUMARTESI = date(2026, 10, 31)


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _bahar() -> SchoolTerm:
    mevcut: SchoolTerm | None = SchoolTerm.objects.filter(
        school_year=aktif_yil(), sequence=2
    ).first()
    if mevcut is not None:
        return mevcut
    yeni: SchoolTerm = SchoolTerm.objects.create(
        school_year=aktif_yil(),
        sequence=2,
        start_date=date(2027, 2, 8),
        end_date=date(2027, 6, 30),
    )
    return yeni


def _takvim(course_count: int = 1, *, round_: int = 1) -> ExamCalendar:
    """9/A'da 3 öğrencili, `course_count` dersli TASLAK takvim (dersler seviye geneli)."""
    guz = donem()
    sube(9, "A", students=3, start_no=101)
    calendar = takvim.create_exam_calendar(
        semester_id=guz.pk, round=round_, start_date=date(2026, 10, 26), end_date=date(2026, 11, 6)
    )
    # Dersler takvimden SONRA yaratılır: yaratılışta havuz kendiliğinden tohumlanıyor,
    # aynı çift iki kez eklenmesin.
    for i in range(course_count):
        course = ders(f"Ders {i + 1}", levels=[9])
        takvim.add_calendar_entry(calendar=calendar, course_id=course.pk, level=9)
    return calendar


def _girdiler(calendar: ExamCalendar) -> list[ExamCalendarEntry]:
    return list(ExamCalendarEntry.objects.filter(calendar=calendar).order_by("id"))


def _onayla(calendar: ExamCalendar) -> ExamCalendar:
    takvim.submit_calendar(calendar)
    return takvim.approve_calendar(calendar)


def _oturumlu_taslak_takvim() -> tuple[ExamCalendar, ExamCalendarEntry]:
    """Slotundan oturum ÜRETİLMİŞ, sonra yeniden taslağa alınmış takvim + bağlı girdi."""
    calendar = _takvim(course_count=1)
    (entry,) = _girdiler(calendar)
    takvim.place_entry(entry, on_date=GUN, period_no=1)
    _onayla(calendar)
    takvim.create_session_from_slot(calendar, on_date=GUN, period_no=1)
    takvim.reopen_calendar(calendar)
    entry.refresh_from_db()
    assert entry.session_id is not None
    return calendar, entry


def _ret(yanit: Any, icerir: str) -> None:
    """Servis reddi sözleşmesi: 400 + `validation_error` + gerekçe `message`'da."""
    assert yanit.status_code == 400, yanit.content
    govde = yanit.json()
    assert govde["code"] == "validation_error"
    assert icerir in govde["message"], govde


def _alan_hatasi(yanit: Any, alan: str) -> None:
    """Gövde doğrulaması sözleşmesi: 400 + hatalı alan `fields`'ta adıyla."""
    assert yanit.status_code == 400, yanit.content
    assert alan in yanit.json()["fields"], yanit.json()


# ===========================================================================
# Liste + oluşturma + güncelleme + silme
# ===========================================================================


def test_liste_donem_yil_ve_durum_suzgecleri(client: APIClient) -> None:
    guz, bahar = donem(), _bahar()
    guz_takvimi = takvim.create_exam_calendar(
        semester_id=guz.pk, round=1, start_date=date(2026, 10, 26), end_date=date(2026, 11, 6)
    )
    bahar_takvimi = takvim.create_exam_calendar(
        semester_id=bahar.pk, round=1, start_date=date(2027, 3, 29), end_date=date(2027, 4, 9)
    )
    takvim.submit_calendar(bahar_takvimi)

    def idler(**params: str) -> list[int]:
        yanit = client.get(URL, params)
        assert yanit.status_code == 200
        return [satir["id"] for satir in yanit.json()["results"]]

    assert idler() == [bahar_takvimi.pk, guz_takvimi.pk]  # başlangıç tarihi AZALAN
    assert idler(semester=str(guz.pk)) == [guz_takvimi.pk]
    assert idler(status="SUBMITTED") == [bahar_takvimi.pk]
    assert idler(school_year=str(aktif_yil().pk)) == [bahar_takvimi.pk, guz_takvimi.pk]
    assert idler(school_year="999999") == []
    # Sayısal olmayan süzgeç 500 üretmez; süzgeç yok sayılır.
    assert idler(semester="guz") == [bahar_takvimi.pk, guz_takvimi.pk]


def test_olusturmada_verilen_ad_korunur_verilmeyen_uretilir(client: APIClient) -> None:
    guz = donem()

    adli = client.post(
        URL,
        {"semester": guz.pk, "round": 1, "name": "  Kasım Sınavları ", **PENCERE},
        format="json",
    )
    adsiz = client.post(URL, {"semester": guz.pk, "round": 2, **PENCERE}, format="json")

    assert adli.status_code == 201 and adli.json()["name"] == "Kasım Sınavları"
    assert adsiz.status_code == 201 and adsiz.json()["name"] == "1. Dönem 2. Sınav Takvimi"
    assert adli.json()["status"] == "DRAFT"


def test_olusturma_retleri(client: APIClient) -> None:
    guz = donem()
    assert (
        client.post(URL, {"semester": guz.pk, "round": 1, **PENCERE}, format="json").status_code
        == 201
    )

    # Aynı dönem + tur ikinci kez açılamaz (servis reddi → gerekçe mesajda).
    _ret(client.post(URL, {"semester": guz.pk, "round": 1, **PENCERE}, format="json"), "zaten var")
    _ret(
        client.post(
            URL,
            {"semester": guz.pk, "round": 2, "start_date": "2026-11-06", "end_date": "2026-10-26"},
            format="json",
        ),
        "Bitiş tarihi başlangıçtan önce olamaz",
    )
    # Gövde doğrulaması servise ulaşmadan reddeder.
    _alan_hatasi(
        client.post(URL, {"semester": guz.pk, "round": 4, **PENCERE}, format="json"), "round"
    )
    _alan_hatasi(
        client.post(URL, {"semester": 999_999, "round": 2, **PENCERE}, format="json"), "semester"
    )
    _alan_hatasi(client.post(URL, {"semester": guz.pk, "round": 2}, format="json"), "start_date")

    assert ExamCalendar.objects.count() == 1


def test_guncelleme_tarih_sirasini_ve_taslak_kilidini_korur(client: APIClient) -> None:
    calendar = _takvim(course_count=0)
    zumre = SubjectDepartment.objects.create(name="Sosyal Bilimler")
    url = f"{URL}{calendar.pk}/"

    duzelt = client.patch(
        url, {"name": " Yeni Ad ", "description_text": "Açıklama."}, format="json"
    )
    assert duzelt.status_code == 200
    assert (duzelt.json()["name"], duzelt.json()["description_text"]) == ("Yeni Ad", "Açıklama.")

    _ret(
        client.patch(url, {"end_date": "2026-10-01"}, format="json"),
        "Bitiş tarihi başlangıçtan önce",
    )

    # Kilitli takvimde imza zümresi de DEĞİŞMEZ: M2M yazımı servis kilidinden sonra gelir.
    takvim.submit_calendar(calendar)
    _ret(client.patch(url, {"signatory_departments": [zumre.pk]}, format="json"), "taslak")
    calendar.refresh_from_db()
    assert calendar.name == "Yeni Ad"
    assert calendar.end_date == date(2026, 11, 6)
    assert list(calendar.signatory_departments.all()) == []


def test_guncellemede_takvim_adi_bos_kaydedilemez(client: APIClient) -> None:
    """Takvim adı PDF başlığına ve üretilen oturum adına basılır; model de boş ada izin
    vermez (`blank=False`). Boş ad ya reddedilmeli ya varsayılan ada düşmelidir."""
    calendar = _takvim(course_count=0)

    client.patch(f"{URL}{calendar.pk}/", {"name": "   "}, format="json")

    calendar.refresh_from_db()
    assert calendar.name.strip() != ""


def test_silme_yalniz_taslakta_ve_oturumsuz_takvimde(client: APIClient) -> None:
    taslak = _takvim(course_count=1)
    assert client.delete(f"{URL}{taslak.pk}/").status_code == 204
    assert client.get(f"{URL}{taslak.pk}/").status_code == 404
    assert ExamCalendar.all_objects.filter(pk=taslak.pk).exists()  # soft

    sunulmus = takvim.create_exam_calendar(
        semester_id=donem().pk, round=2, start_date=date(2026, 12, 28), end_date=date(2027, 1, 8)
    )
    takvim.submit_calendar(sunulmus)
    _ret(client.delete(f"{URL}{sunulmus.pk}/"), "taslak")
    assert ExamCalendar.objects.filter(pk=sunulmus.pk).exists()


def test_oturumu_uretilmis_takvim_silinemez(client: APIClient) -> None:
    """Girdi düzeyindeki koruma takvimi topluca silerek ATLATILAMAZ (OYS Tur 644)."""
    calendar, _entry = _oturumlu_taslak_takvim()

    _ret(client.delete(f"{URL}{calendar.pk}/"), "önce oturumları kaldırın")

    assert ExamCalendar.objects.filter(pk=calendar.pk).exists()


def test_olmayan_takvim_ve_girdi_turkce_404(client: APIClient) -> None:
    for yanit in (
        client.get(f"{URL}999999/grid/"),
        client.post(f"{URL}999999/submit/"),
        client.post(
            f"{GIRDI_URL}999999/place/", {"date": "2026-10-27", "period_no": 1}, format="json"
        ),
        client.delete(f"{GIRDI_URL}999999/"),
    ):
        assert yanit.status_code == 404
        assert yanit.json() == {"code": "not_found", "message": "Kayıt bulunamadı.", "fields": {}}


# ===========================================================================
# Ön tanımlı takvimler + varsayılan metinler
# ===========================================================================


def test_generate_defaults_aktif_yila_duser_ve_idempotenttir(client: APIClient) -> None:
    donem()
    _bahar()

    ilk = client.post(f"{URL}generate-defaults/", {}, format="json")
    assert ilk.status_code == 200
    assert sorted((t["semester_name"], t["round"]) for t in ilk.json()["created"]) == [
        ("1. dönem", 1),
        ("1. dönem", 2),
        ("2. dönem", 1),
        ("2. dönem", 2),
    ]

    # Yıl açıkça da verilebilir; ikinci koşu hiçbir şey üretmez.
    tekrar = client.post(
        f"{URL}generate-defaults/", {"school_year_id": aktif_yil().pk}, format="json"
    )
    assert tekrar.status_code == 200 and tekrar.json()["created"] == []
    assert ExamCalendar.objects.count() == 4


@pytest.mark.parametrize("govde", [{}, {"school_year_id": "bu-yil"}])
def test_generate_defaults_ders_yili_yokken_400(client: APIClient, govde: dict[str, Any]) -> None:
    """Aktif yıl yokken yıl verilmemişse (ya da okunamıyorsa) sessizce boş dönmez."""
    yanit = client.post(f"{URL}generate-defaults/", govde, format="json")

    _alan_hatasi(yanit, "school_year_id")
    assert not ExamCalendar.objects.exists()


def test_varsayilan_aciklama_ucu(client: APIClient) -> None:
    """Önizleme sekmesindeki "Varsayılan metne dön" düğmesinin kaynağı."""
    yanit = client.get(f"{URL}default-description/")

    assert yanit.status_code == 200
    assert yanit.json() == {"text": takvim.DEFAULT_CALENDAR_DESCRIPTION}


# ===========================================================================
# Havuz uçları
# ===========================================================================


def test_fill_pool_ucu_rapor_dondurur_ve_idempotenttir(client: APIClient) -> None:
    calendar = _takvim(course_count=0)
    ders("Coğrafya", levels=[9])  # takvimden SONRA eklendi → tohumda yoktu
    url = f"{URL}{calendar.pk}/fill-pool/"

    ilk = client.post(url)
    assert ilk.status_code == 200
    assert set(ilk.json()) == {"created", "existed", "skipped", "total_pairs"}
    assert ilk.json()["created"] == ["Coğrafya — 9. Sınıf"]

    ikinci = client.post(url)
    assert ikinci.json()["created"] == []
    assert ikinci.json()["existed"] == ["Coğrafya — 9. Sınıf"]
    assert ExamCalendarEntry.objects.filter(calendar=calendar).count() == 1


def test_fill_pool_ucu_tur3_takvimini_reddeder(client: APIClient) -> None:
    calendar = _takvim(course_count=0, round_=3)
    ders("Coğrafya", levels=[9])

    _ret(client.post(f"{URL}{calendar.pk}/fill-pool/"), "elle doldurulur")

    assert not ExamCalendarEntry.objects.filter(calendar=calendar).exists()


@pytest.mark.parametrize("govde", [{}, {"items": "hepsi"}, {"items": {"course_id": 1}}])
def test_bulk_entries_kalem_listesi_ister(client: APIClient, govde: dict[str, Any]) -> None:
    calendar = _takvim(course_count=0)

    _alan_hatasi(client.post(f"{URL}{calendar.pk}/bulk-entries/", govde, format="json"), "items")


def test_girdi_ekleme_alanlari_ve_retleri(client: APIClient) -> None:
    calendar = _takvim(course_count=0)
    beden = ders("Beden Eğitimi", levels=[9])
    url = f"{URL}{calendar.pk}/entries/"

    ekle = client.post(
        url,
        {
            "course": beden.pk,
            "level": 9,
            "exam_kind": "PRACTICE",
            "is_butterfly": False,
            "note": "  spor salonunda ",
        },
        format="json",
    )
    assert ekle.status_code == 201
    veri = ekle.json()
    assert (veri["exam_kind"], veri["is_butterfly"], veri["note"]) == (
        "PRACTICE",
        False,
        "spor salonunda",
    )
    assert (veri["authority"], veri["calendar"], veri["course_name"]) == (
        "SCHOOL",
        calendar.pk,
        "Beden Eğitimi",
    )

    _ret(
        client.post(url, {"course": beden.pk, "level": 9, "exam_kind": "PRACTICE"}, format="json"),
        "zaten var",
    )
    _ret(client.post(url, {"course": beden.pk, "level": 12}, format="json"), "okutulmuyor")
    _alan_hatasi(client.post(url, {"level": 9}, format="json"), "course")
    _alan_hatasi(
        client.post(url, {"course": beden.pk, "level": 9, "exam_kind": "SOZLU"}, format="json"),
        "exam_kind",
    )
    # Aynı ders + seviye FARKLI türle ayrı girdidir (yazılı + uygulama).
    assert client.post(url, {"course": beden.pk, "level": 9}, format="json").status_code == 201
    assert ExamCalendarEntry.objects.filter(calendar=calendar).count() == 2


def test_girdi_listesi_turk_alfabesiyle_siralanir(client: APIClient) -> None:
    """SQLite sıralaması BINARY'dir: 'Çince' Z'den sonraya düşerdi."""
    calendar = _takvim(course_count=0)
    for ad in ("Zooloji", "Çince", "Coğrafya", "İngilizce"):
        course = ders(ad, levels=[9], course_type=CourseType.ELECTIVE)
        takvim.add_calendar_entry(calendar=calendar, course_id=course.pk, level=9)

    yanit = client.get(f"{URL}{calendar.pk}/entries/")

    assert [s["course_name"] for s in yanit.json()["results"]] == [
        "Coğrafya",
        "Çince",
        "İngilizce",
        "Zooloji",
    ]


def test_girdi_duzenleme_ve_silme(client: APIClient) -> None:
    calendar = _takvim(course_count=1)
    (entry,) = _girdiler(calendar)
    uygulama = takvim.add_calendar_entry(
        calendar=calendar, course_id=entry.course_id, level=9, exam_kind="PRACTICE"
    )
    url = f"{GIRDI_URL}{entry.pk}/"

    duzelt = client.patch(
        url,
        {"note": " ek süre ", "is_butterfly": False, "authority": "PROVINCIAL"},
        format="json",
    )
    assert duzelt.status_code == 200
    assert (duzelt.json()["note"], duzelt.json()["is_butterfly"], duzelt.json()["authority"]) == (
        "ek süre",
        False,
        "PROVINCIAL",
    )

    # Tür değişimi teklik çakışmasını ÖNCEDEN yakalar (500 yerine 400 — OYS Tur 644).
    _ret(client.patch(url, {"exam_kind": "PRACTICE"}, format="json"), "zaten var")
    _alan_hatasi(client.patch(url, {"authority": "BELEDIYE"}, format="json"), "authority")
    entry.refresh_from_db()
    assert entry.exam_kind == "WRITTEN"

    # Salt okunur alanlar gövdeyle DEĞİŞMEZ: yerleşim ve sabitleme kendi uçlarındandır.
    client.patch(
        url, {"placed_date": "2026-10-27", "period_no": 1, "is_pinned": True}, format="json"
    )
    entry.refresh_from_db()
    assert (entry.placed_date, entry.period_no, entry.is_pinned) == (None, None, False)

    assert client.delete(f"{GIRDI_URL}{uygulama.pk}/").status_code == 204
    assert not ExamCalendarEntry.objects.filter(pk=uygulama.pk).exists()


def test_katilimci_onizleme_ucu(client: APIClient) -> None:
    calendar = _takvim(course_count=1)  # 9/A: 3 öğrenci
    (entry,) = _girdiler(calendar)

    yanit = client.get(f"{URL}{calendar.pk}/participant-preview/")

    assert yanit.status_code == 200
    assert yanit.json()[str(entry.pk)]["student_count"] == 3
    assert yanit.json()[str(entry.pk)]["whole"] is True


# ===========================================================================
# Yerleştirme uçları
# ===========================================================================


@pytest.mark.parametrize(
    "govde",
    [
        {},
        {"date": "2026-10-27"},
        {"period_no": 1},
        {"date": "27.10.2026", "period_no": 1},  # gg.aa.yyyy kabul edilmez — ISO beklenir
        {"date": "2026-10-27", "period_no": "birinci"},
        {"date": "2026-13-45", "period_no": 1},
    ],
)
def test_place_tarih_ve_ders_saati_ister(client: APIClient, govde: dict[str, Any]) -> None:
    """Eksik/bozuk gövde 500 değil alan hatasıdır ve girdi havuzda kalır."""
    calendar = _takvim(course_count=1)
    (entry,) = _girdiler(calendar)

    _alan_hatasi(client.post(f"{GIRDI_URL}{entry.pk}/place/", govde, format="json"), "date")

    entry.refresh_from_db()
    assert entry.placed_date is None


def test_place_servis_retleri_gerekceyi_mesajda_tasir(client: APIClient) -> None:
    calendar = _takvim(course_count=5)
    entries = _girdiler(calendar)

    def yerlestir(entry: ExamCalendarEntry, period_no: int) -> Any:
        return client.post(
            f"{GIRDI_URL}{entry.pk}/place/",
            {"date": GUN.isoformat(), "period_no": period_no},
            format="json",
        )

    _ret(yerlestir(entries[0], 99), "listede tanımlı değil")
    assert yerlestir(entries[0], 1).status_code == 200
    # Aynı gün + saat + seviyede kapsamı kesişen ikinci sınav SERT reddedilir.
    _ret(yerlestir(entries[1], 1), "aynı anda giremez")
    assert yerlestir(entries[1], 2).status_code == 200
    ucuncu = yerlestir(entries[2], 3)
    assert ucuncu.status_code == 200
    assert any("3. sınav" in uyari for uyari in ucuncu.json()["warnings"])
    # 4. sınav: alan sözlüğüyle gelen ret de snackbar'da (message) görünür.
    dorduncu = yerlestir(entries[3], 4)
    _ret(dorduncu, "4 sınava")
    assert "on_date" in dorduncu.json()["fields"]

    entries[3].refresh_from_db()
    assert entries[3].placed_date is None


def test_place_uyariyla_yerlesir_ve_elle_yerlesen_sabitlenir(client: APIClient) -> None:
    calendar = _takvim(course_count=1)
    (entry,) = _girdiler(calendar)

    yanit = client.post(
        f"{GIRDI_URL}{entry.pk}/place/",
        {"date": CUMARTESI.isoformat(), "period_no": "2"},
        format="json",
    )

    assert yanit.status_code == 200
    assert any("hafta sonu" in uyari for uyari in yanit.json()["warnings"])
    girdi = yanit.json()["entry"]
    assert (girdi["placed_date"], girdi["period_no"], girdi["is_pinned"]) == (
        CUMARTESI.isoformat(),
        2,
        True,
    )


@pytest.mark.parametrize(
    ("govde", "beklenen"),
    [
        ({}, True),  # gövdesiz çağrı "sabitle" demektir
        ({"is_pinned": True}, True),
        ({"is_pinned": False}, False),
        ({"is_pinned": "true"}, True),
        ({"is_pinned": "evet"}, True),
        ({"is_pinned": "false"}, False),
        ({"is_pinned": 0}, False),
        ({"is_pinned": 1}, True),
    ],
)
def test_pin_govdesi_esnek_okunur(client: APIClient, govde: dict[str, Any], beklenen: bool) -> None:
    calendar = _takvim(course_count=1)
    (entry,) = _girdiler(calendar)
    takvim.place_entry(entry, on_date=GUN, period_no=1, pin=not beklenen)

    yanit = client.post(f"{GIRDI_URL}{entry.pk}/pin/", govde, format="json")

    assert yanit.status_code == 200 and yanit.json()["is_pinned"] is beklenen
    entry.refresh_from_db()
    assert entry.is_pinned is beklenen


def test_havuzdaki_girdi_sabitlenemez_ama_cozme_serbesttir(client: APIClient) -> None:
    calendar = _takvim(course_count=1)
    (entry,) = _girdiler(calendar)
    url = f"{GIRDI_URL}{entry.pk}/pin/"

    _ret(client.post(url, {"is_pinned": True}, format="json"), "Havuzdaki girdi sabitlenemez")
    assert client.post(url, {"is_pinned": False}, format="json").status_code == 200


def test_unplace_havuza_alir_ve_sabitlemeyi_dusurur(client: APIClient) -> None:
    calendar = _takvim(course_count=1)
    (entry,) = _girdiler(calendar)
    takvim.place_entry(entry, on_date=GUN, period_no=1)

    yanit = client.post(f"{GIRDI_URL}{entry.pk}/unplace/")

    assert yanit.status_code == 200
    assert (yanit.json()["placed_date"], yanit.json()["period_no"], yanit.json()["is_pinned"]) == (
        None,
        None,
        False,
    )
    grid = client.get(f"{URL}{calendar.pk}/grid/").json()
    assert grid["cells"] == {}
    assert [hucre["entry_id"] for hucre in grid["unplaced"]] == [entry.pk]


def test_auto_place_kip_okuma_ve_retleri(client: APIClient) -> None:
    SchoolConfig.objects.create(pk=SchoolConfig.SINGLETON_PK, exam_period_nos=[1, 2])
    calendar = _takvim(course_count=2)
    elle, _gezici = _girdiler(calendar)
    takvim.place_entry(elle, on_date=GUN, period_no=2)  # ELLE → sabit
    url = f"{URL}{calendar.pk}/auto-place/"

    _ret(client.post(url, {"mode": "KARISTIR"}, format="json"), "Geçersiz kip")

    # Gövdesiz çağrı FILL'dir: yalnız havuzdakini dağıtır, ızgaradakine dokunmaz.
    varsayilan = client.post(url)
    assert varsayilan.status_code == 200
    assert set(varsayilan.json()) == {"placed", "skipped", "warnings", "cleared"}
    assert len(varsayilan.json()["placed"]) == 1 and varsayilan.json()["cleared"] == 0

    # Kip büyük/küçük harfe duyarsızdır; yeniden dağıtım SABİTİ yerinden oynatmaz.
    yeniden = client.post(url, {"mode": "redistribute"}, format="json")
    assert yeniden.status_code == 200 and yeniden.json()["cleared"] == 1
    elle.refresh_from_db()
    assert (elle.placed_date, elle.period_no) == (GUN, 2)


def test_auto_place_aday_slot_yoksa_gerekcesiyle_reddeder(client: APIClient) -> None:
    """Yalnız hafta sonunu kapsayan aralıkta otomatik yerleştirme "0 yerleşti" demez."""
    calendar = _takvim(course_count=1)
    ExamCalendar.objects.filter(pk=calendar.pk).update(start_date=CUMARTESI, end_date=CUMARTESI)

    _ret(client.post(f"{URL}{calendar.pk}/auto-place/"), "hafta içi gün")


# ===========================================================================
# Durum makinesi
# ===========================================================================


def test_durum_gecisleri_sira_disinda_reddedilir(client: APIClient) -> None:
    calendar = _takvim(course_count=1)
    kok = f"{URL}{calendar.pk}/"

    _ret(client.post(f"{kok}approve/", {}, format="json"), "onaya sunulmuş")
    _ret(client.post(f"{kok}reopen/"), "zaten taslak")

    sun = client.post(f"{kok}submit/")
    assert sun.status_code == 200
    assert sun.json()["status"] == "SUBMITTED" and sun.json()["submitted_at"] is not None
    _ret(client.post(f"{kok}submit/"), "Yalnız taslak takvim")

    calendar.refresh_from_db()
    assert calendar.status == ExamCalendarStatus.SUBMITTED


def test_onay_damgasi_ve_yeniden_acma(client: APIClient) -> None:
    """Onaylayan adı gövdeden ad-snapshot'tır; boşsa müdür adına düşer. Yeniden açma
    damgaları SİLMEZ (tarihçe)."""
    SchoolConfig.objects.create(pk=SchoolConfig.SINGLETON_PK, principal_name="Örnek MÜDÜR")
    calendar = _takvim(course_count=1)
    kok = f"{URL}{calendar.pk}/"
    client.post(f"{kok}submit/")

    onay = client.post(
        f"{kok}approve/", {"approved_by_name": "  Deneme   MÜDÜR YARDIMCISI "}, format="json"
    )
    assert onay.status_code == 200
    assert onay.json()["status"] == "APPROVED"
    assert onay.json()["approved_by_name"] == "Deneme MÜDÜR YARDIMCISI"
    _ret(client.post(f"{kok}approve/", {}, format="json"), "onaya sunulmuş")  # ikinci onay yok

    ac = client.post(f"{kok}reopen/")
    assert ac.status_code == 200 and ac.json()["status"] == "DRAFT"
    assert ac.json()["approved_by_name"] == "Deneme MÜDÜR YARDIMCISI"
    assert ac.json()["approved_at"] is not None

    # Ad verilmeyen onay müdür damgasına düşer.
    client.post(f"{kok}submit/")
    assert client.post(f"{kok}approve/").json()["approved_by_name"] == "Örnek MÜDÜR"


def test_onayli_takvim_salt_okunurdur(client: APIClient) -> None:
    """Değiştiren HER uç aynı taslak kilidine takılır; okuma uçları açık kalır."""
    calendar = _takvim(course_count=2)
    yerlesik, havuzdaki = _girdiler(calendar)
    takvim.place_entry(yerlesik, on_date=GUN, period_no=1)
    yeni_ders = ders("Sonradan Gelen", levels=[9])
    _onayla(calendar)
    kok = f"{URL}{calendar.pk}/"
    yer = {"date": "2026-10-28", "period_no": 2}

    degistirenler = {
        "takvim düzenle": client.patch(kok, {"name": "Değişmez"}, format="json"),
        "takvim sil": client.delete(kok),
        "fill-pool": client.post(f"{kok}fill-pool/"),
        "bulk-entries": client.post(
            f"{kok}bulk-entries/",
            {"items": [{"course_id": yeni_ders.pk, "level": 9}]},
            format="json",
        ),
        "girdi ekle": client.post(
            f"{kok}entries/", {"course": yeni_ders.pk, "level": 9}, format="json"
        ),
        "auto-place": client.post(f"{kok}auto-place/"),
        "girdi düzenle": client.patch(
            f"{GIRDI_URL}{yerlesik.pk}/", {"note": "değişmez"}, format="json"
        ),
        "girdi sil": client.delete(f"{GIRDI_URL}{havuzdaki.pk}/"),
        "place": client.post(f"{GIRDI_URL}{havuzdaki.pk}/place/", yer, format="json"),
        "unplace": client.post(f"{GIRDI_URL}{yerlesik.pk}/unplace/"),
        "pin": client.post(f"{GIRDI_URL}{yerlesik.pk}/pin/", {"is_pinned": False}, format="json"),
    }
    for uc, yanit in degistirenler.items():
        assert yanit.status_code == 400, f"{uc}: kilitli takvimde {yanit.status_code} döndü"
        assert "taslak" in yanit.json()["message"], f"{uc}: {yanit.json()}"

    calendar.refresh_from_db()
    yerlesik.refresh_from_db()
    havuzdaki.refresh_from_db()
    assert calendar.status == ExamCalendarStatus.APPROVED
    assert (yerlesik.placed_date, yerlesik.period_no, yerlesik.is_pinned) == (GUN, 1, True)
    assert havuzdaki.placed_date is None
    assert ExamCalendarEntry.objects.filter(calendar=calendar).count() == 2

    for yol in ("", "grid/", "entries/", "track/", "participant-preview/", "elective-options/"):
        assert client.get(f"{kok}{yol}").status_code == 200


# ===========================================================================
# Slot → oturum üretimi
# ===========================================================================


def test_create_session_govde_ve_durum_retleri(client: APIClient) -> None:
    calendar = _takvim(course_count=1)
    (entry,) = _girdiler(calendar)
    takvim.place_entry(entry, on_date=GUN, period_no=1)
    url = f"{URL}{calendar.pk}/create-session/"
    slot = {"date": GUN.isoformat(), "period_no": 1}

    _alan_hatasi(client.post(url, {"date": GUN.isoformat()}, format="json"), "date")
    _alan_hatasi(client.post(url, {"date": "yarın", "period_no": 1}, format="json"), "date")
    _ret(client.post(url, slot, format="json"), "ONAYLANMIŞ")  # taslaktan oturum üretilmez

    _onayla(calendar)
    _ret(
        client.post(url, {"date": "2026-10-28", "period_no": 1}, format="json"), "girdi yok"
    )  # boş slot
    assert not ExamSession.objects.exists()

    uret = client.post(url, slot, format="json")
    assert uret.status_code == 201
    session = ExamSession.objects.get(pk=uret.json()["session_id"])
    assert session.status == ExamSessionStatus.DRAFT
    assert uret.json()["name"] == session.name and "1. Ders" in session.name

    _ret(client.post(url, slot, format="json"), "zaten oturumlu")
    assert ExamSession.objects.count() == 1


def test_oturumu_uretilmis_girdi_tasinamaz_ve_silinemez(client: APIClient) -> None:
    """Takvim yeniden taslağa alınsa bile oturuma bağlı girdi yerinde kalır —
    aksi hâlde takvim ile üretilmiş oturum sessizce ayrışır."""
    _calendar, entry = _oturumlu_taslak_takvim()
    kok = f"{GIRDI_URL}{entry.pk}/"

    _ret(
        client.post(f"{kok}place/", {"date": "2026-10-28", "period_no": 2}, format="json"),
        "taşınamaz",
    )
    _ret(client.post(f"{kok}unplace/"), "havuza geri alınamaz")
    _ret(client.delete(kok), "silinemez")

    entry.refresh_from_db()
    assert (entry.placed_date, entry.period_no) == (GUN, 1)
    assert entry.session_id is not None


def test_oturumu_silinen_girdi_yeniden_serbesttir(client: APIClient) -> None:
    """Kilit CANLI oturuma bağlıdır (A4): slottan üretilen taslak oturum silinince girdi
    havuza alınabilir ve silinebilir. Silme soft olduğundan `session_id` ölü oturumu
    göstermeye devam eder — yalnız kimliğe bakan denetim girdiyi takvimde kilitlerdi."""
    _calendar, entry = _oturumlu_taslak_takvim()
    services.remove_exam_session(ExamSession.objects.get(pk=entry.session_id))
    kok = f"{GIRDI_URL}{entry.pk}/"

    havuz = client.post(f"{kok}unplace/")
    assert havuz.status_code == 200
    # Havuza dönen girdi ölü oturum kimliğini de bırakır (yeniden oturum üretecektir).
    assert (havuz.json()["placed_date"], havuz.json()["session"]) == (None, None)
    entry.refresh_from_db()
    assert entry.session_id is None

    assert client.delete(kok).status_code == 204
    assert not ExamCalendarEntry.objects.filter(pk=entry.pk).exists()


# ===========================================================================
# PDF
# ===========================================================================


def test_pdf_ucu_satir_ici_gosterilir_ve_takvim_kimligiyle_adlanir(client: APIClient) -> None:
    """`inline`: masaüstü kabuğu PDF'i indirme diyaloğu açmadan önizlemede gösterir."""
    calendar = _takvim(course_count=1)

    yanit = client.get(f"{URL}{calendar.pk}/pdf/")

    assert yanit.status_code == 200
    assert yanit["Content-Type"] == "application/pdf"
    assert yanit["Content-Disposition"] == f'inline; filename="sinav_takvimi_{calendar.pk}.pdf"'
    assert yanit.content.startswith(b"%PDF")


# ===========================================================================
# Süreç takip — matris, işaretleme, kalem kataloğu
# ===========================================================================


def _isaretle(client: APIClient, calendar: ExamCalendar, **govde: Any) -> Any:
    return client.post(f"{URL}{calendar.pk}/track/mark/", govde, format="json")


def test_track_matrisi_ve_isaretleme_dongusu(client: APIClient) -> None:
    SchoolConfig.objects.create(pk=SchoolConfig.SINGLETON_PK, principal_name="Örnek MÜDÜR")
    calendar = _takvim(course_count=1)
    (entry,) = _girdiler(calendar)
    item = takvim.create_track_item(name="Soru teslimi")

    bos = client.get(f"{URL}{calendar.pk}/track/").json()
    assert [k["name"] for k in bos["items"]] == ["Soru teslimi"]
    assert bos["rows"][0]["cells"] == [{"item_id": item.pk, "status": None}]

    isaret = _isaretle(
        client, calendar, entry_id=entry.pk, item_id=item.pk, status="DONE", note="teslim alındı"
    )
    assert isaret.status_code == 200
    hucre = isaret.json()["cell"]
    assert (hucre["status"], hucre["note"], hucre["marked_by_name"]) == (
        "DONE",
        "teslim alındı",
        "Örnek MÜDÜR",
    )
    assert hucre["marked_at"]

    # Arayüzün durum döngüsü `note` GÖNDERMEZ: kayıtlı not korunur (OYS Tur 644).
    dongu = _isaretle(
        client,
        calendar,
        entry_id=str(entry.pk),
        item_id=str(item.pk),
        status="NOT_APPLICABLE",
        marked_by_name="Deneme ÖĞRETMEN",
    )
    assert dongu.json()["cell"]["note"] == "teslim alındı"
    assert dongu.json()["cell"]["marked_by_name"] == "Deneme ÖĞRETMEN"
    # Boş not açıkça gönderilirse temizler.
    temiz = _isaretle(client, calendar, entry_id=entry.pk, item_id=item.pk, status="DONE", note="")
    assert temiz.json()["cell"]["note"] == ""

    # status=null işareti kaldırır: hücre "yapılmadı" (kayıt yokluğu) biçimine döner.
    kaldir = _isaretle(client, calendar, entry_id=entry.pk, item_id=item.pk, status=None)
    assert kaldir.json() == {"cell": {"item_id": item.pk, "status": None}}
    assert not ExamTrackMark.objects.filter(entry=entry, item=item).exists()


def test_track_isaretleme_retleri(client: APIClient) -> None:
    calendar = _takvim(course_count=1)
    (entry,) = _girdiler(calendar)
    item = takvim.create_track_item(name="Soru teslimi")
    baska = takvim.create_exam_calendar(
        semester_id=donem().pk, round=2, start_date=date(2026, 12, 28), end_date=date(2027, 1, 8)
    )

    # Sayısal olmayan / eksik / bilinmeyen kimlik 500 değil 400'dür (OYS Tur 644).
    for govde in (
        {"entry_id": "abc", "item_id": item.pk, "status": "DONE"},
        {"entry_id": entry.pk, "status": "DONE"},
        {"entry_id": entry.pk, "item_id": 999_999, "status": "DONE"},
        {"entry_id": 999_999, "item_id": item.pk, "status": "DONE"},
    ):
        _alan_hatasi(_isaretle(client, calendar, **govde), "entry_id")

    # Girdi BAŞKA takvime aitse işaretlenmez (adres çubuğundaki takvim belirleyicidir).
    _alan_hatasi(
        _isaretle(client, baska, entry_id=entry.pk, item_id=item.pk, status="DONE"), "entry_id"
    )
    _ret(
        _isaretle(client, calendar, entry_id=entry.pk, item_id=item.pk, status="YARIM"),
        "Geçersiz durum",
    )

    assert not ExamTrackMark.objects.exists()


def test_kalem_katalogu_ekleme_sira_ve_teklik(client: APIClient) -> None:
    ilk = client.post(
        KALEM_URL, {"name": "  KSD ilanı ", "description": " duyuru panosu "}, format="json"
    )
    ikinci = client.post(KALEM_URL, {"name": "Soru teslimi"}, format="json")

    assert ilk.status_code == 201 and ikinci.status_code == 201
    assert (ilk.json()["name"], ilk.json()["description"]) == ("KSD ilanı", "duyuru panosu")
    # Sıra kendiliğinden artar (araya kalem sokulabilsin diye onar onar).
    assert (ilk.json()["order"], ikinci.json()["order"]) == (10, 20)
    assert ilk.json()["is_active"] is True

    # Ad çakışması 500 (IntegrityError) değil 400'dür ve hatalı alan `name`'dir.
    _alan_hatasi(client.post(KALEM_URL, {"name": "KSD ilanı"}, format="json"), "name")
    _alan_hatasi(client.post(KALEM_URL, {"name": "   "}, format="json"), "name")
    assert ExamTrackItem.objects.count() == 2


def test_kalem_adi_cakismasinin_gerekcesi_snackbara_tasinir(client: APIClient) -> None:
    """Arayüz kalem hatalarını YALNIZ snackbar'da (`message`) gösterir: ad çakışmasının
    gerekçesi orada okunabilmelidir (ekleme ve yeniden adlandırma)."""
    ksd = takvim.create_track_item(name="KSD ilanı")
    teslim = takvim.create_track_item(name="Soru teslimi")

    _ret(client.post(KALEM_URL, {"name": ksd.name}, format="json"), "zaten var")
    _ret(client.patch(f"{KALEM_URL}{teslim.pk}/", {"name": ksd.name}, format="json"), "zaten var")


def test_kalem_katalogu_duzenleme_pasiflestirme_ve_silme(client: APIClient) -> None:
    ksd = takvim.create_track_item(name="KSD ilanı")
    teslim = takvim.create_track_item(name="Soru teslimi")

    def adlar(**params: str) -> list[str]:
        return [k["name"] for k in client.get(KALEM_URL, params).json()["results"]]

    cakisan = client.patch(f"{KALEM_URL}{teslim.pk}/", {"name": "KSD ilanı"}, format="json")
    _alan_hatasi(cakisan, "name")
    teslim.refresh_from_db()
    assert teslim.name == "Soru teslimi"
    ayni_ad = client.patch(f"{KALEM_URL}{teslim.pk}/", {"name": "Soru teslimi"}, format="json")
    assert ayni_ad.status_code == 200  # teklik denetimi kaydın kendisini saymaz

    # Pasif kalem matristen ve olağan listeden düşer, katalog yönetiminde görünür kalır.
    pasif = client.patch(
        f"{KALEM_URL}{ksd.pk}/", {"is_active": False, "description": "eski"}, format="json"
    )
    assert pasif.status_code == 200
    assert (pasif.json()["is_active"], pasif.json()["description"]) == (False, "eski")
    assert adlar() == ["Soru teslimi"]
    assert adlar(include_inactive="true") == ["KSD ilanı", "Soru teslimi"]

    assert client.delete(f"{KALEM_URL}{teslim.pk}/").status_code == 204
    assert adlar() == []
    assert ExamTrackItem.all_objects.filter(pk=teslim.pk).exists()  # soft
    # Silinen kalemin adı yeniden kullanılabilir.
    assert client.post(KALEM_URL, {"name": "Soru teslimi"}, format="json").status_code == 201
