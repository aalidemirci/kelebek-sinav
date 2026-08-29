"""Sınav işlemleri uygulama tanımı.

OYS `sinav_islemleri` modülünün KS portu — fazlarla dolar (tasarım §12):
F2 salon + kelebek motoru çekirdeği; F3 oturum akışı; F4-F5 evrak/kitapçık;
F6 takvim; F7 gözetmen. Motor sözleşmeleri CLAUDE.md §3'te sabittir.
"""

from __future__ import annotations

from django.apps import AppConfig


class SinavConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sinav"
    verbose_name = "Sınav işlemleri"
