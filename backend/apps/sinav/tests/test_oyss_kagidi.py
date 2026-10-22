"""OYSS soru kâğıdına öğrenci bilgisi basımı (22.10.2026).

Kullanıcı isteği: EBA/OYSS'nin ürettiği soru kâğıdına öğrencinin adı basılsın;
A4'e basılınca yapraklar karışmasın diye 3. sayfanın üstüne de sınıf, numara ve
ad soyad gelsin. Testler GERÇEK kâğıdı kullanmaz (sınav sorusu gizlidir, depoya
girmez): kâğıdın düzeni — başlık satırları, TEK satırda üç alan etiketi, öteki
sayfalarda ~1,5 cm üst boşluk — WeasyPrint'le çalışma anında taklit edilir.
Konum ölçüsü programın kendi okuyucusuyla (`oyss_paper.page_glyphs`) yapılır.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.sinav import booklet, oyss_paper, services
from apps.sinav.models import ParticipantType, QuestionPaperFormat, ScoreMode
from apps.sinav.tests.oturum_yardim import ders, oturum, salon, sube
from shared.text import tr_upper

_SAYFA_CSS = """
@page { size: A4; margin: 15mm 14mm 18mm 14mm; }
body { font-family: "DejaVu Serif", serif; font-size: 10.5pt; margin: 0; }
.baslik { text-align: center; font-size: 13pt; line-height: 1.35; margin-left: 30mm; margin-right: 30mm; }
.alanlar { display: flex; justify-content: space-between; font-size: 11pt; margin-top: 9mm; }
.alanlar > span { white-space: nowrap; }
.cizgi { display: inline-block; border-bottom: 0.6pt solid #000; height: 9pt; }
.sayfa { page-break-after: always; }
"""


def _oyss_pdf(*, pages: int = 4, mark: bool = True, labels: bool = True) -> bytes:
    """OYSS kâğıdı düzeninde sentetik soru PDF'i (ad, okul ve sorular kurgudur)."""
    from weasyprint import HTML

    sinav = "1. Dönem 1. Ortak Yazılı Sınavı" if mark else "1. Dönem 1. Yazılı Sınavı"
    alanlar = (
        '<div class="alanlar">'
        '<span>Adı ve Soyadı: <span class="cizgi" style="width: 38mm"></span></span>'
        '<span>Sınıfı/Şubesi: <span class="cizgi" style="width: 12mm"></span></span>'
        '<span>Öğrenci Numarası: <span class="cizgi" style="width: 11mm"></span></span>'
        "</div>"
        if labels
        else ""
    )
    sayfalar = [
        f'<div class="sayfa"><div class="baslik">2026-2027 Eğitim Öğretim Yılı<br>{sinav}<br>'
        "9. Sınıf Coğrafya Dersi<br>Örnek Anadolu Lisesi</div>"
        f"{alanlar}<p><b>1.</b> Kurgu soru metni ığüşöç İĞÜŞÖÇ?</p></div>"
    ]
    for no in range(2, pages + 1):
        sayfalar.append(
            f'<div class="sayfa"><p><b>{no}.</b> Kurgu soru {no} — açıklayınız.</p></div>'
        )
    html = f"<html><head><style>{_SAYFA_CSS}</style></head><body>{''.join(sayfalar)}</body></html>"
    return bytes(HTML(string=html).write_pdf())


def _plain_pdf() -> bytes:
    """Program şablonuyla hazırlanmış (üst 4 cm boş) sıradan soru PDF'i."""
    from weasyprint import HTML

    return bytes(
        HTML(
            string='<html><body style="margin-top: 40mm; font-family: DejaVu Sans">'
            "<p>1) Soru metni — Adı ve Soyadı yazınız.</p></body></html>"
        ).write_pdf()
    )


def _info() -> booklet.SessionInfo:
    return booklet.SessionInfo(
        school_name="Örnek Anadolu Lisesi",
        year_label="2026-2027",
        semester_label="1. Dönem",
        exam_name="1. Ortak Sınav",
        exam_date="03.11.2026",
    )


def _lines(pdf_bytes: bytes, page_index: int) -> list[oyss_paper._Line]:
    page = PdfReader(io.BytesIO(pdf_bytes)).pages[page_index]
    return oyss_paper._lines(oyss_paper.page_glyphs(page))


def _package(pdf: bytes, spec: booklet.BookletSpec, *, backup: int = 0) -> booklet.RoomPackage:
    doc = booklet.CourseDoc(
        group_key="1:9",
        course_name="Coğrafya",
        pdf_bytes=pdf,
        score_mode=ScoreMode.SINGLE_BOX,
        question_count=None,
        oyss_paper=oyss_paper.detect(pdf),
    )
    return booklet.build_room_package("D-201", [spec], {"1:9": doc}, _info(), backup_copies=backup)


_AYSE = booklet.BookletSpec(
    full_name="Ayşe Ğüşiöç Yılmaz", class_label="9/A", student_number="1234", group_key="1:9"
)


# ===========================================================================
# Tanıma
# ===========================================================================


def test_oyss_kagidi_taninir_ve_alanlar_soldan_saga_dizilir() -> None:
    paper = oyss_paper.detect(_oyss_pdf())
    assert paper is not None and paper.has_fields
    assert paper.name is not None and paper.class_label is not None and paper.number is not None
    # Üç alan aynı satırda, birbirine binmeden soldan sağa.
    assert paper.name.baseline == paper.class_label.baseline == paper.number.baseline
    assert paper.name.x0 < paper.name.x1 < paper.class_label.x0 < paper.class_label.x1
    assert paper.class_label.x1 < paper.number.x0 < paper.number.x1 <= paper.right + 0.01
    # Kimlik satırı alabilecek sayfaların (1 ve 3) ilk metni ölçüldü.
    assert {index for index, _ in paper.text_tops} == {0, 2}


def test_sablon_pdf_ve_isaretsiz_kagit_oyss_sayilmaz() -> None:
    assert oyss_paper.detect(_plain_pdf()) is None
    # Etiketler var ama "Ortak Yazılı Sınav" yok → okulun kendi kâğıdı, OYSS değil.
    assert oyss_paper.detect(_oyss_pdf(mark=False)) is None
    # Bozuk girdi yüklemeyi düşürmez: tanıma None döner.
    assert oyss_paper.detect(b"%PDF-1.4 bozuk") is None


def test_konum_okuyucusu_turkce_metni_cozer() -> None:
    metin = " ".join(line.text for line in _lines(_oyss_pdf(), 0))
    assert "ÖRNEK ANADOLU LİSESİ" in metin
    assert "ADI VE SOYADI:" in metin and "ÖĞRENCİ NUMARASI:" in metin
    assert "IĞÜŞÖÇ İĞÜŞÖÇ" in metin


# ===========================================================================
# Basım
# ===========================================================================


def test_oyss_kagidinda_bilgiler_kendi_alanlarina_basilir() -> None:
    pdf = _oyss_pdf()
    paper = oyss_paper.detect(pdf)
    assert paper is not None and paper.name is not None
    pkg = _package(pdf, _AYSE)
    assert pkg.page_count == 4

    satir = next(
        line for line in _lines(pkg.pdf_bytes, 0) if abs(line.baseline - paper.name.baseline) < 3
    )
    # Değerler etiketlerle AYNI taban çizgisinde ve sırasıyla etiketlerin ardında.
    assert (
        "ADI VE SOYADI: AYŞE ĞÜŞİÖÇ YILMAZ SINIFI/ŞUBESİ: 9/A ÖĞRENCİ NUMARASI: 1234" in satir.text
    )
    # Alan sınırını aşan yazı yukarıdaki sıra denetimini bozardı (etiketle iç içe geçer).
    ad = [g for g in satir.glyphs if paper.name.x0 - 0.5 <= g.x0 < paper.name.x1]
    assert ad, "ad alanına yazı basılmadı"
    assert max(abs(g.baseline - paper.name.baseline) for g in ad) < 0.5
    assert max(g.x1 for g in ad) <= paper.name.x1 + 0.5
    # Bant ve sayfa numarası YOK: kâğıdın başlığı örtülmez, kendi numarası yeter.
    tum_metin = " ".join(line.text for i in range(4) for line in _lines(pkg.pdf_bytes, i))
    assert "SAYFA" not in tum_metin and "PUAN" not in tum_metin
    assert "ÖRNEK ANADOLU LİSESİ" in tum_metin  # kâğıdın kendi başlığı yerinde


def test_ucuncu_sayfanin_ustune_kimlik_satiri_basilir() -> None:
    pdf = _oyss_pdf()
    pkg = _package(pdf, _AYSE)
    kimlik = "SINIFI/ŞUBESİ: 9/A · ÖĞRENCİ NUMARASI: 1234 · ADI VE SOYADI: AYŞE ĞÜŞİÖÇ YILMAZ"

    ucuncu = _lines(pkg.pdf_bytes, 2)
    assert ucuncu[0].text == kimlik  # en üst satır kimlik satırı
    assert ucuncu[1].text.startswith("3.")  # kâğıdın ilk satırı altında, yerinde
    ust_kenar = max(g.baseline + g.size for g in ucuncu[1].glyphs)
    alt_kenar = min(g.baseline - 0.25 * g.size for g in ucuncu[0].glyphs)
    assert alt_kenar - ust_kenar > 2, "kimlik satırı sayfanın ilk metnine biniyor"
    sayfa_ust = float(PdfReader(io.BytesIO(pkg.pdf_bytes)).pages[2].mediabox.height)
    assert sayfa_ust - ucuncu[0].baseline >= booklet._OYSS_STRIP_BASELINE_MIN

    # 2. ve 4. sayfa (çift yüzlü basımda 1. ve 3. sayfanın arkası) dokunulmaz.
    for index in (1, 3):
        metin = " ".join(line.text for line in _lines(pkg.pdf_bytes, index))
        assert "AYŞE" not in metin and "1234" not in metin


def test_bes_sayfada_besinci_sayfa_da_kimlik_alir_iki_sayfada_yalniz_alanlar() -> None:
    bes = _package(_oyss_pdf(pages=5), _AYSE)
    for index, beklenen in ((2, True), (3, False), (4, True)):
        metin = " ".join(line.text for line in _lines(bes.pdf_bytes, index))
        assert ("1234" in metin) is beklenen, index
    iki = _package(_oyss_pdf(pages=2), _AYSE)
    assert "AYŞE" not in " ".join(line.text for line in _lines(iki.pdf_bytes, 1))


def test_isimsiz_yedek_kitapcikta_alanlar_bos_kalir() -> None:
    pdf = _oyss_pdf()
    pkg = _package(pdf, _AYSE, backup=1)
    assert pkg.booklet_count == 2 and pkg.page_count == 8
    for index in range(4, 8):
        assert [line.text for line in _lines(pkg.pdf_bytes, index)] == [
            line.text for line in _lines(pdf, index - 4)
        ]


def test_uzun_ad_kuculur_ve_alanina_sigar() -> None:
    pdf = _oyss_pdf()
    paper = oyss_paper.detect(pdf)
    assert paper is not None and paper.name is not None and paper.class_label is not None
    uzun = booklet.BookletSpec(
        full_name="Abdurrahman Muhammed Karaosmanoğlu",
        class_label="11/AB",
        student_number="12345",
        group_key="1:9",
    )
    pkg = _package(pdf, uzun)
    satir = next(
        line for line in _lines(pkg.pdf_bytes, 0) if abs(line.baseline - paper.name.baseline) < 3
    )
    assert "ABDURRAHMAN MUHAMMED KARAOSMANOĞLU SINIFI/ŞUBESİ: 11/AB" in satir.text
    ad = [g for g in satir.glyphs if paper.name.x0 - 0.5 <= g.x0 < paper.name.x1]
    assert max(g.x1 for g in ad) <= paper.name.x1 + 0.5
    assert max(g.size for g in ad) < booklet._OYSS_FIELD_PT  # küçüldü


def test_alan_konumu_bulunamayan_oyss_kagidinda_kimlik_satiri_birinci_sayfaya() -> None:
    """Metinden OYSS diye tanınan ama etiket satırı konumlanamayan kâğıt: bant değil şerit."""
    paper = oyss_paper.OyssPaper(
        name=None, class_label=None, number=None, left=40.0, right=555.0, text_tops=((0, 800.0),)
    )
    marks = booklet._oyss_marks(paper, _AYSE, 0, 4)
    assert len(marks) == 1 and marks[0]["text"].startswith("Sınıfı/Şubesi: 9/A")
    assert booklet._oyss_marks(paper, _AYSE, 1, 4) == []
    assert float(marks[0]["top"]) > 0


def test_sablon_kagidi_eski_bantla_basilmaya_devam_eder() -> None:
    """oyss_paper None → eski davranış birebir (bant + Sayfa x / y)."""
    doc = booklet.CourseDoc(
        group_key="1:9",
        course_name="Coğrafya",
        pdf_bytes=_plain_pdf(),
        score_mode=ScoreMode.SINGLE_BOX,
        question_count=None,
    )
    pkg = booklet.build_room_package("D-201", [_AYSE], {"1:9": doc}, _info())
    metin = PdfReader(io.BytesIO(pkg.pdf_bytes)).pages[0].extract_text() or ""
    assert "Sayfa 1 / 1" in metin and "PUAN" in metin and "Ayşe Ğüşiöç Yılmaz" in metin


# ===========================================================================
# Yükleme + uçtan uca üretim
# ===========================================================================


@pytest.mark.django_db
def test_yukleme_bicimi_kaydeder_ve_kitapcik_alanlara_basilir() -> None:
    sube(9, "A", students=2, start_no=101)
    cografya = ders("Coğrafya", levels=[9])
    session = oturum()
    sc = services.add_session_course(
        session, course_id=cografya.pk, participant_type=ParticipantType.LEVEL, level=9
    )
    services.set_session_rooms(session, [{"room_id": salon("D-201").pk}])
    services.distribute_session(session, seed=7)

    duz = services.upload_question_document(sc, file_bytes=_plain_pdf())
    assert duz.paper_format == QuestionPaperFormat.TEMPLATE
    doc = services.upload_question_document(sc, file_bytes=_oyss_pdf())
    assert doc.paper_format == QuestionPaperFormat.OYSS

    meta = APIClient().get(f"/api/v1/exam-session-courses/{sc.pk}/question/").json()
    assert meta["paper_format"] == "OYSS"

    run = services.request_booklet_run(session)
    assert run.error_message == ""
    with run.file.open("rb") as fh, zipfile.ZipFile(fh) as zf:
        salon_pdf = zf.read(zf.namelist()[0])
    adlar = {tr_upper(a.full_name) for a in session.seat_assignments.all()}
    birinci_sayfa = " ".join(line.text for line in _lines(salon_pdf, 0))
    assert any(f"ADI VE SOYADI: {ad} SINIFI/ŞUBESİ: 9/A" in birinci_sayfa for ad in adlar)
