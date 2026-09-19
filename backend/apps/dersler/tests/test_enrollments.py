"""Seçmeli ders öğrenci listesi (19.09.2026) — `CourseEnrollment` + e-Okul OOK10002R010.

"9/A'da bir grup Kur'an-ı Kerim, bir grup Peygamberimizin Hayatı alıyor": liste
ŞUBE BAZINDADIR — listesiz şubeyi dersi tamamen alır, listeli şubede yalnız
listedekiler. Oturum ve takvim tarafının testleri `apps/sinav/tests/`
(`test_participants.py`, `test_calendar.py`) içindedir.

Veri tamamen sentetiktir: okul numaraları kısa, adlar "AD0/SOYAD" kalıbındadır;
e-Okul PDF'i test sırasında WeasyPrint ile ÜRETİLİR (depoya ikili fixture girmez).
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework.test import APIClient

from apps.dersler import enrollment_import, selectors, services
from apps.dersler.enrollment_import import ParsedReport, ReportGroup, ReportLine
from apps.dersler.models import Course, CourseAlias, CourseEnrollment, CourseType
from apps.dersler.text import course_match_key
from apps.okul.excel_ogrenci import ParserError
from apps.okul.models import ClassSection, ImportRun, ImportSourceType, ImportStatus, Student
from apps.sinav.tests.oturum_yardim import aktif_yil, sube

pytestmark = pytest.mark.django_db


def _secmeli(ad: str, levels: list[int] | None = None) -> Course:
    ders: Course = Course.objects.create(
        name=ad, levels=levels or [9, 10, 11, 12], course_type=CourseType.ELECTIVE
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


# ===========================================================================
# Servis — şube bazında liste
# ===========================================================================


def test_liste_yazilir_okunur_ve_subeyi_kapsama_ekler() -> None:
    a = sube(9, "A", students=4, start_no=101)
    kk = _secmeli("Kur'an-ı Kerim")
    ids = _ogrenciler(a)[:2]

    sonuc = services.set_section_enrollment(
        course_id=kk.pk, school_year_id=aktif_yil().pk, section_id=a.pk, student_ids=ids
    )

    assert sonuc["student_ids"] == ids
    assert services.course_enrollments(course_id=kk.pk, school_year_id=aktif_yil().pk) == {
        a.pk: sorted(ids)
    }
    # Listelenen şube dersin okutulduğu şubedir — kapsam ikinci kez girilmez.
    assert selectors.course_section_map(aktif_yil().pk)[(kk.pk, 9)] == [a.pk]


def test_bos_liste_subenin_tamami_demektir_ve_satirlari_kalici_siler() -> None:
    a = sube(9, "A", students=3, start_no=101)
    kk = _secmeli("Kur'an-ı Kerim")
    yil = aktif_yil().pk
    services.set_section_enrollment(
        course_id=kk.pk, school_year_id=yil, section_id=a.pk, student_ids=_ogrenciler(a)[:1]
    )

    services.set_section_enrollment(
        course_id=kk.pk, school_year_id=yil, section_id=a.pk, student_ids=[]
    )

    assert services.course_enrollments(course_id=kk.pk, school_year_id=yil) == {}
    # Güncel durum listesidir: silinen satır yumuşak silinmiş olarak KALMAZ (KVKK).
    assert not CourseEnrollment.all_objects.exists()
    # Şube kapsamda kalır — listesiz şube dersi tamamen alır.
    assert selectors.course_section_map(yil)[(kk.pk, 9)] == [a.pk]


def test_kalanlar_obur_derse_atanir() -> None:
    """9/A'nın bir grubu Kur'an-ı Kerim, kalanı Peygamberimizin Hayatı — tek adım."""
    a = sube(9, "A", students=5, start_no=101)
    kk = _secmeli("Kur'an-ı Kerim")
    ph = _secmeli("Peygamberimizin Hayatı")
    ogr = _ogrenciler(a)
    yil = aktif_yil().pk

    sonuc = services.set_section_enrollment(
        course_id=kk.pk,
        school_year_id=yil,
        section_id=a.pk,
        student_ids=ogr[:2],
        complement_course_id=ph.pk,
    )

    assert sonuc["complement"] == {"course_id": ph.pk, "student_ids": sorted(ogr[2:])}
    assert services.course_enrollments(course_id=ph.pk, school_year_id=yil) == {
        a.pk: sorted(ogr[2:])
    }
    assert selectors.course_section_map(yil)[(ph.pk, 9)] == [a.pk]


def test_kalan_yoksa_obur_ders_subeden_cikar() -> None:
    """Listesiz şube 'tamamı' demek: 'kimse almıyor' ancak kapsamdan çıkarak ifade edilir."""
    a = sube(9, "A", students=2, start_no=101)
    kk = _secmeli("Kur'an-ı Kerim")
    ph = _secmeli("Peygamberimizin Hayatı")
    yil = aktif_yil().pk
    services.set_course_sections(
        course_id=ph.pk, school_year_id=yil, offerings=[{"level": 9, "section_ids": [a.pk]}]
    )

    services.set_section_enrollment(
        course_id=kk.pk,
        school_year_id=yil,
        section_id=a.pk,
        student_ids=_ogrenciler(a),
        complement_course_id=ph.pk,
    )

    assert (ph.pk, 9) not in selectors.course_section_map(yil)
    assert services.course_enrollments(course_id=ph.pk, school_year_id=yil) == {}


@pytest.mark.parametrize("sorun", ["zorunlu", "yabanci_ogrenci", "duzey", "ayni_ders"])
def test_gecersiz_liste_reddedilir(sorun: str) -> None:
    a = sube(9, "A", students=2, start_no=101)
    b = sube(9, "B", students=1, start_no=201)
    kk = _secmeli("Kur'an-ı Kerim", levels=[9])
    yil = aktif_yil().pk
    kwargs: dict[str, Any] = {
        "course_id": kk.pk,
        "school_year_id": yil,
        "section_id": a.pk,
        "student_ids": _ogrenciler(a),
    }
    if sorun == "zorunlu":
        kwargs["course_id"] = Course.objects.create(name="Matematik", levels=[9]).pk
    elif sorun == "yabanci_ogrenci":
        kwargs["student_ids"] = _ogrenciler(b)
    elif sorun == "duzey":
        kwargs["section_id"] = sube(10, "A").pk
    else:
        kwargs["complement_course_id"] = kk.pk

    with pytest.raises(ValidationError) as exc:
        services.set_section_enrollment(**kwargs)
    # Hata metni öğrenci adı taşımaz (KVKK).
    assert "AD0" not in str(exc.value)
    assert not CourseEnrollment.objects.exists()


def test_kapsamdan_cikan_subenin_listesi_duser() -> None:
    a = sube(9, "A", students=2, start_no=101)
    b = sube(9, "B", students=2, start_no=201)
    kk = _secmeli("Kur'an-ı Kerim")
    yil = aktif_yil().pk
    for s in (a, b):
        services.set_section_enrollment(
            course_id=kk.pk, school_year_id=yil, section_id=s.pk, student_ids=_ogrenciler(s)[:1]
        )

    services.set_course_sections(
        course_id=kk.pk, school_year_id=yil, offerings=[{"level": 9, "section_ids": [a.pk]}]
    )

    assert list(services.course_enrollments(course_id=kk.pk, school_year_id=yil)) == [a.pk]
    assert CourseEnrollment.all_objects.count() == 1


def test_sube_degistiren_ogrencinin_eski_satiri_yeni_listede_silinir() -> None:
    a = sube(9, "A", students=1, start_no=101)
    b = sube(9, "B", students=1, start_no=201)
    kk = _secmeli("Kur'an-ı Kerim")
    yil = aktif_yil().pk
    ogr = Student.objects.get(student_number="101")
    services.set_section_enrollment(
        course_id=kk.pk, school_year_id=yil, section_id=a.pk, student_ids=[ogr.pk]
    )
    ogr.class_section = "B"
    ogr.save()

    services.set_section_enrollment(
        course_id=kk.pk, school_year_id=yil, section_id=b.pk, student_ids=[ogr.pk, *_ogrenciler(b)]
    )

    listeler = services.course_enrollments(course_id=kk.pk, school_year_id=yil)
    assert ogr.pk not in listeler.get(a.pk, [])
    assert ogr.pk in listeler[b.pk]


def test_sayim_ozeti_yalniz_sayi_tasir() -> None:
    a = sube(9, "A", students=3, start_no=101)
    kk = _secmeli("Kur'an-ı Kerim")
    yil = aktif_yil().pk
    services.set_section_enrollment(
        course_id=kk.pk, school_year_id=yil, section_id=a.pk, student_ids=_ogrenciler(a)[:2]
    )
    assert selectors.course_enrollment_counts(yil) == {(kk.pk, a.pk): 2}


# ===========================================================================
# Günlük sınav yükü köprüsü (TB10) — yalnız TAM veride küme döner
# ===========================================================================


def test_kayit_kumesi_yalniz_butun_kapsam_listeliyken_doner() -> None:
    a = sube(9, "A", students=3, start_no=101)
    b = sube(9, "B", students=2, start_no=201)
    kk = _secmeli("Kur'an-ı Kerim")
    yil = aktif_yil().pk
    services.set_course_sections(
        course_id=kk.pk, school_year_id=yil, offerings=[{"level": 9, "section_ids": [a.pk, b.pk]}]
    )
    services.set_section_enrollment(
        course_id=kk.pk, school_year_id=yil, section_id=a.pk, student_ids=_ogrenciler(a)[:1]
    )

    # 9/B listesiz (= şubenin tamamı beyanı, kayıt verisi değil) → bilinmiyor.
    assert selectors.course_level_student_ids(course_id=kk.pk, level=9, school_year_id=yil) == set()

    services.set_section_enrollment(
        course_id=kk.pk, school_year_id=yil, section_id=b.pk, student_ids=_ogrenciler(b)[:1]
    )
    assert selectors.course_level_student_ids(course_id=kk.pk, level=9, school_year_id=yil) == {
        _ogrenciler(a)[0],
        _ogrenciler(b)[0],
    }


def test_kapsami_olmayan_derste_kayit_kumesi_bos() -> None:
    kk = _secmeli("Kur'an-ı Kerim")
    assert (
        selectors.course_level_student_ids(course_id=kk.pk, level=9, school_year_id=aktif_yil().pk)
        == set()
    )


# ===========================================================================
# e-Okul OOK10002R010 — saf ayrıştırma
# ===========================================================================

BASLIK_KK = "SEÇMELİ KUR`AN-I KERİM DERSİ ÖĞRENCİLERİ"
BASLIK_PH = "SEÇMELİ PEYGAMBERİMİZİN HAYATI DERSİ ÖĞRENCİLERİ"
SUTUNLAR = "Öğr.No Adı Soyadı Sınıfı"


def _satir(no: int, sinif: str, sira: int) -> str:
    return f"{no} AD SOYAD AL -  {sinif} (ALANI YOK - DAL YOK) {sira}"


def test_sayfa_metninden_gruplar_cikar() -> None:
    sayfalar = [
        "\n".join(
            [
                "T.C.",
                BASLIK_KK,
                SUTUNLAR,
                _satir(101, "9. Sınıf / A Şubesi", 1),
                _satir(102, "9. Sınıf / İ Şubesi", 2),
                "19.09.2026",  # sayfa altı tarih damgası — aday satır değil
            ]
        ),
        "\n".join([BASLIK_KK, SUTUNLAR, _satir(103, "9. Sınıf / I Şubesi", 3)]),
        "\n".join([BASLIK_PH, SUTUNLAR, _satir(104, "10. Sınıf / B Şubesi", 1), "999 bozuk satır"]),
    ]

    rapor = enrollment_import.parse_report_pages(sayfalar)

    assert rapor.pages == 3
    assert [g.title for g in rapor.groups] == [
        "SEÇMELİ KUR`AN-I KERİM",
        "SEÇMELİ PEYGAMBERİMİZİN HAYATI",
    ]
    kk = rapor.groups[0].lines
    assert [(s.student_number, s.class_level, s.class_section) for s in kk] == [
        ("101", 9, "A"),
        ("102", 9, "İ"),  # İ ile I şubesi ayrı kalır (normalize.tr_upper gerekçesi)
        ("103", 9, "I"),
    ]
    assert rapor.unreadable == [(3, 4)]
    assert rapor.total_rows == 4


def test_ad_satirdan_okunmaz() -> None:
    """KVKK: ayrıştırıcı ad soyadı yakalamaz — satır nesnesinde ad alanı YOK."""
    rapor = enrollment_import.parse_report_pages(
        ["\n".join([BASLIK_KK, _satir(101, "9. Sınıf / A Şubesi", 1)])]
    )
    satir = rapor.groups[0].lines[0]
    assert "AD" not in repr(satir) and "SOYAD" not in repr(satir)


def test_pdf_olmayan_dosya_turkce_hata_verir() -> None:
    with pytest.raises(ParserError, match="PDF olarak okunamadı"):
        enrollment_import.parse_report_pdf(b"bu bir pdf degil")


def _pdf(sayfalar: list[list[str]]) -> bytes:
    """Sentetik e-Okul raporu PDF'i (WeasyPrint) — her satır ayrı paragraf."""
    from weasyprint import HTML

    govde = "".join(
        '<section style="page-break-after: always">'
        + "".join(f"<p style='margin:0'>{s}</p>" for s in sayfa)
        + "</section>"
        for sayfa in sayfalar
    )
    tampon = BytesIO()
    HTML(string=f"<html><body>{govde}</body></html>").write_pdf(tampon)
    return tampon.getvalue()


