"""Sınav evrak motoru (T8 — yol haritası §9, rapor tasarım sistemi madde 7).

Tüm çıktılar TEK ortak şablondan türer: `templates/sinav/reports/
base.html` — DejaVu Sans (tam Türkçe; kullanıcı kararı: Roboto eklenmedi,
mevcut OYS evrakıyla tipografik tutarlılık), okul + oturum üst bandı, altbilgi
"üretim zamanı + Sayfa x/y", A4 ve gri tonlamalı ofis yazıcısı dostu.

Raporlar (R6-R10 → T9):
- R1  Salon Oturma Planı (kroki) — plan geometrisiyle birebir, salon/sayfa.
- R2  Salon Yoklama / İmza Listesi — seat_no sırası + evrak sayım satırı.
- R2k Şube Yoklama Listesi — şube/sayfa, okul no sırası.
- R3  Salon Kapı Listesi — ad/no/şube/koltuk (TCKN ASLA).
- R4  Şube Duyuru Listesi — öğrenci → salon + koltuk.
- R5  Toplu Dağıtım Çizelgesi — Excel (openpyxl), tek sayfa.

KROKİ GEOMETRİ KURALI: çizim GRID kimliğinden — (desk_row, desk_col, slot);
`layout.Seat.x/y` ASLA kullanılmaz (komşu sıra koordinatları çakışabilir —
Tur 223 tuzağı). Bu modül saf veriyle çalışır; DB erişimi services.py'dadır
(booklet.py deseni).
"""

from __future__ import annotations

import io
from collections.abc import Callable
from dataclasses import dataclass

from apps.okul import normalize as okul_normalize
from apps.sinav import layout
from apps.sinav.models import FurnitureKind, SeatStatus

#: Rapor kodu → (başlık, dosya adı kökü). Sıra: yol haritası §9 tablosu.
REPORT_TITLES: dict[str, tuple[str, str]] = {
    "r1": ("SALON OTURMA PLANI", "r1_oturma_plani"),
    "r2": ("SALON YOKLAMA VE İMZA LİSTESİ", "r2_yoklama_listesi"),
    "r2k": ("ŞUBE YOKLAMA VE İMZA LİSTESİ", "r2k_sube_yoklama"),
    "r3": ("SALON KAPI LİSTESİ", "r3_kapi_listesi"),
    "r4": ("ŞUBE DUYURU LİSTESİ", "r4_sube_duyuru"),
    "r5": ("TOPLU DAĞITIM ÇİZELGESİ", "r5_dagitim_cizelgesi"),
    "r6": ("GÖZETMEN GÖREVLENDİRME VE TEBLİĞ-TEBELLÜĞ BELGESİ", "r6_gozetmen_gorevlendirme"),
    "r7": ("SINAV EVRAK ZARFI KAPAĞI / SALON TUTANAĞI", "r7_salon_tutanagi"),
    "r8": ("DAĞITIM DOĞRULAMA RAPORU", "r8_dogrulama_raporu"),
    "r9": ("EVRAK TESLİM / TESLİM ALMA TUTANAĞI", "r9_teslim_tutanagi"),
}

_FURNITURE_LABELS: dict[str, str] = {
    FurnitureKind.DOOR: "KAPI",
    FurnitureKind.BLACKBOARD: "YAZI TAHTASI",
    FurnitureKind.SMART_BOARD: "AKILLI TAHTA",
    FurnitureKind.TEACHER_DESK: "ÖĞRETMEN MASASI",
}

_STATUS_LABELS: dict[str, str] = {
    SeatStatus.NORMAL: "",
    SeatStatus.PINNED: "Sabit",
    SeatStatus.MANUAL: "Elle taşındı",
}


@dataclass(frozen=True)
class ReportHeader:
    """Ortak üst bant (madde 7): okul + oturum bilgisi + üretim zamanı."""

    school_name: str
    year_label: str
    semester_label: str
    exam_name: str
    exam_date: str  # gg.aa.yyyy
    start_time: str  # SS:DD
    generated_at: str  # gg.aa.yyyy SS:DD


@dataclass(frozen=True)
class SeatRow:
    """Tek yerleşim satırı — SeatAssignment snapshot'ının saf izdüşümü."""

    full_name: str
    student_number: str
    class_label: str
    room_name: str
    seat_no: int
    desk_row: int
    desk_col: int
    slot: int
    course_name: str
    status: str  # SeatStatus değeri


@dataclass(frozen=True)
class RoomSheet:
    """Bir salonun kroki girdisi (plan + o salonun satırları)."""

    room_name: str
    block: str
    plan: layout.LayoutPlan
    numbering_scheme: str
    rows: tuple[SeatRow, ...]


