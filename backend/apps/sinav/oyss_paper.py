"""OYSS soru kâğıdını tanıma ve öğrenci alanlarının konumu (22.10.2026).

Bakanlığın Ortak Yazılı Sınav Sistemi (OYSS, eba.gov.tr) sınav kâğıdını KENDİ
başlığıyla üretir: 1. sayfada logo, yıl/dönem/ders/okul satırları ve altında TEK
satırda "Adı ve Soyadı:", "Sınıfı/Şubesi:", "Öğrenci Numarası:" alanları; öteki
sayfaların üstünde ~1,5 cm boşluk; altta kâğıdın kendi "Sayfa x / y" numarası.
Programın kitapçık bandı (üst 4 cm — Word şablonu sözleşmesi) bu kâğıtta
Bakanlığın başlığını ÖRTERDİ. Bu modül kâğıdı tanır ve alanların yerini verir;
basım `booklet`tedir (öğrenci bilgisi kâğıdın kendi alanlarına, 3., 5. … sayfanın
üstüne kimlik satırı — A4'e çift yüzlü basımda ikinci yaprak karışmasın diye).

Konumu neden kendi okuyucumuz çıkarır? pypdf'in hazır yolları gerçek kâğıtta
yetmedi (22.10.2026, EBA'dan Chrome'la kaydedilmiş PDF): `extract_text`
ziyaretçisi boşlukla başlayan parçalara sıfırlanmış matris veriyor (etiketler
(0, 0)'da görünüyor), layout kipi Skia'nın derin `q`/`cm` akışında özyineleme
sınırına çarpıyor. Burada içerik akışı pypdf'in AÇIK API'siyle (`ContentStream`,
dizeler ham bayt) gezilir; konum PDF metin durumu kurallarıyla (Tm/Td/TJ + glif
genişliği) hesaplanır, Unicode ToUnicode tablosundan çözülür. Yeni bağımlılık yok.

Saf modüldür (DB yok). Tanıma bir KOLAYLIKTIR: hata yutulur ve `None` döner —
bozuk ya da tanınmayan PDF yüklemeyi veya kitapçık üretimini düşürmez.
"""

from __future__ import annotations

import io
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from shared.text import tr_upper

logger = logging.getLogger("kelebek_sinav.sinav")

Matrix = tuple[float, float, float, float, float, float]
_IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

#: Glifin taban çizgisinden üst kenarına oranı (punto başına) — en üst metnin
#: kabaca üst kenarı için (Times/DejaVu büyük harf ≈ 0,72-0,76).
_ASCENT = 0.8
#: Aynı satır sayılan taban çizgisi farkı (pt).
_LINE_TOL = 1.0
#: Form XObject iç içeliği sınırı (döngüye karşı sigorta).
_MAX_FORM_DEPTH = 8

#: 1. sayfadaki alan etiketleri — `tr_upper` + boşluk sadeleştirmesinden sonra.
_LABELS: dict[str, re.Pattern[str]] = {
    "name": re.compile(r"ADI (VE )?SOYADI ?:?"),
    "class_label": re.compile(r"SINIFI/ŞUBESİ ?:?"),
    "number": re.compile(r"(ÖĞRENCİ )?NUMARASI ?:?"),
}
#: Kâğıdın OYSS'den geldiğini gösteren başlık sözü (1. sayfada).
_OYSS_MARK = "ORTAK YAZILI SINAV"


@dataclass(frozen=True)
class Glyph:
    """Sayfadaki tek glif: metni, yatay kapsamı, taban çizgisi ve etkin puntosu.

    Koordinatlar PDF kullanıcı uzayındadır (sol-alt köşe, y yukarı, pt).
    """

    text: str
    x0: float
    x1: float
    baseline: float
    size: float


@dataclass(frozen=True)
class FieldSlot:
    """Bir öğrenci alanının yazı yeri: [x0, x1] aralığı + etiketin taban çizgisi."""

    x0: float
    x1: float
    baseline: float


