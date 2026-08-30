"""`--geri-yukle` — yedekten geri yükleme konsol akışı (masaüstü kabuğu).

Bütünlük denetimi bozuk veritabanıyla pencereyi AÇMAZ (desktop/integrity.py);
kullanıcının o noktadaki tek çıkış yolu bu kiptir. Çekirdek iş
`apps.okul.services.backup_restore` içindedir; burası yalnız konsol
etkileşimini ve masaüstü tesisatını (kilit, yollar, Django hazırlığı) yönetir.

WINDOWS PAKETİ PENCERESİZDİR (`console=False`, kelebek_sinav.spec): std
akımlar None'dır, `input()`/`getpass()` çalışmaz. Bu kip kendi konsol
penceresini AÇAR (AllocConsole) — mevcut bir cmd/PowerShell konsoluna
İLİŞTİRİLMEZ: bekleyen kabuk aynı konsoldan okumaya devam ettiği için yazılan
parola kabuk istemine düşebilirdi (ekranda yankılanır, hatta komut olarak
çalışırdı). Ayrı pencere bu yarışı kökten keser ve akış "Başlat > Çalıştır"
üzerinden, hiç terminal bilmeden de kullanılabilir (kurulum Başlat menüsüne
"Yedekten Geri Yükle" kısayolu koyar — kelebek-sinav.iss).

Django BURADA AYAĞA KALDIRILIR ama veritabanına DOKUNULMAZ: `prepare_django`
yalnız ayarları ve uygulama kayıt defterini yükler; göç ve bütünlük denetimi
bu kipte KOŞULMAZ (bozuk veritabanı bu kipin varlık sebebidir).
"""

from __future__ import annotations

import argparse
import logging
import sys
from getpass import getpass
from pathlib import Path
from typing import Any

from desktop.backup_crypto import BACKUP_SUFFIX, MAGIC, BackupCryptoError
from desktop.dialogs import show_error
from desktop.django_bootstrap import prepare_django
from desktop.errors import EXIT_OK, EXIT_RESTORE_FAILED, AlreadyRunningError
from desktop.lock import SingleInstanceLock
from desktop.paths import AppPaths, resolve_backend_dir

logger = logging.getLogger("kelebek_sinav.restore")

# Kendi açtığımız konsol penceresi süreçle birlikte kapanır; sonucu okutmak
# için çıkışta Enter beklenir. Yalnız AllocConsole başarılıysa True olur.
_allocated = False


class RestoreCliError(Exception):
    """Akışı durduran, kullanıcıya olduğu gibi gösterilecek Türkçe mesaj."""


def run_restore(paths: AppPaths, args: argparse.Namespace) -> int:
    """Geri yükleme kipinin girişi; tek-instance kilidini kendisi alır."""
    lock = SingleInstanceLock(paths.lock_path)
    try:
        lock.acquire()
    except AlreadyRunningError as exc:
        show_error(exc.title, "Geri yükleme için önce açık olan programı kapatın.")
        return exc.exit_code
    try:
        return _restore_flow(paths, args)
    finally:
        lock.release()


def _restore_flow(paths: AppPaths, args: argparse.Namespace) -> int:
    interactive = False
    kod = EXIT_RESTORE_FAILED
    try:
        interactive = ensure_console()
        kod = _run_steps(paths, args, interactive)
    except RestoreCliError as hata:
        _report_error(str(hata), interactive)
    except Exception:  # noqa: BLE001 — kip her hatada Türkçe mesajla bitmeli
        logger.exception("Geri yükleme beklenmeyen hatayla durdu.")
        _report_error(
            "Geri yükleme beklenmeyen bir hatayla durdu; ayrıntı veri klasöründeki "
            "logs/uygulama.log dosyasındadır.",
            interactive,
        )
    _pause_before_exit(skip=bool(getattr(args, "evet", False)))
    return kod


def _run_steps(paths: AppPaths, args: argparse.Namespace, interactive: bool) -> int:
    # Ayarlar + uygulama kaydı; sorgu YOK (backup_restore importu bunu ister).
    prepare_django(resolve_backend_dir(), paths.data)
    servis = _load_service()

    if interactive:
        print("Kelebek Sınav — yedekten geri yükleme")
        print(f"Veri klasörü : {paths.data}")
        print(f"Yedek klasörü: {paths.backups}\n")

    yedek = _choose_backup(paths, args, interactive)
    if yedek is None:
        if interactive:
            print("Geri yükleme iptal edildi.")
        return EXIT_OK

    sifreli = _is_encrypted(yedek)
    parola: str | None = str(getattr(args, "parola", "") or "") or None
    anahtar: str | None = str(getattr(args, "kurtarma_anahtari", "") or "") or None
    if sifreli and not parola and not anahtar:
        if not interactive:
            raise RestoreCliError(
                "Bu yedek şifreli; --parola ya da --kurtarma-anahtari verin veya "
                "komutu etkileşimli bir uçbirimden çalıştırın."
            )
        parola, anahtar = _ask_secret()

    if interactive:
        print(f"\nYedek : {yedek.name} ({'şifreli' if sifreli else 'düz'})")
        print(f"Hedef : {paths.db_path}")
        print("Mevcut veritabanı silinmez; 'db-onceki-*' adıyla aynı klasörde saklanır.")
    if not args.evet:
        if not interactive:
            raise RestoreCliError("Onay sorusu sorulamadı (konsol yok); --evet ile çalıştırın.")
        if not _confirm():
            print("Geri yükleme iptal edildi.")
            return EXIT_OK

    try:
        sonuc = servis.restore_database(yedek, paths.db_path, password=parola, recovery_key=anahtar)
    except (BackupCryptoError, servis.BackupRestoreError) as hata:
        raise RestoreCliError(str(hata)) from hata

    logger.info("Yedekten geri yükleme tamamlandı: %s", yedek.name)
    if interactive:
        print("\nGeri yükleme tamamlandı.")
        if sonuc.old_db_path is not None:
            print(f"Önceki veritabanı kenara alındı: {sonuc.old_db_path}")
        if sonuc.state_written:
            print("guvenlik.json yedekteki kurtarma başlığından yeniden yazıldı.")
        print("Programı şimdi normal şekilde açabilirsiniz.")
    return EXIT_OK


