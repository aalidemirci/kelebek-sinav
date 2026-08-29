"""sinav DRF serializer'ları — F2 kesiti."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.sinav import services
from apps.sinav.models import ExamRoom, NumberingScheme


class ExamRoomSerializer(serializers.ModelSerializer[ExamRoom]):
    """Sınav salonu kaydı.

    `capacity` plandan hesaplanır (salt-okunur); plan şemasının asıl
    doğrulaması SERVİS katmanındadır — view perform_* içinde
    services.create/update_exam_room çağrılır, buradaki alanlar yalnız tip/
    varlık denetimi yapar.
    """

    capacity = serializers.SerializerMethodField()
    linked_section_id = serializers.IntegerField(allow_null=True, required=False)
    linked_section_label = serializers.SerializerMethodField()
    numbering_scheme = serializers.ChoiceField(
        choices=NumberingScheme.choices, required=False, default=NumberingScheme.S_PATTERN
    )

    class Meta:
        model = ExamRoom
        fields = (
            "id",
            "name",
            "block",
            "linked_section_id",
            "linked_section_label",
            "layout_plan",
            "numbering_scheme",
            "is_active",
            "capacity",
        )
        read_only_fields = ("id", "capacity", "linked_section_label")

    def get_capacity(self, obj: ExamRoom) -> int:
        return services.room_capacity(obj)

    def get_linked_section_label(self, obj: ExamRoom) -> str:
        return obj.linked_section.class_label if obj.linked_section is not None else ""


class SeatSerializer(serializers.Serializer[Any]):
    """Numaralandırılmış koltuk — editör önizlemesi / kroki verisi (layout.Seat)."""

    desk_row = serializers.IntegerField(read_only=True)
    desk_col = serializers.IntegerField(read_only=True)
    desk_type = serializers.CharField(read_only=True)
    slot = serializers.IntegerField(read_only=True)
    seat_no = serializers.IntegerField(read_only=True)
    x = serializers.FloatField(read_only=True)
    y = serializers.FloatField(read_only=True)