@dataclass(frozen=True)
class OyssPaper:
    """Tanınan OYSS kâğıdı (PDF kullanıcı uzayı, alttan pt).

    `name`/`class_label`/`number` alan yerleri bulunamadıysa None'dır (kâğıt
    metinden OYSS diye tanındı ama etiket satırı konumlanamadı): o zaman kimlik
    satırı 1. sayfanın da üstüne basılır — bant ASLA basılmaz, Bakanlığın
    başlığını örterdi. `text_tops`: sayfa indeksi (0 tabanlı) → o sayfadaki en
    üst metnin üst kenarı; yalnız kimlik satırı alabilecek sayfalar ölçülür.
    """

    name: FieldSlot | None
    class_label: FieldSlot | None
    number: FieldSlot | None
    left: float
    right: float
    text_tops: tuple[tuple[int, float], ...] = ()

    @property
    def has_fields(self) -> bool:
        return None not in (self.name, self.class_label, self.number)

    def text_top(self, page_index: int) -> float | None:
        return dict(self.text_tops).get(page_index)


# ---------------------------------------------------------------------------
# İçerik akışı okuyucusu
# ---------------------------------------------------------------------------


def _mul(m: Matrix, n: Matrix) -> Matrix:
    """PDF matris çarpımı m × n (önce m, sonra n uygulanır)."""
    return (
        m[0] * n[0] + m[1] * n[2],
        m[0] * n[1] + m[1] * n[3],
        m[2] * n[0] + m[3] * n[2],
        m[2] * n[1] + m[3] * n[3],
        m[4] * n[0] + m[5] * n[2] + n[4],
        m[4] * n[1] + m[5] * n[3] + n[5],
    )


def _resolve(obj: Any) -> Any:
    return obj.get_object() if hasattr(obj, "get_object") else obj


_HEX = re.compile(rb"<([0-9A-Fa-f]*)>")
_BFRANGE = re.compile(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(\[[^\]]*\]|<[0-9A-Fa-f]*>)")


def _utf16(hex_bytes: bytes) -> str:
    raw = bytes.fromhex(hex_bytes.decode("ascii"))
    try:
        return raw.decode("utf-16-be")
    except UnicodeDecodeError:
        return ""


def _parse_tounicode(data: bytes) -> dict[int, str]:
    """ToUnicode CMap'inin `bfchar`/`bfrange` eşlemeleri: kod → Unicode metin."""
    table: dict[int, str] = {}
    for block in re.findall(rb"beginbfchar(.*?)endbfchar", data, re.S):
        hexes = _HEX.findall(block)
        for src, dst in zip(hexes[0::2], hexes[1::2], strict=False):
            if src:
                table[int(src, 16)] = _utf16(dst)
    for block in re.findall(rb"beginbfrange(.*?)endbfrange", data, re.S):
        for match in _BFRANGE.finditer(block):
            low, high, dst = int(match.group(1), 16), int(match.group(2), 16), match.group(3)
            if high - low > 0xFFFF:
                continue  # bozuk aralık — bellek sigortası
            if dst.startswith(b"["):
                for offset, item in enumerate(_HEX.findall(dst)):
                    table[low + offset] = _utf16(item)
            elif len(dst) > 2:
                base = bytes.fromhex(dst[1:-1].decode("ascii"))
                start = int.from_bytes(base, "big")
                for offset in range(high - low + 1):
                    value = (start + offset).to_bytes(len(base), "big")
                    table[low + offset] = _utf16(value.hex().encode("ascii"))
    return table


class _Font:
    """Bir yazı tipi kaynağının konum için gerekenleri: kod genişliği ve Unicode."""

    def __init__(self, font_dict: Any) -> None:
        font = _resolve(font_dict)
        self.two_byte = str(font.get("/Subtype")) == "/Type0"
        self.widths: dict[int, float] = {}
        self.default_width = 0.0
        # Glif uzayı → metin uzayı: Type3 kendi /FontMatrix'ini taşır, ötekiler 1/1000.
        self.scale = 0.001
        if str(font.get("/Subtype")) == "/Type3" and font.get("/FontMatrix") is not None:
            self.scale = float(_resolve(font["/FontMatrix"])[0])
        if self.two_byte:
            descendant = _resolve(_resolve(font["/DescendantFonts"])[0])
            self.default_width = float(descendant.get("/DW", 1000))
            self._read_cid_widths(_resolve(descendant.get("/W", [])))
        else:
            first = int(font.get("/FirstChar", 0))
            for offset, width in enumerate(_resolve(font.get("/Widths", [])) or []):
                self.widths[first + offset] = float(_resolve(width))
            descriptor = _resolve(font.get("/FontDescriptor"))
            if descriptor is not None:
                self.default_width = float(descriptor.get("/MissingWidth", 0))
        to_unicode = font.get("/ToUnicode")
        self.unicode = _parse_tounicode(_resolve(to_unicode).get_data()) if to_unicode else {}

    def _read_cid_widths(self, array: Any) -> None:
        """CID yazı tipinin /W dizisi: `c [w…]` ya da `c_ilk c_son w` biçimleri."""
        items = [_resolve(item) for item in array]
        i = 0
        while i + 1 < len(items):
            first, nxt = int(items[i]), items[i + 1]
            if isinstance(nxt, list):
                for offset, width in enumerate(nxt):
                    self.widths[first + offset] = float(_resolve(width))
                i += 2
            elif i + 2 < len(items):
                for code in range(first, min(int(nxt), first + 0xFFFF) + 1):
                    self.widths[code] = float(items[i + 2])
                i += 3
            else:
                break

    def codes(self, raw: bytes) -> list[int]:
        if self.two_byte:
            return [int.from_bytes(raw[i : i + 2], "big") for i in range(0, len(raw) - 1, 2)]
        return list(raw)

    def text(self, code: int) -> str:
        if code in self.unicode:
            return self.unicode[code]
        if not self.two_byte:
            return bytes([code]).decode("cp1252", errors="replace")
        return "�"


