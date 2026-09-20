"""Mazeret sınav takvimi servisleri (20.09.2026, kullanıcı isteği ve kararları).

Son sınav yapılıp yoklamalar girildikten sonra, mazereti kabul edilen öğrencilerin
gireceği mazeret sınavları için AYRI bir takvim kurulur — herkesin girdiği sınavlar
bu takvimde yoktur. Yerleştirme kuralları `makeup_schedule` modül başındadır; bu
modül kayıtları takvime bağlar, yerleştiriciyi koşturur, elle düzeltmeyi denetler,
uyarıları üretir ve onaylanan takvimden mazeret oturumlarını açar.

Kullanıcı kararları: asıl takvim sırası KESİN korunur, istenirse gevşetilir
(`strict_order`) · ülke/il/ilçe geneli sınavlar otomatik yerleşmez, idareci ilan
edilen gün ve saate elle sabitler (Yönerge md. 5/1-aa, bb) · onaylanan takvimin
oturumları tek tıkla üretilir — aynı saatteki sınavlar TEK oturumda toplanır.

Dayanaklar (`docs/mevzuat/`): mazeret sınavı "önceden duyurularak" yapılır ve süre
dönemi aşamaz (OKY md. 48/1) · günde iki sınav esastır, zorunlu hâlde bir sınav
daha (Yönerge md. 5/1-s, OKY md. 45/1-g) · üst makam sınavı günü başka sınav
yapılmaz (Yönerge md. 5/1-s). Tarih ve dönem sınırları UYARIDIR (kullanıcı ilkesi:
"katı bir kısıtlama olmasın"); öğrenci çakışması SERT kısıttır — yorum payı yok.

KVKK: uyarı ve ret metinlerinde öğrenci ADI yazılmaz, okul numarası yazılır.
"""

from __future__ import annotations

from datetime import date, time
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.okul import selectors as okul_selectors
from apps.sinav import makeup_schedule as ms
from apps.sinav import services_makeup
from apps.sinav.models import (
    MAKEUP_MAX_DAY_COUNT,
    MAKEUP_MAX_PER_DAY,
    ExamAttendanceRecord,
    ExamAuthority,
    ExamCalendar,
    ExamCalendarEntry,
    ExamSession,
    ExcuseStatus,
    MakeupPlan,
    MakeupPlanItem,
    MakeupPlanStatus,
)

DEFAULT_PLAN_NAME = "Mazeret Sınav Takvimi"

_EXTERNAL_NOTE = (
    "Ülke, il ya da ilçe geneli sınav: mazeret sınavının tarihini il/ilçe millî eğitim "
    "müdürlüğü ilan eder. İlan edilen gün ve saati elle girin."
)
_EMPTY_NOTE = "Bu sınavın mazereti kabul edilmiş öğrencisi kalmadı."


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def live_item_session(item: MakeupPlanItem) -> ExamSession | None:
    """Kalemin üretilmiş mazeret oturumu — silinmişse None (soft-delete SET_NULL tetiklemez)."""
    session = item.session
    if session is None or session.deleted_at is not None:
        return None
    return session


def _ensure_draft(plan: MakeupPlan) -> None:
    if plan.status != MakeupPlanStatus.DRAFT:
        raise ValidationError(
            "Onaylanmış mazeret takvimi değiştirilemez; önce “Yeniden aç” ile taslağa alın."
        )


def _bell_periods() -> list[dict[str, Any]]:
    from apps.sinav.services_calendar import _bell_periods as periods

    return periods()


def effective_period_nos(plan: MakeupPlan) -> list[int]:
    """Takvimin sınav saatleri: kendi seçimi, yoksa okulun sınav saatleri."""
    from apps.sinav.services_calendar import exam_period_numbers

    var_olan = {int(p["no"]) for p in _bell_periods()}
    secili = sorted({int(no) for no in plan.period_nos or [] if int(no) in var_olan})
    return secili or exam_period_numbers()


def _clean_params(
    *, day_count: Any, max_per_day: Any, period_nos: Any, name: Any
) -> tuple[int, int, list[int], str]:
    try:
        gun = int(day_count)
        sinir = int(max_per_day)
    except (TypeError, ValueError):
        raise ValidationError("Gün sayısı ve günlük sınav sınırı tam sayı olmalı.") from None
    if not 1 <= gun <= MAKEUP_MAX_DAY_COUNT:
        raise ValidationError(
            {"day_count": f"Gün sayısı 1 ile {MAKEUP_MAX_DAY_COUNT} arasında olmalı."}
        )
    if not 1 <= sinir <= MAKEUP_MAX_PER_DAY:
        raise ValidationError(
            {
                "max_per_day": "Bir öğrenci bir günde en çok "
                f"{MAKEUP_MAX_PER_DAY} sınava girebilir: günde iki sınav esastır, zorunlu "
                "hâlde bir sınav daha yapılabilir (Yazılı ve Uygulamalı Sınavlar Yönergesi md. 5)."
            }
        )
    var_olan = {int(p["no"]) for p in _bell_periods()}
    saatler: list[int] = []
    for raw in period_nos or []:
        try:
            no = int(raw)
        except (TypeError, ValueError):
            raise ValidationError({"period_nos": "Sınav saatleri tam sayı olmalı."}) from None
        if no not in var_olan:
            raise ValidationError({"period_nos": f"{no}. ders saati zil çizelgesinde yok."})
        saatler.append(no)
    ad = " ".join(str(name or "").split()) or DEFAULT_PLAN_NAME
    return gun, sinir, sorted(set(saatler)), ad[:120]


