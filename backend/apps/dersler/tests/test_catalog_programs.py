"""Okul türü çizelgeleri (tasarım §7.2): program dosyaları, yürürlük kuralı, senkron, API.

Gerçek veri dosyaları (`data/ders-cizelgeleri/*.md`) her testte yeniden
ayrıştırılır: kürasyon hatası (bilinmeyen tür/sınav etiketi, ters aralık)
kapıda yakalanır. Sentetik dosyalar `tmp_path` altında yazılır; DB testleri
okul yapılandırmasını `SchoolConfig` üzerinden değiştirir. Kişisel veri yok.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from django.conf import settings
from django.test import override_settings
from rest_framework.test import APIClient

from apps.dersler import catalog, services
from apps.dersler.catalog_parser import parse_program_meta
from apps.dersler.models import Course, CourseExamMode, CourseSource, CourseType
from apps.okul.models import SchoolConfig, SchoolType
from apps.okul.services import setup as setup_service

GERCEK_DIZIN = Path(settings.CATALOG_DIR)

# Kademesiz iki tür + bir kademeli tür — yürürlük kuralının üç kalıbı.
AL_MD = """
- program_key: al-test
- ad: AL test
- okul_turu: ANADOLU_LISESI, COK_PROGRAMLI_ANADOLU_LISESI
- hazirlik: hayır
- yururluk: 2025-2026
- kademeli: hayır

| Ders | Seviyeler | Tür | Sınav |
|---|---|---|---|
| Türk Dili ve Edebiyatı | 9-12 | ORTAK | YAZILI |
| Coğrafya | 9, 10 | ORTAK | YAZILI |
| Seçmeli Matematik | 11, 12 | SECMELI | YAZILI |
| Bilişim Teknolojileri ve Yazılım | 9-12 | SECMELI | YAZILI |
| Rehberlik ve Yönlendirme | 9-12 | ORTAK | YOK |
"""

AL_HAZ_MD = """
- program_key: al-haz-test
- ad: AL hazırlık test
- okul_turu: ANADOLU_LISESI
- hazirlik: evet
- yururluk: 2025-2026

| Ders | Seviyeler | Tür | Sınav |
|---|---|---|---|
| Hazırlık Sınıfı Türk Dili ve Edebiyatı | 0 | ORTAK | YAZILI |
| Türk Dili ve Edebiyatı | 9-12 | ORTAK | YAZILI |
| Coğrafya | 9, 10 | ORTAK | YAZILI |
| Bilişim Teknolojileri ve Yazılım | 0, 9-12 | SECMELI | YAZILI |
"""

SBL_MD = """
- program_key: sbl-test
- ad: SBL test
- okul_turu: SOSYAL_BILIMLER_LISESI
- yururluk: 2025-2026

| Ders | Seviyeler | Tür | Sınav |
|---|---|---|---|
| Türk Dili ve Edebiyatı | 9-12 | ORTAK | YAZILI |
| Sanat Tarihi | 12 | ORTAK | YAZILI |
| Coğrafya | 9-12 | ORTAK | YAZILI |
"""

SPOR_MD = """
- program_key: spor-test
- ad: Spor test
- okul_turu: SPOR_LISESI
- yururluk: 2025-2026
- kademeli: evet
- kademeli_ilk_seviyeler: 0, 9, 10
- secmeli_kademeli: hayır

| Ders | Seviyeler | Tür | Sınav |
|---|---|---|---|
| Türk Dili ve Edebiyatı | 9-12 | ORTAK | YAZILI |
| Takım Sporları | 9-12 | ORTAK | UYGULAMA |
| Seçmeli Coğrafya | 11, 12 | SECMELI | YAZILI |
"""

SPOR_ESKI_MD = """
- program_key: spor-eski-test
- ad: Spor eski test
- okul_turu: SPOR_LISESI
- yururluk: 2023-2024
- kademeli: hayır

