"""Gömülü WSGI sunucusu — waitress, arka plan thread'i, 127.0.0.1 + boş port.

Tasarım §5.3: sunucu **sabit port kullanmaz**. Okul bilgisayarında 8000/8080
başka bir program tarafından tutuluyor olabilir; `port=0` ile işletim sistemine
boş port seçtirilir ve gerçek port `effective_port`'tan okunur (önce boş port
arayıp sonra ona bağlanmak yarış koşulu yaratırdı).

`host="127.0.0.1"`: LAN'dan erişilemez. Yerel erişim sigortası ayrıca
`session_guard.SessionTokenMiddleware`'dedir.

waitress istek (erişim) logu üretmez; `logging_setup` bunu ayrıca susturur.
"""

from __future__ import annotations

import logging
import socket
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any, Protocol

from desktop.errors import ServerStartError
from desktop.session_guard import TOKEN_QUERY_PARAM

logger = logging.getLogger("kelebek_sinav.server")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_THREADS = 6
HEALTH_PATH = "/api/v1/setup/status/"


class WSGIServerLike(Protocol):
    """waitress sunucusunun kullandığımız yüzeyi (test için enjekte edilebilir).

    `effective_port` waitress'te METİN döner (`"41435"`); tip bilerek geniştir.
    """

    effective_port: int | str

    def run(self) -> None: ...

    def close(self) -> None: ...


ServerFactory = Callable[..., WSGIServerLike]


def find_free_port(host: str = DEFAULT_HOST) -> int:
    """İşletim sisteminden boş bir port ister (`bind(0)`)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _waitress_factory(app: Any, **kwargs: Any) -> WSGIServerLike:
    """waitress TEMBEL içe aktarılır (paket yoksa modül yine de import edilebilsin)."""
    from waitress.server import create_server  # type: ignore[import-untyped]

    server: WSGIServerLike = create_server(app, **kwargs)
    return server


class BackgroundServer:
    """Uygulamayı arka plan thread'inde çalıştıran gömülü sunucu."""

    def __init__(
        self,
        app: Any,
        *,
        host: str = DEFAULT_HOST,
        threads: int = DEFAULT_THREADS,
        server_factory: ServerFactory | None = None,
    ) -> None:
        self._app = app
        self._host = host
        self._threads = threads
        self._factory = server_factory or _waitress_factory
        self._server: WSGIServerLike | None = None
        self._thread: threading.Thread | None = None
        self._started = threading.Event()

    @property
    def port(self) -> int:
        """Dinlenen gerçek port. waitress metin döndürdüğü için tam sayıya çevrilir."""
        return int(self._server.effective_port) if self._server is not None else 0

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self.port}"

    @property
    def thread(self) -> threading.Thread | None:
        return self._thread

    def start(self) -> str:
        """Sunucuyu ayağa kaldırır ve taban URL'sini döndürür."""
        try:
            self._server = self._factory(
                self._app,
                host=self._host,
                port=0,  # boş portu işletim sistemi seçsin
                threads=self._threads,
                ident=None,  # `Server:` başlığında sürüm sızdırma
                clear_untrusted_proxy_headers=True,
            )
        except Exception as exc:  # noqa: BLE001 — her hata aynı Türkçe mesaja çıkar
            raise ServerStartError(
                "Program başlatılamadı: yerel sunucu ayağa kalkmadı.",
                hint="Bilgisayarı yeniden başlatıp deneyin; sorun sürerse günlük dosyasına bakın.",
            ) from exc

        def _run() -> None:
            self._started.set()
            server = self._server
            if server is not None:
                server.run()

        self._thread = threading.Thread(target=_run, name="ks-wsgi", daemon=True)
        self._thread.start()
        logger.info("Yerel sunucu başladı (port %d).", self.port)
        return self.base_url

    def wait_until_started(self, *, timeout: float = 5.0) -> None:
        """Thread'in çalışmaya başlamasını bekler (soket denemesi yapmaz)."""
        if not self._started.wait(timeout):
            raise ServerStartError("Program başlatılamadı: yerel sunucu yanıt vermedi.")

    def wait_until_ready(self, *, timeout: float = 15.0) -> None:
        """Port bağlantı kabul edene kadar bekler."""
        self.wait_until_started(timeout=min(timeout, 5.0))
        deadline = time.monotonic() + timeout
        last: OSError | None = None
        while time.monotonic() < deadline:
            try:
                with socket.create_connection((self._host, self.port), timeout=1.0):
                    return
            except OSError as exc:
                last = exc
                time.sleep(0.05)
        raise ServerStartError(
            "Program başlatılamadı: yerel sunucu yanıt vermedi.",
            hint="Güvenlik duvarı veya antivirüs yerel bağlantıyı engelliyor olabilir.",
        ) from last

    def stop(self) -> None:
        """Sunucuyu kapatır (thread daemon olduğu için süreç kapanışını bloklamaz)."""
        server, self._server = self._server, None
        thread, self._thread = self._thread, None
        if server is not None:
            try:
                server.close()
            except OSError:
                pass
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self._started.clear()


def _status_code(url: str, timeout: float) -> int:
    """URL'nin HTTP durum kodunu döndürür (4xx/5xx istisna değil, sonuçtur)."""
    request = urllib.request.Request(url, method="GET")  # noqa: S310 — sabit http://127.0.0.1
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def check_health(
    base_url: str,
    token: str,
    *,
    path: str = HEALTH_PATH,
    timeout: float = 10.0,
) -> None:
    """Açılış sağlık denetimi: koruma çalışıyor mu, uygulama yanıt veriyor mu?

    İki istek atar:
    1. **Belirteçsiz** → 403 beklenir. 200 dönerse koruma devrede değildir; bu,
       aynı makinedeki her işlemin öğrenci verisini okuyabilmesi demektir → durulur.
    2. **Belirteçli** → 2xx beklenir (uygulama + veritabanı ayakta).
    """
    root = base_url.rstrip("/")
    try:
        unguarded = _status_code(f"{root}{path}", timeout)
    except (urllib.error.URLError, OSError) as exc:
        raise ServerStartError(
            "Program başlatılamadı: yerel sunucuya bağlanılamadı.",
            hint="Güvenlik duvarı veya antivirüs yerel bağlantıyı engelliyor olabilir.",
        ) from exc

    if unguarded != 403:
        raise ServerStartError(
            "Program başlatılamadı: yerel erişim koruması devrede değil.",
            hint="Kurulum bozuk olabilir; programı yeniden kurun.",
        )

    guarded = _status_code(f"{root}{path}?{TOKEN_QUERY_PARAM}={token}", timeout)
    if not 200 <= guarded < 300:
        raise ServerStartError(
            f"Program başlatılamadı: uygulama yanıt vermedi (HTTP {guarded}).",
            hint="Günlük dosyasında ayrıntı bulabilirsiniz.",
        )
