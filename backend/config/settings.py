"""Kelebek Sınav — Django ayarları (tek dosya, tek kullanıcılı masaüstü uygulama).

OYS'nin (Okul Yönetim Sistemi) çok-kullanıcılı/ağ-merkezli ayar dosyasının
(config/settings/{base,dev,prod}.py) aksine burada TEK dosya yeterli: bu program
LAN/internet servisi sunmaz, tek kullanıcı tek bilgisayarda çalıştırır. Sırlar
`django-environ` OLMADAN doğrudan `os.environ` üzerinden okunur (bağımlılık
yüzeyi küçük tutulur — görev brifi).
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Veri dizini — masaüstü paket kurulumunda platform veri dizinine bağlanır
# ---------------------------------------------------------------------------
# `KS_DATA_DIR` env değişkeni ile geçersiz kılınabilir (Electron/PyInstaller
# paketleyicisi `platformdirs.user_data_dir()` sonucunu buraya verecek).
# Varsayılan geliştirmede `backend/data/` (repo içi, .gitignore'da).
DATA_DIR = Path(os.environ.get("KS_DATA_DIR", str(BASE_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _bool_env(name: str, default: bool) -> bool:
    """Basit boolean env okuyucu (django-environ yok — settings sade kalsın)."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Güvenlik
# ---------------------------------------------------------------------------
# Yerel tek-kullanıcılı masaüstü uygulaması — ağ üzerinden erişilmez, bu yüzden
# sabit bir geliştirme anahtarı güvenlik riski oluşturmaz (kriptografik oturum
# yok). Üretim paketlemesinde `KS_SECRET_KEY` env ile geçersiz kılınabilir.
SECRET_KEY = os.environ.get(
    "KS_SECRET_KEY",
    "django-insecure-kelebek-sinav-yerel-masaustu-gelistirme-anahtari",
)

# Varsayılan FALSE (KVKK): DEBUG hata sayfası yerel değişkenlerdeki ham
# TCKN/telefonu döker — paketlenmiş uygulamada asla açık kalmamalı. Geliştirme
# ortamı docker-compose.yml'de KS_DEBUG=1 ile açar.
DEBUG = _bool_env("KS_DEBUG", False)

# Vite geliştirme proxy'si Docker Compose ağında servise ``backend`` adıyla
# ulaşır (frontend/vite.config.ts). Üretim masaüstü sunucusu yine yalnız
# 127.0.0.1'e bağlanır; bu ad yalnız kapalı geliştirme ağı içindir.
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "backend"]

# ---------------------------------------------------------------------------
# Uygulamalar
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.okul",
    "apps.dersler",
    "apps.sinav",
]

# ---------------------------------------------------------------------------
# MEB ders çizelgesi verisi (K5 — pakete gömülü, tembel tohum)
# ---------------------------------------------------------------------------
# Paketli çalışmada `data/` klasörü backend ağacının YANINDA durur (PyInstaller
# spec bunu kopyalar); geliştirme konteynerinde compose `KS_CATALOG_DIR` ile
# /repo yolunu verir. Dosya yoksa tohum sessizce atlanır (TB2 — elle ekleme açık).
CATALOG_DIR = Path(
    os.environ.get("KS_CATALOG_DIR", str(BASE_DIR.parent / "data" / "ders-cizelgeleri"))
)
COURSE_ALIAS_FILE = Path(
    os.environ.get("KS_COURSE_ALIAS_FILE", str(CATALOG_DIR / "ders-adi-takma-adlari.md"))
)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    # Yedekten geri yükleme uygulandıktan sonra "yeniden başlat" kapısı: süreç
    # içi durum (bellekteki anahtar, bekleyen göçler) diskteki veriyi artık
    # tarif etmez; tüm API 503 restart_required ile kesilir. Kilit kapısından
    # ÖNCE durur — geri yükleme kilit durumunu da bayatlatır.
    "apps.okul.restart_gate.RestartRequiredMiddleware",
    # Opsiyonel açılış parolası kapısı (tasarım §5): parola kuruluysa ve kilit
    # açılmadıysa veri uçlarını 423 Locked ile keser. Parola kurulu değilse
    # hiçbir şey yapmaz.
    "apps.okul.lock_middleware.AppLockMiddleware",
]

