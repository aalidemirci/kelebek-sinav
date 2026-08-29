"""sinav servisleri — F2 kesiti: salon yaşam döngüsü + koltuk önizlemesi.

OYS `sinav_islemleri/services.py`'den UYARLA (tasarım §11): `created_by` düşer;
core köprüleri yerel `apps.okul` selector'larına bağlanır (fonksiyon imzaları
korunur — köprü uyarlaması risk #2). Dağıtım/oturum servisleri F3'te gelir.
"""

from __future__ import annotations

import copy
import math
from types import EllipsisType
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.okul import selectors as okul_selectors
from apps.okul.models import ClassSection
from apps.sinav import layout
from apps.sinav.models import ExamRoom, NumberingScheme


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
