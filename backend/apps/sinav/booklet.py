"""Kişiselleştirilmiş soru kitapçığı motoru (T7 — ADR-0016 karar 5).

Yöntem: WeasyPrint başlık bandı OVERLAY'i + pypdf bindirme
(ReportLab REDDEDİLDİ — yeni bağımlılık yok, mevcut altyapı kullanılır).

Sayfa kuralları (yol haritası §6, madde 5):
- ≤ 2 sayfa → başlık yalnız 1. sayfada; > 2 sayfa → her TEK numaralı sayfada
  (öğrenci bloğu dâhil — kağıtlar ayrılırsa sahibi belli olur).
- "Sayfa x / y" TÜM sayfalara basılır.
- ÖLÇEKLEME YOK (Tur 236, talep 5): soru PDF'i hiç küçültülmez; başlık bandı
  sayfanın üst 4 cm'lik alanına basılır. Öğretmen soruyu indirilen Word
  şablonuyla (üst marj 4 cm) hazırlar — bant içerikle çakışmaz.

Performans: overlay sayfaları SALON BAŞINA TEK WeasyPrint render'ında üretilir
(öğrenci başına render edilmez) — 90 öğrenci × 4 sayfa hedefi < 30 sn.

Bu modül saf veri sınıflarıyla çalışır; DB erişimi services katmanındadır.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BookletSpec:
    """Tek öğrencinin kitapçık tanımı (sıra: salon oturma sırası).

    `group_key` = çakışma grubu anahtarı ("<course_id>:<level>" / "<course_id>:*").
    Tur 241: aynı dersin farklı seviyeleri FARKLI soru dosyası kullanır — eski
    course_id anahtarı seviyeleri ezerdi.
    """

    full_name: str
    class_label: str
    student_number: str
    group_key: str


@dataclass(frozen=True)
class CourseDoc:
    """Bir grubun (ders+seviye) soru dosyası + başlık ayarları."""

    group_key: str
    course_name: str  # başlıkta görünen ad (seviye etiketi dahil edilebilir)
    pdf_bytes: bytes
    score_mode: str  # ScoreMode değeri
    question_count: int | None


@dataclass(frozen=True)
class SessionInfo:
    """Başlık üst bloğu (madde 5) — okul/yıl/dönem/sınav/tarih.

    `district`/`province` (Tur 646, FAZ B1): bant sol bloğundaki kurum kimliği
    satırı ("T.C. · il · ilçe") için — varsayılanlı (boşsa satır kısalır;
    letterhead kimliğinden dolar, eski çağıranlar kırılmaz).
    """

    school_name: str
    year_label: str
    semester_label: str
    exam_name: str
    exam_date: str  # gg.aa.yyyy
    district: str = ""
    province: str = ""


@dataclass
class RoomPackage:
    """Salon çıktısı: birleşik PDF + sayım manifesti (PII içermez)."""

    room_name: str
    pdf_bytes: bytes
    booklet_count: int
    page_count: int
    missing_groups: list[str] = field(default_factory=list)


#: A4 nokta ölçüleri (pypdf koordinatları).
_A4_W, _A4_H = 595.276, 841.89


def _header_page_indices(page_count: int) -> set[int]:
    """Başlık bandı basılacak sayfa indeksleri (0 tabanlı; kurallar §6)."""
    if page_count <= 2:
        return {0}
    return {i for i in range(page_count) if i % 2 == 0}  # 1, 3, 5... (tek numaralı)


def _overlay_pages_context(
    specs: list[BookletSpec],
    docs: dict[str, CourseDoc],
    page_counts: dict[str, int],
) -> list[dict[str, object]]:
    """Şablonun `pages` bağlamı: her (öğrenci, sayfa) için bir overlay sayfası."""
    pages: list[dict[str, object]] = []
    for spec in specs:
        doc = docs[spec.group_key]
        page_total = page_counts[spec.group_key]
        headers = _header_page_indices(page_total)
        for idx in range(page_total):
            pages.append(
                {
                    "header": idx in headers,
                    "full_name": spec.full_name,
                    "class_label": spec.class_label,
                    "student_number": spec.student_number,
                    "course_name": doc.course_name,
                    "score_mode": doc.score_mode,
                    "question_count": doc.question_count,
                    "question_range": range(1, (doc.question_count or 0) + 1),
                    "page_no": idx + 1,
                    "page_total": page_total,
                }
            )
    return pages


def _render_overlay_pdf(
    specs: list[BookletSpec],
    docs: dict[str, CourseDoc],
    info: SessionInfo,
    page_counts: dict[str, int],
) -> bytes:
    """Salonun TÜM overlay sayfalarını tek WeasyPrint render'ında üretir."""
    from django.template.loader import render_to_string
    from weasyprint import HTML  # tembel import — ağır bağımlılık

    # Kurum kimliği satırı (Tur 646): boş parçalar atlanır — "T.C. · İl · İlçe".
    identity_line = " · ".join(p for p in ("T.C.", info.province, info.district) if p)
    html = render_to_string(
        "sinav/booklet_overlay.html",
        {
            "pages": _overlay_pages_context(specs, docs, page_counts),
            "school_name": info.school_name,
            "year_label": info.year_label,
            "semester_label": info.semester_label,
            "exam_name": info.exam_name,
            "exam_date": info.exam_date,
            "identity_line": identity_line,
        },
    )
    return bytes(HTML(string=html).write_pdf())


