"""Açılış hataları — Türkçe mesaj + çözüm ipucu + süreç çıkış kodu.

Her hata tipinin kendi çıkış kodu vardır; `--autotest` kipi ve paket kurulum
testleri (CI) bu kodlara bakar. Mesajlar doğrudan kullanıcıya gösterilir
(`dialogs.show_error`), bu yüzden teknik terim değil eylem içerirler.
"""

from __future__ import annotations

# Süreç çıkış kodları (0 = başarılı).
EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_ALREADY_RUNNING = 2
EXIT_DATABASE_CORRUPT = 3
EXIT_SCHEMA_TOO_NEW = 4
EXIT_MIGRATION_FAILED = 5
EXIT_SERVER_FAILED = 6
EXIT_WEBVIEW_UNAVAILABLE = 7
# Paket teşhis kipi (`--pdf-duman`): Türkçe PDF üretimi/font zinciri bozuk.
EXIT_PDF_SMOKE_FAILED = 8
# Geri yükleme kipi (`--geri-yukle`): yedek açılamadı/yerleştirilemedi.
EXIT_RESTORE_FAILED = 9
# Paket teşhis kipi (`--bagimlilik-duman`): üçüncü taraf modüllerden biri
# pakete girmemiş (K7 hiddenimports borcu).
EXIT_IMPORT_SMOKE_FAILED = 10


class StartupError(Exception):
    """Program açılışını durduran hata (pencere AÇILMAZ)."""

    exit_code: int = EXIT_UNEXPECTED
    title: str = "Kelebek Sınav açılamadı"

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    @property
    def full_message(self) -> str:
        """Kullanıcıya gösterilecek tam metin (mesaj + varsa ipucu)."""
        return f"{self.message}\n\n{self.hint}" if self.hint else self.message


class AlreadyRunningError(StartupError):
    """Program zaten açık — ikinci kopya pencere açmaz."""

    exit_code = EXIT_ALREADY_RUNNING
    title = "Kelebek Sınav zaten çalışıyor"


class DatabaseCorruptError(StartupError):
    """SQLite bütünlük denetimi başarısız — veri dosyası bozuk."""

    exit_code = EXIT_DATABASE_CORRUPT
    title = "Veritabanı bozuk"


class SchemaTooNewError(StartupError):
    """Veri, programın daha yeni bir sürümüyle yazılmış — eski sürüm açamaz."""

    exit_code = EXIT_SCHEMA_TOO_NEW
    title = "Program sürümü eski"


class MigrationError(StartupError):
    """`migrate --no-input` başarısız — pencere açılmaz, yedekten dönüş önerilir."""

    exit_code = EXIT_MIGRATION_FAILED
    title = "Veritabanı güncellenemedi"


class ServerStartError(StartupError):
    """Gömülü sunucu (waitress) ayağa kalkmadı."""

    exit_code = EXIT_SERVER_FAILED
    title = "Program başlatılamadı"


class WebViewUnavailableError(StartupError):
    """Pencere motoru yok (Windows'ta WebView2 kurulu değil)."""

    exit_code = EXIT_WEBVIEW_UNAVAILABLE
    title = "Pencere açılamadı"
