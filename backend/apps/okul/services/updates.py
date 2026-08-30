"""GitHub Release tabanlı uygulama güncelleme denetimi ve güvenli kurucu indirme.

Yalnız sabit proje deposunun ``latest release`` kaydı okunur. Windows kurucusu,
GitHub'ın ``sha256:...`` varlık özetiyle; eski Release kayıtlarında bu alan yoksa
aynı Release'teki ``SHA256SUMS.txt`` ile doğrulanmadan kullanıcıya verilmez.

Çevrimdışı ilke (tasarım §1) korunur: denetim yalnız FE'den gelen istekle koşar,
açılış zincirine girmez; ağ yoksa Türkçe hata döner, banner sessizce yutar.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

GITHUB_REPOSITORY = os.environ.get("KS_UPDATE_REPOSITORY", "aalidemirci/kelebek-sinav").strip()
GITHUB_API_VERSION = "2026-03-10"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
USER_AGENT = "Kelebek-Sinav-Updater"
INSTALLER_PATTERN = re.compile(r"^kelebek-sinav-.+-win64-setup\.exe$", re.IGNORECASE)
MAX_INSTALLER_BYTES = 250 * 1024 * 1024
CACHE_SECONDS = 15 * 60

_cache_lock = threading.Lock()
_cached_release: tuple[float, ReleaseInfo] | None = None


class UpdateError(RuntimeError):
    """Kullanıcıya güvenle gösterilebilen güncelleme hatası."""


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    download_url: str
    size: int
    digest: str


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    tag_name: str
    name: str
    published_at: str
    html_url: str
    installer: ReleaseAsset | None
    checksums: ReleaseAsset | None


def _resource_root() -> Path:
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(str(bundle))
    return Path(__file__).resolve().parents[4]


def get_app_version() -> str:
    """Masaüstü paketi ve bağımsız Django geliştirme ortamında sürümü okur."""
    override = os.environ.get("KS_APP_VERSION")
    if override:
        return override.strip()
    try:
        return (_resource_root() / "VERSION").read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


def version_key(value: str) -> tuple[tuple[int, ...], int, str]:
    """`desktop.version` ile aynı, ön sürümleri kararlı sürümden küçük sayan anahtar."""
    head, _, pre = value.strip().partition("-")
    numbers: list[int] = []
    for part in head.split("."):
        match = re.match(r"^\d+", part.strip())
        numbers.append(int(match.group(0)) if match else 0)
    numbers += [0] * (4 - len(numbers))
    return (tuple(numbers[:4]), 0 if pre else 1, pre)


def update_directory() -> Path:
    """Kurucular için masaüstü uygulamasıyla aynı kullanıcı önbelleğini çözer."""
    override = os.environ.get("KS_APP_HOME")
    if override:
        return Path(override) / "cache" / "updates"
    if sys.platform.startswith("win"):
        home = Path(os.environ.get("USERPROFILE") or Path.home())
        local = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
        return local / "KelebekSinav" / "cache" / "updates"
    home = Path(os.environ.get("HOME") or Path.home())
    cache = Path(os.environ.get("XDG_CACHE_HOME") or home / ".cache")
    return cache / "kelebek-sinav" / "updates"


def _request(url: str) -> Request:
    return Request(  # noqa: S310 — çağıran yalnız HTTPS GitHub adreslerini kabul eder
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": USER_AGENT,
        },
    )


def _read_url(url: str, *, max_bytes: int) -> bytes:
    try:
        with urlopen(_request(url), timeout=20) as response:  # noqa: S310 — URL aşağıda sabitlenir
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(min(1024 * 1024, max_bytes + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise UpdateError("Güncelleme dosyası beklenen boyut sınırını aşıyor.")
                chunks.append(chunk)
            return b"".join(chunks)
    except HTTPError as exc:
        if exc.code == 404:
            raise UpdateError("GitHub'da henüz yayımlanmış bir sürüm bulunmuyor.") from exc
        if exc.code in {403, 429}:
            raise UpdateError(
                "GitHub güncelleme denetimi geçici olarak sınırlandı; daha sonra yeniden deneyin."
            ) from exc
        raise UpdateError(f"GitHub güncelleme sunucusu HTTP {exc.code} hatası verdi.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise UpdateError(
            "Güncelleme sunucusuna ulaşılamadı. İnternet bağlantısını kontrol edin."
        ) from exc


def _safe_release_url(value: Any) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "api.github.com"}:
        return ""
    return url


def _asset_from_json(value: Any) -> ReleaseAsset | None:
    if not isinstance(value, dict):
        return None
    name = str(value.get("name") or "").strip()
    # DD'den sapma (güvenlik sertleştirmesi): ad dosya yoluna çevrildiği için
    # yol bileşeni taşıyan varlık reddedilir — önbellek dizini dışına yazılamaz.
    if "/" in name or "\\" in name or ".." in name:
        return None
    url = _safe_release_url(value.get("browser_download_url"))
    if not name or not url:
        return None
    try:
        size = max(0, int(value.get("size") or 0))
    except (TypeError, ValueError):
        size = 0
    return ReleaseAsset(
        name=name,
        download_url=url,
        size=size,
        digest=str(value.get("digest") or "").strip().lower(),
    )


def _parse_release(payload: Any) -> ReleaseInfo:
    if not isinstance(payload, dict):
        raise UpdateError("GitHub sürüm yanıtı beklenen biçimde değil.")
    tag_name = str(payload.get("tag_name") or "").strip()
    version = tag_name.removeprefix("v").strip()
    if not version:
        raise UpdateError("GitHub sürüm kaydında sürüm etiketi bulunmuyor.")

    assets = [asset for raw in payload.get("assets") or [] if (asset := _asset_from_json(raw))]
    installer = next((a for a in assets if INSTALLER_PATTERN.fullmatch(a.name)), None)
    checksums = next((a for a in assets if a.name.upper() == "SHA256SUMS.TXT"), None)
    return ReleaseInfo(
        version=version,
        tag_name=tag_name,
        name=str(payload.get("name") or tag_name),
        published_at=str(payload.get("published_at") or ""),
        html_url=_safe_release_url(payload.get("html_url")),
        installer=installer,
        checksums=checksums,
    )


def latest_release(*, force: bool = False) -> ReleaseInfo:
    global _cached_release

    now = time.monotonic()
    with _cache_lock:
        if not force and _cached_release and now - _cached_release[0] < CACHE_SECONDS:
            return _cached_release[1]

    raw = _read_url(LATEST_RELEASE_URL, max_bytes=2 * 1024 * 1024)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateError("GitHub sürüm yanıtı okunamadı.") from exc
    release = _parse_release(payload)
    with _cache_lock:
        _cached_release = (now, release)
    return release


def update_status(*, force: bool = False, current_version: str | None = None) -> dict[str, Any]:
    current = current_version or get_app_version()
    release = latest_release(force=force)
    available = version_key(release.version) > version_key(current)
    return {
        "current_version": current,
        "latest_version": release.version,
        "update_available": available,
        "release_name": release.name,
        "published_at": release.published_at,
        "release_url": release.html_url,
        "can_download": available and release.installer is not None,
        "installer_name": release.installer.name if release.installer else "",
        "installer_size": release.installer.size if release.installer else 0,
    }


def _expected_digest(release: ReleaseInfo) -> str:
    installer = release.installer
    if installer is None:
        raise UpdateError("Bu sürümde Windows kurulum dosyası bulunmuyor.")
    if installer.digest.startswith("sha256:"):
        digest = installer.digest.removeprefix("sha256:")
        if re.fullmatch(r"[0-9a-f]{64}", digest):
            return digest
    if release.checksums is None:
        raise UpdateError("Kurulum dosyasının SHA-256 doğrulama özeti bulunmuyor.")
    checksum_text = _read_url(release.checksums.download_url, max_bytes=256 * 1024).decode(
        "utf-8", errors="replace"
    )
    for line in checksum_text.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2:
            continue
        digest, filename = parts
        if filename.lstrip("*") == installer.name and re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            return digest.lower()
    raise UpdateError("SHA256SUMS.txt içinde Windows kurulum dosyası bulunmuyor.")


def download_latest_installer(*, force: bool = False) -> Path:
    release = latest_release(force=force)
    current = get_app_version()
    if version_key(release.version) <= version_key(current):
        raise UpdateError("Uygulama zaten güncel; indirilecek daha yeni bir sürüm yok.")
    installer = release.installer
    if installer is None:
        raise UpdateError("Yeni sürümde Windows kurulum dosyası bulunmuyor.")
    if installer.size > MAX_INSTALLER_BYTES:
        raise UpdateError("Kurulum dosyası güvenli boyut sınırını aşıyor.")

    expected = _expected_digest(release)
    content = _read_url(installer.download_url, max_bytes=MAX_INSTALLER_BYTES)
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected:
        raise UpdateError("İndirilen kurulum dosyasının SHA-256 doğrulaması başarısız.")

    update_dir = update_directory()
    update_dir.mkdir(parents=True, exist_ok=True)
    target = update_dir / installer.name
    temporary = target.with_suffix(target.suffix + ".part")
    temporary.write_bytes(content)
    temporary.replace(target)
    return target
