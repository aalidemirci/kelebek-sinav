"""GitHub Release tabanlı güncelleme servisinin ağsız birim testleri (F8).

DD `test_updates.py`'den KS'ye uyarlandı: ürün/depo adları değişti, akış aynı.
Ağ hiç kullanılmaz — `latest_release`/`_read_url` monkeypatch'lenir; ağ katmanının
kendisi (`_read_url`) sınanırken de `urlopen` sahtelenir.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import time
from collections.abc import Iterable
from email.message import Message
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest
from desktop.paths import resolve_app_paths
from django.http import StreamingHttpResponse
from rest_framework.test import APIClient

from apps.okul.services import updates


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture(autouse=True)
def _surum_onbellegi_yalitilir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sürüm önbelleği modül düzeyinde yaşar (15 dk): her test boş önbellekle başlar ve
    sahte sürüm sonraki teste sızmaz — testler koşu sırasından bağımsız kalır."""
    monkeypatch.setattr(updates, "_cached_release", None)


@pytest.fixture(autouse=True)
def _windows_platformu(monkeypatch: pytest.MonkeyPatch) -> None:
    """Uygulama içi indirme yalnız Windows'ta açıktır; testler Linux kabında koşar.

    Akış testleri Windows'u varsayar; Pardus davranışını sınayan testler bu
    değeri kendileri `False`'a çevirir.
    """
    monkeypatch.setattr(updates, "installer_supported", lambda: True)


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


def test_pardusta_windows_kurulum_dosyasi_onerilmez(
    monkeypatch: pytest.MonkeyPatch, client: APIClient
) -> None:
    """Pardus/Linux'ta "Doğrula ve indir" Windows `setup.exe`'sini öneriyordu.

    Güncelleme orada paketle (.deb/.tar.gz) yapılır: durum `platform: linux` ve
    `can_download: false` döner, kurulum dosyası adı/boyutu BOŞTUR; indirme ucu
    da (arayüz atlansa bile) anlaşılır Türkçe ret verir.
    """
    monkeypatch.setattr(updates, "installer_supported", lambda: False)
    monkeypatch.setattr(updates, "latest_release", lambda *, force=False: _release())

    durum = updates.update_status(current_version="2026.9.0")
    assert durum["update_available"] is True
    assert (durum["platform"], durum["can_download"]) == ("linux", False)
    assert (durum["installer_name"], durum["installer_size"]) == ("", 0)

    with pytest.raises(updates.UpdateError, match="yalnız Windows"):
        updates.download_latest_installer()


def test_windowsta_platform_alani_ve_indirme_acik(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updates, "latest_release", lambda *, force=False: _release())

    durum = updates.update_status(current_version="2026.9.0")

    assert (durum["platform"], durum["can_download"]) == ("windows", True)
    assert durum["installer_name"].endswith("-win64-setup.exe")


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


# ===========================================================================
# Ağ katmanı (`_read_url`) — `urlopen` sahtelenir, gerçek ağ HİÇ kullanılmaz
# ===========================================================================


class _SahteYanit:
    """`urlopen` dönüşünün yerine geçen, parça parça okunan bağlam yöneticisi."""

    def __init__(self, govde: bytes) -> None:
        self._akis = io.BytesIO(govde)

    def __enter__(self) -> _SahteYanit:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def read(self, boyut: int = -1) -> bytes:
        return self._akis.read(boyut)


def _http_hatasi(kod: int) -> HTTPError:
    return HTTPError(updates.LATEST_RELEASE_URL, kod, "hata", Message(), None)