def test_pdf_uretilen_raporu_okur() -> None:
    bayt = _pdf(
        [
            [BASLIK_KK, SUTUNLAR, _satir(101, "9. Sınıf / A Şubesi", 1)],
            [BASLIK_PH, SUTUNLAR, _satir(102, "9. Sınıf / A Şubesi", 1)],
        ]
    )
    rapor = enrollment_import.parse_report_pdf(bayt)
    assert [(g.title, [s.student_number for s in g.lines]) for g in rapor.groups] == [
        ("SEÇMELİ KUR`AN-I KERİM", ["101"]),
        ("SEÇMELİ PEYGAMBERİMİZİN HAYATI", ["102"]),
    ]


def test_basliksiz_pdf_reddedilir() -> None:
    with pytest.raises(ParserError, match="başlığı bulunamadı"):
        enrollment_import.parse_report_pdf(
            _pdf([["Öğrenci Listesi", _satir(1, "9. Sınıf / A Şubesi", 1)]])
        )


# ===========================================================================
# e-Okul başlığı → havuzdaki seçmeli ders
# ===========================================================================


def _takma(ad: str, hedef: Course) -> None:
    CourseAlias.objects.create(alias_key=course_match_key(ad), display_name=ad, course=hedef)


def test_ders_adi_cozumu() -> None:
    secmeli_mat = _secmeli("Seçmeli Matematik", levels=[11, 12])
    Course.objects.create(name="Matematik", levels=[9, 10])  # zorunlu adaş
    adab = _secmeli("Adabımuaşeret")
    _takma("Seçmeli Adabımuaşeret", adab)
    kk = _secmeli("Kur'an-ı Kerim")
    birinci = Course.objects.create(name="Birinci Yabancı Dil", levels=[9, 10, 11, 12])
    _takma("Yabancı Dil", birinci)
    secmeli_birinci = _secmeli("Seçmeli Birinci Yabancı Dil", levels=[11, 12])

    def cozum(baslik: str) -> Course | None:
        return enrollment_import.resolve_report_course(baslik)[0]

    assert cozum("SEÇMELİ MATEMATİK") == secmeli_mat
    assert cozum("SEÇMELİ ADABIMUAŞERET") == adab
    assert cozum("SEÇMELİ KUR`AN-I KERİM") == kk  # ters tırnak
    # Takma ad zinciri zorunlu 'Birinci Yabancı Dil'e düşerdi; doğrusu seçmeli karşılığı.
    assert cozum("SEÇMELİ YABANCI DİL") == secmeli_birinci


