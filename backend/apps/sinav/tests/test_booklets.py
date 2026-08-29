"""Soru kitapçığı motoru testleri (F5) — OYS test_booklets.py'den UYARLA.

Kabul kriterleri (tasarım §12 F5 kapısı): bant ≤ 40mm invariantı (şablon
taraması), tek/çift sayfa başlık kuralları, Sayfa x/y, Türkçe karakter,
salon sıralı paket (karışık ders), eksik dosya hatası (ders adıyla, öğrenci
adsız), 90×4 sayfa performansı, yükleme doğrulamaları (A4 dikey ±6pt dahil),
Word şablonu (4 cm üst marj). KS uyarlaması: RBAC/AccessLog/Celery düştü —
üretim SENKRON (request_booklet_run tek çağrıda tamamlar).
Ölçekleme yok — içerik 1:1, bant üst 4 cm sabit (OYS Tur 236).
"""

from __future__ import annotations

import io
import re
import time as time_mod
import zipfile
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.dersler.models import Course
from apps.okul.models import SchoolConfig
from apps.sinav import booklet, services
from apps.sinav.models import (
    BookletRunStatus,
    DeskType,
    ExamSession,
    ParticipantType,
    QuestionDocument,
    ScoreMode,
    SeatAssignment,
)
from apps.sinav.tests.oturum_yardim import ders, oturum, salon, sube

pytestmark = pytest.mark.django_db

PLAN_3X2_DOUBLE: dict[str, Any] = {
    "grid": {"rows": 3, "cols": 2},
    "desks": [{"row": r, "col": c, "type": DeskType.DOUBLE} for r in range(3) for c in range(2)],
    "furniture": [],
}


def _question_pdf(pages: int, *, title: str = "Soru") -> bytes:
    """Test soru PDF'i — WeasyPrint ile metinli gerçek sayfalar."""
    from weasyprint import HTML

    body = "".join(
        f'<div style="page-break-after: always; font-family: DejaVu Sans;">'
        f"<h2>{title} — sayfa {i + 1}</h2><p>1) Soru metni ĞÜŞİÖÇ ığüşöç?</p></div>"
        for i in range(pages)
    )
    return bytes(HTML(string=f"<html><body>{body}</body></html>").write_pdf())


def _distributed_session(*, question_pages: dict[str, int] | None = None) -> ExamSession:
    """2 ders × 4'er öğrenci, dağıtılmış oturum; istenirse soru dosyaları yüklü."""
    sube(9, "A", students=4, start_no=101)
    sube(10, "A", students=4, start_no=201)
    c9 = ders("Coğrafya", levels=[9])
    c10 = ders("Fizik", levels=[10])
    session = oturum()
    sc9 = services.add_session_course(
        session, course_id=c9.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    sc10 = services.add_session_course(
        session, course_id=c10.pk, participant_type=ParticipantType.LEVEL, level=10
    )
    services.set_session_rooms(session, [{"room_id": salon("D-201", plan=PLAN_3X2_DOUBLE).pk}])
    services.distribute_session(session, seed=42)
    if question_pages:
        services.upload_question_document(
            sc9, file_bytes=_question_pdf(question_pages.get("Coğrafya", 2), title="Coğrafya")
        )
        services.upload_question_document(
            sc10, file_bytes=_question_pdf(question_pages.get("Fizik", 2), title="Fizik")
        )
    return session


def _page_texts(pdf_bytes: bytes) -> list[str]:
    return [page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf_bytes)).pages]


# ===========================================================================
# Motor (booklet.py) — sayfa kuralları
# ===========================================================================


def test_header_page_indices_rules() -> None:
    assert booklet._header_page_indices(1) == {0}
    assert booklet._header_page_indices(2) == {0}  # ≤2 sayfa → yalnız 1. sayfa
    assert booklet._header_page_indices(4) == {0, 2}  # tek numaralı: 1 ve 3
    assert booklet._header_page_indices(5) == {0, 2, 4}


def _info() -> booklet.SessionInfo:
    return booklet.SessionInfo(
        school_name="Örnek Anadolu Lisesi",
        year_label="2026-2027",
        semester_label="1. Dönem",
        exam_name="1. Ortak Sınav",
        exam_date="16.11.2026",
    )


