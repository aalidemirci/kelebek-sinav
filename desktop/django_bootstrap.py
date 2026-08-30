"""Django'yu masaüstü kabuğu içinde ayağa kaldırma.

`backend/` dizini `sys.path`'e eklenir (paket içinde exe'nin yanındadır),
veri dizini `KS_DATA_DIR` ile settings'e bildirilir. Django içe aktarmaları
TEMBELDİR: bu modül import edildiğinde Django kurulmuş olmak zorunda değildir,
böylece `paths`/`lock`/`backup` testleri Django olmadan koşar.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from desktop.errors import MigrationError, ServerStartError
from desktop.logging_setup import apply_access_log_policy
from desktop.session_guard import ENV_TOKEN

logger = logging.getLogger("kelebek_sinav.django")

SETTINGS_MODULE = "config.settings"
ENV_DATA_DIR = "KS_DATA_DIR"
GUARD_MIDDLEWARE_PATH = "desktop.session_guard.SessionTokenMiddleware"


def prepare_django(backend_dir: Path, data_dir: Path) -> None:
    """Django'yu yapılandırır ve `django.setup()` çağırır.

    ÖNEMLİ: bu çağrıdan ÖNCE `KS_SESSION_TOKEN` ayarlanmış olmalıdır — ayar
    dosyası oturum belirteci middleware'ini o değişkene bakarak ekler ve
    ayarlar bir kez okunduktan sonra değişmez.
    """
    backend = str(backend_dir)
    if backend not in sys.path:
        sys.path.insert(0, backend)
    os.environ[ENV_DATA_DIR] = str(data_dir)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", SETTINGS_MODULE)

    import django

    django.setup()
    # `django.setup()` kendi günlük yapılandırmasını uygular ve `django.request`
    # susturmasını siler (bkz. `logging_setup.apply_access_log_policy`) → yeniden uygula.
    apply_access_log_policy()


def has_pending_migrations() -> bool:
    """Uygulanmamış göç var mı? (varsa `migrate` öncesi ayrı yedek alınır)"""
    from django.db import connections
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connections["default"])
    targets = executor.loader.graph.leaf_nodes()
    return bool(executor.migration_plan(targets))


def run_migrations() -> None:
    """`migrate --no-input` — hata halinde açılış durur (pencere açılmaz)."""
    from django.core.management import call_command

    try:
        call_command("migrate", interactive=False, verbosity=0)
    except Exception as exc:  # noqa: BLE001 — her göç hatası aynı kullanıcı akışına çıkar
        logger.exception("Veritabanı güncellemesi başarısız.")
        raise MigrationError(
            "Veritabanı güncellenemedi; program veriyi korumak için açılmadı.",
            hint=(
                "Yedek klasöründeki en son 'pre-migrate-*' veya günlük yedeği geri "
                "yüklemek için Başlat menüsündeki 'Kelebek Sınav — Yedekten Geri "
                "Yükle' kısayolunu (veya 'kelebek-sinav --geri-yukle' komutunu) "
                "çalıştırıp programı yeniden açın."
            ),
        ) from exc


def assert_session_guard_installed() -> None:
    """Fail-closed: belirteç koruması gerçekten zincirde mi?

    `KS_SESSION_TOKEN` ayarlandığı hâlde middleware yüklenmemişse (ayar dosyası
    değişmiş, sıralama bozulmuş) API kimlik doğrulamasız açılırdı. Bu sessiz
    hata veri sızıntısıdır → açılış durur.
    """
    from django.conf import settings

    if not os.environ.get(ENV_TOKEN):
        raise ServerStartError("Program başlatılamadı: oturum belirteci üretilmedi.")
    if GUARD_MIDDLEWARE_PATH not in list(settings.MIDDLEWARE):
        raise ServerStartError(
            "Program başlatılamadı: yerel erişim koruması yüklenmedi.",
            hint="Kurulum bozuk olabilir; programı yeniden kurun.",
        )


def build_wsgi_application() -> object:
    """WSGI uygulamasını üretir (middleware zinciri burada kurulur)."""
    from django.core.wsgi import get_wsgi_application

    application = get_wsgi_application()
    # `get_wsgi_application()` içeride `django.setup()`'ı TEKRAR çağırır ve Django'nun
    # günlük yapılandırması `django.request` susturmasını yeniden siler. Politika bu
    # yüzden Django'ya dokunan HER giriş noktasından sonra uygulanır; aksi hâlde
    # 4xx/5xx yanıtların istek yolu (DEBUG açıkken) konsola düşer.
    apply_access_log_policy()
    return application
