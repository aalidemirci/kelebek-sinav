"""Ders havuzu DRF serializer'ları — doğrulama serviste (normalize_levels)."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.dersler.models import Course, CourseExamMode
from apps.dersler.services import level_label

#: Sınav biçimi değeri → Türkçe etiket. `CourseExamMode.choices` sözlüğü tek
#: yerde çözülür; bilinmeyen değer (eski kayıt/elle yazım) ham dönerse arayüz
#: boş hücre göstermez.
_EXAM_MODE_LABELS: dict[str, str] = dict(CourseExamMode.choices)


class CourseSerializer(serializers.ModelSerializer[Course]):
    level_labels = serializers.SerializerMethodField()
    exam_mode_label = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id",
            "name",
            "levels",
            "level_labels",
            "course_type",
            "exam_mode",
            "exam_mode_label",
            "source",
            "is_active",
        ]
        read_only_fields = ["source"]

    def get_level_labels(self, obj: Course) -> list[str]:
        return [level_label(int(lvl)) for lvl in (obj.levels or [])]

    def get_exam_mode_label(self, obj: Course) -> str:
        return _EXAM_MODE_LABELS.get(obj.exam_mode, obj.exam_mode)


class CourseMergeSerializer(serializers.Serializer[dict[str, Any]]):
    duplicate = serializers.IntegerField()
    canonical = serializers.IntegerField()
