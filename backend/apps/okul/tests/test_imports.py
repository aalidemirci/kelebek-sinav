"""İçe aktarma servisi — okul-no upsert, dry-run paritesi, idempotency, şube tohumu.

DD test kalıbından KS'ye uyarlandı: TCKN/veli senaryoları kalktı; upsert
anahtarı okul numarası, şube tohumu ClassSection'a yazar.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from apps.okul.models import (
    ClassSection,
    ImportRun,
    ImportStatus,
    Personnel,
    SchoolYear,
    Student,
    StudentStatus,
)
from apps.okul.services import imports as import_service

BASLIK = "Sınıf\tOkul No\tAdı Soyadı"

#: Sentetik e-Okul ihraç örnekleri (gerçek veri DEĞİL — bkz. tests/veri/).
VERI = Path(__file__).resolve().parent / "veri"
EOKUL_SINIF_LISTESI = VERI / "eokul_sinif_listesi.xls"
EOKUL_PERSONEL_LISTESI = VERI / "eokul_personel_listesi.xls"


def _metin(*satirlar: str) -> str:
    return "\n".join([BASLIK, *satirlar])


@pytest.fixture
def aktif_yil() -> SchoolYear:
    yil: SchoolYear = SchoolYear.objects.create(
        name="2026-2027",
        start_date=date(2026, 9, 1),
        end_date=date(2027, 6, 30),
        is_active=True,
    )
    return yil


@pytest.mark.django_db
class TestStudentCommit:
    def test_yeni_ogrenciler_olusur(self, aktif_yil: SchoolYear) -> None:
        rapor = import_service.commit_students_text(
            text=_metin("10/A\t101\tEMRE CAN YILMAZ", "10/B\t102\tZEYNEP KAYA")
        )
        assert rapor.created_students == 2
        assert rapor.processed == 2
        ogrenci = Student.objects.get(student_number="101")
        assert ogrenci.first_name == "EMRE CAN"
        assert ogrenci.class_label == "10/A"

    def test_ayni_numara_gunceller_yeni_satir_acmaz(self, aktif_yil: SchoolYear) -> None:
        import_service.commit_students_text(text=_metin("10/A\t101\tEMRE CAN YILMAZ"))
        rapor = import_service.commit_students_text(text=_metin("11/A\t101\tEMRE CAN YILMAZ"))
        assert rapor.updated_students == 1
        assert Student.objects.count() == 1
        assert Student.objects.get(student_number="101").class_level == 11

    def test_degismeyen_satir_unchanged_sayilir(self, aktif_yil: SchoolYear) -> None:
        import_service.commit_students_text(text=_metin("10/A\t101\tEMRE CAN YILMAZ"))
        rapor = import_service.commit_students_text(text=_metin("10/A\t101\tEMRE CAN YILMAZ"))
        assert rapor.unchanged_students == 1
        assert rapor.already_imported is True  # aynı hash — uyarı, engel değil

    def test_numarasiz_satir_atlanir(self, aktif_yil: SchoolYear) -> None:
        rapor = import_service.commit_students_text(text=_metin("10/A\t\tADSIZ ÖĞRENCİ"))
        assert rapor.created_students == 0
        assert rapor.skipped and rapor.skipped[0].field == "number"

    def test_cozulmeyen_sinif_atlanir(self, aktif_yil: SchoolYear) -> None:
        rapor = import_service.commit_students_text(text=_metin("8/A\t101\tALİ VELİ"))
        assert rapor.skipped and rapor.skipped[0].field == "class"

    def test_ayrilmis_ogrenci_eslesmez_yeni_aktif_kayit_acilir(self, aktif_yil: SchoolYear) -> None:
        """Numara yeniden kullanımı: LEFT kayıt upsert'e takılmaz (aktif-eşleşme)."""
        Student.objects.create(
            first_name="ESKİ",
            last_name="ÖĞRENCİ",
            student_number="101",
            status=StudentStatus.LEFT,
        )
        rapor = import_service.commit_students_text(text=_metin("9/A\t101\tYENİ ÖĞRENCİ"))
        assert rapor.created_students == 1
        assert Student.objects.filter(student_number="101").count() == 2

    def test_sube_katalogu_tohumlanir(self, aktif_yil: SchoolYear) -> None:
        import_service.commit_students_text(
            text=_metin("10/A\t101\tEMRE CAN YILMAZ", "10/B\t102\tZEYNEP KAYA")
        )
        etiketler = sorted(s.class_label for s in ClassSection.objects.all())
        assert etiketler == ["10/A", "10/B"]

    def test_aktif_yil_yoksa_tohum_sessizce_atlanir(self) -> None:
        rapor = import_service.commit_students_text(text=_metin("10/A\t101\tEMRE CAN YILMAZ"))
        assert rapor.created_students == 1
        assert ClassSection.objects.count() == 0

    def test_hazirlik_sinifi_config_bayragina_bagli(self, aktif_yil: SchoolYear) -> None:
        from apps.okul.models import SchoolConfig

        SchoolConfig.objects.create(pk=SchoolConfig.SINGLETON_PK, has_prep_class=True)
        rapor = import_service.commit_students_text(text=_metin("HAZIRLIK/A\t101\tALİ VELİ"))
        assert rapor.created_students == 1
        assert Student.objects.get(student_number="101").class_level == 0