def _raw_bytes(value: Any) -> bytes:
    if isinstance(value, bytes):
        return bytes(value)
    if hasattr(value, "get_original_bytes"):
        return bytes(value.get_original_bytes())
    return str(value).encode("latin-1", errors="replace")


def _floats(operands: Iterable[Any]) -> list[float]:
    return [float(_resolve(value)) for value in operands]


class _TextWalker:
    """İçerik akışını gezip glifleri toplar (metin durumu: PDF 1.7 §9.3-9.4)."""

    def __init__(self, pdf: Any) -> None:
        self.pdf = pdf
        self.glyphs: list[Glyph] = []

    def walk(self, content: Any, resources: Any, ctm: Matrix, depth: int = 0) -> None:
        from pypdf.generic import ContentStream

        resources = _resolve(resources) or {}
        fonts = _resolve(resources.get("/Font")) or {}
        xobjects = _resolve(resources.get("/XObject")) or {}
        cache: dict[str, _Font] = {}
        stack: list[Matrix] = []
        tm = tlm = _IDENTITY
        font: _Font | None = None
        size = char_spacing = word_spacing = leading = rise = 0.0
        h_scale = 1.0

        def show(raw: bytes) -> None:
            nonlocal tm
            if font is None:
                return
            for code in font.codes(raw):
                width = font.widths.get(code, font.default_width) * font.scale
                spacing = word_spacing if (not font.two_byte and code == 32) else 0.0
                advance = (width * size + char_spacing + spacing) * h_scale
                start = _mul(_mul((1.0, 0.0, 0.0, 1.0, 0.0, rise), tm), ctm)
                tm = _mul((1.0, 0.0, 0.0, 1.0, advance, 0.0), tm)
                if abs(start[1]) > 0.05 * abs(start[0]):
                    continue  # döndürülmüş metin (kâğıttaki çapraz filigran) satır değildir
                end = _mul(_mul((1.0, 0.0, 0.0, 1.0, 0.0, rise), tm), ctm)
                effective = size * (start[2] ** 2 + start[3] ** 2) ** 0.5
                self.glyphs.append(
                    Glyph(
                        text=font.text(code),
                        x0=start[4],
                        x1=end[4],
                        baseline=start[5],
                        size=effective,
                    )
                )

        def next_line(tx: float, ty: float) -> None:
            nonlocal tm, tlm
            tlm = _mul((1.0, 0.0, 0.0, 1.0, tx, ty), tlm)
            tm = tlm

        for operands, op in ContentStream(content, self.pdf, "bytes").operations:
            try:
                if op == b"q":
                    stack.append(ctm)
                elif op == b"Q":
                    ctm = stack.pop() if stack else ctm
                elif op == b"cm":
                    ctm = _mul(tuple(_floats(operands)), ctm)  # type: ignore[arg-type]
                elif op == b"BT":
                    tm = tlm = _IDENTITY
                elif op == b"Tf":
                    name = str(operands[0])
                    if name not in cache and name in fonts:
                        cache[name] = _Font(fonts[name])
                    font = cache.get(name)
                    size = float(operands[1])
                elif op == b"Tc":
                    char_spacing = float(operands[0])
                elif op == b"Tw":
                    word_spacing = float(operands[0])
                elif op == b"Tz":
                    h_scale = float(operands[0]) / 100.0
                elif op == b"TL":
                    leading = float(operands[0])
                elif op == b"Ts":
                    rise = float(operands[0])
                elif op == b"Td":
                    next_line(float(operands[0]), float(operands[1]))
                elif op == b"TD":
                    leading = -float(operands[1])
                    next_line(float(operands[0]), float(operands[1]))
                elif op == b"Tm":
                    tm = tlm = tuple(_floats(operands))  # type: ignore[assignment]
                elif op == b"T*":
                    next_line(0.0, -leading)
                elif op == b"Tj":
                    show(_raw_bytes(operands[0]))
                elif op == b"'":
                    next_line(0.0, -leading)
                    show(_raw_bytes(operands[0]))
                elif op == b'"':
                    word_spacing, char_spacing = float(operands[0]), float(operands[1])
                    next_line(0.0, -leading)
                    show(_raw_bytes(operands[2]))
                elif op == b"TJ":
                    for item in operands[0]:
                        if isinstance(item, bytes | str):
                            show(_raw_bytes(item))
                        else:
                            shift = -float(item) / 1000.0 * size * h_scale
                            tm = _mul((1.0, 0.0, 0.0, 1.0, shift, 0.0), tm)
                elif op == b"Do" and depth < _MAX_FORM_DEPTH:
                    xobject = _resolve(xobjects.get(str(operands[0])))
                    if xobject is not None and str(xobject.get("/Subtype")) == "/Form":
                        matrix = tuple(_floats(xobject.get("/Matrix", _IDENTITY)))
                        inner = xobject.get("/Resources") or resources
                        self.walk(xobject, inner, _mul(matrix, ctm), depth + 1)  # type: ignore[arg-type]
            except (ArithmeticError, IndexError, KeyError, TypeError, ValueError):
                continue  # bozuk işleç atlanır; tanıma bir kolaylıktır


