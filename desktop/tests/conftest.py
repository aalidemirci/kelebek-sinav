"""Masaüstü testleri için ortak kurulum.

Bu testler Django *uygulamasını* (apps/okul) çalıştırmaz —
oturum belirteci middleware'i yalnız `HttpRequest`/`HttpResponse` sözleşmesine
dokunur. Bu yüzden gerçek `config.settings` yerine asgari bir ayar kümesi
kurulur: veritabanı, uygulama kaydı ve migration gerekmez, testler milisaniyede
koşar. Uçtan uca açılış doğrulaması `test_main.py`'deki `--autotest` alt-süreç
testinde gerçek ayarlarla yapılır.

`desktop.main.run` açılışta `faulthandler`ı `logs/cokme.log`a bağlar
(`enable_crash_log`, 19.09.2026). Bu SÜREÇ GENELİNDE bir ayardır: testlerde
gerçekten çağrılırsa pytest'in kendi çöküş çıktısı geçici bir dosyaya kayardı.
Aşağıdaki fikstür onu etkisizleştirir; gerçek davranış `test_logging_setup.py`
içinde AYRI bir alt süreçte, gerçek bir yerel çöküşle sınanır.
"""

from __future__ import annotations

import faulthandler

import django
import pytest
from django.conf import settings


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: yavaş, uçtan uca alt-süreç testi")


@pytest.fixture(autouse=True)
def _faulthandler_etkisiz(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(faulthandler, "enable", lambda *args, **kwargs: None)


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
