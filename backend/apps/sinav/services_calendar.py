"""Sınav takvimi iş mantığı — pencere/CRUD/onay/yerleştirme/doğrulama/grid (F6).

OYS `services_calendar.py`'den UYARLA (tasarım §11: "çekirdek aynen; onay
tek-kullanıcı; bildirim dalı silinir"). View katmanı yalnız bu modülü çağırır.
KS kesimleri:
- `_notify_calendar_event` + çağrıları KESİLDİ (B4 — snackbar yeter).
- Zümre imza köprüsü UYARLANDI (B7 revizyonu): zümre yapısı okul app'inde
  (`okul.SubjectDepartment`) ve takvim başına seçilir; seçim yoksa OYS'nin
  "modül yoksa" dalı (derslerden boş imza çizgileri) yedek yol olarak durur.
- Tatil/kapalı-gün uyarısı KESİLDİ (DD Holiday motoru ALMA) — hafta sonu
  uyarısı durur; `place_entry` imzası değişmedi.
- Zil çizelgesi köprüsü (B6 SADELEŞTİR): `SchoolConfig.bell_schedule` +
  `DEFAULT_BELL_SCHEDULE` — öğe şekli OYS ile birebir {no, name, start}.
- `created_by`/`by_user` parametreleri düştü (B17); onay damgası ad-snapshot
  (`approved_by_name` + zaman — B12/risk #10, ExamSession emsali).
"""

from __future__ import annotations

import calendar as _calmod
from dataclasses import dataclass, field
from datetime import date, time, timedelta
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.okul import selectors as okul_selectors
from apps.okul.models import SchoolConfig
from apps.sinav.models import (
    ExamAuthority,
    ExamCalendar,
    ExamCalendarEntry,
    ExamCalendarStatus,
    ExamKind,
    ExamSession,
    ExamTrackItem,
    ExamTrackMark,
    ExamTrackMarkStatus,
    ParticipantType,
)

# Varsayılan açıklama metni (PDF bunu basar; create sırasında kopyalanır).
# "AÇIKLAMALAR" başlığı metnin İÇİNDE DEĞİL: şablon bölüm başlığını kendisi basar
# (`calendar_pdf.html` section-title) — metne de yazılırsa başlık iki kez çıkardı.
DEFAULT_CALENDAR_DESCRIPTION = (
    "1. Ortak yazılı sınavlar, zümrelerce ilan edilen Konu Soru Dağılım (KSD) "
    "tablolarına uygun olarak hazırlanır ve okul genelinde ortak yapılır (MEB Ölçme "
    "ve Değerlendirme Yönetmeliği md. 5; Yazılı ve Uygulamalı Sınavlar Yönergesi md. 5).\n"
    "2. Ülke, il veya ilçe geneli ortak yazılı sınav yapılacağı duyurulan derslerde ve "
    "tarihlerde okul geneli ayrıca sınav yapılmaz; bu takvim gerektiğinde ilgili "
    "duyurulara göre güncellenir.\n"
    "3. Bir sınıfta bir günde yapılacak yazılı ve uygulamalı sınav sayısının ikiyi "
    "geçmemesi esastır; zorunlu hâllerde bir sınav daha yapılabilir (Ölçme ve "
    "Değerlendirme Yönetmeliği md. 5).\n"
    "4. Sınava katılamayan öğrencilerin özür belgeleri, sınav tarihinden itibaren en geç "
    "5 iş günü içinde velisi tarafından okul yönetimine yazılı olarak bildirilir "
    "(Ortaöğretim Kurumları Yönetmeliği md. 48). Özrü uygun görülen öğrenciler, ders "
    "zümresince belirlenen ve önceden duyurulan tarihte bir defaya mahsus mazeret "
    "sınavına alınır.\n"
    "5. Geçerli özrü olmadan sınava katılmayan öğrencinin durumu puanla değerlendirilmez; "
    "e-Okul'a 'G' olarak işlenir ve dönem puanı ortalaması hesabına katılır (OKY md. 48).\n"
    "6. Sınav tarihinde raporlu veya izinli olan öğrenci sınava alınmaz (OKY md. 48).\n"
    "7. Sınav sonuçları, sınav tarihinden itibaren en geç 10 iş günü içinde öğrencilere "
    "duyurulur ve e-Okul sistemine işlenir (OKY md. 49).\n"
    "8. Sınav günü ve saatlerinde gerekli tedbirler okul müdürlüğünce alınır; takvimde "
    "zorunlu değişiklikler ilgili mevzuat çerçevesinde ayrıca duyurulur."
)

# Varsayılan dipnot — takvim tablosunun altına, açıklamalardan sonra basılır ve
# kullanıcı tarafından düzenlenebilir. AÇIKLAMALAR maddeleriyle çakışmasın diye
# yalnız MAZERET TAKVİMİNİ ve okul dışı makam sınavlarının saatini söyler.
# "İzleyen hafta" bir mevzuat hükmü DEĞİL, okul müdürlüğünün takdiridir
# (Yönerge md. 5: okul geneli sınavların mazeret işlemleri okul müdürlüğünce
# yürütülür) — bu yüzden ona madde numarası bağlanmaz.
DEFAULT_CALENDAR_FOOTNOTE = (
    "Okulumuzda yapılan sınavların mazeret sınavları, bu sınav takvimini izleyen "
    "hafta içerisinde okul müdürlüğünce belirlenip duyurulan tarih ve saatlerde "
    "yapılır. Bakanlık ya da İl/İlçe Millî Eğitim Müdürlüğü tarafından yapılan "
    "sınavlar ile bunların mazeret sınavları, ilgili makamın kılavuzunda ilan "
    "edilen tarih ve saatlerde uygulanır (Yazılı ve Uygulamalı Sınavlar "
    "Yönergesi md. 5)."
)

# Dönem + tur → pencere başı ayı (Ölçme Yön. md. 5/1-ç).
# donem 1: R1 Ekim, R2 Aralık; donem 2: R1 Mart, R2 Mayıs. Yıl = semester.start_date.year.
_WINDOW_MONTH: dict[tuple[int, int], int] = {
    (1, 1): 10,
    (1, 2): 12,
    (2, 1): 3,
    (2, 2): 5,
}

#: B6 — zil çizelgesi köprüsünün KS karşılığı: SchoolConfig.bell_schedule boşsa
#: bu varsayılan kullanılır. Öğe şekli OYS sözleşmesiyle birebir (no/name/start).
DEFAULT_BELL_SCHEDULE: list[dict[str, Any]] = [
    {"no": i, "name": f"{i}. Ders", "start": start}
    for i, start in enumerate(
        ("08:30", "09:20", "10:10", "11:00", "11:50", "12:40", "13:30", "14:20"), start=1
    )
]


# --------------------------------------------------------------------------- #
# Statutory pencere + ön tanımlı takvim üretimi
# --------------------------------------------------------------------------- #


def _last_monday(year: int, month: int) -> date:
    """Verilen ay içindeki son Pazartesi."""
    last_day = _calmod.monthrange(year, month)[1]
    d = date(year, month, last_day)
    return d - timedelta(days=(d.weekday()))  # weekday() Pazartesi=0 → geriye kaydır


def _semester_donem(semester: Any) -> int:
    """Dönem sırası (1/2) — SchoolTerm.sequence; yoksa start_date ayına düşer."""
    seq = int(getattr(semester, "sequence", 0) or 0)
    if seq in (1, 2):
        return seq
    return 1 if semester.start_date.month >= 8 else 2


def statutory_window(semester: Any, round_: int) -> tuple[date, date]:
    """Dönem+tur için mevzuat sınav penceresi (Ölçme ve Değ. Yön. md. 5/1-ç).

    Başlangıç = ilgili ayın son Pazartesisi, bitiş = +11 gün (sonraki hafta Cuma —
    'ay son haftası + ay ilk haftası'); dönem tarihlerine kırpılır. Tur 3 için
    statutory pencere yoktur → dönemin son iki haftası döner (elle düzenlenir).
    """
    donem = _semester_donem(semester)
    year = semester.start_date.year
    month = _WINDOW_MONTH.get((donem, round_))
    if month is None:
        # Tur 3 (il zümre kararı) — dönemin son iki haftası.
        end = semester.end_date
        return (max(semester.start_date, end - timedelta(days=13)), end)
    start = _last_monday(year, month)
    end = start + timedelta(days=11)
    # Dönem sınırlarına kırp.
    start = max(start, semester.start_date)
    end = min(end, semester.end_date)
    if start > end:
        start = semester.start_date
        end = min(semester.end_date, start + timedelta(days=11))
    return (start, end)


