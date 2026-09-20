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
    ExamSession,
    ExamSessionStatus,
    IepStudent,
    IndividualQuestionDocument,
    ScoreMode,
    SeatAssignment,
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
# BEP kapsamındaki öğrenciler (kalıcı liste)
# ---------------------------------------------------------------------------
def iep_rows() -> dict[int, IepStudent]:
    """Öğrenci pk → BEP kaydı. Çözülemeyen bağ atlanır; mükerrerde ilk kayıt kalır."""
    rows: dict[int, IepStudent] = {}
    for row in IepStudent.objects.all().order_by("pk"):
        student_id = _ref_id(row.student_ref)
        if student_id is not None:
            rows.setdefault(student_id, row)
    return rows


def iep_student_ids() -> set[int]:
    return set(iep_rows())


def iep_list() -> list[dict[str, Any]]:
    """Liste ekranı satırları — sınıf/şube, sonra okul no sırasıyla (ad şifreli: TB3)."""
    purge_stale()
    rows = iep_rows()
    students = {s.pk: s for s in Student.objects.filter(pk__in=list(rows))}
    items = [
        {
            "id": rows[student_id].pk,
            "student_id": student_id,
            "student_number": student.student_number,
            "full_name": student.full_name,
            "class_label": student.class_label,
        }
        for student_id, student in students.items()
    ]
    items.sort(
        key=lambda item: (
            reports.class_label_sort_key(str(item["class_label"])),
            reports.student_number_sort_key(str(item["student_number"])),
        )
    )
    return items


@transaction.atomic
def add_iep_student(student_id: int) -> IepStudent:
    """Öğrenciyi BEP kapsamındaki öğrenciler listesine ekler (yalnız üyelik)."""
    student = okul_selectors.get_student(student_id)
    if student is None or student.status != StudentStatus.ACTIVE:
        raise ValidationError("Öğrenci bulunamadı ya da aktif değil.")
    if student_id in iep_rows():
        raise ValidationError("Bu öğrenci zaten listede.")
    row: IepStudent = IepStudent.objects.create(student_ref=str(student_id))
    return row


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
    referenced = set(iep_rows())
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
            "Bireysel soru dosyası yalnız BEP kapsamındaki öğrenciler listesindeki "
            "öğrenciye uygulanır; öğrenciyi önce listeye ekleyin."
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


def render_iep_summary(session: ExamSession) -> ReportFile:
    """BEP kapsamındaki öğrenciler — İDARE ÖZETİ (PDF; salonlara GİTMEZ).

    Kullanıcı kararı: gözetmenlere dağıtılan belge yok; idareci bilgiyi kendisi
    aktarır. Bu yüzden özet `REPORT_CODES`te DEĞİLDİR ("Tümünü indir" paketine
    girmez) ve ayrı uçtan, bilerek indirilir.
    """
    from apps.sinav.services import _PDF_MIME, _REPORTABLE_STATUSES, ReportFile, _report_header

    if session.status not in _REPORTABLE_STATUSES:
        raise ValidationError("Önce dağıtım yapın — özet yerleşimden üretilir.")
    rows = [row for row in session_rows(session) if row["seat_no"] is not None]
    if not rows:
        raise ValidationError("Bu oturumda BEP kapsamında yerleşmiş öğrenci yok.")
    table = [
        {
            **row,
            "paper": (
                PAPER_COURSE
                if row["document"] is None
                else PAPER_INDIVIDUAL
                if row["document"]["has_file"]
                else PAPER_PENDING
            ),
        }
        for row in rows
    ]
    context: dict[str, object] = {
        "header": _report_header(session),
        "title": "BEP Kapsamındaki Öğrenciler — İdare Özeti",
        "rows": table,
        "total": len(table),
        "individual_total": sum(1 for row in table if row["document"] is not None),
    }
    return ReportFile(
        filename=f"bep_idare_ozeti_oturum_{session.pk}.pdf",
        content_type=_PDF_MIME,
        content=reports.render_pdf("sinav/reports/bep_idare_ozeti.html", context),
    )