def _eligible_rows(semester_id: int) -> list[dict[str, Any]]:
    """Takvime alınabilecek kayıtlar: Mazeretli, oturuma ve başka takvime alınmamış."""
    return [r for r in services_makeup.absence_rows(semester_id) if r["can_makeup"]]


def _item_records(items: list[MakeupPlanItem]) -> dict[int, list[ExamAttendanceRecord]]:
    """Kalem → CANLI ve hâlâ "Mazeretli" kayıtlar (tek sorgu; kaynak oturumu silinmemiş)."""
    sonuc: dict[int, list[ExamAttendanceRecord]] = {item.pk: [] for item in items}
    kayitlar = ExamAttendanceRecord.objects.filter(
        makeup_plan_item__in=items,
        excuse_status=ExcuseStatus.EXCUSED,
        student__isnull=False,
        session__deleted_at__isnull=True,
    ).select_related("session")
    # Sıra Python'da: şube etiketi ve okul no METİN alanıdır ("10/A" < "9/A", "1001" < "901").
    for kayit in sorted(
        kayitlar, key=lambda k: (_class_key(k.class_label), _number_key(k.student_number))
    ):
        sonuc[kayit.makeup_plan_item_id].append(kayit)
    return sonuc


def _live_items(plan: MakeupPlan) -> list[MakeupPlanItem]:
    return list(plan.items.select_related("course", "session"))


def _item_label(item: MakeupPlanItem) -> str:
    from apps.dersler.text import level_label

    return f"{item.course.name} — {level_label(item.level)}"


def _numbers(student_ids: tuple[int, ...] | set[int], by_student: dict[int, str]) -> str:
    """Öğrenci kimlikleri → 'Okul No 101, 104' (ad YAZILMAZ — KVKK)."""
    nolar = sorted({by_student.get(sid, "?") for sid in student_ids}, key=_number_key)
    kisa = ", ".join(nolar[:6]) + (f" ve {len(nolar) - 6} öğrenci daha" if len(nolar) > 6 else "")
    return f"Okul No {kisa}"


def _number_key(value: str) -> tuple[int, str]:
    return (int(value), "") if value.isdigit() else (10**9, value)


def _class_key(class_label: str) -> tuple[int, str]:
    """'10/A' → (10, 'A'); hazırlık ('Hz/A') en başa. Metin sıralaması 10'u 9'dan önce koyar."""
    duzey, _, sube = class_label.partition("/")
    return (int(duzey) if duzey.strip().isdigit() else 0, sube)


def _blocked_days(plan: MakeupPlan) -> frozenset[tuple[date, int]]:
    """Üst makam sınavı olan (gün, düzey) — o gün o düzeye mazeret sınavı konmaz."""
    girdiler = ExamCalendarEntry.objects.filter(
        calendar__semester_id=plan.semester_id,
        calendar__deleted_at__isnull=True,
        placed_date__isnull=False,
    ).exclude(authority=ExamAuthority.SCHOOL)
    return frozenset((g.placed_date, int(g.level)) for g in girdiler if g.placed_date is not None)


def _groups(
    items: list[MakeupPlanItem], kayitlar: dict[int, list[ExamAttendanceRecord]]
) -> list[ms.PlanGroup]:
    """Kalemler → yerleştirici girdisi. Sabit ya da OTURUMU üretilmiş kalem yerinde kalır."""
    gruplar: list[ms.PlanGroup] = []
    for item in items:
        ogrenciler = frozenset(int(k.student_id) for k in kayitlar[item.pk] if k.student_id)
        if not ogrenciler:
            continue
        yerinde = item.placed_date is not None and item.period_no is not None
        sabit = yerinde and (item.is_pinned or live_item_session(item) is not None)
        gruplar.append(
            ms.PlanGroup(
                key=item.pk,
                order=(item.source_date, item.source_time),
                students=ogrenciler,
                level=int(item.level),
                tie=_item_label(item),
                fixed=(item.placed_date, int(item.period_no)) if sabit else None,  # type: ignore[arg-type]
                auto=not item.external,
            )
        )
    return gruplar