def default_calendar_name(semester: Any, round_: int) -> str:
    donem = _semester_donem(semester)
    return f"{donem}. Dönem {round_}. Sınav Takvimi"


@transaction.atomic
def generate_default_calendars(*, school_year_id: int) -> list[ExamCalendar]:
    """Yılın dönemleri × 2 turu için ön tanımlı takvimleri üretir (idempotent)."""
    semesters = list(okul_selectors.school_terms(school_year_id=school_year_id))
    created: list[ExamCalendar] = []
    for semester in semesters:
        for round_ in (1, 2):
            if ExamCalendar.objects.filter(semester=semester, round=round_).exists():
                continue
            start, end = statutory_window(semester, round_)
            calendar = ExamCalendar.objects.create(
                semester=semester,
                round=round_,
                name=default_calendar_name(semester, round_),
                start_date=start,
                end_date=end,
                description_text=DEFAULT_CALENDAR_DESCRIPTION,
                footnote_text=DEFAULT_CALENDAR_FOOTNOTE,
            )
            # OYS D-P1: üretilen takvim havuzu DOLU gelir (yalnız round 1-2).
            # Tohumlama takvimi DÜŞÜREMEZ — `create_exam_calendar` ile aynı
            # sertlik: katalog boşsa/seviye eşleşmezse hata yutulur ve idareci
            # havuzu elle doldurur. İki yolun davranışı ayrışmamalı.
            _seed_pool(calendar)
            created.append(calendar)
    return created


def _seed_pool(calendar: ExamCalendar) -> None:
    """Yeni takvimin havuzunu ZORUNLU derslerle tohumlar (round 1-2; hata yutulur).

    Kendi savepoint'inde koşar: yutulan `ValidationError` dış işlemi kirletmez
    (Django atomic bloğunda yakalanan hata, savepoint geri alınmadan devam
    edilirse "broken transaction" üretirdi).
    """
    if calendar.round not in (1, 2):
        return
    try:
        with transaction.atomic():
            fill_calendar_pool(calendar)
    except ValidationError:
        # Tohumlama bir KOLAYLIKTIR; başarısızlığı takvim yaratmayı düşürmez.
        return


@transaction.atomic
def create_exam_calendar(
    *,
    semester_id: int,
    round: int,  # noqa: A002 — OYS API yüzeyi (gövde alanı adı)
    start_date: date,
    end_date: date,
    name: str | None = None,
) -> ExamCalendar:
    """Yeni sınav takvimi; 1. ve 2. turda havuz ZORUNLU derslerle tohumlanır.

    Kullanıcı geri bildirimi (31.08.2026): idareci takvimi yaratır yaratmaz
    zorunlu yazılı derslerin havuzda hazır olmasını bekliyor — tek tek ekleme
    "çok uzun sürüyor". Tohumlama `_seed_pool` ile ve HATA YUTULARAK yapılır:
    katalog boşsa ya da hiçbir seviye eşleşmiyorsa takvim yine yaratılır.
    3. turda tohumlama YOKTUR (havuzu elle doldurulur — `fill_calendar_pool`
    o turu zaten reddeder).
    """
    semester = okul_selectors.get_school_term(semester_id)
    if semester is None:
        raise ValidationError({"semester_id": "Dönem bulunamadı."})
    if round not in (1, 2, 3):
        raise ValidationError({"round": "Sınav turu 1-3 aralığında olmalı."})
    if start_date > end_date:
        raise ValidationError({"end_date": "Bitiş tarihi başlangıçtan önce olamaz."})
    if ExamCalendar.objects.filter(semester=semester, round=round).exists():
        raise ValidationError({"round": "Bu dönem ve tur için takvim zaten var."})
    created: ExamCalendar = ExamCalendar.objects.create(
        semester=semester,
        round=round,
        name=(name or default_calendar_name(semester, round)).strip(),
        start_date=start_date,
        end_date=end_date,
        description_text=DEFAULT_CALENDAR_DESCRIPTION,
        footnote_text=DEFAULT_CALENDAR_FOOTNOTE,
    )
    _seed_pool(created)
    return created


def _ensure_draft(calendar: ExamCalendar) -> None:
    if calendar.status != ExamCalendarStatus.DRAFT:
        raise ValidationError("Yalnız taslak durumundaki takvim düzenlenebilir.")


@transaction.atomic
def update_exam_calendar(
    calendar: ExamCalendar,
    *,
    name: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    description_text: str | None = None,
    footnote_text: str | None = None,
) -> ExamCalendar:
    _ensure_draft(calendar)
    if name is not None:
        calendar.name = name.strip()
    if start_date is not None:
        calendar.start_date = start_date
    if end_date is not None:
        calendar.end_date = end_date
    if calendar.start_date > calendar.end_date:
        raise ValidationError({"end_date": "Bitiş tarihi başlangıçtan önce olamaz."})
    if description_text is not None:
        calendar.description_text = description_text
    if footnote_text is not None:
        calendar.footnote_text = footnote_text
    calendar.save()
    return calendar


def remove_exam_calendar(calendar: ExamCalendar) -> None:
    _ensure_draft(calendar)
    # OYS Tur 644: girdi-düzeyi koruma takvim silme yolunda atlatılamaz —
    # CANLI oturuma bağlı girdisi olan takvim topluca silinemez.
    bound_session_ids = ExamCalendarEntry.objects.filter(
        calendar=calendar, session__isnull=False
    ).values_list("session_id", flat=True)
    if ExamSession.objects.filter(pk__in=list(bound_session_ids)).exists():
        raise ValidationError(
            "Oturumu üretilmiş girdileri olan takvim silinemez — önce oturumları kaldırın."
        )
    calendar.delete()


# --------------------------------------------------------------------------- #
# Onay akışı — tek kullanıcı (B12): SUBMITTED tek tıkla geçilir; APPROVED
# kilidi ve damgalar KORUNUR (risk #10). Bildirim dalı KESİLDİ (B4).
# --------------------------------------------------------------------------- #


def submit_calendar(calendar: ExamCalendar) -> ExamCalendar:
    if calendar.status != ExamCalendarStatus.DRAFT:
        raise ValidationError("Yalnız taslak takvim onaya sunulabilir.")
    calendar.status = ExamCalendarStatus.SUBMITTED
    calendar.submitted_at = timezone.now()
    calendar.save(update_fields=["status", "submitted_at", "updated_at"])
    return calendar


def approve_calendar(calendar: ExamCalendar, *, approved_by_name: str = "") -> ExamCalendar:
    from apps.sinav.services import _default_stamp_name

    if calendar.status != ExamCalendarStatus.SUBMITTED:
        raise ValidationError("Yalnız onaya sunulmuş takvim onaylanabilir.")
    calendar.status = ExamCalendarStatus.APPROVED
    calendar.approved_by_name = " ".join((approved_by_name or "").split()) or _default_stamp_name()
    calendar.approved_at = timezone.now()
    calendar.save(update_fields=["status", "approved_by_name", "approved_at", "updated_at"])
    return calendar


def reopen_calendar(calendar: ExamCalendar) -> ExamCalendar:
    """SUBMITTED|APPROVED → DRAFT. Üretilmiş oturumlara DOKUNMAZ (kendi yaşam
    döngüsü); damgaları SİLMEZ (tarihçe — OYS ile birebir)."""
    if calendar.status == ExamCalendarStatus.DRAFT:
        raise ValidationError("Takvim zaten taslak durumunda.")
    calendar.status = ExamCalendarStatus.DRAFT
    calendar.save(update_fields=["status", "updated_at"])
    return calendar


# --------------------------------------------------------------------------- #
# Havuz + yerleştirme
# --------------------------------------------------------------------------- #


@dataclass
class PlacementResult:
    entry: ExamCalendarEntry
    warnings: list[str] = field(default_factory=list)