@pytest.mark.django_db
class TestPreview:
    def test_dry_run_hicbir_sey_yazmaz_ama_rapor_paritesi_tam(self, aktif_yil: SchoolYear) -> None:
        metin = _metin("10/A\t101\tEMRE CAN YILMAZ", "8/X\t103\tKUME DIŞI")
        onizleme = import_service.preview_students_text(text=metin)
        assert onizleme.dry_run is True
        assert Student.objects.count() == 0
        assert ClassSection.objects.count() == 0

        gercek = import_service.commit_students_text(text=metin)
        assert onizleme.created_students == gercek.created_students
        assert [s.issue for s in onizleme.skipped] == [s.issue for s in gercek.skipped]

    def test_onizleme_kalici_iz_birakir(self, aktif_yil: SchoolYear) -> None:
        import_service.preview_students_text(text=_metin("10/A\t101\tEMRE CAN YILMAZ"))
        assert ImportRun.objects.filter(status=ImportStatus.PREVIEWED).count() == 1


@pytest.mark.django_db
class TestImportRunLifecycle:
    def test_ayni_hash_yeniden_commit_mevcut_satiri_gunceller(self, aktif_yil: SchoolYear) -> None:
        metin = _metin("10/A\t101\tEMRE CAN YILMAZ")
        import_service.commit_students_text(text=metin)
        import_service.commit_students_text(text=metin)
        assert ImportRun.objects.filter(status=ImportStatus.COMPLETED).count() == 1

    def test_parser_hatasi_failed_izi_birakir(self, aktif_yil: SchoolYear) -> None:
        from apps.okul.excel_ogrenci import ParserError

        with pytest.raises(ParserError):
            import_service.commit_students_text(text="Alakasız\tBaşlıklar\n1\t2")
        kayit = ImportRun.objects.get(status=ImportStatus.FAILED)
        assert "Zorunlu sütun" in kayit.report["error"]

    def test_satir_sonu_farki_ayni_hashe_iner(self) -> None:
        assert import_service.text_hash("a\tb\r\nc\td") == import_service.text_hash("a\tb\nc\td")


@pytest.mark.django_db
class TestPersonnelImport:
    def test_yeni_personel_olusur_ve_ada_gore_guncellenir(self) -> None:
        rapor = import_service.commit_personnel_text(
            text="Adı\tSoyadı\tGörevi\tBranşı\nAYŞE\tÖĞRETMEN\tÖğretmen\tCoğrafya"
        )
        assert rapor.created_personnel == 1

        rapor2 = import_service.commit_personnel_text(
            text="Adı\tSoyadı\tGörevi\tBranşı\nAYŞE\tÖĞRETMEN\tMüdür Yardımcısı\tCoğrafya"
        )
        assert rapor2.updated_personnel == 1
        assert Personnel.objects.count() == 1
        kisi = Personnel.objects.first()
        assert kisi is not None and kisi.title == "Müdür Yardımcısı"

    def test_bos_hucre_mevcut_veriyi_silmez(self) -> None:
        import_service.commit_personnel_text(
            text="Adı\tSoyadı\tGörevi\tBranşı\nAYŞE\tÖĞRETMEN\tÖğretmen\tCoğrafya"
        )
        import_service.commit_personnel_text(text="Adı\tSoyadı\tGörevi\tBranşı\nAYŞE\tÖĞRETMEN\t\t")
        kisi = Personnel.objects.first()
        assert kisi is not None and kisi.branch == "Coğrafya"

    def test_bos_ad_soyad_atlanir(self) -> None:
        rapor = import_service.commit_personnel_text(text="Adı\tSoyadı\n\t")
        assert rapor.created_personnel == 0


