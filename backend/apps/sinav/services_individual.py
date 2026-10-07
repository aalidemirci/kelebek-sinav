"""BEP kapsamındaki öğrenciler + bireysel soru dosyası (20.09.2026, kullanıcı isteği).

İstek: BEP kapsamındaki öğrencinin sınavı sisteme yüklensin ve kitapçığı ADINA
basılsın; hangi öğrenciye ayrı sınav uygulanacağını idareci seçsin; öğrenciyi
ayrıştıran hiçbir işaret ne yoklamaya ne kitapçığa basılsın. Dayanak: ÖDY
md. 4/1-ç, 5/1-n, 6/1-d · Yönerge md. 5/1-u · OKY md. 45/1-ğ · ÖDSHGM 10.09.2026
yazısı md. 8 ("sınavlarının, BEP'leri doğrultusunda ilgili sınıf/ders
öğretmenleri tarafından hazırlanması").

Kullanıcı kararları (20.09.2026):
1. KALICI liste (`IepStudent`, yalnız üyelik) + oturumda seçim
   (`IndividualQuestionDocument`; satırın varlığı seçimdir).
2. Uygulama parolası ZORUNLU DEĞİL — parola kapalıyken arayüz uyarır.
3. Basılı bilgi YALNIZ idare özetidir (`render_iep_summary`); salonlara giden
   hiçbir belge bu bilgiyi taşımaz, özet "Tümünü indir" paketine GİRMEZ.

KVKK (md. 6 — özel nitelikli veriye işaret eder):
- Öğrenci bağı şifreli metindir; teklik ve süzme burada, Python'da yapılır.
  Çözülemeyen bağ (kilitli kasa, yarım geçiş) ATLANIR — asla silinmez, asla
  çökertmez.
- Satırlar KATI silinir (soft-delete yok). Ayrılan/silinen öğrencinin kaydı
  `forget_student` ile anında, kaçan yollar için okumada `purge_stale` ile düşer.
- Günlük ve hata metinlerinde öğrenci kimliği (ad, okul no, pk) GEÇMEZ; yalnız
  sayı yazılır. Uçlar da öğrenci pk'sini YOLDA taşımaz (Django 4xx yanıtını yoluyla
  günlüğe yazar) — satır kimliği opaktır, öğrenci pk'si yalnız gövdede gelir.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import TYPE_CHECKING, Any

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.db import transaction
from django.utils import timezone

from apps.okul import selectors as okul_selectors
from apps.okul.models import Student, StudentStatus
from apps.sinav import question_pdf, reports
from apps.sinav.models import (
    MAX_EXTRA_MINUTES,
    AccommodationPlacement,
    ExamRoom,
    ExamSession,
    ExamSessionStatus,
    IepStudent,
    IndividualQuestionDocument,
    PlacementRule,
    RuleReason,
    RuleScope,
    RuleType,
    ScoreMode,
    SeatAssignment,
    SeatPreference,
)

if TYPE_CHECKING:
    from apps.sinav.services import ReportFile

logger = logging.getLogger("kelebek_sinav.sinav")

#: Bireysel dosyanın kitapçık sözlüğündeki anahtarı: "<grup anahtarı>#<satır pk>".
#: Çakışma grubu anahtarı ("<course_id>:<level>") DEĞİŞMEZ — öğrenci aynı grupta
#: kalır; bu ek yalnız `booklet.build_room_package`in doküman sözlüğünde yaşar.
INDIVIDUAL_KEY_SEP = "#"

_EDITABLE_STATUSES: tuple[str, ...] = (ExamSessionStatus.DRAFT, ExamSessionStatus.DISTRIBUTED)

#: İdare özetinde ve panelde "hangi kitapçık basılacak" etiketleri. "Ortak"
#: sözcüğü BİLİNÇLE yok (MEB'de "ortak sınav" okul geneli sınavdır — sözlük).
PAPER_INDIVIDUAL = "Bireysel soru dosyası"
PAPER_PENDING = "Bireysel soru dosyası (dosya bekleniyor)"
PAPER_COURSE = "Dersin soru dosyası"


def _ref_id(ref: str | None) -> int | None:
    """Şifreli bağdan öğrenci pk'si; çözülemeyen/bozuk değer → None (satır atlanır)."""
    text = (ref or "").strip()
    return int(text) if text.isdigit() else None


# ---------------------------------------------------------------------------
# BEP kapsamındaki öğrenciler + kalıcı sınav tedbirleri (tek liste, 07.10.2026)
# ---------------------------------------------------------------------------
def accommodation_rows() -> dict[int, IepStudent]:
    """Öğrenci pk → listedeki satırı (BEP + tedbir). Çözülemeyen bağ atlanır; mükerrerde ilk kalır."""
    rows: dict[int, IepStudent] = {}
    for row in IepStudent.objects.select_related("target_room").order_by("pk"):
        student_id = _ref_id(row.student_ref)
        if student_id is not None:
            rows.setdefault(student_id, row)
    return rows


