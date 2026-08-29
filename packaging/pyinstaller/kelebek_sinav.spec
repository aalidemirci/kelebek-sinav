# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Kelebek Sınav (Windows + Linux ORTAK).

Kullanım (depo kökünden):

    pyinstaller --noconfirm --clean packaging/pyinstaller/kelebek_sinav.spec

Ortam değişkenleri:
    KS_WITH_QT=0   → PyQt5/QtWebEngine paketlenmez (yalnız `--autotest`/CI
                     doğrulaması için küçük ve hızlı derleme; pencere AÇILMAZ).
    KS_DLL_DIR     → (Windows) `dll_kapanisi.py` ile üretilmiş DLL klasörü.

--------------------------------------------------------------------------
TASARIMDAN BİLİNÇLİ SAPMA — backend KAYNAK OLARAK paketlenir
--------------------------------------------------------------------------
Tasarım §5.1 `collect_submodules('apps')` diyor, yani Django uygulamalarının
donmuş arşive gömülmesini. BURADA BAŞKA YOL SEÇİLDİ: `backend/` ağacı KAYNAK
DOSYA olarak pakete kopyalanır, çalışma anında `desktop.django_bootstrap`
`sys.path`'e ekler. Gerekçeler:

1. `desktop/paths.py::resolve_backend_dir()` paketin içinde gerçek bir
   `backend/config/settings.py` DOSYASI arar ve bulamazsa açılışı durdurur.
   Donmuş arşive gömülen modüller diskte dosya olarak görünmez; kabuk yeniden
   yazılmadan donmuş yol çalışmaz (kabuk bu görevin dosya sahipliği dışında).
2. Django'nun göç yükleyicisi, şablon yükleyicisi ve uygulama keşfi dosya
   sistemine dayanır; kaynak ağaç bu üç mekanizmayı da tuzaksız çalıştırır
   ("migrations dinamik import tuzağı" bu yolda hiç doğmaz).
3. Sahada teşhis kolaylaşır: bir şablonun içeriği okunabilir/düzeltilebilir.

BEDELİ: diskteki kaynak kodu PyInstaller'ın statik çözümleyicisi TARAMAZ.
Dolayısıyla backend'in kullandığı ÜÇÜNCÜ TARAF paketler bu dosyada AÇIKÇA
`hiddenimports` olarak sayılmak ZORUNDADIR. Backend'e yeni bir üçüncü taraf
bağımlılık eklenirse buraya da eklenmelidir; unutulursa paket "geliştirmede
çalışıyor, kurulumda çöküyor" hatası verir. `--pdf-duman` duman testi bu sınıf
hataların en tehlikelisini (WeasyPrint zinciri) her derlemede yakalar.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyInstaller.building.datastruct import Tree
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

# `SPECPATH` PyInstaller tarafından tanımlanır (spec dosyasının bulunduğu dizin).
REPO = Path(SPECPATH).resolve().parents[1]  # noqa: F821 — PyInstaller global'i

WINDOWS = sys.platform.startswith("win")
WITH_QT = os.environ.get("KS_WITH_QT", "1").strip() not in {"0", "false", "no"}

DIST_NAME = "kelebek-sinav"
ENTRY = REPO / "packaging" / "pyinstaller" / "giris.py"
RUNTIME_HOOK = REPO / "packaging" / "pyinstaller" / "rthook_ks.py"
ICON = REPO / "packaging" / "ikonlar" / "kelebek-sinav.ico"

# ---------------------------------------------------------------------------
# Kaynak ağaçları (kaynak dosya olarak kopyalanır)
# ---------------------------------------------------------------------------
_TREE_EXCLUDES = ["__pycache__", "tests", "*.pyc", "*.pyo", ".pytest_cache", ".mypy_cache"]

