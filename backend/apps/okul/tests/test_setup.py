"""Kurulum sihirbazı uçları + kurulum durumu (KS uyarlaması).

`setup/status/` alan kümesi hem arayüz kurulum kapısının hem masaüstü sağlık
denetiminin sözleşmesidir — küme değişirse FE `SetupStatus` tipi ve
`desktop/server.py` birlikte gözden geçirilir.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.okul.models import SchoolConfig, SchoolType
from apps.okul.services import setup as setup_service


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
class TestSetupStatus:
    def test_alan_kumesi_ve_bos_kurulum(self, client: APIClient) -> None:
        yanit = client.get("/api/v1/setup/status/")
        assert yanit.status_code == 200
        assert set(yanit.json().keys()) == {
            "setup_completed",
            "school_name",
            "has_active_school_year",
            "student_count",
            "personnel_count",
            "class_section_count",
        }
        assert yanit.json()["setup_completed"] is False

    def test_kurulum_sonrasi_sayimlar(self, client: APIClient) -> None:
        client.put(
            "/api/v1/setup/school-config/",
            {"school_name": "Örnek Anadolu Lisesi", "province": "İstanbul", "district": "Örnek"},
            format="json",
        )
        yil = client.post(
            "/api/v1/school-years/",
            {"name": "2026-2027", "start_date": "2026-09-01", "end_date": "2027-06-30"},
            format="json",
        ).json()
        client.post(f"/api/v1/school-years/{yil['id']}/activate/")
        client.post("/api/v1/setup/complete/")

        veri = client.get("/api/v1/setup/status/").json()
        assert veri["setup_completed"] is True
        assert veri["school_name"] == "Örnek Anadolu Lisesi"
        assert veri["has_active_school_year"] is True


@pytest.mark.django_db
class TestSchoolConfigApi:
    def test_okul_turu_ve_hazirlik_guncellenir(self, client: APIClient) -> None:
        yanit = client.put(
            "/api/v1/setup/school-config/",
            {
                "school_name": "Örnek AL",
                "school_type": SchoolType.ANADOLU_LISESI,
                "has_prep_class": True,
            },
            format="json",
        )
        assert yanit.status_code == 200
        assert yanit.json()["has_prep_class"] is True
        assert SchoolConfig.load().grade_levels == (0, 9, 10, 11, 12)

    def test_setup_completed_put_ile_degistirilemez(self, client: APIClient) -> None:
        """Kapı alanı yalnız `setup/complete/` ucuyla açılır (read-only)."""
        client.put(
            "/api/v1/setup/school-config/",
            {"school_name": "X", "setup_completed": True},
            format="json",
        )
        assert SchoolConfig.load().setup_completed is False

    def test_gecersiz_okul_turu_reddedilir(self, client: APIClient) -> None:
        yanit = client.put(
            "/api/v1/setup/school-config/",
            {"school_name": "X", "school_type": "MESLEK_LISESI"},
            format="json",
        )
        assert yanit.status_code == 400


@pytest.mark.django_db
class TestGradeLevelsApi:
    def test_seviyeler_okul_turunden_turetilir(self, client: APIClient) -> None:
        veri = client.get("/api/v1/grade-levels/").json()
        assert [x["value"] for x in veri["levels"]] == [9, 10, 11, 12]
        assert veri["prep_enabled"] is False

    def test_hazirlik_acilinca_listeye_girer(self, client: APIClient) -> None:
        setup_service.update_school_config(fields={"has_prep_class": True})
        veri = client.get("/api/v1/grade-levels/").json()
        assert veri["levels"][0] == {"value": 0, "label": "Hazırlık"}
        assert veri["prep_enabled"] is True


@pytest.mark.django_db
class TestSchoolYearTerms:
    def test_donem_yapilandirma(self, client: APIClient) -> None:
        yil = client.post(
            "/api/v1/school-years/",
            {"name": "2026-2027", "start_date": "2026-09-01", "end_date": "2027-06-30"},
            format="json",
        ).json()
        yanit = client.put(
            f"/api/v1/school-years/{yil['id']}/terms/",
            {"first_term_end": "2027-01-16", "second_term_start": "2027-02-01"},
            format="json",
        )
        assert yanit.status_code == 200
        donemler = yanit.json()
        assert [d["sequence"] for d in donemler] == [1, 2]
        assert donemler[0]["start_date"] == "2026-09-01"
        assert donemler[1]["end_date"] == "2027-06-30"

    def test_ters_donem_tarihleri_reddedilir(self, client: APIClient) -> None:
        yil = client.post(
            "/api/v1/school-years/",
            {"name": "2026-2027", "start_date": "2026-09-01", "end_date": "2027-06-30"},
            format="json",
        ).json()
        yanit = client.put(
            f"/api/v1/school-years/{yil['id']}/terms/",
            {"first_term_end": "2027-02-01", "second_term_start": "2027-01-16"},
            format="json",
        )
        assert yanit.status_code == 400


def test_spa_catchall_arayuz_derlenmemisken_503_ve_turkce_yonerge() -> None:
    """SPA catch-all, dist yokken beyaz ekran yerine Türkçe yönerge döndürür."""
    yanit = APIClient().get("/olmayan-bir-rota")
    assert yanit.status_code in (200, 503)  # dist derlenmişse 200, temiz depoda 503
    if yanit.status_code == 503:
        assert "Arayüz derlenmemiş".encode() in yanit.content


@pytest.mark.django_db
def test_update_school_config_whitelist_disi_alan_yazmaz() -> None:
    setup_service.update_school_config(fields={"school_name": "X", "app_password_hash": "hack"})
    assert SchoolConfig.load().app_password_hash == ""


@pytest.mark.django_db
def test_letterhead_identity_bos_okul_adi_yer_tutucuya_duser() -> None:
    assert setup_service.get_letterhead_identity()["school_name"] == "Okul"
