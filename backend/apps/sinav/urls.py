"""sinav URL'leri — DRF router (kebab-case, çoğul kaynak)."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.sinav.views import (
    BookletRunViewSet,
    ExamAttendanceRecordViewSet,
    ExamRoomGroupViewSet,
    ExamRoomViewSet,
    ExamSessionCourseViewSet,
    ExamSessionViewSet,
    PlacementRuleViewSet,
    ProctorAssignmentViewSet,
    ProctorExemptionViewSet,
)
from apps.sinav.views_calendar import (
    ExamCalendarEntryViewSet,
    ExamCalendarViewSet,
    ExamTrackItemViewSet,
)

router = DefaultRouter()
router.register("exam-rooms", ExamRoomViewSet, basename="exam-room")
router.register("exam-room-groups", ExamRoomGroupViewSet, basename="exam-room-group")
router.register("exam-sessions", ExamSessionViewSet, basename="exam-session")
router.register("exam-session-courses", ExamSessionCourseViewSet, basename="exam-session-course")
router.register("booklet-runs", BookletRunViewSet, basename="booklet-run")
router.register("exam-calendars", ExamCalendarViewSet, basename="exam-calendar")
router.register("exam-calendar-entries", ExamCalendarEntryViewSet, basename="exam-calendar-entry")
router.register("exam-track-items", ExamTrackItemViewSet, basename="exam-track-item")
router.register("placement-rules", PlacementRuleViewSet, basename="placement-rule")
router.register("proctor-assignments", ProctorAssignmentViewSet, basename="proctor-assignment")
router.register("proctor-exemptions", ProctorExemptionViewSet, basename="proctor-exemption")
router.register(
    "exam-attendance-records", ExamAttendanceRecordViewSet, basename="exam-attendance-record"
)

urlpatterns = router.urls
