"""sinav modülü modelleri — F2 kesiti: sınav salonu + plan enum'ları.

OYS `sinav_islemleri/models.py`'den UYARLA (tasarım §11): `created_by` düşer,
`linked_section` OYS `core.Section` yerine yerel `okul.ClassSection`'a bağlanır
(şube kataloğu — F1). Oturum/yerleşim modelleri F3'te gelir.
"""

from __future__ import annotations

from django.db import models

from shared.models import BaseModel


class NumberingScheme(models.TextChoices):
    """Koltuk numaralandırma düzeni (dönemlik kılavuz: S düzeni varsayılan)."""

    S_PATTERN = "S_PATTERN", "S düzeni"
    STRAIGHT = "STRAIGHT", "Düz"


class DeskType(models.TextChoices):
    SINGLE = "SINGLE", "Tekli"
    DOUBLE = "DOUBLE", "İkili"
    TRIPLE = "TRIPLE", "Üçlü"


class FurnitureKind(models.TextChoices):
    DOOR = "DOOR", "Kapı"
    BLACKBOARD = "BLACKBOARD", "Yazı tahtası"
    SMART_BOARD = "SMART_BOARD", "Akıllı tahta"
    TEACHER_DESK = "TEACHER_DESK", "Öğretmen masası"


class ExamRoom(BaseModel):
    """Sınav salonu — 2D yerleşim planı + numaralandırma düzeni.

    `layout_plan` JSON şeması SERVİS katmanında doğrulanır (`layout.py`);
    kapasite plandaki aktif sıra hücrelerinden hesaplanır, ayrıca alan olarak
    tutulmaz. `linked_section` "bu salon 11-C'nin dersliğidir" eşlemesidir —
    klasik (kendi dersliğinde) düzenin ve KENDI_DERSLIGINDE sabit kuralının
    temeli. Kişisel veri içermez.
    """

    name = models.CharField(
        "salon adı",
        max_length=80,
        db_index=True,
        help_text="Örn. 'D-204', 'Fen Laboratuvarı'.",
    )
    block = models.CharField(
        "blok / kat",
        max_length=80,
        blank=True,
        default="",
        help_text="Serbest konum bilgisi (örn. 'A Blok 2. Kat').",
    )
    linked_section = models.ForeignKey(
        "okul.ClassSection",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="exam_rooms",
        verbose_name="bağlı şube",
        help_text="Salon bir şubenin dersliğiyse o şube (klasik düzen eşlemesi).",
    )
    layout_plan = models.JSONField(
        "yerleşim planı",
        default=dict,
        blank=True,
        help_text="2D plan: grid + sıralar (tekli/ikili/üçlü) + mobilya. "
        "Şema layout.validate_layout_plan ile doğrulanır.",
    )
    numbering_scheme = models.CharField(
        "numaralandırma",
        max_length=10,
        choices=NumberingScheme.choices,
        default=NumberingScheme.S_PATTERN,
    )
    is_active = models.BooleanField(
        "aktif",
        default=True,
        help_text="Pasif salon yeni oturum planlamasında seçilemez; kayıt silinmez.",
    )

    class Meta:
        verbose_name = "sınav salonu"
        verbose_name_plural = "sınav salonları"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_examroom_name_alive",
            ),
        ]

    def __str__(self) -> str:
        return self.name