def test_ag_istegi_github_basliklariyla_ve_zaman_asimiyla_gider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GitHub API'si User-Agent'sız isteği 403'ler; zaman aşımı olmazsa ağsız okulda
    güncelleme denetimi arayüzü süresiz bekletirdi."""
    gorulen: dict[str, Any] = {}

    def sahte_urlopen(istek: Request, timeout: float) -> _SahteYanit:
        gorulen["istek"] = istek
        gorulen["timeout"] = timeout
        return _SahteYanit(b'{"tag_name": "v2026.10.0"}')

    monkeypatch.setattr(updates, "urlopen", sahte_urlopen)

    govde = updates._read_url(updates.LATEST_RELEASE_URL, max_bytes=1024)  # noqa: SLF001

    assert govde == b'{"tag_name": "v2026.10.0"}'
    istek = gorulen["istek"]
    assert istek.full_url == updates.LATEST_RELEASE_URL
    assert istek.get_header("User-agent") == updates.USER_AGENT
    assert istek.get_header("Accept") == "application/vnd.github+json"
    assert istek.get_header("X-github-api-version") == updates.GITHUB_API_VERSION
    assert 0 < gorulen["timeout"] <= 30


def test_ag_yaniti_boyut_sinirinda_kesilir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sınır KADAR gövde kabul, bir bayt fazlası ret — bellek, uzak uca güvenilerek dolmaz."""
    monkeypatch.setattr(updates, "urlopen", lambda *_a, **_k: _SahteYanit(b"x" * 10))
    assert updates._read_url("https://github.com/x", max_bytes=10) == b"x" * 10  # noqa: SLF001

    monkeypatch.setattr(updates, "urlopen", lambda *_a, **_k: _SahteYanit(b"x" * 11))
    with pytest.raises(updates.UpdateError, match="boyut sınırını aşıyor"):
        updates._read_url("https://github.com/x", max_bytes=10)  # noqa: SLF001


@pytest.mark.parametrize(
    ("kod", "beklenen"),
    [
        (403, "geçici olarak sınırlandı"),
        (429, "geçici olarak sınırlandı"),
        (500, "HTTP 500"),
    ],
)
def test_http_hatalari_turkce_guncelleme_hatasina_cevrilir(
    monkeypatch: pytest.MonkeyPatch, kod: int, beklenen: str
) -> None:
    def patla(*_a: object, **_k: object) -> _SahteYanit:
        raise _http_hatasi(kod)

    monkeypatch.setattr(updates, "urlopen", patla)

    with pytest.raises(updates.UpdateError, match=beklenen) as yakalanan:
        updates._read_url(updates.LATEST_RELEASE_URL, max_bytes=1024)  # noqa: SLF001
    # 404 DIŞINDAKİ hatalar "sürüm yok" sayılmaz — ön-sürüm yedek yolu tetiklenmemeli.
    assert not isinstance(yakalanan.value, updates.ReleaseNotFoundError)


def test_http_404_surum_yok_hatasidir(monkeypatch: pytest.MonkeyPatch) -> None:
    def patla(*_a: object, **_k: object) -> _SahteYanit:
        raise _http_hatasi(404)

    monkeypatch.setattr(updates, "urlopen", patla)

    with pytest.raises(updates.ReleaseNotFoundError):
        updates._read_url(updates.LATEST_RELEASE_URL, max_bytes=1024)  # noqa: SLF001


@pytest.mark.parametrize(
    "hata", [URLError("dns yok"), TimeoutError("zaman aşımı"), OSError("ağ kapalı")]
)
def test_ag_yokken_baglanti_mesaji_verilir(
    monkeypatch: pytest.MonkeyPatch, hata: Exception
) -> None:
    """Çevrimdışı okul olağan durumdur: ham soket hatası değil, anlaşılır Türkçe mesaj."""

    def patla(*_a: object, **_k: object) -> _SahteYanit:
        raise hata

    monkeypatch.setattr(updates, "urlopen", patla)

    with pytest.raises(updates.UpdateError, match="İnternet bağlantısını kontrol edin"):
        updates._read_url(updates.LATEST_RELEASE_URL, max_bytes=1024)  # noqa: SLF001


# ===========================================================================
# Sürüm okuma + karşılaştırma + önbellek dizini
# ===========================================================================


def test_surum_anahtari_sayisal_karsilastirir_ve_on_surumu_kucuk_sayar() -> None:
    anahtar = updates.version_key
    assert anahtar("2026.10.0") > anahtar("2026.9.0")  # dizge sırasında '10' < '9' olurdu
    assert anahtar("2026.10.0-beta.2") < anahtar("2026.10.0")
    assert anahtar("2026.10.0-beta.2") > anahtar("2026.10.0-beta.1")
    assert anahtar("2026.10") == anahtar("2026.10.0")  # eksik parça sıfırla dolar
    assert anahtar(" 2026.10.0 ") == anahtar("2026.10.0")