def test_room_package_header_and_pageno_rules() -> None:
    """>2 sayfa: başlık (öğrenci adı) tek numaralı sayfalarda; x/y her sayfada."""
    doc = booklet.CourseDoc(
        group_key="1:9",
        course_name="Coğrafya",
        pdf_bytes=_question_pdf(4),
        score_mode=ScoreMode.SINGLE_BOX,
        question_count=None,
    )
    spec = booklet.BookletSpec(
        full_name="Ayşe Ğüşiöç", class_label="9/A", student_number="101", group_key="1:9"
    )
    pkg = booklet.build_room_package("D-201", [spec], {"1:9": doc}, _info())
    texts = _page_texts(pkg.pdf_bytes)
    assert pkg.booklet_count == 1 and pkg.page_count == 4 and len(texts) == 4
    # Başlık: sayfa 1 ve 3'te öğrenci adı + okul adı; 2 ve 4'te YOK.
    assert "Ayşe Ğüşiöç" in texts[0] and "Ayşe Ğüşiöç" in texts[2]
    assert "Ayşe Ğüşiöç" not in texts[1] and "Ayşe Ğüşiöç" not in texts[3]
    assert "Örnek Anadolu" in texts[0]
    # Sayfa x/y HER sayfada; Türkçe soru metni korunmuş (1:1 birleştirme bozmaz).
    for i, text in enumerate(texts):
        assert f"Sayfa {i + 1} / 4" in text
        assert "ığüşöç" in text
    # PUAN kutusu (tek kutu modu) başlıklı sayfada.
    assert "PUAN" in texts[0]


def test_two_page_doc_header_only_first() -> None:
    doc = booklet.CourseDoc(
        group_key="1:9",
        course_name="Fizik",
        pdf_bytes=_question_pdf(2),
        score_mode=ScoreMode.QUESTION_TABLE,
        question_count=5,
    )
    spec = booklet.BookletSpec(
        full_name="Mehmet Can", class_label="10/A", student_number="201", group_key="1:9"
    )
    pkg = booklet.build_room_package("D-201", [spec], {"1:9": doc}, _info())
    texts = _page_texts(pkg.pdf_bytes)
    assert "Mehmet Can" in texts[0] and "Mehmet Can" not in texts[1]
    assert "TOPLAM" in texts[0]  # soru bazlı puan tablosu (K5)
    assert "S5" in texts[0]
    assert "Sayfa 2 / 2" in texts[1]


def test_room_package_seat_order_interleaves_courses() -> None:
    """Salon paketi oturma sırasında — kelebek karışımında dersler ardışık değişir."""
    session = _distributed_session(question_pages={"Coğrafya": 1, "Fizik": 1})
    run = services.request_booklet_run(session)
    assert run.status == BookletRunStatus.COMPLETED

    with zipfile.ZipFile(io.BytesIO(run.file.read())) as zf:
        names = zf.namelist()
        assert names == ["D-201.pdf"]
        texts = _page_texts(zf.read(names[0]))
    # 8 kitapçık × 1 sayfa; sıra SeatAssignment seat_no sırası.
    cografya_id = _course_id("Coğrafya")
    expected = [
        (a.full_name, "Coğrafya" if a.conflict_group.startswith(f"{cografya_id}:") else "Fizik")
        for a in SeatAssignment.objects.filter(session=session).order_by("seat_no")
    ]
    assert len(texts) == 8
    for text, (name, course) in zip(texts, expected, strict=True):
        assert name in text
        assert course in text
    # Kelebek karışımı: art arda hep aynı ders olmamalı (2 grup dengeli).
    courses_in_order = [course for _, course in expected]
    assert any(a != b for a, b in zip(courses_in_order, courses_in_order[1:], strict=False))


def _course_id(name: str) -> int:
    return int(Course.objects.get(name=name).pk)


def test_backup_copies_unnamed() -> None:
    doc = booklet.CourseDoc(
        group_key="1:9",
        course_name="Coğrafya",
        pdf_bytes=_question_pdf(1),
        score_mode=ScoreMode.SINGLE_BOX,
        question_count=None,
    )
    spec = booklet.BookletSpec(
        full_name="Ayşe Yılmaz", class_label="9/A", student_number="101", group_key="1:9"
    )
    pkg = booklet.build_room_package("D-201", [spec], {"1:9": doc}, _info(), backup_copies=2)
    assert pkg.booklet_count == 3
    texts = _page_texts(pkg.pdf_bytes)
    assert "Ayşe Yılmaz" in texts[0]
    assert "Ayşe Yılmaz" not in texts[1] and "Ayşe Yılmaz" not in texts[2]  # isimsiz
    assert "Coğrafya" in texts[1]  # başlık bandı var, ad boş


