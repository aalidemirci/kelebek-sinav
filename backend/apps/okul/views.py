"""`okul` API uçları — İNCE view'lar (View → Service → Model; ORM selectors'ta).

Authsuz tek kullanıcılı program: izin sınıfı yok (settings AllowAny). Hata
gövdesi `shared.exceptions.ks_exception_handler` ile `{code, message, fields}`
sözleşmesine çevrilir; parser hataları ValidationError olarak yükseltilir.

DD kalıbından KS'ye budama: tatil/sınıf-sorumlusu/yıl-devri/güncelleme uçları
alınmadı (tasarım §11 ALMA; güncelleme F8'de gelir). Şube kataloğu (ClassSection)
ve okul türüne bağlı seviye listesi bu projeye özgüdür (U4).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from io import BytesIO
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import FileResponse
from rest_framework import generics, serializers
from rest_framework.generics import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.okul import selectors
from apps.okul.excel_ogrenci import ParserError
from apps.okul.models import (
    ClassSection,
    ClassSectionGroup,
    Personnel,
    SchoolYear,
    Student,
    SubjectDepartment,
)
from apps.okul.serializers import (
    ClassSectionGroupSerializer,
    ClassSectionSerializer,
    ImportRequestSerializer,
    PersonnelSerializer,
    SchoolConfigSerializer,
    SchoolTermConfigurationSerializer,
    SchoolTermSerializer,
    SchoolYearSerializer,
    SectionGroupAssignSerializer,
    StudentSerializer,
    SubjectDepartmentSerializer,
)
from apps.okul.services import app_password as app_password_service
from apps.okul.services import departments as department_service
from apps.okul.services import encrypted_backup as encrypted_backup_service
from apps.okul.services import imports as import_service
from apps.okul.services import live_restore as live_restore_service
from apps.okul.services import persons as persons_service
from apps.okul.services import school_year as school_year_service
from apps.okul.services import sections as section_service
from apps.okul.services import setup as setup_service
from apps.okul.services import templates as template_service
from apps.okul.services import terms as term_service
from apps.okul.services import updates as update_service

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Boolean query parametresi için kabul edilen "açık" değerler.
TRUE_VALUES = frozenset({"true", "1"})


@contextmanager
def _service_errors() -> Iterator[None]:
    """Servis `ValueError`'larını sözleşmeli 400'e çevirir (Türkçe mesaj korunur)."""
    try:
        yield
    except ValueError as exc:
        raise serializers.ValidationError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Kurulum sihirbazı
# ---------------------------------------------------------------------------
class SetupStatusView(APIView):
    """Kurulum durumu — masaüstü sağlık denetimi + arayüz kurulum kapısı."""

    def get(self, request: Request) -> Response:
        return Response(selectors.setup_status())


class GradeLevelsView(APIView):
    """`GET /api/v1/grade-levels/` — UI seçicileri için geçerli öğrenim seviyeleri.

    Liste okul türünden türetilir (`SchoolConfig.grade_levels`, U4): v1'de
    Anadolu Lisesi 9-12 (+ hazırlık bayrağıyla 0). Sabit kod aralığı YOKTUR —
    yeni okul türü `SCHOOL_TYPE_LEVELS`'a satır ekleyerek gelir.
    """

    def get(self, request: Request) -> Response:
        config = setup_service.get_school_config()
        return Response(
            {
                "levels": selectors.grade_levels(),
                "prep_enabled": config.has_prep_class,
            }
        )


class SchoolTypesView(APIView):
    """`GET /api/v1/setup/school-types/` — okul türleri + bu sürümde çizelge verisi var mı.

    Seçici her türü listeler; `available=False` olan tür de seçilebilir ama
    arayüz havuzun boş başlayacağını söyler (TB2 — veri sonraki sürümde).
    """

    def get(self, request: Request) -> Response:
        from apps.dersler import services as ders_services

        return Response(ders_services.school_type_options())


class SchoolConfigView(APIView):
    def get(self, request: Request) -> Response:
        return Response(SchoolConfigSerializer(setup_service.get_school_config()).data)

    def put(self, request: Request) -> Response:
        serializer = SchoolConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = setup_service.update_school_config(fields=dict(serializer.validated_data))
        return Response(SchoolConfigSerializer(config).data)


class SetupCompleteView(APIView):
    def post(self, request: Request) -> Response:
        config = setup_service.mark_setup_completed()
        return Response({"setup_completed": config.setup_completed})


# ---------------------------------------------------------------------------
# Ders yılları
# ---------------------------------------------------------------------------
class SchoolYearListCreateView(generics.ListCreateAPIView[SchoolYear]):
    serializer_class = SchoolYearSerializer

    def get_queryset(self) -> Any:
        return selectors.school_years()

    def perform_create(self, serializer: serializers.BaseSerializer[SchoolYear]) -> None:
        serializer.instance = school_year_service.create_school_year(
            **dict(serializer.validated_data)
        )


class SchoolTermView(APIView):
    def get(self, request: Request, pk: int) -> Response:
        year = get_object_or_404(selectors.school_years(), pk=pk)
        return Response(SchoolTermSerializer(year.terms.all(), many=True).data)

    def put(self, request: Request, pk: int) -> Response:
        year = get_object_or_404(selectors.school_years(), pk=pk)
        serializer = SchoolTermConfigurationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with _service_errors():
            terms = term_service.configure_terms(
                year,
                first_end=serializer.validated_data["first_term_end"],
                second_start=serializer.validated_data["second_term_start"],
            )
        return Response(SchoolTermSerializer(terms, many=True).data)


class SchoolYearActivateView(APIView):
    def post(self, request: Request, pk: int) -> Response:
        year = get_object_or_404(selectors.school_years(), pk=pk)
        school_year_service.activate_school_year(year)
        return Response(SchoolYearSerializer(year).data)


# ---------------------------------------------------------------------------
# Öğrenciler / Personel / Şubeler
# ---------------------------------------------------------------------------
class StudentListCreateView(generics.ListCreateAPIView[Student]):
    serializer_class = StudentSerializer

    def get_queryset(self) -> Any:
        params = self.request.query_params
        raw_level = params.get("class_level", "").strip()
        class_level: int | None = None
        if raw_level:
            # isdigit() Unicode basamaklarda ('²') True dönüp int()'te patlar;
            # sayısal olmayan değer de sessizce yutulmamalı — sözleşmeli 400.
            try:
                class_level = int(raw_level)
            except ValueError as exc:
                raise serializers.ValidationError(
                    {"class_level": "Sınıf filtresi sayısal olmalıdır."}
                ) from exc
        return selectors.student_list(
            class_level=class_level,
            class_section=params.get("class_section", ""),
            search=params.get("search", ""),
            # Süzgeç OPT-IN: sicil ekranı ayrılmış öğrenciyi de görmeli; yalnız
            # seçiciler (autocomplete) `only_active=true` gönderir.
            only_active=params.get("only_active", "").strip().lower() in TRUE_VALUES,
        )

    def perform_create(self, serializer: serializers.BaseSerializer[Student]) -> None:
        serializer.instance = persons_service.create_student(**dict(serializer.validated_data))


class StudentDetailView(generics.RetrieveUpdateDestroyAPIView[Student]):
    serializer_class = StudentSerializer

    def get_queryset(self) -> Any:
        return selectors.students_all()

    def perform_update(self, serializer: serializers.BaseSerializer[Student]) -> None:
        assert serializer.instance is not None
        serializer.instance = persons_service.update_student(
            serializer.instance, **dict(serializer.validated_data)
        )

    def perform_destroy(self, instance: Student) -> None:
        persons_service.delete_student(instance)


class PersonnelListCreateView(generics.ListCreateAPIView[Personnel]):
    serializer_class = PersonnelSerializer

    def get_queryset(self) -> Any:
        params = self.request.query_params
        return selectors.personnel_list(
            search=params.get("search", ""),
            only_active=params.get("only_active", "").strip().lower() in TRUE_VALUES,
        )

    def perform_create(self, serializer: serializers.BaseSerializer[Personnel]) -> None:
        serializer.instance = persons_service.create_personnel(**dict(serializer.validated_data))


class PersonnelDetailView(generics.RetrieveUpdateDestroyAPIView[Personnel]):
    serializer_class = PersonnelSerializer

    def get_queryset(self) -> Any:
        return selectors.personnel_list()

    def perform_update(self, serializer: serializers.BaseSerializer[Personnel]) -> None:
        assert serializer.instance is not None
        serializer.instance = persons_service.update_personnel(
            serializer.instance, **dict(serializer.validated_data)
        )

    def perform_destroy(self, instance: Personnel) -> None:
        persons_service.delete_personnel(instance)


class ClassSectionListCreateView(generics.ListCreateAPIView[ClassSection]):
    serializer_class = ClassSectionSerializer

    def get_queryset(self) -> Any:
        raw_year = self.request.query_params.get("school_year", "").strip()
        school_year_id: int | None = None
        if raw_year:
            try:
                school_year_id = int(raw_year)
            except ValueError as exc:
                raise serializers.ValidationError(
                    {"school_year": "Ders yılı kimliği sayısal olmalıdır."}
                ) from exc
        return selectors.class_sections_sorted(school_year_id=school_year_id)

    def perform_create(self, serializer: serializers.BaseSerializer[ClassSection]) -> None:
        serializer.instance = section_service.create_class_section(
            **dict(serializer.validated_data)
        )


class ClassSectionDetailView(generics.DestroyAPIView[ClassSection]):
    serializer_class = ClassSectionSerializer

    def get_queryset(self) -> Any:
        return ClassSection.objects.select_related("school_year")

    def perform_destroy(self, instance: ClassSection) -> None:
        section_service.delete_class_section(instance)


class ClassSectionGroupListCreateView(generics.ListCreateAPIView[ClassSectionGroup]):
    """Şube kümesi kataloğu — sınav sihirbazında toplu şube seçiminin kaynağı."""

    serializer_class = ClassSectionGroupSerializer

    def get_queryset(self) -> Any:
        return selectors.class_section_groups_sorted()

    def perform_create(self, serializer: serializers.BaseSerializer[ClassSectionGroup]) -> None:
        serializer.instance = section_service.create_section_group(
            **dict(serializer.validated_data)
        )


class ClassSectionGroupDetailView(generics.RetrieveUpdateDestroyAPIView[ClassSectionGroup]):
    serializer_class = ClassSectionGroupSerializer

    def get_queryset(self) -> Any:
        return selectors.class_section_groups()

    def perform_update(self, serializer: serializers.BaseSerializer[ClassSectionGroup]) -> None:
        assert serializer.instance is not None
        serializer.instance = section_service.update_section_group(
            serializer.instance, **dict(serializer.validated_data)
        )

    def perform_destroy(self, instance: ClassSectionGroup) -> None:
        section_service.delete_section_group(instance)


class ClassSectionGroupAssignView(APIView):
    """`POST /class-section-groups/assign/` — şubeleri topluca kümeye alır."""

    def post(self, request: Request) -> Response:
        serializer = SectionGroupAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = serializer.validated_data["group"]
        try:
            updated = section_service.assign_section_group(
                section_ids=list(serializer.validated_data["section_ids"]),
                group_id=group.pk if group is not None else None,
            )
        except DjangoValidationError as exc:
            # DRF varsayılan handler'ı Django ValidationError'ı 400'e ÇEVİRMEZ
            # (yanıt 500 olurdu) — dönüşüm burada elle yapılır.
            raise serializers.ValidationError(exc.messages) from exc
        return Response({"updated": updated})


class SubjectDepartmentListCreateView(generics.ListCreateAPIView[SubjectDepartment]):
    """Zümre kataloğu — sınav takvimi imza bloğunun kaynağı (F6/B7 revizyonu)."""

    serializer_class = SubjectDepartmentSerializer

    def get_queryset(self) -> Any:
        board_only = self.request.query_params.get("board_only", "").strip().lower() in TRUE_VALUES
        return selectors.subject_departments_sorted(board_only=board_only)

    def perform_create(self, serializer: serializers.BaseSerializer[SubjectDepartment]) -> None:
        serializer.instance = department_service.create_subject_department(
            **dict(serializer.validated_data)
        )


class SubjectDepartmentDetailView(generics.RetrieveUpdateDestroyAPIView[SubjectDepartment]):
    serializer_class = SubjectDepartmentSerializer

    def get_queryset(self) -> Any:
        return selectors.subject_departments()

    def perform_update(self, serializer: serializers.BaseSerializer[SubjectDepartment]) -> None:
        assert serializer.instance is not None
        serializer.instance = department_service.update_subject_department(
            serializer.instance, **dict(serializer.validated_data)
        )

    def perform_destroy(self, instance: SubjectDepartment) -> None:
        department_service.delete_subject_department(instance)


# ---------------------------------------------------------------------------
# İçe aktarma (dosya VEYA pano metni — aynı boru hattı)
# ---------------------------------------------------------------------------
class _BaseImportView(APIView):
    """Ortak istek çözümü; alt sınıf servis fonksiyonlarını belirler."""

    file_handler: str = ""  # import_service fonksiyon adı (dosya yolu)
    text_handler: str = ""  # import_service fonksiyon adı (metin yolu)

    def post(self, request: Request) -> Response:
        serializer = ImportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded = serializer.validated_data.get("file")
        try:
            if uploaded is not None:
                handler = getattr(import_service, self.file_handler)
                report = handler(file_bytes=uploaded.read(), file_name=uploaded.name or "")
            else:
                handler = getattr(import_service, self.text_handler)
                report = handler(text=serializer.validated_data["text"])
        except ParserError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return Response(report.to_dict())


class StudentImportPreviewView(_BaseImportView):
    file_handler = "preview_students_file"
    text_handler = "preview_students_text"


class StudentImportCommitView(_BaseImportView):
    file_handler = "commit_students_file"
    text_handler = "commit_students_text"


class PersonnelImportPreviewView(_BaseImportView):
    file_handler = "preview_personnel_file"
    text_handler = "preview_personnel_text"


class PersonnelImportCommitView(_BaseImportView):
    file_handler = "commit_personnel_file"
    text_handler = "commit_personnel_text"


# ---------------------------------------------------------------------------
# Şablon indirme
# ---------------------------------------------------------------------------
class StudentTemplateView(APIView):
    def get(self, request: Request) -> FileResponse:
        return FileResponse(
            BytesIO(template_service.student_template_xlsx()),
            as_attachment=True,
            filename="sablon-ogrenci.xlsx",
            content_type=XLSX_CONTENT_TYPE,
        )


class PersonnelTemplateView(APIView):
    def get(self, request: Request) -> FileResponse:
        return FileResponse(
            BytesIO(template_service.personnel_template_xlsx()),
            as_attachment=True,
            filename="sablon-personel.xlsx",
            content_type=XLSX_CONTENT_TYPE,
        )


# ---------------------------------------------------------------------------
# Uygulama parolası / kilit (tasarım §5, DD F5-D5 kalıbı)
# ---------------------------------------------------------------------------
# Bu uçlar `apps.okul.lock_middleware.AppLockMiddleware` tarafından KİLİT
# KAPISINDAN MUAFTIR (`/api/v1/security/` ön eki) — kilidi açmanın tek yolu
# bunlardır. Parolalar YALNIZ istek gövdesinde taşınır; hiçbir yanıtta,
# günlükte veya hata mesajında yankılanmaz.
class AppPasswordRequestSerializer(serializers.Serializer[dict[str, Any]]):
    password = serializers.CharField(trim_whitespace=False)


class AppPasswordChangeSerializer(serializers.Serializer[dict[str, Any]]):
    current_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)


class AppPasswordRecoverSerializer(serializers.Serializer[dict[str, Any]]):
    recovery_key = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)


class SecurityStatusView(APIView):
    """`GET /api/v1/security/status/` — parola kurulu mu, kilitli mi, geçiş yarım mı."""

    def get(self, request: Request) -> Response:
        return Response(app_password_service.status())


class SecurityEnableView(APIView):
    """`POST /api/v1/security/enable/` — parolayı kurar, alanları şifreler.

    Yanıttaki `recovery_key` TEK SEFERLİKTİR: sunucu onu bir daha üretemez
    (yalnız sarmalı saklanır). Arayüz kullanıcıya yazdırtmadan diyaloğu kapatmaz.
    """

    def post(self, request: Request) -> Response:
        req = AppPasswordRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        with _service_errors():
            kurtarma = app_password_service.enable(password=req.validated_data["password"])
        return Response({"recovery_key": kurtarma, **app_password_service.status()}, status=201)


class SecurityUnlockView(APIView):
    """`POST /api/v1/security/unlock/` — parolayla kilidi açar (yarım geçişi tamamlar)."""

    def post(self, request: Request) -> Response:
        req = AppPasswordRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        with _service_errors():
            app_password_service.unlock(password=req.validated_data["password"])
        return Response(app_password_service.status())


class SecurityLockView(APIView):
    """`POST /api/v1/security/lock/` — anahtarı bellekten düşürür."""

    def post(self, request: Request) -> Response:
        app_password_service.lock()
        return Response(app_password_service.status())


class SecurityRecoverView(APIView):
    """`POST /api/v1/security/recover/` — kurtarma anahtarıyla açar + yeni parola."""

    def post(self, request: Request) -> Response:
        req = AppPasswordRecoverSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        with _service_errors():
            app_password_service.unlock_with_recovery(
                recovery_key=req.validated_data["recovery_key"],
                new_password=req.validated_data["new_password"],
            )
        return Response(app_password_service.status())


class SecurityChangePasswordView(APIView):
    """`POST /api/v1/security/change-password/` — veri yeniden şifrelenmez, sarmal yenilenir."""

    def post(self, request: Request) -> Response:
        req = AppPasswordChangeSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        with _service_errors():
            app_password_service.change_password(
                current_password=req.validated_data["current_password"],
                new_password=req.validated_data["new_password"],
            )
        return Response(app_password_service.status())


class SecurityDisableView(APIView):
    """`POST /api/v1/security/disable/` — parolayı kaldırır, alanları düz metne döndürür."""

    def post(self, request: Request) -> Response:
        req = AppPasswordRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        with _service_errors():
            app_password_service.disable(password=req.validated_data["password"])
        return Response(app_password_service.status())


# ---------------------------------------------------------------------------
# Kullanıcı isteğiyle oluşturulan şifreli veritabanı yedeği
# ---------------------------------------------------------------------------
class EncryptedBackupDownloadView(APIView):
    def post(self, request: Request) -> FileResponse:
        with _service_errors():
            content, filename = encrypted_backup_service.create_encrypted_backup()
        return FileResponse(
            BytesIO(content),
            as_attachment=True,
            filename=filename,
            content_type="application/octet-stream",
        )


# ---------------------------------------------------------------------------
# Yedekten geri yükleme (Güvenlik sekmesi — çalışan program içinden)
# ---------------------------------------------------------------------------
class BackupRestoreRequestSerializer(serializers.Serializer[dict[str, Any]]):
    """Kaynak İKİSİNDEN BİRİ: `name` (yedek klasöründen) YA DA `file` (yükleme).

    Parola/kurtarma anahtarı yalnız gövdede taşınır; yanıt ve günlüklerde
    yankılanmaz (security uçlarıyla aynı kural).
    """

    name = serializers.CharField(required=False, allow_blank=True, default="")
    file = serializers.FileField(required=False, allow_null=True, default=None)
    password = serializers.CharField(
        required=False, allow_blank=True, default="", trim_whitespace=False
    )
    recovery_key = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        ad = str(attrs.get("name") or "").strip()
        dosya = attrs.get("file")
        if bool(ad) == bool(dosya):
            raise serializers.ValidationError(
                "Yedek klasöründen bir dosya seçin YA DA bir .ksbak dosyası yükleyin."
            )
        attrs["name"] = ad
        return attrs


class BackupListView(APIView):
    """`GET /api/v1/backups/` — yedek klasöründeki geri yüklenebilir dosyalar."""

    def get(self, request: Request) -> Response:
        return Response(live_restore_service.list_backups())


class BackupRestoreView(APIView):
    """`POST /api/v1/backups/restore/` — yedeği veritabanının yerine koyar.

    Başarıda süreç "yeniden başlat" kapısına girer (`restart_gate`): sonraki
    tüm API istekleri 503 `restart_required` döner, kullanıcı programı kapatıp
    yeniden açar. Hata hâlinde hedefe dokunulmaz ve kapı kurulmaz.
    """

    def post(self, request: Request) -> Response:
        req = BackupRestoreRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        yuklenen = req.validated_data["file"]
        with _service_errors():
            payload = live_restore_service.restore_and_require_restart(
                name=req.validated_data["name"],
                content=yuklenen.read() if yuklenen is not None else None,
                password=req.validated_data["password"],
                recovery_key=req.validated_data["recovery_key"],
            )
        return Response(payload)


# ---------------------------------------------------------------------------
# GitHub Release tabanlı uygulama güncellemesi (F8 — DD updates.py AYNEN)
# ---------------------------------------------------------------------------
class UpdateStatusView(APIView):
    """GitHub'daki son kararlı sürümü çalışan sürümle karşılaştırır."""

    def get(self, request: Request) -> Response:
        force = str(request.query_params.get("force", "")).lower() in TRUE_VALUES
        try:
            return Response(update_service.update_status(force=force))
        except update_service.UpdateError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class UpdateInstallerView(APIView):
    """Doğrulanmış Windows kurucusunu uygulama indirmesi olarak döndürür."""

    def get(self, request: Request) -> FileResponse:
        try:
            installer = update_service.download_latest_installer(force=True)
        except update_service.UpdateError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        # Savunma derinliği: dönen dosya güncelleme önbelleği içinde mi?
        update_dir = update_service.update_directory().resolve()
        if update_dir not in installer.resolve().parents:
            raise serializers.ValidationError("Güncelleme dosyası güvenli önbellek dışında.")
        return FileResponse(
            installer.open("rb"),
            as_attachment=True,
            filename=installer.name,
            content_type="application/vnd.microsoft.portable-executable",
        )