def student_number_sort_key(number: str) -> tuple[int, int | str]:
    """Okul no sıralaması — sayısal numaralar önce ve değerce artan."""
    return (0, int(number)) if number.isdigit() else (1, number)


def room_name_sort_key(name: str) -> tuple[tuple[int, int], ...]:
    """Salon adı sıralaması — TÜRK ALFABESİNE göre ('10/I Dersliği' < '10/İ Dersliği').

    Şube derslikleri `services.section_room_name` ile adlandırılır ve şube harfi
    artık ASCII'ye katlanmadığı için ('10/İ Dersliği') ham `str` karşılaştırması
    Ç/Ğ/İ/Ö/Ş/Ü'yü 'Z'den sonraya atıyordu: 10/I ile 10/İ dersliğinin sayfaları
    basılı evrakın iki ucuna düşüyordu.

    Rakam öbeklerini SAYISAL sıralamaz ('10/A' < '9/A' davranışı korunur) —
    salon adı kelebek düzende serbest metindir ("A-101", "Çok Amaçlı Salon") ve
    karışık tipli bir anahtar sıralamada çöker. Doğal sıralama ayrı bir karardır
    ve TÜM salon yüzeylerinde birlikte yapılmalıdır.
    """
    return okul_normalize.tr_sort_key(name)


def class_label_sort_key(label: str) -> tuple[int, int, tuple[tuple[int, int], ...]]:
    """Şube sıralaması seviye-sayısal, şube harfi TÜRK ALFABESİNE göre.

    9/A < 9/B < 10/B (seviye alfabetik DEĞİL, sayısal) ve 10/C < 10/Ç < 10/D,
    10/I < 10/İ < 10/J. Şube harfi ASCII'ye katlanmadığı için (`normalize.
    tr_upper`) kod noktası sıralaması Ç/Ğ/İ/Ö/Ş/Ü'yü 'Z'den sonraya atardı.
    """
    head, _, section = label.partition("/")
    head = head.strip()
    if head.isdigit():
        return (0, int(head), okul_normalize.tr_sort_key(section))
    return (1, 0, okul_normalize.tr_sort_key(label))


# ---------------------------------------------------------------------------
# R1 — kroki
# ---------------------------------------------------------------------------
def build_room_kroki(sheet: RoomSheet) -> dict[str, object]:
    """Salon krokisi şablon bağlamı: rows×cols hücre matrisi.

    Hücre türleri: desk (koltuk kutuları slot sırasında), furniture, empty.
    Devre dışı sıra "KULLANIM DIŞI" olarak çizilir (fiziken salonda durur);
    öğrencisiz aktif koltuk "BOŞ" görünür.
    """
    plan = sheet.plan
    by_seat_key: dict[tuple[int, int, int], SeatRow] = {
        (r.desk_row, r.desk_col, r.slot): r for r in sheet.rows
    }
    seat_no_by_key: dict[tuple[int, int, int], int] = {
        (s.desk_row, s.desk_col, s.slot): s.seat_no
        for s in layout.numbered_seats(plan, sheet.numbering_scheme)
    }
    desk_by_cell = {(d.row, d.col): d for d in plan.desks}
    furniture_by_cell = {(f.row, f.col): f for f in plan.furniture}

    grid: list[list[dict[str, object]]] = []
    for row in range(plan.rows):
        cells: list[dict[str, object]] = []
        for col in range(plan.cols):
            desk = desk_by_cell.get((row, col))
            furn = furniture_by_cell.get((row, col))
            if desk is not None and not desk.disabled:
                seats: list[dict[str, object]] = []
                for slot in range(desk.seat_count):
                    key = (row, col, slot)
                    assigned = by_seat_key.get(key)
                    seats.append(
                        {
                            "seat_no": seat_no_by_key.get(key),
                            "full_name": assigned.full_name if assigned else "",
                            "student_number": assigned.student_number if assigned else "",
                            "class_label": assigned.class_label if assigned else "",
                            "empty": assigned is None,
                        }
                    )
                cells.append({"kind": "desk", "seats": seats})
            elif desk is not None:
                cells.append({"kind": "disabled_desk"})
            elif furn is not None:
                cells.append({"kind": "furniture", "label": _FURNITURE_LABELS[furn.kind]})
            else:
                cells.append({"kind": "empty"})
        grid.append(cells)

    return {
        "room_name": sheet.room_name,
        "block": sheet.block,
        "grid": grid,
        "col_width_pct": round(100.0 / plan.cols, 4),
        "student_count": len(sheet.rows),
        "capacity": plan.capacity,
    }