# ---------------------------------------------------------------------------
# Konsol tesisatı
# ---------------------------------------------------------------------------
def ensure_console() -> bool:
    """Etkileşimli konsol akımlarını hazırlar; başarısızsa False döner."""
    if sys.stdin is not None and sys.stdout is not None:
        return True
    if sys.platform != "win32":
        return False

    global _allocated
    import ctypes

    kernel32 = ctypes.windll.kernel32
    if kernel32.GetConsoleWindow() == 0:
        if not kernel32.AllocConsole():
            return False
        _allocated = True
    # Türkçe karakterler için UTF-8 kod sayfası; akımlar yeni konsola bağlanır.
    kernel32.SetConsoleCP(65001)
    kernel32.SetConsoleOutputCP(65001)
    kernel32.SetConsoleTitleW("Kelebek Sınav — yedekten geri yükleme")
    try:
        sys.stdin = open("CONIN$", encoding="utf-8")
        sys.stdout = open("CONOUT$", "w", encoding="utf-8")
        sys.stderr = open("CONOUT$", "w", encoding="utf-8")
    except OSError:
        return False
    return True


def _pause_before_exit(*, skip: bool) -> None:
    """Kendi konsol penceremiz varsa kullanıcı sonucu okuyana dek bekler."""
    if not _allocated or skip:
        return
    try:
        input("\nKapatmak için Enter tuşuna basın...")
    except (EOFError, OSError):
        pass


def _report_error(message: str, interactive: bool) -> None:
    logger.error("Geri yükleme başarısız: %s", message)
    if interactive:
        print(f"\nHATA: {message}")
    else:
        show_error("Geri yükleme başarısız", message)


# ---------------------------------------------------------------------------
# Yedek seçimi ve sır istemleri
# ---------------------------------------------------------------------------
def list_backups(backup_dir: Path) -> list[Path]:
    """Geri yüklenebilir `.ksbak` dosyaları — en yeniden eskiye."""
    if not backup_dir.is_dir():
        return []
    dosyalar = [yol for yol in backup_dir.glob(f"*{BACKUP_SUFFIX}") if yol.is_file()]
    dosyalar.sort(key=lambda yol: yol.stat().st_mtime, reverse=True)
    return dosyalar


def _is_encrypted(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(len(MAGIC)) == MAGIC
    except OSError:
        return False


def _choose_backup(paths: AppPaths, args: argparse.Namespace, interactive: bool) -> Path | None:
    istenen = str(args.geri_yukle or "")
    if istenen:
        yol = Path(istenen).expanduser()
        if yol.is_file():
            return yol
        # Yalnız dosya adı verildiyse yedek klasöründe aranır.
        aday = paths.backups / istenen
        if aday.is_file():
            return aday
        raise RestoreCliError(f"Yedek dosyası bulunamadı: {istenen}")
    if not interactive:
        raise RestoreCliError("Yedek dosyası belirtilmedi ve seçim için konsol açılamadı.")
    yedekler = list_backups(paths.backups)
    if not yedekler:
        raise RestoreCliError(f"Yedek klasöründe geri yüklenebilir dosya yok: {paths.backups}")
    return _pick_backup(yedekler)


def _pick_backup(yedekler: list[Path]) -> Path | None:
    print("Geri yüklenebilir yedekler (en yeniden eskiye):")
    for sira, yol in enumerate(yedekler, start=1):
        kip = "şifreli" if _is_encrypted(yol) else "düz"
        boyut = max(1, yol.stat().st_size // 1024)
        print(f"  {sira:2d}) {yol.name}  ({kip}, {boyut} KB)")
    while True:
        try:
            secim = input("Geri yüklenecek yedeğin numarası (vazgeçmek için boş bırakın): ").strip()
        except EOFError:
            return None
        if not secim:
            return None
        if secim.isdigit() and 1 <= int(secim) <= len(yedekler):
            return yedekler[int(secim) - 1]
        print("Geçersiz seçim; listedeki numaralardan birini yazın.")


def _ask_secret() -> tuple[str | None, str | None]:
    """(parola, kurtarma anahtarı) — biri dolu döner."""
    try:
        parola = getpass("Uygulama parolası (kurtarma anahtarıyla açmak için boş bırakın): ")
    except EOFError:
        parola = ""
    if parola:
        return parola, None
    try:
        anahtar = input("Kurtarma anahtarı (yazdırdığınız kâğıttaki): ").strip()
    except EOFError:
        anahtar = ""
    if not anahtar:
        raise RestoreCliError("Parola ya da kurtarma anahtarı girilmedi.")
    return None, anahtar


def _confirm() -> bool:
    try:
        yanit = input("Devam edilsin mi? [e/H] ").strip().lower()
    except EOFError:
        return False
    return yanit in {"e", "evet"}


def _load_service() -> Any:
    """Backend çekirdeğini yükler (Django hazırlandıktan SONRA çağrılır).

    Import fonksiyon içindedir: masaüstü birim testleri asgari Django
    ayarlarıyla koşar ve `apps.okul` ancak gerçek ayarlarla import edilebilir.
    """
    from apps.okul.services import backup_restore

    return backup_restore