# ===========================================================================
# Servis — yükleme doğrulamaları + koşu ön koşulları
# ===========================================================================


def test_upload_validations() -> None:
    session = _distributed_session()
    sc = session.courses.first()
    assert sc is not None

    with pytest.raises(ValidationError, match="PDF değil"):
        services.upload_question_document(sc, file_bytes=b"degil")
    with pytest.raises(ValidationError, match="Boş dosya"):
        services.upload_question_document(sc, file_bytes=b"")
    with pytest.raises(ValidationError, match="soru sayısı"):
        services.upload_question_document(
            sc, file_bytes=_question_pdf(1), score_mode=ScoreMode.QUESTION_TABLE
        )

    doc = services.upload_question_document(sc, file_bytes=_question_pdf(3))
    assert doc.page_count == 3
    # Yeniden yükleme eskisini kapatır (tek canlı dosya).
    doc2 = services.upload_question_document(sc, file_bytes=_question_pdf(2))
    assert doc2.page_count == 2
    assert QuestionDocument.objects.filter(session_course=sc).count() == 1


def test_run_requires_distribution_and_all_documents() -> None:
    session = _distributed_session()  # soru dosyaları YOK
    with pytest.raises(ValidationError) as exc_info:
        services.request_booklet_run(session)
    message = str(exc_info.value)
    assert "Coğrafya" in message and "Fizik" in message  # ders adlarıyla
    assert "AD0" not in message  # öğrenci adı ASLA

    # Taslak oturumda koşu reddedilir.
    draft = oturum(name="Taslak Oturum")
    with pytest.raises(ValidationError, match="Önce dağıtım"):
        services.request_booklet_run(draft)


def test_sync_run_completes_and_failure_recorded() -> None:
    """KS senkron akış: koşu tek çağrıda COMPLETED; üretim hatası FAILED + PII'siz mesaj."""
    session = _distributed_session(question_pages={"Coğrafya": 2, "Fizik": 2})
    run = services.request_booklet_run(session)
    assert run.status == BookletRunStatus.COMPLETED
    assert run.completed_at is not None
    assert run.manifest["total_booklets"] == 8
    assert run.manifest["total_pages"] == 16

    # Soru dosyası diskten kaybolursa (bozulma senaryosu) koşu FAILED'a düşer,
    # hata mesajı öğrenci adı içermez ve istisna dışarı sızmaz.
    for qd in QuestionDocument.objects.filter(session_course__session=session):
        Path(qd.file.path).unlink()
    broken = services.request_booklet_run(session)
    assert broken.status == BookletRunStatus.FAILED
    assert broken.error_message != ""
    assert "AD0" not in broken.error_message


# Duvar saati tavanı. NEDEN 90 sn (tasarım hedefi ~30 sn): iddia ORTAMA bağlı —
# OYS Tur 703'te tam paket koşarken 30 sn eşiği sahte kırmızı verdi, izole
# koşuda 27.9 sn ile geçti. Eşiğin amacı mikro-optimizasyon ölçmek DEĞİL,
# katlanarak yavaşlamayı (ör. O(n²) regresyonu) yakalamak; 90 sn bunu hâlâ
# yakalar çünkü sağlıklı koşu ~25-30 sn. Asıl davranış güvencesi iş-ölçüsü
# iddiasıdır (booklet_count/page_count) — o ortamdan bağımsızdır.
BOOKLET_PERF_CEILING_SEC = 90


