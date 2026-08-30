"""Tek-instance kilidi (tasarım §5.3) + Inno AppMutex sinyali.

İki kopya aynı SQLite dosyasına yazarsa WAL kilitleri yüzünden kullanıcı
"veritabanı kilitli" hatalarıyla karşılaşır; daha kötüsü iki pencere aynı dosya
üzerinde farklı işlem yapar. Bu yüzden ikinci kopya **pencere açmadan** Türkçe
mesajla çıkar.

Yöntem işletim sistemine göre değişir ama sözleşme aynıdır: bir dosya açılır ve
üzerine paylaşımsız kilit konur. Kilit süreç ölünce (çökme dahil) işletim sistemi
tarafından bırakılır — bayat PID dosyası sorunu yaşanmaz.

Windows'ta kilide EK olarak `KelebekSinav` adlı bir mutex açılır (tasarım §2.3).
Tek-instance güvencesi ondan GELMEZ — o yalnız Inno Setup'ın `AppMutex`
denetimine "program açık" sinyalidir: mutex olmadan kurucu, çalışan programın
`_internal/` ağacını üzerine yazmaya çalışırdı (DD iskeletinde bu sinyal hiç
üretilmiyordu; iss'teki denetim ölüydü).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import TracebackType
from typing import BinaryIO

from desktop.errors import AlreadyRunningError

#: Inno `AppMutex` ile birebir aynı olmak ZORUNDA (packaging/windows/kelebek-sinav.iss).
APP_MUTEX_NAME = "KelebekSinav"

_MESSAGE = "Kelebek Sınav zaten çalışıyor. Aynı anda yalnızca bir kopya açılabilir."
_HINT = (
    "Açık olan pencereyi kullanın. Pencere görünmüyorsa oturumu kapatıp açın veya "
    "görev yöneticisinden programı sonlandırın."
)


def _apply_exclusive_lock(handle: BinaryIO) -> None:
    """Dosyaya bloklamayan paylaşımsız kilit koyar; alınamazsa OSError yükseltir."""
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release_lock(handle: BinaryIO) -> None:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class SingleInstanceLock:
    """Kilit dosyası üzerinden tek-instance güvencesi (context manager)."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._handle: BinaryIO | None = None
        self._mutex_handle: int | None = None

    @property
    def path(self) -> Path:
        return self._path

    @property
    def handle(self) -> BinaryIO | None:
        """Kilit alınmışsa açık dosya tanıtıcısı, aksi halde None (test/teşhis)."""
        return self._handle

    def acquire(self) -> None:
        """Kilidi alır; başka bir kopya çalışıyorsa `AlreadyRunningError` yükseltir."""
        if self._handle is not None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # "a+b": yoksa oluşturur, varsa içeriğini korur (dosyaya bir şey yazmıyoruz —
        # kilit dosyanın kendisinde, içeriğinde değil; PID dosyası bayatlayabilirdi).
        handle: BinaryIO = self._path.open("a+b")
        try:
            _apply_exclusive_lock(handle)
        except OSError as exc:
            handle.close()
            raise AlreadyRunningError(_MESSAGE, hint=_HINT) from exc
        self._handle = handle
        self._mutex_handle = self._create_app_mutex()

    @staticmethod
    def _create_app_mutex() -> int | None:
        """Windows'ta kurucuya görünen adlandırılmış mutex'i açar (yalnız sinyal).

        Başarısızlık açılışı DURDURMAZ: tek-instance güvencesi dosya kilidinde;
        mutex yalnız Inno'nun "program açıkken yükseltme yapma" denetimi içindir.
        """
        if sys.platform != "win32":
            return None
        try:
            import ctypes

            handle = int(ctypes.windll.kernel32.CreateMutexW(None, False, APP_MUTEX_NAME))
            return handle or None
        except (OSError, AttributeError):
            return None

    @staticmethod
    def _close_app_mutex(handle: int) -> None:
        if sys.platform != "win32":
            return
        import ctypes

        ctypes.windll.kernel32.CloseHandle(handle)

    def release(self) -> None:
        """Kilidi bırakır. Kilit alınmamışsa sessizce döner."""
        mutex = self._mutex_handle
        self._mutex_handle = None
        if mutex is not None:
            self._close_app_mutex(mutex)
        handle = self._handle
        if handle is None:
            return
        self._handle = None
        try:
            _release_lock(handle)
        except OSError:
            # Kilit zaten düşmüşse (dosya silinmiş vb.) kapatmak yeterli.
            pass
        finally:
            handle.close()

    def __enter__(self) -> SingleInstanceLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()
