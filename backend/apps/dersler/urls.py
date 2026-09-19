"""Ders havuzu URL'leri."""

from __future__ import annotations

from django.urls import path

from apps.dersler import views

urlpatterns = [
    path("courses/", views.CourseListCreateView.as_view(), name="course-list"),
    path("courses/catalog-status/", views.CatalogStatusView.as_view(), name="catalog-status"),
    path("courses/resync/", views.CatalogResyncView.as_view(), name="catalog-resync"),
    path("courses/duplicates/", views.CourseDuplicatesView.as_view(), name="course-duplicates"),
    path(
        "courses/section-offerings/",
        views.CourseSectionOfferingsView.as_view(),
        name="course-section-offerings",
    ),
    path("courses/merge/", views.CourseMergeView.as_view(), name="course-merge"),
    path(
        "courses/enrollment-counts/",
        views.CourseEnrollmentCountsView.as_view(),
        name="course-enrollment-counts",
    ),
    path(
        "courses/enrollments/import/preview/",
        views.EnrollmentImportPreviewView.as_view(),
        name="course-enrollments-import-preview",
    ),
    path(
        "courses/enrollments/import/commit/",
        views.EnrollmentImportCommitView.as_view(),
        name="course-enrollments-import-commit",
    ),
    path("courses/<int:pk>/", views.CourseDetailView.as_view(), name="course-detail"),
    path(
        "courses/<int:pk>/sections/",
        views.CourseSectionsView.as_view(),
        name="course-sections",
    ),
    path(
        "courses/<int:pk>/enrollments/",
        views.CourseEnrollmentsView.as_view(),
        name="course-enrollments",
    ),
]