def test_performance_90_students_4_pages() -> None:
    """Kabul kriteri: 90 öğrenci × 4 sayfa tek salon paketi — katlanarak yavaşlamamalı."""
    doc = booklet.CourseDoc(
        group_key="1:9",
        course_name="Coğrafya",
        pdf_bytes=_question_pdf(4),
        score_mode=ScoreMode.QUESTION_TABLE,
        question_count=10,
    )
    specs = [
        booklet.BookletSpec(
            full_name=f"Öğrenci Ğüşiöç {i}",
            class_label="9/A",
            student_number=str(100 + i),
            group_key="1:9",
        )
        for i in range(90)
    ]
    started = time_mod.monotonic()
    pkg = booklet.build_room_package("Spor Salonu", specs, {"1:9": doc}, _info())
    elapsed = time_mod.monotonic() - started
    # Ortamdan BAĞIMSIZ iddia (asıl davranış güvencesi):
    assert pkg.booklet_count == 90 and pkg.page_count == 360
    # Ortama BAĞLI iddia (yalnız katlanarak yavaşlamayı yakalar — üstteki nota bak):
    assert elapsed < BOOKLET_PERF_CEILING_SEC, (
        f"{elapsed:.1f} sn (tavan {BOOKLET_PERF_CEILING_SEC} sn) — sağlıklı koşu ~25-30 sn. "
        "Makine boştayken de aşıyorsa gerçek regresyon olabilir."
    )


# ===========================================================================
# API — uçlar (authsuz tek kullanıcı; senkron akış)
# ===========================================================================


def test_api_upload_download_and_booklet_flow() -> None:
    session = _distributed_session()
    sc = session.courses.select_related("course").get(course__name="Coğrafya")
    sc2 = session.courses.select_related("course").get(course__name="Fizik")
    client = APIClient()

    up = client.post(
        f"/api/v1/exam-session-courses/{sc.pk}/question/",
        {"file": io.BytesIO(_question_pdf(2)), "score_mode": "SINGLE_BOX"},
        format="multipart",
    )
    assert up.status_code == 201
    assert up.data["page_count"] == 2

    meta = client.get(f"/api/v1/exam-session-courses/{sc.pk}/question/")
    assert meta.status_code == 200 and meta.data["course_name"] == "Coğrafya"

    down = client.get(f"/api/v1/exam-session-courses/{sc.pk}/question/download/")
    assert down.status_code == 200
    assert "soru_" in down["Content-Disposition"]

    client.post(
        f"/api/v1/exam-session-courses/{sc2.pk}/question/",
        {"file": io.BytesIO(_question_pdf(2))},
        format="multipart",
    )

    # Senkron: 201 yanıtı TAMAMLANMIŞ koşuyu taşır — polling yok.
    start = client.post(f"/api/v1/exam-sessions/{session.pk}/booklets/", {}, format="json")
    assert start.status_code == 201
    assert start.data["status"] == "COMPLETED"
    run_id = start.data["id"]

    listed = client.get(f"/api/v1/booklet-runs/?session={session.pk}")
    assert listed.status_code == 200 and listed.data["count"] == 1

    dl = client.get(f"/api/v1/booklet-runs/{run_id}/download/")
    assert dl.status_code == 200
    assert f"kitapciklar_oturum_{session.pk}.zip" in dl["Content-Disposition"]

    # Silme ucu: canlı dosya kapanır, üst veri 404'e döner.
    assert client.delete(f"/api/v1/exam-session-courses/{sc.pk}/question/").status_code == 204
    assert client.get(f"/api/v1/exam-session-courses/{sc.pk}/question/").status_code == 404


# ===========================================================================
# Ölçekleme yasağı + Word şablonu
# ===========================================================================


def test_no_scale_factor_in_booklet_module() -> None:
    """booklet modülünde SCALE_FACTOR adı bulunmamalı (OYS Tur 236 — ölçekleme yok)."""
    assert not hasattr(booklet, "SCALE_FACTOR")


def test_room_package_pages_are_a4() -> None:
    """build_room_package çıktısındaki her sayfa A4 genişliğinde (~595.276 puan)."""
    doc = booklet.CourseDoc(
        group_key="1:9",
        course_name="Matematik",
        pdf_bytes=_question_pdf(2),
        score_mode=ScoreMode.SINGLE_BOX,
        question_count=None,
    )
    spec = booklet.BookletSpec(
        full_name="Test Öğrenci", class_label="11/A", student_number="301", group_key="1:9"
    )
    pkg = booklet.build_room_package("D-101", [spec], {"1:9": doc}, _info())
    reader = PdfReader(io.BytesIO(pkg.pdf_bytes))
    for page in reader.pages:
        width = float(page.mediabox.width)
        assert abs(width - 595.276) < 1.0, f"Sayfa genişliği A4 değil: {width}"


