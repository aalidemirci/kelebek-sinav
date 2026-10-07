"""Şube değiştiren / nakil gelen öğrenci → seçmeli ders seçimi bekler (07.10.2026).

Kullanıcı isteği: "nakil gelen veya sınıfı değiştirilen öğrencileri yeni
sınıflarındaki derslerle ilişkilendirip eski sınıflarıyla bağlarını silsin;
sınıfın bölünerek aldığı dersler varsa uyarıp hangi dersi aldığını seçtirsin."
Kullanıcı kararı: seçim beklerken o şubenin bölünmüş dersini içeren oturum
DAĞITILAMAZ (uyarı değil engel).

Veri tamamen sentetiktir (okul no kısa, adlar "AD0/SOYAD" kalıbında).
"""

from __future__ import annotations

from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework.test import APIClient

from apps.dersler import enrollment_import, selectors, services
from apps.dersler.enrollment_import import ParsedReport, ReportGroup, ReportLine
from apps.dersler.models import (
    Course,
    CourseAlias,
    CourseEnrollment,
    CourseType,
    PendingElectiveChoice,
)
from apps.dersler.text import course_match_key
from apps.okul.models import ClassSection, Student, StudentStatus
from apps.okul.services import imports as import_service
from apps.okul.services import persons
from apps.sinav import participants
from apps.sinav import services as sinav_services
from apps.sinav.models import ParticipantType
from apps.sinav.tests.oturum_yardim import aktif_yil, oturum, salon, sube

pytestmark = pytest.mark.django_db


def _secmeli(ad: str) -> Course:
    ders: Course = Course.objects.create(
        name=ad, levels=[9, 10, 11, 12], course_type=CourseType.ELECTIVE
    )
    return ders


def _ogrenciler(sube_kaydi: ClassSection) -> list[int]:
    return list(
        Student.objects.filter(
            class_level=sube_kaydi.class_level, class_section=sube_kaydi.class_section
        )
        .order_by("student_number")
        .values_list("pk", flat=True)
    )


@pytest.fixture
def okul() -> dict[str, Any]:
    """9/A (4) ve 9/B (4): iki şube de Almanca/Fransızca'yı BÖLÜNEREK alıyor; 9/C listesiz."""
    a = sube(9, "A", students=4, start_no=101)
    b = sube(9, "B", students=4, start_no=201)
    c = sube(9, "C", students=2, start_no=301)
    al = _secmeli("Almanca")
    fr = _secmeli("Fransızca")
    yil = aktif_yil().pk
    for kayit in (a, b):
        ogr = _ogrenciler(kayit)
        services.set_section_enrollment(
            course_id=al.pk,
            school_year_id=yil,
            section_id=kayit.pk,
            student_ids=ogr[:2],
            complement_course_id=fr.pk,
        )
    # 9/C Almanca'yı şubenin TAMAMI olarak alıyor (liste yok).
    services.set_course_sections(
        course_id=al.pk,
        school_year_id=yil,
        offerings=[{"level": 9, "section_ids": [a.pk, b.pk, c.pk]}],
    )
    return {"a": a, "b": b, "c": c, "al": al, "fr": fr, "yil": yil}


def _bekleyen(student_id: int) -> PendingElectiveChoice | None:
    kayit: PendingElectiveChoice | None = PendingElectiveChoice.objects.filter(
        student_id=student_id
    ).first()
    return kayit


# ===========================================================================
# Şube değişikliği — elle düzenleme
# ===========================================================================


def test_sube_degisince_eski_satir_silinir_ve_bolunmus_derste_secim_bekler(
    okul: dict[str, Any],
) -> None:
    """9/A'nın Almanca listesindeki öğrenci 9/B'ye geçer: eski satır gider, seçim bekler."""
    ogr = _ogrenciler(okul["a"])[0]  # 9/A Almanca listesinde
    ogrenci = Student.objects.get(pk=ogr)

    persons.update_student(ogrenci, class_section="B")

    assert not CourseEnrollment.all_objects.filter(student_id=ogr).exists()
    bekleyen = _bekleyen(ogr)
    assert bekleyen is not None
    assert bekleyen.section_id == okul["b"].pk
    # Eski şubede aldığı ders öneri olarak saklanır.
    assert bekleyen.previous_course_ids == [okul["al"].pk]