trees = [
    Tree(str(REPO / "backend" / "config"), prefix="backend/config", excludes=_TREE_EXCLUDES),
    Tree(str(REPO / "backend" / "apps"), prefix="backend/apps", excludes=_TREE_EXCLUDES),
    Tree(str(REPO / "backend" / "shared"), prefix="backend/shared", excludes=_TREE_EXCLUDES),
    Tree(str(REPO / "backend" / "templates"), prefix="backend/templates", excludes=_TREE_EXCLUDES),
    # MEB ders çizelgesi verisi (K5): settings.CATALOG_DIR paketli kipte
    # backend ağacının YANINDAKİ data/ klasörünü arar — tembel tohum buradan okur.
    Tree(
        str(REPO / "data" / "ders-cizelgeleri"),
        prefix="data/ders-cizelgeleri",
        excludes=_TREE_EXCLUDES,
    ),
    # Derlenmiş SPA — `frontend/dist` boşsa paket açılır ama beyaz ekran verir;
    # `packaging/linux/build.sh` bunu derleme öncesi denetler.
    Tree(str(REPO / "frontend" / "dist"), prefix="frontend/dist", excludes=_TREE_EXCLUDES),
]

datas: list[tuple[str, str]] = [
    # Sürüm damgası — `desktop/version.py` paket kökünde arar.
    (str(REPO / "VERSION"), "."),
    # Kullanıcıya dağıtılan her kopyada bağlayıcı lisans metni bulunur.
    (str(REPO / "LICENSE"), "."),
    # WinForms pencere ikonu çalışma anında `desktop/window.py` tarafından atanır.
    (str(ICON), "."),
]

# ---------------------------------------------------------------------------
# Fontlar + Windows font yapılandırması
# ---------------------------------------------------------------------------
# Tasarım §5.1: Windows'ta YALNIZ gömülü DejaVu kullanılır. Linux'ta sistem
# fontu (.deb bağımlılığı `fonts-dejavu-core`) kullanılır; yine de fontlar
# pakete konur ki taşınabilir `.tar.gz` kurulumunda font eksikse metin
# bozulmasın — Linux'ta `FONTCONFIG_FILE` AYARLANMAZ, bu kopya atıl durur.
for ttf in sorted((REPO / "packaging" / "fontlar").glob("*.ttf")):
    datas.append((str(ttf), "fonts"))
datas.append((str(REPO / "packaging" / "fontlar" / "DejaVu-LISANS.txt"), "fonts"))
datas.append((str(REPO / "packaging" / "pyinstaller" / "fonts.conf.tmpl"), "."))

# ---------------------------------------------------------------------------
# Üçüncü taraf paket verileri
# ---------------------------------------------------------------------------
datas += collect_data_files("django")  # tr yerelleştirmesi, şablonlar, .mo dosyaları
datas += collect_data_files("rest_framework")
datas += collect_data_files("weasyprint")  # gömülü CSS'ler (html5_ua.css …)
datas += collect_data_files("pyphen")  # heceleme sözlükleri
datas += collect_data_files("tinyhtml5")
datas += collect_data_files("webview")  # Windows: WebView2 köprü DLL'leri

# ---------------------------------------------------------------------------
# Windows DLL kapanışı (ntldd/objdump ile üretilir — elle liste YOK)
# ---------------------------------------------------------------------------
binaries: list[tuple[str, str]] = []
binaries += collect_dynamic_libs("webview")

if WINDOWS:
    dll_dir = Path(os.environ.get("KS_DLL_DIR", str(REPO / "packaging" / "windows" / "dll")))
    if not dll_dir.is_dir():
        raise SystemExit(
            f"DLL klasörü yok: {dll_dir}. Önce `python packaging/windows/dll_kapanisi.py` "
            "çalıştırın (tasarım §5.1)."
        )
    dll_files = sorted(dll_dir.glob("*.dll"))
    if not dll_files:
        raise SystemExit(f"DLL klasörü boş: {dll_dir}.")
    for dll in dll_files:
        # Paket köküne konur; `rthook_ks.py` WEASYPRINT_DLL_DIRECTORIES ile gösterir.
        binaries.append((str(dll), "."))

