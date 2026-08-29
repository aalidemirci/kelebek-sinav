"""F0 kurulum durumu ucu — sözleşme testleri.

Uç hem arayüz kurulum kapısının hem masaüstü sağlık denetiminin dayanağıdır;
F1'de gerçek verilere bağlanınca bu testler alan kümesini korumaya devam eder.
"""

from __future__ import annotations

from rest_framework.test import APIClient


def test_setup_status_alan_kumesi() -> None:
    yanit = APIClient().get("/api/v1/setup/status/")

    assert yanit.status_code == 200
    assert set(yanit.data.keys()) == {
        "setup_completed",
        "school_name",
        "has_active_school_year",
        "student_count",
        "personnel_count",
    }
    # F0 iskeletinde kurulum hiçbir zaman tamamlanmış görünmez.
    assert yanit.data["setup_completed"] is False


def test_spa_catchall_arayuz_derlenmemisken_503_ve_turkce_yonerge() -> None:
    """SPA catch-all, dist yokken beyaz ekran yerine Türkçe yönerge döndürür."""
    yanit = APIClient().get("/olmayan-bir-rota")

    assert yanit.status_code in (200, 503)  # dist derlenmişse 200, temiz depoda 503
    if yanit.status_code == 503:
        assert "Arayüz derlenmemiş".encode() in yanit.content
