"""Paketlenmiş programın giriş noktası (PyInstaller `kelebek_sinav.spec`).

Normal çalışmada tek işi vardır: `desktop.main.run()`'a devretmek. Kabuğun
kendisi `desktop/` altındadır ve bu dosyaya bağımlı DEĞİLDİR — depodan
`python -m desktop.main` ile çalıştırmak da aynı sonucu verir.

Ek olarak paketlenmiş sürümde **iki teşhis kipi** sunar:

    kelebek-sinav --bagimlilik-duman

Bu kip `RUNTIME_MODULES`'ın tamamını import eder ve K7 borcunun (CLAUDE.md §2)
runtime kapısıdır: spec'e eklenmeyi unutulan bir bağımlılık burada, derleme
başında yakalanır — sahada değil. Aşağıdaki PDF kipi yalnız WeasyPrint
zincirini sınadığı için tek başına yetmez (30.08.2026'da `xlrd` eklendiğinde
görüldü: yeni bağımlılığın pakete girip girmediğini sınayan kapı yoktu).

    kelebek-sinav --pdf-duman [dosya.pdf]

Bu kip Türkçe metinli, tek fotoğraflı küçük bir PDF üretir ve pypdf ile geri
okuyup doğrular. Amacı üç katmanı ayrı ayrı sınamaktır:

1. **PDF motoru ayakta mı** — Windows'ta WeasyPrint pango/harfbuzz/fontconfig
   DLL'lerini çalışma anında `dlopen` ile açar; paketten bir DLL eksikse bu
   kip ilk açılışta değil, burada patlar (tasarım §9 "WeasyPrint Win DLL
   cehennemi").
2. **Türkçe karakterler doğru font ile mi diziliyor** — üretilen PDF'te
   `ĞÜŞİÖÇ ığüşiöç` metni geri okunabiliyor ve kullanılan font gömülü DejaVu
   ise, fontconfig gömülü fonta bakıyor demektir (tasarım §5.1 "fontconfig
   tuzağı").
3. **Fotoğraf JPEG olarak gömülüyor mu** — salon evrakının fotoğraflı oturma
   planı (19.09.2026) öğrenci fotoğrafını Pillow'la JPEG'e kodlar, WeasyPrint
   onu PDF'e gömer. WeasyPrint çözemediği görseli yalnız UYARIYLA atlar: JPEG
   zinciri pakette eksikse evrak hata vermeden fotoğrafsız basılırdı. Kip
   görseli çalışma anında üretir ve PDF'te DCT (JPEG) görsel nesnesi arar.

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
IMPORT_SMOKE_FLAG = "--bagimlilik-duman"

# `desktop/errors.py` 0-7 arasını kullanıyor; teşhis kipi 8'den devam eder
# (9 = --geri-yukle). Kodlar `desktop/errors.py` ile İKİZDİR.
EXIT_PDF_SMOKE_FAILED = 8
EXIT_IMPORT_SMOKE_FAILED = 10

#: Paketin İÇİNDE çalışma anında bulunması ZORUNLU üçüncü taraf modüller.
#:
#: K7 borcunun (CLAUDE.md §2) son halkası. Zincirin ilk üç halkası STATİKTİR ve
#: bir modülün pakete gerçekten girdiğini kanıtlamaz:
#:   requirements.txt → DAGITIM_IMPORT_ESLEME → spec hiddenimports
#: Bu liste dördüncü halkadır: paketlenmiş ikili her derlemede modülleri
#: GERÇEKTEN import eder. `--pdf-duman` yalnız WeasyPrint zincirini sınar;
#: 30.08.2026'da `xlrd` eklendiğinde onun paketlenip paketlenmediğini sınayan
#: hiçbir kapı olmadığı görüldü (e-Okul .xls içe aktarımı sahada çökebilirdi).
#:
#: Liste `backend/requirements.txt` ile senkron tutulur; kaymayı
#: `packaging/tests/test_spec_kapsami.py` kapıya bağlar.
RUNTIME_MODULES: tuple[str, ...] = (
    "django",
    "rest_framework",
    "argon2",
    "cryptography",
    "openpyxl",
    "xlrd",
    "PIL",
    "weasyprint",
    "pypdf",
    "whitenoise",
    "waitress",
)

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
    <img src="{photo}" alt="" style="width: 12mm; height: 16mm" />
  </body>
</html>
"""