def test_listesiz_subeye_gecen_ogrenci_beklemez(okul: dict[str, Any]) -> None:
    """9/C dersi şubenin tamamı olarak alıyor — seçim gerekmez, eski satır yine silinir."""
    ogr = _ogrenciler(okul["a"])[0]

    persons.update_student(Student.objects.get(pk=ogr), class_section="C")

    assert _bekleyen(ogr) is None
    assert not CourseEnrollment.all_objects.filter(student_id=ogr).exists()


def test_sube_degismeyen_ogrenci_beklemez(okul: dict[str, Any]) -> None:
    """Hiçbir listede olmayan eski öğrenci o dersleri almıyor olabilir — bekletilmez."""
    yeni = Student.objects.create(
        first_name="AD9", last_name="SOYAD", student_number="999", class_level=9, class_section="B"
    )  # ORM ile: köprü çağrılmadı (eski kayıt gibi)

    persons.update_student(yeni, first_name="AD8")

    assert _bekleyen(yeni.pk) is None


def test_ayni_subeye_geri_donen_ogrencinin_onerisi_korunur(okul: dict[str, Any]) -> None:
    ogr = _ogrenciler(okul["a"])[0]
    ogrenci = Student.objects.get(pk=ogr)
    persons.update_student(ogrenci, class_section="B")

    persons.update_student(ogrenci, class_section="A")

    bekleyen = _bekleyen(ogr)
    assert bekleyen is not None and bekleyen.section_id == okul["a"].pk
    assert bekleyen.previous_course_ids == [okul["al"].pk]
    assert PendingElectiveChoice.all_objects.filter(student_id=ogr).count() == 1


# ===========================================================================
# Nakil gelen öğrenci — elle kayıt ve e-Okul aktarımı
# ===========================================================================


def test_nakil_gelen_ogrenci_bolunmus_subede_secim_bekler(okul: dict[str, Any]) -> None:
    yeni = persons.create_student(
        first_name="AD9", last_name="SOYAD", student_number="999", class_level=9, class_section="B"
    )

    bekleyen = _bekleyen(yeni.pk)
    assert bekleyen is not None and bekleyen.previous_course_ids == []


def test_nakil_gelen_ogrenci_listesiz_subede_beklemez(okul: dict[str, Any]) -> None:
    yeni = persons.create_student(
        first_name="AD9", last_name="SOYAD", student_number="999", class_level=9, class_section="C"
    )

    assert _bekleyen(yeni.pk) is None


def _metin(*satirlar: str) -> str:
    return "\n".join(["Sınıf\tOkul No\tAdı Soyadı", *satirlar])


def test_ogrenci_aktarimi_sube_degisenleri_ve_yenileri_sayar(okul: dict[str, Any]) -> None:
    """Önizleme sayıyı yazmadan söyler; aktarım bekleyen kaydı yazar."""
    metin = _metin(
        "9/B\t101\tAD0 SOYAD9A",  # 9/A → 9/B (bölünmüş şube)
        "9/C\t102\tAD1 SOYAD9A",  # 9/A → 9/C (listesiz şube)
        "9/A\t103\tAD2 SOYAD9A",  # değişmedi
        "9/A\t998\tAD7 SOYAD",  # nakil gelen → 9/A bölünmüş
    )

    on = import_service.preview_students_text(text=metin)
    assert on.elective_choices_pending == 2
    assert not PendingElectiveChoice.objects.exists()

    sonuc = import_service.commit_students_text(text=metin)

    assert sonuc.elective_choices_pending == 2
    bekleyenler = {
        Student.objects.get(pk=k.student_id).student_number: k.section_id
        for k in PendingElectiveChoice.objects.all()
    }
    assert bekleyenler == {"101": okul["b"].pk, "998": okul["a"].pk}
    # 9/C'ye geçenin eski satırı da gitti, beklemiyor.
    assert not CourseEnrollment.objects.filter(student__student_number="102").exists()