def test_zorunlu_ya_da_bilinmeyen_ders_gerekceyle_doner() -> None:
    Course.objects.create(name="Fizik", levels=[9, 10])
    ders, neden = enrollment_import.resolve_report_course("FİZİK")
    assert ders is None and "zorunlu ders" in neden
    ders, neden = enrollment_import.resolve_report_course("SEÇMELİ OLMAYAN DERS")
    assert ders is None and "karşılığı bulunamadı" in neden


# ===========================================================================
# Yazım — önizleme/aktarım (PDF'siz: ayrıştırılmış rapor doğrudan verilir)
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


@pytest.fixture
def okul(settings: Any, tmp_path: Any) -> dict[str, Any]:
    """9/A (4) + 9/B (2) öğrenci, iki din seçmelisi; katalog senkronu tmp dizine kapalı."""
    settings.CATALOG_DIR = tmp_path
    settings.COURSE_ALIAS_FILE = tmp_path / "takma-ad-yok.md"
    a = sube(9, "A", students=4, start_no=101)
    b = sube(9, "B", students=2, start_no=201)
    kk = _secmeli("Kur'an-ı Kerim", levels=[9, 10, 11, 12])
    _takma("Seçmeli Kur'an-ı Kerim", kk)
    ph = _secmeli("Peygamberimizin Hayatı", levels=[9, 10, 11, 12])
    _takma("Seçmeli Peygamberimizin Hayatı", ph)
    return {"a": a, "b": b, "kk": kk, "ph": ph, "yil": aktif_yil()}


