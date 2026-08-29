"""Yerel oturum belirteci testleri (tasarım §5.3 son madde — KRİTİK).

Program authsuz olduğundan, gömülü sunucu ayakta olduğu sürece aynı makinedeki
BAŞKA bir işlem 127.0.0.1'e istek atıp öğrenci verisini okuyabilir. Belirteç bunu
engeller: yalnız pencerenin bildiği rastgele değeri taşıyan istekler geçer.
"""

from __future__ import annotations

import json

import pytest
from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from desktop.session_guard import (
    ENV_TOKEN,
    SESSION_COOKIE_NAME,
    TOKEN_HEADER,
    TOKEN_QUERY_PARAM,
    SessionTokenMiddleware,
    generate_session_token,
    window_url,
)

TOKEN = "test-belirteci-1234567890"  # gitleaks:allow — yalnız test sabiti


@pytest.fixture
def guard(monkeypatch: pytest.MonkeyPatch) -> SessionTokenMiddleware:
    monkeypatch.setenv(ENV_TOKEN, TOKEN)

    def gorunum(request: HttpRequest) -> HttpResponse:
        return HttpResponse("tamam")

    return SessionTokenMiddleware(gorunum)


def test_belirtec_yeterince_uzun_ve_her_seferinde_farkli() -> None:
    ilk, ikinci = generate_session_token(), generate_session_token()

    assert ilk != ikinci
    assert len(ilk) >= 32
    assert ilk.isascii()


def test_belirtec_yoksa_middleware_hic_yuklenmez(monkeypatch: pytest.MonkeyPatch) -> None:
    """Geliştirme/test koşusunda (`KS_SESSION_TOKEN` boş) middleware devre dışıdır."""
    monkeypatch.delenv(ENV_TOKEN, raising=False)

    with pytest.raises(MiddlewareNotUsed):
        SessionTokenMiddleware(lambda request: HttpResponse())


def test_belirtecsiz_istek_reddedilir(guard: SessionTokenMiddleware) -> None:
    yanit = guard(RequestFactory().get("/api/v1/students/"))

    assert yanit.status_code == 403
    govde = json.loads(yanit.content)
    assert set(govde) == {"code", "message", "fields"}
    assert govde["code"] == "forbidden"
    assert govde["message"]
    assert govde["fields"] == {}


def test_yanlis_belirtec_reddedilir(guard: SessionTokenMiddleware) -> None:
    istek = RequestFactory().get(f"/?{TOKEN_QUERY_PARAM}=yanlis")

    assert guard(istek).status_code == 403


def test_ret_yaniti_belirteci_sizdirmaz(guard: SessionTokenMiddleware) -> None:
    yanit = guard(RequestFactory().get("/api/v1/students/"))

    assert TOKEN.encode() not in yanit.content


def test_dogru_cerez_gecer(guard: SessionTokenMiddleware) -> None:
    istekci = RequestFactory()
    istekci.cookies[SESSION_COOKIE_NAME] = TOKEN

    yanit = guard(istekci.get("/api/v1/students/"))

    assert yanit.status_code == 200
    assert yanit.content == b"tamam"


def test_url_belirteci_gecer_ve_cerez_kurulur(guard: SessionTokenMiddleware) -> None:
    """İlk gezinme URL'den gelir; sonraki XHR istekleri çerezle taşınır."""
    yanit = guard(RequestFactory().get(f"/?{TOKEN_QUERY_PARAM}={TOKEN}"))

    assert yanit.status_code == 200
    cerez = yanit.cookies[SESSION_COOKIE_NAME]
    assert cerez.value == TOKEN
    assert cerez["httponly"]
    assert cerez["samesite"] == "Strict"
    assert cerez["path"] == "/"


def test_baslik_adi_django_meta_bicimindedir() -> None:
    assert TOKEN_HEADER == "HTTP_X_KS_TOKEN"  # `X-KS-Token` başlığının META karşılığı


def test_baslik_ile_de_gecilebilir(guard: SessionTokenMiddleware) -> None:
    yanit = guard(RequestFactory().get("/api/v1/students/", headers={"x-ks-token": TOKEN}))

    assert yanit.status_code == 200
    assert SESSION_COOKIE_NAME not in yanit.cookies


def test_cerez_gelen_istekte_yeniden_kurulmaz(guard: SessionTokenMiddleware) -> None:
    istekci = RequestFactory()
    istekci.cookies[SESSION_COOKIE_NAME] = TOKEN

    yanit = guard(istekci.get("/"))

    assert SESSION_COOKIE_NAME not in yanit.cookies


def test_karsilastirma_sabit_zamanlidir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Belirteç karşılaştırması `hmac.compare_digest` ile yapılmalı (zamanlama sızıntısı)."""
    import hmac

    cagrildi: list[bool] = []
    gercek = hmac.compare_digest

    def izleyici(a: str, b: str) -> bool:
        cagrildi.append(True)
        return bool(gercek(a, b))

    monkeypatch.setenv(ENV_TOKEN, TOKEN)
    # `session_guard` de aynı modül nesnesini kullanır (`import hmac`).
    monkeypatch.setattr(hmac, "compare_digest", izleyici)
    guard = SessionTokenMiddleware(lambda request: HttpResponse())

    guard(RequestFactory().get(f"/?{TOKEN_QUERY_PARAM}={TOKEN}"))

    assert cagrildi


def test_pencere_url_i_belirteci_tasir() -> None:
    assert window_url("http://127.0.0.1:5051", TOKEN) == (
        f"http://127.0.0.1:5051/?{TOKEN_QUERY_PARAM}={TOKEN}"
    )


def test_pencere_url_i_ozel_karakterleri_kacisir() -> None:
    assert "+" not in window_url("http://127.0.0.1:1", "a b+c")