# ---------------------------------------------------------------------------
# Kayıtları takvime bağlama + otomatik yerleştirme
# ---------------------------------------------------------------------------
def _attach_rows(plan: MakeupPlan, rows: list[dict[str, Any]]) -> int:
    """Kayıtları (ders, düzey) kalemlerine bağlar; kalem yoksa açar. Bağlanan kayıt sayısı."""
    mevcut = {(i.course_id, int(i.level)): i for i in _live_items(plan)}
    gruplu: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in rows:
        gruplu.setdefault((int(row["course_id"]), int(row["level"])), []).append(row)
    for anahtar, satirlar in gruplu.items():
        ilk = min(satirlar, key=lambda r: (r["exam_date"], r["exam_time"]))
        kaynak = (date.fromisoformat(ilk["exam_date"]), time.fromisoformat(ilk["exam_time"]))
        item = mevcut.get(anahtar)
        if item is None:
            item = MakeupPlanItem.objects.create(
                plan=plan,
                course_id=anahtar[0],
                level=anahtar[1],
                source_date=kaynak[0],
                source_time=kaynak[1],
                external=any(r["external"] for r in satirlar),
            )
        elif kaynak < (item.source_date, item.source_time):
            # Sıra anahtarı kalemin EN ERKEN asıl sınavıdır.
            item.source_date, item.source_time = kaynak
            item.save(update_fields=["source_date", "source_time", "updated_at"])
        ExamAttendanceRecord.objects.filter(pk__in=[r["record_id"] for r in satirlar]).update(
            makeup_plan_item=item, updated_at=timezone.now()
        )
    return len(rows)


@transaction.atomic
def auto_place(plan: MakeupPlan) -> dict[str, Any]:
    """Sabit olmayan sınavları yeniden yerleştirir; yerleşemeyenin gerekçesini kaleme yazar."""
    _ensure_draft(plan)
    items = _live_items(plan)
    kayitlar = _item_records(items)
    gruplar = _groups(items, kayitlar)
    sonuc = ms.schedule(
        gruplar,
        ms.plan_slots(plan.start_date, plan.day_count, effective_period_nos(plan)),
        max_per_day=plan.max_per_day,
        strict_order=plan.strict_order,
        blocked_days=_blocked_days(plan),
    )
    numaralar = {
        int(k.student_id): k.student_number for ks in kayitlar.values() for k in ks if k.student_id
    }
    sabitler = {g.key for g in gruplar if g.fixed is not None}
    yerlesen = 0
    for item in items:
        if item.pk in sabitler:
            continue
        slot = sonuc.placements.get(item.pk)
        item.placed_date, item.period_no = (slot[0], slot[1]) if slot else (None, None)
        item.is_pinned = False
        item.note = "" if slot else _unplaced_note(item, sonuc.unplaced.get(item.pk), numaralar)
        item.save(update_fields=["placed_date", "period_no", "is_pinned", "note", "updated_at"])
        yerlesen += 1 if slot else 0
    return {"placed": yerlesen, "unplaced": len(items) - yerlesen - len(sabitler)}


def _unplaced_note(
    item: MakeupPlanItem, neden: ms.Unplaced | None, numaralar: dict[int, str]
) -> str:
    if neden is None:
        return _EMPTY_NOTE  # öğrencisi kalmayan kalem yerleştiriciye hiç girmez
    if neden.reason == ms.NOT_AUTO:
        return _EXTERNAL_NOTE
    if neden.reason == ms.STUDENT_LIMITS:
        return (
            f"Belirlenen günlere sığmadı: {_numbers(neden.blockers, numaralar)} için uygun saat "
            "kalmadı (aynı saatte başka sınavı var ya da günlük sınırı doluyor)."
        )
    return "Belirlenen günlere sığmadı: sıradaki önceki sınavlar son saate kadar uzadı."


@transaction.atomic
def create_plan(
    *,
    semester_id: int,
    start_date: date,
    day_count: Any,
    max_per_day: Any = 2,
    period_nos: Any = None,
    strict_order: bool = True,
    name: Any = "",
) -> MakeupPlan:
    """Dönemin bekleyen "Mazeretli" kayıtlarıyla taslak mazeret takvimi kurar ve yerleştirir."""
    donem = okul_selectors.get_school_term(semester_id)
    if donem is None:
        raise ValidationError({"semester_id": "Dönem bulunamadı."})
    gun, sinir, saatler, ad = _clean_params(
        day_count=day_count, max_per_day=max_per_day, period_nos=period_nos, name=name
    )
    rows = _eligible_rows(semester_id)
    if not rows:
        raise ValidationError(
            "Takvime alınacak öğrenci yok: mazereti kabul edilmiş (“Mazeretli”) ve henüz mazeret "
            "sınavına ya da başka bir mazeret takvimine alınmamış kayıt bulunmuyor."
        )
    plan: MakeupPlan = MakeupPlan.objects.create(
        semester=donem,
        name=ad,
        start_date=start_date,
        day_count=gun,
        max_per_day=sinir,
        period_nos=saatler,
        strict_order=bool(strict_order),
    )
    _attach_rows(plan, rows)
    auto_place(plan)
    return plan