def test_onizleme_yazmaz_aktarim_yazar(okul: dict[str, Any]) -> None:
    rapor = _rapor(
        ("SEÇMELİ KUR`AN-I KERİM", [("101", 9, "A"), ("102", 9, "A")]),
        ("SEÇMELİ PEYGAMBERİMİZİN HAYATI", [("103", 9, "A"), ("104", 9, "A"), ("201", 9, "B")]),
    )

    with transaction.atomic():  # önizleme deseni (`_giris`): gerçek yazım + geri alma
        on = enrollment_import._ingest(rapor, source_hash="x" * 64, file_name="r.pdf")
        transaction.set_rollback(True)
    assert on.processed == 5 and not CourseEnrollment.objects.exists()

    sonuc = enrollment_import._ingest(rapor, source_hash="y" * 64, file_name="r.pdf")

    assert [(c.course_name, c.students, c.sections) for c in sonuc.courses] == [
        ("Kur'an-ı Kerim", 2, ["9/A"]),
        ("Peygamberimizin Hayatı", 3, ["9/A", "9/B"]),
    ]
    kk_listesi = services.course_enrollments(course_id=okul["kk"].pk, school_year_id=okul["yil"].pk)
    assert {k: len(v) for k, v in kk_listesi.items()} == {okul["a"].pk: 2}
    harita = selectors.course_section_map(okul["yil"].pk)
    assert harita[(okul["ph"].pk, 9)] == sorted([okul["a"].pk, okul["b"].pk])
    assert ImportRun.objects.filter(
        source_type=ImportSourceType.ELECTIVES, status=ImportStatus.COMPLETED
    ).exists()