# Yerel oturum belirteci koruması (tasarım §5.3 son madde). Program authsuz
# olduğundan, gömülü sunucu ayakta iken aynı makinedeki BAŞKA bir işlem
# 127.0.0.1'e istek atıp öğrenci verisini okuyabilir. Masaüstü başlatıcısı
# (`desktop/main.py`) açılışta rastgele bir belirteç üretip `KS_SESSION_TOKEN`
# ile verir; middleware belirteçsiz istekleri 403'ler.
# Geliştirme/test koşusunda değişken boştur → middleware HİÇ yüklenmez, yani
# backend'in `desktop` paketine bağımlılığı YOKTUR.
if os.environ.get("KS_SESSION_TOKEN"):
    MIDDLEWARE.insert(0, "desktop.session_guard.SessionTokenMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Veritabanı — SQLite (tek kullanıcılı masaüstü uygulama; Postgres yok)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
        "OPTIONS": {
            # WAL: eşzamanlı okuma/yazım; foreign_keys: Django varsayılan olarak
            # açar ama açıkça belirtmek niyeti netleştirir; busy_timeout: kilit
            # çakışmasında 5 sn bekle (masaüstü uygulamada tek süreç ama arka
            # plan görevi olabilir); synchronous=NORMAL: WAL ile güvenli + hızlı.
            "init_command": (
                "PRAGMA journal_mode=WAL;"
                "PRAGMA foreign_keys=ON;"
                "PRAGMA busy_timeout=5000;"
                "PRAGMA synchronous=NORMAL;"
            ),
            "transaction_mode": "IMMEDIATE",
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Yerelleştirme
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Statik dosyalar (whitenoise — ayrı web sunucusu yok)
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = DATA_DIR / "static"
# WhiteNoise dizin yoksa her istekte uyarı basar; açılışta oluşturmak yeterli.
STATIC_ROOT.mkdir(parents=True, exist_ok=True)

# Derlenmiş SPA. Masaüstü penceresi kök URL'yi açar; burası servis edilmezse
# kullanıcı programı değil Django hata sayfasını görür (F5-D4 denetiminde
# yakalandı). Paketlenmiş çalışmada PyInstaller çalışma-zamanı kancası
# KS_FRONTEND_DIR'i doldurur; geliştirmede depodaki frontend/dist kullanılır.
FRONTEND_DIR = Path(os.environ.get("KS_FRONTEND_DIR", str(BASE_DIR.parent / "frontend" / "dist")))
# WhiteNoise SPA varlıklarını (/assets/…) doğrudan verir; index.html'i istemci
# tarafı rotalar için config/urls.py'deki catch-all döndürür.
WHITENOISE_ROOT = FRONTEND_DIR
WHITENOISE_INDEX_FILE = True

# ---------------------------------------------------------------------------
# Medya (soru belgesi PDF'leri ve kitapçık ZIP'leri — veri dizini altında)
# ---------------------------------------------------------------------------
MEDIA_ROOT = DATA_DIR / "media"

# Dosya eki yükleme sınırı (MB) — OYS varsayılanıyla aynı.
MAX_UPLOAD_SIZE_MB = int(os.environ.get("KS_MAX_UPLOAD_SIZE_MB", "20"))
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
# Tek kullanıcılı masaüstü uygulama — kimlik doğrulama YOK (yerel işletim
# sistemi oturumu zaten tek kullanıcıyı sınırlar). DEFAULT_AUTHENTICATION_CLASSES
# boş + UNAUTHENTICATED_USER None: DRF hiçbir kimlik doğrulama denemesi yapmaz.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 25,
    # `{code, message, fields}` hata sözleşmesi (tasarım §4.3; FE lib/api.ts bunu bekler).
    "EXCEPTION_HANDLER": "shared.exceptions.ks_exception_handler",
}