def iep_rows() -> dict[int, IepStudent]:
    """Öğrenci pk → BEP kaydı — YALNIZ gerekçesi BEP olan satırlar.

    BEP'e özgü işler (oturumdaki hatırlatma, bireysel soru dosyası) buradan
    beslenir: ÖDSHGM 10.09.2026 yazısı md. 8 BEP'li öğrenci içindir; sağlık ya da
    başka gerekçeli tedbir satırı bireysel soru dosyası açmaz.
    """
    return {
        student_id: row
        for student_id, row in accommodation_rows().items()
        if row.reason_category == RuleReason.IEP
    }


def iep_student_ids() -> set[int]:
    return set(iep_rows())


def measure_labels(row: IepStudent) -> list[str]:
    """Tedbirlerin kullanıcı dilindeki özeti — liste, oturum paneli ve idare özeti AYNI metni basar.

    Ön yüz kendi etiket kopyasını üretmez (bu liste uçta döner).
    """
    etiketler: list[str] = []
    if row.placement == AccommodationPlacement.HOME_CLASSROOM:
        etiketler.append("Kendi sınıfında")
    elif row.placement == AccommodationPlacement.SEPARATE_ROOM:
        salon = row.target_room.name if row.target_room is not None else "salon seçilmedi"
        etiketler.append(f"Ayrı salon ({salon})")
    elif row.placement == AccommodationPlacement.FRONT_ROW:
        etiketler.append("Ön sırada")
    if row.placement != AccommodationPlacement.FRONT_ROW:
        if row.seat_preference == SeatPreference.FRONT:
            etiketler.append("ön sıra")
        elif row.seat_preference == SeatPreference.BACK:
            etiketler.append("arka sıra")
    if row.solo_desk:
        etiketler.append("sırada tek başına")
    if row.extra_minutes:
        etiketler.append(f"Ek süre {row.extra_minutes} dk")
    if row.reader:
        etiketler.append("Okuyucu desteği")
    if row.scribe:
        etiketler.append("Yazıcı desteği")
    return etiketler


def has_measures(row: IepStudent) -> bool:
    return bool(
        row.placement != AccommodationPlacement.NONE
        or row.extra_minutes
        or row.reader
        or row.scribe
    )


def _list_item(row: IepStudent, student: Student) -> dict[str, Any]:
    return {
        "id": row.pk,
        "student_id": student.pk,
        "student_number": student.student_number,
        "full_name": student.full_name,
        "class_label": student.class_label,
        "reason_category": row.reason_category,
        "reason_label": RuleReason(row.reason_category).label,
        "placement": row.placement,
        "target_room_id": row.target_room_id,
        "seat_preference": row.seat_preference,
        "solo_desk": row.solo_desk,
        "extra_minutes": row.extra_minutes,
        "reader": row.reader,
        "scribe": row.scribe,
        "measures": measure_labels(row),
    }


def iep_list() -> list[dict[str, Any]]:
    """Liste ekranı satırları — sınıf/şube, sonra okul no sırasıyla (ad şifreli: TB3)."""
    purge_stale()
    rows = accommodation_rows()
    students = {s.pk: s for s in Student.objects.filter(pk__in=list(rows))}
    items = [_list_item(rows[student_id], student) for student_id, student in students.items()]
    items.sort(
        key=lambda item: (
            reports.class_label_sort_key(str(item["class_label"])),
            reports.student_number_sort_key(str(item["student_number"])),
        )
    )
    return items


