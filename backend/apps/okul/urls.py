"""`okul` URL'leri — kebab-case, çoğul kaynak adları (OYS API sözleşmesi).

`setup/status/` hem arayüz kurulum kapısının hem masaüstü sağlık denetiminin
(`desktop/server.py::HEALTH_PATH`) tek kaynağıdır — yolu değişirse üçü birlikte
güncellenir. `security/` ön eki kilit kapısından muaftır
(`lock_middleware.ALLOWED_PREFIXES` ile birebir aynı kalmalıdır).
"""

from __future__ import annotations

from django.urls import path

from apps.okul import views

urlpatterns = [
    # Kurulum sihirbazı
    path("setup/status/", views.SetupStatusView.as_view(), name="setup-status"),
    path("setup/school-config/", views.SchoolConfigView.as_view(), name="setup-school-config"),
    path("setup/complete/", views.SetupCompleteView.as_view(), name="setup-complete"),
    # Öğrenim seviyeleri (okul türünden türetilir — U4)
    path("grade-levels/", views.GradeLevelsView.as_view(), name="grade-levels"),
    # Ders yılları + dönemler
    path("school-years/", views.SchoolYearListCreateView.as_view(), name="school-year-list"),
    path(
        "school-years/<int:pk>/terms/",
        views.SchoolTermView.as_view(),
        name="school-year-terms",
    ),
    path(
        "school-years/<int:pk>/activate/",
        views.SchoolYearActivateView.as_view(),
        name="school-year-activate",
    ),
    # Öğrenciler / Personel / Şubeler
    path("students/", views.StudentListCreateView.as_view(), name="student-list"),
    path("students/<int:pk>/", views.StudentDetailView.as_view(), name="student-detail"),
    path("personnel/", views.PersonnelListCreateView.as_view(), name="personnel-list"),
    path("personnel/<int:pk>/", views.PersonnelDetailView.as_view(), name="personnel-detail"),
    path("class-sections/", views.ClassSectionListCreateView.as_view(), name="class-section-list"),
    path(
        "class-sections/<int:pk>/",
        views.ClassSectionDetailView.as_view(),
        name="class-section-detail",
    ),
    # Şube kümeleri (SAY/EA/DİL — sihirbazda toplu şube seçimi)
    path(
        "class-section-groups/",
        views.ClassSectionGroupListCreateView.as_view(),
        name="class-section-group-list",
    ),
    path(
        "class-section-groups/assign/",
        views.ClassSectionGroupAssignView.as_view(),
        name="class-section-group-assign",
    ),
    path(
        "class-section-groups/<int:pk>/",
        views.ClassSectionGroupDetailView.as_view(),
        name="class-section-group-detail",
    ),
    # Zümreler (okul zümre başkanları kurulu — takvim imza bloğunun kaynağı)
    path(
        "subject-departments/",
        views.SubjectDepartmentListCreateView.as_view(),
        name="subject-department-list",
    ),
    path(
        "subject-departments/<int:pk>/",
        views.SubjectDepartmentDetailView.as_view(),
        name="subject-department-detail",
    ),
    # İçe aktarma (dosya veya pano metni)
    path(
        "imports/students/preview/",
        views.StudentImportPreviewView.as_view(),
        name="import-students-preview",
    ),
    path(
        "imports/students/commit/",
        views.StudentImportCommitView.as_view(),
        name="import-students-commit",
    ),
    path(
        "imports/personnel/preview/",
        views.PersonnelImportPreviewView.as_view(),
        name="import-personnel-preview",
    ),
    path(
        "imports/personnel/commit/",
        views.PersonnelImportCommitView.as_view(),
        name="import-personnel-commit",
    ),
    # Şablon indirme
    path("templates/students/", views.StudentTemplateView.as_view(), name="template-students"),
    path("templates/personnel/", views.PersonnelTemplateView.as_view(), name="template-personnel"),
    # Uygulama parolası / kilit (tasarım §5)
    path("security/status/", views.SecurityStatusView.as_view(), name="security-status"),
    path("security/enable/", views.SecurityEnableView.as_view(), name="security-enable"),
    path("security/unlock/", views.SecurityUnlockView.as_view(), name="security-unlock"),
    path("security/lock/", views.SecurityLockView.as_view(), name="security-lock"),
    path("security/recover/", views.SecurityRecoverView.as_view(), name="security-recover"),
    path(
        "security/change-password/",
        views.SecurityChangePasswordView.as_view(),
        name="security-change-password",
    ),
    path("security/disable/", views.SecurityDisableView.as_view(), name="security-disable"),
    path(
        "backups/encrypted/",
        views.EncryptedBackupDownloadView.as_view(),
        name="encrypted-backup-download",
    ),
    # Yedekten geri yükleme (Güvenlik sekmesi — çalışan program içinden)
    path("backups/", views.BackupListView.as_view(), name="backup-list"),
    path("backups/restore/", views.BackupRestoreView.as_view(), name="backup-restore"),
    # GitHub Release tabanlı uygulama güncellemesi (F8)
    path("updates/latest/", views.UpdateStatusView.as_view(), name="update-latest"),
    path(
        "updates/latest/installer/",
        views.UpdateInstallerView.as_view(),
        name="update-installer",
    ),
]
