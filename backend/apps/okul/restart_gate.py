"""Geri yükleme sonrası "yeniden başlat" kapısı (Güvenlik sekmesi ayağı).

Çalışan sunucunun altındaki db.sqlite3 bir yedekle DEĞİŞTİRİLDİĞİNDE süreç içi
durum diskteki veriyi artık tarif etmez: bellekteki DEK eski veritabanına
aittir, bekleyen şema göçleri yalnız açılışta koşar, Django/DRF önbellekleri
eski kayıtları taşıyabilir. Program kendini yeniden BAŞLATAMAZ (pencere
pywebview olay döngüsüne bağlıdır, sunucu onun içinde bir thread'dir); bu kapı
ikinci en güvenli şeyi yapar: bayrak kalktıktan sonra TÜM API isteklerini
`503 restart_required` ile keser. Arayüz bu kodu tam ekran "programı kapatıp
yeniden açın" ekranına çevirir (frontend `lib/restart.ts`).

Bayrak SÜREÇ İÇİ ve tek yönlüdür: temizlemenin tek yolu süreci kapatmaktır
(testler `_reset_for_tests` kullanır). Middleware, kilit kapısından
(`lock_middleware`) ÖNCE durur — geri yükleme uygulandıysa kilit durumu da
bayat bilgidir. SPA'nın kendisi ve statik dosyalar serbesttir: kullanıcı
sayfayı yenilese de yönlendirme ekranı yüklenebilmelidir.
"""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

API_PREFIX = "/api/"

RESTART_MESSAGE = "Yedekten geri yükleme uygulandı. Devam etmek için programı kapatıp yeniden açın."

_BODY = {"code": "restart_required", "message": RESTART_MESSAGE, "fields": {}}

_restart_required = False


def mark_restart_required() -> None:
    """Kapıyı kapatır; bu süreçte bir daha açılmaz (yeniden başlatma gerekir)."""
    global _restart_required
    _restart_required = True


def restart_required() -> bool:
    return _restart_required


def _reset_for_tests() -> None:
    """Yalnız testler için: bayrak süreç içi olduğundan testler arasında sızar."""
    global _restart_required
    _restart_required = False


class RestartRequiredMiddleware:
    """Geri yükleme uygulandıktan sonra tüm API isteklerini 503 ile keser."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self._get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if _restart_required and request.path.startswith(API_PREFIX):
            return JsonResponse(_BODY, status=503)
        return self._get_response(request)