@transaction.atomic
def replan(plan: MakeupPlan, **fields: Any) -> MakeupPlan:
    """Parametreleri günceller ve sabit olmayanları yeniden yerleştirir."""
    _ensure_draft(plan)
    bilinmeyen = set(fields) - {
        "name",
        "start_date",
        "day_count",
        "max_per_day",
        "period_nos",
        "strict_order",
    }
    if bilinmeyen:
        raise ValidationError(f"Bu alanlar güncellenemez: {', '.join(sorted(bilinmeyen))}.")
    gun, sinir, saatler, ad = _clean_params(
        day_count=fields.get("day_count", plan.day_count),
        max_per_day=fields.get("max_per_day", plan.max_per_day),
        period_nos=fields.get("period_nos", plan.period_nos),
        name=fields.get("name", plan.name),
    )
    plan.name, plan.day_count, plan.max_per_day, plan.period_nos = ad, gun, sinir, saatler
    if "start_date" in fields:
        plan.start_date = fields["start_date"]
    if "strict_order" in fields:
        plan.strict_order = bool(fields["strict_order"])
    plan.save()
    auto_place(plan)
    return plan


@transaction.atomic
def sync_records(plan: MakeupPlan) -> int:
    """Takvim kurulduktan SONRA "Mazeretli" olan kayıtları ekler ve yeniden yerleştirir."""
    _ensure_draft(plan)
    rows = _eligible_rows(plan.semester_id)
    if rows:
        _attach_rows(plan, rows)
    auto_place(plan)
    return len(rows)


# ---------------------------------------------------------------------------
# Elle düzeltme
# ---------------------------------------------------------------------------
def _ensure_movable(item: MakeupPlanItem) -> None:
    _ensure_draft(item.plan)
    if live_item_session(item) is not None:
        raise ValidationError("Bu sınavın mazeret oturumu üretilmiş; yeri değiştirilemez.")


@transaction.atomic
def move_item(
    item: MakeupPlanItem, *, placed_date: date, period_no: int, pin: bool = True
) -> list[str]:
    """Sınavı elle bir gün/saate koyar. Öğrenci çakışması RET; gerisi uyarıdır.

    Dönen liste YALNIZ bu taşımanın doğurduğu yeni uyarılardır (günlük sınır, sıra,
    dönem dışı gün…) — takvimin eski uyarıları ekranda zaten durur.
    """
    _ensure_movable(item)
    if int(period_no) not in {int(p["no"]) for p in _bell_periods()}:
        raise ValidationError({"period_no": f"{period_no}. ders saati zil çizelgesinde yok."})
    onceki = set(plan_warnings(item.plan))
    items = _live_items(item.plan)
    kayitlar = _item_records(items)
    benim = {int(k.student_id): k.student_number for k in kayitlar[item.pk] if k.student_id}
    for diger in items:
        if diger.pk == item.pk or (diger.placed_date, diger.period_no) != (placed_date, period_no):
            continue
        ortak = {int(k.student_id) for k in kayitlar[diger.pk] if k.student_id} & set(benim)
        if ortak:
            raise ValidationError(
                f"{_numbers(ortak, benim)} aynı saatte “{_item_label(diger)}” sınavına da "
                "giriyor; bir öğrenci aynı anda iki sınavda olamaz."
            )
    item.placed_date, item.period_no, item.is_pinned, item.note = placed_date, period_no, pin, ""
    item.save(update_fields=["placed_date", "period_no", "is_pinned", "note", "updated_at"])
    return [w for w in plan_warnings(item.plan) if w not in onceki]


@transaction.atomic
def unplace_item(item: MakeupPlanItem) -> MakeupPlanItem:
    _ensure_movable(item)
    item.placed_date, item.period_no, item.is_pinned = None, None, False
    item.note = _EXTERNAL_NOTE if item.external else "Elle takvim dışına alındı."
    item.save(update_fields=["placed_date", "period_no", "is_pinned", "note", "updated_at"])
    return item


@transaction.atomic
def set_item_pinned(item: MakeupPlanItem, *, is_pinned: bool) -> MakeupPlanItem:
    _ensure_movable(item)
    if is_pinned and item.placed_date is None:
        raise ValidationError("Takvime konmamış sınav sabitlenemez.")
    item.is_pinned = is_pinned
    item.save(update_fields=["is_pinned", "updated_at"])
    return item


def _release_records(items: list[MakeupPlanItem]) -> None:
    ExamAttendanceRecord.objects.filter(makeup_plan_item__in=items).update(
        makeup_plan_item=None, updated_at=timezone.now()
    )


