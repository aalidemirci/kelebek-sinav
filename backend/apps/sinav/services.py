"""sinav servisleri — salon (F2) + oturum (F3) + evrak (F4) + kitapçık (F5) + gözetmen (F7).

OYS `sinav_islemleri/services.py`'den UYARLA (tasarım §11): `created_by`/User
damgaları düşer (tek kullanıcı — ad-snapshot + zaman kalır), core köprüleri
yerel `apps.okul`/`apps.dersler` selector'larına bağlanır (fonksiyon imzaları
korunur — köprü uyarlaması risk #2). Gözetmen sıfırlama ve takvim çözme
blokları alınmadı (F7/F6'da gelir); GROUPS katılımcı tipi alınmadı (TB7).
"""

from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass
from types import EllipsisType
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.dersler import selectors as ders_selectors
from apps.dersler import services as ders_services
from apps.okul import selectors as okul_selectors
from apps.okul.models import ClassSection, Personnel, SchoolConfig
from apps.sinav import booklet, engine, layout, participants, reports, validator
from apps.sinav.models import (
    BookletRun,
    BookletRunStatus,
    ExamAttendanceRecord,
    ExamRoom,
    ExamSession,
    ExamSessionCourse,
    ExamSessionRoom,
    ExamSessionStatus,
    ExamSessionType,
    ExcuseStatus,
    ExemptionReason,
    LayoutMode,
    NumberingScheme,
    ParticipantType,
    PlacementRule,
    ProctorAssignment,
    ProctorExemption,
    ProctorRole,
    QuestionDocument,
    RuleReason,
    RuleScope,
    RuleType,
    ScoreMode,
    SeatAssignment,
    SeatStatus,
)


def _normalize_room_name(name: str) -> str:
    """Salon adındaki kenar/iç fazla boşlukları temizle."""
    cleaned = " ".join((name or "").split())
    if not cleaned:
        raise ValidationError("Salon adı boş olamaz.")
    return cleaned


def _resolve_linked_section(section_id: int | None) -> ClassSection | None:
    """Bağlı şubeyi okul köprüsünden çözer (model importu şube kataloğuna)."""
    if section_id is None:
        return None
    section = okul_selectors.get_class_section(section_id)
    if section is None:
        raise ValidationError("Bağlı şube bulunamadı.")
    return section


@transaction.atomic
def create_exam_room(
    *,
    name: str,
    layout_plan: dict[str, Any] | None = None,
    numbering_scheme: str | None = None,
    block: str = "",
    linked_section_id: int | None = None,
) -> ExamRoom:
    """Yeni salon oluşturur; plan verilmezse boş varsayılan plan kullanılır.

    Plan şeması burada (servis katmanında) doğrulanır — geçersiz plan Türkçe
    mesajlı ``ValidationError`` fırlatır, kayıt yazılmaz.
    """
    cleaned = _normalize_room_name(name)
    if ExamRoom.objects.filter(name=cleaned).exists():
        raise ValidationError(f"'{cleaned}' adlı salon zaten kayıtlı.")
    plan_raw: dict[str, Any] = (
        copy.deepcopy(layout.DEFAULT_LAYOUT_PLAN) if layout_plan is None else layout_plan
    )
    layout.validate_layout_plan(plan_raw)
    room: ExamRoom = ExamRoom.objects.create(
        name=cleaned,
        block=(block or "").strip(),
        linked_section=_resolve_linked_section(linked_section_id),
        layout_plan=plan_raw,
        numbering_scheme=numbering_scheme or ExamRoom._meta.get_field("numbering_scheme").default,
    )
    return room


def update_exam_room(
    room: ExamRoom,
    *,
    name: str | None = None,
    layout_plan: dict[str, Any] | None = None,
    numbering_scheme: str | None = None,
    block: str | None = None,
    linked_section_id: int | None | EllipsisType = ...,
    is_active: bool | None = None,
) -> ExamRoom:
    """Salon alanlarını günceller (kısmi). Plan değişiyorsa şema yeniden doğrulanır.

    `linked_section_id=...` sentineli "değiştirme"; None geçirilirse eşleme
    açıkça kaldırılır.
    """
    if name is not None:
        cleaned = _normalize_room_name(name)
        if ExamRoom.objects.exclude(pk=room.pk).filter(name=cleaned).exists():
            raise ValidationError(f"'{cleaned}' adlı salon zaten kayıtlı.")
        room.name = cleaned
    if layout_plan is not None:
        layout.validate_layout_plan(layout_plan)
        room.layout_plan = layout_plan
    if numbering_scheme is not None:
        room.numbering_scheme = numbering_scheme
    if block is not None:
        room.block = block.strip()
    if not isinstance(linked_section_id, EllipsisType):
        room.linked_section = _resolve_linked_section(linked_section_id)
    if is_active is not None:
        room.is_active = is_active
    room.save()
    return room


def room_seats(room: ExamRoom) -> list[layout.Seat]:
    """Salonun numaralandırılmış koltukları (plan + düzenden türetilir).

    Editör önizlemesi, kroki (R1) ve dağıtım motoru aynı listeden okur.
    """
    plan = layout.validate_layout_plan(room.layout_plan)
    return layout.numbered_seats(plan, room.numbering_scheme)


def room_capacity(room: ExamRoom) -> int:
    """Salon kapasitesi — plandaki aktif sıra koltuklarının toplamı."""
    return layout.validate_layout_plan(room.layout_plan).capacity


def preview_room_seats(
    layout_plan: object, numbering_scheme: str | None = None
) -> tuple[int, list[layout.Seat]]:
    """KAYDEDİLMEMİŞ planın kapasite + numara önizlemesi (salon editörü).

    Numaralandırma iş kuralı backend'de kalır (frontend'de business logic yok);
    editör her plan değişiminde bu fonksiyonun ucunu çağırır, hiçbir şey
    kaydedilmez. Geçersiz plan Türkçe ``ValidationError``.
    """
    plan = layout.validate_layout_plan(layout_plan)
    scheme = numbering_scheme or NumberingScheme.S_PATTERN
    return plan.capacity, layout.numbered_seats(plan, scheme)


def section_room_name(class_level: int, class_section: str, labels: dict[int, str]) -> str:
    """Şube derslik salon adı: 'Hazırlık/A Dersliği' veya '9/A Dersliği'."""
    label = labels.get(class_level, str(class_level))
    return f"{label}/{class_section.strip().upper()} Dersliği"


def _level_labels() -> dict[int, str]:
    """Seviye → görüntü etiketi sözlüğü (okul açık servis arayüzünden)."""
    return {int(o["value"]): str(o["label"]) for o in okul_selectors.grade_levels()}


@transaction.atomic
def generate_section_rooms() -> dict[str, Any]:
    """Aktif yılın her şubesi için `linked_section`'lı ExamRoom üretir (idempotent).

    Varsayılan plan `layout.default_section_plan` (kapı sol-ön, öğretmen masası
    sağ-ön, ikili sıralar 4 sütun). Öğrenci sayısı 40'ı aşarsa satır sayısı
    büyür (`max(5, ceil(n/8))`) — sabit 40 koltuk taşan şubede kapasite hatasını
    önler. Öğrencisiz şube DE salon alır (katalog tek doğruluk kaynağı).

    İdempotens iki katmanlı: (a) `linked_section`'a bağlı canlı salon varsa atla
    (yeniden adlandırılanı da yakalar); (b) ad çakışması → 'skipped'. `orphan_rooms`
    = soft-silinmiş şubeye bağlı canlı+aktif salonlar (kullanıcıya pasifleştirme
    önerisi). Dönüş: {created, skipped, orphan_rooms, sections_total}.
    """
    labels = _level_labels()
    created: list[str] = []
    skipped: list[str] = []
    sections = list(okul_selectors.class_sections())

    linked_section_ids = set(
        ExamRoom.objects.filter(linked_section__isnull=False).values_list(
            "linked_section_id", flat=True
        )
    )

    for section in sections:
        room_name = section_room_name(section.class_level, section.class_section, labels)
        if section.pk in linked_section_ids:
            # Bu şubeye bağlı salon zaten var (yeniden adlandırılmış olsa da) → atla+raporla.
            skipped.append(room_name)
            continue
        roster = list(
            okul_selectors.student_list(
                class_level=section.class_level,
                class_section=section.class_section,
                only_active=True,
            )
        )
        desk_rows = max(5, math.ceil(len(roster) / 8)) if roster else 5
        if ExamRoom.objects.filter(name=_normalize_room_name(room_name)).exists():
            skipped.append(room_name)
            continue
        create_exam_room(
            name=room_name,
            layout_plan=layout.default_section_plan(desk_rows=desk_rows),
            linked_section_id=section.pk,
        )
        created.append(room_name)

    # Ölü şubeye bağlı canlı+aktif salonlar (öneri listesi — otomatik pasifleme yok).
    orphan_rooms = list(
        ExamRoom.objects.filter(
            is_active=True,
            linked_section__isnull=False,
            linked_section__deleted_at__isnull=False,
        ).values_list("name", flat=True)
    )

    return {
        "created": created,
        "skipped": skipped,
        "orphan_rooms": orphan_rooms,
        "sections_total": len(sections),
    }


# ===========================================================================
# F3 — Oturum akışı (OYS T4-T6, T9, T11, Tur 245 kesiti)
# ===========================================================================


def session_course_label(course_name: str, level: int | None, *, shared_booklet: bool) -> str:
    """Oturum dersi görünüm etiketi: "Matematik — 9. Sınıf" (+ ortak kitapçık eki)."""
    base = course_name if level is None else f"{course_name} — {ders_services.level_label(level)}"
    return f"{base} (ortak kitapçık)" if shared_booklet else base


def conflict_group_labels(keys: set[str] | frozenset[str]) -> dict[str, str]:
    """Çakışma grubu anahtarlarını insan-okur etikete çözer (motor sözleşmesi §3).

    "12:9" → "Matematik — 9. Sınıf", "12:*" → "Matematik — Ortak kitapçık".
    R8 doğrulama raporu ve seating ucu aynı kaynaktan beslenir.
    """
    course_names = ders_selectors.course_names_by_ids({int(key.split(":")[0]) for key in keys})
    labels: dict[str, str] = {}
    for key in keys:
        cid_raw, level = key.split(":", 1)
        name = course_names.get(int(cid_raw), f"Ders {cid_raw}")
        labels[key] = (
            f"{name} — Ortak kitapçık"
            if level == "*"
            else f"{name} — {ders_services.level_label(int(level))}"
        )
    return labels


