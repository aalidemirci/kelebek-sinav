"""sinav DRF view'ları — F2 kesiti (ince; mantık services.py'da).

OYS `ExamRoomViewSet`'ten UYARLA: izin sınıfları/denetim/OpenAPI süslemeleri
düşer (authsuz tek kullanıcı); `layout-pdf` ucu F4'te (WeasyPrint şablonlarıyla)
gelir. Silme ucu yok: salon `is_active=False` ile pasifleştirilir.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers as drf_serializers
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.sinav import selectors, services
from apps.sinav.models import ExamRoom
from apps.sinav.serializers import ExamRoomSerializer, SeatSerializer


class ExamRoomViewSet(viewsets.ModelViewSet[ExamRoom]):
    """Sınav salonları — plan şeması servis katmanında doğrulanır.

    `seats` ucu numaralandırılmış koltuk önizlemesini döner (editör + kroki);
    `preview-seats` KAYDEDİLMEMİŞ planı numaralandırır (iş kuralı tek yerde).
    """

    serializer_class = ExamRoomSerializer
    http_method_names = ["get", "post", "patch"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return selectors.exam_rooms(
            include_inactive=self.request.query_params.get("include_inactive") == "true"
        )

    def perform_create(self, serializer: drf_serializers.BaseSerializer[ExamRoom]) -> None:
        data: dict[str, Any] = dict(serializer.validated_data or {})
        try:
            serializer.instance = services.create_exam_room(**data)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc

    def perform_update(self, serializer: drf_serializers.BaseSerializer[ExamRoom]) -> None:
        instance = serializer.instance
        assert instance is not None  # ModelViewSet update akışında garanti
        # partial=True: validated_data yalnız gönderilen alanları içerir —
        # linked_section_id yoksa servis sentineli (...) "değiştirme" der.
        data: dict[str, Any] = dict(serializer.validated_data or {})
        try:
            serializer.instance = services.update_exam_room(instance, **data)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc

    @action(detail=True, methods=["get"], serializer_class=SeatSerializer)
    def seats(self, request: Request, pk: str | None = None) -> Response:
        """`GET /exam-rooms/<id>/seats/` — numaralandırılmış koltuk listesi."""
        room = self.get_object()
        seat_list = services.room_seats(room)
        return Response(
            {
                "room_id": room.pk,
                "numbering_scheme": room.numbering_scheme,
                "capacity": len(seat_list),
                "seats": SeatSerializer(seat_list, many=True).data,
            }
        )

    @action(
        detail=False, methods=["post"], url_path="preview-seats", serializer_class=SeatSerializer
    )
    def preview_seats(self, request: Request) -> Response:
        """KAYDEDİLMEMİŞ planın kapasite + numara önizlemesi (salon editörü).

        Numaralandırma iş kuralı backend'dedir; editör her plan değişiminde bu
        ucu çağırır, kayıt yazılmaz. Geçersiz plan Türkçe 400.
        """
        scheme_raw = request.data.get("numbering_scheme")
        try:
            capacity, seat_list = services.preview_room_seats(
                request.data.get("layout_plan"),
                str(scheme_raw) if scheme_raw else None,
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response({"capacity": capacity, "seats": SeatSerializer(seat_list, many=True).data})

    @action(detail=False, methods=["post"], url_path="generate-section-rooms")
    def generate_section_rooms(self, request: Request) -> Response:
        """Aktif yılın her şubesi için 40 koltuklu ikili-sıra derslik üretir (idempotent).

        Kapı sol-ön, öğretmen masası sağ-ön; mevcut salonlar (linked_section VEYA
        ad çakışması) atlanır. Yanıt: {created, skipped, orphan_rooms, sections_total}.
        """
        result = services.generate_section_rooms()
        return Response(result)