def _validate_entry_participants(
    *, level: int, participant_type: str, section_ids: list[int] | None
) -> tuple[str, list[int]]:
    """Takvim girdisinin katılımcı kapsamını doğrular → (tip, temiz şube listesi).

    Emsal `services._validate_participant_refs`, ama YÖN TERSTİR: oturum
    dersinde seviye şubelerden TÜRETİLİR; takvim girdisinde `level` zorunlu
    alandır ve `(takvim, ders, seviye, tür)` teklik anahtarının parçasıdır —
    bu yüzden seviye GİRDİ, şubeler ona karşı denetlenir. Mesaj kalıbı oturum
    tarafıyla aynı tutuldu (idareci aynı cümleyi iki ekranda görsün).

    Canlılık denetimi bedavadır: `get_class_section` soft-delete süzgeçli
    manager'dan okur, silinmiş şube `None` döner. Şube kimlikleri sıra
    korunarak teklenir (`dict.fromkeys` — oturum tarafındaki desen).
    KÜME KİMLİĞİ BURAYA GİRMEZ (CLAUDE.md §3): arayüz kümeyi somut pk
    listesine açar; kayda yalnız şube pk'leri yazılır.
    """
    from apps.dersler.services import level_label

    if participant_type not in ParticipantType.values:
        raise ValidationError(
            {"participant_type": f"Geçersiz katılımcı tipi: {participant_type!r}."}
        )
    if participant_type == ParticipantType.LEVEL:
        # Seviye genelinde şube listesi ANLAMSIZDIR — sessizce temizlenir
        # (tip değiştirilince eski seçim artık kalmasın).
        return (ParticipantType.LEVEL, [])
    clean: list[int] = []
    for raw in section_ids or []:
        try:
            clean.append(int(raw))
        except (TypeError, ValueError):
            raise ValidationError({"section_ids": f"Geçersiz şube kimliği: {raw!r}."}) from None
    if not clean:
        raise ValidationError({"section_ids": "Şube bazlı atamada en az bir şube seçin."})
    for sid in clean:
        section = okul_selectors.get_class_section(sid)
        if section is None:
            raise ValidationError({"section_ids": f"Şube bulunamadı (id={sid})."})
        if int(section.class_level) != int(level):
            raise ValidationError(
                {
                    "section_ids": f"'{section.class_label}' şubesi {level_label(level)} "
                    "seviyesinde değil; her seviye için ayrı girdi ekleyin."
                }
            )
    return (ParticipantType.SECTIONS, list(dict.fromkeys(clean)))


def participant_scope_label(participant_type: str, section_ids: list[int] | None) -> str:
    """Kapsam rozeti metni — ızgara hücresi, havuz tablosu ve API AYNI metni basar."""
    if participant_type == ParticipantType.SECTIONS:
        return f"{len(section_ids or [])} şube"
    return str(ParticipantType.LEVEL.label)


@transaction.atomic
def add_calendar_entry(
    *,
    calendar: ExamCalendar,
    course_id: int,
    level: int,
    exam_kind: str = ExamKind.WRITTEN,
    is_butterfly: bool = True,
    authority: str = ExamAuthority.SCHOOL,
    participant_type: str = ParticipantType.LEVEL,
    section_ids: list[int] | None = None,
    note: str = "",
) -> ExamCalendarEntry:
    _ensure_draft(calendar)
    if exam_kind not in ExamKind.values:
        raise ValidationError({"exam_kind": "Geçersiz sınav türü."})
    if authority not in ExamAuthority.values:
        raise ValidationError({"authority": "Geçersiz hazırlayan makam."})
    # OYS Tur 644: ders + seviye uyumu HAVUZA EKLENİRKEN doğrulanır — uyumsuzluk
    # onay SONRASI oturum üretiminde patlayıp slotun tamamını engelliyordu.
    from apps.dersler import selectors as ders_selectors
    from apps.dersler.services import level_label

    course = ders_selectors.get_course(course_id, active_only=True)
    if course is None:
        raise ValidationError({"course_id": "Ders bulunamadı (veya pasif)."})
    if level not in course.levels:
        raise ValidationError(
            {
                "level": f"'{course.name}' dersi {level_label(level)} seviyesinde "
                "okutulmuyor (havuz tanımı)."
            }
        )
    # Kapsam doğrulaması ders+seviye uyumundan SONRA: "şube seviyede değil"
    # hatası ancak seviyenin kendisi geçerliyken anlamlıdır.
    ptype, sections = _validate_entry_participants(
        level=level, participant_type=participant_type, section_ids=section_ids
    )
    if ExamCalendarEntry.objects.filter(
        calendar=calendar, course_id=course_id, level=level, exam_kind=exam_kind
    ).exists():
        raise ValidationError({"course_id": "Bu ders + seviye + tür havuzda zaten var."})
    entry: ExamCalendarEntry = ExamCalendarEntry.objects.create(
        calendar=calendar,
        course_id=course_id,
        level=level,
        exam_kind=exam_kind,
        is_butterfly=is_butterfly,
        authority=authority,
        participant_type=ptype,
        section_ids=sections,
        note=note.strip(),
    )
    return entry


def _validation_text(exc: ValidationError) -> str:
    """ValidationError'dan tek satırlık Türkçe mesaj (skipped raporu için)."""
    if hasattr(exc, "message_dict"):
        messages = [m for values in exc.message_dict.values() for m in values]
    else:
        messages = list(exc.messages)
    return messages[0] if messages else "doğrulama hatası"


@transaction.atomic
def fill_calendar_pool(calendar: ExamCalendar) -> dict[str, Any]:
    """Havuzu ZORUNLU + YAZILI derslerle doldurur (OYS Tur 647 / ADR-0044 k. 12).

    KS sapması (B6/B8): OYS kaynağı canlı ders programıydı; KS'de kaynak
    `dersler.selectors.taught_course_levels` — aktif katalog × (ders seviyeleri
    ∩ okul seviyeleri ∩ öğrencisi olan seviyeler). İdempotent: var olan
    (ders, seviye, YAZILI) `existed`'a düşer; reddedilen çift SESSİZCE
    DÜŞÜRÜLMEZ — `skipped`'a nedeniyle yazılır. Round 3 havuzu ELLE doldurulur.

    SAPMA (31.08.2026 kullanıcı geri bildirimi): kaynak artık kataloğun
    TAMAMI DEĞİL, yalnız ZORUNLU (`CourseType.COMMON`) ve YAZILI
    (`CourseExamMode.WRITTEN`) derslerdir. Anadolu Lisesi kataloğunda 19 ortak
    + 45 seçmeli satır seviyelere açılınca ~175 havuz girdisi oluşuyor, idareci
    gerçekte sınav yapılacak ~30 tanesi kalana dek satırları tek tek siliyordu.
    Seçmeli dersler artık `elective_pool_options` + `add_calendar_entries_bulk`
    ile SEÇİLEREK eklenir; uygulama sınavı yapılan (Beden/Görsel/Müzik/Spor)
    ve sınavı olmayan (Rehberlik) dersler ise `exam_mode` sayesinde havuza hiç
    girmez. Kenar durumlar (uygulama sınavı, kelebek-değil, üst makam sınavı)
    elle ekleme formunda durur. Dönüş sözlüğünün ŞEKLİ DEĞİŞMEDİ.
    """
    from apps.dersler import selectors as ders_selectors
    from apps.dersler.models import CourseExamMode, CourseType

    _ensure_draft(calendar)
    if calendar.round == 3:
        raise ValidationError(
            "3. sınav takviminin havuzu elle doldurulur — otomatik doldurma yalnız "
            "1. ve 2. ortak sınav takvimlerinde geçerlidir."
        )
    pairs = ders_selectors.taught_course_levels(
        calendar.semester.school_year_id,
        course_types=[CourseType.COMMON],
        exam_modes=[CourseExamMode.WRITTEN],
    )
    live_pairs = set(
        ExamCalendarEntry.objects.filter(calendar=calendar, exam_kind=ExamKind.WRITTEN).values_list(
            "course_id", "level"
        )
    )
    created: list[str] = []
    existed: list[str] = []
    skipped: list[str] = []
    for pair in pairs:
        label = f"{pair.course_name} — {_level_display(pair.level)}"
        if (pair.course_id, pair.level) in live_pairs:
            existed.append(label)
            continue
        try:
            # add_calendar_entry iç içe atomic (savepoint) — tek çiftin reddi
            # koşunun kalanını geri almaz; varsayılanlar YAZILI + kelebek.
            add_calendar_entry(calendar=calendar, course_id=pair.course_id, level=pair.level)
        except ValidationError as exc:
            skipped.append(f"{label} ({_validation_text(exc)})")
            continue
        created.append(label)
    return {
        "created": created,
        "existed": existed,
        "skipped": skipped,
        "total_pairs": len(pairs),
    }


def _bulk_item_int(item: dict[str, Any], key: str) -> int | None:
    """Toplu ekleme kaleminden tam sayı alan (bozuksa None — kalem skipped'a düşer)."""
    try:
        return int(item[key])
    except (KeyError, TypeError, ValueError):
        return None