@transaction.atomic
def remove_item(item: MakeupPlanItem) -> None:
    """Sınavı takvimden çıkarır; kayıtları yeniden "mazeret sınavı bekleyen" olur."""
    _ensure_movable(item)
    _release_records([item])
    item.delete()


@transaction.atomic
def remove_plan(plan: MakeupPlan) -> None:
    _ensure_draft(plan)
    items = _live_items(plan)
    if any(live_item_session(i) is not None for i in items):
        raise ValidationError(
            "Bu takvimden mazeret oturumu üretilmiş; önce o oturumları silin (taslakken)."
        )
    _release_records(items)
    for item in items:
        item.delete()
    plan.delete()


# ---------------------------------------------------------------------------
# Denetim ve uyarılar
# ---------------------------------------------------------------------------
def _audit(plan: MakeupPlan) -> tuple[ms.Audit, dict[int, MakeupPlanItem], dict[int, str]]:
    items = _live_items(plan)
    kayitlar = _item_records(items)
    gruplar = {g.key: g for g in _groups(items, kayitlar)}
    yerlesik = [
        (gruplar[i.pk], (i.placed_date, int(i.period_no)))
        for i in items
        if i.pk in gruplar and i.placed_date is not None and i.period_no is not None
    ]
    numaralar = {
        int(k.student_id): k.student_number for ks in kayitlar.values() for k in ks if k.student_id
    }
    rapor = ms.audit(yerlesik, max_per_day=plan.max_per_day, strict_order=plan.strict_order)
    return rapor, {i.pk: i for i in items}, numaralar


def plan_errors(plan: MakeupPlan) -> list[str]:
    """ONAYI ENGELLEYEN kusurlar: aynı saatte iki sınava düşen öğrenci."""
    rapor, items, numaralar = _audit(plan)
    return [
        f"{_numbers(set(ogr), numaralar)} aynı saatte hem “{_item_label(items[a])}” hem "
        f"“{_item_label(items[b])}” sınavında görünüyor; sınavlardan birini başka saate taşıyın."
        for a, b, ogr in rapor.clashes
    ]


def plan_warnings(plan: MakeupPlan) -> list[str]:
    """Onayı ENGELLEMEYEN uyarılar — karar idarecinindir."""
    from apps.sinav.services_calendar import _tr_date

    rapor, items, numaralar = _audit(plan)
    uyarilar: list[str] = []
    if plan.max_per_day >= MAKEUP_MAX_PER_DAY:
        uyarilar.append(
            "Öğrenci başına günde 3 sınav yalnız zorunlu hâlde yapılabilir; zorunlu hâlin takdiri "
            "okul müdürlüğünündür (Yazılı ve Uygulamalı Sınavlar Yönergesi md. 5)."
        )
    for sid, gun, adet in rapor.over_limit:
        uyarilar.append(
            f"{_numbers({sid}, numaralar)}: {_tr_date(gun)} günü {adet} mazeret sınavı var "
            f"(belirlediğiniz günlük sınır {plan.max_per_day})."
        )
    for once, sonra in rapor.order_breaks:
        uyarilar.append(
            f"“{_item_label(items[once])}” asıl takvimde “{_item_label(items[sonra])}” sınavından "
            "önceydi, mazeret takviminde sonraya düştü."
        )
    gunler = sorted({i.placed_date for i in items.values() if i.placed_date is not None})
    donem = plan.semester
    disinda = [g for g in gunler if not donem.start_date <= g <= donem.end_date]
    if disinda:
        uyarilar.append(
            f"{_tr_date(disinda[0])} dönem dışında: mazeret sınavı için belirlenen süre, özrün "
            "ait olduğu dönemi aşamaz (Ortaöğretim Kurumları Yönetmeliği md. 48)."
        )
    if any(g.weekday() >= 5 for g in gunler):
        uyarilar.append("Takvimde hafta sonuna konmuş mazeret sınavı var.")
    olagan = ExamCalendar.objects.filter(semester_id=plan.semester_id)
    cakisan = [g for g in gunler if any(t.start_date <= g <= t.end_date for t in olagan)]
    if cakisan:
        uyarilar.append(
            f"{_tr_date(cakisan[0])} olağan sınav takviminin günleri içinde: öğrencinin o günkü "
            "olağan sınavları günlük sınıra DAHİL EDİLMEZ; gün seçimini gözden geçirin."
        )
    ust_makam = _blocked_days(plan)
    for i in items.values():
        if i.placed_date is not None and (i.placed_date, int(i.level)) in ust_makam:
            uyarilar.append(
                f"“{_item_label(i)}”: {_tr_date(i.placed_date)} günü bu sınıf düzeyinde üst makam "
                "sınavı var; o tarihte başka sınav yapılmaz (Yönerge md. 5)."
            )
    bekleyen = ExamAttendanceRecord.objects.filter(
        session__semester_id=plan.semester_id,
        session__deleted_at__isnull=True,
        session__is_makeup=False,
        excuse_status=ExcuseStatus.PENDING,
        student__isnull=False,
    ).count()
    if bekleyen:
        uyarilar.append(
            f"{bekleyen} kaydın mazeret kararı hâlâ “Beklemede”; mazereti sonradan kabul edilen "
            "öğrenci takvime kendiliğinden girmez — önce kararları tamamlayın."
        )
    return uyarilar


