"""Okul çekirdeği uygulama tanımı (F0 iskeleti).

F1'de SchoolConfig/SchoolYear/Personnel/Student modelleri, kurulum sihirbazı
servisleri ve içe aktarma boru hattı buraya gelir (tasarım §4 + §12/F1).
"""

from __future__ import annotations

from django.apps import AppConfig


class OkulConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.okul"
    verbose_name = "Okul çekirdeği"
