"""Günlük yapılandırması testleri — erişim logu KAPALI, PII yazılmaz (F2 bulgu #20)."""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path

from desktop.logging_setup import (
    LOG_FILE_NAME,
    LOGGER_NAME,
    apply_access_log_policy,
    configure_logging,
)

# Django'nun `DEFAULT_LOGGING`'inin bizi ilgilendiren iskeleti: "django" günlükçüsünü
# tanımlar, "django.request"i tanımlamaz. `dictConfig`, tanımlı bir günlükçünün
# ALTINDA kalan mevcut günlükçüleri (child_loggers) SIFIRLAR — seviye NOTSET,
# handler listesi boş, propagate True.
DJANGO_VARSAYILAN_GUNLUK = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"django": {"handlers": ["console"], "level": "INFO"}},
}


def test_gunluk_veri_dizinindeki_logs_altina_yazilir(tmp_path: Path) -> None:
    logger = configure_logging(tmp_path)

    logger.info("Program açıldı.")
    logging.shutdown()

    icerik = (tmp_path / LOG_FILE_NAME).read_text(encoding="utf-8")
    assert "Program açıldı." in icerik


def test_yapilandirma_tekrarlanabilir_ve_handler_cogaltmaz(tmp_path: Path) -> None:
    configure_logging(tmp_path)
    configure_logging(tmp_path)
    logger = configure_logging(tmp_path)

    assert len(logger.handlers) == 1


def test_erisim_logu_uretilmez(tmp_path: Path) -> None:
    """waitress/Django istek logları `?search=<öğrenci adı>` sızdırır → kapalı."""
    configure_logging(tmp_path)

    for ad in ("waitress", "waitress.queue", "django.server"):
        assert logging.getLogger(ad).level >= logging.ERROR

    logging.getLogger("django.server").info('"GET /api/v1/students/?search=Ayşe" 200')
    logging.shutdown()

    icerik = (tmp_path / LOG_FILE_NAME).read_text(encoding="utf-8")
    assert "Ayşe" not in icerik


def test_sorgu_dizesi_gunluge_yazilmaz(tmp_path: Path) -> None:
    """Sigorta: bir kütüphane yine de URL loglarsa sorgu dizesi kırpılır."""
    logger = configure_logging(tmp_path)

    logger.warning("İstek başarısız: /api/v1/students/?search=Ayşe%20Yılmaz&limit=25")
    logging.shutdown()

    icerik = (tmp_path / LOG_FILE_NAME).read_text(encoding="utf-8")
    assert "Ayşe" not in icerik
    assert "/api/v1/students/" in icerik


def test_django_kurulumu_erisim_logu_susturmasini_ezer(tmp_path: Path) -> None:
    """`django.setup()` kendi günlük yapılandırmasını uygular ve bizimkini SİLER.

    Bu yüzden `django.request` susturması `django.setup()` SONRASINDA yeniden
    uygulanmalıdır; yoksa istek yolları (DEBUG açıkken sorgu dizeleri de) konsola
    düşer.
    """
    configure_logging(tmp_path)

    logging.config.dictConfig(DJANGO_VARSAYILAN_GUNLUK)

    assert logging.getLogger("django.request").level == logging.NOTSET  # ezildi

    apply_access_log_policy()

    request_logger = logging.getLogger("django.request")
    assert request_logger.level >= logging.ERROR
    assert request_logger.propagate is False


def test_erisim_logu_politikasi_yapilandirmadan_once_de_cagrilabilir() -> None:
    apply_access_log_policy()

    assert logging.getLogger("waitress").level >= logging.ERROR


def test_echo_kipi_ikinci_handler_ekler(tmp_path: Path) -> None:
    logger = configure_logging(tmp_path, echo=True)

    assert len(logger.handlers) == 2


def test_dizin_yoksa_olusturulur(tmp_path: Path) -> None:
    hedef = tmp_path / "a" / "logs"

    configure_logging(hedef)

    assert hedef.is_dir()


def test_logger_adi_paket_ile_hizali(tmp_path: Path) -> None:
    logger = configure_logging(tmp_path)

    assert logger.name == LOGGER_NAME
    assert LOGGER_NAME == "kelebek_sinav"