# ---------------------------------------------------------------------------
# R2 / R2k / R3 / R4 — liste bağlamları
# ---------------------------------------------------------------------------
def build_room_attendance(rows: list[SeatRow]) -> list[dict[str, object]]:
    """R2: salon başına sayfa, oturma (seat_no) sırasında."""
    return [
        {
            "scope_prefix": "Salon: ",
            "scope_label": room_name,
            "show_room_columns": False,
            "rows": sorted(group, key=lambda r: r.seat_no),
        }
        for room_name, group in _grouped(
            rows, key=lambda r: r.room_name, sort_key=room_name_sort_key
        ).items()
    ]


def build_section_attendance(rows: list[SeatRow]) -> list[dict[str, object]]:
    """R2k: şube başına sayfa, okul no sırasında; salon/koltuk sütunlu."""
    return [
        {
            "scope_prefix": "Şube: ",
            "scope_label": class_label,
            "show_room_columns": True,
            "rows": sorted(group, key=lambda r: student_number_sort_key(r.student_number)),
        }
        for class_label, group in _grouped(
            rows, key=lambda r: r.class_label, sort_key=class_label_sort_key
        ).items()
    ]


def build_door_lists(rows: list[SeatRow]) -> list[dict[str, object]]:
    """R3: salon başına sayfa, oturma sırasında — ad, no, şube, koltuk."""
    return [
        {
            "room_name": room_name,
            "rows": sorted(group, key=lambda r: r.seat_no),
        }
        for room_name, group in _grouped(
            rows, key=lambda r: r.room_name, sort_key=room_name_sort_key
        ).items()
    ]


def build_announcements(rows: list[SeatRow]) -> list[dict[str, object]]:
    """R4: şube başına sayfa, okul no sırasında — öğrenci → salon + koltuk."""
    return [
        {
            "class_label": class_label,
            "rows": sorted(group, key=lambda r: student_number_sort_key(r.student_number)),
        }
        for class_label, group in _grouped(
            rows, key=lambda r: r.class_label, sort_key=class_label_sort_key
        ).items()
    ]


def _grouped(
    rows: list[SeatRow],
    *,
    key: Callable[[SeatRow], str],
    sort_key: Callable[[str], tuple[object, ...]] | None = None,
) -> dict[str, list[SeatRow]]:
    """Anahtar değerine göre gruplar; grup sırası `sort_key` (yoksa alfabetik)."""
    groups: dict[str, list[SeatRow]] = {}
    for row in rows:
        groups.setdefault(key(row), []).append(row)
    if sort_key is None:
        return dict(sorted(groups.items()))
    return dict(sorted(groups.items(), key=lambda kv: sort_key(kv[0])))


# ---------------------------------------------------------------------------
# R6 — gözetmen görevlendirme / tebliğ-tebellüğ (T9b)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ProctorRow:
    """Tek görevlendirme satırı — ProctorAssignment snapshot'ının saf izdüşümü."""

    teacher_name: str
    role: str  # ProctorRole değeri
    role_label: str
    room_name: str  # YEDEK için boş


#: R6 tablo sırası: salonlu görevler salon adına göre; yedekler sonda (Tur 235: CHIEF kalktı).
_PROCTOR_ROLE_ORDER: dict[str, int] = {"PROCTOR": 0, "RESERVE": 1}


def build_assignment_context(rows: list[ProctorRow]) -> dict[str, object]:
    """R6 şablon bağlamı — resmî yazı tablosu + sayım satırları."""
    ordered = sorted(
        rows,
        key=lambda r: (
            r.room_name == "",  # yedekler (salonsuz) sona
            room_name_sort_key(r.room_name),
            _PROCTOR_ROLE_ORDER.get(r.role, 9),
            r.teacher_name,
        ),
    )
    return {
        "rows": [
            {
                "teacher_name": row.teacher_name,
                "role_label": row.role_label,
                "room_name": row.room_name or "—",
            }
            for row in ordered
        ],
        "duty_count": len(ordered),
        "reserve_count": sum(1 for row in ordered if not row.room_name),
    }


# ---------------------------------------------------------------------------
# R7 / R8 / R9 — tutanak bağlamları (T9)
# ---------------------------------------------------------------------------
def build_envelope_sheets(rows: list[SeatRow]) -> list[dict[str, object]]:
    """R7: salon başına zarf kapağı/tutanak — kayıtlı sayı + ders dağılımı.

    Mevcut/giren/girmeyen sayıları ELLE doldurulur (kutular şablonda);
    ders dağılımı görevlinin deste sayımı içindir.
    """
    sheets: list[dict[str, object]] = []
    for room_name, group in _grouped(
        rows, key=lambda r: r.room_name, sort_key=room_name_sort_key
    ).items():
        course_counts: dict[str, int] = {}
        for row in group:
            course_counts[row.course_name] = course_counts.get(row.course_name, 0) + 1
        sheets.append(
            {
                "room_name": room_name,
                "registered": len(group),
                "courses": [
                    {"course_name": name, "count": count}
                    for name, count in sorted(course_counts.items())
                ],
            }
        )
    return sheets


