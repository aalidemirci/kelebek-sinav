"""Öğretmen soru kâğıdı Word şablonu (Tur 236 — talep 5).

.docx = ZIP içinde üç küçük XML parçası ([Content_Types].xml, _rels/.rels,
word/document.xml). python-docx bilinçli olarak EKLENMEDİ (booklet.py'deki
ReportLab reddiyle aynı gerekçe — yeni bağımlılık yok); stdlib `zipfile`
yeterli. Emsal: apps/core/views/imports.py PersonnelImportTemplateView
(boş .xlsx'i çalışma anında üretir).

Şablon: A4 dikey, ÜST MARJ 4 cm (2268 twip) — kitapçık motoru başlık bandını
sayfanın üst 4 cm'ine bastığından (booklet_overlay.html invariantı
top+height ≤ 40mm) öğretmenin içeriği bantla çakışmaz. Diğer marjlar 2 cm.
"""

from __future__ import annotations

import io
import zipfile

#: 1 mm ≈ 56.693 twip (1/20 punto). 40 mm → 2268, 20 mm → 1134.
_TOP_MARGIN_TWIP = 2268
_OTHER_MARGIN_TWIP = 1134
#: A4 (mm → twip): 210×297.
_PAGE_W_TWIP = 11906
_PAGE_H_TWIP = 16838

_CONTENT_TYPES_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" '
    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    "</Types>"
)

_RELS_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/>'
    "</Relationships>"
)

#: Şablondaki yönerge paragrafları (öğretmen yazmaya başlarken siler).
#: Tur 646 (FAZ B1): 6 kurallık genişletme — SorularPaneli "Şablon Kuralları"
#: kartı AYNI 6 maddeyi gösterir (iki liste birlikte güncellenir).
_GUIDE_PARAGRAPHS = (
    "SORU KÂĞIDI ŞABLONU — sayfanın üst 4 cm'lik boşluğu sisteme ayrılmıştır: "
    "okul başlık bandı (kurum kimliği, sınav bilgisi, öğrenci adı/sınıfı/numarası "
    "ve puan bölümü) basım sırasında bu alana yerleştirilir. Kâğıt 2 sayfayı "
    "aşarsa bant tek numaralı sayfalara basılır; üst boşluk her sayfada korunur.",
    "KURAL 1 — SAYFA: A4 DİKEY kalır; üst kenar boşluğuna (4 cm) DOKUNMAYIN. "
    "Diğer kenar boşlukları 2 cm'dir ve serbestçe kullanılabilir. Yatay sayfa "
    "içeren PDF sistemce REDDEDİLİR.",
    "KURAL 2 — YAZI TİPİ: Times New Roman, Arial veya Calibri kullanın ve PDF'e "
    "aktarırken yazı tipini GÖMÜN (varsayılan dışa aktarma gömer). Gövde metni "
    "en az 11 punto, şıklar en az 10 punto olmalıdır.",
    "KURAL 3 — GÖRSEL: Şekil/grafikler en az 300 dpi çözünürlükte ve SALT "
    "SİYAH-BEYAZ olmalıdır; açık gri tonlar fotokopide kaybolur — KULLANMAYIN.",
    "KURAL 4 — SAYFA NUMARASI: Belgeye sayfa numarası EKLEMEYİN; sistem her "
    "kitapçığa 'Sayfa x / y' numarasını basım sırasında kendisi basar.",
    "KURAL 5 — DOSYA: Yalnız PDF yüklenir (en çok 20 MB, tüm sayfalar A4 dikey). "
    "Bitirince PDF olarak dışa aktarın (Dosya → Farklı Kaydet → PDF) ve "
    "sistemdeki Soru Dosyaları panelinden yükleyin.",
    "KURAL 6 — TEMİZLİK: Yazmaya başlamadan önce bu yönerge paragraflarının "
    "tamamını silin; sorularınızı bu satırdan itibaren yazın.",
)


def _escape(text: str) -> str:
    """XML metin kaçışı (yalnız &, <, > — yönergelerde başka özel yok)."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _paragraph(text: str) -> str:
    """Tek yönerge paragrafı — 8 punto sonrası boşluklu gövde metni."""
    return (
        '<w:p><w:pPr><w:spacing w:after="160"/></w:pPr>'
        f'<w:r><w:t xml:space="preserve">{_escape(text)}</w:t></w:r></w:p>'
    )


def _document_xml() -> str:
    paragraphs = "".join(_paragraph(p) for p in _GUIDE_PARAGRAPHS)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        f"{paragraphs}"
        "<w:sectPr>"
        f'<w:pgSz w:w="{_PAGE_W_TWIP}" w:h="{_PAGE_H_TWIP}"/>'
        f'<w:pgMar w:top="{_TOP_MARGIN_TWIP}" w:right="{_OTHER_MARGIN_TWIP}" '
        f'w:bottom="{_OTHER_MARGIN_TWIP}" w:left="{_OTHER_MARGIN_TWIP}" '
        'w:header="709" w:footer="709" w:gutter="0"/>'
        "</w:sectPr>"
        "</w:body>"
        "</w:document>"
    )


def build_question_template_docx() -> bytes:
    """4 cm üst marjlı, yönerge metinli boş soru şablonunu (.docx) üretir."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES_XML)
        zf.writestr("_rels/.rels", _RELS_XML)
        zf.writestr("word/document.xml", _document_xml())
    return buffer.getvalue()
