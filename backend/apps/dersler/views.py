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


class CatalogStatusView(APIView):
    """`GET /api/v1/courses/catalog-status/` — yürürlükteki çizelge planı.

    Ders havuzu ekranının "hangi çizelge, hangi seviyede, dayanağı ne" paneli ve
    kurulum/ayar matrisinin program listesi tek uçtan gelir (tasarım §7.2).
    Salt okunur; senkron tetiklemez (liste ucu zaten tembel tohumu koşar).
    """

    def get(self, request: Request) -> Response:
        import json

        params = request.query_params
        school_type = params.get("school_type") or None
        raw_prep = params.get("has_prep_class", "").strip().lower()
        has_prep = raw_prep in TRUE_VALUES if raw_prep else None
        overrides: dict[str, Any] | None = None
        raw_overrides = params.get("level_programs", "").strip()
        if raw_overrides:
            try:
                parsed = json.loads(raw_overrides)
            except ValueError as exc:
                raise serializers.ValidationError(
                    {"level_programs": "Seviye atamaları JSON sözlük olmalıdır."}
                ) from exc
            if not isinstance(parsed, dict):
                raise serializers.ValidationError(
                    {"level_programs": "Seviye atamaları JSON sözlük olmalıdır."}
                )
            overrides = parsed
        return Response(
            services.catalog_status(school_type=school_type, has_prep=has_prep, overrides=overrides)
        )


class CatalogResyncView(APIView):
    """`POST /api/v1/courses/resync/` — kataloğu çizelgeye zorla yeniden çeker.

    Damga eşit olsa da koşar (idareci "çizelgeyi yeniden uygula" dedi). Sonuç
    sayaçları + güncel plan döner; MEB dersi olmayan okulda yalnız uyarı gelir.
    """

    def post(self, request: Request) -> Response:
        sonuc = services.ensure_catalog_synced(force=True)
        services.ensure_course_aliases()
        ozet = (
            {
                "created": sonuc.created,
                "updated": sonuc.updated,
                "unchanged": sonuc.unchanged,
                "restored": sonuc.restored,
                "excluded": sonuc.excluded,
                "errors": sonuc.errors,
                "warnings": sonuc.warnings,
            }
            if sonuc is not None
            else None
        )
        return Response({"result": ozet, "status": services.catalog_status()})


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


def _cozulen_yil_id(request: Request) -> int:
    """İstekten ders yılı: `school_year` parametresi ya da aktif yıl."""
    from apps.okul import selectors as okul_selectors

    raw = request.query_params.get("school_year") or request.data.get("school_year_id")
    if raw is not None and raw != "":
        try:
            return int(str(raw))
        except (TypeError, ValueError) as exc:
            raise serializers.ValidationError({"school_year": "Ders yılı sayısal olmalı."}) from exc
    year = okul_selectors.active_school_year()
    if year is None:
        raise serializers.ValidationError(
            {"school_year": "Aktif ders yılı yok — Ayarlar → Ders Yılları'ndan bir yıl açın."}
        )
    return int(year.pk)


class CourseSectionOfferingsView(APIView):
    """`GET /api/v1/courses/section-offerings/` — seçmeli derslerin şube kapsamı.

    Çıktı `{"school_year": <id>, "results": [{"course": <id>, "level": <int>,
    "section_ids": [...]}]}`. Ders havuzu tablosu "Şubeler" sütununu bundan
    doldurur; sınav takvimi de aynı kaynaktan beslenir (kapsamın TEK doğruluk
    kaynağı ders havuzudur — takvim girdisi kopya tutar).

    Silinmiş şube okuma anında düşer (`selectors.course_section_map`).
    """

    def get(self, request: Request) -> Response:
        year_id = _cozulen_yil_id(request)
        harita = selectors.course_section_map(year_id)
        return Response(
            {
                "school_year": year_id,
                "results": [
                    {"course": course_id, "level": level, "section_ids": section_ids}
                    for (course_id, level), section_ids in sorted(harita.items())
                ],
            }
        )


class CourseSectionsView(APIView):
    """`GET/PUT /api/v1/courses/<pk>/sections/` — tek dersin şube kapsamı.

    PUT gövdesi `{"school_year_id"?: <id>, "offerings": [{"level", "section_ids"}]}`
    ve TAM DEĞİŞTİRME yapar: gönderilmeyen seviyenin kaydı silinir (diyalog
    dersin bütün seviyelerini birlikte gösterir).
    """

    def get(self, request: Request, pk: int) -> Response:
        year_id = _cozulen_yil_id(request)
        get_object_or_404(Course.objects.all(), pk=pk)
        return Response(
            {
                "school_year": year_id,
                "offerings": [
                    {"level": level, "section_ids": ids}
                    for level, ids in sorted(
                        services.course_section_offerings(
                            course_id=pk, school_year_id=year_id
                        ).items()
                    )
                ],
            }
        )

    def put(self, request: Request, pk: int) -> Response:
        year_id = _cozulen_yil_id(request)
        offerings = request.data.get("offerings")
        if not isinstance(offerings, list):
            raise serializers.ValidationError({"offerings": "Kapsam listesi gerekli."})
        guncel = _servis(
            services.set_course_sections,
            course_id=pk,
            school_year_id=year_id,
            offerings=offerings,
        )
        return Response(
            {
                "school_year": year_id,
                "offerings": [
                    {"level": level, "section_ids": ids} for level, ids in guncel.items()
                ],
            }
        )