@transaction.atomic
def add_calendar_entries_bulk(
    calendar: ExamCalendar, items: list[dict[str, Any]]
) -> dict[str, list[str]]:
    """Havuza TOPLU girdi ekler (seçmeli ders seçim diyaloğunun tek çağrısı).

    Kalem şekli: `{"course_id", "level", "participant_type", "section_ids",
    "exam_kind", "is_butterfly", "authority"}` — `course_id` ve `level` dışı
    hepsi isteğe bağlıdır (varsayılanlar `add_calendar_entry` ile aynı).

    İdempotent: havuzda ZATEN OLAN (ders, seviye, tür) `existed`'a düşer, hata
    üretmez — diyalog yeniden kaydedilince kullanıcı hata görmemeli. Her kalem
    `add_calendar_entry`'nin İÇ İÇE ATOMIC'i (savepoint) içinde koşar: bir
    kalemin reddi koşunun kalanını geri almaz. Reddedilen kalem SESSİZCE
    DÜŞMEZ — `skipped`'a nedeniyle yazılır (`fill_calendar_pool` emsali) ve
    arayüz sonucu snackbar'da özetler.
    """
    from apps.dersler import selectors as ders_selectors

    _ensure_draft(calendar)
    created: list[str] = []
    existed: list[str] = []
    skipped: list[str] = []
    for item in items:
        course_id = _bulk_item_int(item, "course_id")
        level = _bulk_item_int(item, "level")
        if course_id is None or level is None:
            skipped.append(f"{item!r} (ders ve seviye zorunlu)")
            continue
        exam_kind = str(item.get("exam_kind") or ExamKind.WRITTEN)
        course = ders_selectors.get_course(course_id, active_only=True)
        # Etiket ders adından gelir; ders yoksa kimlikle yazılır ki kullanıcı
        # hangi kalemin düştüğünü görebilsin.
        label = (
            f"{course.name} — {_level_display(level)}"
            if course is not None
            else f"Ders #{course_id} — {_level_display(level)}"
        )
        if ExamCalendarEntry.objects.filter(
            calendar=calendar, course_id=course_id, level=level, exam_kind=exam_kind
        ).exists():
            existed.append(label)
            continue
        try:
            add_calendar_entry(
                calendar=calendar,
                course_id=course_id,
                level=level,
                exam_kind=exam_kind,
                is_butterfly=bool(item.get("is_butterfly", True)),
                authority=str(item.get("authority") or ExamAuthority.SCHOOL),
                participant_type=str(item.get("participant_type") or ParticipantType.LEVEL),
                section_ids=item.get("section_ids"),
                note=str(item.get("note") or ""),
            )
        except ValidationError as exc:
            skipped.append(f"{label} ({_validation_text(exc)})")
            continue
        created.append(label)
    return {"created": created, "existed": existed, "skipped": skipped}


def elective_pool_options(calendar: ExamCalendar) -> list[dict[str, Any]]:
    """Seviye bazında seçilebilir SEÇMELİ (yazılı) dersler + havuzda mı bilgisi.

    `fill_calendar_pool` artık yalnız zorunlu dersleri basıyor; seçmeli dersler
    bu listeden SEÇİLEREK eklenir. Kaynak yine `taught_course_levels` (aktif
    katalog × okulda öğrencisi olan seviyeler), yalnız `ELECTIVE` + `WRITTEN`
    süzgeciyle. `in_pool` o takvimde CANLI YAZILI girdi olup olmadığıdır —
    diyalog o dersi işaretli + kilitli gösterir.

    Ders adları TÜRK ALFABESİ sırasındadır: `taught_course_levels` DB'den
    `order_by("name")` ile gelir ve SQLite karşılaştırması BINARY'dir
    (Ç/Ğ/İ/Ö/Ş/Ü 'Z'den sonraya düşer) — sıralama bu yüzden Python'da
    (`exam_rooms_sorted` emsali). Seviye görünüm etiketi ızgarayla AYNI
    yardımcıdan (`_level_display`) gelir.
    """
    from apps.dersler import selectors as ders_selectors
    from apps.dersler.models import CourseExamMode, CourseType
    from apps.okul.normalize import tr_sort_key

    pairs = ders_selectors.taught_course_levels(
        calendar.semester.school_year_id,
        course_types=[CourseType.ELECTIVE],
        exam_modes=[CourseExamMode.WRITTEN],
    )
    live_pairs = set(
        ExamCalendarEntry.objects.filter(calendar=calendar, exam_kind=ExamKind.WRITTEN).values_list(
            "course_id", "level"
        )
    )
    by_level: dict[int, list[dict[str, Any]]] = {}
    for pair in pairs:
        by_level.setdefault(pair.level, []).append(
            {
                "id": pair.course_id,
                "name": pair.course_name,
                "in_pool": (pair.course_id, pair.level) in live_pairs,
            }
        )
    return [
        {
            "value": level,
            "display_label": _level_display(level),
            "courses": sorted(courses, key=lambda c: tr_sort_key(str(c["name"]))),
        }
        for level, courses in sorted(by_level.items())
    ]


@transaction.atomic
def update_calendar_entry(
    entry: ExamCalendarEntry,
    *,
    is_butterfly: bool | None = None,
    exam_kind: str | None = None,
    authority: str | None = None,
    participant_type: str | None = None,
    section_ids: list[int] | None = None,
    note: str | None = None,
) -> ExamCalendarEntry:
    _ensure_draft(entry.calendar)
    if is_butterfly is not None:
        entry.is_butterfly = is_butterfly
    if exam_kind is not None:
        if exam_kind not in ExamKind.values:
            raise ValidationError({"exam_kind": "Geçersiz sınav türü."})
        # OYS Tur 644: tür değişimi unique-alive çakışmasını önceden yakalar
        # (500 yerine 400).
        if (
            exam_kind != entry.exam_kind
            and ExamCalendarEntry.objects.filter(
                calendar_id=entry.calendar_id,
                course_id=entry.course_id,
                level=entry.level,
                exam_kind=exam_kind,
            )
            .exclude(pk=entry.pk)
            .exists()
        ):
            raise ValidationError({"exam_kind": "Bu ders + seviye + tür havuzda zaten var."})
        entry.exam_kind = exam_kind
    if authority is not None:
        if authority not in ExamAuthority.values:
            raise ValidationError({"authority": "Geçersiz hazırlayan makam."})
        entry.authority = authority
    # Kapsam ÇİFTİ birlikte doğrulanır: tip SECTIONS'a çevrilirken şube listesi
    # zorunlu olur, LEVEL'e dönerken eski liste temizlenir (services.py
    # `update_session_course`'un `fields.get(..., mevcut)` deseni).
    if participant_type is not None or section_ids is not None:
        entry.participant_type, entry.section_ids = _validate_entry_participants(
            level=entry.level,
            participant_type=(
                participant_type if participant_type is not None else entry.participant_type
            ),
            section_ids=(section_ids if section_ids is not None else list(entry.section_ids or [])),
        )
    if note is not None:
        entry.note = note.strip()
    entry.save()
    return entry


def remove_calendar_entry(entry: ExamCalendarEntry) -> None:
    _ensure_draft(entry.calendar)
    if entry.session_id is not None:
        raise ValidationError("Oturumu üretilmiş girdi silinemez — önce oturumu kaldırın.")
    entry.delete()


def _bell_periods() -> list[dict[str, Any]]:
    """Ders saati listesi — SchoolConfig.bell_schedule; boşsa varsayılan (B6)."""
    raw = SchoolConfig.load().bell_schedule
    schedule = raw if isinstance(raw, list) and raw else DEFAULT_BELL_SCHEDULE
    return [dict(p) for p in schedule]


def _external_authority_clash(entry: ExamCalendarEntry, on_date: date) -> bool:
    """Aynı gün+seviyede OKUL sınavı ile ÜST MAKAM sınavı yan yana mı düşüyor?

    İki yön de uyarı üretir: okul sınavı üst makam gününe konursa da, üst makam
    sınavı okul sınavı olan güne konursa da (Yönerge md. 5 aynı yasağı anlatır).
    Yasağın konusu OKUL–ÜST MAKAM çiftidir: aynı güne iki üst makam sınavı
    düşmesi bu maddenin kapsamında DEĞİLDİR, uyarı üretmez (aksi hâlde
    `calendar_validation` kolu ile çelişirdi — orada koşul "kümede hem SCHOOL
    hem başka makam var").
    """
    same_day = ExamCalendarEntry.objects.filter(
        calendar=entry.calendar, level=entry.level, placed_date=on_date
    ).exclude(pk=entry.pk)
    if entry.authority == ExamAuthority.SCHOOL:
        return same_day.exclude(authority=ExamAuthority.SCHOOL).exists()
    return same_day.filter(authority=ExamAuthority.SCHOOL).exists()


