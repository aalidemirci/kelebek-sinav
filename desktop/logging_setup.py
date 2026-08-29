"""Uygulama günlüğü — erişim logu KAPALI, PII yazılmaz.

F2 denetim bulgusu #20: `?search=<öğrenci adı>` gibi sorgu dizeleri istek
loglarına düşerse, kişisel veri düz metin olarak diske yazılır. Gömülü sunucuda
erişim logu üretmenin hiçbir faydası yok (tek kullanıcı, tek makine), zararı var
→ waitress/Django istek günlükçüleri susturulur.

Uygulama günlüğü YALNIZ veri dizinindeki `logs/` altına yazılır (kurulum
dizinine değil — orası salt-okunur olabilir). Sigorta olarak biçimlendirici
mesajlardaki sorgu dizelerini kırpar: bir kütüphane yine de URL loglarsa
`?search=...` bölümü diske ulaşmaz.
"""

from __future__ import annotations

import logging
import logging.handlers
import re
import sys
from pathlib import Path

LOGGER_NAME = "kelebek_sinav"
LOG_FILE_NAME = "uygulama.log"

_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 3
_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"

# Sorgu dizesi: "?" ile başlar, boşluk/tırnak/satır sonuna kadar sürer.
_QUERY_RE = re.compile(r"\?[^\s\"']*")

# İstek günlüğü üreten kütüphane günlükçüleri (PII riski).
_ACCESS_LOGGERS = ("waitress", "waitress.queue", "django.server")

# `configure_logging` tarafından kurulan dosya handler'ı — `apply_access_log_policy`
# yeniden uygulanırken aynı dosyaya bağlanabilsin diye saklanır.
_file_handler: logging.Handler | None = None


class PiiSafeFormatter(logging.Formatter):
    """Mesajdaki sorgu dizesini kırpar (`?search=Ayşe` → `?…`)."""

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        return _QUERY_RE.sub("?…", text)


def configure_logging(
    log_dir: Path, *, level: int = logging.INFO, echo: bool = False
) -> logging.Logger:
    """Uygulama günlükçüsünü kurar ve döndürür. Tekrar çağrılabilir (idempotent)."""
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    # Kök günlükçüye yayılmasın: kök yapılandırması (varsa) PII filtresiz olabilir.
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = PiiSafeFormatter(_FORMAT)
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / LOG_FILE_NAME,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if echo:
        # `--autotest` ve hata iletisi geri dönüşü için (konsol varsa görünür).
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    global _file_handler
    _file_handler = file_handler
    apply_access_log_policy()

    return logger


def apply_access_log_policy() -> None:
    """İstek (erişim) günlüklerini susturur — `django.setup()` SONRASINDA da çağrılır.

    Django kendi `DEFAULT_LOGGING`'ini `dictConfig` ile uygular; `dictConfig`,
    yapılandırmada adı geçen bir günlükçünün (`django`) ALTINDAKİ mevcut
    günlükçüleri sıfırlar: seviye NOTSET, handler listesi boş, `propagate=True`.
    Yani açılışta kurduğumuz `django.request` susturması `django.setup()` ile
    SİLİNİR ve istek yolları (DEBUG açıkken) konsola düşmeye başlar. Bu yüzden
    politika `django_bootstrap.prepare_django()` içinde yeniden uygulanır.
    """
    for name in _ACCESS_LOGGERS:
        access_logger = logging.getLogger(name)
        access_logger.setLevel(logging.ERROR)
        access_logger.propagate = False
        access_logger.handlers = [logging.NullHandler()]

    # Sunucu hataları teşhis edilebilsin: yol yazılır, sorgu dizesi kırpılır.
    # (Günlük dosyası henüz kurulmadıysa hiçbir yere yazılmaz — sessiz kalır.)
    request_logger = logging.getLogger("django.request")
    request_logger.setLevel(logging.ERROR)
    request_logger.propagate = False
    request_logger.handlers = [_file_handler] if _file_handler else [logging.NullHandler()]
