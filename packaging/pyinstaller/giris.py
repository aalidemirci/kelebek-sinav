"""Paketlenmiş programın giriş noktası (PyInstaller `kelebek_sinav.spec`).

Normal çalışmada tek işi vardır: `desktop.main.run()`'a devretmek. Kabuğun
kendisi `desktop/` altındadır ve bu dosyaya bağımlı DEĞİLDİR — depodan
`python -m desktop.main` ile çalıştırmak da aynı sonucu verir.

Ek olarak paketlenmiş sürümde **teşhis kipi** sunar:

    kelebek-sinav --pdf-duman [dosya.pdf]

Bu kip Türkçe metinli küçük bir PDF üretir ve metni pypdf ile geri okuyup
doğrular. Amacı iki katmanı ayrı ayrı sınamaktır:

1. **PDF motoru ayakta mı** — Windows'ta WeasyPrint pango/harfbuzz/fontconfig
   DLL'lerini çalışma anında `dlopen` ile açar; paketten bir DLL eksikse bu
   kip ilk açılışta değil, burada patlar (tasarım §9 "WeasyPrint Win DLL
   cehennemi").
2. **Türkçe karakterler doğru font ile mi diziliyor** — üretilen PDF'te
   `ĞÜŞİÖÇ ığüşiöç` metni geri okunabiliyor ve kullanılan font gömülü DejaVu
   ise, fontconfig gömülü fonta bakıyor demektir (tasarım §5.1 "fontconfig
   tuzağı").

Kip hem CI duman testinde (§8) hem de sahada "programın PDF üretimi çalışıyor
mu?" sorusunu tek komutla yanıtlamak için kullanılır. Veritabanına DOKUNMAZ:
Django ayağa kaldırılmaz, veri dizinine yazılmaz.
"""

from __future__ import annotations

import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

# Depodan doğrudan çalıştırıldığında (`python packaging/pyinstaller/giris.py`)
# depo kökü `sys.path`'te olmayabilir; paketlenmiş çalışmada zaten donmuş hâlde.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

PDF_SMOKE_FLAG = "--pdf-duman"

# `desktop/errors.py` 0-7 arasını kullanıyor; teşhis kipi 8'den devam eder.
EXIT_PDF_SMOKE_FAILED = 8

# Duman testinin aradığı metin — Türkçe'ye özgü altı harf, hem büyük hem küçük.
TURKISH_SAMPLE = "ĞÜŞİÖÇ ığüşiöç"
# Yalnız gömülü DejaVu ile dizilmeli; sistem fontuna düşerse bu ad görünmez.
EXPECTED_FONT_FRAGMENT = "DejaVu"

_SMOKE_HTML = """<!DOCTYPE html>
<html lang="tr">
  <head>
    <meta charset="utf-8" />
    <style>
      @page {{ size: A4; margin: 20mm; }}
      body {{ font-family: "DejaVu Sans", sans-serif; font-size: 12pt; }}
    </style>
  </head>
  <body>
    <p>{sample}</p>
    <p>Kelebek Sınav PDF duman testi.</p>
  </body>
</html>
"""


def _write(message: str) -> None:
    """Teşhis çıktısı — konsol yoksa (Windows penceresiz derleme) sessiz geçer.

    `print()` bilinçli olarak kullanılmaz: paketlenmiş penceresiz derlemede
    `sys.stdout` `None`'dır ve `print` orada `AttributeError` üretir.
    """
    stream = sys.stderr
    if stream is None:
        return
    try:
        stream.write(message + "\n")
        stream.flush()
    except (OSError, ValueError):
        return


def _pdf_fonts(pdf_path: Path) -> set[str]:
    """PDF'in ilk sayfasındaki gömülü font adlarını döndürür."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    resources = reader.pages[0].get("/Resources")
    if resources is None:
        return set()
    fonts = resources.get_object().get("/Font")
    if fonts is None:
        return set()
    names: set[str] = set()
    for value in fonts.get_object().values():
        base_font = value.get_object().get("/BaseFont")
        if base_font is not None:
            names.add(str(base_font))
    return names


def _pdf_text(pdf_path: Path) -> str:
    """PDF'in ilk sayfasındaki metni döndürür."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    return reader.pages[0].extract_text() or ""