@transaction.atomic
def place_entry(entry: ExamCalendarEntry, *, on_date: date, period_no: int) -> PlacementResult:
    """Girdiyi ızgaraya yerleştirir (tarih + ders saati). Doğrulama + uyarılar.

    KS kesimi: resmî/idari tatil uyarısı yok (kapalı-gün kaynağı taşınmadı);
    hafta sonu uyarısı durur.
    """
    _ensure_draft(entry.calendar)
    # OYS Tur 644: CANLI oturuma bağlı girdi başka slota TAŞINAMAZ — aksi hâlde
    # takvim ile üretilmiş oturum sessizce ayrışır. (Bağlı oturumu soft-silinmiş
    # girdi taşınabilir — create_session_from_slot aday mantığıyla tutarlı.)
    if entry.session_id is not None and ExamSession.objects.filter(pk=entry.session_id).exists():
        raise ValidationError("Oturumu üretilmiş girdi taşınamaz — önce oturumu kaldırın.")
    warnings: list[str] = []

    periods = _bell_periods()
    valid_period_nos = {int(p["no"]) for p in periods}
    if valid_period_nos and period_no not in valid_period_nos:
        raise ValidationError({"period_no": "Ders saati listede tanımlı değil."})

    if not (entry.calendar.start_date <= on_date <= entry.calendar.end_date):
        warnings.append("Seçilen tarih takvim aralığı dışında.")

    if on_date.weekday() >= 5:
        warnings.append("Seçilen tarih hafta sonuna denk geliyor.")

    # Yönerge md. 5: ülke/il/ilçe geneli ortak yazılı sınavların yapılacağı
    # tarihlerde başka sınav yapılmaz. Sert kısıt DEĞİL (zorunlu hâl takdiri
    # okul müdürlüğünün) — üç kanallı uyarı desenine uyar.
    if _external_authority_clash(entry, on_date):
        warnings.append(
            "Bu gün ve seviyede Bakanlık/İl MEM/İlçe MEM sınavı var — üst makam "
            "sınavlarının yapılacağı tarihlerde okul geneli ayrıca sınav yapılmaz "
            "(Yazılı ve Uygulamalı Sınavlar Yönergesi md. 5)."
        )

    # Günlük sınav yükü ÖĞRENCİ bazlı (OYS Tur 648, ADR-0044 karar 13): kural
    # öğrencinin gireceği sınav sayısıdır (OKY md. 45 "bir sınıfta bir günde
    # ikiyi geçmemesi" esası).
    same_day_courses = list(
        ExamCalendarEntry.objects.filter(
            calendar=entry.calendar, level=entry.level, placed_date=on_date
        )
        .exclude(pk=entry.pk)
        .values_list("course_id", flat=True)
    )
    max_load, affected = _daily_exam_load(
        entry.calendar, entry.level, on_date, [*same_day_courses, entry.course_id]
    )
    if max_load == 3:
        detail = f" ({affected} öğrenci üç sınava giriyor)" if affected else ""
        warnings.append(
            f"Bu seviyede aynı gün 3. sınav{detail} — OKY md. 45: günde ikiyi "
            "geçmemesi esastır (zorunlu hâl gerekçesi okul müdürlüğünündür)."
        )
    elif max_load >= 4:
        raise ValidationError(
            {
                "on_date": "Yerleştirilemez: en az bir öğrenci aynı gün 4 sınava "
                "girmiş olurdu (OKY md. 45)."
            }
        )

    entry.placed_date = on_date
    entry.period_no = period_no
    entry.save(update_fields=["placed_date", "period_no", "updated_at"])
    return PlacementResult(entry=entry, warnings=warnings)


@transaction.atomic
def unplace_entry(entry: ExamCalendarEntry) -> ExamCalendarEntry:
    _ensure_draft(entry.calendar)
    if entry.session_id is not None:
        raise ValidationError("Oturumu üretilmiş girdi havuza geri alınamaz.")
    entry.placed_date = None
    entry.period_no = None
    entry.save(update_fields=["placed_date", "period_no", "updated_at"])
    return entry


# --------------------------------------------------------------------------- #
# Slot → kelebek oturum üretimi (OYS D4)
# --------------------------------------------------------------------------- #


def _period_start_time(period_no: int) -> time | None:
    """Ders saati listesinden başlangıç ('SS:DD' → time); yoksa None."""
    for p in _bell_periods():
        if int(p["no"]) == period_no:
            raw = str(p.get("start", "")).strip()
            if raw:
                parts = raw.split(":")
                return time(int(parts[0]), int(parts[1]))
    return None


def _live_section_ids(entry: ExamCalendarEntry) -> tuple[list[int], list[int]]:
    """Girdinin şube kapsamını canlı/kayıp diye ayırır → (canlı pk'ler, kayıp pk'ler).

    `section_ids` bir JSON listesidir; şube soft-silinince ne FK koruması ne de
    kayda yansıyan bir temizlik vardır (CLAUDE.md: soft-delete ileri-FK'da
    süzmez). `get_class_section` soft-delete süzgeçli manager'dan okur, silinmiş
    şube `None` döner — kayıp pk'ler ÇAĞIRANA bildirilir, sessizce yutulmaz.
    """
    canli: list[int] = []
    kayip: list[int] = []
    for raw in entry.section_ids or []:
        sid = int(raw)
        if okul_selectors.get_class_section(sid) is None:
            kayip.append(sid)
        else:
            canli.append(sid)
    return canli, kayip


@transaction.atomic
def create_session_from_slot(calendar: ExamCalendar, *, on_date: date, period_no: int) -> Any:
    """Onaylı takvim slotundan (tarih+ders saati) TASLAK kelebek ExamSession üretir.

    Adaylar = o slottaki is_butterfly=True girdilerden `session` bağı boş VEYA
    bağlı oturumu soft-silinmiş olanlar (yeniden üretilebilir). Oturum saati
    ders saati listesinden, dönem takvimden gelir; katılımcı seviyelerin şube
    derslikleri ön-seçilir. 'Kelebek Değil' girdiler DAHİL EDİLMEZ.
    """
    from apps.sinav import selectors, services

    if calendar.status != ExamCalendarStatus.APPROVED:
        raise ValidationError("Oturum yalnız ONAYLANMIŞ takvimden üretilebilir.")

    slot_entries = list(
        selectors.entries_for_slot(calendar.pk, on_date, period_no).filter(is_butterfly=True)
    )
    # Bağı boş VEYA soft-silinmiş oturuma bağlı olanlar (yeniden üretim).
    candidates = [
        e
        for e in slot_entries
        if e.session_id is None or not ExamSession.objects.filter(pk=e.session_id).exists()
    ]
    if not candidates:
        raise ValidationError(
            "Bu slotta oturum üretilecek (kelebek) girdi yok — hepsi zaten oturumlu."
        )

    # Kapsamı SİLİNMİŞ şubeye bakan girdi slotu KİLİTLEMEZ (31.08.2026 denetimi).
    # Şube pk'si JSON listede durur; şube soft-silinince FK koruması diye bir şey
    # yoktur ve onaylı takvimde girdi artık düzenlenemez (`_ensure_draft`) —
    # eskiden `add_session_course` "Şube bulunamadı (id=…)" atıp SLOTUN TAMAMINI
    # üretilemez yapıyordu (OYS Tur 644'ün kapattığı hata sınıfının onay sonrası
    # nüksü). Emsal `participants._resolve_sections` / `services._remap_sections`:
    # kayıp şube ATLANIR, kalanla devam edilir. Kapsamı tümüyle silinmiş girdi
    # oturuma alınmaz ve oturuma BAĞLANMAZ (şube geri açılınca yeniden üretilir);
    # sessiz düşmesin diye `calendar_validation` bunu kalıcı uyarı olarak basar.
    usable: list[tuple[ExamCalendarEntry, list[int] | None]] = []
    kapsamsiz: list[str] = []
    for entry in candidates:
        if entry.participant_type != ParticipantType.SECTIONS:
            usable.append((entry, None))
            continue
        canli, _kayip = _live_section_ids(entry)
        if not canli:
            kapsamsiz.append(f"{entry.course.name} — {_level_display(entry.level)}")
            continue
        usable.append((entry, canli))
    if not usable:
        raise ValidationError(
            "Bu slottaki girdilerin şube kapsamı silinmiş şubelere bakıyor "
            f"({', '.join(kapsamsiz)}) — şubeyi yeniden tanımlayın ya da takvimi "
            "taslağa alıp kapsamı düzeltin."
        )

    start_time = _period_start_time(period_no) or time(8, 0)
    # OYS Tur 644: birleşik ad model sınırını aşarsa takvim-adı parçası kırpılır.
    suffix = f" — {_tr_date(on_date)} {period_no}. Ders"
    max_len = int(ExamSession._meta.get_field("name").max_length or 120)
    base_name = calendar.name
    if len(base_name) + len(suffix) > max_len:
        base_name = base_name[: max_len - len(suffix) - 1].rstrip() + "…"
    session = services.create_exam_session(
        name=f"{base_name}{suffix}",
        exam_date=on_date,
        start_time=start_time,
        term_id=calendar.semester_id,
    )
    levels: set[int] = set()
    for entry, sections in usable:
        # Katılımcı KAPSAMI takvimden oturuma AYNEN taşınır (eskiden "LEVEL"
        # sabitti): seçmeli ders havuzda şube şube seçilmişse üretilen oturum
        # dersi de yalnız o şubeleri kapsar, yoksa idareci aynı seçimi her slot
        # üretiminde yeniden yapardı. `sections` LEVEL kapsamda None'dır —
        # `add_session_course` o dalda zaten [] yazar.
        services.add_session_course(
            session,
            course_id=entry.course_id,
            participant_type=entry.participant_type,
            level=entry.level,
            section_ids=sections,
        )
        levels.add(entry.level)

    # Salon ön seçimi: katılımcı seviyelerin şube derslikleri (F3 selector'ı).
    # ŞUBE kapsamlı girdide de seviyenin TÜM şube derslikleri ön-seçilir —
    # bilinçli karar (31.08.2026): ön seçim bir kolaylıktır, sihirbazda elle
    # daraltılır; kapsama göre daraltmak aynı slotta seviye geneli BAŞKA bir
    # ders varsa onun salonlarını düşürürdü.
    rooms = selectors.section_rooms_for_levels(levels)
    if rooms:
        services.set_session_rooms(session, [{"room_id": r.pk} for r in rooms])

    # Girdileri oturuma bağla (kapsamı silinmiş girdi BAĞLANMAZ — düzeltilince
    # aynı slottan yeniden üretilebilsin).
    ExamCalendarEntry.objects.filter(pk__in=[e.pk for e, _ in usable]).update(session=session)
    return session