def unsynced_count(plan: MakeupPlan) -> int:
    """Takvim kurulduktan sonra "Mazeretli" olup hiçbir takvime alınmamış kayıt sayısı."""
    return len(_eligible_rows(plan.semester_id))


# ---------------------------------------------------------------------------
# Onay + oturum üretimi
# ---------------------------------------------------------------------------
@transaction.atomic
def approve_plan(plan: MakeupPlan, *, approved_by_name: str = "") -> MakeupPlan:
    from apps.sinav.services import _default_stamp_name

    _ensure_draft(plan)
    if not any(i.placed_date is not None for i in _live_items(plan)):
        raise ValidationError("Takvimde yerleştirilmiş sınav yok; onaylanacak bir şey bulunmuyor.")
    hatalar = plan_errors(plan)
    if hatalar:
        raise ValidationError(hatalar)
    plan.status = MakeupPlanStatus.APPROVED
    plan.approved_by_name = " ".join((approved_by_name or "").split()) or _default_stamp_name()
    plan.approved_at = timezone.now()
    plan.save(update_fields=["status", "approved_by_name", "approved_at", "updated_at"])
    return plan


@transaction.atomic
def reopen_plan(plan: MakeupPlan) -> MakeupPlan:
    if plan.status != MakeupPlanStatus.APPROVED:
        raise ValidationError("Yalnız onaylanmış mazeret takvimi yeniden açılabilir.")
    if any(live_item_session(i) is not None for i in _live_items(plan)):
        raise ValidationError(
            "Bu takvimden mazeret oturumu üretilmiş; takvim yeniden açılamaz. Değişiklik "
            "gerekiyorsa önce üretilen (taslak) oturumları silin."
        )
    plan.status = MakeupPlanStatus.DRAFT
    plan.approved_by_name, plan.approved_at = "", None
    plan.save(update_fields=["status", "approved_by_name", "approved_at", "updated_at"])
    return plan


def _period_info(period_no: int) -> tuple[str, time]:
    for p in _bell_periods():
        if int(p["no"]) == int(period_no):
            saat, dakika = str(p.get("start") or "09:00").split(":")[:2]
            return str(p.get("name") or f"{period_no}. Ders"), time(int(saat), int(dakika))
    return f"{period_no}. Ders", time(9, 0)


@transaction.atomic
def create_sessions(plan: MakeupPlan) -> dict[str, list[str]]:
    """Onaylı takvimin her sınav saati için TASLAK mazeret oturumu açar (idempotent).

    Aynı saatteki sınavlar TEK oturumda toplanır; çakışma denetimi o saatte aynı
    öğrencinin iki sınavı olmadığını zaten güvenceye almıştır. Oturumu üretilmiş ya da
    öğrencisi kalmamış kalem atlanır.
    """
    if plan.status != MakeupPlanStatus.APPROVED:
        raise ValidationError("Oturumlar yalnız ONAYLANMIŞ mazeret takviminden üretilir.")
    items = [i for i in _live_items(plan) if i.placed_date is not None and i.period_no is not None]
    kayitlar = _item_records(items)
    saatler: dict[tuple[date, int], list[MakeupPlanItem]] = {}
    for item in items:
        if live_item_session(item) is None and kayitlar[item.pk]:
            saatler.setdefault((item.placed_date, int(item.period_no)), []).append(item)  # type: ignore[arg-type]
    sonuc: dict[str, list[str]] = {"created": [], "skipped": []}
    for (gun, saat_no), kalemler in sorted(saatler.items()):
        saat_adi, baslangic = _period_info(saat_no)
        ad = f"{plan.name} — {gun.strftime('%d.%m.%Y')} {saat_adi}"[:120]
        oturum = services_makeup.create_makeup_session(
            record_ids=[k.pk for item in kalemler for k in kayitlar[item.pk]],
            name=ad,
            exam_date=gun,
            start_time=baslangic,
            from_plan=True,
        )
        for item in kalemler:
            item.session = oturum
            item.save(update_fields=["session", "updated_at"])
        sonuc["created"].append(ad)
    for item in items:
        if not kayitlar[item.pk]:
            sonuc["skipped"].append(f"{_item_label(item)}: mazeretli öğrencisi kalmadı.")
    return sonuc