def page_glyphs(page: Any) -> list[Glyph]:
    """Sayfanın glifleri (içerik sırasıyla)."""
    walker = _TextWalker(page.pdf)
    contents = page.get_contents()
    if contents is not None:
        walker.walk(contents, page.get("/Resources"), _IDENTITY)
    return walker.glyphs


# ---------------------------------------------------------------------------
# Satırlar ve etiketler
# ---------------------------------------------------------------------------


@dataclass
class _Line:
    baseline: float
    glyphs: list[Glyph]
    #: `tr_upper` + boşluk sadeleştirmesinden geçmiş satır metni ve her karakterin
    #: geldiği glif (araya konan boşlukta None).
    text: str = ""
    sources: tuple[Glyph | None, ...] = ()


def _lines(glyphs: list[Glyph]) -> list[_Line]:
    """Glifleri taban çizgisine göre satırlara toplar; satır içinde soldan sağa."""
    lines: list[_Line] = []
    for glyph in sorted(glyphs, key=lambda g: (-g.baseline, g.x0)):
        if lines and abs(lines[-1].baseline - glyph.baseline) <= _LINE_TOL:
            lines[-1].glyphs.append(glyph)
        else:
            lines.append(_Line(baseline=glyph.baseline, glyphs=[glyph]))
    for line in lines:
        line.glyphs.sort(key=lambda g: g.x0)
        chars: list[str] = []
        sources: list[Glyph | None] = []
        previous: Glyph | None = None
        for glyph in line.glyphs:
            # Boşluk glifi olmadan konumla açılan aralık da sözcük arasıdır (TJ kaydırması).
            if (
                previous is not None
                and glyph.x0 - previous.x1 > 0.2 * max(glyph.size, 1.0)
                and chars
                and chars[-1] != " "
            ):
                chars.append(" ")
                sources.append(None)
            for char in tr_upper(glyph.text):
                if char.isspace():
                    if chars and chars[-1] == " ":
                        continue
                    char = " "
                chars.append(char)
                sources.append(glyph)
            previous = glyph
        # "Sınıfı / Şubesi" yazımı da tanınsın: eğik çizgi çevresindeki boşluk düşer.
        kept = [
            i
            for i, char in enumerate(chars)
            if not (
                char == " "
                and (
                    (i > 0 and chars[i - 1] == "/") or (i + 1 < len(chars) and chars[i + 1] == "/")
                )
            )
        ]
        line.text = "".join(chars[i] for i in kept)
        line.sources = tuple(sources[i] for i in kept)
    return lines