def _clean_measures(data: dict[str, Any]) -> dict[str, Any]:
    """Tedbir alanlarını doğrular ve modele yazılacak sözlüğe çevirir.

    Kurallar yerleştirme kuralının sözleşmesidir (`create_placement_rule`): ayrı
    salon hedef salon ister, başka yer salon almaz; salon içi tercih yalnız kendi
    sınıfında / ayrı salonda anlamlıdır; "tek başına" bir yer kuralı ister. BEP
    dışındaki gerekçede en az bir tedbir şarttır — tedbirsiz satır yalnız BEP
    üyeliği olarak anlamlıdır. Hata metni öğrenci kimliği taşımaz.
    """
    reason = str(data.get("reason_category") or RuleReason.IEP)
    if reason not in RuleReason.values:
        raise ValidationError("Geçersiz gerekçe.")
    placement = str(data.get("placement") or AccommodationPlacement.NONE)
    if placement not in AccommodationPlacement.values:
        raise ValidationError("Geçersiz yer seçimi.")
    seat_preference = str(data.get("seat_preference") or SeatPreference.NONE)
    if seat_preference not in SeatPreference.values:
        raise ValidationError("Geçersiz salon içi tercih.")
    solo = bool(data.get("solo_desk", False))
    reader = bool(data.get("reader", False))
    scribe = bool(data.get("scribe", False))
    raw_minutes = data.get("extra_minutes", 0)
    if isinstance(raw_minutes, bool) or not isinstance(raw_minutes, int):
        raise ValidationError("Ek süre dakika olarak tam sayı olmalı.")
    if not 0 <= raw_minutes <= MAX_EXTRA_MINUTES:
        raise ValidationError(f"Ek süre 0 ile {MAX_EXTRA_MINUTES} dakika arasında olmalı.")

    target_room: ExamRoom | None = None
    room_id = data.get("target_room_id")
    if placement == AccommodationPlacement.SEPARATE_ROOM:
        if isinstance(room_id, bool) or not isinstance(room_id, int):
            raise ValidationError("“Ayrı salon” için salon seçin.")
        target_room = ExamRoom.objects.filter(pk=room_id, is_active=True).first()
        if target_room is None:
            raise ValidationError("Seçilen salon bulunamadı ya da pasif.")
    elif room_id is not None:
        raise ValidationError("Salon yalnız “Ayrı salon” seçildiğinde verilir.")
    if seat_preference != SeatPreference.NONE and placement not in (
        AccommodationPlacement.HOME_CLASSROOM,
        AccommodationPlacement.SEPARATE_ROOM,
    ):
        raise ValidationError(
            "Salon içinde ön/arka tercihi yalnız “Kendi sınıfında” ya da “Ayrı salon” ile seçilir."
        )
    if solo and placement == AccommodationPlacement.NONE:
        raise ValidationError(
            "“Sırada tek başına” için bir yer seçin (kendi sınıfında, ayrı salon ya da ön sırada)."
        )
    cleaned: dict[str, Any] = {
        "reason_category": reason,
        "placement": placement,
        "target_room": target_room,
        "seat_preference": seat_preference,
        "solo_desk": solo,
        "extra_minutes": raw_minutes,
        "reader": reader,
        "scribe": scribe,
    }
    if reason != RuleReason.IEP and not (
        placement != AccommodationPlacement.NONE or raw_minutes or reader or scribe
    ):
        raise ValidationError(
            "BEP dışındaki gerekçede en az bir tedbir seçin (yer, ek süre ya da destek)."
        )
    return cleaned


@transaction.atomic
def add_iep_student(student_id: int, measures: dict[str, Any] | None = None) -> IepStudent:
    """Öğrenciyi listeye ekler; tedbir verilmezse yalnız BEP üyeliğidir (eski davranış)."""
    student = okul_selectors.get_student(student_id)
    if student is None or student.status != StudentStatus.ACTIVE:
        raise ValidationError("Öğrenci bulunamadı ya da aktif değil.")
    if student_id in accommodation_rows():
        raise ValidationError("Bu öğrenci zaten listede.")
    row: IepStudent = IepStudent.objects.create(
        student_ref=str(student_id), **_clean_measures(measures or {})
    )
    return row


@transaction.atomic
def update_accommodation(row: IepStudent, measures: dict[str, Any]) -> IepStudent:
    """Satırın gerekçe ve tedbirlerini TAMAMEN değiştirir (gönderilmeyen tedbir kapanır).

    Gerekçe BEP'ten çıkarsa onaylanmamış oturumlardaki bireysel soru dosyaları
    düşer — `remove_iep_student` ile aynı kural: bireysel soru dosyası BEP'e özgüdür.
    """
    eski_bep = row.reason_category == RuleReason.IEP
    for name, value in _clean_measures(measures).items():
        setattr(row, name, value)
    row.save()
    student_id = _ref_id(row.student_ref)
    if eski_bep and row.reason_category != RuleReason.IEP and student_id is not None:
        _drop_individual_rows(student_id, only_editable=True)
    return row


#: Toplu eklemede bir istekte en çok kaç okul numarası işlenir.
MAX_BULK_NUMBERS = 200


@transaction.atomic
def add_by_numbers(numbers: list[str], measures: dict[str, Any] | None = None) -> dict[str, Any]:
    """Okul numaralarıyla toplu ekleme — hepsine AYNI gerekçe ve tedbirler yazılır.

    Dönüş SAYI ve numara taşır, ad taşımaz: `added`, `already` (zaten listede —
    yalnız sayı; numarası "listede" bilgisini yanıta yazmasın), `not_found` (bu
    numarayla aktif öğrenci yok — sistemdeki bir öğrenciye işaret etmez).
    """
    cleaned = _clean_measures(measures or {})
    istenen = list(dict.fromkeys(n.strip() for n in numbers if n and n.strip()))
    if not istenen:
        raise ValidationError("En az bir okul numarası yazın.")
    if len(istenen) > MAX_BULK_NUMBERS:
        raise ValidationError(f"Bir seferde en çok {MAX_BULK_NUMBERS} okul numarası eklenir.")
    ogrenciler = {
        s.student_number: s
        for s in Student.objects.filter(student_number__in=istenen, status=StudentStatus.ACTIVE)
    }
    mevcut = set(accommodation_rows())
    eklenen = 0
    zaten = 0
    bulunamayan: list[str] = []
    for number in istenen:
        student = ogrenciler.get(number)
        if student is None:
            bulunamayan.append(number)
            continue
        if student.pk in mevcut:
            zaten += 1
            continue
        IepStudent.objects.create(student_ref=str(student.pk), **cleaned)
        mevcut.add(student.pk)
        eklenen += 1
    return {"added": eklenen, "already": zaten, "not_found": bulunamayan}


