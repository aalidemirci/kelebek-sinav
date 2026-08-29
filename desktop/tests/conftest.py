"""Masaüstü testleri için ortak kurulum.

Bu testler Django *uygulamasını* (apps/okul) çalıştırmaz —
oturum belirteci middleware'i yalnız `HttpRequest`/`HttpResponse` sözleşmesine
dokunur. Bu yüzden gerçek `config.settings` yerine asgari bir ayar kümesi
kurulur: veritabanı, uygulama kaydı ve migration gerekmez, testler milisaniyede
koşar. Uçtan uca açılış doğrulaması `test_main.py`'deki `--autotest` alt-süreç
testinde gerçek ayarlarla yapılır.
"""

from __future__ import annotations

import django
import pytest
from django.conf import settings


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: yavaş, uçtan uca alt-süreç testi")


if not settings.configured:
    settings.configure(
        DEBUG=False,
        ALLOWED_HOSTS=["127.0.0.1", "localhost"],
        DEFAULT_CHARSET="utf-8",
        USE_TZ=True,
        TIME_ZONE="Europe/Istanbul",
        INSTALLED_APPS=[],
        DATABASES={},
    )
    django.setup()