# ===========================================================================
# Ayrılma / silme — KVKK
# ===========================================================================


@pytest.mark.parametrize("yol", ["ayrildi", "silindi"])
def test_ayrilan_ogrencinin_listeleri_ve_bekleyisi_kati_silinir(
    okul: dict[str, Any], yol: str
) -> None:
    ogr = _ogrenciler(okul["a"])[0]
    persons.update_student(Student.objects.get(pk=ogr), class_section="B")
    assert _bekleyen(ogr) is not None
    ogrenci = Student.objects.get(pk=ogr)
    services.resolve_elective_choice(
        student_id=ogr, course_ids=[okul["al"].pk], school_year_id=okul["yil"]
    )

    if yol == "ayrildi":
        persons.update_student(ogrenci, status=StudentStatus.LEFT)
    else:
        persons.delete_student(ogrenci)

    assert not CourseEnrollment.all_objects.filter(student_id=ogr).exists()
    assert not PendingElectiveChoice.all_objects.filter(student_id=ogr).exists()


def test_yeniden_aktiflesen_ogrenci_yeni_gelen_gibi_sorulur(okul: dict[str, Any]) -> None:
    ogr = _ogrenciler(okul["b"])[0]
    ogrenci = Student.objects.get(pk=ogr)
    persons.update_student(ogrenci, status=StudentStatus.LEFT)
    assert not CourseEnrollment.all_objects.filter(student_id=ogr).exists()

    persons.update_student(ogrenci, status=StudentStatus.ACTIVE)

    assert _bekleyen(ogr) is not None


# ===========================================================================
# Seçimin kaydı
# ===========================================================================


def test_secim_kaydi_listelere_yazar_ve_bekleyisi_kapatir(okul: dict[str, Any]) -> None:
    ogr = _ogrenciler(okul["a"])[0]
    persons.update_student(Student.objects.get(pk=ogr), class_section="B")

    sonuc = services.resolve_elective_choice(
        student_id=ogr, course_ids=[okul["fr"].pk], school_year_id=okul["yil"]
    )

    assert sonuc == {"student_id": ogr, "section_id": okul["b"].pk, "course_ids": [okul["fr"].pk]}
    assert _bekleyen(ogr) is None
    listeler = services.course_enrollments(course_id=okul["fr"].pk, school_year_id=okul["yil"])
    assert ogr in listeler[okul["b"].pk]


def test_bos_secim_hicbirini_almiyor_demektir(okul: dict[str, Any]) -> None:
    ogr = _ogrenciler(okul["a"])[0]
    persons.update_student(Student.objects.get(pk=ogr), class_section="B")

    services.resolve_elective_choice(student_id=ogr, course_ids=[], school_year_id=okul["yil"])

    assert _bekleyen(ogr) is None
    assert not CourseEnrollment.objects.filter(student_id=ogr).exists()


def test_bosalan_liste_dersi_subenin_tamamina_gecirmez(okul: dict[str, Any]) -> None:
    """Son üyesi çıkarılan listede ders o şubenin kapsamından düşer."""
    yil = okul["yil"]
    d = sube(10, "D", students=2, start_no=401)
    ogr = _ogrenciler(d)
    ast = _secmeli("Astronomi")
    services.set_section_enrollment(
        course_id=ast.pk, school_year_id=yil, section_id=d.pk, student_ids=ogr[:1]
    )
    PendingElectiveChoice.objects.create(student_id=ogr[0], school_year_id=yil, section=d)

    services.resolve_elective_choice(student_id=ogr[0], course_ids=[], school_year_id=yil)

    assert (ast.pk, 10) not in selectors.course_section_map(yil)