# PDF'te JPEG görselin süzgeç adı (WeasyPrint JPEG'i yeniden kodlamadan gömer).
JPEG_FILTER = "/DCTDecode"


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


def _pdf_image_filters(pdf_path: Path) -> list[str]:
    """PDF'in ilk sayfasındaki görsellerin süzgeçlerini döndürür.

    Görsel sayfa kaynağında ya da bir form nesnesinin içinde durabilir; ikisine
    de bakılır (derinlik sınırlı — kendini gösteren form döngüye sokmasın).
    """
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    resources = reader.pages[0].get("/Resources")
    if resources is None:
        return []
    filters: list[str] = []
    bekleyen = [(resources.get_object(), 0)]
    while bekleyen:
        kaynak, derinlik = bekleyen.pop()
        xobjects = kaynak.get("/XObject")
        if xobjects is None:
            continue
        for value in xobjects.get_object().values():
            nesne = value.get_object()
            if nesne.get("/Subtype") == "/Image":
                filters.append(str(nesne.get("/Filter", "")))
            elif nesne.get("/Resources") is not None and derinlik < 3:
                bekleyen.append((nesne["/Resources"].get_object(), derinlik + 1))
    return filters


def _smoke_photo_uri() -> str:
    """Duman fotoğrafı: Pillow ile ÇALIŞMA ANINDA kodlanmış küçük bir JPEG.

    Depoya ikili gömülmez; öğrenci fotoğrafının yolunu (Pillow JPEG kodlayıcı →
    data URI → WeasyPrint) birebir izler. Kodlayıcı pakette yoksa burada düşer.
    """
    import base64
    import io

    from PIL import Image

    tampon = io.BytesIO()
    Image.new("RGB", (30, 40), (170, 60, 60)).save(tampon, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(tampon.getvalue()).decode("ascii")


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
    """Türkçe metinli, fotoğraflı PDF üretir, geri okuyup doğrular; 0 = başarılı."""
    from weasyprint import HTML

    target.parent.mkdir(parents=True, exist_ok=True)
    html = _SMOKE_HTML.format(sample=TURKISH_SAMPLE, photo=_smoke_photo_uri())
    HTML(string=html).write_pdf(str(target))
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

    filters = _pdf_image_filters(target)
    if not any(JPEG_FILTER in filtre for filtre in filters):
        _write(
            f"HATA: PDF'e JPEG fotoğraf gömülmemiş (bulunan görseller: {filters}). "
            "Pillow JPEG eklentisi ya da WeasyPrint görsel zinciri pakette eksik; "
            "salon evrakının oturma planı fotoğrafsız basılır."
        )
        return EXIT_PDF_SMOKE_FAILED

    _write(f"PDF duman testi başarılı: {target}")
    _write(f"Fontlar: {sorted(fonts)}")
    _write(f"Görseller: {filters}")
    return 0


def run_import_smoke() -> int:
    """`RUNTIME_MODULES`'ın tamamını import eder; 0 = hepsi pakette.

    Django ayağa KALDIRILMAZ, veri dizinine dokunulmaz — yalnız modül çözümü
    sınanır. Bir modül eksikse paket "geliştirmede çalışıyor, kurulumda
    çöküyor" sınıfına girer; hangi modülün düştüğü tek tek yazılır.
    """
    import importlib

    eksik: list[str] = []
    for modul in RUNTIME_MODULES:
        try:
            importlib.import_module(modul)
        except Exception as hata:  # noqa: BLE001 — teşhis kipi: her hata rapor edilir
            eksik.append(f"{modul} ({hata!r})")

    if eksik:
        _write("HATA: şu modüller pakette çözülemedi (K7 hiddenimports eksiği):")
        for satir in eksik:
            _write(f"  - {satir}")
        _write("Düzeltme: packaging/pyinstaller/kelebek_sinav.spec → hiddenimports.")
        return EXIT_IMPORT_SMOKE_FAILED

    _write(f"Bağımlılık duman testi başarılı: {len(RUNTIME_MODULES)} modül çözüldü.")
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
    if IMPORT_SMOKE_FLAG in args:
        try:
            return run_import_smoke()
        except Exception as error:  # noqa: BLE001 — teşhis kipi: her hata rapor edilir
            _write(f"HATA: bağımlılık duman testi çöktü: {error!r}")
            return EXIT_IMPORT_SMOKE_FAILED

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
