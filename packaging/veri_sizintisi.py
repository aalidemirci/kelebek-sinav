"""Dağıtım paketinde kullanıcı verisi bulunmadığını doğrula.

Bu denetim dosya içeriklerini okumadan yalnızca yolları inceler. Böylece hata
çıktısı da kişisel veri içermez.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

YASAK_UZANTILAR = frozenset({".sqlite", ".sqlite3", ".xls", ".xlsx"})
YASAK_DIZIN_CIFTLERI = frozenset(
    {
        ("backend", "data"),
        ("backend", "media"),
    }
)
YASAK_SONLAR = (".sqlite3-shm", ".sqlite3-wal")


def guvenli_metin(metin: str, encoding: str | None = None) -> str:
    """Konsolun kodlayamadığı karakterleri kaçış dizisine çevirir.

    GitHub Windows runner'ı stdout için CP1252 kullanabilir; bu kodlama Türkçe
    ``ş`` harfini içermez. Denetim başarıyla bittiği hâlde yalnız mesaj yazımı
    yüzünden derlemenin kırılmasını önler.
    """
    hedef = encoding or getattr(sys.stdout, "encoding", None) or "utf-8"
    return metin.encode(hedef, errors="backslashreplace").decode(hedef)


def yaz(metin: str) -> None:
    print(guvenli_metin(metin))


def yol_yasak_mi(goreli_yol: Path) -> bool:
    """Bir paket içi yolun kullanıcı verisi olma ihtimalini sınar."""
    parcalar = tuple(parca.casefold() for parca in goreli_yol.parts)
    ciftler = set(zip(parcalar, parcalar[1:], strict=False))
    ad = goreli_yol.name.casefold()

    return (
        bool(ciftler & YASAK_DIZIN_CIFTLERI)
        or goreli_yol.suffix.casefold() in YASAK_UZANTILAR
        or ad.endswith(YASAK_SONLAR)
    )


def yasak_dosyalari_bul(kok: Path) -> list[Path]:
    """Kök altındaki şüpheli veri dosyalarını göreli yollarıyla döndürür."""
    return sorted(
        (
            yol.relative_to(kok)
            for yol in kok.rglob("*")
            if yol.is_file() and yol_yasak_mi(yol.relative_to(kok))
        ),
        key=lambda yol: str(yol).casefold(),
    )


def argumanlari_ayristir(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Komut satırı argümanlarını ayrıştırır."""
    parser = argparse.ArgumentParser(
        description="Dağıtım paketinde kullanıcı verisi bulunmadığını denetler."
    )
    parser.add_argument("kok", type=Path, help="Denetlenecek paket dizini")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Komut satırı giriş noktası."""
    args = argumanlari_ayristir(argv)
    kok: Path = args.kok

    if not kok.is_dir():
        yaz(f"HATA: paket dizini bulunamadı: {kok}")
        return 2

    yasak_dosyalar = yasak_dosyalari_bul(kok)
    if yasak_dosyalar:
        yaz("HATA: pakette kullanıcı verisi olabilecek dosyalar bulundu:")
        for yol in yasak_dosyalar:
            yaz(f"  - {yol.as_posix()}")
        return 1

    yaz("Paket veri denetimi başarılı: kullanıcı veri dosyası bulunmadı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