# ---------------------------------------------------------------------------
# Sınav oturumu — yalnız TASLAK düzenlenebilir
# ---------------------------------------------------------------------------
def _ensure_draft(session: ExamSession) -> None:
    if not session.is_draft:
        raise ValidationError(
            f"Oturum '{session.get_status_display()}' durumunda; yalnız taslak düzenlenebilir."
        )


def _resolve_term(term_id: int) -> Any:
    """Dönemi okul köprüsünden çözer (OYS core.get_semester karşılığı)."""
    term = okul_selectors.get_school_term(term_id)
    if term is None:
        raise ValidationError("Dönem bulunamadı.")
    return term


def _default_stamp_name() -> str:
    """Beyan/onay damgalarının varsayılan adı — kurulumdaki müdür adı (B12).

    Tek kullanıcılı uygulamada login yok; basılı evrakın resmî değeri damga
    adına dayanır. Ad verilmezse kurum yapılandırmasındaki müdür adı basılır.
    """
    return SchoolConfig.load().principal_name


@transaction.atomic
def create_exam_session(
    *,
    name: str,
    exam_date: Any,
    start_time: Any,
    duration_minutes: int = 40,
    term_id: int,
    session_type: str = ExamSessionType.SCHOOL,
    layout_mode: str = LayoutMode.BUTTERFLY,
    proctors_enabled: bool = False,
) -> ExamSession:
    """Yeni TASLAK oturum oluşturur (Adım 1)."""
    cleaned = " ".join((name or "").split())
    if not cleaned:
        raise ValidationError("Oturum adı boş olamaz.")
    session: ExamSession = ExamSession.objects.create(
        name=cleaned,
        exam_date=exam_date,
        start_time=start_time,
        duration_minutes=duration_minutes,
        semester=_resolve_term(term_id),
        session_type=session_type,
        layout_mode=layout_mode,
        proctors_enabled=proctors_enabled,
    )
    return session


def update_exam_session(session: ExamSession, **fields: Any) -> ExamSession:
    """Taslak oturumun üst bilgilerini günceller (kısmi).

    Durum/onay alanları buradan DEĞİŞTİRİLEMEZ (durum makinesi servisleri).
    """
    _ensure_draft(session)
    allowed = {
        "name",
        "exam_date",
        "start_time",
        "duration_minutes",
        "session_type",
        "layout_mode",
        "proctors_enabled",
    }
    unknown = set(fields) - allowed - {"term_id"}
    if unknown:
        raise ValidationError(f"Bu alanlar güncellenemez: {', '.join(sorted(unknown))}.")
    if "name" in fields:
        cleaned = " ".join((fields["name"] or "").split())
        if not cleaned:
            raise ValidationError("Oturum adı boş olamaz.")
        fields["name"] = cleaned
    if "term_id" in fields:
        session.semester = _resolve_term(fields.pop("term_id"))
    for key, value in fields.items():
        setattr(session, key, value)
    session.save()
    return session


def remove_exam_session(session: ExamSession) -> None:
    """Taslak oturumu kaldırır (soft-delete) — ders/salon satırlarıyla birlikte."""
    _ensure_draft(session)
    now = timezone.now()
    ExamSessionCourse.objects.filter(session=session).update(deleted_at=now)
    ExamSessionRoom.objects.filter(session=session).update(deleted_at=now)
    session.delete()


def confirm_transfer_check(session: ExamSession, *, confirmed_by_name: str = "") -> ExamSession:
    """Adım 0 beyanı: 'nakil gelen/giden güncellemeleri yapıldı' — kim/ne zaman.

    B10: veri sorgusu yok, kullanıcı beyanı esastır (Yönerge md. 5/1-v). Ad
    verilmezse kurulumdaki müdür adı damgalanır.
    """
    _ensure_draft(session)
    session.transfer_check_confirmed_by_name = (
        " ".join((confirmed_by_name or "").split()) or _default_stamp_name()
    )
    session.transfer_check_confirmed_at = timezone.now()
    session.save(
        update_fields=[
            "transfer_check_confirmed_by_name",
            "transfer_check_confirmed_at",
            "updated_at",
        ]
    )
    return session


def term_options() -> list[dict[str, Any]]:
    """Sihirbaz Adım 1 dönem seçici: aktif ders yılının dönemleri (okul köprüsü).

    PII içermez (id + etiket). Aktif yıl tanımlı değilse boş liste.
    """
    year = okul_selectors.active_school_year()
    if year is None:
        return []
    return [
        {"id": term.pk, "label": str(term)}
        for term in okul_selectors.school_terms(school_year_id=year.pk)
    ]


def pre_check_summary() -> dict[str, Any]:
    """Adım 0 verisi: seviye bazlı aktif öğrenci sayıları + son öğrenci aktarımı.

    OYS'deki e-Okul nakil hareket sorgusu KS'de YOK (B10 — çevrimdışı, beyan
    esaslı); onun yerine listenin tazeliği gösterilir. PII içermez.
    """
    last_import = okul_selectors.last_student_import()
    return {
        "active_students_by_level": okul_selectors.active_student_counts_by_level(),
        "last_student_import": (
            {
                "file_name": last_import.file_name,
                "finished_at": (
                    last_import.finished_at.isoformat() if last_import.finished_at else None
                ),
            }
            if last_import is not None
            else None
        ),
    }


# --- Oturum dersleri -------------------------------------------------------
def _validate_participant_refs(
    *,
    participant_type: str,
    level: int | None,
    section_ids: list[int],
) -> tuple[int, list[int]]:
    """Katılımcı referanslarını doğrular; satırın TEK seviyesini döndürür (Tur 241).

    LEVEL tipinde seviye açıkça verilir; SECTIONS tipinde seçilen şubelerin
    class_level'ından türetilir — karışık seviye reddedilir (bir oturum dersi
    tek seviyeye bağlıdır). GROUPS tipi alınmadı (TB7).
    """
    if participant_type == ParticipantType.LEVEL:
        if level is None:
            raise ValidationError("Seviye geneli atamada seviye seçin.")
        return ders_services.normalize_levels([level])[0], []
    if participant_type == ParticipantType.SECTIONS:
        if not section_ids:
            raise ValidationError("Şube bazlı atamada en az bir şube seçin.")
        seen_levels: set[int] = set()
        for sid in section_ids:
            section = okul_selectors.get_class_section(int(sid))
            if section is None:
                raise ValidationError(f"Şube bulunamadı (id={sid}).")
            seen_levels.add(int(section.class_level))
        if len(seen_levels) > 1:
            raise ValidationError(
                "Bir oturum dersi tek seviyeye bağlıdır; seçilen şubeler farklı "
                "seviyelerde. Her seviye için ayrı satır ekleyin."
            )
        return seen_levels.pop(), list(dict.fromkeys(section_ids))
    raise ValidationError(f"Geçersiz katılımcı tipi: {participant_type!r}.")


def _ensure_shared_booklet_sync(
    session: ExamSession, course: Any, shared_booklet: bool, *, exclude_pk: int | None = None
) -> None:
    """Aynı dersin oturumdaki tüm satırlarında shared_booklet senkron olmalı (K7)."""
    siblings = ExamSessionCourse.objects.filter(session=session, course=course)
    if exclude_pk is not None:
        siblings = siblings.exclude(pk=exclude_pk)
    if siblings.filter(shared_booklet=not shared_booklet).exists():
        raise ValidationError(
            f"'{course.name}' dersinin oturumdaki diğer satırlarıyla ortak kitapçık "
            "işareti uyuşmuyor — bayrak aynı dersin tüm satırlarında aynı olmalı."
        )


@transaction.atomic
def add_session_course(
    session: ExamSession,
    *,
    course_id: int,
    participant_type: str,
    level: int | None = None,
    section_ids: list[int] | None = None,
    duration_minutes: int | None = None,
    shared_booklet: bool = False,
) -> ExamSessionCourse:
    """Taslak oturuma TEK seviyeli ders + katılımcı tanımı ekler (Tur 241)."""
    _ensure_draft(session)
    course = ders_selectors.get_course(course_id, active_only=True)
    if course is None:
        raise ValidationError("Ders havuzunda bulunamadı (veya pasif).")
    lv, sec = _validate_participant_refs(
        participant_type=participant_type,
        level=level,
        section_ids=section_ids or [],
    )
    if lv not in course.levels:
        raise ValidationError(
            f"'{course.name}' dersi {ders_services.level_label(lv)} seviyesinde "
            "okutulmuyor (havuz tanımı)."
        )
    if ExamSessionCourse.objects.filter(session=session, course=course, level=lv).exists():
        raise ValidationError(
            f"'{session_course_label(course.name, lv, shared_booklet=False)}' "
            "bu oturuma zaten ekli."
        )
    _ensure_shared_booklet_sync(session, course, shared_booklet)
    row: ExamSessionCourse = ExamSessionCourse.objects.create(
        session=session,
        course=course,
        participant_type=participant_type,
        level=lv,
        section_ids=sec,
        duration_minutes=duration_minutes,
        shared_booklet=shared_booklet,
    )
    return row


@transaction.atomic
def update_session_course(sc: ExamSessionCourse, **fields: Any) -> ExamSessionCourse:
    """Oturum dersinin seviye/katılımcı tanımını günceller (taslakta)."""
    _ensure_draft(sc.session)
    participant_type = fields.get("participant_type", sc.participant_type)
    lv, sec = _validate_participant_refs(
        participant_type=participant_type,
        level=fields.get("level", sc.level),
        section_ids=fields.get("section_ids", sc.section_ids) or [],
    )
    if lv not in sc.course.levels:
        raise ValidationError(
            f"'{sc.course.name}' dersi {ders_services.level_label(lv)} seviyesinde "
            "okutulmuyor (havuz tanımı)."
        )
    duplicate = ExamSessionCourse.objects.filter(
        session=sc.session, course=sc.course, level=lv
    ).exclude(pk=sc.pk)
    if duplicate.exists():
        raise ValidationError(
            f"'{session_course_label(sc.course.name, lv, shared_booklet=False)}' "
            "bu oturuma zaten ekli."
        )
    shared = bool(fields.get("shared_booklet", sc.shared_booklet))
    _ensure_shared_booklet_sync(sc.session, sc.course, shared, exclude_pk=sc.pk)
    sc.participant_type = participant_type
    sc.level = lv
    sc.section_ids = sec
    if "duration_minutes" in fields:
        sc.duration_minutes = fields["duration_minutes"]
    sc.shared_booklet = shared
    sc.save()
    return sc


def remove_session_course(sc: ExamSessionCourse) -> None:
    """Dersi taslak oturumdan çıkarır (soft-delete — tarihsel iz)."""
    _ensure_draft(sc.session)
    sc.delete()