@pytest.mark.django_db
class TestEokulDosyasi:
    """Uçtan uca: e-Okul'un DEĞİŞTİRİLMEMİŞ .xls raporu doğrudan yüklenir.

    Fixture'lar sentetiktir (`tests/veri/uret_eokul_ornekleri.py`) — yerleşim
    gerçek raporlarla aynı, adlar uydurmadır (KVKK).
    """

    def test_sinif_listesi_dosyasi_aktarilir(self, aktif_yil: SchoolYear) -> None:
        rapor = import_service.commit_students_file(
            file_bytes=EOKUL_SINIF_LISTESI.read_bytes(), file_name="OOG01001R020_827.XLS"
        )
        assert rapor.created_students == 6
        assert rapor.skipped == []
        assert Student.objects.count() == 6
        assert any("şube bloğu" in u.issue for u in rapor.warnings)

    def test_i_ve_noktali_i_subeleri_ayri_kaydedilir(self, aktif_yil: SchoolYear) -> None:
        """KORUMA TESTİ: iki ayrı şube tek şubeye çökmez (öğrenciler karışmaz)."""
        import_service.commit_students_file(
            file_bytes=EOKUL_SINIF_LISTESI.read_bytes(), file_name="OOG01001R020_827.XLS"
        )
        assert set(Student.objects.values_list("class_section", flat=True)) == {"I", "İ"}
        assert Student.objects.filter(class_level=10, class_section="I").count() == 3
        assert Student.objects.filter(class_level=10, class_section="İ").count() == 3
        assert ClassSection.objects.filter(school_year=aktif_yil).count() == 2

    def test_onizleme_yazmaz(self, aktif_yil: SchoolYear) -> None:
        rapor = import_service.preview_students_file(
            file_bytes=EOKUL_SINIF_LISTESI.read_bytes(), file_name="OOG01001R020_827.XLS"
        )
        assert rapor.dry_run is True and rapor.created_students == 6
        assert Student.objects.count() == 0

    def test_personel_listesi_dosyasi_aktarilir(self) -> None:
        rapor = import_service.commit_personnel_file(
            file_bytes=EOKUL_PERSONEL_LISTESI.read_bytes(), file_name="OOK01001R1_826.XLS"
        )
        assert rapor.created_personnel == 4
        assert Personnel.objects.count() == 4
        # Sayaç dipnotu ('Toplam Personel Sayısı: 4') personel olarak yazılmadı.
        assert not any("Sayısı" in p.full_name for p in Personnel.objects.all())

    def test_ayni_dosya_ikinci_kez_uyarir(self, aktif_yil: SchoolYear) -> None:
        veri = EOKUL_SINIF_LISTESI.read_bytes()
        import_service.commit_students_file(file_bytes=veri, file_name="OOG01001R020_827.XLS")
        tekrar = import_service.commit_students_file(
            file_bytes=veri, file_name="OOG01001R020_827.XLS"
        )
        assert tekrar.already_imported is True
        assert tekrar.unchanged_students == 6
        assert Student.objects.count() == 6


@pytest.mark.django_db
class TestImportApi:
    def test_onizleme_ve_aktarma_uclari(self, aktif_yil: SchoolYear) -> None:
        from rest_framework.test import APIClient

        client = APIClient()
        metin = _metin("10/A\t101\tEMRE CAN YILMAZ")
        on = client.post("/api/v1/imports/students/preview/", {"text": metin}, format="multipart")
        assert on.status_code == 200 and on.json()["dry_run"] is True
        assert Student.objects.count() == 0

        yanit = client.post("/api/v1/imports/students/commit/", {"text": metin}, format="multipart")
        assert yanit.status_code == 200
        assert Student.objects.count() == 1

    def test_dosya_ve_metin_ayni_anda_reddedilir(self) -> None:
        from rest_framework.test import APIClient

        yanit = APIClient().post("/api/v1/imports/students/preview/", {}, format="multipart")
        assert yanit.status_code == 400
        assert yanit.json()["code"] == "validation_error"