| Ders | Seviyeler | Tür | Sınav |
|---|---|---|---|
| Türk Dili ve Edebiyatı | 9-12 | ORTAK | YAZILI |
| Eski Alan Dersi | 12 | ORTAK | YAZILI |
"""


def _dizin(tmp_path: Path, **dosyalar: str) -> Path:
    for ad, icerik in dosyalar.items():
        (tmp_path / f"{ad}.md").write_text(icerik, encoding="utf-8")
    return tmp_path


def _plan(
    school_type: str,
    *,
    has_prep: bool = False,
    year: int = 2026,
    overrides: dict[str, list[str]] | None = None,
    root: Path = GERCEK_DIZIN,
) -> catalog.CatalogPlan:
    levels = (0, 9, 10, 11, 12) if has_prep else (9, 10, 11, 12)
    return catalog.resolve_plan(
        school_type=school_type,
        has_prep=has_prep,
        levels=levels,
        year=year,
        overrides=overrides,
        root=root,
    )


class TestGercekDosyalar:
    """Depodaki program dosyaları — kürasyon kapısı."""

    @pytest.fixture(autouse=True)
    def _dizin_var(self) -> None:
        if not GERCEK_DIZIN.is_dir():
            pytest.skip("çizelge dizini bu ortamda yok")

    def test_her_program_hatasiz_ayrisir(self) -> None:
        programs = catalog.load_programs(GERCEK_DIZIN)
        assert len(programs) >= 15
        for program in programs.values():
            assert not program.errors, program.errors
            assert program.school_types, program.key
            assert program.start_year is not None, program.key
            assert program.source, program.key
            assert program.rows, program.key
            # Her program dosyası adıyla anahtarlanır (SchoolConfig.level_programs sözleşmesi).
            assert program.path.stem == program.key

    def test_her_okul_turunun_verisi_var(self) -> None:
        options = catalog.school_type_options(catalog.load_programs(GERCEK_DIZIN))
        assert {o["value"] for o in options} == {str(t) for t in SchoolType}
        assert all(o["available"] for o in options), options

    def test_anadolu_lisesi_hazirliksiz_sifir_seviyesi_icermez(self) -> None:
        """Kullanıcı bulgusu (03.09.2026): hazırlıksız okulda 'Hazırlık' etiketi görünüyordu."""
        rows = _plan(SchoolType.ANADOLU_LISESI).rows()
        assert rows and all(0 not in r.levels for r in rows)
        adlar = {r.name for r in rows}
        assert "Hazırlık Sınıfı Türk Dili ve Edebiyatı" not in adlar
        assert "İkinci Yabancı Dil" not in adlar
        beden = next(r for r in rows if r.name == "Beden Eğitimi ve Spor")
        assert beden.levels == (9, 10, 11)
        # Kararın açıklamaları: HTDE notla değerlendirilmez.
        htde = next(r for r in rows if r.name == "Hedef Temelli Destek Eğitimi")
        assert htde.exam_mode == CourseExamMode.NONE

    def test_hazirlikli_anadolu_lisesi_hazirlik_varyantini_secer(self) -> None:
        plan = _plan(SchoolType.ANADOLU_LISESI, has_prep=True)
        assert plan.plans[0].program_keys == ("anadolu-lisesi-hazirlik-2025",)
        assert any(r.name == "Hazırlık Sınıfı Türk Dili ve Edebiyatı" for r in plan.rows())

    def test_fen_ve_sbl_farklari(self) -> None:
        fen = {r.name: r for r in _plan(SchoolType.FEN_LISESI).rows()}
        assert fen["Matematik"].levels == (9, 10, 11, 12)
        assert "Seçmeli Matematik" not in fen and "Genetik Bilimine Giriş" in fen
        sbl = {r.name: r for r in _plan(SchoolType.SOSYAL_BILIMLER_LISESI).rows()}
        assert sbl["Sanat Tarihi"].course_type == CourseType.COMMON
        assert sbl["Sanat Tarihi"].levels == (12,)
        assert sbl["Coğrafya"].levels == (9, 10, 11, 12)

    def test_spor_lisesi_2026_12_sinif_uyarisi_2027_de_kalkar(self) -> None:
        """Ortak dersler hazırlık-9-10'dan kademeli (TTK 2025/9): 2026-27'de 12 kapsanmaz."""
        uyarili = _plan(SchoolType.SPOR_LISESI, year=2026)
        assert any("12. sınıf ortak" in w for w in uyarili.warnings)
        assert not _plan(SchoolType.SPOR_LISESI, year=2027).warnings

    def test_cok_programli_al_uc_cizelgeyi_birlestirir(self) -> None:
        plan = _plan(SchoolType.COK_PROGRAMLI_ANADOLU_LISESI)
        assert set(plan.plans[9].program_keys) == {
            "anadolu-lisesi-2025",
            "anadolu-imam-hatip-lisesi-2025",
            "mesleki-ve-teknik-anadolu-lisesi-2023",
        }
        # Varsayılan dışı program (B grubu) kendiliğinden girmez.
        assert "anadolu-imam-hatip-lisesi-program-proje-2025" not in plan.plans[9].program_keys


class TestMetaVeYururluk:
    def test_meta_blogu_tablo_baslayinca_biter(self) -> None:
        meta = parse_program_meta("- program_key: x\n- ad: Y\n| Ders |\n- kaynak: sonra")
        assert meta == {"program_key": "x", "ad": "Y"}

    def test_kademesiz_program_tum_seviyeleri_kapsar(self, tmp_path: Path) -> None:
        programs = catalog.load_programs(_dizin(tmp_path, al=AL_MD))
        p = programs["al-test"]
        assert p.covers(12, 2025, course_type=CourseType.COMMON)
        assert not p.covers(9, 2024, course_type=CourseType.COMMON)  # yürürlük öncesi

    def test_kademeli_program_kohortla_ilerler(self, tmp_path: Path) -> None:
        p = catalog.load_programs(_dizin(tmp_path, spor=SPOR_MD))["spor-test"]
        # 2025-26: hazırlık, 9, 10 · 2026-27: +11 · 2027-28: +12
        assert p.covers(10, 2025, course_type=CourseType.COMMON)
        assert not p.covers(11, 2025, course_type=CourseType.COMMON)
        assert p.covers(11, 2026, course_type=CourseType.COMMON)
        assert not p.covers(12, 2026, course_type=CourseType.COMMON)
        assert p.covers(12, 2027, course_type=CourseType.COMMON)
        # Seçmeliler hemen ("diğer bileşenleri tüm sınıf seviyelerinde").
        assert p.covers(12, 2025, course_type=CourseType.ELECTIVE)

    def test_eski_nesil_kapsanmayan_seviyeye_girer_yenisi_kazanir(self, tmp_path: Path) -> None:
        programs = catalog.load_programs(_dizin(tmp_path, spor=SPOR_MD, eski=SPOR_ESKI_MD))
        plans = catalog.default_assignment(
            programs,
            school_type=SchoolType.SPOR_LISESI,
            has_prep=False,
            levels=(9, 10, 11, 12),
            year=2026,
        )
        assert plans[9].common_from == ("spor-test",)
        assert plans[12].common_from == ("spor-eski-test",)  # 12 henüz eski çizelgede
        assert plans[12].elective_from == ("spor-test",)  # seçmeli hemen yeni
        assert not plans[12].warnings
        rows = {r.name: r for r in catalog.effective_rows(plans, programs)}
        assert rows["Eski Alan Dersi"].levels == (12,)
        assert rows["Takım Sporları"].levels == (9, 10, 11)

    def test_kapsanmayan_seviye_yedekle_uyarir(self, tmp_path: Path) -> None:
        programs = catalog.load_programs(_dizin(tmp_path, spor=SPOR_MD))
        plans = catalog.default_assignment(
            programs,
            school_type=SchoolType.SPOR_LISESI,
            has_prep=False,
            levels=(9, 10, 11, 12),
            year=2026,
        )
        assert plans[12].common_from == ("spor-test",)
        assert plans[12].warnings and "12. sınıf" in plans[12].warnings[0]

    def test_hazirlik_varyanti_okul_bayragina_gore_secilir(self, tmp_path: Path) -> None:
        programs = catalog.load_programs(_dizin(tmp_path, al=AL_MD, haz=AL_HAZ_MD))
        hazirliksiz = catalog.default_assignment(
            programs,
            school_type=SchoolType.ANADOLU_LISESI,
            has_prep=False,
            levels=(9, 10, 11, 12),
            year=2026,
        )
        assert hazirliksiz[9].program_keys == ("al-test",)
        hazirlikli = catalog.default_assignment(
            programs,
            school_type=SchoolType.ANADOLU_LISESI,
            has_prep=True,
            levels=(0, 9, 10, 11, 12),
            year=2026,
        )
        assert hazirlikli[0].program_keys == ("al-haz-test",)
        assert hazirlikli[9].program_keys == ("al-haz-test",)

    def test_tek_varyant_iki_okulda_da_kullanilir(self, tmp_path: Path) -> None:
        # AİHL emsali: yalnız hazırlık sütunlu dosya var; hazırlıksız okul da onu kullanır,
        # 0. seviye satırları okul seviye kümesinde olmadığından düşer.
        rows = {
            r.name: r
            for r in _plan(SchoolType.ANADOLU_LISESI, root=_dizin(tmp_path, haz=AL_HAZ_MD)).rows()
        }
        assert "Hazırlık Sınıfı Türk Dili ve Edebiyatı" not in rows
        assert rows["Bilişim Teknolojileri ve Yazılım"].levels == (9, 10, 11, 12)

    def test_kademeli_tur_donusumu_acik_atama(self, tmp_path: Path) -> None:
        """AL → SBL dönüşümünün ilk yılı: 12. sınıf hâlâ AL, 9 SBL (kullanıcı senaryosu)."""
        plan = _plan(
            SchoolType.ANADOLU_LISESI,
            overrides={"9": ["sbl-test"]},
            root=_dizin(tmp_path, al=AL_MD, sbl=SBL_MD),
        )
        assert plan.transitional
        assert plan.plans[9].explicit and plan.plans[9].program_keys == ("sbl-test",)
        assert not plan.plans[10].explicit
        rows = {r.name: r for r in plan.rows()}
        assert rows["Coğrafya"].levels == (9, 10)  # 9 SBL'den, 10 AL'den
        assert "Sanat Tarihi" not in rows  # SBL 12'de, ama 12 AL'de
        assert rows["Seçmeli Matematik"].levels == (11, 12)

    def test_bilinmeyen_program_anahtari_uyari_verir(self, tmp_path: Path) -> None:
        plan = _plan(
            SchoolType.ANADOLU_LISESI,
            overrides={"9": ["yok-boyle-program"]},
            root=_dizin(tmp_path, al=AL_MD),
        )
        assert any("yok-boyle-program" in w for w in plan.warnings)

    def test_tur_catismasinda_secmeli_kazanir(self, tmp_path: Path) -> None:
        ortak = (
            AL_MD.replace(
                "| Bilişim Teknolojileri ve Yazılım | 9-12 | SECMELI | YAZILI |",
                "| Bilişim Teknolojileri ve Yazılım | 9, 10 | ORTAK | UYGULAMA |",
            )
            .replace("program_key: al-test", "program_key: fen-test")
            .replace(
                "okul_turu: ANADOLU_LISESI, COK_PROGRAMLI_ANADOLU_LISESI",
                "okul_turu: FEN_LISESI",
            )
        )
        programs = catalog.load_programs(_dizin(tmp_path, al=AL_MD, fen=ortak))
        plans, _ = catalog.apply_overrides(
            catalog.default_assignment(
                programs,
                school_type=SchoolType.ANADOLU_LISESI,
                has_prep=False,
                levels=(9, 10, 11, 12),
                year=2026,
            ),
            {"9": ["fen-test"]},
            programs,
        )
        rows = {r.name: r for r in catalog.effective_rows(plans, programs)}
        bty = rows["Bilişim Teknolojileri ve Yazılım"]
        assert bty.course_type == CourseType.ELECTIVE
        assert bty.exam_mode == CourseExamMode.PRACTICE  # kısıtlayıcı kazanır
        assert bty.levels == (9, 10, 11, 12)

    def test_damga_girdiyle_degisir(self, tmp_path: Path) -> None:
        programs = catalog.load_programs(_dizin(tmp_path, al=AL_MD))

        def damga(year: int, overrides: dict[str, list[str]] | None) -> str:
            return catalog.compute_stamp(
                year=year,
                school_type=SchoolType.ANADOLU_LISESI,
                has_prep=False,
                levels=(9, 10, 11, 12),
                overrides=overrides,
                programs=programs,
            )

        a = damga(2026, None)
        assert a == damga(2026, {})
        assert a != damga(2027, None)
        assert a != damga(2026, {"9": ["al-test"]})


@pytest.mark.django_db
class TestSenkron:
    """Senkron akışı. Ayar kaydı (`update_school_config`) kataloğu KENDİ tetikler;
    bu yüzden `settings.CATALOG_DIR` sınıf çapında tmp dizine çevrilir — aksi
    hâlde otomatik senkron depodaki gerçek çizelgeleri yüklerdi.
    """

    @pytest.fixture(autouse=True)
    def _katalog_dizini(self, settings: Any, tmp_path: Path) -> None:
        settings.CATALOG_DIR = tmp_path
        settings.COURSE_ALIAS_FILE = tmp_path / "takma-ad-yok.md"

    def _kur(self, tmp_path: Path, **dosyalar: str) -> Path:
        return _dizin(tmp_path, **(dosyalar or {"al": AL_MD, "haz": AL_HAZ_MD, "sbl": SBL_MD}))

    def test_ilk_senkron_ve_damga_idempotansi(self, tmp_path: Path) -> None:
        self._kur(tmp_path)
        sonuc = services.ensure_catalog_synced()
        assert sonuc is not None and sonuc.created == 5
        assert SchoolConfig.load().catalog_stamp
        assert services.ensure_catalog_synced() is None  # damga eşit

    def test_hazirlik_acilinca_sifir_seviyesi_gelir_kapaninca_gider(self, tmp_path: Path) -> None:
        self._kur(tmp_path)
        services.ensure_catalog_synced()
        assert Course.objects.get(name="Türk Dili ve Edebiyatı").levels == [9, 10, 11, 12]
        # Ayar kaydı senkronu kendisi koşturur.
        setup_service.update_school_config(fields={"has_prep_class": True})
        haz = Course.objects.get(name="Hazırlık Sınıfı Türk Dili ve Edebiyatı")
        assert haz.is_active and haz.levels == [0]
        bty = Course.objects.get(name="Bilişim Teknolojileri ve Yazılım")
        assert bty.levels == [0, 9, 10, 11, 12]
        # Hazırlık kapanınca: 0 düşer, hazırlığa özgü ders çizelge dışı kalır.
        setup_service.update_school_config(fields={"has_prep_class": False})
        haz.refresh_from_db()
        assert not haz.is_active and haz.catalog_excluded
        bty.refresh_from_db()
        assert bty.levels == [9, 10, 11, 12]
        # Geri açılınca yalnız çizelge dışı bayraklı kayıt yeniden AÇILIR.
        setup_service.update_school_config(fields={"has_prep_class": True})
        haz.refresh_from_db()
        assert haz.is_active and not haz.catalog_excluded
        assert services.ensure_catalog_synced() is None  # damga zaten güncel

    def test_geri_acma_sayaci(self, tmp_path: Path) -> None:
        self._kur(tmp_path)
        services.ensure_catalog_synced()
        Course.objects.filter(name="Coğrafya").update(is_active=False, catalog_excluded=True)
        sonuc = services.ensure_catalog_synced(force=True)
        assert sonuc is not None and sonuc.restored == 1
        assert Course.objects.get(name="Coğrafya").is_active

    def test_idarecinin_pasiflestirdigi_ders_senkronla_acilmaz(self, tmp_path: Path) -> None:
        self._kur(tmp_path)
        services.ensure_catalog_synced()
        ders = Course.objects.get(name="Coğrafya")
        services.update_course(ders, is_active=False)
        services.ensure_catalog_synced(force=True)
        ders.refresh_from_db()
        assert not ders.is_active and not ders.catalog_excluded

    def test_okul_turu_degisince_eski_dersler_cizelge_disi(self, tmp_path: Path) -> None:
        self._kur(tmp_path)
        services.ensure_catalog_synced()
        setup_service.update_school_config(
            fields={"school_type": SchoolType.SOSYAL_BILIMLER_LISESI}
        )
        assert Course.objects.get(name="Sanat Tarihi").is_active  # SBL'ye özgü ders geldi
        secmeli = Course.objects.get(name="Seçmeli Matematik")
        assert not secmeli.is_active and secmeli.catalog_excluded
        assert Course.objects.get(name="Coğrafya").levels == [9, 10, 11, 12]
        # Çizelge dışı: Seçmeli Matematik + BTY + Rehberlik.
        assert Course.objects.filter(catalog_excluded=True).count() == 3

    def test_elle_ders_ve_veri_yoksa_dokunulmaz(self, tmp_path: Path) -> None:
        self._kur(tmp_path)
        services.ensure_catalog_synced()
        elle = services.create_course(name="Okul Dersi", levels=[9])
        # Verisi olmayan tür: hiçbir kayda dokunulmaz, uyarı döner.
        setup_service.update_school_config(fields={"school_type": SchoolType.FEN_LISESI})
        sonuc = services.ensure_catalog_synced(force=True)
        assert sonuc is not None and sonuc.excluded == 0
        assert any("çizelge verisi" in w for w in sonuc.warnings)
        assert not Course.objects.filter(catalog_excluded=True).exists()
        elle.refresh_from_db()
        assert elle.is_active
        assert Course.objects.get(name="Türk Dili ve Edebiyatı").is_active

    def test_dosya_degisince_damga_degisir_ve_katalog_guncellenir(self, tmp_path: Path) -> None:
        """K5: uygulama sürümüyle gelen yeni dosya kurulu veritabanına da iner (göç gerekmez)."""
        root = self._kur(tmp_path)
        services.ensure_catalog_synced()
        (root / "al.md").write_text(
            AL_MD.replace("| Coğrafya | 9, 10 |", "| Coğrafya | 9-11 |"), encoding="utf-8"
        )
        sonuc = services.ensure_catalog_synced()
        assert sonuc is not None and sonuc.updated == 1
        assert Course.objects.get(name="Coğrafya").levels == [9, 10, 11]

    def test_kademeli_atama_kaydi(self, tmp_path: Path) -> None:
        self._kur(tmp_path)
        setup_service.update_school_config(fields={"level_programs": {"9": ["sbl-test"]}})
        assert Course.objects.get(name="Coğrafya").levels == [9, 10]
        assert not Course.objects.filter(name="Sanat Tarihi").exists()
        setup_service.update_school_config(fields={"level_programs": {"12": ["sbl-test"]}})
        assert Course.objects.get(name="Sanat Tarihi").levels == [12]
        assert Course.objects.get(name="Seçmeli Matematik").levels == [11]

    def test_liste_ucu_ve_kurulum_tamamlama_senkronu_kosturur(self, tmp_path: Path) -> None:
        self._kur(tmp_path)
        assert APIClient().get("/api/v1/courses/").status_code == 200
        assert Course.objects.filter(source=CourseSource.MEB_CATALOG).count() == 5
        (tmp_path / "al.md").write_text(
            AL_MD.replace("| Coğrafya | 9, 10 |", "| Coğrafya | 9-11 |"), encoding="utf-8"
        )
        setup_service.mark_setup_completed()
        assert Course.objects.get(name="Coğrafya").levels == [9, 10, 11]


@pytest.mark.django_db
class TestApi:
    def test_catalog_status_ve_onizleme(self, tmp_path: Path) -> None:
        root = _dizin(tmp_path, al=AL_MD, sbl=SBL_MD)
        client = APIClient()
        with override_settings(CATALOG_DIR=root, COURSE_ALIAS_FILE=root / "yok.md"):
            veri = client.get("/api/v1/courses/catalog-status/").json()
            assert veri["school_type"] == "ANADOLU_LISESI"
            assert [lv["level"] for lv in veri["levels"]] == [9, 10, 11, 12]
            assert veri["levels"][0]["programs"][0]["key"] == "al-test"
            assert veri["custom"] is False and veri["data_available"] is True
            # Önizleme: kaydedilmemiş seçim (SBL + hazırlık + 9 için AL).
            veri = client.get(
                "/api/v1/courses/catalog-status/",
                {
                    "school_type": "SOSYAL_BILIMLER_LISESI",
                    "has_prep_class": "1",
                    "level_programs": '{"9": ["al-test"]}',
                },
            ).json()
            assert veri["school_type"] == "SOSYAL_BILIMLER_LISESI"
            assert [lv["level"] for lv in veri["levels"]] == [0, 9, 10, 11, 12]
            assert veri["custom"] is True and veri["transitional"] is True
            assert veri["levels"][1]["explicit"] is True
            assert veri["synced"] is False
            yanit = client.get("/api/v1/courses/catalog-status/", {"level_programs": "bozuk"})
            assert yanit.status_code == 400

    def test_resync_ucu(self, tmp_path: Path) -> None:
        root = _dizin(tmp_path, al=AL_MD)
        with override_settings(CATALOG_DIR=root, COURSE_ALIAS_FILE=root / "yok.md"):
            yanit = APIClient().post("/api/v1/courses/resync/")
            assert yanit.status_code == 200
            assert yanit.json()["result"]["created"] == 5
            assert yanit.json()["status"]["synced"] is True

    def test_okul_turleri_ucu(self, tmp_path: Path) -> None:
        root = _dizin(tmp_path, al=AL_MD)
        with override_settings(CATALOG_DIR=root, COURSE_ALIAS_FILE=root / "yok.md"):
            veri = APIClient().get("/api/v1/setup/school-types/").json()
        secenek = {o["value"]: o for o in veri}
        assert secenek["ANADOLU_LISESI"]["available"] is True
        assert secenek["COK_PROGRAMLI_ANADOLU_LISESI"]["available"] is True
        assert secenek["FEN_LISESI"]["available"] is False

    def test_level_programs_dogrulamasi(self, tmp_path: Path) -> None:
        root = _dizin(tmp_path, al=AL_MD)
        client = APIClient()
        with override_settings(CATALOG_DIR=root, COURSE_ALIAS_FILE=root / "yok.md"):
            yanit = client.put(
                "/api/v1/setup/school-config/",
                {"school_name": "X", "level_programs": {"9": ["olmayan"]}},
                format="json",
            )
            assert yanit.status_code == 400
            yanit = client.put(
                "/api/v1/setup/school-config/",
                {"school_name": "X", "level_programs": {"8": ["al-test"]}},
                format="json",
            )
            assert yanit.status_code == 400
            yanit = client.put(
                "/api/v1/setup/school-config/",
                {"school_name": "X", "level_programs": {"9": ["al-test", "al-test"]}},
                format="json",
            )
            assert yanit.status_code == 200
            assert yanit.json()["level_programs"] == {"9": ["al-test"]}
            assert SchoolConfig.load().level_programs == {"9": ["al-test"]}

    def test_liste_cizelge_disi_bayragini_verir(self, tmp_path: Path) -> None:
        root = _dizin(tmp_path, al=AL_MD)
        with override_settings(CATALOG_DIR=root, COURSE_ALIAS_FILE=root / "yok.md"):
            client = APIClient()
            client.get("/api/v1/courses/")
            Course.objects.filter(name="Coğrafya").update(is_active=False, catalog_excluded=True)
            veri = client.get("/api/v1/courses/?include_inactive=true").json()
        satir = next(c for c in veri if c["name"] == "Coğrafya")
        assert satir["catalog_excluded"] is True and satir["source"] == CourseSource.MEB_CATALOG
