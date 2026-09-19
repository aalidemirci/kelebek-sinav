"""Mazeret takibi uçları (19.09.2026) — ince katman; mantık `services_makeup`'ta.

    GET  /makeup/absences/?semester=<id>   dönemin sınava girmeyenleri + sayaçlar
    POST /makeup/sessions/                  seçilen "Mazeretli" kayıtlarla mazeret sınavı
    POST /makeup/remove/                    kayıtları mazeret sınavından çıkarır
    GET  /makeup/report/?semester=&kind=    takip raporu (pdf | xlsx)

Rapor biçimi `kind` ile seçilir: `?format=` DRF'nin içerik müzakeresine ayrılmıştır
(URL_FORMAT_OVERRIDE) ve "pdf" verilince uç 404 dönerdi.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from rest_framework import serializers as drf_serializers
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.sinav import services_makeup
from apps.sinav.serializers import (
    ExamSessionSerializer,
    MakeupRecordsSerializer,
    MakeupSessionCreateSerializer,
)


def _semester_param(request: Request, semesters: list[dict[str, Any]]) -> int | None:
    """`?semester=` verilmezse varsayılan dönem (bugünü içeren, yoksa son)."""
    raw = request.query_params.get("semester", "")
    if raw.isdigit():
        return int(raw)
    return next((s["id"] for s in semesters if s["default"]), None)


class MakeupViewSet(viewsets.ViewSet):
    """Mazeret takibi — kayıt yazmaz; yoklama kayıtlarını okur ve bağlar."""

    @action(detail=False, methods=["get"])
    def absences(self, request: Request) -> Response:
        semesters = services_makeup.semester_options()
        semester_id = _semester_param(request, semesters)
        rows = services_makeup.absence_rows(semester_id) if semester_id is not None else []
        return Response(
            {
                "semester_id": semester_id,
                "semesters": semesters,
                "rows": rows,
                "summary": services_makeup.absence_summary(rows),
                "notice_business_days": services_makeup.NOTICE_BUSINESS_DAYS,
            }
        )

    @action(detail=False, methods=["post"])
    def sessions(self, request: Request) -> Response:
        serializer = MakeupSessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd: dict[str, Any] = dict(serializer.validated_data)
        try:
            session = services_makeup.create_makeup_session(
                record_ids=list(vd["record_ids"]),
                name=str(vd.get("name") or ""),
                exam_date=vd["exam_date"],
                start_time=vd["start_time"],
                duration_minutes=int(vd.get("duration_minutes") or 40),
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(ExamSessionSerializer(session).data, status=201)

    @action(detail=False, methods=["post"])
    def remove(self, request: Request) -> Response:
        serializer = MakeupRecordsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            count = services_makeup.remove_from_makeup(
                record_ids=list(serializer.validated_data["record_ids"])
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response({"removed": count})

    @action(detail=False, methods=["get"])
    def report(self, request: Request) -> HttpResponse:
        semester_id = _semester_param(request, services_makeup.semester_options())
        if semester_id is None:
            raise drf_serializers.ValidationError("Aktif ders yılında dönem tanımlı değil.")
        kind = request.query_params.get("kind", "pdf")
        try:
            report_file = services_makeup.render_makeup_report(semester_id, kind)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        response = HttpResponse(report_file.content, content_type=report_file.content_type)
        response["Content-Disposition"] = f'attachment; filename="{report_file.filename}"'
        return response