def _numaralar(ids: list[int]) -> list[str]:
    return sorted(Student.objects.filter(pk__in=ids).values_list("student_number", flat=True))


def test_yeniden_aktarim_kapsanan_subelerde_listeyi_tamamen_yeniler(okul: dict[str, Any]) -> None:
    enrollment_import._ingest(
        _rapor(("SEÇMELİ KUR`AN-I KERİM", [("101", 9, "A"), ("201", 9, "B")])),
        source_hash="a" * 64,
        file_name="",
    )
    # İkinci rapor iki şubeyi de kapsar; 9/B'nin öğrencisi artık yalnız
    # Peygamberimizin Hayatı alıyor → Kur'an-ı Kerim 9/B'den ÇIKAR.
    enrollment_import._ingest(
        _rapor(
            ("SEÇMELİ KUR`AN-I KERİM", [("102", 9, "A")]),
            ("SEÇMELİ PEYGAMBERİMİZİN HAYATI", [("201", 9, "B")]),
        ),
        source_hash="b" * 64,
        file_name="",
    )

    listeler = services.course_enrollments(course_id=okul["kk"].pk, school_year_id=okul["yil"].pk)
    assert list(listeler) == [okul["a"].pk]
    assert _numaralar(listeler[okul["a"].pk]) == ["102"]
    assert selectors.course_section_map(okul["yil"].pk)[(okul["kk"].pk, 9)] == [okul["a"].pk]
    # Eski satırlar kalıcı silindi (soft-delete artığı yok).
    assert CourseEnrollment.all_objects.filter(course=okul["kk"]).count() == 1