def test_on_surum_sirasi_onuncu_surumde_de_dogrudur(monkeypatch: pytest.MonkeyPatch) -> None:
    """İki basamaklı ön-sürüm numarası tek basamaklıdan BÜYÜKTÜR (beta.10 > beta.9)."""

    def sahte_read_url(url: str, *, max_bytes: int) -> bytes:
        if url == updates.LATEST_RELEASE_URL:
            raise updates.ReleaseNotFoundError("kararlı sürüm yok")
        return json.dumps(
            [
                {"tag_name": "v2026.9.0-beta.9", "assets": []},
                {"tag_name": "v2026.9.0-beta.10", "assets": []},
            ]
        ).encode("utf-8")

    monkeypatch.setattr(updates, "_read_url", sahte_read_url)

    durum = updates.update_status(force=True, current_version="2026.9.0-beta.9")

    assert durum["latest_version"] == "2026.9.0-beta.10"
    assert durum["update_available"] is True


def test_calisan_surum_ortam_degiskeninden_ya_da_version_dosyasindan_okunur(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Öncelik: `KS_APP_VERSION` > paket kökündeki `VERSION`; ikisi de yoksa 0.0.0.

    0.0.0 bilinçli bir düşüştür: sürümü okunamayan kurulum "güncel" sanılmaz,
    güncelleme önerisi görür.
    """
    monkeypatch.setattr(updates, "_resource_root", lambda: tmp_path)
    monkeypatch.delenv("KS_APP_VERSION", raising=False)

    assert updates.get_app_version() == "0.0.0"  # dosya yok

    (tmp_path / "VERSION").write_text("  \n", encoding="utf-8")
    assert updates.get_app_version() == "0.0.0"  # dosya boş

    (tmp_path / "VERSION").write_text("2026.9.0-beta.5\n", encoding="utf-8")
    assert updates.get_app_version() == "2026.9.0-beta.5"

    monkeypatch.setenv("KS_APP_VERSION", " 2026.9.1 ")
    assert updates.get_app_version() == "2026.9.1"


def test_paketli_ikilide_surum_paket_kokunden_okunur(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """PyInstaller paketi kaynak ağacı taşımaz: `VERSION` `sys._MEIPASS` altındadır."""
    (tmp_path / "VERSION").write_text("2026.10.0\n", encoding="utf-8")
    monkeypatch.delenv("KS_APP_VERSION", raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert updates.get_app_version() == "2026.10.0"


@pytest.mark.parametrize(
    ("platform", "ortam"),
    [
        ("win32", {"KS_APP_HOME": "/veri/ks"}),
        ("linux", {"KS_APP_HOME": "/veri/ks"}),
        ("win32", {"LOCALAPPDATA": "/kullanici/AppData/Local", "USERPROFILE": "/kullanici"}),
        ("linux", {"XDG_CACHE_HOME": "/ev/.onbellek", "HOME": "/ev"}),
        ("linux", {"HOME": "/ev"}),
    ],
)
def test_guncelleme_onbellegi_masaustu_kabuguyla_ayni_dizini_cozer(
    monkeypatch: pytest.MonkeyPatch, platform: str, ortam: dict[str, str]
) -> None:
    """Kurucu, masaüstü kabuğunun önbelleğine (`AppPaths.cache`) iner — iki çözümleyici
    ayrışırsa indirilen kurucu, kabuğun temizlediği/aradığı dizinin dışında kalır."""
    for ad in ("KS_APP_HOME", "LOCALAPPDATA", "USERPROFILE", "XDG_CACHE_HOME", "HOME"):
        monkeypatch.delenv(ad, raising=False)
    for ad, deger in ortam.items():
        monkeypatch.setenv(ad, deger)

    with monkeypatch.context() as gecici:
        gecici.setattr(sys, "platform", platform)
        cozulen = updates.update_directory()

    beklenen = resolve_app_paths(environ=ortam, platform=platform).cache / "updates"
    assert cozulen == beklenen


# ===========================================================================
# Sürüm yanıtının çözümü
# ===========================================================================


@pytest.mark.parametrize("govde", [None, [], "v2026.10.0", {"tag_name": ""}, {"tag_name": " v "}])
def test_bicimsiz_surum_yaniti_reddedilir(govde: Any) -> None:
    with pytest.raises(updates.UpdateError):
        updates._parse_release(govde)  # noqa: SLF001


def test_surum_yaniti_varlik_ve_baglantilari_temizler() -> None:
    """Uzak yanıta güvenilmez: GitHub dışı bağlantı boşaltılır, bozuk varlık atlanır,
    yalnız Windows kurucusu seçilir (aynı sürümde Linux paketi de yayımlanır)."""
    release = updates._parse_release(  # noqa: SLF001
        {
            "tag_name": "v2026.10.0",
            "html_url": "http://github.com/aalidemirci/kelebek-sinav/releases/tag/v2026.10.0",
            "assets": [
                "varlık değil",
                {"name": "", "browser_download_url": "https://github.com/x/y.exe"},
                {
                    "name": "kelebek-sinav-2026.10.0-linux-x86_64.AppImage",
                    "browser_download_url": "https://github.com/x/y.AppImage",
                },
                {
                    "name": "KELEBEK-SINAV-2026.10.0-WIN64-SETUP.EXE",
                    "browser_download_url": "https://github.com/x/setup.exe",
                    "size": "bilinmiyor",
                    "digest": f"SHA256:{'A' * 64}",
                },
            ],
        }
    )

    assert release.name == "v2026.10.0"  # ad yoksa etiket
    assert release.html_url == ""  # https değil → arayüze bağlantı verilmez
    assert release.checksums is None
    assert release.installer is not None
    assert release.installer.name == "KELEBEK-SINAV-2026.10.0-WIN64-SETUP.EXE"
    assert release.installer.size == 0  # sayı olmayan boyut çökertmez
    assert release.installer.digest == f"sha256:{'a' * 64}"  # özet küçük harfe iner


@pytest.mark.parametrize("ham", [b"{bozuk json", b"\xff\xfe\x00"])
def test_okunamayan_surum_yaniti_guncelleme_hatasidir(
    monkeypatch: pytest.MonkeyPatch, ham: bytes
) -> None:
    """Tutsak portal/vekil sunucu HTML ya da ikili çöp döndürebilir — iz dökümü değil mesaj."""
    monkeypatch.setattr(updates, "_read_url", lambda *_a, **_k: ham)

    with pytest.raises(updates.UpdateError, match="okunamadı"):
        updates.latest_release(force=True)


def _on_surum_listesi(monkeypatch: pytest.MonkeyPatch, liste: Any) -> None:
    def sahte_read_url(url: str, *, max_bytes: int) -> bytes:
        if url == updates.LATEST_RELEASE_URL:
            raise updates.ReleaseNotFoundError("kararlı sürüm yok")
        return json.dumps(liste).encode("utf-8")

    monkeypatch.setattr(updates, "_read_url", sahte_read_url)


def test_on_surum_listesi_liste_degilse_reddedilir(monkeypatch: pytest.MonkeyPatch) -> None:
    _on_surum_listesi(monkeypatch, {"message": "API rate limit exceeded"})

    with pytest.raises(updates.UpdateError, match="beklenen biçimde değil"):
        updates.latest_release(force=True)


def test_on_surum_listesinde_yayimlanmis_surum_yoksa_surum_yok_denir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Taslak, etiketsiz ve biçimsiz kayıtlar elenir; geriye bir şey kalmazsa 'sürüm yok'."""
    _on_surum_listesi(
        monkeypatch,
        [{"tag_name": "v2026.11.0", "draft": True}, {"tag_name": ""}, "kayıt değil"],
    )

    with pytest.raises(updates.ReleaseNotFoundError):
        updates.latest_release(force=True)


# ===========================================================================
# Sürüm önbelleği (15 dk) — her sayfa açılışında GitHub'a gidilmez
# ===========================================================================


@pytest.fixture
def sayac(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Çağrı sayan sahte ağ + elle ilerletilen saat (önbellek autouse fixture'la boştur)."""
    durum: dict[str, Any] = {"cagri": 0, "saat": 1000.0, "etiket": "v2026.10.0"}

    def sahte_read_url(_url: str, *, max_bytes: int) -> bytes:
        durum["cagri"] += 1
        return json.dumps({"tag_name": durum["etiket"]}).encode("utf-8")

    monkeypatch.setattr(updates, "_read_url", sahte_read_url)
    monkeypatch.setattr(time, "monotonic", lambda: durum["saat"])
    return durum


def test_surum_sorgusu_onbellekten_yanitlanir(sayac: dict[str, Any]) -> None:
    ilk = updates.latest_release()
    sayac["etiket"] = "v2026.11.0"  # GitHub'da yeni sürüm çıktı
    ikinci = updates.latest_release()

    assert sayac["cagri"] == 1
    assert ikinci is ilk and ikinci.version == "2026.10.0"


def test_force_onbellegi_atlar_ve_tazeler(sayac: dict[str, Any]) -> None:
    """Ayarlar'daki "Şimdi denetle" düğmesi `force=true` gönderir: bayat yanıt dönmemeli."""
    updates.latest_release()
    sayac["etiket"] = "v2026.11.0"

    assert updates.latest_release(force=True).version == "2026.11.0"
    assert sayac["cagri"] == 2
    # Zorlanan sorgu önbelleği de yeniler: sonraki olağan sorgu yeni sürümü görür.
    assert updates.latest_release().version == "2026.11.0"
    assert sayac["cagri"] == 2


def test_onbellek_suresi_dolunca_yeniden_sorgulanir(sayac: dict[str, Any]) -> None:
    updates.latest_release()
    sayac["etiket"] = "v2026.11.0"

    sayac["saat"] += updates.CACHE_SECONDS - 1
    assert updates.latest_release().version == "2026.10.0"

    sayac["saat"] += 2
    assert updates.latest_release().version == "2026.11.0"
    assert sayac["cagri"] == 2


def test_basarisiz_sorgu_onbellege_yazilmaz(
    sayac: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ağ bir kez koptu diye 15 dakika boyunca hata dönmez — sonraki sorgu yeniden dener."""

    def kopuk(_url: str, *, max_bytes: int) -> bytes:
        raise updates.UpdateError("Güncelleme sunucusuna ulaşılamadı.")

    with monkeypatch.context() as gecici:
        gecici.setattr(updates, "_read_url", kopuk)
        with pytest.raises(updates.UpdateError):
            updates.latest_release()

    assert updates.latest_release().version == "2026.10.0"


# ===========================================================================
# Durum özeti + kurucu indirme kapıları
# ===========================================================================


def _kurucusuz_surum() -> updates.ReleaseInfo:
    return updates.ReleaseInfo(
        version="2026.10.0",
        tag_name="v2026.10.0",
        name="Ekim",
        published_at="",
        html_url="",
        installer=None,
        checksums=None,
    )


def test_kurucusuz_surum_duyurulur_ama_indirilemez(monkeypatch: pytest.MonkeyPatch) -> None:
    """Yalnız Linux paketi çıkmış sürüm: banner sürümü söyler, "İndir" düğmesi kapalıdır."""
    monkeypatch.setattr(updates, "latest_release", lambda **_kwargs: _kurucusuz_surum())

    durum = updates.update_status(current_version="2026.9.0")

    assert durum["update_available"] is True
    assert (durum["can_download"], durum["installer_name"], durum["installer_size"]) == (
        False,
        "",
        0,
    )


@pytest.mark.parametrize("calisan", ["2026.10.0", "2026.11.0-dev"])
def test_guncel_ya_da_daha_yeni_kurulumda_guncelleme_onerilmez(
    monkeypatch: pytest.MonkeyPatch, calisan: str
) -> None:
    monkeypatch.setattr(updates, "latest_release", lambda **_kwargs: _release())

    durum = updates.update_status(current_version=calisan)

    assert durum["update_available"] is False
    assert durum["can_download"] is False


def _indirme_ortami(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    release: updates.ReleaseInfo,
    yanitlar: dict[str, bytes],
    *,
    calisan: str = "2026.9.0",
) -> list[str]:
    """İndirme akışını sahte ağla kurar → istenen adreslerin listesi (sıralı)."""
    istenen: list[str] = []

    def sahte_read_url(url: str, *, max_bytes: int) -> bytes:
        istenen.append(url)
        return yanitlar[url]

    monkeypatch.setattr(updates, "latest_release", lambda **_kwargs: release)
    monkeypatch.setattr(updates, "get_app_version", lambda: calisan)
    monkeypatch.setattr(updates, "_read_url", sahte_read_url)
    monkeypatch.setattr(updates, "update_directory", lambda: tmp_path / "updates")
    return istenen


def _sums_varligi() -> updates.ReleaseAsset:
    return updates.ReleaseAsset(
        name="SHA256SUMS.txt",
        download_url="https://github.com/aalidemirci/kelebek-sinav/releases/download/v2026.10.0/SHA256SUMS.txt",
        size=200,
        digest="",
    )


@pytest.mark.parametrize("varlik_ozeti", ["", "sha256:kisa-ve-bozuk"])
def test_varlik_ozeti_yoksa_sha256sums_dosyasiyla_dogrulanir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, varlik_ozeti: str
) -> None:
    """Eski Release kayıtlarında `digest` alanı yoktur (ya da bozuktur): aynı sürümün
    SHA256SUMS.txt dosyası okunur — `*` ikili işareti ve BÜYÜK harfli özet tanınır,
    boş/eksik/bozuk satırlar ayrıştırmayı düşürmez."""
    icerik = b"kurulum"
    ozet = hashlib.sha256(icerik).hexdigest().upper()
    sums = _sums_varligi()
    release = _release(digest=varlik_ozeti, checksums=sums)
    assert release.installer is not None
    sums_metni = (
        f"{'0' * 64}  kelebek-sinav-2026.10.0-linux-x86_64.AppImage\n"
        "\n"
        "yalniz-tek-sutun\n"
        f"ozet-degil  {release.installer.name}\n"
        f"{ozet} *{release.installer.name}\n"
    )
    _indirme_ortami(
        monkeypatch,
        tmp_path,
        release,
        {sums.download_url: sums_metni.encode("utf-8"), release.installer.download_url: icerik},
    )

    hedef = updates.download_latest_installer()

    assert hedef.read_bytes() == icerik


def test_dogrulama_ozeti_olmayan_kurucu_hic_indirilmez(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Doğrulanamayacak dosya ağdan ÇEKİLMEZ bile (yalnız sonradan reddetmek yetmez)."""
    istenen = _indirme_ortami(monkeypatch, tmp_path, _release(digest="", checksums=None), {})

    with pytest.raises(updates.UpdateError, match="doğrulama özeti bulunmuyor"):
        updates.download_latest_installer()

    assert istenen == []
    assert not (tmp_path / "updates").exists()


def test_sha256sums_kurucuyu_icermiyorsa_indirilmez(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sums = _sums_varligi()
    release = _release(digest="", checksums=sums)
    istenen = _indirme_ortami(
        monkeypatch,
        tmp_path,
        release,
        {sums.download_url: f"{'0' * 64}  baska-dosya.exe\n".encode()},
    )

    with pytest.raises(updates.UpdateError, match="SHA256SUMS.txt içinde"):
        updates.download_latest_installer()

    assert istenen == [sums.download_url]  # kurucunun kendisi istenmedi


@pytest.mark.parametrize("calisan", ["2026.10.0", "2026.11.0"])
def test_guncel_kurulum_kurucu_indirmez(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, calisan: str
) -> None:
    """Sürüm düşürme (downgrade) yolu YOKTUR: eski kurucu yeni şemalı veriyi açamaz."""
    istenen = _indirme_ortami(
        monkeypatch, tmp_path, _release(digest=f"sha256:{'a' * 64}"), {}, calisan=calisan
    )

    with pytest.raises(updates.UpdateError, match="zaten güncel"):
        updates.download_latest_installer()

    assert istenen == []


def test_kurucusuz_ya_da_asiri_buyuk_surum_indirilmez(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    istenen = _indirme_ortami(monkeypatch, tmp_path, _kurucusuz_surum(), {})
    with pytest.raises(updates.UpdateError, match="kurulum dosyası bulunmuyor"):
        updates.download_latest_installer()

    olagan = _release(digest=f"sha256:{'a' * 64}")
    assert olagan.installer is not None
    sisman = updates.ReleaseInfo(
        version=olagan.version,
        tag_name=olagan.tag_name,
        name=olagan.name,
        published_at=olagan.published_at,
        html_url=olagan.html_url,
        installer=updates.ReleaseAsset(
            name=olagan.installer.name,
            download_url=olagan.installer.download_url,
            size=updates.MAX_INSTALLER_BYTES + 1,
            digest=olagan.installer.digest,
        ),
        checksums=None,
    )
    monkeypatch.setattr(updates, "latest_release", lambda **_kwargs: sisman)
    with pytest.raises(updates.UpdateError, match="güvenli boyut sınırını"):
        updates.download_latest_installer()

    assert istenen == []  # bildirilen boyut sınırı aşıyorsa indirme hiç başlamaz


# ===========================================================================
# Uç sözleşmesi — hata ve indirme yolları
# ===========================================================================


@pytest.mark.django_db
def test_guncelleme_api_hatayi_400_ve_turkce_mesajla_dondurur(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Banner hatayı sessizce yutar; Ayarlar ekranı ise bu mesajı gösterir (500 değil)."""
    gorulen: dict[str, Any] = {}

    def patla(**kwargs: Any) -> dict[str, Any]:
        gorulen.update(kwargs)
        raise updates.UpdateError("Güncelleme sunucusuna ulaşılamadı.")

    monkeypatch.setattr(updates, "update_status", patla)

    yanit = client.get("/api/v1/updates/latest/", {"force": "true"})

    assert yanit.status_code == 400
    assert yanit.json()["message"] == "Güncelleme sunucusuna ulaşılamadı."
    assert gorulen == {"force": True}


@pytest.mark.django_db
def test_guncelleme_api_varsayilan_olarak_onbellegi_kullanir(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    gorulen: dict[str, Any] = {}

    def sahte(**kwargs: Any) -> dict[str, Any]:
        gorulen.update(kwargs)
        return {}

    monkeypatch.setattr(updates, "update_status", sahte)

    assert client.get("/api/v1/updates/latest/").status_code == 200
    assert gorulen == {"force": False}


@pytest.mark.django_db
def test_kurucu_indirme_ucu_dogrulanmis_dosyayi_ek_olarak_verir(
    client: APIClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    onbellek = tmp_path / "updates"
    onbellek.mkdir()
    kurucu = onbellek / "kelebek-sinav-2026.10.0-win64-setup.exe"
    kurucu.write_bytes(b"kurulum")
    monkeypatch.setattr(updates, "download_latest_installer", lambda **_kwargs: kurucu)
    monkeypatch.setattr(updates, "update_directory", lambda: onbellek)

    yanit = client.get("/api/v1/updates/latest/installer/")

    assert yanit.status_code == 200
    assert "attachment" in yanit["Content-Disposition"]
    assert kurucu.name in yanit["Content-Disposition"]
    assert isinstance(yanit, StreamingHttpResponse)
    assert b"".join(cast(Iterable[bytes], yanit.streaming_content)) == b"kurulum"


@pytest.mark.django_db
def test_kurucu_indirme_ucu_onbellek_disindaki_dosyayi_vermez(
    client: APIClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Savunma derinliği: servis ne dönerse dönsün, uç yalnız önbellek İÇİNDEKİ dosyayı sunar."""
    disari = tmp_path / "gizli.txt"
    disari.write_bytes(b"sizmamali")
    monkeypatch.setattr(updates, "download_latest_installer", lambda **_kwargs: disari)
    monkeypatch.setattr(updates, "update_directory", lambda: tmp_path / "updates")

    yanit = client.get("/api/v1/updates/latest/installer/")

    assert yanit.status_code == 400
    assert "güvenli önbellek dışında" in yanit.json()["message"]


@pytest.mark.django_db
def test_kurucu_indirme_ucu_servis_hatasini_400_yapar(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def patla(**_kwargs: Any) -> Path:
        raise updates.UpdateError("Uygulama zaten güncel; indirilecek daha yeni bir sürüm yok.")

    monkeypatch.setattr(updates, "download_latest_installer", patla)

    yanit = client.get("/api/v1/updates/latest/installer/")

    assert yanit.status_code == 400
    assert "zaten güncel" in yanit.json()["message"]