def test_word_template_docx_structure() -> None:
    """build_question_template_docx() geçerli .docx üretir; 4 cm üst marj + A4."""
    from apps.sinav.word_template import build_question_template_docx

    docx_bytes = build_question_template_docx()
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as zf:
        names = zf.namelist()
        assert "word/document.xml" in names
        assert "[Content_Types].xml" in names
        doc_xml = zf.read("word/document.xml").decode("utf-8")

    # 4 cm üst marj = 2268 twip
    assert 'w:top="2268"' in doc_xml
    # A4 genişliği = 11906 twip
    assert 'w:w="11906"' in doc_xml


def test_api_question_template() -> None:
    """GET /exam-sessions/question-template/ → 200 + soru_sablonu.docx."""
    resp = APIClient().get("/api/v1/exam-sessions/question-template/")
    assert resp.status_code == 200
    assert "soru_sablonu.docx" in resp.get("Content-Disposition", "")


# ===========================================================================
# Bant geometrisi invariantı (tasarım §9) — şablon taraması
# ===========================================================================


def test_band_gecometry_invariant_40mm() -> None:
    """Bant üst 4mm + yükseklik 32mm ≤ 40mm; overlay sayfası 296mm (WeasyPrint tuzağı)."""
    sablon = (Path(settings.BASE_DIR) / "templates" / "sinav" / "booklet_overlay.html").read_text(
        encoding="utf-8"
    )
    top = re.search(r"\.band\s*{[^}]*top:\s*(\d+(?:\.\d+)?)mm", sablon, re.DOTALL)
    height = re.search(r"\.band\s*{[^}]*height:\s*(\d+(?:\.\d+)?)mm", sablon, re.DOTALL)
    assert top is not None and height is not None, "Bant top/height mm cinsinden tanımlı olmalı"
    assert (
        float(top.group(1)) + float(height.group(1)) <= 40.0
    ), "Bant Word şablonunun 4 cm üst marjını taşıyor — word_template ile birlikte değişmeli"
    # 297mm'de WeasyPrint fazladan boş sayfa üretebiliyor → overlay_idx kayar
    # ve YANLIŞ öğrencinin bandı yanlış kitapçığa biner (kasıtlı 296).
    assert "height: 296mm" in sablon
    assert "overflow: hidden" in sablon


# ===========================================================================
# Seviye-bazlı soru dosyası / ortak kitapçık kuralı (OYS Tur 241)
# ===========================================================================


def _two_level_session() -> ExamSession:
    """Aynı ders ("Matematik") iki seviyeyle, dağıtılmış oturum."""
    sube(9, "A", students=4, start_no=101)
    sube(10, "A", students=4, start_no=201)
    course = ders("Matematik", levels=[9, 10])
    session = oturum(name="Seviyeli Sınav")
    for level in (9, 10):
        services.add_session_course(
            session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=level
        )
    services.set_session_rooms(session, [{"room_id": salon("D-301", plan=PLAN_3X2_DOUBLE).pk}])
    services.distribute_session(session, seed=7)
    return session


def test_same_course_two_levels_use_distinct_question_docs() -> None:
    """KRİTİK (OYS Tur 241): Matematik 9 ve Matematik 10 FARKLI PDF basar.

    Eski course_id anahtarı seviyeleri ezerdi — grup anahtarı bunu ayırır.
    """
    session = _two_level_session()
    sc9 = session.courses.get(level=9)
    sc10 = session.courses.get(level=10)
    services.upload_question_document(sc9, file_bytes=_question_pdf(1, title="MAT-DOKUZ"))
    services.upload_question_document(sc10, file_bytes=_question_pdf(1, title="MAT-ON"))

    run = services.request_booklet_run(session)
    assert run.status == BookletRunStatus.COMPLETED

    with zipfile.ZipFile(io.BytesIO(run.file.read())) as zf:
        pdf_bytes = zf.read(zf.namelist()[0])
    pages = _page_texts(pdf_bytes)
    text_9 = "\n".join(p for p in pages if "9/A" in p)
    text_10 = "\n".join(p for p in pages if "10/A" in p)
    # 9. sınıf öğrencisinin sayfasında 9'un sorusu, 10'unkinde 10'un sorusu:
    assert "MAT-DOKUZ" in text_9 and "MAT-ON" not in text_9
    assert "MAT-ON" in text_10 and "MAT-DOKUZ" not in text_10


