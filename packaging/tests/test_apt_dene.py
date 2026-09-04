"""`packaging/linux/apt_dene.sh` — apt yeniden deneme sarmalının davranışı.

Gerçek apt çağrılmaz: PATH'e sahte bir `apt-get` konur ve kaçıncı çağrıda
başarılı olacağı sayaçla ayarlanır. Böylece test ağdan ve dağıtımdan bağımsız
kalır — sarmalın işi zaten "ağ/ayna kararsızsa ne olacak" sorusudur.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SARMAL = Path(__file__).resolve().parents[1] / "linux" / "apt_dene.sh"
# Tam yol: ruff/bandit S607 kısmi yolu uyarır. Testler yalnız Docker'da koşar
# (CLAUDE.md §1.5), orada bash /bin/bash'tir; `which` yerel kabuğu da bulur.
BASH = shutil.which("bash") or "/bin/bash"

# Verilen denemeden itibaren başarılı olan sahte apt-get. `update` her zaman
# geçer; asıl kırılma `install` tarafındadır (gerçek vakadaki gibi).
SAHTE_APT = """#!/usr/bin/env bash
if [ "$1" = "update" ]; then exit 0; fi
n=$(cat "$SAYAC" 2>/dev/null || echo 0)
n=$((n + 1))
echo "$n" > "$SAYAC"
if [ "$n" -ge "$BASARILI_DENEME" ]; then
  echo "kuruldu (deneme $n)"
  exit 0
fi
echo "E: Failed to fetch ... 404 Not Found" >&2
exit 100
"""


def _kos(tmp_path: Path, basarili_deneme: int) -> subprocess.CompletedProcess[str]:
    sahte_dizin = tmp_path / "bin"
    sahte_dizin.mkdir()
    sahte = sahte_dizin / "apt-get"
    sahte.write_text(SAHTE_APT, encoding="utf-8")
    sahte.chmod(0o755)

    betik = f'. "{SARMAL}"\n' "APT_BEKLEME_SANIYE=0 apt_dene apt-get install -y kukla-paket\n"
    # S603: komut satırı testin KENDİSİ tarafından üretiliyor, dış girdi yok.
    return subprocess.run(  # noqa: S603
        [BASH, "-c", betik],
        capture_output=True,
        text=True,
        env={
            "PATH": f"{sahte_dizin}:/usr/bin:/bin",
            "SAYAC": str(tmp_path / "sayac"),
            "BASARILI_DENEME": str(basarili_deneme),
        },
        check=False,
    )


def test_ilk_denemede_gecen_komut_yeniden_denenmez(tmp_path: Path) -> None:
    sonuc = _kos(tmp_path, basarili_deneme=1)

    assert sonuc.returncode == 0
    assert "UYARI" not in sonuc.stderr


def test_gecici_404_sonrasi_kurtarir(tmp_path: Path) -> None:
    """Gerçek vaka: v2026.9.0-beta.5 koşusu 404 aldı, aynı commit sonra geçti."""
    sonuc = _kos(tmp_path, basarili_deneme=3)

    assert sonuc.returncode == 0
    assert sonuc.stderr.count("UYARI: apt") == 2  # iki başarısız deneme uyarısı
    assert "kuruldu (deneme 3)" in sonuc.stdout


def test_kalici_hatada_pes_eder_ve_hata_doner(tmp_path: Path) -> None:
    """Sarmal SONSUZ denemez: kalıcı bir kırılma kapıyı kırmalı (fail-closed)."""
    sonuc = _kos(tmp_path, basarili_deneme=99)

    assert sonuc.returncode == 1
    assert "3 denemede de başarısız" in sonuc.stderr


@pytest.mark.parametrize("azami", ["1", "2"])
def test_deneme_sayisi_ayarlanabilir(tmp_path: Path, azami: str) -> None:
    sahte_dizin = tmp_path / "bin"
    sahte_dizin.mkdir()
    sahte = sahte_dizin / "apt-get"
    sahte.write_text(SAHTE_APT, encoding="utf-8")
    sahte.chmod(0o755)

    # S603: komut satırı testin kendisi tarafından üretiliyor, dış girdi yok.
    sonuc = subprocess.run(  # noqa: S603
        [BASH, "-c", f'. "{SARMAL}"\nAPT_BEKLEME_SANIYE=0 apt_dene apt-get install -y x\n'],
        capture_output=True,
        text=True,
        env={
            "PATH": f"{sahte_dizin}:/usr/bin:/bin",
            "SAYAC": str(tmp_path / "sayac"),
            "BASARILI_DENEME": "99",
            "APT_AZAMI_DENEME": azami,
        },
        check=False,
    )

    assert sonuc.returncode == 1
    assert f"{azami} denemede de başarısız" in sonuc.stderr