@pytest.mark.parametrize("sorun", ["bekleyen_yok", "sube_degisti", "listesiz_ders", "tip"])
def test_gecersiz_secim_reddedilir(okul: dict[str, Any], sorun: str) -> None:
    ogr = _ogrenciler(okul["a"])[0]
    persons.update_student(Student.objects.get(pk=ogr), class_section="B")
    kwargs: dict[str, Any] = {
        "student_id": ogr,
        "course_ids": [okul["al"].pk],
        "school_year_id": okul["yil"],
    }
    if sorun == "bekleyen_yok":
        kwargs["student_id"] = _ogrenciler(okul["c"])[0]
    elif sorun == "sube_degisti":
        Student.objects.filter(pk=ogr).update(class_section="C")  # köprüsüz değişiklik
    elif sorun == "listesiz_ders":
        kwargs["course_ids"] = [_secmeli("Astronomi").pk]
    else:
        kwargs["course_ids"] = ["x"]

    with pytest.raises(ValidationError) as exc:
        services.resolve_elective_choice(**kwargs)
    assert "AD0" not in str(exc.value)  # hata metni ad taşımaz (KVKK)


# ===========================================================================
# Oturum — dağıtım ENGELLENİR (kullanıcı kararı 07.10.2026)
# ===========================================================================


def _bolunmus_oturum(okul: dict[str, Any]) -> Any:
    session = oturum()
    for course in (okul["al"], okul["fr"]):
        sinav_services.add_session_course(
            session,
            course_id=course.pk,
            participant_type=ParticipantType.SECTIONS,
            section_ids=[okul["b"].pk],
        )
    sinav_services.set_session_rooms(session, [{"room_id": salon("D-201").pk}])
    return session


def test_secim_bekleyen_varken_oturum_dagitilamaz(okul: dict[str, Any]) -> None:
    ogr = _ogrenciler(okul["a"])[0]
    persons.update_student(Student.objects.get(pk=ogr), class_section="B")
    session = _bolunmus_oturum(okul)

    cozum = participants.resolve_session(session)
    assert cozum.has_pending_choices
    assert ogr not in {p.student_id for p in cozum.participants}
    assert any("seçimi bekliyor" in w for c in cozum.courses for w in c.warnings)
    with pytest.raises(ValidationError) as exc:
        sinav_services.distribute_session(session, seed=7)
    assert "1 öğrencinin seçmeli ders seçimi bekliyor (9/B)" in str(exc.value)
    assert "AD0" not in str(exc.value)

    services.resolve_elective_choice(
        student_id=ogr, course_ids=[okul["al"].pk], school_year_id=okul["yil"]
    )
    session, _sonuc, rapor = sinav_services.distribute_session(session, seed=7)
    assert rapor.is_valid
    assert ogr in {p.student_id for p in participants.resolve_session(session).participants}


def test_listesine_elle_eklenen_bekleyen_o_dersi_durdurmaz(okul: dict[str, Any]) -> None:
    """Bekleyen öğrenci Almanca listesine elle eklendiyse Almanca belli, Fransızca belirsiz."""
    yil = okul["yil"]
    ogr = _ogrenciler(okul["a"])[0]
    persons.update_student(Student.objects.get(pk=ogr), class_section="B")
    mevcut = services.course_enrollments(course_id=okul["al"].pk, school_year_id=yil)
    services.set_section_enrollment(
        course_id=okul["al"].pk,
        school_year_id=yil,
        section_id=okul["b"].pk,
        student_ids=[*mevcut[okul["b"].pk], ogr],
    )
    almanca = oturum(name="Almanca")
    fransizca = oturum(name="Fransızca")
    for session, course in ((almanca, okul["al"]), (fransizca, okul["fr"])):
        sinav_services.add_session_course(
            session,
            course_id=course.pk,
            participant_type=ParticipantType.SECTIONS,
            section_ids=[okul["b"].pk],
        )

    cozum = participants.resolve_session(almanca)
    assert not cozum.has_pending_choices
    assert ogr in {p.student_id for p in cozum.participants}
    assert participants.resolve_session(fransizca).has_pending_choices
    # Günlük sayım da yalnız belirsiz derste "bilinmiyor"a düşer.
    services.set_course_sections(
        course_id=okul["al"].pk,
        school_year_id=yil,
        offerings=[{"level": 9, "section_ids": [okul["a"].pk, okul["b"].pk]}],
    )
    assert ogr in selectors.course_level_student_ids(
        course_id=okul["al"].pk, level=9, school_year_id=yil
    )
    assert (
        selectors.course_level_student_ids(course_id=okul["fr"].pk, level=9, school_year_id=yil)
        == set()
    )