# ---------------------------------------------------------------------------
# Tedbir → oturum (yerleştirme kuralı, uyarılar, panel)
# ---------------------------------------------------------------------------
_PLACEMENT_RULE_TYPES: dict[str, str] = {
    AccommodationPlacement.HOME_CLASSROOM: RuleType.HOME_CLASSROOM,
    AccommodationPlacement.SEPARATE_ROOM: RuleType.SEPARATE_ROOM,
    AccommodationPlacement.FRONT_ROW: RuleType.FRONT_ROW,
}


def accommodation_rules(student_ids: list[int]) -> dict[int, PlacementRule]:
    """Tedbirin YER ayağından KAYDEDİLMEMİŞ kalıcı kural (öğrenci pk → kural).

    `services._effective_rules` bunları oturum ve kalıcı kuralların ALTINA koyar:
    oturumdaki kural kazanır. Kural satırı yazılmaz — tedbirin kaynağı şifreli
    bağlı listedir; düz FK'lı `PlacementRule` satırı o bağı açık ederdi. Kayıtsız
    kural `pk is None` ile tanınır (`is_accommodation_rule`).
    """
    wanted = set(student_ids)
    if not wanted:
        return {}
    rules: dict[int, PlacementRule] = {}
    for student_id, row in accommodation_rows().items():
        rule_type = _PLACEMENT_RULE_TYPES.get(row.placement)
        if student_id not in wanted or rule_type is None:
            continue
        rules[student_id] = PlacementRule(
            student_id=student_id,
            scope=RuleScope.PERMANENT,
            rule_type=rule_type,
            target_room=row.target_room,
            seat_preference=(
                SeatPreference.NONE if rule_type == RuleType.FRONT_ROW else row.seat_preference
            ),
            solo_desk=row.solo_desk,
            reason_category=row.reason_category,
        )
    return rules


def is_accommodation_rule(rule: PlacementRule) -> bool:
    """Kural kalıcı sınav tedbirinden mi türedi (kayıtlı kural satırı DEĞİL)?"""
    return rule.pk is None


#: İdare özetinde ve panelde yer tedbirinin yerleşime yansımadığını söyleyen not.
PLACEMENT_NOT_APPLIED = "yer tedbiri bu dağıtımda uygulanmadı — oturumu yeniden dağıtın"


def placement_applied(row: IepStudent, assignment: SeatAssignment | None) -> bool | None:
    """Yer tedbiri bu yerleşime yansıdı mı? Yer tedbiri yoksa ya da yerleşim yoksa None.

    Kural (tedbir ya da oturum kuralı) yerleştirdiği öğrenciyi SABİT koltuğa koyar
    (`SeatStatus.PINNED`). Tedbir dağıtımdan SONRA girildiyse, düzen "Kendi
    dersliğinde" ise ya da dağıtım tedbirden önce yapıldıysa koltuk sabit değildir —
    özet bunu söylemezse "dağıtımda uygulandı" yanlış bilgi olurdu.
    """
    from apps.sinav.models import SeatStatus

    if assignment is None or row.placement == AccommodationPlacement.NONE:
        return None
    return bool(assignment.status == SeatStatus.PINNED)


def extra_minutes_map(student_ids: list[int] | None = None) -> dict[int, int]:
    """Öğrenci pk → ek süre (dakika); ek süresi olmayan sözlükte yoktur."""
    wanted = None if student_ids is None else set(student_ids)
    return {
        student_id: int(row.extra_minutes)
        for student_id, row in accommodation_rows().items()
        if row.extra_minutes and (wanted is None or student_id in wanted)
    }


