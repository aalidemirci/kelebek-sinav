"""Ders havuzu URL'leri."""

from __future__ import annotations

from django.urls import path

from apps.dersler import views

urlpatterns = [
    path("courses/", views.CourseListCreateView.as_view(), name="course-list"),
    path("courses/duplicates/", views.CourseDuplicatesView.as_view(), name="course-duplicates"),
    path("courses/merge/", views.CourseMergeView.as_view(), name="course-merge"),
    path("courses/<int:pk>/", views.CourseDetailView.as_view(), name="course-detail"),
]
