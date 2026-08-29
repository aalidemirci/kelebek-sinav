"""Kök URL yapılandırması — tüm API `/api/v1/` altında (kebab-case, çoğul kaynak).

Sonda SPA catch-all durur: masaüstü penceresi kök URL'yi açar ve istemci-tarafı
rotalar (`/oturumlar/12` gibi) sunucuda tanımlı DEĞİLDİR — hepsi `index.html`'e
düşer, gerisini React yönlendiricisi çözer. `api/` ve `static/` ön ekleri dışarıda
bırakılır; aksi hâlde var olmayan bir API ucu 404 yerine HTML döner ve istemci onu
JSON sanar.
"""

from __future__ import annotations

from django.conf import settings
from django.http import FileResponse, HttpRequest, HttpResponse, HttpResponseBase
from django.urls import URLPattern, URLResolver, include, path, re_path

urlpatterns: list[URLPattern | URLResolver] = [
    path("api/v1/", include("apps.okul.urls")),
    path("api/v1/", include("apps.dersler.urls")),
]


def spa(request: HttpRequest) -> HttpResponseBase:
    """SPA giriş noktası — derlenmiş `index.html`."""
    index = settings.FRONTEND_DIR / "index.html"
    if not index.exists():
        # Arayüz derlenmemiş (temiz depo) ya da paket eksik: sessiz beyaz ekran
        # yerine ne yapılacağını söyle.
        return HttpResponse(
            "<!doctype html><meta charset='utf-8'>"
            "<p>Arayüz derlenmemiş. Geliştirmede <code>npm run build</code> çalıştırın; "
            "kurulu programda paket eksiktir, yeniden kurun.</p>",
            content_type="text/html; charset=utf-8",
            status=503,
        )
    return FileResponse(index.open("rb"), content_type="text/html")


urlpatterns += [re_path(r"^(?!api/|static/).*$", spa, name="spa")]