def distribution_warnings(
    session: ExamSession, student_ids: list[int], placements: list[Any]
) -> list[str]:
    """Dağıtım sonrası tedbir uyarıları — yalnız SAYI söyler, öğrenci kimliği yok.

    Okuyucu/yazıcı desteği yerleşimi kendiliğinden değiştirmez (sesli okuma
    için ayrı salon önerilir; görevliyi program atamaz — kullanıcı kararı).
    """
    from apps.sinav.models import LayoutMode

    kapsam = set(student_ids)
    rows = {sid: row for sid, row in accommodation_rows().items() if sid in kapsam}
    if not rows:
        return []
    warnings: list[str] = []
    if session.layout_mode == LayoutMode.HOME_CLASSROOM:
        ayri = sum(
            1 for row in rows.values() if row.placement == AccommodationPlacement.SEPARATE_ROOM
        )
        if ayri:
            warnings.append(
                f"Ayrı salonda sınava girmesi gereken {ayri} öğrenci var; “Kendi dersliğinde” "
                "düzeninde yerleştirme kuralları uygulanmaz. Bu öğrencileri ayrı salona siz "
                "alın ya da düzeni Kelebek yapın."
            )
    destekli = [sid for sid, row in rows.items() if row.reader or row.scribe]
    ayri_degil = sum(
        1 for sid in destekli if rows[sid].placement != AccommodationPlacement.SEPARATE_ROOM
    )
    if ayri_degil:
        warnings.append(
            f"Okuyucu ya da yazıcı desteği alan {ayri_degil} öğrenci ayrı salonda değil; sesli "
            "okuma ve yazdırma salondaki öbür öğrencileri etkiler."
        )
    salon_basina: dict[int, int] = {}
    for placement in placements:
        if placement.participant.student_id in destekli:
            salon_basina[placement.room_id] = salon_basina.get(placement.room_id, 0) + 1
    kalabalik = [room_id for room_id, n in salon_basina.items() if n > 1]
    if kalabalik:
        adlar = dict(ExamRoom.objects.filter(pk__in=kalabalik).values_list("pk", "name"))
        for room_id in sorted(
            kalabalik, key=lambda r: reports.room_name_sort_key(adlar.get(r, ""))
        ):
            warnings.append(
                f"“{adlar.get(room_id, 'salon')}” salonunda okuyucu ya da yazıcı desteği alan "
                f"{salon_basina[room_id]} öğrenci var; destek her öğrenciye ayrı verilecekse "
                "öğrencilere ayrı salon seçin."
            )
    ek = sum(1 for row in rows.values() if row.extra_minutes)
    if ek:
        warnings.append(
            f"Bu oturumda ek süreli {ek} öğrenci var; ek süre salon evrakına basılmaz — "
            "gözetmenlere idare özetiyle bildirin."
        )
    return warnings


def session_accommodations(session: ExamSession) -> list[dict[str, Any]]:
    """Oturuma giren tedbirli öğrenciler (Yerleştirme Kuralları paneli).

    Kapsam: güncel katılımcı çözümü ∩ liste (BEP üyeliği tek başına tedbir
    değildir — tedbiri olmayan BEP satırı burada GÖRÜNMEZ, Sorular sekmesinde
    görünür). Oturum kuralı olan öğrencide tedbirin yer ayağı uygulanmaz
    (`overridden`); süre/destek yine geçerlidir.
    """
    from apps.sinav import participants as sinav_participants

    purge_stale()
    rows = {sid: row for sid, row in accommodation_rows().items() if has_measures(row)}
    if not rows:
        return []
    katilimcilar = {p.student_id for p in sinav_participants.resolve_session(session).participants}
    ortak = [sid for sid in rows if sid in katilimcilar]
    if not ortak:
        return []
    oturum_kurali = set(
        PlacementRule.objects.filter(
            session=session, scope=RuleScope.SESSION, student_id__in=ortak
        ).values_list("student_id", flat=True)
    )
    koltuk = {
        a.student_id: a
        for a in SeatAssignment.objects.filter(
            session=session, student_id__in=ortak
        ).select_related("room")
    }
    ogrenciler = {s.pk: s for s in Student.objects.filter(pk__in=ortak)}
    items: list[dict[str, Any]] = []
    for sid in ortak:
        student = ogrenciler.get(sid)
        if student is None:
            continue
        row = rows[sid]
        a = koltuk.get(sid)
        items.append(
            {
                "student_id": sid,
                "student_number": student.student_number,
                "full_name": student.full_name,
                "class_label": student.class_label,
                "reason_label": RuleReason(row.reason_category).label,
                "measures": measure_labels(row),
                "overridden": sid in oturum_kurali and row.placement != AccommodationPlacement.NONE,
                # None: yer tedbiri yok ya da dağıtılmadı; False: dağıtım tedbirden önce
                # yapılmış (ya da düzen kuralları uygulamıyor) — yeniden dağıtılmalı.
                "placement_applied": placement_applied(row, a),
                "room_name": a.room.name if a is not None else "",
                "seat_no": a.seat_no if a is not None else None,
            }
        )
    items.sort(
        key=lambda item: (
            reports.class_label_sort_key(str(item["class_label"])),
            reports.student_number_sort_key(str(item["student_number"])),
        )
    )
    return items


@transaction.atomic
def remove_iep_student(row: IepStudent) -> None:
    """Listeden çıkarır; ONAYLANMAMIŞ oturumlardaki bireysel soru dosyaları da silinir.

    Onaylı/arşiv oturumun kaydı o sınavın yapıldığı hâlin parçasıdır — yerinde
    kalır (arşiv anonimleştirmesi ya da öğrencinin ayrılması siler).
    """
    student_id = _ref_id(row.student_ref)
    row.hard_delete()
    if student_id is not None:
        _drop_individual_rows(student_id, only_editable=True)


@transaction.atomic
def delete_all() -> dict[str, int]:
    """KVKK düğmesi: BÜTÜN BEP kayıtları ve BÜTÜN bireysel soru dosyaları KATI silinir."""
    documents = list(IndividualQuestionDocument.all_objects.all())
    _delete_documents(documents)
    removed, _ = IepStudent.all_objects.get_queryset().all().hard_delete()
    logger.info(
        "BEP kayıtları silindi: %s kayıt, %s bireysel soru dosyası", removed, len(documents)
    )
    return {"students": int(removed), "documents": len(documents)}


