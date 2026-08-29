"""Ana marka logosunu üretir: `kelebek-sinav-logo.png` (1024×1024, saydam).

Tasarım: oturma planı ızgarasının yuvarlatılmış kare hücrelerinden kurulan bir
kelebek — üst kanatlar mürekkep mavisi, alt kanatlar çini yeşili, gövde koyu
arduvaz. Program salon krokisindeki koltuk karelerini markaya taşır.

Çalıştırma (depo kökünden, Docker içinde — host'a kurulum YASAK):

    docker compose run --rm -w /repo backend python packaging/ikonlar/logo_uret.py
    docker compose run --rm -w /repo backend python packaging/ikonlar/ikon_uret.py

Çıktı depoya COMMIT EDİLİR; ikon kesimlerini `ikon_uret.py` bu dosyadan üretir.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUTPUT = Path(__file__).resolve().parent / "kelebek-sinav-logo.png"

# 9×9 hücre haritası: 1 = üst kanat, 2 = alt kanat, 3 = gövde, 0 = boş.
# Sol yarı tasarlandı, sağ yarı aynadır (kelebek simetrisi = kroki simetrisi).
_SOL = [
    [0, 0, 1, 1],
    [0, 1, 1, 1],
    [1, 1, 1, 1],
    [1, 1, 1, 1],
    [0, 1, 1, 1],
    [0, 2, 2, 0],
    [2, 2, 2, 0],
    [0, 2, 2, 0],
    [0, 0, 2, 0],
]
_GOVDE_SATIRLARI = range(1, 8)

RENKLER = {
    1: (41, 80, 124, 255),  # mürekkep mavisi — üst kanat
    2: (47, 125, 116, 255),  # çini yeşili — alt kanat
    3: (28, 39, 51, 255),  # koyu arduvaz — gövde
}

HUCRE = 100  # hücre kenarı (px)
BOSLUK = 14  # hücreler arası boşluk
YARICAP = 24  # hücre köşe yarıçapı


def _harita() -> list[list[int]]:
    satirlar: list[list[int]] = []
    for y, sol in enumerate(_SOL):
        govde = 3 if y in _GOVDE_SATIRLARI else 0
        satirlar.append(sol + [govde] + list(reversed(sol)))
    return satirlar


def generate() -> Path:
    harita = _harita()
    genislik = len(harita[0]) * (HUCRE + BOSLUK) - BOSLUK
    yukseklik = len(harita) * (HUCRE + BOSLUK) - BOSLUK
    kenar = max(genislik, yukseklik)
    image = Image.new("RGBA", (kenar, kenar), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    x0 = (kenar - genislik) // 2
    y0 = (kenar - yukseklik) // 2
    for y, satir in enumerate(harita):
        for x, deger in enumerate(satir):
            if deger == 0:
                continue
            sol = x0 + x * (HUCRE + BOSLUK)
            ust = y0 + y * (HUCRE + BOSLUK)
            draw.rounded_rectangle(
                (sol, ust, sol + HUCRE, ust + HUCRE),
                radius=YARICAP,
                fill=RENKLER[deger],
            )

    image.save(OUTPUT, format="PNG", optimize=True)
    return OUTPUT


if __name__ == "__main__":
    import sys

    sys.stderr.write(f"yazıldı: {generate()}\n")