# --------------------------------------------------------------------------- #
# Doğrulama + ızgara + katılımcı önizleme
# --------------------------------------------------------------------------- #


def calendar_validation(calendar: ExamCalendar) -> dict[str, list[str]]:
    """Takvim geneli doğrulama — errors (bloklayıcı) + warnings (uyarı)."""
    errors: list[str] = []
    warnings: list[str] = []
    periods = _bell_periods()
    valid_period_nos = {int(p["no"]) for p in periods}

    # Kapsamı silinmiş şubeye bakan girdi: yerleştirilmiş olsun ya da olmasın
    # uyarılır. Kaynağı önizleme DEĞİL doğrulamadır, çünkü önizlemenin uyarı
    # kanalı yok — `_section_scope_groups` kayıp şubeyi atlayıp sayıyı sessizce
    # küçültür, idareci "0 öğrenci"yi ancak burada görebilir. Onay SONRASI
    # silinen şube oturum üretiminden düşürüldüğü için (bkz.
    # `create_session_from_slot`) tek görünür iz bu satırdır.
    for entry in ExamCalendarEntry.objects.filter(
        calendar=calendar, participant_type=ParticipantType.SECTIONS
    ).select_related("course"):
        _, kayip = _live_section_ids(entry)
        if kayip:
            warnings.append(
                f"{entry.course.name} — {_level_display(entry.level)}: kapsamdaki "
                f"{len(kayip)} şube silinmiş (id={', '.join(str(s) for s in kayip)}); "
                "kapsamı düzeltin, o şubeler sınava alınmaz."
            )

    placed = ExamCalendarEntry.objects.filter(calendar=calendar, placed_date__isnull=False)
    # Seviye + gün başına ders listesi (öğrenci-bazlı yük için).
    per_day: dict[tuple[int, date], list[int]] = {}
    # Seviye + gün başına makam kümesi (Yönerge md. 5 — üst makam günü çakışması).
    authorities_per_day: dict[tuple[int, date], set[str]] = {}
    for e in placed:
        if valid_period_nos and e.period_no not in valid_period_nos:
            errors.append(f"Girdi #{e.pk}: ders saati listede yok.")
        if e.placed_date is not None and not (
            calendar.start_date <= e.placed_date <= calendar.end_date
        ):
            warnings.append(f"Girdi #{e.pk}: tarih takvim aralığı dışında.")
        if e.placed_date is not None:
            per_day.setdefault((e.level, e.placed_date), []).append(e.course_id)
            authorities_per_day.setdefault((e.level, e.placed_date), set()).add(e.authority)
    for (level, day), makamlar in sorted(
        authorities_per_day.items(), key=lambda kv: (kv[0][1], kv[0][0])
    ):
        if ExamAuthority.SCHOOL in makamlar and len(makamlar) > 1:
            warnings.append(
                f"{_level_display(level)} {day}: aynı güne hem okul hem üst makam "
                "sınavı yerleştirilmiş — üst makam sınav günlerinde okul geneli "
                "ayrıca sınav yapılmaz (Yazılı ve Uygulamalı Sınavlar Yönergesi md. 5)."
            )
    for (level, day), course_ids in per_day.items():
        max_load, affected = _daily_exam_load(calendar, level, day, course_ids)
        if max_load == 3:
            detail = f" ({affected} öğrenci)" if affected else ""
            warnings.append(
                f"{_level_display(level)} {day}: bir öğrenciye aynı gün 3 sınav"
                f"{detail} — mevzuat esası 2."
            )
        elif max_load >= 4:
            errors.append(
                f"{_level_display(level)} {day}: bir öğrenciye aynı gün {max_load} sınav "
                "— üst sınır aşıldı."
            )
    return {"errors": errors, "warnings": warnings}


def _level_display(level: int) -> str:
    """Seviye görüntü metni: '9. Sınıf' / 'Hazırlık' — TEK KAYNAK.

    Havuz etiketleri, doğrulama uyarıları, seçmeli seçim listesi ve ızgara
    sütun başlığı AYNI metni basmak zorundadır. `level_label` zaten
    "9. Sınıf"/"Hazırlık" üretiyor; buradaki eski `f"{label}. sınıf"` dalı ÖLÜ
    KODDU (label hiçbir zaman salt rakam değil) ve `calendar_grid` aynı sonucu
    AYRI bir inline ifadeyle türetiyordu — iki kaynak sürüklenmesin diye ikisi
    de buraya bağlandı (çıktı birebir aynı kaldı).
    """
    from apps.dersler.services import level_label

    return level_label(level)


def _daily_exam_load(
    calendar: ExamCalendar, level: int, on_date: date, course_ids: list[int]
) -> tuple[int, int]:
    """Aynı gün + seviyedeki derslerde ÖĞRENCİ başına en yüksek sınav yükü.

    Dönüş (max_yuk, etkilenen): etkilenen = en yüksek yüke ulaşan öğrenci sayısı.
    KAYIT VERİSİ OLMAYAN ders seviyenin TAMAMINI kapsar sayılır (konservatif —
    ADR-0044 karar 13; risk #4: GEVŞETİLEMEZ). KS v1'de ders kayıt verisi hiç
    olmadığından `course_level_student_ids` hep boş döner → yük fiilen o günkü
    ders sayısıdır; algoritma OYS ile birebir korunur (veri gelirse dolar).

    DEĞİŞMEZ — takvim girdisine ŞUBE KAPSAMI (`section_ids`) gelmesi bu hesabı
    GEVŞETMEZ: kapsam verisi "hangi şubeler sınava girer"i söyler, "hangi
    ÖĞRENCİ o derse kayıtlı"yı değil. Seçmeli dersin kapsamı 9/A ile 9/B olsa
    bile o şubelerdeki her öğrencinin dersi seçtiği bilinmez; yükü şube
    kesişimine indirmek, aynı gün üç sınava giren öğrenciyi görünmez kılardı.
    Ders kayıt verisi geldiğinde dolacak yer `course_level_student_ids`'tir —
    burası değil (ADR-0044 karar 13, risk #4).
    """
    from apps.dersler import selectors as ders_selectors

    if not course_ids:
        return (0, 0)
    full_cover = 0  # kayıt verisi olmayan dersler — herkesin yüküne eklenir
    counts: dict[int, int] = {}
    for course_id in course_ids:
        ids = ders_selectors.course_level_student_ids(
            course_id=course_id,
            level=level,
            school_year_id=calendar.semester.school_year_id,
            on_date=on_date,
        )
        if not ids:
            full_cover += 1
            continue
        for sid in ids:
            counts[sid] = counts.get(sid, 0) + 1
    if not counts:
        return (full_cover, 0)  # hiç kayıt verisi yok → ders sayısı = ortak yük
    max_specific = max(counts.values())
    affected = sum(1 for v in counts.values() if v == max_specific)
    return (max_specific + full_cover, affected)


