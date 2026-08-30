"""GitHub Release tabanlı güncelleme servisinin ağsız birim testleri (F8).

DD `test_updates.py`'den KS'ye uyarlandı: ürün/depo adları değişti, akış aynı.
Ağ hiç kullanılmaz — `latest_release`/`_read_url` monkeypatch'lenir.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.okul.services import updates


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _release(
    *, digest: str = "", checksums: updates.ReleaseAsset | None = None
) -> updates.ReleaseInfo:
    installer = updates.ReleaseAsset(
        name="kelebek-sinav-2026.10.0-win64-setup.exe",
        download_url="https://github.com/aalidemirci/kelebek-sinav/releases/download/v2026.10.0/kelebek-sinav-2026.10.0-win64-setup.exe",
        size=8,
        digest=digest,
    )
    return updates.ReleaseInfo(
        version="2026.10.0",
        tag_name="v2026.10.0",
        name="Kelebek Sınav 2026.10.0",
        published_at="2026-10-01T12:00:00Z",
        html_url="https://github.com/aalidemirci/kelebek-sinav/releases/tag/v2026.10.0",
        installer=installer,
        checksums=checksums,
    )


def test_release_yaniti_windows_kurucusunu_ve_ozeti_cozer() -> None:
    release = updates._parse_release(  # noqa: SLF001
        {
            "tag_name": "v2026.10.0",
            "name": "Ekim sürümü",
            "html_url": "https://github.com/aalidemirci/kelebek-sinav/releases/tag/v2026.10.0",
            "assets": [
                {
                    "name": "kelebek-sinav-2026.10.0-win64-setup.exe",
                    "browser_download_url": "https://github.com/aalidemirci/kelebek-sinav/releases/download/v2026.10.0/setup.exe",
                    "size": 1234,
                    "digest": f"sha256:{'a' * 64}",
                },
                {
                    "name": "SHA256SUMS.txt",
                    "browser_download_url": "https://github.com/aalidemirci/kelebek-sinav/releases/download/v2026.10.0/SHA256SUMS.txt",
                    "size": 100,
                },
            ],
        }
    )

    assert release.version == "2026.10.0"
    assert release.installer is not None
    assert release.installer.size == 1234
    assert release.checksums is not None


def test_yol_bilesenli_varlik_adi_reddedilir() -> None:
    """Ad dosya yoluna çevrilir; `..`/ayırıcı taşıyan varlık önbellek dizini
    dışına yazamamalı (DD'den bilinçli sapma — güvenlik sertleştirmesi)."""
    release = updates._parse_release(  # noqa: SLF001
        {
            "tag_name": "v2026.10.0",
            "assets": [
                {
                    "name": "kelebek-sinav-/../../ele-gecir-win64-setup.exe",
                    "browser_download_url": "https://github.com/aalidemirci/kelebek-sinav/releases/download/v2026.10.0/setup.exe",
                }
            ],
        }
    )

    assert release.installer is None


def test_guvenilmeyen_varlik_adresi_kabul_edilmez() -> None:
    release = updates._parse_release(  # noqa: SLF001
        {
            "tag_name": "v2026.10.0",
            "assets": [
                {
                    "name": "kelebek-sinav-2026.10.0-win64-setup.exe",
                    "browser_download_url": "https://example.org/zararli.exe",
                }
            ],
        }
    )

    assert release.installer is None


def test_kararli_surum_yokken_on_surum_listeden_secilir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Beta dönemi: `releases/latest` 404 verir (yalnız --prerelease yayın var);
    liste okunur, taslaklar elenir, en yüksek sürüm seçilir (F9 bulgusu)."""

    def sahte_read_url(url: str, *, max_bytes: int) -> bytes:
        if url == updates.LATEST_RELEASE_URL:
            raise updates.ReleaseNotFoundError("GitHub'da henüz yayımlanmış bir sürüm bulunmuyor.")
        assert url == updates.RELEASE_LIST_URL
        return json.dumps(
            [
                {"tag_name": "v2026.10.0-beta.1", "assets": []},
                {"tag_name": "v2026.10.0-beta.2", "assets": []},
                {"tag_name": "v2026.11.0", "draft": True, "assets": []},  # taslak elenir
            ]
        ).encode("utf-8")

    monkeypatch.setattr(updates, "_read_url", sahte_read_url)

    release = updates.latest_release(force=True)

    assert release.version == "2026.10.0-beta.2"


def test_guncelleme_durumu_surumu_karsilastirir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updates, "latest_release", lambda **_kwargs: _release())

    status = updates.update_status(current_version="2026.9.0")

    assert status["update_available"] is True
    assert status["can_download"] is True
    assert status["latest_version"] == "2026.10.0"


def test_kurucu_sha256_dogrulanarak_onbellege_yazilir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    content = b"kurulum"
    release = _release(digest=f"sha256:{hashlib.sha256(content).hexdigest()}")
    monkeypatch.setattr(updates, "latest_release", lambda **_kwargs: release)
    monkeypatch.setattr(updates, "get_app_version", lambda: "2026.9.0")
    monkeypatch.setattr(updates, "_read_url", lambda *_args, **_kwargs: content)
    monkeypatch.setattr(updates, "update_directory", lambda: tmp_path / "updates")

    target = updates.download_latest_installer()

    assert target.read_bytes() == content
    assert target.parent == tmp_path / "updates"
    assert not target.with_suffix(target.suffix + ".part").exists()


def test_kurucu_ozeti_tutmazsa_dosya_yazilmaz(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    release = _release(digest=f"sha256:{'0' * 64}")
    monkeypatch.setattr(updates, "latest_release", lambda **_kwargs: release)
    monkeypatch.setattr(updates, "get_app_version", lambda: "2026.9.0")
    monkeypatch.setattr(updates, "_read_url", lambda *_args, **_kwargs: b"farkli")
    monkeypatch.setattr(updates, "update_directory", lambda: tmp_path / "updates")

    with pytest.raises(updates.UpdateError, match="SHA-256"):
        updates.download_latest_installer()

    assert not (tmp_path / "updates").exists()


@pytest.mark.django_db
def test_guncelleme_api_durumu_dondurur(
    client: APIClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected: dict[str, Any] = {
        "current_version": "2026.9.0",
        "latest_version": "2026.10.0",
        "update_available": True,
        "release_name": "Yeni sürüm",
        "published_at": "",
        "release_url": "",
        "can_download": True,
        "installer_name": "setup.exe",
        "installer_size": 42,
    }
    monkeypatch.setattr(updates, "update_status", lambda **_kwargs: expected)

    response = client.get("/api/v1/updates/latest/")

    assert response.status_code == 200
    assert response.json() == expected
