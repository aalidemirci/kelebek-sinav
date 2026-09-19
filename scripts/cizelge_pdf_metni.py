"""TTKB haftalık ders çizelgesi PDF'ini düzen-korumalı metne döker.

`scripts/cizelge_metninden_tablo.py`'nin GİRDİSİNİ üretir: her sayfa
`===== SAYFA n =====` başlığıyla, pypdf'in `extract_text(extraction_mode="layout")`
çıktısı. Metin, PDF'in yanına `<ad>.txt` olarak UTF-8 yazılır (kabuk
yönlendirmesi kullanılmaz: PowerShell `>` UTF-8'i BOM'lu/UTF-16 yazar).

Kullanım (Docker'da; host'a Python kurulmaz — CLAUDE.md §1/5). `data/raw/` git
dışıdır; worktree'de çalışırken ana deponun dizini `-v` ile bağlanır:

    docker compose run --rm backend python /repo/scripts/cizelge_pdf_metni.py \
        /repo/data/raw/ttkb-2026-102-spor-lisesi.pdf
    docker compose run --rm backend python /repo/scripts/cizelge_pdf_metni.py \
        --dondurulmus /repo/data/raw/mtegm-cop9-bilisim-2026.pdf

DYS sarmalı (19.09.2026, TTK 2026/102-104): 09.2026'dan itibaren TTKB'nin
yayımladığı PDF'ler DYS çıktısıdır (üretici "OpenPDF"). Özgün sayfa tek bir
Form XObject'e sarılmış, sayfanın KENDİ içerik akışında yalnız çapraz indirme
filigranı (rakam dizisi) kalmıştır. pypdf'in düzen kipi yalnız sayfa akışını
okur, forma inmez → "metin yok / taranmış görüntü" SANILIR, oysa metin formun
içindedir. Bu betik, sayfadan harf çıkmıyorsa ve sayfada tek form varsa formu
BELLEKTE sayfa içeriği yapar (/Contents ← form akışı, /Resources ← form
kaynakları) ve yeniden okur; filigran da böylece döküme girmez. PDF değişmez.

`--dondurulmus`: MTAL çerçeve öğretim programlarında çizelge DÖNDÜRÜLMÜŞ
metindir; düzen kipi onu atlar ("Rotated text discovered"), düz kip
`orientations=(0, 90, 180, 270)` ile okur (sütun hizası korunmaz).
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

from pypdf import PageObject, PdfReader
from pypdf.generic import IndirectObject, NameObject


def _ac(nesne: Any) -> Any:
    """Dolaylı başvuruyu nesnesine çözer (pypdf sözlükleri gevşek tiplidir)."""
    return nesne.get_object() if isinstance(nesne, IndirectObject) else nesne


def _tek_form(sayfa: PageObject) -> IndirectObject | None:
    """Sayfanın kaynaklarındaki TEK Form XObject'in başvurusu (yoksa/çoksa None)."""
    kaynaklar = _ac(sayfa.get("/Resources"))
    xobj = _ac(kaynaklar.get("/XObject")) if kaynaklar is not None else None
    if not xobj:
        return None
    formlar = [ref for ref in xobj.values() if _ac(ref).get("/Subtype") == "/Form"]
    if len(formlar) != 1 or not isinstance(formlar[0], IndirectObject):
        return None
    return formlar[0]


def sayfa_metni(sayfa: PageObject, *, dondurulmus: bool = False) -> tuple[str, bool]:
    """(metin, form_acildi_mi). Harf çıkmayan tek-formlu sayfada form açılıp yeniden okunur."""

    def oku() -> str:
        if dondurulmus:
            return sayfa.extract_text(orientations=(0, 90, 180, 270)) or ""
        return sayfa.extract_text(extraction_mode="layout") or ""

    metin = oku()
    if any(ch.isalpha() for ch in metin):
        return metin, False
    form = _tek_form(sayfa)
    if form is None:
        return metin, False
    sayfa[NameObject("/Contents")] = form
    sayfa[NameObject("/Resources")] = _ac(form)["/Resources"]
    return oku(), True


def dok(yol: Path, *, dondurulmus: bool = False) -> Path:
    veri = yol.read_bytes()
    okuyucu = PdfReader(str(yol))
    parcalar: list[str] = []
    acilan: list[int] = []
    for no, sayfa in enumerate(okuyucu.pages, 1):
        metin, acildi = sayfa_metni(sayfa, dondurulmus=dondurulmus)
        if acildi:
            acilan.append(no)
        parcalar.append(f"===== SAYFA {no} =====")
        parcalar.append(metin)
    cikti = yol.with_suffix(".txt")
    cikti.write_text("\n" + "\n".join(parcalar) + "\n", encoding="utf-8")
    ozet = hashlib.sha256(veri).hexdigest()
    print(f"{yol.name}: {len(veri)} bayt, sha256={ozet}, {len(okuyucu.pages)} sayfa")
    if acilan:
        print(f"  DYS sarmalı: içerik Form XObject'ten okundu (sayfa {acilan}); filigran atlandı.")
    harfli = sum(1 for p in parcalar[1::2] if any(ch.isalpha() for ch in p))
    if harfli < len(okuyucu.pages):
        print(f"  UYARI: {len(okuyucu.pages) - harfli} sayfadan harf çıkmadı (taranmış görüntü?).")
    print(f"  -> {cikti}")
    return cikti


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    dondurulmus = "--dondurulmus" in argv
    yollar = [Path(a) for a in argv if not a.startswith("--")]
    for yol in yollar:
        dok(yol, dondurulmus=dondurulmus)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