def _label_span(line: _Line, pattern: re.Pattern[str]) -> tuple[float, float, float] | None:
    """Etiketin (x0, x1, punto) değeri; satırda yoksa None."""
    match = pattern.search(line.text)
    if match is None:
        return None
    glyphs = [g for g in line.sources[match.start() : match.end()] if g is not None]
    if not glyphs:
        return None
    return glyphs[0].x0, glyphs[-1].x1, max(g.size for g in glyphs)


def _field_slots(lines: list[_Line], right: float) -> tuple[FieldSlot, FieldSlot, FieldSlot] | None:
    """Üç etiketi AYNI satırda taşıyan satırdan alan yerleri; yoksa None.

    Alan, etiketin bitişinden bir sonraki etiketin başına (son alanda içerik sağ
    kenarına) uzanır; aralar etiket puntosuyla orantılı bırakılır.
    """
    for line in lines:
        spans = {key: _label_span(line, pattern) for key, pattern in _LABELS.items()}
        if any(span is None for span in spans.values()):
            continue
        found = {key: span for key, span in spans.items() if span is not None}
        starts = sorted(span[0] for span in found.values())
        slots: dict[str, FieldSlot] = {}
        for key, (_x0, x1, size) in found.items():
            following = [start for start in starts if start > x1]
            limit = (following[0] - 0.5 * size) if following else right
            slots[key] = FieldSlot(x0=x1 + 0.25 * size, x1=limit, baseline=line.baseline)
        if all(slot.x1 - slot.x0 > 10 for slot in slots.values()):
            return slots["name"], slots["class_label"], slots["number"]
    return None


def _text_top(glyphs: list[Glyph]) -> float | None:
    visible = [g for g in glyphs if g.text.strip()]
    if not visible:
        return None
    return max(g.baseline + _ASCENT * g.size for g in visible)


def _plain_text_has_labels(page: Any) -> bool:
    """Konum okunamadığında son çare: pypdf düz metninde OYSS işaretleri var mı?"""
    try:
        text = " ".join(tr_upper(page.extract_text() or "").split())
    except Exception:  # pypdf çeşitli hatalar fırlatabilir; tanıma bir kolaylıktır
        return False
    text = text.replace(" / ", "/").replace(" /", "/").replace("/ ", "/")
    return _OYSS_MARK in text and all(
        pattern.search(text) is not None for pattern in _LABELS.values()
    )


def detect(pdf_bytes: bytes) -> OyssPaper | None:
    """PDF bir OYSS soru kâğıdıysa alan yerleriyle döner; değilse None.

    Tanıma şartı 1. sayfada "Ortak Yazılı Sınav" sözü + üç alan etiketidir
    (Adı ve Soyadı / Sınıfı/Şubesi / Öğrenci Numarası). Etiketler aynı satırda
    konumlanırsa alanlar doldurulur; konumlanamazsa (metin katmanı farklı
    üretilmiş PDF) kâğıt yine OYSS sayılır ve kimlik satırına düşülür.
    """
    try:
        return _detect(pdf_bytes)
    except Exception as exc:  # tanıma bir kolaylıktır — yükleme/üretim düşmez
        logger.warning("OYSS kâğıdı tanınamadı (%s)", type(exc).__name__)
        return None


def _detect(pdf_bytes: bytes) -> OyssPaper | None:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    if not reader.pages:
        return None
    first = reader.pages[0]
    glyphs = page_glyphs(first)
    lines = _lines(glyphs)
    page_text = " ".join(line.text for line in lines)
    visible = [g for g in glyphs if g.text.strip()]
    width = float(first.mediabox.width)
    left = min((g.x0 for g in visible), default=0.1 * width)
    # Sağ kenar: en sağdaki metin ya da (sağa uzanan metin yoksa — numara alanının
    # çizgisi metin değildir) sol kenar boşluğunun simetriği.
    right = min(max(max((g.x1 for g in visible), default=0.0), width - left), width - 10.0)

    slots = _field_slots(lines, right) if _OYSS_MARK in page_text else None
    if slots is None and not _plain_text_has_labels(first):
        return None

    tops: list[tuple[int, float]] = []
    for index in range(0, len(reader.pages), 2):  # kimlik satırı tek numaralı sayfalarda
        page_glyph_list = glyphs if index == 0 else page_glyphs(reader.pages[index])
        top = _text_top(page_glyph_list)
        if top is not None:
            tops.append((index, top))
    name, class_label, number = slots if slots is not None else (None, None, None)
    return OyssPaper(
        name=name,
        class_label=class_label,
        number=number,
        left=left,
        right=right,
        text_tops=tuple(tops),
    )