def test_kismi_rapor_kapsam_disi_subenin_listesini_silmez(okul: dict[str, Any]) -> None:
    """e-Okul raporu tek şube/düzey için alınmışsa öbür şubelerin listesi KORUNUR."""
    enrollment_import._ingest(
        _rapor(
            ("SEÇMELİ KUR`AN-I KERİM", [("101", 9, "A"), ("102", 9, "A"), ("201", 9, "B")]),
            ("SEÇMELİ PEYGAMBERİMİZİN HAYATI", [("103", 9, "A"), ("104", 9, "A"), ("202", 9, "B")]),
        ),
        source_hash="f" * 64,
        file_name="",
    )

    # Yalnız 9/A için alınmış rapor; 102 Peygamberimizin Hayatı'na geçmiş.
    sonuc = enrollment_import._ingest(
        _rapor(
            ("SEÇMELİ KUR`AN-I KERİM", [("101", 9, "A")]),
            ("SEÇMELİ PEYGAMBERİMİZİN HAYATI", [("102", 9, "A"), ("103", 9, "A"), ("104", 9, "A")]),
        ),
        source_hash="g" * 64,
        file_name="",
    )

    assert sonuc.covered_section_count == 1
    assert sonuc.covered_levels == ["9. Sınıf"]
    yil = okul["yil"].pk
    kk = services.course_enrollments(course_id=okul["kk"].pk, school_year_id=yil)
    ph = services.course_enrollments(course_id=okul["ph"].pk, school_year_id=yil)
    assert _numaralar(kk[okul["a"].pk]) == ["101"]
    assert _numaralar(kk[okul["b"].pk]) == ["201"]  # kapsam dışı — dokunulmadı
    assert _numaralar(ph[okul["a"].pk]) == ["102", "103", "104"]
    assert _numaralar(ph[okul["b"].pk]) == ["202"]
    harita = selectors.course_section_map(yil)
    assert harita[(okul["kk"].pk, 9)] == sorted([okul["a"].pk, okul["b"].pk])
    assert harita[(okul["ph"].pk, 9)] == sorted([okul["a"].pk, okul["b"].pk])


def test_kapsanan_subede_ogrencisi_kalmayan_dersin_kapsami_kalkar(okul: dict[str, Any]) -> None:
    """Rapordaki derste bir düzeyin bütün şubeleri boşalırsa kapsam kaydı da kalkar."""
    enrollment_import._ingest(
        _rapor(("SEÇMELİ KUR`AN-I KERİM", [("101", 9, "A")])), source_hash="h" * 64, file_name=""
    )
    # Ders raporda var ama 9/A satırı artık Peygamberimizin Hayatı'nda; Kur'an-ı
    # Kerim grubunda tanınmayan (listede olmayan) bir numara kalmış.
    sonuc = enrollment_import._ingest(
        _rapor(
            ("SEÇMELİ KUR`AN-I KERİM", [("999", 9, "A")]),
            ("SEÇMELİ PEYGAMBERİMİZİN HAYATI", [("101", 9, "A")]),
        ),
        source_hash="i" * 64,
        file_name="",
    )

    assert (okul["kk"].pk, 9) not in selectors.course_section_map(okul["yil"].pk)
    assert not services.course_enrollments(course_id=okul["kk"].pk, school_year_id=okul["yil"].pk)
    assert any(s.value == "999" for s in sonuc.skipped)


def test_raporda_olmayan_derse_dokunulmaz_ve_listelenir(okul: dict[str, Any]) -> None:
    services.set_section_enrollment(
        course_id=okul["ph"].pk,
        school_year_id=okul["yil"].pk,
        section_id=okul["a"].pk,
        student_ids=_ogrenciler(okul["a"])[:1],
    )

    sonuc = enrollment_import._ingest(
        _rapor(("SEÇMELİ KUR`AN-I KERİM", [("101", 9, "A")])), source_hash="c" * 64, file_name=""
    )

    assert sonuc.untouched_courses == ["Peygamberimizin Hayatı"]
    assert services.course_enrollments(course_id=okul["ph"].pk, school_year_id=okul["yil"].pk)