def _section_student_count(class_level: int, class_section: str) -> int:
    """Şubedeki AKTİF öğrenci SAYISI — okul köprüsü üzerinden, yalnız COUNT.

    `student_list` arama verilmediğinde QuerySet döndürür; `.count()` saf bir
    SQL COUNT'tur, roster belleğe alınmaz (veri minimizasyonu — şifreli ad
    alanları hiç çözülmez). `list` dalı yalnız arama sürümü içindir, buraya
    düşmez; mypy için yine de karşılanır.
    """
    rows = okul_selectors.student_list(
        class_level=class_level, class_section=class_section, only_active=True
    )
    return rows.count() if isinstance(rows, QuerySet) else len(rows)


def _section_scope_groups(entry: ExamCalendarEntry) -> list[tuple[str, int]] | None:
    """ŞUBE kapsamlı girdinin (etiket, sayı) kırılımı; kapsam yoksa None.

    Ders kayıt verisi HÂLÂ YOK (`course_level_student_ids` boş döner), ama
    kapsam artık girdinin KENDİ şube listesinde duruyor — önizleme onu sayar.
    Silinmiş/bulunamayan şube atlanır: `get_class_section` soft-delete
    süzgeçlidir ve önizlemenin uyarı kanalı yoktur (dipnot sayıyı gösterir).
    """
    if entry.participant_type != ParticipantType.SECTIONS or not entry.section_ids:
        return None
    groups: list[tuple[str, int]] = []
    for sid in entry.section_ids:
        section = okul_selectors.get_class_section(int(sid))
        if section is None:
            continue
        groups.append(
            (
                section.class_label,
                _section_student_count(section.class_level, section.class_section),
            )
        )
    return groups


def entry_participant_preview(calendar: ExamCalendar) -> dict[int, dict[str, Any]]:
    """entry_id → {student_count, groups:[label], whole} (ızgara dipnotu)."""
    from apps.dersler import selectors as ders_selectors

    on_date = calendar.start_date
    result: dict[int, dict[str, Any]] = {}
    for entry in ExamCalendarEntry.objects.filter(calendar=calendar).select_related("course"):
        sections = _section_scope_groups(entry)
        if sections is not None:
            # ŞUBE kapsamı: sayım girdinin şube listesinden gelir; `whole`
            # False'tur — "seviyenin tamamı" DEĞİL, seçilen şubelerdir.
            result[entry.pk] = {
                "student_count": sum(n for _, n in sections),
                "whole": False,
                "groups": [f"{label} ({n})" for label, n in sections],
            }
            continue
        groups = ders_selectors.course_level_coverage(
            course_id=entry.course_id,
            level=entry.level,
            school_year_id=calendar.semester.school_year_id,
            on_date=on_date,
        )
        total = sum(g.student_count for g in groups)
        whole = len(groups) == 1 and groups[0].whole_sections
        result[entry.pk] = {
            "student_count": total,
            "whole": whole,
            "groups": [g.label for g in groups],
        }
    return result


def _level_options() -> list[dict[str, Any]]:
    return [
        {"value": int(o["value"]), "label": str(o["label"])} for o in okul_selectors.grade_levels()
    ]


def calendar_grid(calendar: ExamCalendar) -> dict[str, Any]:
    """FE + PDF ortak ızgara: seviyeler × günler × hücreler + havuz + doğrulama."""
    periods = _bell_periods()
    period_by_no = {int(p["no"]): p for p in periods}

    # Seviye sütunları: seçilebilir seviyeler ∪ girdi seviyeleri.
    entries = list(ExamCalendarEntry.objects.filter(calendar=calendar).select_related("course"))
    entry_levels = {e.level for e in entries}
    level_opts = _level_options()
    known = {o["value"] for o in level_opts}
    for lvl in sorted(entry_levels - known):
        level_opts.append({"value": lvl, "label": str(lvl)})
    # Sayım-only selector (veri minimizasyonu — roster PII çekmez).
    roster_counts = okul_selectors.active_student_counts_by_level()
    levels = [
        {
            "value": o["value"],
            "label": o["label"],
            # Sütun başlığı için hazır görüntü etiketi — havuz etiketleriyle
            # AYNI yardımcıdan ("9. Sınıf" / "Hazırlık"); ayrı inline ifade
            # iki kaynağın sürüklenmesine yol açıyordu.
            "display_label": _level_display(int(o["value"])),
            "student_count": roster_counts.get(o["value"], 0),
        }
        for o in level_opts
    ]

    # Günler = aralık içindeki tüm günler (hafta sonu işaretli).
    days: list[dict[str, Any]] = []
    cur = calendar.start_date
    while cur <= calendar.end_date:
        days.append(
            {
                "date": cur.isoformat(),
                "is_weekend": cur.weekday() >= 5,
                "weekday": cur.weekday(),
            }
        )
        cur += timedelta(days=1)

    cells: dict[str, list[dict[str, Any]]] = {}
    unplaced: list[dict[str, Any]] = []
    for e in entries:
        cell = {
            "entry_id": e.pk,
            "course_id": e.course_id,
            "course_name": e.course.name,
            "level": e.level,
            "exam_kind": e.exam_kind,
            "is_butterfly": e.is_butterfly,
            "authority": e.authority,
            # Hücre anahtarı biçimi SABİTTİR (CLAUDE.md §3); sözlüğe alan
            # EKLENEBİLİR — havuz tablosu ve ızgara kapsamı buradan okur.
            "participant_type": e.participant_type,
            "section_ids": list(e.section_ids or []),
            "participant_label": participant_scope_label(e.participant_type, e.section_ids),
            "session_id": e.session_id,
            "note": e.note,
        }
        if e.placed_date is not None and e.period_no is not None:
            key = f"{e.placed_date.isoformat()}|{e.period_no}|{e.level}"
            cells.setdefault(key, []).append(cell)
        else:
            unplaced.append(cell)

    validation = calendar_validation(calendar)
    return {
        "calendar": {
            "id": calendar.pk,
            "name": calendar.name,
            "status": calendar.status,
            "start_date": calendar.start_date.isoformat(),
            "end_date": calendar.end_date.isoformat(),
        },
        "levels": levels,
        "periods": [
            {"no": int(p["no"]), "name": str(p.get("name", p["no"])), "start": p.get("start", "")}
            for p in periods
        ],
        "period_by_no": {str(k): v for k, v in period_by_no.items()},
        "days": days,
        "cells": cells,
        "unplaced": unplaced,
        "errors": validation["errors"],
        "warnings": validation["warnings"],
    }


# --------------------------------------------------------------------------- #
# Resmî PDF — imza bloğu takvime seçilen zümrelerden (B7 revizyonu)
# --------------------------------------------------------------------------- #

# Türkçe ay adları (WeasyPrint locale bağımsız — |date filtresi TR locale tuzağı).
_TR_MONTHS = (
    "",
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
)
_TR_WEEKDAYS = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")


def _tr_date(d: date) -> str:
    return f"{d.day} {_TR_MONTHS[d.month]} {d.year} {_TR_WEEKDAYS[d.weekday()]}"


def _chair_name(department: Any) -> str:
    """Zümre başkanının adı; kayıt SİLİNMİŞSE boş (evrakta noktalı çizgi).

    `head` ileri-FK erişimi `_base_manager` üzerinden (ve burada `select_related`
    JOIN'iyle) çözülür — ikisi de soft-delete süzgeci UYGULAMAZ. Personel silme
    soft-delete olduğundan (`services/persons.py`) `on_delete=PROTECT` hiç
    tetiklenmez; süzgeç bu yüzden burada elle konur, yoksa okuldan ayrılmış
    öğretmen resmî takvimde imzacı görünürdü.
    """
    head = department.head
    if head is None or head.deleted_at is not None:
        return ""
    return str(head.get_full_name())


