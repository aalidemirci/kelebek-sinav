"""sinav URL'leri — DRF router (kebab-case, çoğul kaynak)."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.sinav.views import ExamRoomViewSet

router = DefaultRouter()
router.register("exam-rooms", ExamRoomViewSet, basename="exam-room")

urlpatterns = router.urls