def build_handover_rows(
    rows: list[SeatRow], *, proctor_names: dict[str, str] | None = None
) -> list[dict[str, object]]:
    """R9: salon başına tek satır — görevli adı varsayılan ELLE yazılır (K2).

    `proctor_names` (salon adı → görevli adları) doluysa T9b gözetmen
    modülünün atamaları basılı gelir; şablon değişmez.
    """
    names = proctor_names or {}
    return [
        {
            "room_name": room_name,
            "registered": len(group),
            "proctor_name": names.get(room_name, ""),
        }
        for room_name, group in _grouped(
            rows, key=lambda r: r.room_name, sort_key=room_name_sort_key
        ).items()
    ]


def build_validation_context(
    *,
    is_valid: bool,
    hard_violations: list[str],
    first_ring_pairs: int,
    min_distances: dict[str, float],
    proximity_score: float,
    params: dict[str, object],
    group_labels: dict[str, str],
    warnings: list[str],
    cross_section_pairs: int = 0,
    occupancy: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """R8 şablon bağlamı — metrik anahtarları ders adına çözülmüş halde.

    İhlal metinleri doğrulayıcıdan adsız gelir (okul no bile yok, yalnız
    id/koordinat); burada da kişisel veri eklenmez. K1 (Tur 645):
    `cross_section_pairs` (aynı şube, farklı grup, 1. halka) +
    `occupancy` (salon doluluk tablosu — salon adı + sayı, PII yok).
    """
    return {
        "is_valid": is_valid,
        "hard_violations": hard_violations,
        "violation_count": len(hard_violations),
        "first_ring_pairs": first_ring_pairs,
        "min_distances": [
            {"group_label": group_labels.get(key, key), "distance": dist}
            for key, dist in sorted(min_distances.items())
        ],
        "proximity_score": round(proximity_score, 4),
        "cross_section_pairs": cross_section_pairs,
        "occupancy": list(occupancy or []),
        "params": params,
        "warnings": warnings,
    }


def reports_zip(files: list[tuple[str, bytes]]) -> bytes:
    """Üretilmiş evrakları tek ZIP'te toplar (dosya adı güvenli karaktere indirgenir)."""
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files:
            safe = "".join(c if c.isalnum() or c in "-_. " else "_" for c in filename)
            zf.writestr(safe or "evrak", content)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Render — PDF (WeasyPrint) + Excel (openpyxl)
# ---------------------------------------------------------------------------
def render_pdf(template_name: str, context: dict[str, object]) -> bytes:
    """Ortak şablonu kullanan rapor sayfasını PDF'e çevirir."""
    from django.template.loader import render_to_string
    from weasyprint import HTML  # tembel import — ağır bağımlılık

    return bytes(HTML(string=render_to_string(template_name, context)).write_pdf())


def build_r5_workbook(header: ReportHeader, rows: list[SeatRow]) -> bytes:
    """R5: tüm oturum tek sayfa Excel — idare çalışma kopyası.

    raporlar modülünün exporter'ı İÇERİ AKTARILMAZ (ADR-0002 modül sınırı);
    çizelge burada doğrudan openpyxl ile kurulur. Gri tonlamalı stil.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    title, _ = REPORT_TITLES["r5"]
    wb = Workbook()
    ws = wb.active
    ws.title = "Dagitim"

    columns = ("Okul No", "Ad Soyad", "Şube", "Ders", "Salon", "Koltuk No", "Durum")
    ws.cell(row=1, column=1, value=f"{header.school_name} — {title}").font = Font(
        bold=True, size=13
    )
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(columns))
    meta = (
        f"{header.exam_name} · {header.exam_date} {header.start_time} · "
        f"{header.year_label} {header.semester_label} · Üretim: {header.generated_at}"
    )
    ws.cell(row=2, column=1, value=meta)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(columns))

    header_row = 4
    for col_idx, label in enumerate(columns, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=label)
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="D9D9D9")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    ordered = sorted(
        rows, key=lambda r: (room_name_sort_key(r.room_name), r.seat_no)
    )  # salon + oturma sırası — deste/karşılaştırma kopyası
    for offset, row in enumerate(ordered):
        values = (
            row.student_number,
            row.full_name,
            row.class_label,
            row.course_name,
            row.room_name,
            row.seat_no,
            _STATUS_LABELS.get(row.status, row.status),
        )
        for col_idx, value in enumerate(values, start=1):
            ws.cell(row=header_row + 1 + offset, column=col_idx, value=value)

    widths = (10, 32, 8, 26, 18, 10, 14)
    for col_idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    ws.freeze_panes = f"A{header_row + 1}"

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
