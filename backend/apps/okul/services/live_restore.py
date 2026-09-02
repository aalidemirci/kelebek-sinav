"""Çalışan program içinden yedekten geri yükleme (Güvenlik sekmesi — API ayağı).

Dosya değişimini `backup_restore` çekirdeği yapar; bu modül ÇALIŞAN sunucuya
özgü tesisatı ekler ve view'a tek kapı sunar:

* yedek listesi — `app_password.backup_dir()` içindeki `.ksbak` dosyaları
  (masaüstü `desktop/restore.py::list_backups` ile aynı kaynak, en yeniden
  eskiye);
* kullanıcının YÜKLEDİĞİ dosyanın geçici yazımı (çekirdek yol ister) — KVKK:
  geçici dosya işlem sonunda her durumda silinir, kullanıcının elindeki asıl
  dosya zaten kendindedir;
* takas öncesi Django bağlantılarının kapatılması — Windows'ta SQLite dosyayı
  FILE_SHARE_DELETE olmadan açar; açık bağlantı varken `os.replace` erişim
  hatasıyla düşer (Linux'ta düşmez ama bağlantı eski dosyada asılı kalırdı);
* başarıda anahtarın bellekten düşürülmesi + "yeniden başlat" kapısının
  kurulması (`restart_gate`): bellekteki DEK ve süreç durumu geri yüklenen
  veriye ait değildir, bekleyen göçler ancak açılışta koşar — sunucu bu
  hâliyle çalışmaya devam EDEMEZ.

Masaüstü kardeşi `desktop/restore.py` bozuk-veritabanı senaryosudur (pencere
hiç açılmadan `--geri-yukle`); bu modül programın AÇILABİLDİĞİ senaryo içindir
(yanlış veri girişi sonrası eski güne dönme). Parola/kurtarma anahtarı yalnız
parametre olarak akar; hiçbir günlük satırına ve hata metnine yazılmaz.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from desktop.backup_crypto import BACKUP_SUFFIX, MAGIC
from django.conf import settings
from django.db import connections
from django.utils import timezone

from apps.okul import restart_gate
from apps.okul.services import app_password, backup_restore

logger = logging.getLogger("kelebek_sinav.restore")


class LiveRestoreError(ValueError):
    """Kullanıcıya gösterilecek Türkçe hata (view katmanı 400'e çevirir)."""


def list_backups() -> dict[str, Any]:
    """Yedek klasöründeki geri yüklenebilir `.ksbak` dosyaları (en yeniden eskiye).

    `backup_dir` yanıtta bilinçli olarak vardır: kullanıcı elle aldığı bir
    yedeği nereye koyacağını ya da dosyaların nerede durduğunu buradan görür
    (tek kullanıcılı yerel program — yol kişisel veri değildir).
    """
    dizin = app_password.backup_dir()
    satirlar: list[dict[str, Any]] = []
    if dizin.is_dir():
        for yol in dizin.glob(f"*{BACKUP_SUFFIX}"):
            if not yol.is_file():
                continue
            bilgi = yol.stat()
            satirlar.append(
                {
                    "name": yol.name,
                    "size": bilgi.st_size,
                    "modified_at": timezone.localtime(
                        datetime.fromtimestamp(bilgi.st_mtime, tz=UTC)
                    ).isoformat(),
                    "encrypted": _is_encrypted(yol),
                    "_mtime": bilgi.st_mtime,
                }
            )
    satirlar.sort(key=lambda satir: float(satir["_mtime"]), reverse=True)
    for satir in satirlar:
        del satir["_mtime"]
    return {"backup_dir": str(dizin), "backups": satirlar}


def restore_and_require_restart(
    *,
    name: str = "",
    content: bytes | None = None,
    password: str = "",
    recovery_key: str = "",
) -> dict[str, Any]:
    """Yedeği veritabanının yerine koyar ve süreci "yeniden başlat" kapısına alır.

    Kaynak ikisinden biridir: `name` (yedek klasöründen) YA DA `content`
    (kullanıcının yüklediği dosyanın baytları). Hata hâlinde hedefe dokunulmaz
    (çekirdek garantisi) ve kapı KURULMAZ — kullanıcı yeniden dener.
    """
    hedef = _database_path()
    gecici: Path | None = None
    if content is not None:
        dizin = app_password.backup_dir()
        dizin.mkdir(parents=True, exist_ok=True)
        # `.ksbak` uzantısı BİLEREK verilmez: rotasyon/listeleme yalnız o
        # uzantıya bakar, yarım kalan bir geçici dosya yedek sanılmamalı.
        gecici = dizin / f".yukleme-{uuid4().hex}.tmp"
        gecici.write_bytes(content)
        kaynak = gecici
    else:
        kaynak = _resolve_named(name)
    try:
        # Takas öncesi TÜM bağlantılar kapatılır; sonraki istekler zaten
        # restart_gate'e takılacağından yeniden açılmaları sorun olmaz.
        connections.close_all()
        sonuc = backup_restore.restore_database(
            kaynak,
            hedef,
            password=password or None,
            recovery_key=recovery_key or None,
        )
    finally:
        if gecici is not None:
            gecici.unlink(missing_ok=True)
    # Bellekteki DEK eski veritabanına aittir; düşürülür. Kapı kurulunca kilit
    # ekranı dahil tüm API kesilir — tek çıkış programı kapatıp yeniden açmaktır.
    app_password.lock()
    restart_gate.mark_restart_required()
    logger.info(
        "API'den geri yükleme uygulandı: %s (%s kip); yeniden başlatma bekleniyor.",
        kaynak.name if content is None else "yüklenen dosya",
        "şifreli" if sonuc.encrypted else "düz",
    )
    return {
        "encrypted": sonuc.encrypted,
        "old_db_name": sonuc.old_db_path.name if sonuc.old_db_path is not None else "",
        "state_written": sonuc.state_written,
        "restart_required": True,
    }


# ---------------------------------------------------------------------------
# İç yardımcılar
# ---------------------------------------------------------------------------
def _is_encrypted(path: Path) -> bool:
    try:
        with path.open("rb") as dosya:
            # bool(): desktop.* backend mypy koşusunda Any çözümlenir (test_backup_restore notu).
            return bool(dosya.read(len(MAGIC)) == MAGIC)
    except OSError:
        return False


def _resolve_named(name: str) -> Path:
    """Yedek klasöründeki adı yola çevirir; klasör dışına çıkışı reddeder."""
    duz_ad = name.strip()
    if (
        not duz_ad
        or not duz_ad.endswith(BACKUP_SUFFIX)
        # Yol ayracı denetimi platformdan bağımsız elle yapılır: testler
        # Linux'ta koşar, hedef makine Windows'tur; ikisinde de ".." ve
        # ayraçlı adlar klasör dışına işaret edebilir.
        or "/" in duz_ad
        or "\\" in duz_ad
        or duz_ad != Path(duz_ad).name
    ):
        raise LiveRestoreError(f"Geçerli bir yedek dosyası adı verin ({BACKUP_SUFFIX}).")
    yol = app_password.backup_dir() / duz_ad
    if not yol.is_file():
        raise LiveRestoreError(f"Yedek klasöründe böyle bir dosya yok: {duz_ad}")
    return yol


def _database_path() -> Path:
    """Hedef dosyanın yolu — bağlantı AÇILMAZ (restore_backup komutuyla aynı kural)."""
    ad = str(settings.DATABASES["default"].get("NAME") or "")
    if not ad or ad == ":memory:" or "mode=memory" in ad:
        raise LiveRestoreError("Veritabanı dosya tabanlı değil; geri yükleme uygulanamaz.")
    return Path(ad)
