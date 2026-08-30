"""Kilit kapısı — uygulama parolası kuruluyken açılmamış veriye API erişimini keser.

Tasarım §6. Parola kurulu ve kilit açılmamışken hassas alanlar zaten okunamaz
(şifreli token döner), ama uygulamanın "çalışıyormuş gibi" davranıp resmî evraka
çözülememiş metin basması KABUL EDİLEMEZ. Bu ara katman, kilitliyken güvenlik
uçları dışındaki tüm API isteklerini `423 Locked` ile reddeder.

KİLİTLİYKEN NE ÇALIŞIR (kritik tasarım sorusu 1'in ikinci yarısı):

* `GET /api/v1/security/status/`, `POST /api/v1/security/unlock/`,
  `POST /api/v1/security/recover/` — kilidi açmanın tek yolu bunlar.
* `GET /api/v1/setup/status/` — masaüstü kabuğunun AÇILIŞ SAĞLIK DENETİMİ bu
  ucu çağırır (`desktop/server.py::HEALTH_PATH`); kilitliyken 423 dönseydi
  parola kurulu her kurulumda program hiç açılmazdı. Yanıtı kişisel veri
  içermez (okul adı + kayıt sayaçları) ve istek zaten oturum belirteci
  gerektirir. Kurulum sihirbazının YAZMA uçları kapalı kalır.
* API dışı yollar (SPA'nın kendisi, statik dosyalar) — kilit ekranının
  yüklenebilmesi için serbest.
* **Yerel yedekleme etkilenmez**: günlük yedek bir HTTP ucu değildir, masaüstü
  kabuğu onu açılışta açık yedek anahtarıyla alır (`desktop/main.py`). Ortaya
  yalnız AES-256-GCM korumalı `.ksbak` çıkar; kilit bunu engellemez.

Bu ara katman `config/settings.py` MIDDLEWARE listesine eklenir. Eklenmezse
program yine çalışır (alanlar şifreli görünür), yalnız bu kapı devre dışı kalır.
"""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

from apps.okul.services import app_password

API_PREFIX = "/api/"
# Kilitliyken izin verilen uçlar (ön ek eşleşmesi).
ALLOWED_PREFIXES = (
    "/api/v1/security/",
    # Açılış sağlık denetimi (bkz. dosya başlığı). YALNIZ bu tekil yol; kurulum
    # sihirbazının diğer uçları kapalıdır.
    "/api/v1/setup/status/",
    # Kişisel veri içermez; kilit ekranında başlayan otomatik sürüm denetimi (F8).
    "/api/v1/updates/",
)

_LOCKED_BODY = {
    "code": "locked",
    "message": (
        "Kayıtlar uygulama parolasıyla kilitli. Devam etmek için parolanızı girin "
        "(parolanızı unuttuysanız kurtarma anahtarını kullanın)."
    ),
    "fields": {},
}


class AppLockMiddleware:
    """Kilitliyken güvenlik uçları dışındaki API isteklerini 423 ile reddeder."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self._get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        path = request.path
        if (
            path.startswith(API_PREFIX)
            and not path.startswith(ALLOWED_PREFIXES)
            and app_password.is_locked()
        ):
            # Gövde sabit: hangi ucun istendiği yankılanmaz, kilit sebebi sızdırılmaz.
            return JsonResponse(_LOCKED_BODY, status=423)
        return self._get_response(request)
