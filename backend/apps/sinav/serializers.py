"""sinav DRF serializer'ları — salon (F2) + oturum (F3) + kitapçık (F5) + takvim (F6)."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.sinav import services
from apps.sinav.models import (
    BookletRun,
    ExamAttendanceRecord,
    ExamCalendar,
    ExamCalendarEntry,
    ExamRoom,
    ExamSession,
    ExamSessionCourse,
    ExamSessionRoom,
    ExamTrackItem,
    NumberingScheme,
    PlacementRule,
    QuestionDocument,
    ScoreMode,
    SeatAssignment,
)


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


# ===========================================================================
# F3 — oturum akışı serializer'ları
# ===========================================================================


class ExamSessionCourseSerializer(serializers.ModelSerializer[ExamSessionCourse]):
    """Oturum dersi — TEK seviye + katılımcı tanımı (asıl doğrulama services'te).

    Tur 241: satır tek `level` taşır; `display_label` "Matematik — 9. Sınıf"
    görünümünü hazır verir. GROUPS tipi alınmadı (TB7).
    """

    course_id = serializers.IntegerField()
    course_name = serializers.CharField(source="course.name", read_only=True)
    level = serializers.IntegerField(required=False, allow_null=True)
    display_label = serializers.SerializerMethodField()

    class Meta:
        model = ExamSessionCourse
        fields = (
            "id",
            "course_id",
            "course_name",
            "participant_type",
            "level",
            "display_label",
            "section_ids",
            "duration_minutes",
            "shared_booklet",
        )
        read_only_fields = ("id", "course_name", "display_label")

    def get_display_label(self, obj: ExamSessionCourse) -> str:
        return services.session_course_label(
            obj.course.name, obj.level, shared_booklet=obj.shared_booklet
        )


class ExamSessionRoomSerializer(serializers.ModelSerializer[ExamSessionRoom]):
    """Oturum salonu satırı (okuma)."""

    room_id = serializers.IntegerField(source="room.pk", read_only=True)
    room_name = serializers.CharField(source="room.name", read_only=True)

    class Meta:
        model = ExamSessionRoom
        fields = ("id", "room_id", "room_name", "order", "capacity_override")
        read_only_fields = fields


class ExamSessionSerializer(serializers.ModelSerializer[ExamSession]):
    """Sınav oturumu. Durum/onay alanları salt-okunur — geçişler servislerde.

    `term_id` model alanı `semester_id`'ye eşlenir (OYS core.Semester →
    KS okul.SchoolTerm köprüsü); view servis çağrısında adı çevirir.
    """

    term_id = serializers.IntegerField(source="semester_id")
    term_label = serializers.SerializerMethodField()
    courses = ExamSessionCourseSerializer(many=True, read_only=True)
    rooms = ExamSessionRoomSerializer(many=True, read_only=True)

    class Meta:
        model = ExamSession
        fields = (
            "id",
            "name",
            "exam_date",
            "start_time",
            "duration_minutes",
            "session_type",
            "layout_mode",
            "proctors_enabled",
            "term_id",
            "term_label",
            "status",
            "transfer_check_confirmed_by_name",
            "transfer_check_confirmed_at",
            "approved_by_name",
            "approved_at",
            "courses",
            "rooms",
        )
        read_only_fields = (
            "id",
            "term_label",
            "status",
            "transfer_check_confirmed_by_name",
            "transfer_check_confirmed_at",
            "approved_by_name",
            "approved_at",
            "courses",
            "rooms",
        )

    def get_term_label(self, obj: ExamSession) -> str:
        return str(obj.semester)


class SessionRoomsUpdateSerializer(serializers.Serializer[Any]):
    """`PUT .../rooms/` girdisi — sıra liste sırasından gelir."""

    class _Entry(serializers.Serializer[Any]):
        room_id = serializers.IntegerField(min_value=1)
        capacity_override = serializers.IntegerField(
            min_value=1, max_value=200, required=False, allow_null=True
        )

    rooms = _Entry(many=True)


class ParticipantSerializer(serializers.Serializer[Any]):
    """Çözümlenmiş katılımcı (anlık görünüm — DB'de tutulmaz)."""

    student_id = serializers.IntegerField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    student_number = serializers.CharField(read_only=True)
    class_level = serializers.IntegerField(read_only=True)
    class_section = serializers.CharField(read_only=True)
    course_id = serializers.IntegerField(read_only=True)
    course_name = serializers.CharField(read_only=True)
    conflict_group = serializers.CharField(read_only=True)


class DistributeSerializer(serializers.Serializer[Any]):
    """`POST .../distribute/` girdisi — seed verilmezse rastgele üretilir."""

    seed = serializers.IntegerField(min_value=1, max_value=999_999, required=False)
    strict = serializers.BooleanField(required=False, default=False)


class SeatAssignmentSerializer(serializers.ModelSerializer[SeatAssignment]):
    """Yerleşim satırı (snapshot) — kişisel veri içerir (şifreli ad çözülür)."""

    room_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = SeatAssignment
        fields = (
            "id",
            "room_id",
            "seat_no",
            "desk_row",
            "desk_col",
            "slot",
            "student_id",
            "full_name",
            "student_number",
            "class_label",
            "conflict_group",
            "status",
        )
        read_only_fields = fields


class PlacementRuleSerializer(serializers.ModelSerializer[PlacementRule]):
    """Yerleştirme kuralı — ÖZEL NİTELİKLİ veriye işaret (KVKK md. 6).

    Gerekçe yalnız kategori; serbest metin alanı YOK. Öğrenci adı UI
    kolaylığı için döner (şifreli alan Python'da çözülür).
    """

    student_id = serializers.IntegerField()
    student_name = serializers.SerializerMethodField()
    session_id = serializers.IntegerField(required=False, allow_null=True)
    target_room_id = serializers.IntegerField(required=False, allow_null=True)
    target_room_name = serializers.SerializerMethodField()

    class Meta:
        model = PlacementRule
        fields = (
            "id",
            "student_id",
            "student_name",
            "scope",
            "session_id",
            "rule_type",
            "target_room_id",
            "target_room_name",
            "reason_category",
        )
        read_only_fields = ("id", "student_name", "target_room_name")

    def get_student_name(self, obj: PlacementRule) -> str:
        # F27: anonimleştirilmiş arşiv kurallarında öğrenci bağı koparılmıştır.
        return obj.student.full_name if obj.student is not None else "—"

    def get_target_room_name(self, obj: PlacementRule) -> str:
        return obj.target_room.name if obj.target_room is not None else ""


class ExamAttendanceRecordSerializer(serializers.ModelSerializer[ExamAttendanceRecord]):
    """Sınav yoklama kaydı — snapshot alanlar salt-okunur (KİŞİSEL VERİ)."""

    room_name = serializers.CharField(source="room.name", read_only=True)

    class Meta:
        model = ExamAttendanceRecord
        fields = (
            "id",
            "student_id",
            "full_name",
            "student_number",
            "class_label",
            "room_id",
            "room_name",
            "seat_no",
            "excuse_status",
            "note",
            "created_at",
        )
        read_only_fields = (
            "id",
            "student_id",
            "full_name",
            "student_number",
            "class_label",
            "room_id",
            "room_name",
            "seat_no",
            "created_at",
        )


class AttendanceMarkSerializer(serializers.Serializer[dict[str, object]]):
    """Girmedi işaretleme girdisi — referans SeatAssignment'tır."""

    session_id = serializers.IntegerField()
    seat_assignment_id = serializers.IntegerField()
    excuse_status = serializers.CharField(required=False, default="PENDING")
    note = serializers.CharField(required=False, allow_blank=True, default="")


class QuestionUploadSerializer(serializers.Serializer[Any]):
    """`POST /exam-session-courses/<id>/question/` girdisi (multipart)."""

    file = serializers.FileField(help_text="Soru PDF'i.")
    score_mode = serializers.ChoiceField(
        choices=ScoreMode.choices, required=False, default=ScoreMode.SINGLE_BOX
    )
    question_count = serializers.IntegerField(
        min_value=1, max_value=60, required=False, allow_null=True
    )
    # OYS Tur 236: scaling_enabled kaldırıldı — eski istemcinin gönderdiği
    # anahtar DRF tarafından sessizce yutulur.


class QuestionDocumentSerializer(serializers.ModelSerializer[QuestionDocument]):
    """Soru dosyası özeti (dosya içeriği ayrı uçtan indirilir)."""

    course_name = serializers.CharField(source="session_course.course.name", read_only=True)

    class Meta:
        model = QuestionDocument
        fields = (
            "id",
            "course_name",
            "page_count",
            "sha256",
            "score_mode",
            "question_count",
            "created_at",
        )
        read_only_fields = fields


class BookletRunSerializer(serializers.ModelSerializer[BookletRun]):
    """Kitapçık koşusu durumu (manifest PII içermez)."""

    class Meta:
        model = BookletRun
        fields = (
            "id",
            "status",
            "backup_copies",
            "manifest",
            "error_message",
            "created_at",
            "completed_at",
        )
        read_only_fields = fields


# --------------------------------------------------------------------------- #
# F6 — sınav takvimi (OYS FAZ T2 serializer'larından UYARLA)
# --------------------------------------------------------------------------- #


class ExamCalendarSerializer(serializers.ModelSerializer[ExamCalendar]):
    """Takvim kaydı. Yazma servis katmanında (create/update_exam_calendar).

    KS: `school_year` FK'sı modelde yok — yıl adı dönem üzerinden okunur;
    onay damgası (approved_by_name) FE onay özetinde gösterilir (B12).
    """

    semester_name = serializers.CharField(source="semester.name", read_only=True)
    school_year_name = serializers.CharField(source="semester.school_year.name", read_only=True)
    # Ad opsiyonel — verilmezse servis "1. Dönem 1. Sınav Takvimi" üretir.
    # OYS Tur 644: elle override modelin max_length'ini düşürmüştü; tur 1-3'e sabit.
    name = serializers.CharField(required=False, allow_blank=True, max_length=120)
    round = serializers.IntegerField(min_value=1, max_value=3)

    class Meta:
        model = ExamCalendar
        fields = (
            "id",
            "school_year_name",
            "semester",
            "semester_name",
            "round",
            "name",
            "start_date",
            "end_date",
            "status",
            "description_text",
            "submitted_at",
            "approved_by_name",
            "approved_at",
        )
        read_only_fields = (
            "id",
            "school_year_name",
            "semester_name",
            "status",
            "submitted_at",
            "approved_by_name",
            "approved_at",
        )
        validators: list[object] = []


class ExamCalendarEntrySerializer(serializers.ModelSerializer[ExamCalendarEntry]):
    course_name = serializers.CharField(source="course.name", read_only=True)

    class Meta:
        model = ExamCalendarEntry
        fields = (
            "id",
            "calendar",
            "course",
            "course_name",
            "level",
            "exam_kind",
            "is_butterfly",
            "placed_date",
            "period_no",
            "session",
            "note",
        )
        read_only_fields = (
            "id",
            "course_name",
            "calendar",
            "placed_date",
            "period_no",
            "session",
        )
        validators: list[object] = []


class ExamTrackItemSerializer(serializers.ModelSerializer[ExamTrackItem]):
    class Meta:
        model = ExamTrackItem
        fields = ("id", "name", "description", "order", "is_active")
        read_only_fields = ("id", "order")
        validators: list[object] = []