@transaction.atomic
def forget_student(student_id: int) -> None:
    """Ayrılan/silinen öğrencinin BEP kaydını ve bireysel soru dosyalarını KATI siler.

    `okul.services.persons` öğrenci pasifleşince/silinince çağırır (kanca —
    `SinavConfig.ready`); fotoğraf emsali: kişisel veri artığı kalmasın.
    Oturum durumuna BAKILMAZ (arşiv dahil).
    """
    for row in IepStudent.all_objects.all():
        if _ref_id(row.student_ref) == student_id:
            row.hard_delete()
    _drop_individual_rows(student_id, only_editable=False)


def purge_stale() -> int:
    """Aktif olmayan/silinmiş öğrenciye ait kayıtları KATI siler; silinen öğrenci sayısı.

    `forget_student` kancasına uğramadan durumu değişen öğrenci (toplu işlem,
    yedekten dönüş) için sigorta — fotoğraflardaki `purge_stale_photos` deseni.
    Çözülemeyen bağa DOKUNULMAZ (kilitli kasada liste silinmez).
    """
    referenced = set(accommodation_rows())
    for document in IndividualQuestionDocument.objects.all():
        student_id = _ref_id(document.student_ref)
        if student_id is not None:
            referenced.add(student_id)
    if not referenced:
        return 0
    alive = set(
        Student.objects.filter(pk__in=list(referenced), status=StudentStatus.ACTIVE).values_list(
            "pk", flat=True
        )
    )
    stale = referenced - alive
    for student_id in stale:
        forget_student(student_id)
    if stale:
        logger.info("BEP kayıtları temizlendi: %s öğrenci", len(stale))
    return len(stale)


# ---------------------------------------------------------------------------
# Bireysel soru dosyası (oturum bazında seçim + yükleme)
# ---------------------------------------------------------------------------
def _ensure_editable(session: ExamSession) -> None:
    if session.status not in _EDITABLE_STATUSES:
        raise ValidationError("Onaylı/arşiv oturumda bireysel soru dosyası değiştirilemez.")


def _touch(session_id: int) -> None:
    """Kitapçık üretiminin bayatlık damgası (satır KATI silindiği için oturumda durur)."""
    ExamSession.all_objects.filter(pk=session_id).update(individual_changed_at=timezone.now())


def individual_rows(session: ExamSession) -> dict[int, IndividualQuestionDocument]:
    """Öğrenci pk → oturumdaki bireysel soru dosyası satırı (çözülemeyen bağ atlanır)."""
    rows: dict[int, IndividualQuestionDocument] = {}
    for row in IndividualQuestionDocument.objects.filter(session=session).order_by("pk"):
        student_id = _ref_id(row.student_ref)
        if student_id is not None:
            rows.setdefault(student_id, row)
    return rows


def get_individual(document_id: int) -> IndividualQuestionDocument | None:
    return (
        IndividualQuestionDocument.objects.select_related("session").filter(pk=document_id).first()
    )


@transaction.atomic
def select_individual(session: ExamSession, *, student_id: int) -> IndividualQuestionDocument:
    """ "Bu öğrenciye bireysel soru dosyası uygulanacak" seçimi (dosya sonra yüklenir)."""
    _ensure_editable(session)
    if student_id not in iep_student_ids():
        raise ValidationError(
            "Bireysel soru dosyası yalnız BEP kapsamındaki öğrenciye uygulanır; öğrenciyi "
            "Kişiler → BEP ve tedbirler listesine “BEP” gerekçesiyle ekleyin."
        )
    if not SeatAssignment.objects.filter(session=session, student_id=student_id).exists():
        raise ValidationError(
            "Bu öğrenci oturumun yerleşiminde yok; önce dağıtım yapın ya da öğrencinin "
            "bu sınava girdiğini denetleyin."
        )
    if student_id in individual_rows(session):
        raise ValidationError("Bu öğrenci için bireysel soru dosyası zaten seçili.")
    row: IndividualQuestionDocument = IndividualQuestionDocument.objects.create(
        session=session, student_ref=str(student_id)
    )
    _touch(session.pk)
    return row


@transaction.atomic
def upload_individual(
    row: IndividualQuestionDocument,
    *,
    file_bytes: bytes,
    score_mode: str = ScoreMode.SINGLE_BOX,
    question_count: int | None = None,
) -> IndividualQuestionDocument:
    """Bireysel soru PDF'ini yükler/değiştirir — ders dosyasıyla AYNI doğrulama.

    Eski dosya diskten silinir (commit sonrası); yeni dosya öğrenciyle ilişkisiz
    rastgele adla yazılır.
    """
    _ensure_editable(row.session)
    page_count = question_pdf.validate_question_pdf(
        file_bytes, score_mode=score_mode, question_count=question_count
    )
    old = _stored(row)
    row.page_count = page_count
    row.sha256 = hashlib.sha256(file_bytes).hexdigest()
    row.score_mode = score_mode
    row.question_count = question_count if score_mode == ScoreMode.QUESTION_TABLE else None
    row.file.save(f"soru_b_{uuid.uuid4().hex}.pdf", ContentFile(file_bytes), save=False)
    row.save()
    _delete_files_on_commit(old)
    _touch(row.session_id)
    return row


