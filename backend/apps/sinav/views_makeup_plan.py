"""Mazeret sınav takvimi uçları (20.09.2026) — ince katman; mantık `services_makeup_plan`'da.

    GET    /makeup-plans/?semester=<id>        dönemin takvimleri (özet)
    POST   /makeup-plans/                       bekleyen "Mazeretli" kayıtlarla takvim kurar
    GET    /makeup-plans/<id>/                  takvim ekranının verisi
    PATCH  /makeup-plans/<id>/                  parametreleri değiştirir + yeniden yerleştirir
    DELETE /makeup-plans/<id>/                  taslağı siler (kayıtlar serbest kalır)
    POST   /makeup-plans/<id>/replace/          yeniden yerleştir (sabitlere dokunmaz)
    POST   /makeup-plans/<id>/sync/             sonradan "Mazeretli" olan kayıtları ekler
    POST   /makeup-plans/<id>/approve/ · reopen/ · sessions/
    GET    /makeup-plans/<id>/pdf/?kind=ilan|liste&names=0|1
    PATCH  /makeup-plan-items/<id>/             elle taşı / takvim dışına al / sabitle
    DELETE /makeup-plan-items/<id>/             sınavı takvimden çıkar

Belge türü `kind` ile seçilir: `?format=` DRF'nin içerik müzakeresine ayrılmıştır.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from rest_framework import serializers as drf_serializers
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.sinav import services_makeup, services_makeup_plan
from apps.sinav.models import MakeupPlan, MakeupPlanItem
from apps.sinav.serializers import MakeupPlanItemMoveSerializer, MakeupPlanParamsSerializer
from apps.sinav.views_makeup import _semester_param


def _messages(exc: DjangoValidationError) -> drf_serializers.ValidationError:
    return drf_serializers.ValidationError(exc.messages)


class MakeupPlanViewSet(viewsets.GenericViewSet[MakeupPlan]):
    """Mazeret takvimi — yerleştirme, onay, oturum üretimi, belgeler."""

    queryset = MakeupPlan.objects.select_related("semester", "semester__school_year")

    def list(self, request: Request) -> Response:
        semesters = services_makeup.semester_options()
        semester_id = _semester_param(request, semesters)
        planlar = services_makeup_plan.plan_list(semester_id) if semester_id is not None else []
        return Response(
            {
                "semester_id": semester_id,
                "plans": planlar,
                # Yeni takvim formu için: zil çizelgesi + okulun sınav saatleri ve takvime
                # alınmayı bekleyen "Mazeretli" kayıt sayısı.
                **services_makeup_plan.form_options(semester_id),
            }
        )

    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        return Response(services_makeup_plan.plan_payload(self.get_object()))

    def create(self, request: Request) -> Response:
        serializer = MakeupPlanParamsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd: dict[str, Any] = dict(serializer.validated_data)
        eksik = [alan for alan in ("semester_id", "start_date", "day_count") if alan not in vd]
        if eksik:
            raise drf_serializers.ValidationError({alan: "Bu alan zorunlu." for alan in eksik})
        try:
            plan = services_makeup_plan.create_plan(
                semester_id=int(vd["semester_id"]),
                start_date=vd["start_date"],
                day_count=vd["day_count"],
                max_per_day=vd.get("max_per_day", 2),
                period_nos=vd.get("period_nos"),
                strict_order=vd.get("strict_order", True),
                name=vd.get("name", ""),
            )
        except DjangoValidationError as exc:
            raise _messages(exc) from exc
        return Response(services_makeup_plan.plan_payload(plan), status=201)

    def partial_update(self, request: Request, pk: str | None = None) -> Response:
        plan = self.get_object()
        serializer = MakeupPlanParamsSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields: dict[str, Any] = dict(serializer.validated_data)
        fields.pop("semester_id", None)  # dönem değişmez (OKY md. 48/1: süre dönemi aşamaz)
        try:
            plan = services_makeup_plan.replan(plan, **fields)
        except DjangoValidationError as exc:
            raise _messages(exc) from exc
        return Response(services_makeup_plan.plan_payload(plan))

    def destroy(self, request: Request, pk: str | None = None) -> Response:
        try:
            services_makeup_plan.remove_plan(self.get_object())
        except DjangoValidationError as exc:
            raise _messages(exc) from exc
        return Response(status=204)

    def _run(self, islem: Any) -> Response:
        plan = self.get_object()
        try:
            ek = islem(plan)
        except DjangoValidationError as exc:
            raise _messages(exc) from exc
        plan.refresh_from_db()
        return Response({**services_makeup_plan.plan_payload(plan), "result": ek})

    @action(detail=True, methods=["post"])
    def replace(self, request: Request, pk: str | None = None) -> Response:
        return self._run(services_makeup_plan.auto_place)

    @action(detail=True, methods=["post"])
    def sync(self, request: Request, pk: str | None = None) -> Response:
        return self._run(lambda plan: {"added": services_makeup_plan.sync_records(plan)})

    @action(detail=True, methods=["post"])
    def approve(self, request: Request, pk: str | None = None) -> Response:
        ad = str(request.data.get("approved_by_name") or "")
        return self._run(
            lambda plan: services_makeup_plan.approve_plan(plan, approved_by_name=ad) and None
        )

    @action(detail=True, methods=["post"])
    def reopen(self, request: Request, pk: str | None = None) -> Response:
        return self._run(lambda plan: services_makeup_plan.reopen_plan(plan) and None)

    @action(detail=True, methods=["post"])
    def sessions(self, request: Request, pk: str | None = None) -> Response:
        return self._run(services_makeup_plan.create_sessions)

    @action(detail=True, methods=["get"])
    def pdf(self, request: Request, pk: str | None = None) -> HttpResponse:
        plan = self.get_object()
        kind = request.query_params.get("kind", "ilan")
        names = request.query_params.get("names", "1") != "0"
        try:
            dosya = services_makeup_plan.render_plan_pdf(plan, kind=kind, show_names=names)
        except DjangoValidationError as exc:
            raise _messages(exc) from exc
        response = HttpResponse(dosya.content, content_type=dosya.content_type)
        response["Content-Disposition"] = f'attachment; filename="{dosya.filename}"'
        return response


class MakeupPlanItemViewSet(viewsets.GenericViewSet[MakeupPlanItem]):
    """Takvimin tek sınavı — elle taşıma, sabitleme, takvimden çıkarma."""

    queryset = MakeupPlanItem.objects.select_related("plan", "plan__semester", "course")

    def partial_update(self, request: Request, pk: str | None = None) -> Response:
        item = self.get_object()
        serializer = MakeupPlanItemMoveSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        vd: dict[str, Any] = dict(serializer.validated_data)
        uyarilar: list[str] = []
        try:
            if "placed_date" in vd or "period_no" in vd:
                gun, saat = vd.get("placed_date"), vd.get("period_no")
                if gun is None or saat is None:
                    services_makeup_plan.unplace_item(item)
                else:
                    uyarilar = services_makeup_plan.move_item(
                        item, placed_date=gun, period_no=int(saat), pin=vd.get("is_pinned", True)
                    )
            elif "is_pinned" in vd:
                services_makeup_plan.set_item_pinned(item, is_pinned=bool(vd["is_pinned"]))
        except DjangoValidationError as exc:
            raise _messages(exc) from exc
        return Response(
            {**services_makeup_plan.plan_payload(item.plan), "result": {"warnings": uyarilar}}
        )

    def destroy(self, request: Request, pk: str | None = None) -> Response:
        item = self.get_object()
        plan = item.plan
        try:
            services_makeup_plan.remove_item(item)
        except DjangoValidationError as exc:
            raise _messages(exc) from exc
        return Response(services_makeup_plan.plan_payload(plan))
