"""BEP kapsamındaki öğrenciler + bireysel soru dosyası uçları (20.09.2026).

İnce katman; mantık `services_individual`'da.

    GET    /iep-students/                       liste (sınıf/şube + okul no sıralı)
    POST   /iep-students/                       {student_id} — listeye ekle
    DELETE /iep-students/<id>/                  listeden çıkar
    POST   /iep-students/delete-all/            KVKK düğmesi — tüm kayıtlar + dosyalar

    GET    /individual-questions/?session=<id>  oturum paneli satırları
    POST   /individual-questions/               {session_id, student_id} — seçim
    DELETE /individual-questions/<id>/          seçimi kaldır (satır + dosya)
    POST   /individual-questions/<id>/file/     bireysel soru PDF'i yükle/değiştir
    GET    /individual-questions/<id>/file/     indir/önizle
    GET    /individual-questions/summary/?session=<id>   idare özeti (PDF)

KVKK md. 6: yollardaki `<id>` SATIR kimliğidir (opak); öğrenci pk'si yalnız İSTEK
GÖVDESİNDE gelir. Django 4xx yanıtını yoluyla günlüğe yazar — öğrenci kimliği
yolda olsaydı "şu öğrencinin bireysel soru dosyası var" bilgisi `uygulama.log`a
sızardı.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import FileResponse, HttpResponse
from rest_framework import serializers as drf_serializers
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.sinav import selectors, services_individual
from apps.sinav.models import (
    ExamSession,
    IepStudent,
    IndividualQuestionDocument,
    ScoreMode,
)
from apps.sinav.serializers import (
    IepStudentAddSerializer,
    IndividualSelectSerializer,
    QuestionUploadSerializer,
)
from apps.sinav.views import _missing_media_response, _stored_file_exists


def _not_found(message: str) -> Response:
    return Response({"code": "not_found", "message": message, "fields": {}}, status=404)


def _session_param(request: Request) -> ExamSession | None:
    raw = request.query_params.get("session", "")
    return selectors.get_exam_session(int(raw)) if raw.isdigit() else None


def _document(pk: str | None) -> IndividualQuestionDocument | None:
    """Yoldaki SATIR kimliğinden kayıt; sayı değilse/yoksa None."""
    return services_individual.get_individual(int(pk)) if pk is not None and pk.isdigit() else None


class IepStudentViewSet(viewsets.ViewSet):
    """BEP kapsamındaki öğrenciler — yalnız üyelik; tanı/açıklama alanı YOKTUR."""

    def list(self, request: Request) -> Response:
        return Response({"results": services_individual.iep_list()})

    def create(self, request: Request) -> Response:
        serializer = IepStudentAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            row = services_individual.add_iep_student(serializer.validated_data["student_id"])
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response({"id": row.pk}, status=201)

    def destroy(self, request: Request, pk: str | None = None) -> Response:
        row = IepStudent.objects.filter(pk=pk).first() if str(pk).isdigit() else None
        if row is None:
            return _not_found("Kayıt bulunamadı.")
        services_individual.remove_iep_student(row)
        return Response(status=204)

    @action(detail=False, methods=["post"], url_path="delete-all")
    def delete_all(self, request: Request) -> Response:
        """Geri alınamaz; arayüz onay ister ("Tüm fotoğrafları sil" emsali)."""
        return Response(services_individual.delete_all())


class IndividualQuestionViewSet(viewsets.ViewSet):
    """Bireysel soru dosyaları — oturum bazında seçim + yükleme."""

    def list(self, request: Request) -> Response:
        session = _session_param(request)
        if session is None:
            return _not_found("Oturum bulunamadı.")
        return Response({"rows": services_individual.session_rows(session)})

    def create(self, request: Request) -> Response:
        serializer = IndividualSelectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        session = selectors.get_exam_session(vd["session_id"])
        if session is None:
            return _not_found("Oturum bulunamadı.")
        try:
            row = services_individual.select_individual(session, student_id=vd["student_id"])
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(services_individual.document_payload(row), status=201)

    def destroy(self, request: Request, pk: str | None = None) -> Response:
        row = _document(pk)
        if row is None:
            return _not_found("Kayıt bulunamadı.")
        try:
            services_individual.remove_individual(row)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(status=204)

    # ÇOK METOTLU `@action` — GET indir/önizle · POST yükle/değiştir (soru dosyası kalıbı).
    @action(detail=True, methods=["get", "post"])
    def file(self, request: Request, pk: str | None = None) -> Response | FileResponse:
        row = _document(pk)
        if row is None:
            return _not_found("Kayıt bulunamadı.")
        if request.method == "GET":
            if not row.file:
                return _not_found("Bireysel soru dosyası yüklenmemiş.")
            if not _stored_file_exists(row.file):
                return _missing_media_response("Bireysel soru dosyası")
            # Dosya adı öğrenciyi ANMAZ (indirilenler klasöründe iz kalmasın).
            return FileResponse(
                row.file.open("rb"),
                as_attachment=True,
                filename="bireysel_soru_dosyasi.pdf",
                content_type="application/pdf",
            )
        serializer = QuestionUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        try:
            row = services_individual.upload_individual(
                row,
                file_bytes=vd["file"].read(),
                score_mode=vd.get("score_mode", ScoreMode.SINGLE_BOX),
                question_count=vd.get("question_count"),
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        return Response(services_individual.document_payload(row), status=201)

    @action(detail=False, methods=["get"])
    def summary(self, request: Request) -> HttpResponse | Response:
        """İdare özeti (PDF) — "Tümünü indir" paketine GİRMEZ; bilerek indirilir."""
        session = _session_param(request)
        if session is None:
            return _not_found("Oturum bulunamadı.")
        try:
            report_file = services_individual.render_iep_summary(session)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages) from exc
        response = HttpResponse(report_file.content, content_type=report_file.content_type)
        response["Content-Disposition"] = f'attachment; filename="{report_file.filename}"'
        return response