# --- Oturum salonları ------------------------------------------------------
@transaction.atomic
def set_session_rooms(
    session: ExamSession,
    room_entries: list[dict[str, Any]],
) -> list[ExamSessionRoom]:
    """Oturumun salon listesini verilen kümeye eşitler (replace semantiği).

    `room_entries`: [{"room_id": 3, "capacity_override": 24?}, ...] — sıra,
    liste sırasından gelir. Pasif/yinelenen salon reddedilir; çıkarılanlar
    soft-delete edilir.
    """
    _ensure_draft(session)
    seen: set[int] = set()
    resolved: list[tuple[ExamRoom, int | None]] = []
    for entry in room_entries:
        room_id = entry.get("room_id")
        if not isinstance(room_id, int):
            raise ValidationError("Her satırda sayısal room_id zorunludur.")
        if room_id in seen:
            raise ValidationError(f"Salon listede iki kez geçiyor (id={room_id}).")
        seen.add(room_id)
        room = ExamRoom.objects.filter(pk=room_id, is_active=True).first()
        if room is None:
            raise ValidationError(f"Salon bulunamadı veya pasif (id={room_id}).")
        resolved.append((room, entry.get("capacity_override")))

    ExamSessionRoom.objects.filter(session=session).exclude(
        room_id__in=[room.pk for room, _ in resolved]
    ).update(deleted_at=timezone.now())

    rows: list[ExamSessionRoom] = []
    for order, (room, cap) in enumerate(resolved):
        # Soft-silinmiş satırı diriltme deseni: all_objects + deleted_at=None anahtarı.
        row, _created = ExamSessionRoom.all_objects.update_or_create(
            session=session,
            room=room,
            deleted_at=None,
            defaults={"order": order, "capacity_override": cap},
        )
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Dağıtım — kelebek motoru + klasik düzen + bağımsız doğrulama
# ---------------------------------------------------------------------------
def _room_seats_for(room: ExamRoom, *, cap: int | None = None) -> engine.RoomSeats:
    """Salonun rota-sıralı koltukları (kapasite sınırı rota başından uygulanır)."""
    seats = room_seats(room)
    if cap is not None:
        seats = seats[:cap]
    return engine.RoomSeats(room_id=room.pk, seats=tuple(seats))


def _session_room_seats(session: ExamSession) -> list[engine.RoomSeats]:
    rows = (
        ExamSessionRoom.objects.filter(session=session)
        .select_related("room")
        .order_by("order", "id")
    )
    return [_room_seats_for(row.room, cap=row.capacity_override) for row in rows]


def _placed_from(placements: list[engine.Placement]) -> list[validator.PlacedStudent]:
    """Motor çıktısını bağımsız doğrulayıcı girdisine çevirir."""
    return [
        validator.PlacedStudent(
            student_id=pl.participant.student_id,
            conflict_group=pl.participant.conflict_group,
            room_id=pl.room_id,
            desk_row=pl.seat.desk_row,
            desk_col=pl.seat.desk_col,
            slot=pl.seat.slot,
            x=pl.seat.x,
            y=pl.seat.y,
            # K1: aynı-şube komşuluk metriği şube etiketiyle ölçülür.
            section_label=f"{pl.participant.class_level}/{pl.participant.class_section}",
        )
        for pl in placements
    ]


