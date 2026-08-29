"""Onaylı logo kaynağından uygulama ikonlarını üretir (PNG + Windows `.ico`).

Çalıştırma (depo kökünden, Docker içinde — host'a kurulum YASAK):

    docker compose run --rm -w /repo backend python packaging/ikonlar/ikon_uret.py

Çıktılar `packaging/ikonlar/` altına yazılır ve depoya COMMIT EDİLİR: paket
üretimi (CI dahil) ikon üretmez, hazır dosyaları kopyalar. Böylece Pillow
sürümü değiştiğinde paketin görüntüsü sessizce değişmez.

`kelebek-sinav-logo.png`, ImageGen ile tasarlanıp alfa kanalı doğrulanmış ana
markadır. Betik görünür alanı kareye alır, güvenli boşluk ekler ve bütün platform
kesimlerini aynı kaynaktan üretir. Böylece EXE/Start menüsü ve uygulama içi marka
birbirinden sapmaz.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

OUTPUT_DIR = Path(__file__).resolve().parent
MASTER_SOURCE = OUTPUT_DIR / "kelebek-sinav-logo.png"
FRONTEND_TARGET = OUTPUT_DIR.parents[1] / "frontend" / "public" / "app-logo.png"
PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _load_master() -> Image.Image:
    """Saydam ana markayı görünür sınıra kırpar ve %8 güvenli boşlukla kareler."""
    image = Image.open(MASTER_SOURCE).convert("RGBA")
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise RuntimeError(f"Logo tamamen saydam: {MASTER_SOURCE}")
    cropped = image.crop(bbox)
    padding = max(8, round(max(cropped.size) * 0.08))
    side = max(cropped.size) + 2 * padding
    master = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    master.alpha_composite(
        cropped,
        ((side - cropped.width) // 2, (side - cropped.height) // 2),
    )
    return master


def generate() -> list[Path]:
    """Tüm ikon dosyalarını yazar ve yollarını döndürür."""
    master = _load_master()
    written: list[Path] = []

    for size in PNG_SIZES:
        target = OUTPUT_DIR / f"kelebek-sinav-{size}.png"
        master.resize((size, size), Image.Resampling.LANCZOS).save(
            target, format="PNG", optimize=True
        )
        written.append(target)

    ico = OUTPUT_DIR / "kelebek-sinav.ico"
    master.resize((256, 256), Image.Resampling.LANCZOS).save(
        ico, format="ICO", sizes=[(size, size) for size in ICO_SIZES]
    )
    written.append(ico)

    FRONTEND_TARGET.parent.mkdir(parents=True, exist_ok=True)
    master.resize((192, 192), Image.Resampling.LANCZOS).save(
        FRONTEND_TARGET, format="PNG", optimize=True
    )
    written.append(FRONTEND_TARGET)
    return written


if __name__ == "__main__":
    import sys

    for path in generate():
        # Betik yalnız elle çalıştırılır; çıktı listesi bilinçli olarak yazılır.
        sys.stderr.write(f"yazıldı: {path}\n")