def _calendar_signatures(calendar: ExamCalendar) -> dict[str, Any]:
    """İmza bloğu: takvime SEÇİLEN zümreler; seçim yoksa derslerden boş çizgiler.

    B7 revizyonu: OYS'de zümre modülü kuruluysa gerçek başkan adları basılırdı;
    KS'de zümre yapısı Ayarlar'da tanımlanır (`okul.SubjectDepartment`) ve
    takvim başına seçilir — seçilen zümrenin başkanı varsa adı basılır, yoksa
    noktalı çizgi kalır. Zümre seçilmemiş (ve eski) takvimlerde OYS'nin
    "modülsüz" dalı yedek yoldur: takvimdeki her dersten bir imza çizgisi.

    Başkan adı ŞİFRELİ alandan çözülür → sıralama DB'de değil, zümre adına göre
    Python'da (Türk alfabesi). Sözleşme: `{"chairs": [{"name", "role"}],
    "school_chair_name": str}` — şablon bu iki anahtarı tüketir.
    """
    from apps.okul.normalize import tr_sort_key

    departments = list(calendar.signatory_departments.select_related("head").all())
    if departments:
        departments.sort(key=lambda d: tr_sort_key(d.name))
        return {
            "chairs": [
                {"name": _chair_name(d), "role": f"{d.name} Zümre Başkanı"} for d in departments
            ],
            "school_chair_name": "",
        }

    from apps.dersler import selectors as ders_selectors

    course_ids = list(
        ExamCalendarEntry.objects.filter(calendar=calendar)
        .values_list("course_id", flat=True)
        .distinct()
    )
    course_names = ders_selectors.course_names_by_ids(set(course_ids))

    chairs: list[dict[str, str]] = [
        {"name": "", "role": f"{course_names.get(course_id, '')} Zümre Başkanı"}
        for course_id in course_ids
    ]
    chairs.sort(key=lambda c: tr_sort_key(c["role"]))
    return {"chairs": chairs, "school_chair_name": ""}


def _pdf_day_rows(grid: dict[str, Any]) -> list[dict[str, Any]]:
    """PDF gün satırları: sınav içeren her gün — HAFTA SONU DAHİL (OYS Tur 644).

    place_entry hafta sonuna yalnız UYARIYLA izin verir; hafta sonu atlansa
    yerleştirilmiş girdi resmî çıktıdan sessizce kaybolurdu. Boş günler
    (hafta sonu dahil) zaten satır üretmez.
    """
    day_rows: list[dict[str, Any]] = []
    for day in grid["days"]:
        d = date.fromisoformat(day["date"])
        period_cells: list[dict[str, Any]] = []
        for p in grid["periods"]:
            slot_cells = []
            for level in grid["levels"]:
                key = f"{day['date']}|{p['no']}|{level['value']}"
                slot_cells.append(grid["cells"].get(key, []))
            if any(slot_cells):
                period_cells.append({"period": p, "level_cells": slot_cells})
        if period_cells:
            day_rows.append({"label": _tr_date(d), "period_cells": period_cells})
    return day_rows


def render_calendar_pdf(calendar: ExamCalendar) -> bytes:
    """Resmî sınav takvimi PDF'i (WeasyPrint — documents/base.html; A4 YATAY)."""
    from django.template.loader import render_to_string
    from weasyprint import HTML

    from shared.letterhead import letterhead_context
    from shared.text import tr_upper

    config = SchoolConfig.load()
    grid = calendar_grid(calendar)
    day_rows = _pdf_day_rows(grid)
    signatures = _calendar_signatures(calendar)

    context = {
        **letterhead_context(
            school_name=config.school_name,
            unit="Okul Müdürlüğü",
            district=config.district,
            principal_name=config.principal_name,
        ),
        "calendar": calendar,
        "calendar_title": tr_upper(calendar.name),
        "levels": grid["levels"],
        "day_rows": day_rows,
        "description_lines": calendar.description_text.split("\n"),
        "footnote_lines": [ln for ln in calendar.footnote_text.split("\n") if ln.strip()],
        "chairs": signatures["chairs"],
        "school_chair_name": signatures["school_chair_name"],
        "principal_name": config.principal_name,
        "is_draft": calendar.status != ExamCalendarStatus.APPROVED,
        "generated_at": timezone.now(),
    }
    html = render_to_string("sinav/calendar_pdf.html", context)
    return bytes(HTML(string=html).write_pdf())


# --------------------------------------------------------------------------- #
# Süreç takip kalemleri + matris
# --------------------------------------------------------------------------- #


@transaction.atomic
def create_track_item(
    *, name: str, description: str = "", order: int | None = None
) -> ExamTrackItem:
    name = name.strip()
    if not name:
        raise ValidationError({"name": "Kalem adı boş olamaz."})
    if ExamTrackItem.objects.filter(name=name).exists():
        raise ValidationError({"name": "Bu adla canlı bir kalem zaten var."})
    if order is None:
        last = ExamTrackItem.objects.order_by("-order").values_list("order", flat=True).first()
        order = (last or 0) + 10
    created: ExamTrackItem = ExamTrackItem.objects.create(
        name=name, description=description.strip(), order=order
    )
    return created


@transaction.atomic
def update_track_item(
    item: ExamTrackItem,
    *,
    name: str | None = None,
    description: str | None = None,
    is_active: bool | None = None,
) -> ExamTrackItem:
    if name is not None:
        name = name.strip()
        if not name:
            raise ValidationError({"name": "Kalem adı boş olamaz."})
        if ExamTrackItem.objects.filter(name=name).exclude(pk=item.pk).exists():
            raise ValidationError({"name": "Bu adla canlı bir kalem zaten var."})
        item.name = name
    if description is not None:
        item.description = description.strip()
    if is_active is not None:
        item.is_active = is_active
    item.save()
    return item


@transaction.atomic
def set_track_mark(
    *,
    entry: ExamCalendarEntry,
    item: ExamTrackItem,
    status: str | None,
    note: str | None = None,
    marked_by_name: str = "",
) -> ExamTrackMark | None:
    """İşaret upsert'i; status None → işareti kaldır (soft-delete).

    `note=None` → mevcut not KORUNUR (OYS Tur 644: FE durum döngüsü note
    göndermez; koşulsuz ezme kayıtlı notu siliyordu). Temizlemek için `note=""`.
    İşaretleyen ad-snapshot'ı boşsa yapılandırmadaki müdür adı basılır.
    """
    from apps.sinav.services import _default_stamp_name

    current: ExamTrackMark | None = ExamTrackMark.objects.filter(entry=entry, item=item).first()
    if status is None:
        if current is not None:
            current.delete()
        return None
    if status not in ExamTrackMarkStatus.values:
        raise ValidationError({"status": "Geçersiz durum."})
    stamp = " ".join((marked_by_name or "").split()) or _default_stamp_name()
    if current is None:
        created: ExamTrackMark = ExamTrackMark.objects.create(
            entry=entry,
            item=item,
            status=status,
            note=(note or "").strip(),
            marked_by_name=stamp,
            marked_at=timezone.now(),
        )
        return created
    current.status = status
    if note is not None:
        current.note = note.strip()
    current.marked_by_name = stamp
    current.marked_at = timezone.now()
    current.save(update_fields=["status", "note", "marked_by_name", "marked_at", "updated_at"])
    return current


def track_matrix(
    calendar: ExamCalendar, *, restrict_course_ids: set[int] | None = None
) -> dict[str, Any]:
    """Süreç takip matrisi: satır=girdi (ders+seviye), sütun=aktif kalem, hücre=işaret."""
    items = list(ExamTrackItem.objects.filter(is_active=True).order_by("order", "id"))
    entries = list(
        ExamCalendarEntry.objects.filter(calendar=calendar)
        .select_related("course")
        .order_by("course__name", "level", "exam_kind")
    )
    if restrict_course_ids is not None:
        entries = [e for e in entries if e.course_id in restrict_course_ids]
    entry_ids = [e.pk for e in entries]
    marks = ExamTrackMark.objects.filter(
        entry_id__in=entry_ids, item__is_active=True, item__deleted_at__isnull=True
    ).only("entry_id", "item_id", "status", "note", "marked_by_name", "marked_at")
    cell_map: dict[tuple[int, int], dict[str, Any]] = {}
    for m in marks:
        cell_map[(m.entry_id, m.item_id)] = {
            "item_id": m.item_id,
            "status": m.status,
            "note": m.note,
            "marked_by_name": m.marked_by_name,
            "marked_at": m.marked_at.isoformat(),
        }
    rows = [
        {
            "entry_id": e.pk,
            "course_name": e.course.name,
            "level": e.level,
            "exam_kind": e.exam_kind,
            "cells": [cell_map.get((e.pk, i.pk), {"item_id": i.pk, "status": None}) for i in items],
        }
        for e in entries
    ]
    return {
        "items": [
            {"id": i.pk, "name": i.name, "description": i.description, "order": i.order}
            for i in items
        ],
        "rows": rows,
    }
