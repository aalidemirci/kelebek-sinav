"""Kelebek Sınav masaüstü başlatıcısı — açılış sırası (tasarım §5.3).

    1. Veri dizinleri (exe DIŞINDA) + günlük yapılandırması
    2. Tek-instance kilidi ................. ikinci kopya pencere AÇMAZ
    3. Oturum belirteci ..................... ayarlar okunmadan ÖNCE üretilir
    4. Sürüm damgası ........................ eski program yeni veriyi AÇMAZ
    5. Bütünlük denetimi .................... bozuk veriyle pencere AÇILMAZ
    6. Günlük yedek + 14 gün rotasyonu ...... `Connection.backup()`
    7. Göç öncesi yedek + `migrate --no-input`
    8. Gömülü sunucu (waitress, 127.0.0.1, boş port) + sağlık denetimi
    9. Pencere (pywebview) — `--autotest` kipinde AÇILMAZ

Adım sırası bilinçlidir: bütünlük denetimi yedeklemeden ÖNCE koşar; veritabanı
bozukken rotasyonun sağlam eski yedekleri silmesi istenmez.

Herhangi bir adım başarısız olursa pencere açılmaz; kullanıcıya Türkçe ileti +
"son yedekten dön" yolu gösterilir ve hataya özel bir çıkış kodu döner (CI ve
paket kurulum testleri bu kodlara bakar).
"""

from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Sequence

from desktop.backup import (
    daily_backup,
    encrypt_legacy_backups,
    pre_migrate_backup,
    rotate_backups,
)
from desktop.dialogs import show_error
from desktop.django_bootstrap import (
    assert_session_guard_installed,
    build_wsgi_application,
    has_pending_migrations,
    prepare_django,
    run_migrations,
)
from desktop.errors import EXIT_OK, EXIT_UNEXPECTED, StartupError
from desktop.integrity import check_database_integrity
from desktop.lock import SingleInstanceLock
from desktop.logging_setup import configure_logging
from desktop.paths import (
    ENV_APP_HOME,
    AppPaths,
    check_sync_hazard,
    resolve_app_paths,
    resolve_backend_dir,
)
from desktop.server import BackgroundServer, check_health
from desktop.session_guard import ENV_TOKEN, generate_session_token, window_url
from desktop.version import (
    ensure_stamp_compatible,
    get_app_version,
    write_version_stamp,
)
from desktop.window import open_window, require_window_runtime

logger = logging.getLogger("kelebek_sinav")

_UNEXPECTED_MESSAGE = "Program açılırken beklenmeyen bir hata oluştu."
_UNEXPECTED_HINT = (
    "Programı yeniden başlatmayı deneyin. Sorun sürerse veri klasöründeki "
    "logs/uygulama.log dosyasını okul bilişim sorumlusuna iletin."
)


def build_parser() -> argparse.ArgumentParser:
    """Komut satırı arayüzü."""
    parser = argparse.ArgumentParser(
        prog="kelebek-sinav",
        description="Kelebek Sınav — çevrimdışı sınav planlama masaüstü programı.",
    )
    parser.add_argument(
        "--autotest",
        action="store_true",
        help="Pencere açmadan açılış adımlarını koşar, sağlık denetimi yapıp çıkar.",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Veri klasörünü değiştirir (taşınabilir kip ve testler için).",
    )
    return parser


def resolve_paths(args: argparse.Namespace) -> AppPaths:
    """`--data-dir` verildiyse yerleşimi ona bağlar."""
    if args.data_dir:
        os.environ[ENV_APP_HOME] = str(args.data_dir)
    return resolve_app_paths()


def prepare_data(paths: AppPaths, app_version: str) -> None:
    """Veriyi açılışa hazırlar: sürüm → bütünlük → yedek → göç → damga."""
    ensure_stamp_compatible(paths.version_stamp_path, app_version)
    check_database_integrity(paths.db_path, backup_dir=paths.backups)

    encrypt_legacy_backups(paths.backups, paths.data)
    daily_backup(paths.db_path, paths.backups)
    rotate_backups(paths.backups)

    prepare_django(resolve_backend_dir(), paths.data)
    if has_pending_migrations():
        pre_migrate_backup(paths.db_path, paths.backups, app_version)
    run_migrations()
    write_version_stamp(paths.version_stamp_path, app_version)


def serve(paths: AppPaths, token: str, autotest: bool) -> int:
    """Gömülü sunucuyu başlatır; `--autotest` değilse pencereyi açar."""
    application = build_wsgi_application()
    assert_session_guard_installed()

    server = BackgroundServer(application)
    server.start()
    try:
        server.wait_until_ready()
        check_health(server.base_url, token)
        if autotest:
            logger.info("Açılış denetimi başarılı.")
            return EXIT_OK
        require_window_runtime()
        open_window(
            window_url(server.base_url, token),
            storage_path=paths.webview_storage_path,
        )
        return EXIT_OK
    finally:
        server.stop()


def run(argv: Sequence[str] | None = None) -> int:
    """Programı çalıştırır ve süreç çıkış kodunu döndürür."""
    args = build_parser().parse_args(argv)
    paths = resolve_paths(args)
    paths.ensure()
    configure_logging(paths.logs, echo=args.autotest)

    # PyInstaller çalışma-zamanı kancası günlük yapılandırmasından ÖNCE koşar;
    # uyarısını env'e bırakır, buraya kadar taşınmazsa sessizce kaybolurdu.
    rthook_uyarisi = os.environ.pop("KS_RTHOOK_UYARI", "")
    if rthook_uyarisi:
        logger.warning("Paket ortamı uyarısı: %s", rthook_uyarisi)

    app_version = get_app_version()
    logger.info("Kelebek Sınav %s başlıyor.", app_version)
    hazard = check_sync_hazard(paths.root)
    if hazard:
        logger.warning("%s", hazard)

    lock = SingleInstanceLock(paths.lock_path)
    try:
        lock.acquire()
        try:
            # Belirteç, ayarlar okunmadan ÖNCE üretilir: `config/settings.py`
            # middleware'i bu değişkene bakarak ekler.
            token = generate_session_token()
            os.environ[ENV_TOKEN] = token
            prepare_data(paths, app_version)
            return serve(paths, token, args.autotest)
        finally:
            os.environ.pop(ENV_TOKEN, None)
            lock.release()
    except StartupError as exc:
        logger.error("Açılış durdu: %s", exc.message)
        show_error(exc.title, exc.full_message)
        return exc.exit_code
    except Exception:
        logger.exception("Açılışta beklenmeyen hata.")
        show_error("Kelebek Sınav açılamadı", f"{_UNEXPECTED_MESSAGE}\n\n{_UNEXPECTED_HINT}")
        return EXIT_UNEXPECTED


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