@transaction.atomic
def remove_individual(row: IndividualQuestionDocument) -> None:
    """Seçimi kaldırır: satır + dosya KATI silinir; öğrenci dersin kitapçığını alır."""
    _ensure_editable(row.session)
    session_id = row.session_id
    _delete_documents([row])
    _touch(session_id)


def purge_session(session: ExamSession) -> int:
    """Oturumun bütün bireysel soru dosyalarını KATI siler (oturum silme + F27 anonimleştirme)."""
    documents = list(IndividualQuestionDocument.all_objects.filter(session=session))
    _delete_documents(documents)
    return len(documents)


def _stored(row: IndividualQuestionDocument) -> list[tuple[Storage, str]]:
    return [(row.file.storage, row.file.name)] if row.file and row.file.name else []


def _delete_files_on_commit(files: list[tuple[Storage, str]]) -> None:
    """Dosya silme COMMIT SONRASINA ertelenir: işlem geri sarılırsa dosya yerinde kalır."""
    if not files:
        return

    def _delete() -> None:
        for storage, name in files:
            if storage.exists(name):
                storage.delete(name)

    transaction.on_commit(_delete)


def _delete_documents(documents: list[IndividualQuestionDocument]) -> None:
    files = [item for document in documents for item in _stored(document)]
    for document in documents:
        document.hard_delete()
    _delete_files_on_commit(files)


def _drop_individual_rows(student_id: int, *, only_editable: bool) -> None:
    queryset = IndividualQuestionDocument.all_objects.select_related("session")
    if only_editable:
        queryset = queryset.filter(session__status__in=_EDITABLE_STATUSES)
    matched = [row for row in queryset if _ref_id(row.student_ref) == student_id]
    session_ids = {row.session_id for row in matched}
    _delete_documents(matched)
    for session_id in session_ids:
        _touch(session_id)


# ---------------------------------------------------------------------------
# Kitapçık üretimi köprüsü (`services.request_booklet_run` / `generate_booklets_for_run`)
# ---------------------------------------------------------------------------
def booklet_rows(session: ExamSession) -> dict[int, IndividualQuestionDocument]:
    """Kitapçık üretiminin okuduğu satırlar — önce bayat kayıtlar düşer."""
    purge_stale()
    return individual_rows(session)


def document_key(group_key: str, row: IndividualQuestionDocument) -> str:
    """Bireysel dosyanın `booklet` doküman sözlüğündeki anahtarı (grup anahtarına EK)."""
    return f"{group_key}{INDIVIDUAL_KEY_SEP}{row.pk}"


# ---------------------------------------------------------------------------
# Oturum paneli + idare özeti
# ---------------------------------------------------------------------------
def session_rows(session: ExamSession) -> list[dict[str, Any]]:
    """Oturuma giren BEP kapsamındaki öğrenciler + bireysel dosya durumu (panel).

    Kapsam: BEP listesindeki öğrencilerden bu oturumda YERLEŞİMİ olanlar; ayrıca
    bireysel soru dosyası satırı olup yerleşimde görünmeyen öğrenci (yeniden
    dağıtımda oturumdan düşmüş) — görünmez kalmasın, kaldırılabilsin diye.
    """
    from apps.sinav.services import conflict_group_labels

    purge_stale()
    iep_ids = iep_student_ids()
    documents = individual_rows(session)
    wanted = iep_ids | set(documents)
    if not wanted:
        return []
    assignments = list(
        SeatAssignment.objects.filter(session=session, student_id__in=list(wanted)).select_related(
            "room"
        )
    )
    labels = conflict_group_labels({a.conflict_group for a in assignments})
    items: list[dict[str, Any]] = []
    placed: set[int] = set()
    for a in assignments:
        if a.student_id is None:
            continue
        placed.add(a.student_id)
        items.append(
            _session_row(
                student_id=a.student_id,
                student_number=a.student_number,
                full_name=a.full_name,
                class_label=a.class_label,
                room_name=a.room.name,
                seat_no=a.seat_no,
                course_label=labels.get(a.conflict_group, ""),
                on_iep_list=a.student_id in iep_ids,
                document=documents.get(a.student_id),
            )
        )
    orphans = set(documents) - placed
    for student in Student.objects.filter(pk__in=list(orphans)):
        items.append(
            _session_row(
                student_id=student.pk,
                student_number=student.student_number,
                full_name=student.full_name,
                class_label=student.class_label,
                room_name="",
                seat_no=None,
                course_label="",
                on_iep_list=student.pk in iep_ids,
                document=documents.get(student.pk),
            )
        )
    items.sort(
        key=lambda item: (
            item["seat_no"] is None,
            reports.room_name_sort_key(str(item["room_name"])),
            item["seat_no"] or 0,
        )
    )
    return items


