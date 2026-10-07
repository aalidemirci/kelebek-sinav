"""Ders havuzu uygulama tanımı (F1).

OYS `ders_yapisi` modülünün KELEBEK KESİTİ: yalnız ders kataloğu + MEB çizelge
tohumu + takma adlar + mükerrer birleştirme (tasarım §7). LessonGroup/derslik/
çerçeve zinciri ALINMADI (§11 ALMA — Postgres'e ve ders programına bağlıydı).
"""

from __future__ import annotations

from django.apps import AppConfig


class DerslerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dersler"
    verbose_name = "Ders havuzu"

    def ready(self) -> None:
        """Ayrılan/silinen öğrencinin seçmeli listeleri KATI silinsin (KVKK — 07.10.2026).

        Fotoğraf ve BEP kaydının emsali (`persons.register_student_forget_hook`):
        temizlik okulun öğrenci servisinde AYNI işlemde koşar.
        """
        from apps.dersler import services
        from apps.okul.services import persons

        persons.register_student_forget_hook(services.forget_student_enrollments)
