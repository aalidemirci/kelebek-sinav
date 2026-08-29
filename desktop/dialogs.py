"""Açılış hatalarını kullanıcıya gösterme.

Program pencere açmadan durduğunda (bozuk veritabanı, ikinci kopya, başarısız
migrate) kullanıcıya ulaşacak tek yol işletim sisteminin ileti kutusudur:
masaüstü kısayolundan başlatılan bir GUI programının konsolu yoktur, `stderr`
kimseye görünmez.

Sıra: **önce günlüğe yaz**, sonra ileti kutusunu dene. Diyalog hiçbir koşulda
hata yükseltmez — hata gösterirken patlamak en kötü sonuçtur.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from collections.abc import Callable

logger = logging.getLogger("kelebek_sinav.dialogs")

DialogRunner = Callable[[list[str]], bool]

# Windows MessageBox bayrakları: MB_OK | MB_ICONERROR | MB_SETFOREGROUND
_MB_FLAGS = 0x00000000 | 0x00000010 | 0x00010000


def _show_windows_message_box(title: str, message: str) -> bool:
    """Windows yerel ileti kutusu (user32.MessageBoxW)."""
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, title, _MB_FLAGS)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — ileti gösterimi asla akışı bozmamalı
        return False
    return True


def _run_dialog_command(argv: list[str]) -> bool:
    """Linux'ta zenity/kdialog ile ileti gösterir; ikisi de yoksa False."""
    executable = shutil.which(argv[0])
    if executable is None:
        return False
    try:
        subprocess.run(  # noqa: S603 — argümanlar sabit; kullanıcı girdisi kabuğa gitmez
            [executable, *argv[1:]],
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def show_error(
    title: str,
    message: str,
    *,
    platform: str | None = None,
    runner: DialogRunner | None = None,
) -> None:
    """Hatayı günlüğe yazar ve mümkünse görsel ileti kutusunda gösterir."""
    logger.error("%s — %s", title, message)

    system = sys.platform if platform is None else platform
    if system.startswith("win"):
        if _show_windows_message_box(title, message):
            return

    run = runner or _run_dialog_command
    for argv in (
        ["zenity", "--error", f"--title={title}", f"--text={message}"],
        ["kdialog", "--error", message, "--title", title],
    ):
        try:
            if run(argv):
                return
        except Exception:  # noqa: BLE001 — ileti gösterimi asla akışı bozmamalı
            logger.warning("Görsel ileti gösterilemedi (%s).", argv[0])
    # Görsel ileti gösterilemedi: günlük dosyası tek iz olarak kalır.
