"""sinav DRF view'ları — ince katman; mantık services.py'da.

OYS view'larından UYARLA: izin sınıfları/denetim/OpenAPI süslemeleri düşer
(authsuz tek kullanıcı); `layout-pdf` + rapor uçları F4'te WeasyPrint
şablonlarıyla geldi. Salon silme ucu yok: `is_active=False` ile pasifleştirilir.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import QuerySet
from django.http import FileResponse, HttpResponse
from rest_framework import serializers as drf_serializers
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.sinav import participants as sinav_participants
from apps.sinav import selectors, services
from apps.sinav.models import (
    BookletRun,
    BookletRunStatus,
    ExamAttendanceRecord,
    ExamRoom,
    ExamRoomGroup,
    ExamSession,
    ExamSessionCourse,
    PlacementRule,
    ProctorAssignment,
    ProctorExemption,
)
from apps.sinav.serializers import (
    AttendanceMarkSerializer,
    BookletRunSerializer,
    CopySessionPlanSerializer,
    DistributeSerializer,
    ExamAttendanceRecordSerializer,
    ExamRoomGroupSerializer,
    ExamRoomSerializer,
    ExamSessionCourseSerializer,
    ExamSessionRoomSerializer,
    ExamSessionSerializer,
    ParticipantSerializer,
    PlacementRuleSerializer,
    ProctorAssignmentSerializer,
    ProctorAssignSerializer,
    ProctorExemptionSerializer,
    QuestionDocumentSerializer,
    QuestionUploadSerializer,
    RoomGroupAssignSerializer,
    SeatAssignmentSerializer,
    SeatSerializer,
    SessionRoomsUpdateSerializer,
)


class ExamRoomGroupViewSet(viewsets.ModelViewSet[ExamRoomGroup]):
    """Derslik kümeleri (Sabah/Öğle gibi) — yalnız seçim kolaylığı."""

    serializer_class = ExamRoomGroupSerializer
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        # DETAY yolları (PATCH/DELETE) QuerySet ister — sıralı LİSTE burada
        # döndürülemez, `list()` içinde döndürülür.
        return selectors.exam_room_groups()

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Sıralama Türk alfabesiyle Python'da (SQLite BINARY karşılaştırır)."""
        rows = selectors.exam_room_groups_sorted()
        page = self.paginate_queryset(rows)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(rows, many=True).data)

    def perform_create(self, serializer: drf_serializers.BaseSerializer[ExamRoomGroup]) -> None:
        serializer.instance = services.create_room_group(**dict(serializer.validated_data))

    def perform_update(self, serializer: drf_serializers.BaseSerializer[ExamRoomGroup]) -> None:
        instance = serializer.instance
        assert instance is not None
        serializer.instance = services.update_room_group(
            instance, **dict(serializer.validated_data)
        )

    def perform_destroy(self, instance: ExamRoomGroup) -> None:
        services.delete_room_group(instance)

    @action(detail=False, methods=["post"])
    def assign(self, request: Request) -> Response:
        """`POST /exam-room-groups/assign/` — salonları topluca kümeye alır."""
        serializer = RoomGroupAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = serializer.validated_data["group"]
        try:
            updated = services.assign_room_group(
                room_ids=list(serializer.validated_data["room_ids"]),
                group_id=group.pk if group is not None else None,
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response({"updated": updated})


class ExamRoomViewSet(viewsets.ModelViewSet[ExamRoom]):
    """Sınav salonları — plan şeması servis katmanında doğrulanır.

    `seats` ucu numaralandırılmış koltuk önizlemesini döner (editör + kroki);
    `preview-seats` KAYDEDİLMEMİŞ planı numaralandırır (iş kuralı tek yerde).
    """

    serializer_class = ExamRoomSerializer
    http_method_names = ["get", "post", "patch"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        # DETAY yolları (PATCH, seats, layout-pdf) QuerySet ister; Türkçe sıralı
        # LİSTE `list()` içinde döndürülür (ExamRoomGroupViewSet emsali).
        return selectors.exam_rooms(
            include_inactive=self.request.query_params.get("include_inactive") == "true"
        )

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Salon listesi TÜRK ALFABESİ sırasıyla (SQLite BINARY karşılaştırır)."""
        rows = selectors.exam_rooms_sorted(
            include_inactive=request.query_params.get("include_inactive") == "true"
        )
        page = self.paginate_queryset(rows)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(rows, many=True).data)

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

    @action(detail=True, methods=["get"], url_path="layout-pdf")
    def layout_pdf(self, request: Request, pk: str | None = None) -> HttpResponse:
        """`GET /exam-rooms/<id>/layout-pdf/` — BOŞ yerleşim planı PDF'i.

        Sınav öncesi dersliği düzenlemek için kapıya asılır; oturumdan
        bağımsızdır ve kişisel veri içermez (`seats` ucu emsali).
        """
        room = self.get_object()
        try:
            report_file = services.render_room_layout_pdf(room)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        response = HttpResponse(report_file.content, content_type=report_file.content_type)
        response["Content-Disposition"] = f'attachment; filename="{report_file.filename}"'
        return response

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

    @action(detail=False, methods=["get"], url_path="question-template")
    def question_template(self, request: Request) -> HttpResponse:
        """`GET /exam-sessions/question-template/` — öğretmen Word şablonu (F5).

        4 cm üst marjlı boş .docx döner; kişisel veri içermez.
        """
        from apps.sinav.word_template import build_question_template_docx

        response = HttpResponse(
            build_question_template_docx(),
            content_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
        )
        response["Content-Disposition"] = 'attachment; filename="soru_sablonu.docx"'
        return response

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

    @action(detail=True, methods=["post"], url_path="copy-plan")
    def copy_plan(self, request: Request, pk: str | None = None) -> Response:
        """Başka oturumun ders+şube ve salon planını bu TASLAĞA kopyalar (Ö5).

        Kopya sihirbazın üstüne gelir ve üzerinde değişiklik yapılabilir. Seed,
        yerleşim, yoklama, gözetmen ve onay damgaları TAŞINMAZ.
        """
        session = self.get_object()
        serializer = CopySessionPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            report = services.copy_session_plan(
                session,
                source_id=serializer.validated_data["source_id"],
                courses=serializer.validated_data["courses"],
                rooms=serializer.validated_data["rooms"],
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        session.refresh_from_db()
        return Response({"session": ExamSessionSerializer(session).data, "report": report})

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

    @action(detail=True, methods=["get"], url_path=r"reports/(?P<code>[a-z0-9]+)")
    def reports(
        self, request: Request, pk: str | None = None, code: str | None = None
    ) -> HttpResponse | Response:
        """Sınav evrakı indirme (F4): R1 · R4-R8 — senkron PDF/Excel.

        `?room_id=` salon bazlı evrakı (R1 salon evrakı / R7 tutanak) tek salona
        daraltır; `code=zip` tüm seti tek arşivde döner. Arşiv oturumdan yeniden
        basım açıktır (durum kapısı serviste).
        """
        session = self.get_object()
        if code != "zip" and code not in services.REPORT_CODES:
            return Response(
                {"code": "not_found", "message": "Bilinmeyen rapor kodu.", "fields": {}},
                status=404,
            )
        room_raw = request.query_params.get("room_id", "")
        room_id = int(room_raw) if room_raw.isdigit() else None
        try:
            if code == "zip":
                report_file = services.render_session_reports_zip(session)
            else:
                report_file = services.render_session_report(session, code, room_id=room_id)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        response = HttpResponse(report_file.content, content_type=report_file.content_type)
        response["Content-Disposition"] = f'attachment; filename="{report_file.filename}"'
        return response

    @action(detail=True, methods=["post"])
    def booklets(self, request: Request, pk: str | None = None) -> Response:
        """Kitapçık koşusu başlatır ve SENKRON üretir (R10 — F5).

        Yanıt tamamlanmış (COMPLETED/FAILED) koşu kaydıdır; ZIP indirme
        `/booklet-runs/<id>/download/` ucundadır (geçmiş izlenebilir kalır).
        """
        session = self.get_object()
        backup_raw = request.data.get("backup_copies", 0)
        backup = int(backup_raw) if str(backup_raw).isdigit() else 0
        try:
            run = services.request_booklet_run(session, backup_copies=min(backup, 10))
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(BookletRunSerializer(run).data, status=201)

    # ÇOK METOTLU `@action` — GET görevlendirme listesi · POST elle atama (F7).
    @action(detail=True, methods=["get", "post"], serializer_class=ProctorAssignmentSerializer)
    def proctors(self, request: Request, pk: str | None = None) -> Response:
        """Gözetmen görevlendirmeleri (U2 — elle atama; oto-öneri yok)."""
        session = self.get_object()
        if request.method == "GET":
            qs = selectors.proctor_assignments(session_id=session.pk)
            return Response(
                {
                    "proctors_enabled": session.proctors_enabled,
                    "assignments": ProctorAssignmentSerializer(qs, many=True).data,
                }
            )
        serializer = ProctorAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        try:
            assignment = services.assign_proctor(
                session,
                teacher_id=vd["teacher_id"],
                role=vd.get("role", "PROCTOR"),
                room_id=vd.get("room_id"),
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(ProctorAssignmentSerializer(assignment).data, status=201)

    @action(detail=True, methods=["get"], url_path="proctor-candidates")
    def proctor_candidates(self, request: Request, pk: str | None = None) -> Response:
        """Atama ekranı: aktif personel havuzu + uygunluk bayrakları (F7)."""
        return Response({"candidates": services.proctor_candidates(self.get_object())})

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

    # ÇOK METOTLU `@action` — GET süresi dolan arşiv adayları · POST kullanıcı
    # onaylı GERİ DÖNÜŞSÜZ anonimleştirme (F27/F8, K14). POST gövdesi aday
    # id listesini AÇIKÇA taşır: FE onay diyaloğu listeyi göstermeden tetik
    # atamaz (risk #9 — aday listesi görülmeden veri kaybı şikâyeti kaçınılmaz).
    @action(detail=False, methods=["get", "post"], url_path="archive-anonymization")
    def archive_anonymization(self, request: Request) -> Response:
        if request.method == "GET":
            return Response(
                {
                    "retention_days": services.EXAM_ARCHIVE_RETENTION_DAYS,
                    "candidates": [
                        {
                            "id": session.pk,
                            "name": session.name,
                            "exam_date": session.exam_date.isoformat(),
                        }
                        for session in services.expired_archive_candidates()
                    ],
                }
            )
        raw_ids = request.data.get("session_ids")
        if not isinstance(raw_ids, list) or not raw_ids:
            raise drf_serializers.ValidationError(
                "Anonimleştirilecek oturumların id listesi (session_ids) zorunludur."
            )
        # bool int'in alt tipidir: JSON `true` → int(True)=1 sessizce id olurdu.
        if not all(isinstance(value, int) and not isinstance(value, bool) for value in raw_ids):
            raise drf_serializers.ValidationError("session_ids yalnız tam sayı içerebilir.")
        session_ids = list(raw_ids)
        try:
            done = services.anonymize_expired_exam_archives(session_ids=session_ids)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response({"anonymized": done})


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

    # ÇOK METOTLU `@action` — tek yolda GET üst veri · POST yükle/değiştir ·
    # DELETE kaldır (OYS Tur 842 kalıbı).
    @action(detail=True, methods=["get", "post", "delete"])
    def question(self, request: Request, pk: str | None = None) -> Response:
        """Soru dosyası ucu (F5) — doğrulama servis katmanında (A4 ±6pt dahil)."""
        sc = self.get_object()
        doc = selectors.question_document_for(sc.pk)
        if request.method == "GET":
            if doc is None:
                return Response(
                    {"code": "not_found", "message": "Soru dosyası yüklenmemiş.", "fields": {}},
                    status=404,
                )
            return Response(QuestionDocumentSerializer(doc).data)
        if request.method == "DELETE":
            if doc is not None:
                doc.delete()
            return Response(status=204)
        serializer = QuestionUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        try:
            doc = services.upload_question_document(
                sc,
                file_bytes=vd["file"].read(),
                score_mode=vd.get("score_mode", "SINGLE_BOX"),
                question_count=vd.get("question_count"),
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(QuestionDocumentSerializer(doc).data, status=201)

    @action(detail=True, methods=["get"], url_path="question/download")
    def question_download(self, request: Request, pk: str | None = None) -> Response | FileResponse:
        """Soru PDF'i indirme — sınav öncesi gizlilik: yalnız yerel API'den sunulur."""
        sc = self.get_object()
        doc = selectors.question_document_for(sc.pk)
        # F27 anonimleştirmesi satırı koruyup dosyayı siler — boş FieldFile
        # açılmaya çalışılırsa ham ValueError 500 olurdu.
        if doc is None or not doc.file:
            return Response(
                {"code": "not_found", "message": "Soru dosyası yüklenmemiş.", "fields": {}},
                status=404,
            )
        return FileResponse(
            doc.file.open("rb"),
            as_attachment=True,
            filename=f"soru_{sc.course.name}.pdf",
            content_type="application/pdf",
        )


class BookletRunViewSet(viewsets.GenericViewSet[BookletRun]):
    """Kitapçık koşuları — durum + ZIP indirme (ZIP kişisel veri içerir)."""

    serializer_class = BookletRunSerializer

    def get_queryset(self) -> QuerySet[BookletRun]:
        params = self.request.query_params
        session_raw = params.get("session", "")
        return selectors.booklet_runs(
            session_id=int(session_raw) if session_raw.isdigit() else None
        )

    def list(self, request: Request) -> Response:
        page = self.paginate_queryset(self.get_queryset())
        serializer = BookletRunSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        return Response(BookletRunSerializer(self.get_object()).data)

    @action(detail=True, methods=["get"])
    def download(self, request: Request, pk: str | None = None) -> Response | FileResponse:
        """ZIP indirme — kitapçıklar öğrenci ad/no taşır; yalnız yerel API'den."""
        run = self.get_object()
        if run.status != BookletRunStatus.COMPLETED or not run.file:
            return Response(
                {"code": "not_ready", "message": "Koşu henüz tamamlanmadı.", "fields": {}},
                status=409,
            )
        return FileResponse(
            run.file.open("rb"),
            as_attachment=True,
            filename=f"kitapciklar_oturum_{run.session_id}.zip",
            content_type="application/zip",
        )


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


class ProctorAssignmentViewSet(viewsets.GenericViewSet[ProctorAssignment]):
    """Görevlendirme satırı — kaldırma + tebellüğ işleme (F7)."""

    serializer_class = ProctorAssignmentSerializer

    def get_queryset(self) -> QuerySet[ProctorAssignment]:
        return selectors.proctor_assignments()

    def destroy(self, request: Request, pk: str | None = None) -> Response:
        assignment = self.get_object()
        try:
            services.remove_proctor_assignment(assignment)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(status=204)

    @action(detail=True, methods=["post"])
    def acknowledge(self, request: Request, pk: str | None = None) -> Response:
        """Tebliğ-tebellüğ işler (imza karşılığı tebliğin sistem izi)."""
        assignment = self.get_object()
        try:
            assignment = services.acknowledge_proctor(assignment)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(ProctorAssignmentSerializer(assignment).data)


class ProctorExemptionViewSet(viewsets.ModelViewSet[ProctorExemption]):
    """Gözetmenlik muafiyetleri (F7) — güncelleme yok: kaldır + yeniden ekle.

    `reason_category` SAĞLIK kategorisinde özel nitelikli veriye işaret eder
    (PlacementRule emsali); serbest metin alanı bilinçle yoktur.
    """

    serializer_class = ProctorExemptionSerializer
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self) -> QuerySet[ProctorExemption]:
        params = self.request.query_params
        session_raw = params.get("session")
        return selectors.proctor_exemptions(
            session_id=int(session_raw) if session_raw and session_raw.isdigit() else None,
        )

    def perform_create(self, serializer: drf_serializers.BaseSerializer[ProctorExemption]) -> None:
        data: dict[str, Any] = dict(serializer.validated_data or {})
        session_id = data.pop("session_id", None)
        session = selectors.get_exam_session(session_id) if session_id is not None else None
        if session_id is not None and session is None:
            raise drf_serializers.ValidationError("Oturum bulunamadı.")
        try:
            serializer.instance = services.create_proctor_exemption(session=session, **data)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        services.remove_proctor_exemption(self.get_object())
        return Response(status=204)
