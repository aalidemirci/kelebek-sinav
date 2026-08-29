"""sinav DRF view'ları — ince katman; mantık services.py'da.

OYS view'larından UYARLA: izin sınıfları/denetim/OpenAPI süslemeleri düşer
(authsuz tek kullanıcı); `layout-pdf` ve rapor uçları F4'te (WeasyPrint
şablonlarıyla) gelir. Salon silme ucu yok: `is_active=False` ile pasifleştirilir.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers as drf_serializers
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.sinav import participants as sinav_participants
from apps.sinav import selectors, services
from apps.sinav.models import (
    ExamAttendanceRecord,
    ExamRoom,
    ExamSession,
    ExamSessionCourse,
    PlacementRule,
)
from apps.sinav.serializers import (
    AttendanceMarkSerializer,
    DistributeSerializer,
    ExamAttendanceRecordSerializer,
    ExamRoomSerializer,
    ExamSessionCourseSerializer,
    ExamSessionRoomSerializer,
    ExamSessionSerializer,
    ParticipantSerializer,
    PlacementRuleSerializer,
    SeatAssignmentSerializer,
    SeatSerializer,
    SessionRoomsUpdateSerializer,
)


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


# ===========================================================================
# F3 — oturum akışı view'ları
# ===========================================================================


def _report_payload(report: Any) -> dict[str, Any]:
    """Doğrulayıcı raporunu API sözlüğüne çevirir (K1 metrikleri dahil)."""
    return {
        "is_valid": report.is_valid,
        "hard_violations": report.hard_violations,
        "first_ring_same_group_pairs": report.first_ring_same_group_pairs,
        "min_same_group_distance": report.min_same_group_distance,
        "proximity_score": round(report.proximity_score, 4),
        # K1 gözlemlenebilirlik (additive): aynı-şube komşu çifti + salon
        # başına yerleşen sayısı (anahtarlar str — JSON sözleşmesi).
        "cross_group_same_section_first_ring_pairs": (
            report.cross_group_same_section_first_ring_pairs
        ),
        "room_counts": {str(k): v for k, v in sorted(report.room_counts.items())},
    }


class ExamSessionViewSet(viewsets.ModelViewSet[ExamSession]):
    """Sınav oturumları — sihirbaz + dağıtım + durum makinesi uçları.

    Taslak dışı oturum services._ensure_draft ile korunur; onay yalnız
    İHLALSİZ yerleşimde (servis guard'ı).
    """

    serializer_class = ExamSessionSerializer
    http_method_names = ["get", "post", "patch", "put", "delete"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return selectors.exam_sessions(status=self.request.query_params.get("status") or None)

    @staticmethod
    def _service_data(validated: dict[str, Any]) -> dict[str, Any]:
        """Serializer iç anahtarını servis imzasına çevirir (semester_id→term_id)."""
        data = dict(validated)
        if "semester_id" in data:
            data["term_id"] = data.pop("semester_id")
        return data

    def perform_create(self, serializer: drf_serializers.BaseSerializer[ExamSession]) -> None:
        data = self._service_data(dict(serializer.validated_data or {}))
        try:
            serializer.instance = services.create_exam_session(**data)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc

    def perform_update(self, serializer: drf_serializers.BaseSerializer[ExamSession]) -> None:
        instance = serializer.instance
        assert instance is not None
        data = self._service_data(dict(serializer.validated_data or {}))
        try:
            serializer.instance = services.update_exam_session(instance, **data)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Taslak oturumu kaldırır (soft-delete)."""
        session = self.get_object()
        try:
            services.remove_exam_session(session)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(status=204)

    # --- Sihirbaz uçları ---------------------------------------------------
    @action(detail=False, methods=["get"], url_path="pre-check")
    def pre_check(self, request: Request) -> Response:
        """`GET /exam-sessions/pre-check/` — Adım 0 verisi (sayılar; PII yok)."""
        return Response(services.pre_check_summary())

    @action(detail=False, methods=["get"])
    def terms(self, request: Request) -> Response:
        """Adım 1 dönem seçici — aktif ders yılının dönemleri (id + etiket)."""
        return Response({"terms": services.term_options()})

    @action(detail=True, methods=["post"], url_path="confirm-transfer-check")
    def confirm_transfer_check(self, request: Request, pk: str | None = None) -> Response:
        """Adım 0 beyan kutusu — kim/ne zaman oturuma yazılır (B10)."""
        session = self.get_object()
        try:
            session = services.confirm_transfer_check(
                session,
                confirmed_by_name=str(request.data.get("confirmed_by_name") or ""),
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(ExamSessionSerializer(session).data)

    @action(detail=True, methods=["post"])
    def courses(self, request: Request, pk: str | None = None) -> Response:
        """Oturuma ders + katılımcı tanımı ekler (Adım 2)."""
        session = self.get_object()
        serializer = ExamSessionCourseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = dict(serializer.validated_data or {})
        try:
            row = services.add_session_course(session, **data)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(ExamSessionCourseSerializer(row).data, status=201)

    @action(detail=True, methods=["put"])
    def rooms(self, request: Request, pk: str | None = None) -> Response:
        """Oturum salon listesini eşitler (Adım 3; replace semantiği)."""
        session = self.get_object()
        serializer = SessionRoomsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            rows = services.set_session_rooms(
                session,
                [dict(entry) for entry in serializer.validated_data["rooms"]],
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response({"rooms": ExamSessionRoomSerializer(rows, many=True).data})

    @action(detail=True, methods=["get"])
    def participants(self, request: Request, pk: str | None = None) -> Response:
        """Katılımcı çözümü — ders bazlı liste + çakışma/uyarılar (Adım 2/4)."""
        session = self.get_object()
        resolution = sinav_participants.resolve_session(session)
        cross = sinav_participants.overlapping_session_conflicts(session)
        return Response(
            {
                "total_count": resolution.total_count,
                "has_blocking_conflicts": resolution.has_blocking_conflicts,
                "warnings": [*resolution.warnings, *cross],
                "courses": [
                    {
                        "session_course_id": c.session_course_id,
                        "course_id": c.course_id,
                        "course_name": c.course_name,
                        "count": c.count,
                        "warnings": c.warnings,
                        "participants": ParticipantSerializer(c.participants, many=True).data,
                    }
                    for c in resolution.courses
                ],
            }
        )

    # --- Dağıtım + yerleşim ------------------------------------------------
    @action(detail=True, methods=["post"])
    def distribute(self, request: Request, pk: str | None = None) -> Response:
        """Dağıt & Önizle (Adım 4) — motor + bağımsız doğrulama + snapshot yazımı."""
        session = self.get_object()
        serializer = DistributeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        try:
            session, result, report = services.distribute_session(
                session,
                seed=vd.get("seed"),
                strict=vd.get("strict", False),
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(
            {
                "status": session.status,
                "seed": result.seed,
                "checkerboard": result.checkerboard,
                "placed": len(result.placements),
                "warnings": result.warnings,
                "report": _report_payload(report),
            }
        )

    @action(detail=True, methods=["get"])
    def seating(self, request: Request, pk: str | None = None) -> Response:
        """Kayıtlı yerleşim (salon bazlı) + doğrulama metrikleri + doluluk."""
        session = self.get_object()
        assignments = list(selectors.session_seat_assignments(session.pk))
        report = services.seating_report(session)

        rooms_payload: list[dict[str, Any]] = []
        for assignment in assignments:
            if not rooms_payload or rooms_payload[-1]["room_id"] != assignment.room_id:
                rooms_payload.append(
                    {
                        "room_id": assignment.room_id,
                        "room_name": assignment.room.name,
                        "assignments": [],
                    }
                )
            rooms_payload[-1]["assignments"].append(SeatAssignmentSerializer(assignment).data)
        # Lejant için grup anahtarı → insan-okur etiket (Tur 241 talep 9a).
        group_keys = {a.conflict_group for a in assignments}
        return Response(
            {
                "session_id": session.pk,
                "status": session.status,
                "distribution_params": session.distribution_params,
                "conflict_group_labels": services.conflict_group_labels(group_keys),
                "rooms": rooms_payload,
                "report": _report_payload(report),
                # K1 (additive): salon doluluk özeti — FE doluluk çipleri.
                "occupancy": services.room_occupancy(session),
            }
        )

    @action(detail=True, methods=["post"], url_path="swap-seats")
    def swap_seats(self, request: Request, pk: str | None = None) -> Response:
        """İki koltuğu takas eder (önizleme) — anlık doğrulayıcı raporu döner."""
        session = self.get_object()
        a_raw = request.data.get("assignment_a", "")
        b_raw = request.data.get("assignment_b", "")
        if not (str(a_raw).isdigit() and str(b_raw).isdigit()):
            raise drf_serializers.ValidationError("assignment_a ve assignment_b sayısal id olmalı.")
        try:
            swapped, report = services.swap_seats(
                session,
                assignment_a_id=int(a_raw),
                assignment_b_id=int(b_raw),
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(
            {
                "swapped": SeatAssignmentSerializer(swapped, many=True).data,
                "report": _report_payload(report),
            }
        )

    # --- Durum makinesi ----------------------------------------------------
    def _transition(self, transition: Any) -> Response:
        """Durum geçişi ortak gövdesi — hata Türkçe 400'e çevrilir."""
        session = self.get_object()
        try:
            session = transition(session)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(ExamSessionSerializer(session).data)

    @action(detail=True, methods=["post"])
    def approve(self, request: Request, pk: str | None = None) -> Response:
        """Oturumu onaylar — yerleşim ihlalsizse DAĞITILDI → ONAYLANDI (kilit)."""
        session = self.get_object()
        try:
            session = services.approve_session(
                session,
                approved_by_name=str(request.data.get("approved_by_name") or ""),
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(ExamSessionSerializer(session).data)

    @action(detail=True, methods=["post"])
    def reopen(self, request: Request, pk: str | None = None) -> Response:
        """Onayı geri alır — ONAYLANDI → DAĞITILDI (yanlış onay telafisi)."""
        return self._transition(services.reopen_session)

    @action(detail=True, methods=["post"])
    def archive(self, request: Request, pk: str | None = None) -> Response:
        """Arşivler — ONAYLANDI → ARŞİV (salt-okunur; yeniden basım açık)."""
        return self._transition(services.archive_session)


class ExamSessionCourseViewSet(viewsets.GenericViewSet[ExamSessionCourse]):
    """Oturum dersi güncelle/çıkar — `/exam-session-courses/<id>/`."""

    serializer_class = ExamSessionCourseSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return ExamSessionCourse.objects.select_related("session", "course")

    def partial_update(self, request: Request, pk: str | None = None) -> Response:
        sc = self.get_object()
        serializer = ExamSessionCourseSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = dict(serializer.validated_data or {})
        data.pop("course_id", None)  # ders değiştirilemez; çıkar + yeniden ekle
        try:
            sc = services.update_session_course(sc, **data)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(ExamSessionCourseSerializer(sc).data)

    def destroy(self, request: Request, pk: str | None = None) -> Response:
        sc = self.get_object()
        try:
            services.remove_session_course(sc)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(status=204)


class PlacementRuleViewSet(viewsets.ModelViewSet[PlacementRule]):
    """Yerleştirme kuralları — güncelleme YOK (kaldır + yeniden ekle: tarihsel iz).

    `reason_category` kategori düzeyinde bile özel nitelikli veriye işaret
    eder (KVKK md. 6); serbest metin alanı yoktur. Silme soft-delete.
    """

    serializer_class = PlacementRuleSerializer
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        params = self.request.query_params
        session_raw = params.get("session")
        return selectors.placement_rules(
            session_id=int(session_raw) if session_raw and session_raw.isdigit() else None,
        )

    def perform_create(self, serializer: drf_serializers.BaseSerializer[PlacementRule]) -> None:
        data: dict[str, Any] = dict(serializer.validated_data or {})
        session_id = data.pop("session_id", None)
        session = selectors.get_exam_session(session_id) if session_id is not None else None
        if session_id is not None and session is None:
            raise drf_serializers.ValidationError("Oturum bulunamadı.")
        try:
            serializer.instance = services.create_placement_rule(session=session, **data)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        rule = self.get_object()
        services.remove_placement_rule(rule)
        return Response(status=204)


class ExamAttendanceRecordViewSet(viewsets.ModelViewSet[ExamAttendanceRecord]):
    """Sınav yoklama kayıtları (Tur 245).

    Girmedi işaretleme yalnız ONAYLI/ARŞİV oturumda (servis guard'ı);
    mazeret durumu/notu ARŞİVDE DE güncellenebilir (belge sonradan gelir).
    Silme = soft-delete (yanlış işaretleme telafisi).
    """

    serializer_class = ExamAttendanceRecordSerializer
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        params = self.request.query_params
        session_raw = params.get("session")
        return selectors.attendance_records(
            session_id=int(session_raw) if session_raw and session_raw.isdigit() else None,
        )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = AttendanceMarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd: dict[str, Any] = dict(serializer.validated_data)
        session = selectors.get_exam_session(int(vd["session_id"]))
        if session is None:
            raise drf_serializers.ValidationError("Oturum bulunamadı.")
        try:
            record = services.mark_absent(
                session,
                seat_assignment_id=int(vd["seat_assignment_id"]),
                excuse_status=str(vd.get("excuse_status") or "PENDING"),
                note=str(vd.get("note") or ""),
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(ExamAttendanceRecordSerializer(record).data, status=201)

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        record = self.get_object()
        serializer = ExamAttendanceRecordSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            record = services.update_attendance_record(
                record, **dict(serializer.validated_data or {})
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(ExamAttendanceRecordSerializer(record).data)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        record = self.get_object()
        services.unmark_absent(record)
        return Response(status=204)
