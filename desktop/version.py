"""Uygulama sürümü + veri sürüm damgası (tasarım §5.3 "eski exe yeni DB'yi AÇMAZ").

**Karar — damga TABLO değil DOSYA:** veri dizinindeki `surum.json`.
Gerekçe: (1) veritabanı açılamadığında/bozukken bile okunabilir, yani sürüm
denetimi bütünlük denetiminden önce koşabilir; (2) yeni bir tablo eklemek için
migration gerekmez ve Django'nun şema karşılaştırmasına gölge düşürmez;
(3) yedekten geri dönüşte damga eksik/eski kalırsa program yine de açılır
(eksik damga engel sayılmaz) — kullanıcıyı kilitlemeyen tarafta hata yapar.

Damga her başarılı `migrate` sonrası yazılır. Damgadaki sürüm çalışan programdan
YENİYSE program açılmaz: eski sürüm, yeni şemayı tanımadığı için veriyi bozardı.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from desktop.errors import SchemaTooNewError
from desktop.paths import resource_root

ENV_APP_VERSION = "KS_APP_VERSION"
VERSION_FILE_NAME = "VERSION"
FALLBACK_VERSION = "0.0.0"

logger = logging.getLogger("kelebek_sinav.version")

_LEADING_DIGITS = re.compile(r"^\d+")


@dataclass(frozen=True)
class VersionStamp:
    """Veriyi en son yazan program sürümünün damgası."""

    app_version: str
    written_at: str


def get_app_version(*, environ: Mapping[str, str] | None = None) -> str:
    """Çalışan programın sürümü — `KS_APP_VERSION` > paketlenmiş `VERSION` dosyası."""
    env = os.environ if environ is None else environ
    override = env.get(ENV_APP_VERSION)
    if override:
        return override.strip()
    version_file = resource_root() / VERSION_FILE_NAME
    try:
        text = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        logger.warning("Sürüm dosyası okunamadı; %s varsayılıyor.", FALLBACK_VERSION)
        return FALLBACK_VERSION
    return text or FALLBACK_VERSION


def version_key(value: str) -> tuple[tuple[int, ...], int, str]:
    """Sürümü karşılaştırılabilir anahtara çevirir ("1.0.0-dev" < "1.0.0")."""
    head, _, pre = value.strip().partition("-")
    numbers: list[int] = []
    for part in head.split("."):
        match = _LEADING_DIGITS.match(part.strip())
        numbers.append(int(match.group(0)) if match else 0)
    numbers += [0] * (4 - len(numbers))
    # Ön-sürüm (-dev/-rc1) kesin sürümden ÖNCE gelir → 0, kesin sürüm → 1.
    return (tuple(numbers[:4]), 0 if pre else 1, pre)


def read_version_stamp(path: Path) -> VersionStamp | None:
    """Damgayı okur. Dosya yoksa veya bozuksa None (program kilitlenmez)."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    app_version = str(raw.get("app_version") or "").strip()
    if not app_version:
        return None
    return VersionStamp(app_version=app_version, written_at=str(raw.get("written_at") or ""))


def write_version_stamp(path: Path, app_version: str) -> None:
    """Damgayı yazar (başarılı `migrate` sonrası çağrılır)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "app_version": app_version,
        "written_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_stamp_compatible(path: Path, app_version: str) -> None:
    """Veri, çalışan programdan yeni bir sürümle yazılmışsa açılışı durdurur."""
    stamp = read_version_stamp(path)
    if stamp is None:
        return
    if version_key(stamp.app_version) > version_key(app_version):
        raise SchemaTooNewError(
            "Bu veri, programın daha yeni bir sürümüyle "
            f"({stamp.app_version}) oluşturulmuş. Çalışan sürüm: {app_version}.",
            hint=(
                "Veriyi bozmamak için program açılmadı. Bu bilgisayardaki programı "
                "güncel sürüme yükseltip yeniden açın."
            ),
        )