# ---------------------------------------------------------------------------
# Gizli import'lar — diskteki backend kodunun ihtiyaç duyduğu her paket
# ---------------------------------------------------------------------------
hiddenimports: list[str] = []
hiddenimports += collect_submodules("django")
hiddenimports += collect_submodules("rest_framework")
hiddenimports += collect_submodules("whitenoise")
hiddenimports += collect_submodules("waitress")
hiddenimports += collect_submodules("weasyprint")
hiddenimports += collect_submodules("fontTools")
hiddenimports += collect_submodules("openpyxl")
hiddenimports += collect_submodules("pypdf")
hiddenimports += collect_submodules("webview")
hiddenimports += [
    # WeasyPrint zinciri
    "pydyf",
    "tinycss2",
    "cssselect2",
    "tinyhtml5",
    "pyphen",
    "PIL",
    "PIL.Image",
    "brotli",
    "zopfli",
    # Opsiyonel açılış parolası (F5-D5): Argon2id cffi ikilisi `argon2` ile
    # otomatik toplanmayabilir; eksikse parola kurulu kurulumlar HİÇ açılmaz ve
    # `--pdf-duman` bunu yakalamaz (ayrı zincir).
    "argon2",
    "argon2.low_level",
    "_argon2_cffi_bindings",
    "cryptography.fernet",
    # Backend yardımcıları
    "filetype",
    "sqlparse",
    "platformdirs",
    # Django SQLite arka ucu (dizeyle import edilir)
    "django.db.backends.sqlite3",
    "django.db.backends.sqlite3.base",
    # F5-D5 (opsiyonel parola) için: alan şifrelemesi + Argon2id
    "cryptography",
    "cryptography.fernet",
    "argon2",
]

if WITH_QT:
    # PyInstaller'ın PyQt5 kancaları QtWebEngineProcess yardımcı sürecini,
    # kaynak dosyalarını ve çevirileri bu import üzerinden toplar.
    hiddenimports += [
        "PyQt5",
        "PyQt5.QtCore",
        "PyQt5.QtGui",
        "PyQt5.QtWidgets",
        "PyQt5.QtWebEngineWidgets",
        "PyQt5.QtWebEngineCore",
        "PyQt5.QtNetwork",
        "PyQt5.QtPrintSupport",
        "webview.platforms.qt",
    ]

# ---------------------------------------------------------------------------
# Dışlananlar — paket boyutu + AV yanlış-pozitif yüzeyi
# ---------------------------------------------------------------------------
excludes = [
    "tkinter",
    "pytest",
    "_pytest",
    "factory",
    "faker",
    "coverage",
    "mypy",
    "ruff",
    "django_stubs_ext",
    "IPython",
    "numpy",
    "matplotlib",
    "psycopg",
    "psycopg2",
    "redis",
    "celery",
]
if not WITH_QT:
    excludes += ["PyQt5", "PyQt6", "PySide2", "PySide6"]

a = Analysis(  # noqa: F821 — PyInstaller global'i
    [str(ENTRY)],
    pathex=[str(REPO)],
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(RUNTIME_HOOK)],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)  # noqa: F821 — PyInstaller global'i

exe = EXE(  # noqa: F821 — PyInstaller global'i
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=DIST_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX KAPALI: sıkıştırılmış çalıştırılabilirler antivirüs yanlış-pozitifinin
    # başlıca kaynağıdır (tasarım §9 "AV false-positive").
    upx=False,
    # Windows'ta konsol penceresi açılmaz. Teşhis çıktısı günlük dosyasına ve
    # süreç çıkış koduna düşer (`--autotest`, `--pdf-duman`).
    console=not WINDOWS,
    disable_windowed_traceback=False,
    icon=str(ICON) if (WINDOWS and ICON.is_file()) else None,
)

coll = COLLECT(  # noqa: F821 — PyInstaller global'i
    exe,
    a.binaries,
    a.datas,
    *trees,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=DIST_NAME,
)