# ---------------------------------------------------------------------------
# Arayüz ve belge verisi
# ---------------------------------------------------------------------------
def plan_payload(plan: MakeupPlan) -> dict[str, Any]:
    """Takvim ekranının tek verisi: parametreler, günler, saatler, sınavlar, uyarılar."""
    from apps.sinav.services_calendar import _TR_WEEKDAYS

    items = _live_items(plan)
    kayitlar = _item_records(items)
    saatler = effective_period_nos(plan)
    gunler = set(ms.plan_days(plan.start_date, plan.day_count))
    gunler |= {i.placed_date for i in items if i.placed_date is not None}
    kullanilan = set(saatler) | {int(i.period_no) for i in items if i.period_no is not None}
    sigmayan = [
        g
        for g in _groups(items, kayitlar)
        if g.fixed is None and g.auto and _item_by(items, g.key).placed_date is None
    ]
    en_az = None
    if sigmayan and plan.status == MakeupPlanStatus.DRAFT:
        en_az = ms.minimum_days(
            _groups(items, kayitlar),
            plan.start_date,
            saatler,
            max_per_day=plan.max_per_day,
            strict_order=plan.strict_order,
            blocked_days=_blocked_days(plan),
        )
    return {
        "id": plan.pk,
        "name": plan.name,
        "semester_id": plan.semester_id,
        "semester_label": str(plan.semester),
        "status": plan.status,
        "status_label": plan.get_status_display(),
        "start_date": plan.start_date.isoformat(),
        "day_count": plan.day_count,
        "max_per_day": plan.max_per_day,
        "period_nos": list(plan.period_nos or []),
        "strict_order": plan.strict_order,
        "approved_by_name": plan.approved_by_name,
        "approved_at": plan.approved_at.isoformat() if plan.approved_at else None,
        "days": [
            {"date": g.isoformat(), "weekday_label": _TR_WEEKDAYS[g.weekday()]}
            for g in sorted(gunler)
        ],
        "periods": [
            {
                "no": int(p["no"]),
                "name": str(p.get("name") or ""),
                "start": str(p.get("start") or ""),
            }
            for p in _bell_periods()
            if int(p["no"]) in kullanilan
        ],
        "all_periods": [
            {
                "no": int(p["no"]),
                "name": str(p.get("name") or ""),
                "start": str(p.get("start") or ""),
            }
            for p in _bell_periods()
        ],
        "items": [_item_payload(i, kayitlar[i.pk]) for i in items],
        "errors": plan_errors(plan),
        "warnings": plan_warnings(plan),
        "min_days": en_az,
        "unsynced_count": unsynced_count(plan) if plan.status == MakeupPlanStatus.DRAFT else 0,
    }


def _item_by(items: list[MakeupPlanItem], pk: int) -> MakeupPlanItem:
    return next(i for i in items if i.pk == pk)


def _item_payload(item: MakeupPlanItem, kayitlar: list[ExamAttendanceRecord]) -> dict[str, Any]:
    oturum = live_item_session(item)
    return {
        "id": item.pk,
        "course_id": item.course_id,
        "level": item.level,
        "course_label": _item_label(item),
        "source_date": item.source_date.isoformat(),
        "external": item.external,
        "placed_date": item.placed_date.isoformat() if item.placed_date else None,
        "period_no": item.period_no,
        "is_pinned": item.is_pinned,
        "note": item.note,
        "student_count": len(kayitlar),
        "students": [
            {
                "record_id": k.pk,
                "student_number": k.student_number,
                "full_name": k.full_name,
                "class_label": k.class_label,
            }
            for k in kayitlar
        ],
        "session_id": oturum.pk if oturum else None,
        "session_name": oturum.name if oturum else "",
        "session_status": oturum.status if oturum else None,
    }


def form_options(semester_id: int | None) -> dict[str, Any]:
    """Yeni takvim formunun verisi: ders saatleri, varsayılan sınav saatleri, bekleyen kayıt."""
    from apps.sinav.services_calendar import exam_period_numbers

    return {
        "all_periods": [
            {
                "no": int(p["no"]),
                "name": str(p.get("name") or ""),
                "start": str(p.get("start") or ""),
            }
            for p in _bell_periods()
        ],
        "default_period_nos": exam_period_numbers(),
        "eligible_count": len(_eligible_rows(semester_id)) if semester_id is not None else 0,
        "max_day_count": MAKEUP_MAX_DAY_COUNT,
    }


def plan_list(semester_id: int) -> list[dict[str, Any]]:
    """Dönemin mazeret takvimleri (özet) — en yenisi önce."""
    planlar = MakeupPlan.objects.filter(semester_id=semester_id).order_by("-start_date", "-id")
    return [
        {
            "id": p.pk,
            "name": p.name,
            "status": p.status,
            "status_label": p.get_status_display(),
            "start_date": p.start_date.isoformat(),
            "day_count": p.day_count,
        }
        for p in planlar
    ]