def _fontconfig_teshisi() -> None:
    """Font eşleşmesi başarısızsa NEDEN olduğunu yazar.

    Windows'ta fontconfig yapılandırması ya hiç okunmaz (env yok) ya da
    ayrıştırılamayıp SESSİZCE reddedilir; ikisinde de sonuç aynıdır — sistem
    fontuna düşer. Bu ayrımı log'suz yapmak imkânsız olduğu için tanılama
    doğrudan buraya konur (CI koşusu başına ~5 dk; tahminle iterasyon pahalı).
    """
    import os

    for degisken in ("FONTCONFIG_FILE", "FONTCONFIG_PATH", "KS_RTHOOK_UYARI"):
        _write(f"  {degisken}={os.environ.get(degisken, '<yok>')}")

    conf = os.environ.get("FONTCONFIG_FILE", "")
    if conf:
        yol = Path(conf)
        _write(f"  fonts.conf var mı: {yol.is_file()}")
        if yol.is_file():
            try:
                _write("  fonts.conf içeriği (ilk 400 karakter):")
                _write("    " + yol.read_text(encoding="utf-8")[:400].replace("\n", "\n    "))
            except OSError as hata:
                _write(f"  fonts.conf okunamadı: {hata}")

    kok = Path(getattr(sys, "_MEIPASS", _REPO_ROOT))
    font_dizini = kok / "fonts"
    _write(f"  gömülü font dizini: {font_dizini} (var mı: {font_dizini.is_dir()})")
    if font_dizini.is_dir():
        _write(f"  içindekiler: {sorted(p.name for p in font_dizini.iterdir())}")


def run_pdf_smoke(target: Path) -> int:
    """Türkçe metinli PDF üretir, geri okuyup doğrular; 0 = başarılı."""
    from weasyprint import HTML

    target.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=_SMOKE_HTML.format(sample=TURKISH_SAMPLE)).write_pdf(str(target))
    if not target.is_file() or target.stat().st_size == 0:
        _write(f"HATA: PDF üretilemedi ({target}).")
        return EXIT_PDF_SMOKE_FAILED

    text = _pdf_text(target)
    # PDF metin çıkarımı satır sonu/boşluk ekleyebilir; harf harf aranır.
    missing = [letter for letter in TURKISH_SAMPLE if letter != " " and letter not in text]
    if missing:
        _write("HATA: PDF metninde Türkçe karakterler bulunamadı: " + "".join(missing))
        _write(f"Okunan metin: {text!r}")
        return EXIT_PDF_SMOKE_FAILED

    fonts = _pdf_fonts(target)
    if not any(EXPECTED_FONT_FRAGMENT in name for name in sorted(fonts)):
        _write(
            "HATA: PDF gömülü DejaVu fontu ile dizilmemiş "
            f"(bulunan fontlar: {sorted(fonts)}). Fontconfig sistem fontuna düşmüş olabilir."
        )
        _fontconfig_teshisi()
        return EXIT_PDF_SMOKE_FAILED

    _write(f"PDF duman testi başarılı: {target}")
    _write(f"Fontlar: {sorted(fonts)}")
    return 0


def _smoke_target(argv: Sequence[str]) -> Path:
    """`--pdf-duman` sonrasında dosya yolu verildiyse onu, yoksa geçici dosyayı seçer."""
    index = list(argv).index(PDF_SMOKE_FLAG)
    rest = list(argv)[index + 1 :]
    if rest and not rest[0].startswith("-"):
        return Path(rest[0])
    return Path(tempfile.gettempdir()) / "kelebek-sinav-pdf-duman.pdf"


def run(argv: Sequence[str] | None = None) -> int:
    """Argümanlara göre teşhis kipini veya normal açılışı çalıştırır."""
    args = list(sys.argv[1:] if argv is None else argv)
    if PDF_SMOKE_FLAG in args:
        try:
            return run_pdf_smoke(_smoke_target(args))
        except Exception as error:  # noqa: BLE001 — teşhis kipi: her hata rapor edilir
            _write(f"HATA: PDF duman testi çöktü: {error!r}")
            return EXIT_PDF_SMOKE_FAILED

    from desktop.main import run as run_shell

    return run_shell(args)


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