def build_room_package(
    room_name: str,
    specs: list[BookletSpec],
    docs: dict[str, CourseDoc],
    info: SessionInfo,
    *,
    backup_copies: int = 0,
) -> RoomPackage:
    """Salonun birleşik PDF'ini üretir (oturma sırasında kişisel kitapçıklar).

    `backup_copies` > 0 ise sona o kadar İSİMSİZ kitapçık eklenir (her gruptan
    döngüyle — tek gruplu salonda hep o grup). Soru dosyası eksik grupların
    öğrencileri atlanır ve `missing_groups`'a yazılır (sessiz yutulmaz).
    """
    from pypdf import PdfReader, PdfWriter

    available = [s for s in specs if s.group_key in docs]
    missing = sorted({s.group_key for s in specs} - set(docs))

    # İsimsiz yedekler: salonda görülen gruplardan sırayla.
    backup_specs: list[BookletSpec] = []
    seen_groups = list(dict.fromkeys(s.group_key for s in available))
    for i in range(backup_copies):
        if not seen_groups:
            break
        backup_specs.append(
            BookletSpec(
                full_name="",
                class_label="",
                student_number="",
                group_key=seen_groups[i % len(seen_groups)],
            )
        )
    all_specs = [*available, *backup_specs]

    writer = PdfWriter()
    total_pages = 0
    if all_specs:
        readers: dict[str, PdfReader] = {
            key: PdfReader(io.BytesIO(doc.pdf_bytes)) for key, doc in docs.items()
        }
        page_counts = {key: len(r.pages) for key, r in readers.items()}
        overlay_reader = PdfReader(
            io.BytesIO(_render_overlay_pdf(all_specs, docs, info, page_counts))
        )
        overlay_idx = 0
        for spec in all_specs:
            reader = readers[spec.group_key]
            for page in reader.pages:
                # Soru sayfasının kopyası writer'a alınır; orijinal reader bozulmaz.
                # Ölçekleme YOK (Tur 236) — içerik 1:1, A4 tuvale sol-alt hizalı;
                # üst 4 cm'lik bant alanını Word şablonu marjı garanti eder.
                new_page = writer.add_blank_page(width=_A4_W, height=_A4_H)
                new_page.merge_page(page)
                new_page.merge_page(overlay_reader.pages[overlay_idx])
                overlay_idx += 1
                total_pages += 1

    buffer = io.BytesIO()
    writer.write(buffer)
    return RoomPackage(
        room_name=room_name,
        pdf_bytes=buffer.getvalue(),
        booklet_count=len(all_specs),
        page_count=total_pages,
        missing_groups=missing,
    )


def package_zip(packages: list[RoomPackage]) -> bytes:
    """Salon PDF'lerini tek ZIP'te toplar (dosya adı = salon adı)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for pkg in packages:
            safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in pkg.room_name)
            zf.writestr(f"{safe or 'salon'}.pdf", pkg.pdf_bytes)
    return buffer.getvalue()
