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

    def ready(self) -> None:
        """Ayrılan/silinen öğrencinin BEP verisi KATI silinsin (KVKK — fotoğraf emsali).

        Bağımlılık yönü sinav → okul'dur: okul bu uygulamayı import etmez,
        temizlik kancası buradan kaydedilir (`persons.register_student_forget_hook`).
        """
        from apps.okul.services import persons
        from apps.sinav import services_individual

        persons.register_student_forget_hook(services_individual.forget_student)
