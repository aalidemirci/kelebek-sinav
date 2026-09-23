"""Kilit kapısı — uygulama parolası kuruluyken açılmamış veriye API erişimini keser.

Tasarım §6. Parola kurulu ve kilit açılmamışken hassas alanlar zaten okunamaz
(şifreli token döner) ve yazılamaz (`shared.crypto.KeyMissingError`), ama
uygulamanın "çalışıyormuş gibi" davranıp resmî evraka çözülememiş metin basması
KABUL EDİLEMEZ. Bu ara katman iki kilidi uygular; ikisi de tek sorguyla
belirlenir (`app_password.gate_state`):

1. **Güvenlik dosyası kayıp** (`423 guvenlik_dosyasi_kayip`): DB'de anahtar
   parmak izi var ama `guvenlik.json` yok — ya da dosya var ama kullanılamıyor
   (boş, bozuk, sarmal bölümleri eksik). Dosyanın silinmesi, yeniden
   adlandırılması ya da bozulması programı "parolasız"a döndürmez ve kullanıcıyı
   çıkışsız bir kilit ekranında da bırakmaz. Anahtar bellekteyken dosya kaybolsa
   bile kapı kapanır: bir sonraki kilitte açılamayacak bir durumda çalışmaya
   devam etmek yerine kullanıcı sorunu hemen görür. Açık kalanlar (TAM yol):
   - `GET setup/status/` — açılış sağlık denetimi (`desktop/server.py::HEALTH_PATH`);
   - `GET security/status/` — arayüzün hangi ekranı göstereceğini öğrendiği uç;
   - `POST security/state/reset/` — yalnız korunan satır yokken (parmak izi boş)
     okunamayan dosyayı arşivleyip parolasız kipe döner; uç koşulu kendisi
     denetler (aksi 409);
   - `GET backups/` ve `POST backups/restore/` — çıkış yolu: geri yükleme
     `guvenlik.json`'u yedeğin kurtarma başlığından yeniden yazar
     (`backup_restore._ensure_state_file`). Diğer çıkış yolu dosyanın sağlam
     kopyasını veri klasörüne geri koymaktır; kapı her istekte diske bakar,
     dosya döndüğü anda olağan kilit durumuna geçilir.
2. **Kilitli** (`423 locked`): parola kurulu, anahtar bellekte değil. Açık kalanlar:
   - `/api/v1/security/` ön eki — durum, kilit açma, kurtarma (kilidi açmanın
     tek yolu bunlar). İstisna `LOCKED_DENIED_PATHS`: kurtarma anahtarı
     yenileme kilitliyken kesilir (kilit açma yolu değildir; açık kalsaydı
     parola için ikinci bir deneme kapısı olurdu);
   - `GET setup/status/` — açılış sağlık denetimi; yanıtı kişisel veri içermez
     (okul adı + kayıt sayaçları) ve istek zaten oturum belirteci gerektirir.
     Kurulum sihirbazının YAZMA uçları kapalı kalır;
   - `/api/v1/updates/` — kişisel veri içermeyen sürüm denetimi (F8).

Parolasız kipte (güvenlik dosyası yok VE parmak izi boş) kapı hiçbir şey yapmaz.

API dışı yollar (SPA'nın kendisi, statik dosyalar) daima serbesttir — kilit
ekranı yüklenebilmelidir. **Yerel yedekleme etkilenmez**: günlük yedek bir HTTP
ucu değildir, masaüstü kabuğu onu açılışta açık yedek anahtarıyla alır
(`desktop/main.py`). Ortaya yalnız AES-256-GCM korumalı `.ksbak` çıkar.

Bu ara katman `config/settings.py` MIDDLEWARE listesine eklenir. Eklenmezse
program yine çalışır (alanlar şifreli görünür), yalnız bu kapı devre dışı kalır.
"""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

from apps.okul.services import app_password
from shared.exceptions import LOCKED_CODE, LOCKED_MESSAGE

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
# `security/` ön ekinde olup kilitliyken YİNE DE kesilen uçlar (TAM yol).
LOCKED_DENIED_PATHS = frozenset({"/api/v1/security/recovery-key/renew/"})
# Güvenlik dosyası kayıpken izin verilen uçlar (TAM yol eşleşmesi).
SECURITY_FILE_MISSING_ALLOWED_PATHS = frozenset(
    {
        "/api/v1/setup/status/",
        "/api/v1/security/status/",
        "/api/v1/security/state/reset/",
        "/api/v1/backups/",
        "/api/v1/backups/restore/",
    }
)

# Şifreli alan kapısının 423'üyle (`shared.exceptions.LockedResponse`) aynı gövde.
_LOCKED_BODY = {"code": LOCKED_CODE, "message": LOCKED_MESSAGE, "fields": {}}

_SECURITY_FILE_MISSING_BODY = {
    "code": "guvenlik_dosyasi_kayip",
    "message": app_password.SECURITY_FILE_MISSING_MESSAGE,
    "fields": {},
}


class AppLockMiddleware:
    """Güvenlik dosyası kayıpken ve kilitliyken izinli uçlar dışındaki API'yi 423 ile keser."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self._get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        path = request.path
        if path.startswith(API_PREFIX):
            # Gövdeler sabit: hangi ucun istendiği yankılanmaz, kilit sebebi sızdırılmaz.
            kapi = app_password.gate_state()
            if kapi == app_password.GATE_MISSING:
                if path not in SECURITY_FILE_MISSING_ALLOWED_PATHS:
                    return JsonResponse(_SECURITY_FILE_MISSING_BODY, status=423)
            elif kapi == app_password.GATE_LOCKED and (
                not path.startswith(ALLOWED_PREFIXES) or path in LOCKED_DENIED_PATHS
            ):
                return JsonResponse(_LOCKED_BODY, status=423)
        return self._get_response(request)