def test_sorunlu_satirlar_konumla_raporlanir_ad_yazilmaz(okul: dict[str, Any]) -> None:
    Student.objects.filter(student_number="102").update(class_section="B")
    sonuc = enrollment_import._ingest(
        _rapor(
            ("SEÇMELİ KUR`AN-I KERİM", [("999", 9, "A"), ("102", 9, "A"), ("101", 9, "A")]),
            ("SEÇMELİ OLMAYAN DERS", [("103", 9, "A")]),
        ),
        source_hash="d" * 64,
        file_name="",
    )

    atlananlar = {s.value: s.issue for s in sonuc.skipped}
    assert "aktif öğrenci kaydı yok" in atlananlar["999"]
    assert any("aktarılmadı" in s.issue for s in sonuc.skipped)
    assert [w.value for w in sonuc.warnings] == ["102"]
    assert "kayıttaki şube kullanıldı" in sonuc.warnings[0].issue
    # Kayıttaki şubeye (9/B) yazıldı.
    listeler = services.course_enrollments(course_id=okul["kk"].pk, school_year_id=okul["yil"].pk)
    assert Student.objects.get(student_number="102").pk in listeler[okul["b"].pk]
    metin = repr(sonuc.to_dict())
    assert "AD0" not in metin and "SOYAD" not in metin


def test_aktif_yil_yoksa_turkce_hata(okul: dict[str, Any]) -> None:
    okul["yil"].is_active = False
    okul["yil"].save()
    with pytest.raises(ParserError, match="Aktif ders yılı yok"):
        enrollment_import._ingest(
            _rapor(("SEÇMELİ KUR`AN-I KERİM", [])), source_hash="e" * 64, file_name=""
        )


# ===========================================================================
# API
# ===========================================================================


def test_api_liste_okuma_yazma_ve_sayim(okul: dict[str, Any]) -> None:
    client = APIClient()
    ids = _ogrenciler(okul["a"])[:2]
    url = f"/api/v1/courses/{okul['kk'].pk}/enrollments/"

    yanit = client.put(
        url,
        {"section_id": okul["a"].pk, "student_ids": ids, "complement_course_id": okul["ph"].pk},
        format="json",
    )
    assert yanit.status_code == 200, yanit.json()
    assert yanit.json()["complement"]["course_id"] == okul["ph"].pk

    assert client.get(url).json()["sections"] == [{"section_id": okul["a"].pk, "student_ids": ids}]
    sayim = client.get("/api/v1/courses/enrollment-counts/").json()["results"]
    assert {(r["course"], r["count"]) for r in sayim} == {(okul["kk"].pk, 2), (okul["ph"].pk, 2)}

    hatali = client.put(url, {"section_id": "x", "student_ids": ids}, format="json")
    assert hatali.status_code == 400


def test_api_pdf_onizleme_ve_aktarim(okul: dict[str, Any]) -> None:
    from django.core.files.uploadedfile import SimpleUploadedFile

    bayt = _pdf([[BASLIK_KK, SUTUNLAR, _satir(101, "9. Sınıf / A Şubesi", 1)]])
    client = APIClient()

    on = client.post(
        "/api/v1/courses/enrollments/import/preview/",
        {"file": SimpleUploadedFile("r.pdf", bayt, content_type="application/pdf")},
        format="multipart",
    )
    assert on.status_code == 200, on.json()
    assert on.json()["dry_run"] is True and on.json()["processed"] == 1
    assert not CourseEnrollment.objects.exists()

    ak = client.post(
        "/api/v1/courses/enrollments/import/commit/",
        {"file": SimpleUploadedFile("r.pdf", bayt, content_type="application/pdf")},
        format="multipart",
    )
    assert ak.status_code == 200 and CourseEnrollment.objects.count() == 1

    bozuk = client.post(
        "/api/v1/courses/enrollments/import/preview/",
        {"file": SimpleUploadedFile("r.pdf", b"x", content_type="application/pdf")},
        format="multipart",
    )
    assert bozuk.status_code == 400
    assert ImportRun.objects.filter(status=ImportStatus.FAILED).exists()
    assert client.post("/api/v1/courses/enrollments/import/preview/", {}).status_code == 400
