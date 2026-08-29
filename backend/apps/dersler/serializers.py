"""Ders havuzu DRF serializer'ları — doğrulama serviste (normalize_levels)."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.dersler.models import Course
from apps.dersler.services import level_label


class CourseSerializer(serializers.ModelSerializer[Course]):
    level_labels = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id",
            "name",
            "levels",
            "level_labels",
            "course_type",
            "source",
            "is_active",
        ]
        read_only_fields = ["source"]

    def get_level_labels(self, obj: Course) -> list[str]:
        return [level_label(int(lvl)) for lvl in (obj.levels or [])]


class CourseMergeSerializer(serializers.Serializer[dict[str, Any]]):
    duplicate = serializers.IntegerField()
    canonical = serializers.IntegerField()
