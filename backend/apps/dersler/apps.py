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
