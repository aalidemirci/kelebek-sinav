"""Sınav takvimi DRF view'ları (F6) — ince; mantık services_calendar'da.

OYS `views_calendar.py`'den UYARLA: izin sınıfları/denetim (SENSITIVE_READ)/
OpenAPI süslemeleri düştü (authsuz tek kullanıcı — B1/B11); zümre daraltması
düştü (B7 — süreç matrisi hep tam görünür); `created_by`/`by_user` düştü
(B17), onay damgası gövdeden ad-snapshot alır (B12).
"""

from __future__ import annotations

from datetime import date
from typing import Any, NoReturn

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import QuerySet
from django.http import HttpResponse
from rest_framework import serializers as drf_serializers
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.okul import selectors as okul_selectors
from apps.sinav import selectors, services_calendar
from apps.sinav.models import ExamCalendar, ExamCalendarEntry, ExamTrackItem
from apps.sinav.serializers import (
    ExamCalendarEntrySerializer,
    ExamCalendarSerializer,
    ExamTrackItemSerializer,
)


def _raise_drf(exc: DjangoValidationError) -> NoReturn:
    detail: Any = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
    raise drf_serializers.ValidationError(detail) from exc


class ExamCalendarViewSet(viewsets.ModelViewSet[ExamCalendar]):
    """Sınav takvimleri (ADR-0044) — durum makinesi + havuz + ızgara + PDF."""

    serializer_class = ExamCalendarSerializer
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self) -> QuerySet[ExamCalendar]:
        params = self.request.query_params
        return selectors.exam_calendars(
            school_year_id=_int_or_none(params.get("school_year")),
            semester_id=_int_or_none(params.get("semester")),
            status=params.get("status"),
        )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            calendar = services_calendar.create_exam_calendar(
                semester_id=data["semester"].pk,
                round=data["round"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                name=data.get("name"),
            )
        except DjangoValidationError as exc:
            _raise_drf(exc)
        return Response(self.get_serializer(calendar).data, status=status.HTTP_201_CREATED)

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        calendar = self.get_object()
        serializer = self.get_serializer(calendar, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            calendar = services_calendar.update_exam_calendar(
                calendar,
                name=data.get("name"),
                start_date=data.get("start_date"),
                end_date=data.get("end_date"),
                description_text=data.get("description_text"),
                footnote_text=data.get("footnote_text"),
            )
        except DjangoValidationError as exc:
            _raise_drf(exc)
        # M2M servis imzasına girmez (DRF nesne listesi döndürür); taslak kilidi
        # yukarıdaki servis çağrısında zaten koştu.
        if "signatory_departments" in data:
            calendar.signatory_departments.set(data["signatory_departments"])
        return Response(self.get_serializer(calendar).data)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            services_calendar.remove_exam_calendar(self.get_object())
        except DjangoValidationError as exc:
            _raise_drf(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="generate-defaults")
    def generate_defaults(self, request: Request) -> Response:
        """Yılın dönemleri × 2 turu için pencereli taslak takvimler (idempotent)."""
        year_id = _int_or_none(request.data.get("school_year_id")) or _active_year_id()
        if year_id is None:
            raise drf_serializers.ValidationError({"school_year_id": "Ders yılı gerekli."})
        created = services_calendar.generate_default_calendars(school_year_id=year_id)
        return Response({"created": ExamCalendarSerializer(created, many=True).data})

    @action(detail=False, methods=["get"], url_path="default-description")
    def default_description(self, request: Request) -> Response:
        """Varsayılan açıklama metni (Önizleme sekmesi "Varsayılan metne dön")."""
        return Response({"text": services_calendar.DEFAULT_CALENDAR_DESCRIPTION})

    @action(detail=False, methods=["get"], url_path="default-footnote")
    def default_footnote(self, request: Request) -> Response:
        """Varsayılan dipnot metni (Önizleme sekmesi "Varsayılan metne dön")."""
        return Response({"text": services_calendar.DEFAULT_CALENDAR_FOOTNOTE})

    @action(detail=True, methods=["post"], url_path="fill-pool")
    def fill_pool(self, request: Request, pk: str | None = None) -> Response:
        """Havuzu ZORUNLU + YAZILI derslerle doldurur (idempotent; round 3 reddedilir).

        Uç adı ve gövde sözleşmesi değişmedi; DAVRANIŞ daraldı (seçmeliler
        artık `bulk-entries` ile seçilerek eklenir) — arayüzdeki etiket de
        "Zorunlu dersleri ekle"dir.
        """
        try:
            result = services_calendar.fill_calendar_pool(self.get_object())
        except DjangoValidationError as exc:
            _raise_drf(exc)
        return Response(result)

    # DİKKAT (OYS Tur 644): aynı `url_path`li iki @action router'da TEK
    # pattern'e düşer. "bulk-entries"/"elective-options" mevcut hiçbir action
    # yoluyla çakışmıyor ("entries" ayrı bir pattern'dir).
    @action(detail=True, methods=["post"], url_path="bulk-entries")
    def bulk_entries(self, request: Request, pk: str | None = None) -> Response:
        """Havuza TOPLU girdi ekler (seçmeli ders diyaloğunun tek çağrısı).

        Gövde: `{"items": [{"course_id", "level", "participant_type",
        "section_ids", "exam_kind", "is_butterfly", "authority"}]}`.
        Dönüş created/existed/skipped etiket listeleridir — reddedilen kalem
        SESSİZCE DÜŞMEZ, arayüz özetler.
        """
        items = request.data.get("items")
        if not isinstance(items, list):
            raise drf_serializers.ValidationError({"items": "Eklenecek kalem listesi gerekli."})
        try:
            result = services_calendar.add_calendar_entries_bulk(self.get_object(), items)
        except DjangoValidationError as exc:
            _raise_drf(exc)
        return Response(result)

    @action(detail=True, methods=["get"], url_path="elective-options")
    def elective_options(self, request: Request, pk: str | None = None) -> Response:
        """Seviye bazında seçilebilir SEÇMELİ (yazılı) dersler + `in_pool` bayrağı."""
        return Response({"results": services_calendar.elective_pool_options(self.get_object())})

    # ÇOK METOTLU `@action` — GET ve POST TEK action'da (OYS Tur 644: aynı
    # url_path'li iki action router'da tek pattern'e düşüp GET 405 alıyordu).
    @action(detail=True, methods=["get", "post"])
    def entries(self, request: Request, pk: str | None = None) -> Response:
        """Havuz listesi (GET) + havuza girdi ekleme (POST)."""
        if request.method == "GET":
            # Kullanıcıya gösterilen liste TR SIRALI (CLAUDE.md §2): DB
            # `order_by` SQLite'ta BINARY'dir ve Ç/Ğ/İ/Ö/Ş/Ü'yü Z'den sonraya
            # atıyordu.
            rows = selectors.calendar_entries_sorted(int(pk) if pk else 0)
            return Response({"results": ExamCalendarEntrySerializer(rows, many=True).data})
        calendar = self.get_object()
        serializer = ExamCalendarEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            entry = services_calendar.add_calendar_entry(
                calendar=calendar,
                course_id=data["course"].pk,
                level=data["level"],
                exam_kind=data.get("exam_kind") or "WRITTEN",
                is_butterfly=data.get("is_butterfly", True),
                authority=data.get("authority") or "SCHOOL",
                participant_type=data.get("participant_type") or "LEVEL",
                section_ids=data.get("section_ids"),
                note=data.get("note", ""),
            )
        except DjangoValidationError as exc:
            _raise_drf(exc)
        return Response(ExamCalendarEntrySerializer(entry).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def grid(self, request: Request, pk: str | None = None) -> Response:
        return Response(services_calendar.calendar_grid(self.get_object()))

    @action(detail=True, methods=["get"])
    def pdf(self, request: Request, pk: str | None = None) -> HttpResponse:
        calendar = self.get_object()
        pdf_bytes = services_calendar.render_calendar_pdf(calendar)
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="sinav_takvimi_{calendar.pk}.pdf"'
        return resp

    @action(detail=True, methods=["get"], url_path="participant-preview")
    def participant_preview(self, request: Request, pk: str | None = None) -> Response:
        return Response(services_calendar.entry_participant_preview(self.get_object()))

    @action(detail=True, methods=["post"], url_path="create-session")
    def create_session(self, request: Request, pk: str | None = None) -> Response:
        """Onaylı takvim slotundan (tarih+ders saati) TASLAK kelebek oturum üretir."""
        on_date = _parse_date(request.data.get("date"))
        period_no = _int_or_none(request.data.get("period_no"))
        if on_date is None or period_no is None:
            raise drf_serializers.ValidationError({"date": "Tarih ve ders saati gerekli."})
        try:
            session = services_calendar.create_session_from_slot(
                self.get_object(), on_date=on_date, period_no=period_no
            )
        except DjangoValidationError as exc:
            _raise_drf(exc)
        return Response(
            {"session_id": session.pk, "name": session.name}, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def submit(self, request: Request, pk: str | None = None) -> Response:
        try:
            calendar = services_calendar.submit_calendar(self.get_object())
        except DjangoValidationError as exc:
            _raise_drf(exc)
        return Response(self.get_serializer(calendar).data)

    @action(detail=True, methods=["post"])
    def approve(self, request: Request, pk: str | None = None) -> Response:
        try:
            calendar = services_calendar.approve_calendar(
                self.get_object(),
                approved_by_name=str(request.data.get("approved_by_name") or ""),
            )
        except DjangoValidationError as exc:
            _raise_drf(exc)
        return Response(self.get_serializer(calendar).data)

    @action(detail=True, methods=["post"])
    def reopen(self, request: Request, pk: str | None = None) -> Response:
        try:
            calendar = services_calendar.reopen_calendar(self.get_object())
        except DjangoValidationError as exc:
            _raise_drf(exc)
        return Response(self.get_serializer(calendar).data)

    @action(detail=True, methods=["get"])
    def track(self, request: Request, pk: str | None = None) -> Response:
        # KS: zümre daraltması yok (B7) — matris hep tam görünür.
        return Response(services_calendar.track_matrix(self.get_object()))

    @action(detail=True, methods=["post"], url_path="track/mark")
    def track_mark(self, request: Request, pk: str | None = None) -> Response:
        # OYS Tur 644: korumasız int() sayısal olmayan girdide 500 üretiyordu.
        entry_id = _int_or_none(request.data.get("entry_id"))
        item_id = _int_or_none(request.data.get("item_id"))
        entry = selectors.get_calendar_entry(entry_id) if entry_id is not None else None
        item = selectors.get_track_item(item_id) if item_id is not None else None
        if entry is None or item is None or entry.calendar_id != self.get_object().pk:
            raise drf_serializers.ValidationError({"entry_id": "Geçerli girdi ve kalem gerekli."})
        # Gövdede note anahtarı yoksa mevcut not korunur (OYS sözleşmesi).
        note_raw = request.data.get("note", None)
        try:
            mark = services_calendar.set_track_mark(
                entry=entry,
                item=item,
                status=request.data.get("status"),
                note=None if note_raw is None else str(note_raw),
                marked_by_name=str(request.data.get("marked_by_name") or ""),
            )
        except DjangoValidationError as exc:
            _raise_drf(exc)
        cell: dict[str, Any] = {"item_id": item.pk, "status": None}
        if mark is not None:
            cell = {
                "item_id": item.pk,
                "status": mark.status,
                "note": mark.note,
                "marked_by_name": mark.marked_by_name,
                "marked_at": mark.marked_at.isoformat(),
            }
        return Response({"cell": cell})


class ExamCalendarEntryViewSet(viewsets.GenericViewSet[ExamCalendarEntry]):
    """Takvim girdisi düzenleme + yerleştirme."""

    serializer_class = ExamCalendarEntrySerializer

    def get_queryset(self) -> QuerySet[ExamCalendarEntry]:
        return ExamCalendarEntry.objects.select_related("calendar", "course")

    def partial_update(self, request: Request, pk: str | None = None) -> Response:
        entry = self.get_object()
        serializer = self.get_serializer(entry, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            entry = services_calendar.update_calendar_entry(
                entry,
                is_butterfly=data.get("is_butterfly"),
                exam_kind=data.get("exam_kind"),
                authority=data.get("authority"),
                participant_type=data.get("participant_type"),
                section_ids=data.get("section_ids"),
                note=data.get("note"),
            )
        except DjangoValidationError as exc:
            _raise_drf(exc)
        return Response(self.get_serializer(entry).data)

    def destroy(self, request: Request, pk: str | None = None) -> Response:
        try:
            services_calendar.remove_calendar_entry(self.get_object())
        except DjangoValidationError as exc:
            _raise_drf(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def place(self, request: Request, pk: str | None = None) -> Response:
        on_date = _parse_date(request.data.get("date"))
        period_no = _int_or_none(request.data.get("period_no"))
        if on_date is None or period_no is None:
            raise drf_serializers.ValidationError({"date": "Tarih ve ders saati gerekli."})
        try:
            result = services_calendar.place_entry(
                self.get_object(), on_date=on_date, period_no=period_no
            )
        except DjangoValidationError as exc:
            _raise_drf(exc)
        return Response(
            {"entry": self.get_serializer(result.entry).data, "warnings": result.warnings}
        )

    @action(detail=True, methods=["post"])
    def unplace(self, request: Request, pk: str | None = None) -> Response:
        try:
            entry = services_calendar.unplace_entry(self.get_object())
        except DjangoValidationError as exc:
            _raise_drf(exc)
        return Response(self.get_serializer(entry).data)


class ExamTrackItemViewSet(viewsets.ModelViewSet[ExamTrackItem]):
    """Süreç kalemi kataloğu (GLOBAL)."""

    serializer_class = ExamTrackItemSerializer
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self) -> QuerySet[ExamTrackItem]:
        include_inactive = self.request.query_params.get("include_inactive") == "true"
        return selectors.track_items(include_inactive=include_inactive)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = services_calendar.create_track_item(
                name=serializer.validated_data["name"],
                description=serializer.validated_data.get("description", ""),
            )
        except DjangoValidationError as exc:
            _raise_drf(exc)
        return Response(self.get_serializer(item).data, status=status.HTTP_201_CREATED)

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        item = self.get_object()
        serializer = self.get_serializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            item = services_calendar.update_track_item(
                item,
                name=data.get("name"),
                description=data.get("description"),
                is_active=data.get("is_active"),
            )
        except DjangoValidationError as exc:
            _raise_drf(exc)
        return Response(self.get_serializer(item).data)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self.get_object().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# Yardımcılar
# --------------------------------------------------------------------------- #


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _active_year_id() -> int | None:
    year = okul_selectors.active_school_year()
    return year.pk if year is not None else None