def test_booklet_run_missing_doc_listed_per_level() -> None:
    """Eksik dosya uyarısı seviye etiketiyle gelir; tek seviye yüklü olsa da öbürü eksiktir."""
    session = _two_level_session()
    sc9 = session.courses.get(level=9)
    services.upload_question_document(sc9, file_bytes=_question_pdf(1))
    with pytest.raises(ValidationError, match="Matematik — 10. Sınıf"):
        services.request_booklet_run(session)


def test_shared_booklet_single_file_rule() -> None:
    """Ortak kitapçıkta dosya TEK satıra yüklenir; kardeş satıra ikinci yükleme reddedilir."""
    sube(11, "A", students=2, start_no=301)
    sube(12, "A", students=2, start_no=401)
    course = ders("Seçmeli Mantık", levels=[11, 12])
    session = oturum(name="Ortak Kitapçık Sınavı")
    rows = [
        services.add_session_course(
            session,
            course_id=course.pk,
            participant_type=ParticipantType.LEVEL,
            level=level,
            shared_booklet=True,
        )
        for level in (11, 12)
    ]
    services.upload_question_document(rows[0], file_bytes=_question_pdf(1))
    with pytest.raises(ValidationError, match="tek satıra"):
        services.upload_question_document(rows[1], file_bytes=_question_pdf(1))


# ===========================================================================
# A4/yön doğrulaması + bant duman testi (OYS Tur 646)
# ===========================================================================


def _custom_page_pdf(width_pt: float, height_pt: float, *, rotate: int = 0) -> bytes:
    """Verilen boyutta (ve istenirse /Rotate'li) tek sayfalık PDF üretir."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    page = writer.add_blank_page(width=width_pt, height=height_pt)
    if rotate:
        page.rotate(rotate)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_upload_rejects_landscape_and_non_a4() -> None:
    session = _distributed_session()
    sc = session.courses.first()
    assert sc is not None

    # Yatay A4 → Türkçe red + Word şablonu yönlendirmesi.
    with pytest.raises(ValidationError, match="YATAY") as exc_info:
        services.upload_question_document(sc, file_bytes=_custom_page_pdf(841.89, 595.28))
    assert "Word şablonu" in str(exc_info.value)

    # Letter (612×792) → A4 değil.
    with pytest.raises(ValidationError, match="A4 boyutunda değil"):
        services.upload_question_document(sc, file_bytes=_custom_page_pdf(612, 792))

    # Dikey mediabox + /Rotate 90 → fiilen yatay, reddedilir (normalize).
    with pytest.raises(ValidationError, match="YATAY"):
        services.upload_question_document(
            sc, file_bytes=_custom_page_pdf(595.28, 841.89, rotate=90)
        )

    # Word küsuratı (±6pt tolerans) kabul edilir.
    doc = services.upload_question_document(sc, file_bytes=_custom_page_pdf(595.32, 841.92))
    assert doc.page_count == 1


def test_band_redesign_smoke_uzun_ad_ve_20_soru() -> None:
    """Bant: kurum kimliği satırı + uzun okul adı + 20 soruluk tablo taşmadan basılır."""
    SchoolConfig.objects.create(
        pk=SchoolConfig.SINGLETON_PK,
        school_name="Örnek Anadolu Lisesi Çok Programlı Fen ve Sosyal Bilimler Kampüsü",
        district="Hendek",
        province="Sakarya",
    )
    session = _distributed_session(question_pages={"Coğrafya": 1, "Fizik": 1})
    sc = session.courses.first()
    assert sc is not None
    services.upload_question_document(
        sc,
        file_bytes=_question_pdf(1, title="Coğrafya"),
        score_mode=ScoreMode.QUESTION_TABLE,
        question_count=20,
    )

    run = services.request_booklet_run(session)
    assert run.status == BookletRunStatus.COMPLETED

    with zipfile.ZipFile(io.BytesIO(run.file.read())) as zf:
        pdf_bytes = zf.read(zf.namelist()[0])
    first_pages = "\n".join(_page_texts(pdf_bytes))
    # Kurum kimliği satırı (T.C. · il · ilçe) + uzun okul adı bantta.
    assert "T.C." in first_pages and "Sakarya" in first_pages and "Hendek" in first_pages
    assert "Örnek Anadolu Lisesi" in first_pages
    # 20 soruluk tablo başlıkları (S1..S20 + TOPLAM) tek bantta.
    assert "S20" in first_pages and "TOPLAM" in first_pages
    # Tek-kutu modundaki ders PUAN kutusunu korur.
    assert "PUAN" in first_pages
