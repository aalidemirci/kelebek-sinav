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

    def ready(self) -> None:
        """Şifreli alanlara "parola kurulu mu?" sorusunun cevabını bağlar.

        `shared.crypto` uygulama katmanını import etmez; anahtar bellekte değilken
        düz yazımın meşru olup olmadığını (parolasız kip) buradan öğrenir.
        Bağlanmasaydı alan, kilitliyken de düz yazardı (fail-open).
        """
        from apps.okul.services import app_password
        from shared import crypto

        crypto.register_key_required_probe(app_password.is_password_set)
