"""Yerel oturum belirteci — authsuz programın tek ağ sigortası (tasarım §5.3).

**Tehdit:** Program 127.0.0.1'de kimlik doğrulamasız bir HTTP sunucusu çalıştırır.
Aynı makinedeki başka bir işlem (başka bir kullanıcı oturumu, bir tarayıcı sekmesi,
kötü niyetli bir betik) portu tarayıp `GET /api/v1/students/` isteyebilir ve
öğrenci/veli verisini okuyabilir. Yerel olması "erişilemez" demek değildir.

**Sigorta:** Program her açılışta rastgele bir belirteç üretir. Belirteç yalnız
pencerenin açılış URL'sinde taşınır; middleware belirteçsiz her isteği 403 ile
reddeder. İlk gezinmede belirteç `HttpOnly` bir çereze yazılır, sonraki API
istekleri çerezle geçer (frontend'de değişiklik gerektirmez).

**Belirteç asla loglanmaz** — ret yanıtında da yankılanmaz.

Middleware `config/settings.py`'ye YALNIZ `KS_SESSION_TOKEN` doluyken eklenir;
geliştirme/test koşusunda hiç yüklenmez (`MiddlewareNotUsed`).
"""

from __future__ import annotations

import hmac
import os
import secrets
from collections.abc import Callable
from urllib.parse import quote

from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpRequest, HttpResponse, JsonResponse

# S105 bastırmaları: bunlar parola değil, ORTAM DEĞİŞKENİ/BAŞLIK ADIDIR.
ENV_TOKEN = "KS_SESSION_TOKEN"  # noqa: S105
SESSION_COOKIE_NAME = "ks_oturum"
TOKEN_QUERY_PARAM = "t"  # noqa: S105
# Django'nun WSGI/`HttpRequest.META` biçimi: `X-KS-Token` başlığı.
TOKEN_HEADER = "HTTP_X_KS_TOKEN"  # noqa: S105

_TOKEN_BYTES = 32

_DENIED = {
    "code": "forbidden",
    "message": (
        "Bu isteğe izin verilmedi. Program penceresini kapatıp yeniden açın; "
        "verilere yalnızca programın kendi penceresinden erişilebilir."
    ),
    "fields": {},
}


def generate_session_token() -> str:
    """Açılışa özel rastgele belirteç (her çalıştırmada yeni)."""
    return secrets.token_urlsafe(_TOKEN_BYTES)


def window_url(base_url: str, token: str) -> str:
    """Pencerenin açacağı URL — belirteci taşır."""
    return f"{base_url.rstrip('/')}/?{TOKEN_QUERY_PARAM}={quote(token, safe='')}"


class SessionTokenMiddleware:
    """Belirteç taşımayan istekleri sözleşmeli 403 ile reddeder."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        token = os.environ.get(ENV_TOKEN, "")
        if not token:
            # Masaüstü kabuğu dışında (geliştirme, testler, `manage.py`) devre dışı.
            raise MiddlewareNotUsed
        self._token = token
        self._get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        supplied, from_query = self._supplied_token(request)
        if supplied is None or not hmac.compare_digest(supplied, self._token):
            return JsonResponse(_DENIED, status=403)

        response = self._get_response(request)
        if from_query:
            # Sonraki istekler (XHR, statik dosyalar) çerezle geçsin.
            response.set_cookie(
                SESSION_COOKIE_NAME,
                self._token,
                httponly=True,
                samesite="Strict",
                secure=False,  # yerel http://127.0.0.1 — TLS yok
                path="/",
            )
        return response

    def _supplied_token(self, request: HttpRequest) -> tuple[str | None, bool]:
        """(belirteç, URL'den mi geldi) — çerez > başlık > sorgu dizesi."""
        cookie = request.COOKIES.get(SESSION_COOKIE_NAME)
        if cookie:
            return cookie, False
        header = request.META.get(TOKEN_HEADER)
        if header:
            return str(header), False
        query = request.GET.get(TOKEN_QUERY_PARAM)
        if query:
            return query, True
        return None, False
