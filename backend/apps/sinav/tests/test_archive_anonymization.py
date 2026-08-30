"""Arşiv saklama süresi + anonimleştirme testleri (F27 — F8; OYS Tur 246'dan).

Kullanıcı kararı: sınav tarihinden itibaren 2 ders yılı (730 gün) dolan ARŞİV
oturumların kişisel verili snapshot'ları geri dönüşsüz anonimleşir; sayısal
düzen (koltuk/salon/grup) istatistik arşivi olarak kalır. KS uyarlaması (K14):
Celery beat yerine açılışta aday tespiti + kullanıcı onaylı elle tetik.

F8 kapısı: anonimleştirme SONRASI evrak yeniden basımı KIRILMAZ — R1-R9 + ZIP
"—" işaretli satırlarla üretilmeye devam eder.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.okul.models import Personnel
from apps.sinav import services
from apps.sinav.models import (
    BookletRun,
    BookletRunStatus,
    ExamAttendanceRecord,
    ExamSession,
    ProctorAssignment,
    ProctorRole,
    QuestionDocument,
    SeatAssignment,
)
from apps.sinav.tests.test_reports import _evrak_oturumu

pytestmark = pytest.mark.django_db

ANONIM_UC = "/api/v1/exam-sessions/archive-anonymization/"


def _arsiv_oturumu(**kwargs: object) -> ExamSession:
    """Gözetmenli + yoklamalı + dosyalı ARŞİV oturum (anonimleştirme kapsamı tam)."""
    session = _evrak_oturumu(**kwargs)
    # R6 kapı testi için gözetmen modülü açık (K2: kapalıyken r6 üretilmez).
    session.proctors_enabled = True
    session.save(update_fields=["proctors_enabled", "updated_at"])
    hoca = Personnel.objects.create(first_name="AYŞE", last_name="ÖĞRETMEN")
    oturum_salonu = session.rooms.select_related("room").first()
    assert oturum_salonu is not None
    ProctorAssignment.objects.create(
        session=session,
        teacher=hoca,
        teacher_name=hoca.full_name,
        role=ProctorRole.PROCTOR,
        room=oturum_salonu.room,
    )
    services.approve_session(session, approved_by_name="Müdür")
    assignment = SeatAssignment.objects.filter(session=session).first()
    assert assignment is not None
    services.mark_absent(session, seat_assignment_id=assignment.pk, note="Rapor no 9, 01.06.2026")
    # Kişisel veri taşıyan dosyalar: kitapçık ZIP'i + soru PDF'i (KS dosya adımı).
    sc = session.courses.first()
    assert sc is not None
    QuestionDocument.objects.create(
        session_course=sc,
        file=ContentFile(b"%PDF-1.4 soru", name="soru.pdf"),
        page_count=1,
        sha256="0" * 64,
    )
    BookletRun.objects.create(
        session=session,
        status=BookletRunStatus.COMPLETED,
        file=ContentFile(b"zip-icerigi", name="kitapcik.zip"),
    )
    services.archive_session(session)
    session.refresh_from_db()
    return session


def test_anonymize_yalniz_arsivde() -> None:
    session = _evrak_oturumu()  # DAĞITILDI
    with pytest.raises(ValidationError, match="ARŞİV"):
        services.anonymize_exam_session(session)


def test_anonymize_snapshotlari_temizler_duzeni_korur() -> None:
    session = _arsiv_oturumu()
    counts = services.anonymize_exam_session(session)
    session.refresh_from_db()
    assert session.anonymized_at is not None
    assert counts["seat_assignments"] == 6  # 2 seviye × 3 öğrenci

    for seat in SeatAssignment.all_objects.filter(session=session):
        assert seat.full_name == services.ANONYMIZED_MARK
        assert seat.student_number == services.ANONYMIZED_MARK
        assert seat.student_id is None
        assert seat.seat_no >= 1  # sayısal düzen korunur
        assert seat.class_label  # şube etiketi tek başına tanımlayıcı değil
    record = ExamAttendanceRecord.all_objects.get(session=session)
    assert record.full_name == services.ANONYMIZED_MARK and record.student_id is None
    assert record.note == ""  # belge no/tarih de kişisel bağlamdır — silinir
    proctor = ProctorAssignment.all_objects.get(session=session)
    assert proctor.teacher_name == services.ANONYMIZED_MARK and proctor.teacher_id is None

    # İkinci çağrı reddedilir (geri dönüşsüz — açık hata; idempotenslik toplu tarafta).
    with pytest.raises(ValidationError, match="zaten"):
        services.anonymize_exam_session(session)


def test_anonymize_dosyalari_siler_satirlari_korur(
    django_capture_on_commit_callbacks: Any,
) -> None:
    """KS eki: kitapçık ZIP + soru PDF dosyaları silinir (OYS'nin açık kalemi).

    Silme `transaction.on_commit`e ertelenir (geri sarmada dosya yerinde kalsın);
    test sarmal işlemde koştuğundan kancalar fikstürle elle tetiklenir.
    """
    session = _arsiv_oturumu()
    run = BookletRun.objects.get(session=session)
    doc = QuestionDocument.objects.get(session_course__session=session)
    storage, run_adi, doc_adi = run.file.storage, run.file.name, doc.file.name
    assert storage.exists(run_adi) and storage.exists(doc_adi)

    with django_capture_on_commit_callbacks(execute=True):
        counts = services.anonymize_exam_session(session)

    assert counts["deleted_files"] == 2
    assert not storage.exists(run_adi) and not storage.exists(doc_adi)
    run.refresh_from_db()
    doc.refresh_from_db()
    assert not run.file and not doc.file
    assert run.status == BookletRunStatus.COMPLETED  # satır/sayım izi kalır


def test_anonymize_sonrasi_yoklama_kapali() -> None:
    session = _arsiv_oturumu()
    record = ExamAttendanceRecord.objects.get(session=session)
    services.anonymize_exam_session(session)
    session.refresh_from_db()
    record.refresh_from_db()

    with pytest.raises(ValidationError, match="anonimleştirilmiş"):
        services.mark_absent(session, seat_assignment_id=1)
    # OYS'de açık kalan delik KS'de kapalı: not güncelleme ve geri alma da kapanır.
    with pytest.raises(ValidationError, match="anonimleştirilmiş"):
        services.update_attendance_record(record, note="yeniden kişisel bağlam")
    with pytest.raises(ValidationError, match="anonimleştirilmiş"):
        services.unmark_absent(record)


def test_anonymize_sonrasi_yeniden_basim_kirilmaz() -> None:
    """F8 kapısı: anonim arşivde R1-R9 + ZIP üretimi çalışır, '—' basılır."""
    session = _arsiv_oturumu()
    services.anonymize_exam_session(session)
    session.refresh_from_db()

    for code in services.REPORT_CODES:
        rf = services.render_session_report(session, code)
        assert rf.content, f"{code} boş üretildi"
    zip_dosyasi = services.render_session_reports_zip(session)
    assert zip_dosyasi.content.startswith(b"PK")


def test_anonymize_sonrasi_kitapcik_ve_soru_indirme_kapali() -> None:
    """Kitapçık üretimi Türkçe hatayla reddedilir (soru PDF'leri silindi — ham
    dosya hatasıyla FAILED koşu birikmesin); soru indirme ucu 404'e düşer."""
    session = _arsiv_oturumu()
    sc = session.courses.first()
    assert sc is not None
    services.anonymize_exam_session(session)
    session.refresh_from_db()

    with pytest.raises(ValidationError, match="anonimleştirilmiş"):
        services.request_booklet_run(session)

    yanit = APIClient().get(f"/api/v1/exam-session-courses/{sc.pk}/question/download/")
    assert yanit.status_code == 404  # boş FieldFile ham 500 olmamalı


def test_expired_yalniz_suresi_dolanlari_isler() -> None:
    session = _arsiv_oturumu()  # sınav tarihi taze — süre dolmadı

    assert services.expired_archive_candidates() == []
    assert services.anonymize_expired_exam_archives() == []
    session.refresh_from_db()
    assert session.anonymized_at is None

    # Sınav tarihi bugünden 731 gün geriye alınınca (>730) aday olur ve işlenir.
    # (Fikstür tarihi GELECEKTE — mutlak kaydırma değil, bugüne göre kurulur.)
    session.exam_date = timezone.localdate() - timedelta(days=731)
    session.save(update_fields=["exam_date"])
    assert [aday.pk for aday in services.expired_archive_candidates()] == [session.pk]
    assert services.anonymize_expired_exam_archives() == [session.pk]
    session.refresh_from_db()
    assert session.anonymized_at is not None

    # İkinci koşu no-op (aday filtresi damgaya bakar — toplu taraf idempotent).
    assert services.anonymize_expired_exam_archives() == []


def test_aday_olmayan_oturum_secilirse_tumu_reddedilir() -> None:
    """Risk #9: aday listesi dışındaki bir id tüm isteği düşürür, kısmi iş yapılmaz."""
    session = _arsiv_oturumu()
    session.exam_date = timezone.localdate() - timedelta(days=731)
    session.save(update_fields=["exam_date"])

    with pytest.raises(ValidationError, match="anonimleştirme adayı değil"):
        services.anonymize_expired_exam_archives(session_ids=[session.pk, 99999])
    session.refresh_from_db()
    assert session.anonymized_at is None  # kısmi anonimleştirme YOK


def test_arsiv_suresi_sabiti_iki_ders_yili() -> None:
    assert services.EXAM_ARCHIVE_RETENTION_DAYS == 730


def test_api_aday_listesi_ve_onayli_tetik() -> None:
    session = _arsiv_oturumu()
    session.exam_date = timezone.localdate() - timedelta(days=731)
    session.save(update_fields=["exam_date"])
    client = APIClient()

    listeleme = client.get(ANONIM_UC)
    assert listeleme.status_code == 200
    govde = listeleme.json()
    assert govde["retention_days"] == 730
    assert [aday["id"] for aday in govde["candidates"]] == [session.pk]
    assert govde["candidates"][0]["name"] == session.name

    # Gövdesiz/boş tetik reddedilir (onay diyaloğu listeyi taşımak zorunda).
    assert client.post(ANONIM_UC, {}, format="json").status_code == 400
    # JSON `true` int'e sessizce dönüşüp id=1 sayılmamalı (bool ⊂ int tuzağı).
    assert client.post(ANONIM_UC, {"session_ids": [True]}, format="json").status_code == 400

    tetik = client.post(ANONIM_UC, {"session_ids": [session.pk]}, format="json")
    assert tetik.status_code == 200
    assert tetik.json() == {"anonymized": [session.pk]}
    session.refresh_from_db()
    assert session.anonymized_at is not None