def test_listesiz_dersin_oturumu_bekleyen_yuzunden_durmaz(okul: dict[str, Any]) -> None:
    """9/B Astronomi'yi şubenin TAMAMI olarak alıyor: bekleyen öğrenci kendiliğinden girer."""
    ast = _secmeli("Astronomi")
    services.set_course_sections(
        course_id=ast.pk,
        school_year_id=okul["yil"],
        offerings=[{"level": 9, "section_ids": [okul["b"].pk]}],
    )
    ogr = _ogrenciler(okul["a"])[0]
    persons.update_student(Student.objects.get(pk=ogr), class_section="B")
    assert _bekleyen(ogr) is not None  # Almanca/Fransızca için bekliyor
    session = oturum()
    sinav_services.add_session_course(
        session,
        course_id=ast.pk,
        participant_type=ParticipantType.SECTIONS,
        section_ids=[okul["b"].pk],
    )

    cozum = participants.resolve_session(session)

    assert not cozum.has_pending_choices
    assert ogr in {p.student_id for p in cozum.participants}


def test_gunluk_sinav_sayimi_bekleyen_varken_bilinmiyor_der(okul: dict[str, Any]) -> None:
    yil = okul["yil"]
    services.set_course_sections(
        course_id=okul["al"].pk,
        school_year_id=yil,
        offerings=[{"level": 9, "section_ids": [okul["a"].pk, okul["b"].pk]}],
    )
    assert selectors.course_level_student_ids(course_id=okul["al"].pk, level=9, school_year_id=yil)

    persons.update_student(Student.objects.get(pk=_ogrenciler(okul["a"])[0]), class_section="B")

    assert (
        selectors.course_level_student_ids(course_id=okul["al"].pk, level=9, school_year_id=yil)
        == set()
    )


# ===========================================================================
# e-Okul seçmeli raporu — raporda geçen öğrencinin bekleyişi kapanır
# ===========================================================================


def _rapor(*gruplar: tuple[str, list[tuple[str, int, str]]]) -> ParsedReport:
    rapor = ParsedReport(pages=1)
    satir = 0
    for baslik, satirlar in gruplar:
        grup = ReportGroup(title=baslik)
        for no, duzey, sube_adi in satirlar:
            satir += 1
            grup.lines.append(ReportLine(1, satir, no, duzey, sube_adi))
        rapor.groups.append(grup)
    return rapor


def test_eokul_raporu_raporda_gecenin_bekleyisini_kapatir(
    okul: dict[str, Any], settings: Any, tmp_path: Any
) -> None:
    settings.CATALOG_DIR = tmp_path
    settings.COURSE_ALIAS_FILE = tmp_path / "takma-ad-yok.md"
    CourseAlias.objects.create(
        alias_key=course_match_key("Seçmeli Almanca"),
        display_name="Seçmeli Almanca",
        course=okul["al"],
    )
    tasinan = _ogrenciler(okul["a"])[0]  # okul no 101
    persons.update_student(Student.objects.get(pk=tasinan), class_section="B")
    yeni = persons.create_student(
        first_name="AD9", last_name="SOYAD", student_number="999", class_level=9, class_section="B"
    )

    with transaction.atomic():
        on = enrollment_import._ingest(
            _rapor(("SEÇMELİ ALMANCA", [("101", 9, "B")])), source_hash="p" * 64, file_name=""
        )
        transaction.set_rollback(True)
    assert on.pending_resolved == 1
    sonuc = enrollment_import._ingest(
        _rapor(("SEÇMELİ ALMANCA", [("101", 9, "B")])), source_hash="q" * 64, file_name=""
    )

    assert sonuc.pending_resolved == 1
    assert _bekleyen(tasinan) is None
    # Raporda geçmeyen öğrenci beklemeye devam eder (rapor eski olabilir).
    assert _bekleyen(yeni.pk) is not None


