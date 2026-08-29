"""Tek-instance kilidi (tasarım §5.3).

İki kopya aynı SQLite dosyasına yazarsa WAL kilitleri yüzünden kullanıcı
"veritabanı kilitli" hatalarıyla karşılaşır; daha kötüsü iki pencere aynı dosya
üzerinde farklı işlem yapar. Bu yüzden ikinci kopya **pencere açmadan** Türkçe
mesajla çıkar.

Yöntem işletim sistemine göre değişir ama sözleşme aynıdır: bir dosya açılır ve
üzerine paylaşımsız kilit konur. Kilit süreç ölünce (çökme dahil) işletim sistemi
tarafından bırakılır — bayat PID dosyası sorunu yaşanmaz.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import TracebackType
from typing import BinaryIO

from desktop.errors import AlreadyRunningError

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

    def release(self) -> None:
        """Kilidi bırakır. Kilit alınmamışsa sessizce döner."""
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