def _session_row(
    *,
    student_id: int,
    student_number: str,
    full_name: str,
    class_label: str,
    room_name: str,
    seat_no: int | None,
    course_label: str,
    on_iep_list: bool,
    document: IndividualQuestionDocument | None,
) -> dict[str, Any]:
    return {
        "student_id": student_id,
        "student_number": student_number,
        "full_name": full_name,
        "class_label": class_label,
        "room_name": room_name,
        "seat_no": seat_no,
        "course_label": course_label,
        "on_iep_list": on_iep_list,
        "document": None if document is None else document_payload(document),
    }


def document_payload(document: IndividualQuestionDocument) -> dict[str, Any]:
    """Satırın arayüz özeti — öğrenci kimliği TAŞIMAZ (satır kimliği opaktır)."""
    return {
        "id": document.pk,
        "has_file": bool(document.file),
        "page_count": document.page_count,
        "score_mode": document.score_mode,
        "question_count": document.question_count,
    }


#: İdare özetinin belge adı (sözlük: "Sınav Tedbirleri ve BEP — İdare Özeti").
SUMMARY_TITLE = "Sınav Tedbirleri ve BEP — İdare Özeti"


def summary_rows(session: ExamSession) -> list[dict[str, Any]]:
    """İdare özetinin satırları: oturumda YERLEŞMİŞ BEP'li ya da tedbirli öğrenciler.

    BEP satırı (tedbirsiz olsa da), tedbiri olan her satır ve bireysel soru
    dosyası seçilmiş öğrenci girer. Tedbir metni `measure_labels`'tandır — panel
    ve liste ekranıyla aynı.
    """
    from apps.sinav.services import conflict_group_labels

    purge_stale()
    rows = accommodation_rows()
    documents = individual_rows(session)
    wanted = {
        sid
        for sid, row in rows.items()
        if row.reason_category == RuleReason.IEP or has_measures(row)
    } | set(documents)
    if not wanted:
        return []
    assignments = list(
        SeatAssignment.objects.filter(session=session, student_id__in=list(wanted)).select_related(
            "room"
        )
    )
    labels = conflict_group_labels({a.conflict_group for a in assignments})
    items: list[dict[str, Any]] = []
    for a in assignments:
        if a.student_id is None:
            continue
        row = rows.get(a.student_id)
        document = documents.get(a.student_id)
        tedbirler = measure_labels(row) if row is not None else []
        if row is not None and placement_applied(row, a) is False:
            tedbirler.append(PLACEMENT_NOT_APPLIED)
        items.append(
            {
                "room_name": a.room.name,
                "seat_no": a.seat_no,
                "student_number": a.student_number,
                "full_name": a.full_name,
                "class_label": a.class_label,
                "course_label": labels.get(a.conflict_group, ""),
                "measures": " · ".join(tedbirler),
                "paper": (
                    PAPER_COURSE
                    if document is None
                    else PAPER_INDIVIDUAL
                    if document.file
                    else PAPER_PENDING
                ),
                "individual": document is not None,
                "extra_minutes": int(row.extra_minutes) if row is not None else 0,
            }
        )
    items.sort(
        key=lambda item: (reports.room_name_sort_key(str(item["room_name"])), item["seat_no"] or 0)
    )
    return items


def render_iep_summary(session: ExamSession) -> ReportFile:
    """Sınav tedbirleri ve BEP — İDARE ÖZETİ (PDF; salonlara GİTMEZ).

    Kullanıcı kararları: gözetmenlere dağıtılan belge yok, idareci bilgiyi
    kendisi aktarır (20.09.2026); ek süre ve okuyucu/yazıcı desteği YALNIZ bu
    özette basılır (07.10.2026). Bu yüzden özet `REPORT_CODES`te DEĞİLDİR
    ("Tümünü indir" paketine girmez) ve ayrı uçtan, bilerek indirilir.
    """
    from apps.sinav.services import _PDF_MIME, _REPORTABLE_STATUSES, ReportFile, _report_header

    if session.status not in _REPORTABLE_STATUSES:
        raise ValidationError("Önce dağıtım yapın — özet yerleşimden üretilir.")
    table = summary_rows(session)
    if not table:
        raise ValidationError(
            "Bu oturumda BEP kapsamında ya da sınav tedbiri olan yerleşmiş öğrenci yok."
        )
    context: dict[str, object] = {
        "header": _report_header(session),
        "title": SUMMARY_TITLE,
        "rows": table,
        "total": len(table),
        "individual_total": sum(1 for row in table if row["individual"]),
        "extra_total": sum(1 for row in table if row["extra_minutes"]),
    }
    return ReportFile(
        filename=f"tedbir_idare_ozeti_oturum_{session.pk}.pdf",
        content_type=_PDF_MIME,
        content=reports.render_pdf("sinav/reports/bep_idare_ozeti.html", context),
    )