# ===========================================================================
# Veri göçü 0009 — güncellemeden ÖNCE şube değiştirmiş / ayrılmış öğrenciler
# ===========================================================================


def test_goc_eski_artiklari_toparlar_ve_secimi_bekletir(okul: dict[str, Any]) -> None:
    import importlib

    from django.apps import apps as django_apps

    goc = importlib.import_module("apps.dersler.migrations.0009_secmeli_liste_bayat_satirlar")
    tasinan, ayrilan = _ogrenciler(okul["a"])[:2]
    # Eski sürümün izi: köprüsüz değişiklik — satırlar yerinde kalmıştı.
    Student.objects.filter(pk=tasinan).update(class_section="B")
    Student.objects.filter(pk=ayrilan).update(status=StudentStatus.LEFT)
    assert CourseEnrollment.objects.filter(student_id__in=[tasinan, ayrilan]).count() == 2

    goc.toparla(django_apps, None)
    goc.toparla(django_apps, None)  # yinelenince zararsız

    assert not CourseEnrollment.all_objects.filter(student_id__in=[tasinan, ayrilan]).exists()
    bekleyen = _bekleyen(tasinan)
    assert bekleyen is not None and bekleyen.section_id == okul["b"].pk
    assert bekleyen.previous_course_ids == [okul["al"].pk]
    assert PendingElectiveChoice.all_objects.count() == 1
    # Yerinde kalan öğrencilerin listelerine dokunulmadı.
    assert CourseEnrollment.objects.filter(section=okul["b"]).count() == 4


# ===========================================================================
# API
# ===========================================================================


def test_api_bekleyenleri_listeler_ve_secimi_kaydeder(okul: dict[str, Any]) -> None:
    ogr = _ogrenciler(okul["a"])[0]
    persons.update_student(Student.objects.get(pk=ogr), class_section="B")
    client = APIClient()

    liste = client.get("/api/v1/courses/elective-choices/")
    assert liste.status_code == 200, liste.json()
    [satir] = liste.json()["results"]
    assert satir["student_id"] == ogr and satir["class_label"] == "9/B"
    dersler = {d["course_name"]: d for d in satir["courses"]}
    assert set(dersler) == {"Almanca", "Fransızca"}
    assert dersler["Almanca"]["suggested"] is True
    assert dersler["Almanca"]["enrolled"] is False
    assert dersler["Fransızca"]["listed_count"] == 2

    kayit = client.post(
        "/api/v1/courses/elective-choices/resolve/",
        {"student_id": ogr, "course_ids": [okul["al"].pk]},
        format="json",
    )
    assert kayit.status_code == 200, kayit.json()
    assert client.get("/api/v1/courses/elective-choices/").json()["results"] == []

    tekrar = client.post(
        "/api/v1/courses/elective-choices/resolve/",
        {"student_id": ogr, "course_ids": []},
        format="json",
    )
    assert tekrar.status_code == 400
    bozuk = client.post(
        "/api/v1/courses/elective-choices/resolve/", {"student_id": "x"}, format="json"
    )
    assert bozuk.status_code == 400


def test_api_oturum_katilimci_ucu_bekleyeni_bildirir(okul: dict[str, Any]) -> None:
    persons.update_student(Student.objects.get(pk=_ogrenciler(okul["a"])[0]), class_section="B")
    session = _bolunmus_oturum(okul)

    yanit = APIClient().get(f"/api/v1/exam-sessions/{session.pk}/participants/").json()

    assert yanit["has_pending_choices"] is True
    assert "Seçimleri yap" in yanit["pending_choices_message"]
