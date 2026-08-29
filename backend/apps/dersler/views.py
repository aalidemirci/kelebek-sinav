"""Ders havuzu API uçları — İNCE view'lar (View → Service → Model).

Katalog listesi ilk açılışta MEB tohumunu tembelce koşar (K5): pakete gömülü
çizelge verisi varsa yüklenir, yoksa sessizce elle-ekleme yoluyla devam edilir.
Ders SİLİNMEZ: pasifleştirilir (`is_active=False`; DELETE ucu bilinçle yok).
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers, status
from rest_framework.generics import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dersler import selectors, services
from apps.dersler.models import Course
from apps.dersler.serializers import CourseMergeSerializer, CourseSerializer

TRUE_VALUES = frozenset({"true", "1"})


def _servis(callable_: Any, /, **kwargs: Any) -> Any:
    """Servis `ValidationError`'larını sözleşmeli 400'e çevirir."""
    try:
        return callable_(**kwargs)
    except DjangoValidationError as exc:
        raise serializers.ValidationError("; ".join(exc.messages)) from exc


class CourseListCreateView(APIView):
    """`GET/POST /api/v1/courses/` — katalog listesi (+tembel tohum) ve elle ekleme."""

    def get(self, request: Request) -> Response:
        services.ensure_seeded()
        params = request.query_params
        include_inactive = params.get("include_inactive", "").lower() in TRUE_VALUES
        course_type = params.get("course_type") or None
        raw_level = params.get("level", "").strip()
        if raw_level:
            try:
                level = int(raw_level)
            except ValueError as exc:
                raise serializers.ValidationError(
                    {"level": "Seviye süzgeci sayısal olmalıdır."}
                ) from exc
            rows: list[Course] = selectors.courses_for_level(
                level, course_type=course_type, include_inactive=include_inactive
            )
        else:
            rows = list(
                selectors.courses(course_type=course_type, include_inactive=include_inactive)
            )
        q = params.get("q", "")
        if q.strip():
            rows = selectors.search_courses(rows, q)
        return Response(CourseSerializer(rows, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = CourseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        course = _servis(services.create_course, **dict(serializer.validated_data))
        return Response(CourseSerializer(course).data, status=status.HTTP_201_CREATED)


class CourseDetailView(APIView):
    """`GET/PATCH /api/v1/courses/<pk>/` — DELETE bilinçle yok (pasifleştir)."""

    def get(self, request: Request, pk: int) -> Response:
        course = get_object_or_404(Course.objects.all(), pk=pk)
        return Response(CourseSerializer(course).data)

    def patch(self, request: Request, pk: int) -> Response:
        course = get_object_or_404(Course.objects.all(), pk=pk)
        serializer = CourseSerializer(course, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        guncel = _servis(services.update_course, course=course, **dict(serializer.validated_data))
        return Response(CourseSerializer(guncel).data)


class CourseDuplicatesView(APIView):
    """`GET /api/v1/courses/duplicates/` — mükerrer aday kümeleri."""

    def get(self, request: Request) -> Response:
        return Response(selectors.duplicate_course_candidates())


class CourseMergeView(APIView):
    """`POST /api/v1/courses/merge/` — mükerrer dersi kanoniğe birleştir."""

    def post(self, request: Request) -> Response:
        req = CourseMergeSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        duplicate = get_object_or_404(Course.objects.all(), pk=req.validated_data["duplicate"])
        canonical = get_object_or_404(Course.objects.all(), pk=req.validated_data["canonical"])
        sonuc = _servis(
            services.consolidate_duplicate_course, duplicate=duplicate, canonical=canonical
        )
        return Response(sonuc)