# ---------------------------------------------------------------------------
# Belgeler: adsız ilan nüshası + öğrenci listeli nüsha
# ---------------------------------------------------------------------------
PDF_KINDS = ("ilan", "liste")


def _pdf_context(plan: MakeupPlan, *, show_names: bool) -> dict[str, Any]:
    from apps.dersler import selectors as ders_selectors
    from apps.okul.models import SchoolConfig
    from apps.okul.normalize import tr_sort_key
    from apps.sinav.services_calendar import _tr_date
    from shared.letterhead import letterhead_context
    from shared.text import tr_upper

    config = SchoolConfig.load()
    items = [i for i in _live_items(plan) if i.placed_date is not None and i.period_no is not None]
    kayitlar = _item_records(items)
    items = [i for i in items if kayitlar[i.pk]]
    items.sort(key=lambda i: (i.placed_date, i.period_no, _item_label(i)))

    gun_satirlari: list[dict[str, Any]] = []
    for item in items:
        saat_adi, baslangic = _period_info(int(item.period_no or 0))
        gun_satirlari.append(
            {
                "date_label": _tr_date(item.placed_date),  # type: ignore[arg-type]
                "period_label": f"{saat_adi} · {baslangic.strftime('%H:%M')}",
                "course_label": _item_label(item),
                "external": item.external,
                "student_count": len(kayitlar[item.pk]),
                "source_date": item.source_date.strftime("%d.%m.%Y"),
            }
        )
    # Aynı günün ilk satırı günü taşır; sonrakiler boş bırakılır (takvim PDF'i deseni).
    onceki = ""
    for satir in gun_satirlari:
        satir["show_date"] = satir["date_label"] != onceki
        onceki = satir["date_label"]

    ogrenciler: dict[tuple[str, str, str], list[str]] = {}
    for item in items:
        saat_adi, baslangic = _period_info(int(item.period_no or 0))
        sinav = (
            f"{item.placed_date.strftime('%d.%m.%Y')} {baslangic.strftime('%H:%M')} · "  # type: ignore[union-attr]
            f"{_item_label(item)}"
        )
        for k in kayitlar[item.pk]:
            ogrenciler.setdefault((k.class_label, k.student_number, k.full_name), []).append(sinav)
    ogrenci_satirlari = [
        {"class_label": sube, "student_number": no, "full_name": ad, "exams": sinavlar}
        for (sube, no, ad), sinavlar in sorted(
            ogrenciler.items(), key=lambda kv: (_class_key(kv[0][0]), _number_key(kv[0][1]))
        )
    ]

    ders_adlari = ders_selectors.course_names_by_ids({i.course_id for i in items})
    zumreler = sorted(
        ({"name": "", "role": f"{ad} Zümre Başkanı"} for ad in set(ders_adlari.values())),
        key=lambda c: tr_sort_key(c["role"]),
    )
    return {
        **letterhead_context(
            school_name=config.school_name,
            unit="Okul Müdürlüğü",
            district=config.district,
            principal_name=config.principal_name,
        ),
        "plan": plan,
        "plan_title": tr_upper(plan.name),
        "year_label": str(plan.semester.school_year.name),
        "term_sequence": plan.semester.sequence,
        "day_rows": gun_satirlari,
        "student_rows": ogrenci_satirlari,
        "show_names": show_names,
        "max_per_day": plan.max_per_day,
        "chairs": zumreler,
        "principal_name": config.principal_name,
        "is_draft": plan.status != MakeupPlanStatus.APPROVED,
        "approved_on": (
            timezone.localtime(plan.approved_at).strftime("%d.%m.%Y")
            if plan.status == MakeupPlanStatus.APPROVED and plan.approved_at
            else ""
        ),
    }


def render_plan_pdf(plan: MakeupPlan, *, kind: str = "ilan", show_names: bool = True) -> Any:
    """`ilan`: adsız duyuru (tarih, saat, ders, öğrenci sayısı) · `liste`: öğrenci listeli nüsha."""
    from django.template.loader import render_to_string

    from apps.sinav.services import _PDF_MIME, ReportFile
    from shared.pdf import html_to_pdf

    if kind not in PDF_KINDS:
        raise ValidationError({"kind": "Belge türü ilan ya da liste olmalı."})
    sablon = "sinav/mazeret_takvimi.html" if kind == "ilan" else "sinav/mazeret_takvimi_liste.html"
    html = render_to_string(sablon, _pdf_context(plan, show_names=show_names))
    ek = "" if kind == "ilan" else ("_liste" if show_names else "_liste_adsiz")
    return ReportFile(
        filename=f"mazeret_takvimi_{plan.pk}{ek}.pdf",
        content_type=_PDF_MIME,
        content=html_to_pdf(html),
    )
