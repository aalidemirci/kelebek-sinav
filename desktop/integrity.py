"""Açılışta SQLite bütünlük denetimi (tasarım §5.3).

Bozuk bir veritabanıyla pencere AÇILMAZ: kullanıcı bozuk veri üzerinde çalışıp
kaydettikçe hasar büyür ve elindeki sağlam yedekler rotasyonla eskir. Bunun
yerine program durur ve "son yedekten dön" yolunu gösterir.

`PRAGMA integrity_check(1)` kullanılır: tam denetimin hızlı biçimi (ilk hatada
durur). Açılışa saniyeler eklememesi için tam tarama yerine bu seçildi; okulun
tek makinesinde veritabanı zaten küçüktür (≤1000 öğrenci).
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from desktop.errors import DatabaseCorruptError

logger = logging.getLogger("kelebek_sinav.integrity")

_MESSAGE = "Veri dosyası bozuk görünüyor; program veriyi korumak için açılmadı."


def _hint(backup_dir: Path | None) -> str:
    if backup_dir is None:
        return (
            "Son sağlam yedeği veri klasöründeki yedekler dizininden geri yükleyin "
            "(yedek dosyasını db.sqlite3 adıyla veri dizinine kopyalayın)."
        )
    return (
        f"Yedek klasörü: {backup_dir}\n"
        "En son tarihli yedeği veri klasörüne 'db.sqlite3' adıyla kopyalayıp programı "
        "yeniden açın. Bozuk dosyayı silmeyin; bir kopyasını saklayın."
    )


def check_database_integrity(db_path: Path, *, backup_dir: Path | None = None) -> None:
    """Veritabanını hızlı bütünlük denetiminden geçirir; bozuksa hata yükseltir.

    Dosya henüz yoksa sessizce döner — ilk açılışta `migrate` onu oluşturacaktır.
    """
    if not db_path.exists():
        return
    try:
        with closing(sqlite3.connect(db_path)) as connection:
            rows = connection.execute("PRAGMA integrity_check(1)").fetchall()
    except sqlite3.DatabaseError as exc:
        # "file is not a database" / "database disk image is malformed" — dosya okunamıyor.
        logger.error("Bütünlük denetimi açılamadı: %s", exc.__class__.__name__)
        raise DatabaseCorruptError(_MESSAGE, hint=_hint(backup_dir)) from exc

    result = str(rows[0][0]) if rows else ""
    if result != "ok":
        logger.error("Bütünlük denetimi başarısız.")
        raise DatabaseCorruptError(_MESSAGE, hint=_hint(backup_dir))