@transaction.atomic
def distribute_session(
    session: ExamSession,
    *,
    seed: int | None = None,
    strict: bool = False,
) -> tuple[ExamSession, engine.DistributionResult, validator.SeatingReport]:
    """Oturumu dağıtır: motoru çalıştırır, SeatAssignment snapshot'larını yazar.

    - Sert çakışma (öğrenci iki derste) varsa reddedilir.
    - Önceki canlı yerleşim soft-delete edilir ('Yeniden Dağıt' = yeni seed).
    - Durum TASLAK/DAĞITILDI iken çalışır; ONAYLANDI/ARŞİV kilitli.
    - Dönen rapor BAĞIMSIZ doğrulayıcıdan gelir (motor çıktısı sıfırdan denetlenir).
    """
    if session.status not in (ExamSessionStatus.DRAFT, ExamSessionStatus.DISTRIBUTED):
        raise ValidationError(
            f"Oturum '{session.get_status_display()}' durumunda; yeniden dağıtılamaz."
        )

    resolution = participants.resolve_session(session)
    if resolution.has_blocking_conflicts:
        raise ValidationError(
            f"Dağıtım engellendi: {len(resolution.duplicate_students)} öğrenci aynı "
            "oturumda birden çok derse düşüyor. Katılımcı önizlemesinden düzeltin."
        )
    pool = resolution.participants

    if seed is None:
        seed = random.randrange(1, 1_000_000)  # noqa: S311 — kripto değil; dağıtım seed'i

    pinned_ids: set[int] = set()
    if session.layout_mode == LayoutMode.HOME_CLASSROOM:
        section_map: dict[str, engine.RoomSeats] = {}
        mapped_rooms = ExamRoom.objects.filter(
            is_active=True, linked_section__isnull=False
        ).select_related("linked_section")
        for room in mapped_rooms:
            assert room.linked_section is not None
            # Motor anahtarı "seviye/şube" biçimidir (Hazırlıkta "0/A" — class_label
            # "Hz/A" DEĞİL; engine.distribute_home_classroom sözleşmesi).
            key = f"{room.linked_section.class_level}/{room.linked_section.class_section}"
            section_map[key] = _room_seats_for(room)
        try:
            result = engine.distribute_home_classroom(pool, section_map)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        # Kurallar klasik düzende uygulanmaz — öğrenci zaten kendi dersliğinde.
        if _effective_rules(session, [p.student_id for p in pool]):
            result.warnings.append(
                "Yerleştirme kuralları klasik düzende uygulanmaz (öğrenciler kendi " "dersliğinde)."
            )
    else:
        rooms = _session_room_seats(session)
        if not rooms:
            raise ValidationError("Oturuma salon eklenmemiş; önce salon seçin (Adım 3).")
        # Kural pinleri koltuğa bağlanır; motor onları taşıyamaz.
        preplaced, butterfly_rooms, pin_warnings = _resolve_rule_pins(session, pool, rooms)
        pinned_ids = {pl.participant.student_id for pl in preplaced}
        free_pool = [p for p in pool if p.student_id not in pinned_ids]
        previous = _previous_seats_map(session, [p.student_id for p in free_pool])
        try:
            result = engine.distribute_butterfly(
                free_pool,
                butterfly_rooms,
                seed=seed,
                strict=strict,
                preplaced=preplaced,
                previous_seats=previous,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        result.placements = [*preplaced, *result.placements]
        result.warnings.extend(pin_warnings)

    report = validator.validate_seating(
        _placed_from(result.placements),
        strict=strict,
        # Klasik düzende (kendi dersliğinde) tüm şube aynı gruptur; bitişik
        # oturma beklenen durumdur — yalnız bütünlük denetlenir (K3).
        enforce_group_separation=session.layout_mode == LayoutMode.BUTTERFLY,
    )

    # Önceki canlı yerleşimi kapat, yenisini yaz (SNAPSHOT deseni).
    SeatAssignment.objects.filter(session=session).update(deleted_at=timezone.now())
    # F7: yeniden dağıtımda salon kümesi değişebilir — görevlendirmeler
    # sıfırlanır (OYS T9b); muafiyetlere DOKUNULMAZ.
    stale_proctors = ProctorAssignment.objects.filter(session=session)
    if stale_proctors.exists():
        stale_proctors.update(deleted_at=timezone.now())
        result.warnings.append(
            "Gözetmen görevlendirmeleri yeni dağıtım nedeniyle sıfırlandı; yeniden atayın."
        )
    SeatAssignment.objects.bulk_create(
        SeatAssignment(
            session=session,
            student_id=pl.participant.student_id,
            full_name=pl.participant.full_name,
            student_number=pl.participant.student_number,
            class_label=f"{pl.participant.class_level}/{pl.participant.class_section}",
            room_id=pl.room_id,
            desk_row=pl.seat.desk_row,
            desk_col=pl.seat.desk_col,
            slot=pl.seat.slot,
            seat_no=pl.seat.seat_no,
            status=(
                SeatStatus.PINNED if pl.participant.student_id in pinned_ids else SeatStatus.NORMAL
            ),
            conflict_group=pl.participant.conflict_group,
        )
        for pl in result.placements
    )

    # K1: salon doluluk farkı gözlemi — yalnız kelebek (klasikte doluluk şubenin
    # kendisidir). Uyarı distribution_params.warnings ile kalıcılaşır.
    if session.layout_mode == LayoutMode.BUTTERFLY:
        gap_warning = _occupancy_gap_warning(room_occupancy(session))
        if gap_warning is not None:
            result.warnings.append(gap_warning)

    # Şube→salon yoğunlaşma metriği — PII yok (etiket+sayı).
    section_rooms: dict[str, set[int]] = {}
    for pl in result.placements:
        label = f"{pl.participant.class_level}/{pl.participant.class_section}"
        section_rooms.setdefault(label, set()).add(pl.room_id)
    rooms_per_section = {label: len(room_ids) for label, room_ids in section_rooms.items()}

    session.status = ExamSessionStatus.DISTRIBUTED
    session.distribution_params = {
        "seed": result.seed,
        "strict": strict,
        "checkerboard": result.checkerboard,
        "layout_mode": session.layout_mode,
        "placed": len(result.placements),
        "pinned": len(pinned_ids),
        "rooms_per_section": {
            "max": max(rooms_per_section.values(), default=0),
            "avg": (
                round(sum(rooms_per_section.values()) / len(rooms_per_section), 2)
                if rooms_per_section
                else 0
            ),
            "sections": dict(sorted(rooms_per_section.items())),
        },
        "warnings": result.warnings,
    }
    session.save(update_fields=["status", "distribution_params", "updated_at"])
    return session, result, report


@transaction.atomic
def swap_seats(
    session: ExamSession,
    *,
    assignment_a_id: int,
    assignment_b_id: int,
) -> tuple[list[SeatAssignment], validator.SeatingReport]:
    """İki öğrencinin koltuğunu takas eder (önizleme — elle düzeltme).

    Yalnız DAĞITILDI durumda (onaylı/arşiv kilitli); her iki satır da bu
    oturumun CANLI yerleşimi olmalı. Takas sonrası iki satır da MANUAL
    işaretlenir ve BAĞIMSIZ doğrulayıcı raporu döner — UI sert ihlali anında
    kırmızı gösterir. Hata mesajları adsızdır (KVKK).
    """
    if session.status != ExamSessionStatus.DISTRIBUTED:
        raise ValidationError(
            f"Oturum '{session.get_status_display()}' durumunda; takas yalnız dağıtılmış "
            "(henüz onaylanmamış) oturumda yapılabilir."
        )
    if assignment_a_id == assignment_b_id:
        raise ValidationError("Takas için iki FARKLI koltuk seçin.")
    rows = list(
        SeatAssignment.objects.filter(
            session=session, pk__in=(assignment_a_id, assignment_b_id)
        ).select_for_update()
    )
    if len(rows) != 2:
        raise ValidationError("Takas satırı bulunamadı (bu oturumun canlı yerleşimi değil).")
    a, b = rows
    a_seat = (a.room_id, a.desk_row, a.desk_col, a.slot, a.seat_no)
    b_seat = (b.room_id, b.desk_row, b.desk_col, b.slot, b.seat_no)
    # Koltuk tekilliği (session, room, seat_no) kısmi unique'e takılmasın diye
    # üç aşamada yaz: önce A'yı geçici koltuğa al, sonra B→A koltuğu, sonra A→B.
    a.room_id, a.desk_row, a.desk_col, a.slot, a.seat_no = (
        b_seat[0],
        b_seat[1],
        b_seat[2],
        b_seat[3],
        0,
    )
    a.status = SeatStatus.MANUAL
    a.save(
        update_fields=["room", "desk_row", "desk_col", "slot", "seat_no", "status", "updated_at"]
    )
    b.room_id, b.desk_row, b.desk_col, b.slot, b.seat_no = a_seat
    b.status = SeatStatus.MANUAL
    b.save(
        update_fields=["room", "desk_row", "desk_col", "slot", "seat_no", "status", "updated_at"]
    )
    a.seat_no = b_seat[4]
    a.save(update_fields=["seat_no", "updated_at"])
    return [a, b], seating_report(session)


#: Doluluk farkı uyarı eşiği (yüzde puan) — K1 gözlemlenebilirlik.
_OCCUPANCY_GAP_THRESHOLD = 20.0


def room_occupancy(session: ExamSession) -> list[dict[str, Any]]:
    """Salon doluluk özeti (K1): kapasite (override uygulanmış) + yerleşen + yüzde.

    Oturum salonları sıralı döner; klasik düzende (ExamSessionRoom satırı yok)
    yerleşimde geçen derslikler ad sırasıyla eklenir. PII yok (salon adı + sayı).
    """
    counts: dict[int, int] = {}
    for room_id in SeatAssignment.objects.filter(session=session).values_list("room_id", flat=True):
        counts[room_id] = counts.get(room_id, 0) + 1

    result: list[dict[str, Any]] = []
    rows = (
        ExamSessionRoom.objects.filter(session=session)
        .select_related("room")
        .order_by("order", "id")
    )
    for row in rows:
        capacity = len(_room_seats_for(row.room, cap=row.capacity_override).seats)
        placed_count = counts.get(row.room_id, 0)
        result.append(
            {
                "room_id": row.room_id,
                "room_name": row.room.name,
                "capacity": capacity,
                "placed": placed_count,
                "percent": round(100 * placed_count / capacity, 1) if capacity else 0.0,
            }
        )
    # Klasik düzen: yerleşim salonları oturum salon listesinde olmayabilir.
    known = {int(o["room_id"]) for o in result}
    extra_ids = [rid for rid in counts if rid not in known]
    for room in ExamRoom.objects.filter(pk__in=extra_ids).order_by("name"):
        capacity = len(room_seats(room))
        placed_count = counts[room.pk]
        result.append(
            {
                "room_id": room.pk,
                "room_name": room.name,
                "capacity": capacity,
                "placed": placed_count,
                "percent": round(100 * placed_count / capacity, 1) if capacity else 0.0,
            }
        )
    return result


def _occupancy_gap_warning(occupancy: list[dict[str, Any]]) -> str | None:
    """En dolu ↔ en boş salon farkı eşiği aşarsa Türkçe uyarı (K1; saf fn).

    Motor kapasite-oransal kota kullandığından fark normalde küçüktür; büyük
    fark tipik olarak elle capacity_override / kural pinleri kaynaklıdır.
    """
    percents = [float(o["percent"]) for o in occupancy if int(o["capacity"]) > 0]
    if len(percents) < 2:
        return None
    gap = max(percents) - min(percents)
    if gap <= _OCCUPANCY_GAP_THRESHOLD:
        return None
    return (
        f"Salon doluluk farkı yüksek (en dolu %{max(percents):.0f}, en boş "
        f"%{min(percents):.0f}): dengeli dağıtım için salon kapasite sınırıyla "
        "(capacity_override) dolulukları yaklaştırabilirsiniz."
    )


def seating_report(session: ExamSession) -> validator.SeatingReport:
    """Kayıtlı yerleşimi bağımsız doğrulayıcıdan geçirir (R8 metrikleri).

    Koordinatlar salon planlarından yeniden türetilir — DB'de tutulmaz.
    """
    assignments = list(SeatAssignment.objects.filter(session=session).select_related("room"))
    seat_maps: dict[int, dict[tuple[int, int, int], Any]] = {}
    placed: list[validator.PlacedStudent] = []
    for a in assignments:
        if a.room_id not in seat_maps:
            seat_maps[a.room_id] = {(s.desk_row, s.desk_col, s.slot): s for s in room_seats(a.room)}
        seat = seat_maps[a.room_id].get((a.desk_row, a.desk_col, a.slot))
        if seat is None:
            # Plan dağıtımdan sonra değişmiş — metrik üretilemez; ihlal olarak raporla.
            report = validator.SeatingReport()
            report.hard_violations.append(
                f"Salon {a.room_id} planı dağıtımdan sonra değişmiş; yeniden dağıtın."
            )
            return report
        placed.append(
            validator.PlacedStudent(
                student_id=a.student_id,
                conflict_group=a.conflict_group,
                room_id=a.room_id,
                desk_row=a.desk_row,
                desk_col=a.desk_col,
                slot=a.slot,
                x=seat.x,
                y=seat.y,
                section_label=a.class_label,  # K1: snapshot'taki "9/A" etiketi
            )
        )
    strict = bool(session.distribution_params.get("strict", False))
    return validator.validate_seating(
        placed,
        strict=strict,
        enforce_group_separation=session.layout_mode == LayoutMode.BUTTERFLY,
    )


# ---------------------------------------------------------------------------
# Onay / kilit / arşiv (onaylı oturum değiştirilemez)
# ---------------------------------------------------------------------------
@transaction.atomic
def approve_session(session: ExamSession, *, approved_by_name: str = "") -> ExamSession:
    """Oturumu onaylar (DAĞITILDI → ONAYLANDI) — yerleşim İHLALSİZ olmalı.

    R8 doğrulayıcısı sert ihlal bulursa onay reddedilir; mesaj yalnız SAYI
    içerir (öğrenci adı asla — KVKK). Onay damgası ad + zaman (B12); ad
    verilmezse kurulumdaki müdür adı basılır.
    """
    if session.status != ExamSessionStatus.DISTRIBUTED:
        raise ValidationError(
            f"Oturum '{session.get_status_display()}' durumunda; yalnız dağıtılmış oturum "
            "onaylanabilir."
        )
    report = seating_report(session)
    if not report.is_valid:
        raise ValidationError(
            f"Onay reddedildi: yerleşimde {len(report.hard_violations)} sert kısıt ihlali var. "
            "Önce yeniden dağıtın (doğrulama raporuna bakın)."
        )
    session.status = ExamSessionStatus.APPROVED
    session.approved_by_name = " ".join((approved_by_name or "").split()) or _default_stamp_name()
    session.approved_at = timezone.now()
    session.save(update_fields=["status", "approved_by_name", "approved_at", "updated_at"])
    return session


@transaction.atomic
def reopen_session(session: ExamSession) -> ExamSession:
    """Onayı geri alır (ONAYLANDI → DAĞITILDI) — yanlış onay telafisi.

    Onay damgaları temizlenir. Arşivlenmiş oturum geri açılamaz (salt-okunur).
    """
    if session.status != ExamSessionStatus.APPROVED:
        raise ValidationError(
            f"Oturum '{session.get_status_display()}' durumunda; yalnız onaylı oturum "
            "yeniden açılabilir."
        )
    session.status = ExamSessionStatus.DISTRIBUTED
    session.approved_by_name = ""
    session.approved_at = None
    session.save(update_fields=["status", "approved_by_name", "approved_at", "updated_at"])
    return session


@transaction.atomic
def archive_session(session: ExamSession) -> ExamSession:
    """Oturumu arşivler (ONAYLANDI → ARŞİV) — geri dönüşsüz, salt-okunur.

    Arşivden evrak yeniden basılabilir; düzenleme/dağıtım/geri açma kapalıdır.
    """
    if session.status != ExamSessionStatus.APPROVED:
        raise ValidationError(
            f"Oturum '{session.get_status_display()}' durumunda; yalnız onaylı oturum "
            "arşivlenebilir."
        )
    session.status = ExamSessionStatus.ARCHIVED
    session.save(update_fields=["status", "updated_at"])
    return session


# ---------------------------------------------------------------------------
# Yerleştirme kuralları (KVKK sıkı: gerekçe YALNIZ kategori)
# ---------------------------------------------------------------------------
def create_placement_rule(
    *,
    student_id: int,
    rule_type: str,
    reason_category: str = RuleReason.OTHER,
    scope: str = RuleScope.PERMANENT,
    session: ExamSession | None = None,
    target_room_id: int | None = None,
) -> PlacementRule:
    """Sabit yerleştirme kuralı oluşturur (gerekçe YALNIZ kategori — KVKK md. 6)."""
    if okul_selectors.get_student(student_id) is None:
        raise ValidationError("Öğrenci bulunamadı.")
    if scope == RuleScope.SESSION and session is None:
        raise ValidationError("Oturum kapsamı için oturum seçin.")
    if scope == RuleScope.PERMANENT:
        session = None
    # Kilit: onaylı/arşiv oturuma kural eklenemez (yerleşim değiştirilemez).
    if session is not None and session.status not in (
        ExamSessionStatus.DRAFT,
        ExamSessionStatus.DISTRIBUTED,
    ):
        raise ValidationError(
            f"Oturum '{session.get_status_display()}' durumunda; kural eklenemez "
            "(onaylı/arşivlenmiş oturum değiştirilemez)."
        )

    target_room: ExamRoom | None = None
    if rule_type in (RuleType.FIXED_ROOM, RuleType.SEPARATE_ROOM):
        if target_room_id is None:
            raise ValidationError("Bu kural tipi için hedef salon zorunludur.")
        target_room = ExamRoom.objects.filter(pk=target_room_id, is_active=True).first()
        if target_room is None:
            raise ValidationError("Hedef salon bulunamadı (veya pasif).")
    elif target_room_id is not None:
        raise ValidationError("Bu kural tipi hedef salon almaz.")

    qs = PlacementRule.objects.filter(student_id=student_id, session=session)
    if qs.exists():
        raise ValidationError("Bu öğrenci için bu kapsamda zaten canlı bir kural var.")

    rule: PlacementRule = PlacementRule.objects.create(
        student_id=student_id,
        scope=scope,
        session=session,
        rule_type=rule_type,
        target_room=target_room,
        reason_category=reason_category,
    )
    return rule


def remove_placement_rule(rule: PlacementRule) -> None:
    """Kuralı kaldırır (soft-delete)."""
    rule.delete()


def _effective_rules(session: ExamSession, student_ids: list[int]) -> dict[int, PlacementRule]:
    """Öğrenci başına geçerli kural: OTURUM kapsamı KALICI'yı ezer."""
    rules = PlacementRule.objects.filter(
        Q(session=session) | Q(session__isnull=True),
        student_id__in=student_ids,
    ).select_related("target_room")
    chosen: dict[int, PlacementRule] = {}
    for rule in rules:
        current = chosen.get(rule.student_id)
        if current is None or (current.session_id is None and rule.session_id is not None):
            chosen[rule.student_id] = rule
    return chosen


def _previous_seats_map(session: ExamSession, student_ids: list[int]) -> engine.PrevSeats:
    """Öğrencinin en son BAŞKA oturumdaki sırası (önceki oturum farklılığı)."""
    prev: engine.PrevSeats = {}
    rows = (
        SeatAssignment.objects.filter(student_id__in=student_ids)
        .exclude(session=session)
        .order_by("student_id", "-created_at")
        .values_list("student_id", "room_id", "desk_row", "desk_col")
    )
    for student_id, room_id, desk_row, desk_col in rows:
        if student_id not in prev:
            prev[student_id] = (room_id, desk_row, desk_col)
    return prev


def _resolve_rule_pins(
    session: ExamSession,
    pool: list[participants.Participant],
    session_rooms_list: list[engine.RoomSeats],
) -> tuple[list[engine.Placement], list[engine.RoomSeats], list[str]]:
    """Kural pinlerini koltuklara bağlar (deterministik — öğrenci id sıralı).

    Döner: (pinli yerleşimler, kelebeğe kalan salonlar, uyarılar). AYRI_SALON
    hedefi kelebek salon listesinden çıkarılır (salon o öğrenciye ayrılır).
    """
    by_student = {p.student_id: p for p in pool}
    rules = _effective_rules(session, list(by_student))
    if not rules:
        return [], session_rooms_list, []

    warnings: list[str] = []
    rooms_cache: dict[int, engine.RoomSeats] = {r.room_id: r for r in session_rooms_list}
    taken: dict[int, set[tuple[int, int, int]]] = {}

    def _room_seats_by_id(room_id: int) -> engine.RoomSeats:
        if room_id not in rooms_cache:
            room = ExamRoom.objects.filter(pk=room_id, is_active=True).first()
            if room is None:
                raise ValidationError(f"Kural hedef salonu bulunamadı (id={room_id}).")
            rooms_cache[room_id] = _room_seats_for(room)
        return rooms_cache[room_id]

    def _take_seat(rs: engine.RoomSeats, *, front_only: bool = False) -> Any:
        keys = taken.setdefault(rs.room_id, set())
        front_row = min((s.desk_row for s in rs.seats), default=None)
        for seat in rs.seats:
            key = (seat.desk_row, seat.desk_col, seat.slot)
            if key in keys:
                continue
            if front_only and seat.desk_row != front_row:
                continue
            keys.add(key)
            return seat
        return None

    preplaced: list[engine.Placement] = []
    separate_room_ids: set[int] = set()

    for student_id in sorted(rules):
        rule = rules[student_id]
        p = by_student[student_id]
        seat = None
        rs: engine.RoomSeats | None = None
        if rule.rule_type == RuleType.HOME_CLASSROOM:
            room = (
                ExamRoom.objects.filter(
                    is_active=True,
                    linked_section__class_level=p.class_level,
                    linked_section__class_section=p.class_section,
                )
                .order_by("id")
                .first()
            )
            if room is None:
                raise ValidationError(
                    f"KENDI_DERSLIGINDE kuralı: {p.class_level}/{p.class_section} için "
                    "bağlı derslik tanımlı değil (salon 'bağlı şube' alanı)."
                )
            rs = _room_seats_by_id(room.pk)
            seat = _take_seat(rs)
        elif rule.rule_type in (RuleType.FIXED_ROOM, RuleType.SEPARATE_ROOM):
            assert rule.target_room_id is not None  # create'te doğrulandı
            rs = _room_seats_by_id(rule.target_room_id)
            if rule.rule_type == RuleType.SEPARATE_ROOM:
                separate_room_ids.add(rs.room_id)
            seat = _take_seat(rs)
        else:  # FRONT_ROW — oturum salonlarından ön sırada ilk boş koltuk
            for candidate in session_rooms_list:
                seat = _take_seat(candidate, front_only=True)
                if seat is not None:
                    rs = candidate
                    break
            if seat is None:
                raise ValidationError(
                    "ON_SIRA kuralı için oturum salonlarında boş ön sıra koltuğu kalmadı."
                )
        if seat is None:
            assert rs is not None
            raise ValidationError(
                f"Sabit kural için salonda boş koltuk kalmadı (salon id={rs.room_id})."
            )
        assert rs is not None
        preplaced.append(engine.Placement(participant=p, room_id=rs.room_id, seat=seat))

    butterfly_rooms = [r for r in session_rooms_list if r.room_id not in separate_room_ids]
    removed = {r.room_id for r in session_rooms_list} & separate_room_ids
    for room_id in sorted(removed):
        warnings.append(
            f"Salon {room_id} AYRI_SALON kuralına ayrıldı; kelebek dağıtımından çıkarıldı."
        )
    return preplaced, butterfly_rooms, warnings


# ---------------------------------------------------------------------------
# Yoklama — sınava girmeyen öğrenci takibi (Tur 245)
# ---------------------------------------------------------------------------
def _ensure_attendance_open(session: ExamSession) -> None:
    """Yoklama yalnız ONAYLI/ARŞİV oturumda işlenir (yerleşim kesin olmalı)."""
    if session.status not in (ExamSessionStatus.APPROVED, ExamSessionStatus.ARCHIVED):
        raise ValidationError(
            f"Oturum '{ExamSessionStatus(session.status).label}' durumunda; "
            "yoklama yalnız onaylanmış oturumda işlenir."
        )
    if session.anonymized_at is not None:
        # F27 (F8'de gelir): snapshot'lar anonim — yeni kişisel kayıt açılamaz.
        raise ValidationError("Oturum arşiv saklama süresi sonunda anonimleştirilmiş.")


@transaction.atomic
def mark_absent(
    session: ExamSession,
    *,
    seat_assignment_id: int,
    excuse_status: str = ExcuseStatus.PENDING,
    note: str = "",
) -> ExamAttendanceRecord:
    """Öğrenciyi sınava GİRMEDİ olarak işaretler (snapshot assignment'tan).

    Referans noktası SeatAssignment'tır — oturumun fiili listesi odur;
    katılımcı yeniden çözülmez. Hata mesajları ad içermez (okul no — KVKK).
    """
    _ensure_attendance_open(session)
    assignment = SeatAssignment.objects.filter(pk=seat_assignment_id, session=session).first()
    if assignment is None:
        raise ValidationError("Yerleşim kaydı bu oturumda bulunamadı.")
    if ExamAttendanceRecord.objects.filter(session=session, student=assignment.student).exists():
        raise ValidationError(
            f"Okul No {assignment.student_number} bu oturumda zaten girmedi olarak işaretli."
        )
    if excuse_status not in ExcuseStatus.values:
        raise ValidationError(f"Geçersiz mazeret durumu: {excuse_status!r}.")
    record: ExamAttendanceRecord = ExamAttendanceRecord.objects.create(
        session=session,
        student=assignment.student,
        full_name=assignment.full_name,
        student_number=assignment.student_number,
        class_label=assignment.class_label,
        room=assignment.room,
        seat_no=assignment.seat_no,
        excuse_status=excuse_status,
        note=note.strip(),
    )
    return record


def update_attendance_record(record: ExamAttendanceRecord, **fields: Any) -> ExamAttendanceRecord:
    """Mazeret durumu/notu günceller — ARŞİVDE DE açık (belge sonradan gelir)."""
    if "excuse_status" in fields:
        status = fields["excuse_status"]
        if status not in ExcuseStatus.values:
            raise ValidationError(f"Geçersiz mazeret durumu: {status!r}.")
        record.excuse_status = status
    if "note" in fields:
        record.note = str(fields["note"] or "").strip()
    record.save(update_fields=["excuse_status", "note", "updated_at"])
    return record


def unmark_absent(record: ExamAttendanceRecord) -> None:
    """Yanlış işaretleme telafisi — soft-delete (iz kalır)."""
    record.delete()


# ===========================================================================
# F4 — sınav evrakı (rapor tasarım sistemi + R1-R5 + R7-R9; tasarım §9)
# ===========================================================================

#: Geçerli rapor kodları (URL parçası; R10 = kitapçık, F5'te ayrı uç).
REPORT_CODES: tuple[str, ...] = ("r1", "r2", "r2k", "r3", "r4", "r5", "r6", "r7", "r8", "r9")

#: Salon filtresi yalnız salon bazlı çıktılarında anlamlı.
_ROOM_SCOPED_CODES: frozenset[str] = frozenset({"r1", "r2", "r3", "r7"})

#: Evrak üretimine açık oturum durumları (ARŞİV dahil — yeniden basım).
_REPORTABLE_STATUSES: tuple[str, ...] = (
    ExamSessionStatus.DISTRIBUTED,
    ExamSessionStatus.APPROVED,
    ExamSessionStatus.ARCHIVED,
)

_PDF_MIME = "application/pdf"
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@dataclass(frozen=True)
class ReportFile:
    """Üretilmiş tek evrak — uç bunu indirme yanıtına çevirir."""

    filename: str
    content_type: str
    content: bytes


def _report_header(session: ExamSession) -> reports.ReportHeader:
    """Ortak üst bant — okul adı yerel yapılandırmadan (OYS core köprüsü yerine)."""
    return reports.ReportHeader(
        school_name=SchoolConfig.load().school_name,
        year_label=session.semester.school_year.name,
        semester_label=session.semester.name,
        exam_name=session.name,
        exam_date=session.exam_date.strftime("%d.%m.%Y"),
        start_time=session.start_time.strftime("%H:%M"),
        generated_at=timezone.localtime().strftime("%d.%m.%Y %H:%M"),
    )


def render_room_layout_pdf(room: ExamRoom) -> ReportFile:
    """Oturumdan bağımsız BOŞ salon yerleşim planı.

    Sınav öncesi dersliğin fiziken hazırlanması için kapıya asılır: sıra
    dizilimi + koltuk numaraları + demirbaş; ÖĞRENCİ VERİSİ İÇERMEZ (kişisel
    veri yok). build_room_kroki R1 ile aynı grid kimliğini kullanır —
    rows=() ile tüm koltuklar boş gelir, şablon yalnız numarayı basar.
    """
    plan = layout.validate_layout_plan(room.layout_plan)
    sheet = reports.RoomSheet(
        room_name=room.name,
        block=room.block,
        plan=plan,
        numbering_scheme=room.numbering_scheme,
        rows=(),
    )
    context: dict[str, object] = {
        # base.html @page footer'ı header.* okur — üç anahtar da zorunlu
        # (exam_name boş string = sağ alt slot boş kalır).
        "header": {
            "school_name": SchoolConfig.load().school_name,
            "generated_at": timezone.localtime().strftime("%d.%m.%Y %H:%M"),
            "exam_name": "",
        },
        "room": reports.build_room_kroki(sheet),
    }
    return ReportFile(
        filename=f"salon_yerlesim_plani_{room.pk}.pdf",
        content_type=_PDF_MIME,
        content=reports.render_pdf("sinav/reports/room_layout.html", context),
    )


def _seat_rows(session: ExamSession, *, room_id: int | None = None) -> list[reports.SeatRow]:
    """Yerleşim snapshot'larını saf rapor satırlarına çevirir (ders adı çözülü)."""
    qs = (
        SeatAssignment.objects.filter(session=session)
        .select_related("room")
        .order_by("room__name", "seat_no")
    )
    if room_id is not None:
        qs = qs.filter(room_id=room_id)
    assignments = list(qs)
    course_ids = {int(a.conflict_group.split(":")[0]) for a in assignments}
    course_names: dict[int, str] = ders_selectors.course_names_by_ids(course_ids)
    return [
        reports.SeatRow(
            full_name=a.full_name,
            student_number=a.student_number,
            class_label=a.class_label,
            room_name=a.room.name,
            seat_no=a.seat_no,
            desk_row=a.desk_row,
            desk_col=a.desk_col,
            slot=a.slot,
            course_name=course_names.get(int(a.conflict_group.split(":")[0]), ""),
            status=a.status,
        )
        for a in assignments
    ]


def _room_sheets(
    session: ExamSession, rows: list[reports.SeatRow], *, room_id: int | None = None
) -> list[reports.RoomSheet]:
    """R1 kroki girdileri — yalnız yerleşim almış oturum salonları, ada göre."""
    used_names = {r.room_name for r in rows}
    sheets: list[reports.RoomSheet] = []
    session_rooms = ExamSessionRoom.objects.filter(session=session).select_related("room")
    for sr in sorted(session_rooms, key=lambda sr: sr.room.name):
        room = sr.room
        if room_id is not None and room.pk != room_id:
            continue
        if room.name not in used_names:
            continue
        sheets.append(
            reports.RoomSheet(
                room_name=room.name,
                block=room.block,
                plan=layout.validate_layout_plan(room.layout_plan),
                numbering_scheme=room.numbering_scheme,
                rows=tuple(r for r in rows if r.room_name == room.name),
            )
        )
    return sheets


def render_session_report(
    session: ExamSession, code: str, *, room_id: int | None = None
) -> ReportFile:
    """Oturum evrakını üretir (R1-R5 + R7-R9; senkron — çıktılar küçük).

    Ön koşul: dağıtım yapılmış olmalı (DAĞITILDI/ONAYLANDI/ARŞİV — arşivden
    yeniden basım açık). Hata metinlerinde öğrenci adı ASLA (KVKK kuralı).
    """
    if code not in REPORT_CODES:
        raise ValidationError("Bilinmeyen rapor kodu.")
    if session.status not in _REPORTABLE_STATUSES:
        raise ValidationError("Önce dağıtım yapın — sınav evrakı yerleşimden üretilir.")
    if code == "r6":
        if not session.proctors_enabled:
            raise ValidationError("Gözetmen modülü bu oturumda kapalı (K2); R6 üretilemez.")
        if not ProctorAssignment.objects.filter(session=session).exists():
            raise ValidationError("Görevlendirme yapılmamış; önce gözetmen atayın.")
    if room_id is not None:
        if code not in _ROOM_SCOPED_CODES:
            raise ValidationError(
                "Salon filtresi yalnız salon bazlı raporlarda (R1/R2/R3) geçerli."
            )
        if not ExamSessionRoom.objects.filter(session=session, room_id=room_id).exists():
            raise ValidationError("Salon bu oturumda tanımlı değil.")

    rows = _seat_rows(session, room_id=room_id)
    if not rows:
        raise ValidationError("Oturumda yerleşim yok.")

    header = _report_header(session)
    title, stem = reports.REPORT_TITLES[code]
    if code == "r5":
        return ReportFile(
            filename=f"{stem}_oturum_{session.pk}.xlsx",
            content_type=_XLSX_MIME,
            content=reports.build_r5_workbook(header, rows),
        )

    context: dict[str, object] = {"header": header, "title": title}
    if code == "r1":
        template = "r1_kroki.html"
        context["rooms"] = [
            reports.build_room_kroki(sheet)
            for sheet in _room_sheets(session, rows, room_id=room_id)
        ]
    elif code in ("r2", "r2k"):
        template = "r2_attendance.html"
        context["sheets"] = (
            reports.build_room_attendance(rows)
            if code == "r2"
            else reports.build_section_attendance(rows)
        )
    elif code == "r3":
        template = "r3_door.html"
        context["sheets"] = reports.build_door_lists(rows)
    elif code == "r4":
        template = "r4_announcement.html"
        context["sheets"] = reports.build_announcements(rows)
    elif code == "r6":
        template = "r6_assignment.html"
        context["duty"] = reports.build_assignment_context(_proctor_rows(session))
    elif code == "r7":
        template = "r7_envelope.html"
        context["sheets"] = reports.build_envelope_sheets(rows)
    elif code == "r8":
        template = "r8_validation.html"
        context["report"] = _validation_report_context(session, rows)
    else:  # r9
        # Tek tablo: öncesi/sonrası imzaları yan yana sütun (OYS Tur 240).
        template = "r9_handover.html"
        context["rows"] = reports.build_handover_rows(
            rows, proctor_names=_proctor_names_by_room(session)
        )

    return ReportFile(
        filename=f"{stem}_oturum_{session.pk}.pdf",
        content_type=_PDF_MIME,
        content=reports.render_pdf(f"sinav/reports/{template}", context),
    )


def _proctor_rows(session: ExamSession) -> list[reports.ProctorRow]:
    """Görevlendirme snapshot'larını saf R6 satırlarına çevirir (booklet deseni)."""
    return [
        reports.ProctorRow(
            teacher_name=a.teacher_name,
            role=a.role,
            role_label=a.get_role_display(),
            room_name=a.room.name if a.room is not None else "",
        )
        for a in ProctorAssignment.objects.filter(session=session).select_related("room")
    ]


def _proctor_names_by_room(session: ExamSession) -> dict[str, str]:
    """R9 basımı: salon adı → görevli ad(lar)ı.

    Salon başına tek gözetmen beklenir (Tur 235 sonrası); join mekanik olarak
    çok-adlı eski kayıtları da kaldırır. Gözetmen modülü kapalıysa boş döner —
    R9 elle yazım modunda kalır (K2). Sıralama düz alanlarda (salon adı/rol);
    ad şifreli — ada dayalı ORM sıralaması yazılmaz (TB3).
    """
    if not session.proctors_enabled:
        return {}
    names: dict[str, list[str]] = {}
    rows = (
        ProctorAssignment.objects.filter(session=session, room__isnull=False)
        .select_related("room")
        .order_by("room__name", "role", "id")
    )
    for assignment in rows:
        assert assignment.room is not None  # filtre garantisi
        names.setdefault(assignment.room.name, []).append(assignment.teacher_name)
    return {room: ", ".join(people) for room, people in names.items()}


def _validation_report_context(
    session: ExamSession, rows: list[reports.SeatRow]
) -> dict[str, object]:
    """R8 bağlamı: bağımsız doğrulayıcı + dağıtım parametreleri (ders adlı)."""
    report = seating_report(session)
    params = dict(session.distribution_params)
    # Çakışma grubu anahtarları ortak yardımcıyla etikete çözülür.
    group_labels = conflict_group_labels(set(report.min_same_group_distance))
    return reports.build_validation_context(
        is_valid=report.is_valid,
        hard_violations=report.hard_violations,
        first_ring_pairs=report.first_ring_same_group_pairs,
        min_distances=report.min_same_group_distance,
        proximity_score=report.proximity_score,
        cross_section_pairs=report.cross_group_same_section_first_ring_pairs,
        occupancy=room_occupancy(session),
        params={
            **params,
            "layout_mode_label": LayoutMode(session.layout_mode).label,
            "seed": params.get("seed", "—"),
            "strict": bool(params.get("strict", False)),
            "checkerboard": bool(params.get("checkerboard", False)),
            "placed": params.get("placed", len(rows)),
            "pinned": params.get("pinned", 0),
        },
        group_labels=group_labels,
        warnings=[str(w) for w in params.get("warnings", [])],
    )


def render_session_reports_zip(session: ExamSession) -> ReportFile:
    """Tüm evrakı tek ZIP'te üretir (Evrak paneli "tümünü indir").

    R10 kitapçıkları HARİÇ — onlar F5'te kendi ZIP'inde. R6 yalnız gözetmen
    modülü açık + görevlendirme varken pakete girer (K2 — koşulu sağlamayan
    r6 sessizce dışarıda kalır, hata değil).
    """
    r6_available = (
        session.proctors_enabled and ProctorAssignment.objects.filter(session=session).exists()
    )
    codes = [code for code in REPORT_CODES if code != "r6" or r6_available]
    files = [
        (rf.filename, rf.content) for rf in (render_session_report(session, code) for code in codes)
    ]
    return ReportFile(
        filename=f"sinav_evraki_oturum_{session.pk}.zip",
        content_type="application/zip",
        content=reports.reports_zip(files),
    )


# ===========================================================================
# F5 — soru dosyası + kitapçık üretimi (R10; OYS T7'den UYARLA, senkron)
# ===========================================================================

_PDF_MAGIC = b"%PDF-"
_MAX_QUESTION_PDF_MB = 20
#: A4 nokta ölçüleri + tolerans (OYS Tur 646): Word'ün PDF ihracı 595.32×841.92
#: gibi küsurat üretir — ±6pt tolerans bunu kapsar, Letter'ı (612×792) reddeder.
_A4_W_PT, _A4_H_PT = 595.28, 841.89
_A4_TOL_PT = 6.0


def upload_question_document(
    sc: ExamSessionCourse,
    *,
    file_bytes: bytes,
    score_mode: str = ScoreMode.SINGLE_BOX,
    question_count: int | None = None,
) -> QuestionDocument:
    """Oturum dersine soru PDF'i yükler; mevcut canlı dosya kapatılır (iz kalır).

    Doğrulama: PDF magic bytes + boyut + sayfa sayısı (pypdf açabilmeli) +
    her sayfa A4 DİKEY ±6pt. Oturum ONAYLANDI/ARŞİV ise yükleme reddedilir.
    """
    import hashlib
    import io as _io

    from django.core.files.base import ContentFile

    if sc.session.status in (ExamSessionStatus.APPROVED, ExamSessionStatus.ARCHIVED):
        raise ValidationError("Onaylı/arşiv oturumda soru dosyası değiştirilemez.")
    if sc.shared_booklet:
        # K7 ortak kitapçık: aynı dersin tüm satırları tek dosya kullanır —
        # kardeş satırda canlı dosya varsa ikinci yükleme reddedilir.
        sibling_doc = QuestionDocument.objects.filter(
            session_course__session=sc.session,
            session_course__course=sc.course,
            session_course__deleted_at__isnull=True,
        ).exclude(session_course=sc)
        if sibling_doc.exists():
            raise ValidationError(
                "Ortak kitapçıkta soru dosyası tek satıra yüklenir — "
                f"'{sc.course.name}' için dosya başka bir seviyede zaten yüklü."
            )
    if not file_bytes:
        raise ValidationError("Boş dosya yüklenemez.")
    if not file_bytes.startswith(_PDF_MAGIC):
        raise ValidationError("Yalnız PDF kabul edilir (dosya imzası PDF değil).")
    if len(file_bytes) > _MAX_QUESTION_PDF_MB * 1024 * 1024:
        raise ValidationError(f"Dosya çok büyük (üst sınır {_MAX_QUESTION_PDF_MB} MB).")
    if score_mode == ScoreMode.QUESTION_TABLE and not question_count:
        raise ValidationError("Soru bazlı puan tablosu için soru sayısı girin.")

    from pypdf import PdfReader

    try:
        reader = PdfReader(_io.BytesIO(file_bytes))
        page_count = len(reader.pages)
    except Exception as exc:  # pypdf çeşitli hatalar fırlatabilir
        raise ValidationError("PDF okunamadı; dosya bozuk olabilir.") from exc
    if page_count == 0:
        raise ValidationError("PDF sayfa içermiyor.")

    # Sayfa boyutu/yönü doğrulaması — bant üst 4 cm sözleşmesi yalnız A4 DİKEY
    # sayfada tutar. /Rotate normalize edilir (90/270 taşıyan dikey mediabox
    # fiilen YATAYdır). NOT: üst bant içerik tespiti BİLİNÇLE yapılmaz —
    # metin katmanı taranmış PDF'te kördür, güvenilir sinyal değil.
    for page_no, page in enumerate(reader.pages, start=1):
        try:
            rotation = int(page.get("/Rotate") or 0) % 360
            box = page.mediabox
            width, height = float(box.width), float(box.height)
        except Exception as exc:
            raise ValidationError(f"PDF sayfa {page_no} okunamadı; dosya bozuk olabilir.") from exc
        if rotation in (90, 270):
            width, height = height, width
        if abs(width - _A4_W_PT) <= _A4_TOL_PT and abs(height - _A4_H_PT) <= _A4_TOL_PT:
            continue
        if abs(width - _A4_H_PT) <= _A4_TOL_PT and abs(height - _A4_W_PT) <= _A4_TOL_PT:
            raise ValidationError(
                f"Sayfa {page_no} YATAY (A4 yatay) — başlık bandı üst 4 cm sözleşmesi "
                "bozulur. Sayfaları A4 DİKEY yapın; panelden indirilen Word şablonunu "
                "kullanmanız önerilir."
            )
        raise ValidationError(
            f"Sayfa {page_no} A4 boyutunda değil ({width:.0f}×{height:.0f} pt; beklenen "
            "595×842). Belgeyi A4 dikey sayfa boyutuyla PDF'e aktarın; panelden "
            "indirilen Word şablonunu kullanmanız önerilir."
        )

    with transaction.atomic():
        QuestionDocument.objects.filter(session_course=sc).update(deleted_at=timezone.now())
        doc = QuestionDocument(
            session_course=sc,
            page_count=page_count,
            sha256=hashlib.sha256(file_bytes).hexdigest(),
            score_mode=score_mode,
            question_count=question_count if score_mode == ScoreMode.QUESTION_TABLE else None,
        )
        doc.file.save(f"soru_{sc.pk}.pdf", ContentFile(file_bytes), save=False)
        doc.save()
    return doc


def _session_info(session: ExamSession) -> booklet.SessionInfo:
    """Başlık üst bloğu — okul/il/ilçe yerel yapılandırmadan (core köprüsü yerine)."""
    config = SchoolConfig.load()
    return booklet.SessionInfo(
        school_name=config.school_name,
        year_label=session.semester.school_year.name,
        semester_label=session.semester.name,
        exam_name=session.name,
        exam_date=session.exam_date.strftime("%d.%m.%Y"),
        district=config.district,
        province=config.province,
    )


def _session_course_group_key(sc: ExamSessionCourse) -> str:
    """Satırın çakışma grubu anahtarı — participants ile tek doğruluk kaynağı."""
    if sc.shared_booklet:
        # Ortak kitapçıkta seviye anahtara girmez ("<course_id>:*").
        return participants.conflict_group_key(sc.course_id, 0, shared_booklet=True)
    if sc.level is None:
        # Servis katmanı seviyeyi ekleme anında zorunlu kılar — None bozuk satırdır.
        raise ValidationError("Oturum dersinin seviyesi eksik; dersi çıkarıp yeniden ekleyin.")
    return participants.conflict_group_key(sc.course_id, sc.level)


def _course_docs(session: ExamSession) -> dict[str, booklet.CourseDoc]:
    """Oturum derslerinin soru dosyaları: çakışma grubu anahtarı → CourseDoc.

    OYS Tur 241 (talep 9b): anahtar course_id DEĞİL grup anahtarıdır — aynı
    dersin 9. ve 10. sınıf satırları FARKLI soru dosyası taşır; eski anahtar
    seviyeleri sessizce ezerdi.
    """
    docs: dict[str, booklet.CourseDoc] = {}
    rows = QuestionDocument.objects.filter(
        session_course__session=session, session_course__deleted_at__isnull=True
    ).select_related("session_course__course")
    for qd in rows:
        sc = qd.session_course
        key = _session_course_group_key(sc)
        with qd.file.open("rb") as fh:
            pdf_bytes = fh.read()
        docs[key] = booklet.CourseDoc(
            group_key=key,
            course_name=session_course_label(
                sc.course.name, sc.level, shared_booklet=sc.shared_booklet
            ),
            pdf_bytes=pdf_bytes,
            score_mode=qd.score_mode,
            question_count=qd.question_count,
        )
    return docs


def _course_docs_keys(session: ExamSession) -> set[str]:
    """Yüklü soru dosyalarının grup anahtarları (PDF içeriği OKUNMADAN)."""
    rows = QuestionDocument.objects.filter(
        session_course__session=session, session_course__deleted_at__isnull=True
    ).select_related("session_course")
    return {_session_course_group_key(qd.session_course) for qd in rows}


def request_booklet_run(session: ExamSession, *, backup_copies: int = 0) -> BookletRun:
    """Kitapçık koşusu oluşturur ve SENKRON üretir (Celery yok — B3).

    Ön koşullar: oturum DAĞITILDI/ONAYLANDI/ARŞİV (arşivden yeniden basım) +
    her katılımcı dersin soru dosyası yüklü (eksikler DERS ADIYLA listelenir —
    öğrenci adı asla). Üretim hatası koşuyu FAILED + PII'siz error_message ile
    kapatır (OYS Celery görev gövdesinin senkron karşılığı); koşu kaydı her
    durumda döner — geçmiş izlenebilir kalır.
    """
    if session.status not in (
        ExamSessionStatus.DISTRIBUTED,
        ExamSessionStatus.APPROVED,
        ExamSessionStatus.ARCHIVED,
    ):
        raise ValidationError("Önce dağıtım yapın — kitapçık yerleşim sırasına göre üretilir.")
    assignments = SeatAssignment.objects.filter(session=session)
    if not assignments.exists():
        raise ValidationError("Oturumda yerleşim yok.")

    # Eksik kontrolü grup anahtarı bazında — seviye başına ayrı dosya.
    needed_groups = set(assignments.values_list("conflict_group", flat=True).distinct())
    have = set(_course_docs_keys(session))
    missing = needed_groups - have
    if missing:
        labels = sorted(conflict_group_labels(missing).values())
        raise ValidationError("Soru dosyası eksik dersler: " + ", ".join(labels) + ".")

    run: BookletRun = BookletRun.objects.create(session=session, backup_copies=backup_copies)
    run.status = BookletRunStatus.IN_PROGRESS
    run.save(update_fields=["status", "updated_at"])
    try:
        generate_booklets_for_run(run)
    except Exception as exc:  # üretim hatası koşuya yazılır (PII'siz)
        run.status = BookletRunStatus.FAILED
        run.error_message = f"{type(exc).__name__}: {exc}"[:2000]
        run.save(update_fields=["status", "error_message", "updated_at"])
    return run


def generate_booklets_for_run(run: BookletRun) -> BookletRun:
    """Koşunun asıl üretimi (OYS Celery görev gövdesi; testlerde doğrudan çağrılır).

    Salon bazlı paketler: yerleşim `seat_no` sırasında (kelebek → oturma
    sırası; klasik → okul no sırası — yerleşim zaten o sırada üretildi).
    """
    from django.core.files.base import ContentFile

    session = run.session
    docs = _course_docs(session)
    info = _session_info(session)

    assignments = list(
        SeatAssignment.objects.filter(session=session)
        .select_related("room")
        .order_by("room_id", "seat_no")
    )
    by_room: dict[int, tuple[str, list[booklet.BookletSpec]]] = {}
    for a in assignments:
        name, specs = by_room.setdefault(a.room_id, (a.room.name, []))
        specs.append(
            booklet.BookletSpec(
                full_name=a.full_name,
                class_label=a.class_label,
                student_number=a.student_number,
                group_key=a.conflict_group,
            )
        )

    packages = [
        booklet.build_room_package(name, specs, docs, info, backup_copies=run.backup_copies)
        for name, specs in by_room.values()
    ]
    zip_bytes = booklet.package_zip(packages)

    run.manifest = {
        "rooms": [
            {
                "room_name": pkg.room_name,
                "booklets": pkg.booklet_count,
                "pages": pkg.page_count,
                "missing_groups": pkg.missing_groups,
            }
            for pkg in packages
        ],
        "total_booklets": sum(p.booklet_count for p in packages),
        "total_pages": sum(p.page_count for p in packages),
    }
    run.file.save(
        f"kitapcik_oturum_{session.pk}_kosu_{run.pk}.zip", ContentFile(zip_bytes), save=False
    )
    run.status = BookletRunStatus.COMPLETED
    run.completed_at = timezone.now()
    run.save()
    return run


# ===========================================================================
# F7 — gözetmen görevlendirme (OYS T9b'den UYARLA; U2: ELLE atama)
# Oto-atama ALINMADI (TB4): OYS'de havuz ders programı + devamsızlık
# köprülerine dayanıyordu (B5/B6) — o kaynaklar KS'de yok, aynı yanlış-seçim
# sorunu geri gelirdi. Adil-yük sayacı da onunla gitti.
# ===========================================================================


def _ensure_proctors_editable(session: ExamSession) -> None:
    """Görevlendirme yalnız gözetmen modülü açık + DAĞITILDI oturumda düzenlenir.

    Taslakta salonlar kesin değildir (klasik düzende salonlar yerleşimden
    gelir); onaylı/arşiv oturumda evrak kilitlidir (T9 emsali).
    """
    if not session.proctors_enabled:
        raise ValidationError("Gözetmen modülü bu oturumda kapalı (K2) — oturum ayarlarından açın.")
    if session.status != ExamSessionStatus.DISTRIBUTED:
        raise ValidationError(
            f"Oturum '{session.get_status_display()}' durumunda; görevlendirme yalnız "
            "dağıtılmış (henüz onaylanmamış) oturumda düzenlenebilir."
        )


def _resolve_active_personnel(teacher_id: int) -> Personnel:
    """Aktif personeli çözer (OYS core köprüsü yerine yerel tablo — B9)."""
    teacher: Personnel | None = Personnel.objects.filter(pk=teacher_id, is_active=True).first()
    if teacher is None:
        raise ValidationError(f"Aktif personel bulunamadı (id={teacher_id}).")
    return teacher


def create_proctor_exemption(
    *,
    teacher_id: int,
    scope: str = RuleScope.PERMANENT,
    session: ExamSession | None = None,
    reason_category: str = ExemptionReason.OTHER,
) -> ProctorExemption:
    """Gözetmenlik muafiyeti oluşturur (gerekçe YALNIZ kategori — KVKK).

    PlacementRule emsali: kapsam SESSION ise oturum zorunlu; onaylı/arşiv
    oturuma muafiyet eklenemez; öğretmen başına kapsamda tek canlı kayıt.
    """
    teacher = _resolve_active_personnel(teacher_id)
    if scope == RuleScope.SESSION and session is None:
        raise ValidationError("Oturum kapsamı için oturum seçin.")
    if scope == RuleScope.PERMANENT:
        session = None
    if session is not None and session.status not in (
        ExamSessionStatus.DRAFT,
        ExamSessionStatus.DISTRIBUTED,
    ):
        raise ValidationError(
            f"Oturum '{session.get_status_display()}' durumunda; muafiyet eklenemez "
            "(onaylı/arşivlenmiş oturum değiştirilemez)."
        )
    if ProctorExemption.objects.filter(teacher=teacher, session=session).exists():
        raise ValidationError("Bu öğretmen için bu kapsamda zaten canlı bir muafiyet var.")
    exemption: ProctorExemption = ProctorExemption.objects.create(
        teacher=teacher,
        scope=scope,
        session=session,
        reason_category=reason_category,
    )
    return exemption


def remove_proctor_exemption(exemption: ProctorExemption) -> None:
    """Muafiyeti kaldırır (soft-delete — tarihsel iz)."""
    exemption.delete()


def _exempt_teacher_ids(session: ExamSession) -> set[int]:
    """Oturum için geçerli muafiyetler: oturuma özel + kalıcı."""
    return set(
        ProctorExemption.objects.filter(Q(session=session) | Q(session__isnull=True)).values_list(
            "teacher_id", flat=True
        )
    )


def _busy_teacher_ids(session: ExamSession) -> set[int]:
    """Aynı tarihte zaman penceresi çakışan BAŞKA oturumda görevli öğretmenler.

    Pencere oturum süresinden hesaplanır (ders bazlı süre farkları yok
    sayılır — pencere oturumun varsayılan süresidir).
    """
    from datetime import datetime, timedelta

    def _window(s: ExamSession) -> tuple[datetime, datetime]:
        start = datetime.combine(s.exam_date, s.start_time)
        return start, start + timedelta(minutes=s.duration_minutes)

    start, end = _window(session)
    busy: set[int] = set()
    rows = (
        ProctorAssignment.objects.filter(session__exam_date=session.exam_date)
        .exclude(session=session)
        .select_related("session")
    )
    for row in rows:
        other_start, other_end = _window(row.session)
        if start < other_end and other_start < end:
            if row.teacher_id is not None:
                busy.add(row.teacher_id)
    return busy


def _seated_rooms(session: ExamSession) -> list[ExamRoom]:
    """Yerleşim almış salonlar (ada göre) — klasikte ExamSessionRoom satırı yoktur."""
    room_ids = (
        SeatAssignment.objects.filter(session=session).values_list("room_id", flat=True).distinct()
    )
    return list(ExamRoom.objects.filter(pk__in=list(room_ids)).order_by("name"))


@transaction.atomic
def assign_proctor(
    session: ExamSession,
    *,
    teacher_id: int,
    role: str = ProctorRole.PROCTOR,
    room_id: int | None = None,
) -> ProctorAssignment:
    """Elle görevlendirme (U2 — tek akış; oto-öneri yok).

    Kendi-şube kuralı elle atamada UYGULANMAZ (idare bilinçli ezebilir);
    muafiyet ve aynı-tarih çakışması her zaman serttir.
    """
    _ensure_proctors_editable(session)
    teacher = _resolve_active_personnel(teacher_id)
    if teacher.pk in _exempt_teacher_ids(session):
        raise ValidationError("Bu öğretmen gözetmenlikten muaf; önce muafiyeti kaldırın.")
    if teacher.pk in _busy_teacher_ids(session):
        raise ValidationError(
            "Bu öğretmen aynı tarihte zaman penceresi çakışan başka oturumda görevli."
        )
    if ProctorAssignment.objects.filter(session=session, teacher=teacher).exists():
        raise ValidationError("Bu öğretmen bu oturumda zaten görevli.")

    room: ExamRoom | None = None
    if role == ProctorRole.RESERVE:
        if room_id is not None:
            raise ValidationError("Yedek görevli salona bağlanmaz (salon boş bırakılır).")
    else:
        if room_id is None:
            raise ValidationError("Bu görev için salon seçin.")
        room = next((r for r in _seated_rooms(session) if r.pk == room_id), None)
        if room is None:
            raise ValidationError("Salon bu oturumun yerleşiminde kullanılmıyor.")
        # Tur 235: salon başına TAM 1 gözetmen (DB kısıtı
        # uq_proctor_session_room_proctor_alive garanti; burada dostça hata).
        if ProctorAssignment.objects.filter(
            session=session, room=room, role=ProctorRole.PROCTOR
        ).exists():
            raise ValidationError("Bu salonda zaten bir gözetmen var.")

    assignment: ProctorAssignment = ProctorAssignment.objects.create(
        session=session,
        room=room,
        teacher=teacher,
        teacher_name=teacher.get_full_name(),
        role=role,
    )
    return assignment


def remove_proctor_assignment(assignment: ProctorAssignment) -> None:
    """Görevlendirmeyi kaldırır (soft-delete) — yalnız düzenlenebilir durumda."""
    _ensure_proctors_editable(assignment.session)
    assignment.delete()


def acknowledge_proctor(assignment: ProctorAssignment) -> ProctorAssignment:
    """Tebliğ-tebellüğ işler (mevzuat: imza karşılığı tebliğin sistem izi).

    Onaydan sonra da işlenebilir (tebliğ genelde müdür onayını izler);
    arşivde kapalı. Tek kullanıcıda elle işaret (B12 emsali).
    """
    if assignment.session.status not in (
        ExamSessionStatus.DISTRIBUTED,
        ExamSessionStatus.APPROVED,
    ):
        raise ValidationError("Tebellüğ yalnız dağıtılmış veya onaylı oturumda işlenebilir.")
    if assignment.acknowledged:
        raise ValidationError("Bu görevlendirme zaten tebellüğ edilmiş.")
    assignment.acknowledged = True
    assignment.acknowledged_at = timezone.now()
    assignment.save(update_fields=["acknowledged", "acknowledged_at", "updated_at"])
    return assignment


def proctor_candidates(session: ExamSession) -> list[dict[str, Any]]:
    """Atama ekranı verisi: aktif personel havuzu + uygunluk bayrakları.

    KS sadeleşmesi (TB4): OYS'deki ders-programı/devamsızlık bayrakları ve
    adil-yük sayacı ALINMADI — havuz = aktif personel; uygunluk = − muaf −
    aynı-pencere-görevli − bu-oturumda-görevli. Sıralama TR-katlamalı Python
    tarafında (ad şifreli — TB3).
    """
    exempt = _exempt_teacher_ids(session)
    busy = _busy_teacher_ids(session)
    assigned = set(
        ProctorAssignment.objects.filter(session=session).values_list("teacher_id", flat=True)
    )
    return [
        {
            "teacher_id": t.pk,
            "teacher_name": t.get_full_name(),
            "is_exempt": t.pk in exempt,
            "is_busy": t.pk in busy,
            "is_assigned": t.pk in assigned,
        }
        for t in okul_selectors.personnel_sorted(only_active=True)
    ]
