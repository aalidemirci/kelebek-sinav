"""Ders havuzu — parser, tohum, seviye süzgeci, sınav biçimi, takma adlar, API."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.dersler import selectors, services, text
from apps.dersler.catalog_parser import parse_alias_table, parse_markdown_catalog
from apps.dersler.models import Course, CourseAlias, CourseExamMode, CourseSource, CourseType
from apps.okul.models import Student

# ÜÇ SÜTUNLU çizelge — 'Sınav' sütunu isteğe bağlı olduğu için bu sabit BİLEREK
# eski biçimde bırakıldı: onu tüketen yedi test, geriye dönük uyumun canlı
# kanıtıdır (`cerceveler/*.md` dosyaları da üç sütunludur).
KATALOG_MD = """
# Örnek çizelge

| Ders | Seviyeler | Tür |
|---|---|---|
| Türk Dili ve Edebiyatı | 9-12 | ORTAK |
| Coğrafya | 9, 10 | ORTAK |
| Seçmeli Coğrafya | 11-12 | SECMELI |
| Girişimcilik | 11 | SECMELI |
"""

# DÖRT SÜTUNLU çizelge — son satırın 'Sınav' hücresi bilerek boş (boş hücre
# 'belirtilmemiş' demektir, YAZILI'ya düşer).
KATALOG_SINAV_MD = """
| Ders | Seviyeler | Tür | Sınav |
|---|---|---|---|
| Matematik | 9-12 | ORTAK | YAZILI |
| Beden Eğitimi ve Spor | 9-11 | ORTAK | UYGULAMA |
| Rehberlik ve Yönlendirme | 9-12 | ORTAK | YOK |
| Girişimcilik | 11 | SECMELI |  |
"""

ALIAS_MD = """
| Takma ad | Kanonik ad |
|---|---|
| T.D.E. | Türk Dili ve Edebiyatı |
| Coğ. | Coğrafya |
"""


class TestParser:
    def test_katalog_tablosu_cozulur(self) -> None:
        parsed = parse_markdown_catalog(KATALOG_MD)
        assert not parsed.errors
        assert len(parsed.rows) == 4
        tde = parsed.rows[0]
        assert tde.name == "Türk Dili ve Edebiyatı"
        assert tde.levels == (9, 10, 11, 12)
        assert tde.course_type == CourseType.COMMON

    def test_hatali_satir_sonucu_durdurmaz(self) -> None:
        parsed = parse_markdown_catalog("| Ders | Seviyeler | Tür |\n| X | bozuk | ORTAK |")
        assert parsed.errors and not parsed.rows

    def test_sinav_sutunu_okunur(self) -> None:
        parsed = parse_markdown_catalog(KATALOG_SINAV_MD)
        assert not parsed.errors
        bicimler = {row.name: row.exam_mode for row in parsed.rows}
        assert bicimler == {
            "Matematik": CourseExamMode.WRITTEN,
            "Beden Eğitimi ve Spor": CourseExamMode.PRACTICE,
            "Rehberlik ve Yönlendirme": CourseExamMode.NONE,
            "Girişimcilik": CourseExamMode.WRITTEN,  # boş hücre → yazılı
        }

    def test_sinav_sutunu_yoksa_yazili_varsayilir(self) -> None:
        # Üç sütunlu dosyalar (cerceveler/*.md) bozulmadan okunmalı.
        parsed = parse_markdown_catalog(KATALOG_MD)
        assert not parsed.errors
        assert {row.exam_mode for row in parsed.rows} == {CourseExamMode.WRITTEN}

    def test_bilinmeyen_sinav_etiketi_satiri_dusurur(self) -> None:
        # Yazım hatası sessizce YAZILI sayılsaydı havuz farkedilmeden şişerdi.
        parsed = parse_markdown_catalog(
            "| Ders | Seviyeler | Tür | Sınav |\n| X | 9 | ORTAK | SÖZLÜ |"
        )
        assert parsed.errors and not parsed.rows

    def test_gercek_cizelge_dosyasi_cozulur(self) -> None:
        """Depodaki gerçek çizelge hatasız okunmalı ve altı satırı işaretlemeli."""
        dosya = Path(settings.CATALOG_DIR) / "anadolu-lisesi-2025-2026.md"
        if not dosya.is_file():  # paketlenmiş/ayrık ortamda veri dizini yok
            pytest.skip("çizelge dosyası bu ortamda yok")
        parsed = parse_markdown_catalog(dosya.read_text(encoding="utf-8"), source_name=dosya.name)
        assert not parsed.errors
        assert {r.name for r in parsed.rows if r.exam_mode == CourseExamMode.PRACTICE} == {
            "Beden Eğitimi ve Spor",
            "Görsel Sanatlar/Müzik",
            "Beden Eğitimi ve Spor/Görsel Sanatlar/Müzik",
            "Spor Eğitimi",
            "Sanat Eğitimi",
        }
        # "Yabancı Dil" de YOK: katalogda yalnız e-Okul program doğrulaması için
        # durur, "Birinci Yabancı Dil"in takma adıdır — YAZILI kalsaydı havuz
        # her seviyede kopya satır alırdı (31.08.2026 denetimi).
        assert {r.name for r in parsed.rows if r.exam_mode == CourseExamMode.NONE} == {
            "Rehberlik ve Yönlendirme",
            "Yabancı Dil",
        }

    def test_alias_tablosu_cozulur(self) -> None:
        parsed = parse_alias_table(ALIAS_MD)
        assert parsed.rows == [
            ("T.D.E.", "Türk Dili ve Edebiyatı"),
            ("Coğ.", "Coğrafya"),
        ]


class TestTextHelpers:
    def test_match_key_tr_ve_sapka(self) -> None:
        assert text.course_match_key("MATEMATİK") == text.course_match_key("Matematik")
        assert text.course_match_key("AHLÂK") == text.course_match_key("Ahlak")

    def test_canon_key_secmeli_oneki_atar(self) -> None:
        assert text.canon_course_key("SEÇMELİ Girişimcilik") == text.canon_course_key(
            "Girişimcilik"
        )

    def test_titlecase_tr(self) -> None:
        assert text.titlecase_tr("SEÇMELİ SANAT EĞİTİMİ") == "Seçmeli Sanat Eğitimi"
        assert text.titlecase_tr("TÜRK DİLİ VE EDEBİYATI") == "Türk Dili ve Edebiyatı"


@pytest.mark.django_db
class TestSeed:
    def _tohumla(self, tmp_path: Path) -> None:
        (tmp_path / "katalog.md").write_text(KATALOG_MD, encoding="utf-8")
        services.ensure_meb_catalog(path=str(tmp_path))

    def test_tohum_idempotent(self, tmp_path: Path) -> None:
        self._tohumla(tmp_path)
        assert Course.objects.count() == 4
        # İkinci çağrı hiçbir şey eklemez (katalog zaten var → hızlı dönüş).
        services.ensure_meb_catalog(path=str(tmp_path))
        assert Course.objects.count() == 4

    def test_dosya_yoksa_sessizce_atlanir(self, tmp_path: Path) -> None:
        sonuc = services.ensure_meb_catalog(path=str(tmp_path / "yok"))
        assert sonuc.created == 0

    def test_pasiflestirilen_ders_importla_geri_acilmaz(self, tmp_path: Path) -> None:
        self._tohumla(tmp_path)
        ders = Course.objects.get(name="Girişimcilik")
        services.update_course(ders, is_active=False)
        # Yeniden import (katalog mevcut → ensure atlar; import_course_rows doğrudan)
        parsed = parse_markdown_catalog(KATALOG_MD)
        services.import_course_rows(parsed.rows)
        ders.refresh_from_db()
        assert ders.is_active is False

    def test_elle_girilen_ayni_ad_meb_kaydina_donusur(self, tmp_path: Path) -> None:
        services.create_course(name="Coğrafya", levels=[9])
        self._tohumla(tmp_path)
        ders = Course.objects.get(name="Coğrafya")
        assert ders.source == CourseSource.MEB_CATALOG
        assert ders.levels == [9, 10]

    def test_import_sinav_bicimini_yazar(self, tmp_path: Path) -> None:
        (tmp_path / "katalog.md").write_text(KATALOG_SINAV_MD, encoding="utf-8")
        services.ensure_meb_catalog(path=str(tmp_path))
        assert Course.objects.get(name="Beden Eğitimi ve Spor").exam_mode == (
            CourseExamMode.PRACTICE
        )
        assert Course.objects.get(name="Rehberlik ve Yönlendirme").exam_mode == CourseExamMode.NONE
        assert Course.objects.get(name="Matematik").exam_mode == CourseExamMode.WRITTEN

    def test_import_sinav_bicimi_farkini_duzeltir(self) -> None:
        # `is_active`in aksine `exam_mode` çizelge verisidir: MEB kaynağı kazanır,
        # aksi hâlde satır 'unchanged' sayılır ve fark hiç düzelmezdi.
        services.create_course(name="Beden Eğitimi ve Spor", levels=[9, 10, 11])
        parsed = parse_markdown_catalog(KATALOG_SINAV_MD)
        sonuc = services.import_course_rows(parsed.rows)
        assert sonuc.updated >= 1
        ders = Course.objects.get(name="Beden Eğitimi ve Spor")
        assert ders.exam_mode == CourseExamMode.PRACTICE
        # Aynı satırların ikinci koşusu artık fark görmez.
        assert services.import_course_rows(parsed.rows).unchanged == len(parsed.rows)

    def test_alias_tohumlari_satir_bazli(self, tmp_path: Path) -> None:
        self._tohumla(tmp_path)
        alias_file = tmp_path / "alias.md"
        alias_file.write_text(ALIAS_MD, encoding="utf-8")
        assert services.ensure_course_aliases(path=str(alias_file)) == 2
        # İkinci koşu yeni satır yazmaz (satır-bazlı idempotans).
        assert services.ensure_course_aliases(path=str(alias_file)) == 0
        # Kanonik adı katalogda olmayan satır sessizce atlanır.
        alias_file.write_text(ALIAS_MD + "| X | Olmayan Ders |\n", encoding="utf-8")
        assert services.ensure_course_aliases(path=str(alias_file)) == 0


@pytest.mark.django_db
class TestLevelsAndSearch:
    def test_seviye_suzgeci_python_tarafinda(self) -> None:
        services.create_course(name="Coğrafya", levels=[9, 10])
        services.create_course(name="Felsefe", levels=[11])
        adlar = [c.name for c in selectors.courses_for_level(9)]
        assert adlar == ["Coğrafya"]

    def test_gecersiz_seviye_reddedilir(self) -> None:
        with pytest.raises(ValidationError, match="Geçersiz seviye"):
            services.create_course(name="X", levels=[8])
        with pytest.raises(ValidationError, match="boş olamaz"):
            services.create_course(name="X", levels=[])

    def test_tr_katlamali_arama(self) -> None:
        services.create_course(name="MATEMATİK", levels=[9])
        bulunan = selectors.search_courses(selectors.courses(), "matematik")
        assert [c.name for c in bulunan] == ["MATEMATİK"]

    def test_ayni_ad_canli_kayitta_reddedilir(self) -> None:
        services.create_course(name="Coğrafya", levels=[9])
        with pytest.raises(ValidationError, match="zaten havuzda"):
            services.create_course(name="  Coğrafya ", levels=[10])

    def test_katalog_listesi_tr_alfabesi_sirali(self) -> None:
        services.create_course(name="Zooloji", levels=[9])
        services.create_course(name="Çağdaş Türk ve Dünya Tarihi", levels=[9])
        services.create_course(name="Coğrafya", levels=[9])
        assert [c.name for c in selectors.courses_sorted()] == [
            "Coğrafya",
            "Çağdaş Türk ve Dünya Tarihi",
            "Zooloji",
        ]
        # DB sıralaması SQLite'ta BINARY'dir — 'Ç' kod noktası olarak 'Z'den
        # sonradır, yani ham `courses()` aynı listeyi sona kaydırarak verir.
        assert [c.name for c in selectors.courses()][-1] == "Çağdaş Türk ve Dünya Tarihi"


@pytest.mark.django_db
class TestTaughtCourseLevels:
    """Havuz doldurma kaynağı — tür/sınav biçimi süzgeçleri ve TR sıralama."""

    def _kur(self) -> None:
        for seviye, no in ((9, "901"), (10, "1001")):
            Student.objects.create(
                first_name="AD",
                last_name="SOYAD",
                student_number=no,
                class_level=seviye,
                class_section="A",
            )
        services.create_course(name="Matematik", levels=[9, 10])
        services.create_course(
            name="Beden Eğitimi ve Spor", levels=[9], exam_mode=CourseExamMode.PRACTICE
        )
        services.create_course(
            name="Rehberlik ve Yönlendirme", levels=[9], exam_mode=CourseExamMode.NONE
        )
        services.create_course(
            name="Çağdaş Türk ve Dünya Tarihi", levels=[9], course_type=CourseType.ELECTIVE
        )

    def test_suzgecsiz_cagri_geriye_donuk_uyumlu(self) -> None:
        self._kur()
        # `school_year_id` KONUMSAL argüman olarak durmaya devam eder (OYS imzası).
        ciftler = selectors.taught_course_levels(7)
        assert [(p.course_name, p.level) for p in ciftler] == [
            ("Beden Eğitimi ve Spor", 9),
            ("Çağdaş Türk ve Dünya Tarihi", 9),
            ("Matematik", 9),
            ("Matematik", 10),
            ("Rehberlik ve Yönlendirme", 9),
        ]

    def test_zorunlu_yazili_suzgeci(self) -> None:
        self._kur()
        ciftler = selectors.taught_course_levels(
            course_types=[CourseType.COMMON], exam_modes=[CourseExamMode.WRITTEN]
        )
        assert [(p.course_name, p.level) for p in ciftler] == [
            ("Matematik", 9),
            ("Matematik", 10),
        ]

    def test_secmeli_yazili_suzgeci(self) -> None:
        self._kur()
        ciftler = selectors.taught_course_levels(
            course_types=[CourseType.ELECTIVE], exam_modes=[CourseExamMode.WRITTEN]
        )
        assert [(p.course_name, p.level) for p in ciftler] == [("Çağdaş Türk ve Dünya Tarihi", 9)]

    def test_tr_alfabesi_sirasi(self) -> None:
        # 'Çağdaş' DB sıralamasında (BINARY) 'Rehberlik'ten sonraya düşerdi.
        self._kur()
        adlar = [p.course_name for p in selectors.taught_course_levels()]
        assert adlar.index("Çağdaş Türk ve Dünya Tarihi") < adlar.index("Matematik")

    def test_ogrencisiz_seviye_disarida_kalir(self) -> None:
        self._kur()
        services.create_course(name="Sosyoloji", levels=[11])
        assert all(p.course_name != "Sosyoloji" for p in selectors.taught_course_levels())


@pytest.mark.django_db
class TestAliasRules:
    def _ders(self, name: str = "Coğrafya") -> Course:
        return services.create_course(name=name, levels=[9])

    def test_oz_alias_yazilmaz(self) -> None:
        ders = self._ders()
        assert services.learn_course_alias(name="COĞRAFYA", course=ders) is None

    def test_operator_seed_i_ezer_tersi_olmaz(self) -> None:
        cog = self._ders()
        fel = self._ders("Felsefe")
        services.learn_course_alias(name="KISALTMA", course=cog, source=CourseAlias.Source.SEED)
        # SEED mevcut kaydı ezmez.
        assert (
            services.learn_course_alias(name="KISALTMA", course=fel, source=CourseAlias.Source.SEED)
            is None
        )
        # OPERATOR ezer.
        alias = services.learn_course_alias(name="KISALTMA", course=fel)
        assert alias is not None and alias.course_id == fel.pk

    def test_alias_pasif_derse_none_doner(self) -> None:
        ders = self._ders()
        services.learn_course_alias(name="KISALTMA", course=ders)
        services.update_course(ders, is_active=False)
        assert selectors.course_by_alias("KISALTMA") is None


@pytest.mark.django_db
class TestDuplicatesAndMerge:
    def test_mukerrer_tespiti_ve_oneri(self) -> None:
        onekli = services.create_course(
            name="Seçmeli Girişimcilik", levels=[11], course_type=CourseType.ELECTIVE
        )
        oneksiz = services.create_course(
            name="Girişimcilik", levels=[11], course_type=CourseType.ELECTIVE
        )
        adaylar = selectors.duplicate_course_candidates()
        assert len(adaylar) == 1
        assert adaylar[0]["suggested_canonical_id"] == oneksiz.pk
        assert {c["id"] for c in adaylar[0]["courses"]} == {onekli.pk, oneksiz.pk}

    def test_resmi_secmeli_meb_dersi_mukerrer_sayilmaz(self, tmp_path: Path) -> None:
        (tmp_path / "k.md").write_text(KATALOG_MD, encoding="utf-8")
        services.ensure_meb_catalog(path=str(tmp_path))
        # 'Coğrafya' (ORTAK) ile 'Seçmeli Coğrafya' (MEB SECMELI) çakışmaz (Tur 661 istisnası).
        assert selectors.duplicate_course_candidates() == []

    def test_birlestirme_referans_tasir_ve_alias_ogrenir(self) -> None:
        kopya = services.create_course(name="Seçmeli Matematik", levels=[11])
        kanonik = services.create_course(name="Matematik", levels=[9, 10])
        sonuc = services.consolidate_duplicate_course(duplicate=kopya, canonical=kanonik)
        assert sonuc["exams"] == 0  # sınav modülü F3'te — yokluğa dayanıklı
        kanonik.refresh_from_db()
        assert kanonik.levels == [9, 10, 11]  # seviye birleşimi
        assert Course.objects.filter(pk=kopya.pk).count() == 0  # soft-delete
        assert selectors.course_by_alias("SEÇMELİ MATEMATİK") == kanonik


@pytest.mark.django_db
class TestCourseApi:
    def test_liste_tembel_tohumu_kosar(self, tmp_path: Path) -> None:
        # settings.CATALOG_DIR gerçek depo verisine bakar (compose env) — testte
        # izole dizine yönlendirilir.
        from django.test import override_settings

        (tmp_path / "k.md").write_text(KATALOG_MD, encoding="utf-8")
        with override_settings(CATALOG_DIR=tmp_path, COURSE_ALIAS_FILE=tmp_path / "alias-yok.md"):
            yanit = APIClient().get("/api/v1/courses/")
        assert yanit.status_code == 200
        assert len(yanit.json()) == 4

    def test_elle_ekle_ve_pasiflestir(self) -> None:
        client = APIClient()
        yanit = client.post(
            "/api/v1/courses/",
            {"name": "Astronomi Kulübü Dersi", "levels": [11], "course_type": "ELECTIVE"},
            format="json",
        )
        assert yanit.status_code == 201
        ders_id = yanit.json()["id"]
        assert yanit.json()["source"] == "MANUAL"

        yanit = client.patch(f"/api/v1/courses/{ders_id}/", {"is_active": False}, format="json")
        assert yanit.status_code == 200 and yanit.json()["is_active"] is False

    def test_delete_ucu_bilinclie_yok(self) -> None:
        ders = services.create_course(name="X Dersi", levels=[9])
        yanit = APIClient().delete(f"/api/v1/courses/{ders.pk}/")
        assert yanit.status_code == 405

    def test_sinav_bicimi_alani_yazilir_ve_etiketlenir(self) -> None:
        client = APIClient()
        yanit = client.post(
            "/api/v1/courses/",
            {
                "name": "Beden Eğitimi ve Spor",
                "levels": [9],
                "course_type": "COMMON",
                "exam_mode": "PRACTICE",
            },
            format="json",
        )
        assert yanit.status_code == 201
        assert yanit.json()["exam_mode"] == "PRACTICE"
        assert yanit.json()["exam_mode_label"] == "Uygulama"

        ders_id = yanit.json()["id"]
        yanit = client.patch(f"/api/v1/courses/{ders_id}/", {"exam_mode": "WRITTEN"}, format="json")
        assert yanit.status_code == 200
        assert yanit.json()["exam_mode_label"] == "Yazılı"

    def test_varsayilan_sinav_bicimi_yazili(self) -> None:
        yanit = APIClient().post(
            "/api/v1/courses/", {"name": "Sosyoloji", "levels": [11]}, format="json"
        )
        assert yanit.status_code == 201 and yanit.json()["exam_mode"] == "WRITTEN"

    def test_post_govdesinde_is_active_500_vermez(self) -> None:
        # View `validated_data`'nın tamamını servise açar; serializer'da olup
        # `create_course` imzasında olmayan alan TypeError → 500 verirdi.
        yanit = APIClient().post(
            "/api/v1/courses/",
            {"name": "Pasif Ders", "levels": [9], "is_active": False},
            format="json",
        )
        assert yanit.status_code == 201 and yanit.json()["is_active"] is False

    def test_seviye_suzgeci_api(self) -> None:
        services.create_course(name="Coğrafya", levels=[9, 10])
        services.create_course(name="Felsefe", levels=[11])
        from django.test import override_settings

        with override_settings(CATALOG_DIR="/olmayan", COURSE_ALIAS_FILE="/olmayan/a.md"):
            yanit = APIClient().get("/api/v1/courses/?level=9")
        assert [c["name"] for c in yanit.json()] == ["Coğrafya"]


class TestGocSiniflandirmasi:
    """0003 veri göçünün ada göre sınıflandırıcısı (DB gerekmez — saf fonksiyon).

    Göç dosyası DONDURULMUŞTUR: normalize tablosunu `apps.dersler.text`'ten
    import etmek yerine inline kopyalar. Bu test o kopyanın davranışını
    sabitler; göçün kendisi `manage.py migrate` ile zaten koşuyor.
    """

    def _goc(self) -> ModuleType:
        return importlib.import_module("apps.dersler.migrations.0003_course_exam_mode_data")

    def test_uygulama_dersleri_isaretlenir(self) -> None:
        goc = self._goc()
        for ad in (
            "Beden Eğitimi ve Spor",
            "Görsel Sanatlar/Müzik",
            "Beden Eğitimi ve Spor/Görsel Sanatlar/Müzik",
            "Görsel Sanatlar",
            "Müzik",
            "Spor Eğitimi",
            "Sanat Eğitimi",
        ):
            assert goc._sinav_bicimi(ad) == CourseExamMode.PRACTICE, ad

    def test_eokul_yazimi_ve_secmeli_oneki_yakalanir(self) -> None:
        # e-Okul 'SEÇMELİ SPOR EĞİTİMİ' yazar (ders-adi-takma-adlari.md); operatörün
        # elle açtığı kayıt bu adı taşıyabilir — öneksiz anahtar onu kaçırırdı.
        goc = self._goc()
        assert goc._sinav_bicimi("SEÇMELİ SPOR EĞİTİMİ") == CourseExamMode.PRACTICE
        assert goc._sinav_bicimi("BEDEN EĞİTİMİ VE SPOR") == CourseExamMode.PRACTICE

    def test_havuza_girmeyen_dersler_sinavsiz_isaretlenir(self) -> None:
        goc = self._goc()
        assert goc._sinav_bicimi("Rehberlik ve Yönlendirme") == CourseExamMode.NONE
        # Genel "Yabancı Dil" = "Birinci Yabancı Dil"in e-Okul yazımı; kurulu
        # veritabanlarında da havuza kopya satır basmamalı.
        assert goc._sinav_bicimi("YABANCI DİL") == CourseExamMode.NONE
        # Ayrı dersler etkilenmez.
        assert goc._sinav_bicimi("Birinci Yabancı Dil") is None
        assert goc._sinav_bicimi("İkinci Yabancı Dil") is None

    def test_diger_derslere_dokunulmaz(self) -> None:
        # None = "sınıflanamadı"; göç o kaydı hiç yazmaz, WRITTEN varsayılanında kalır.
        goc = self._goc()
        assert goc._sinav_bicimi("Matematik") is None
        assert goc._sinav_bicimi("Türk Kültür ve Medeniyet Tarihi") is None
