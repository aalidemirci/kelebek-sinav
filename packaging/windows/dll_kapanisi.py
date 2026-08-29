"""WeasyPrint'in Windows DLL kapanışını üretir (elle liste YOK).

BU DOSYA BU ORTAMDA DOĞRULANMADI — ilk Windows koşusunda sınanacak.
(Linux'ta yalnız ruff/mypy denetimlerinden geçirildi.)

--------------------------------------------------------------------------
Neden gerekli?
--------------------------------------------------------------------------
WeasyPrint 63, pango/harfbuzz/fontconfig kütüphanelerini derleme anında
BAĞLAMAZ; çalışma anında `ctypes`/`cffi` ile açar. PyInstaller'ın statik
çözümleyicisi bu bağı göremez, dolayısıyla bu DLL'ler pakete KENDİLİĞİNDEN
girmez. Tasarım §5.1: liste ELLE yazılmaz — bir sürüm yükseltmesinde sessizce
eksilir ve hata yalnız sahada, PDF üretilirken ortaya çıkar. Bunun yerine
kapanış her derlemede araçla hesaplanır.

--------------------------------------------------------------------------
Nasıl çalışır?
--------------------------------------------------------------------------
1. MSYS2 `mingw64/bin` dizininde tohum kütüphaneler DESENLE aranır
   (`libpango*`, `libgobject*`, …) — böylece dosya adındaki sürüm ekleri
   ("-1.0-0") elle tahmin edilmez.
2. Her tohumun bağımlılıkları özyinelemeli çıkarılır:
   - `ntldd -R` varsa onunla (MSYS2: `mingw-w64-x86_64-ntldd-git`),
   - yoksa `objdump -p` çıktısındaki "DLL Name:" satırlarıyla.
3. Yalnız mingw64/bin içinde BULUNAN DLL'ler kopyalanır; Windows sistem
   DLL'leri (KERNEL32, USER32 …) bilinçli olarak dışarıda bırakılır — onları
   paketlemek hem lisans hem kararlılık açısından yanlıştır.

Kullanım:
    python packaging/windows/dll_kapanisi.py \
        --mingw-bin C:/msys64/mingw64/bin \
        --cikti packaging/windows/dll
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

# Tohum desenleri — WeasyPrint'in çalışma anında açtığı kütüphaneler.
# Desen kullanılır, TAM AD DEĞİL: MSYS2 dosya adları sürümle değişir
# (libpango-1.0-0.dll, libharfbuzz-0.dll …).
SEED_PATTERNS = (
    "libgobject-*.dll",
    "libglib-*.dll",
    "libgio-*.dll",
    "libpango-*.dll",
    "libpangoft2-*.dll",
    "libharfbuzz-*.dll",  # libharfbuzz-0.dll + libharfbuzz-subset.dll
    "libfontconfig-*.dll",
    "libfreetype-*.dll",
)

# En az bunlar bulunmalı; biri yoksa paket sahada PDF üretemez.
REQUIRED_SEED_PREFIXES = (
    "libgobject-",
    "libpango-",
    "libpangoft2-",
    "libharfbuzz-",
    "libfontconfig-",
)

_OBJDUMP_RE = re.compile(r"DLL Name:\s*(\S+)", re.IGNORECASE)
_NTLDD_RE = re.compile(r"=>\s*(\S.*?)\s*\(0x", re.IGNORECASE)


def _run(command: list[str]) -> str | None:
    """Komutu çalıştırır; araç yoksa veya hata verirse None döndürür."""
    try:
        result = subprocess.run(  # noqa: S603 — sabit araç adları, kabuk yok
            command, capture_output=True, text=True, check=False, timeout=120
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def tool_available(name: str) -> bool:
    """Araç PATH'te mi?"""
    return shutil.which(name) is not None


def direct_dependencies(dll: Path) -> set[str]:
    """DLL'in doğrudan bağımlılık ADLARINI döndürür (yol değil)."""
    if tool_available("ntldd"):
        output = _run(["ntldd", "-R", str(dll)])
        if output is not None:
            names = {Path(path).name for path in _NTLDD_RE.findall(output)}
            if names:
                return names
    output = _run(["objdump", "-p", str(dll)])
    if output is None:
        return set()
    return set(_OBJDUMP_RE.findall(output))


def closure(seeds: Iterable[Path], mingw_bin: Path) -> set[Path]:
    """Tohumlardan başlayarak mingw64/bin içindeki tüm bağımlılıkları toplar."""
    # Büyük/küçük harf duyarsız arama (Windows dosya sistemi öyle davranır).
    available = {path.name.lower(): path for path in mingw_bin.glob("*.dll")}
    found: set[Path] = set()
    queue = list(seeds)
    while queue:
        dll = queue.pop()
        if dll in found:
            continue
        found.add(dll)
        for name in direct_dependencies(dll):
            candidate = available.get(name.lower())
            # Sistem DLL'leri (mingw64/bin dışında) bilinçli olarak atlanır.
            if candidate is not None and candidate not in found:
                queue.append(candidate)
    return found


def find_seeds(mingw_bin: Path) -> list[Path]:
    """Tohum desenlerine uyan DLL'leri bulur."""
    seeds: list[Path] = []
    for pattern in SEED_PATTERNS:
        seeds.extend(sorted(mingw_bin.glob(pattern)))
    return sorted(set(seeds))


def missing_required(seeds: Iterable[Path]) -> list[str]:
    """Bulunamayan zorunlu tohumların önekleri."""
    names = [path.name.lower() for path in seeds]
    return [
        prefix for prefix in REQUIRED_SEED_PREFIXES if not any(n.startswith(prefix) for n in names)
    ]


def build(mingw_bin: Path, output_dir: Path) -> int:
    """Kapanışı hesaplar ve DLL'leri çıktı dizinine kopyalar."""
    if not mingw_bin.is_dir():
        sys.stderr.write(f"HATA: mingw64/bin dizini yok: {mingw_bin}\n")
        return 2

    seeds = find_seeds(mingw_bin)
    missing = missing_required(seeds)
    if missing:
        sys.stderr.write(
            "HATA: zorunlu kütüphaneler bulunamadı: "
            + ", ".join(missing)
            + "\nMSYS2'de `pacman -S mingw-w64-x86_64-pango mingw-w64-x86_64-fontconfig` çalıştırın.\n"
        )
        return 3

    if not tool_available("ntldd") and not tool_available("objdump"):
        sys.stderr.write(
            "HATA: ne `ntldd` ne `objdump` bulundu. MSYS2'de "
            "`pacman -S mingw-w64-x86_64-ntldd-git` veya `pacman -S mingw-w64-x86_64-binutils`.\n"
        )
        return 4

    everything = closure(seeds, mingw_bin)
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in output_dir.glob("*.dll"):
        stale.unlink()
    for dll in sorted(everything):
        shutil.copy2(dll, output_dir / dll.name)

    sys.stderr.write(f"{len(everything)} DLL kopyalandı → {output_dir}\n")
    for name in sorted(path.name for path in everything):
        sys.stderr.write(f"  {name}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WeasyPrint Windows DLL kapanışını üretir.")
    parser.add_argument(
        "--mingw-bin",
        default="C:/msys64/mingw64/bin",
        help="MSYS2 mingw64/bin dizini.",
    )
    parser.add_argument(
        "--cikti",
        default=str(Path(__file__).resolve().parent / "dll"),
        help="DLL'lerin kopyalanacağı dizin.",
    )
    args = parser.parse_args(argv)
    return build(Path(args.mingw_bin), Path(args.cikti))


if __name__ == "__main__":
    raise SystemExit(main())
