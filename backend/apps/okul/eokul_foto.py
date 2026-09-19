"""e-Okul fotoğraflı öğrenci listesi (OOG01001R080) Excel ihracından fotoğraf okuma (19.09.2026).

e-Okul raporu SINIF DÜZEYİ başına ayrı dosya verir (kullanıcı bilgisi): tek sayfada
satır başına yedi öğrenci; her öğrencinin FOTOĞRAFI bir hücreye çapalı görsel,
hemen altındaki hücrede "AD SOYAD <okul no>" metni. Şube başlığı yalnız ilk
şube için yazılır — şube bilgisi dosyadan DEĞİL, eşleşen öğrenci kaydından gelir.

Neden Excel (PDF değil): aynı raporun PDF'inde fotoğraf sıkıştırılmamış piksel
dizisidir ve okul numarası fotoğrafın altında ayrı metin öğesidir — eşleştirme
KONUM tahminine kalır (uzun ad numarayı aşağı iter). Excel'de her görsel satır/
sütun ÇAPASIYLA hücreye bağlıdır; eşleştirme kesin. (19.09.2026, gerçek rapor:
431 görsel, 425 JPEG + 1 "fotoğraf yok" yer tutucusu.)

Biçim: .XLS = OLE2 kabı içinde BIFF8 "Workbook" akışı. Görseller OfficeArt
kayıtlarındadır: genel akıştaki MSODRAWINGGROUP (+CONTINUE) BLIP deposunu
(FBSE → gömülü JPEG/PNG/DIB), sayfa akışındaki MSODRAWING her şeklin görsel
sırasını (FOPT `pib`) ve hücre çapasını (ClientAnchor: satır/sütun) taşır.
Hücre metinleri xlrd ile okunur.

KVKK: ad-soyad HİÇ ayrıştırılmaz — hücre metninden yalnız sondaki okul numarası
alınır. Hata/uyarı metinleri satır/sütun konumu ve okul numarası taşır, ad değil.
Görsel baytları bu modülde yalnız bellekte durur; saklama `services.photos`'tadır.
"""

from __future__ import annotations

import re
import struct
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field

from apps.okul.excel_ogrenci import ParserError

# BIFF8 kayıt türleri
_BOF = 0x0809
_EOF = 0x000A
_CONTINUE = 0x003C
_MSODRAWINGGROUP = 0x00EB
_MSODRAWING = 0x00EC

# OfficeArt kayıt türleri
_FBSE = 0xF007
_SP_CONTAINER = 0xF004
_FOPT = 0xF00B
_CLIENT_ANCHOR = 0xF010
_PROP_PIB = 0x0104  # görsel sırası (BStore'da 1 tabanlı)

#: Fotoğraf olarak kabul edilen BLIP türleri → (biçim, ek başlık uzunluğu yok).
#: Metafile'lar (EMF/WMF/PICT) fotoğraf değildir; DIB e-Okul'da "fotoğraf yok"
#: simgesidir — ikisi de yer tutucu sayılır.
_FOTO_BLIPLERI = {0xF01D: "jpeg", 0xF02A: "jpeg", 0xF01E: "png"}
_DIGER_BLIPLER = {0xF01F: "dib", 0xF029: "tiff", 0xF01A: "emf", 0xF01B: "wmf", 0xF01C: "pict"}

#: Hücre metninin sonundaki okul numarası ("AD SOYAD 1234").
_NO_RE = re.compile(r"(\d{1,10})\s*$")


@dataclass(frozen=True)
class Blip:
    """BLIP deposundaki bir görsel (1 tabanlı sırası `pib`)."""

    pib: int
    kind: str  # "jpeg" | "png" | "dib" | …
    data: bytes


@dataclass(frozen=True)
class Shape:
    """Sayfadaki görselli şekil: görsel sırası + hücre çapası (0 tabanlı)."""

    pib: int
    row_top: int
    col_left: int
    row_bottom: int
    col_right: int


@dataclass(frozen=True)
class PhotoCell:
    """Bir öğrencinin fotoğrafı: Excel konumu + okul no + görsel (ad YOK)."""

    row: int  # 1 tabanlı (Excel'deki satır numarası)
    col: str  # Excel sütun harfi ("A")
    student_number: str
    kind: str
    data: bytes
    #: Aynı görsel birden çok öğrencide ya da fotoğraf dışı biçim → yer tutucu.
    placeholder: bool


@dataclass
class PhotoSheet:
    """Rapordan okunan fotoğraflar + okunamayan şekillerin konumu."""

    photos: list[PhotoCell] = field(default_factory=list)
    #: Görseli olup altında okul numarası bulunamayan şekiller (satır, sütun).
    unlabeled: list[tuple[int, str]] = field(default_factory=list)

    @property
    def placeholder_count(self) -> int:
        return sum(1 for p in self.photos if p.placeholder)


# --------------------------------------------------------------------------- #
# BIFF kayıtları
# --------------------------------------------------------------------------- #


def _records(stream: bytes) -> Iterator[tuple[int, bytes]]:
    i = 0
    while i + 4 <= len(stream):
        rtype, length = struct.unpack_from("<HH", stream, i)
        yield rtype, stream[i + 4 : i + 4 + length]
        i += 4 + length


def split_substreams(stream: bytes) -> list[list[tuple[int, bytes]]]:
    """Workbook akışını BOF…EOF alt akışlarına böler (0: genel, 1…: sayfalar)."""
    altlar: list[list[tuple[int, bytes]]] = []
    for rtype, data in _records(stream):
        if rtype == _BOF:
            altlar.append([])
        if altlar:
            altlar[-1].append((rtype, data))
    return altlar


def _joined(records: list[tuple[int, bytes]], rtype: int) -> bytes:
    """`rtype` kayıtlarının ve onları izleyen CONTINUE'ların birleşik verisi."""
    parcalar: list[bytes] = []
    onceki_hedef = False
    for tip, data in records:
        if tip == rtype:
            parcalar.append(data)
            onceki_hedef = True
        elif tip == _CONTINUE and onceki_hedef:
            parcalar.append(data)
        else:
            onceki_hedef = False
    return b"".join(parcalar)


# --------------------------------------------------------------------------- #
# OfficeArt
# --------------------------------------------------------------------------- #


def _officeart(data: bytes, start: int, end: int) -> Iterator[tuple[int, int, int, int]]:
    """(kayıt türü, instance, veri başı, veri uzunluğu) — kapsayıcılara iner."""
    i = start
    while i + 8 <= end:
        ver_inst, rtype, rlen = struct.unpack_from("<HHI", data, i)
        yield rtype, ver_inst >> 4, i + 8, rlen
        if ver_inst & 0xF == 0xF:  # kapsayıcı
            yield from _officeart(data, i + 8, min(i + 8 + rlen, end))
        i += 8 + rlen


def parse_blip_store(group: bytes) -> dict[int, Blip]:
    """MSODRAWINGGROUP verisinden BLIP deposu: pib → görsel."""
    depo: dict[int, Blip] = {}
    pib = 0
    for rtype, _inst, start, length in _officeart(group, 0, len(group)):
        if rtype != _FBSE:
            continue
        pib += 1
        if length < 36:
            continue
        cb_name = group[start + 33]
        blip_start = start + 36 + cb_name
        blip_end = start + length
        if blip_start + 8 > blip_end:
            continue  # gömülü değil (gecikmeli akış) — fotoğraf raporunda görülmez
        ver_inst, btype, blen = struct.unpack_from("<HHI", group, blip_start)
        inst = ver_inst >> 4
        body = blip_start + 8
        kind = _FOTO_BLIPLERI.get(btype) or _DIGER_BLIPLER.get(btype, "bilinmeyen")
        if btype in _FOTO_BLIPLERI or btype in (0xF01F, 0xF029):
            # rgbUid1 (16) [+ rgbUid2 (16) instance tekse] + tag (1) + dosya verisi
            uid = 32 if inst & 1 else 16
            veri = group[body + uid + 1 : body + blen]
        else:
            veri = b""  # metafile: fotoğraf değil
        depo[pib] = Blip(pib=pib, kind=kind, data=bytes(veri))
    return depo


def parse_sheet_shapes(drawing: bytes) -> list[Shape]:
    """MSODRAWING verisinden görselli şekiller (pib + ClientAnchor)."""
    sekiller: list[Shape] = []
    pib: int | None = None
    capa: tuple[int, int, int, int] | None = None

    def kapat() -> None:
        if pib is not None and capa is not None:
            sekiller.append(Shape(pib, capa[0], capa[1], capa[2], capa[3]))

    for rtype, inst, start, length in _officeart(drawing, 0, len(drawing)):
        if rtype == _SP_CONTAINER:
            kapat()
            pib, capa = None, None
        elif rtype == _FOPT:
            for k in range(inst):
                if start + 6 * k + 6 > start + length:
                    break
                opid, deger = struct.unpack_from("<HI", drawing, start + 6 * k)
                if opid & 0x3FFF == _PROP_PIB:
                    pib = int(deger)
        elif rtype == _CLIENT_ANCHOR and length >= 18:
            _f, col_l, _dxl, row_t, _dyt, col_r, _dxr, row_b, _dyb = struct.unpack_from(
                "<9H", drawing, start
            )
            capa = (row_t, col_l, row_b, col_r)
    kapat()
    return sekiller


# --------------------------------------------------------------------------- #
# Hücre metni → okul no
# --------------------------------------------------------------------------- #


def student_number_from_text(text: object) -> str:
    """'AD SOYAD 1234' → '1234'; sayı yoksa ''. Ad hiç döndürülmez."""
    if isinstance(text, float) and text == int(text):
        return str(int(text))
    eslesme = _NO_RE.search(str(text or "").strip())
    return eslesme.group(1) if eslesme else ""


def column_letter(col: int) -> str:
    """0 tabanlı sütun → Excel harfi (0 → 'A', 26 → 'AA')."""
    harf = ""
    col += 1
    while col:
        col, kalan = divmod(col - 1, 26)
        harf = chr(65 + kalan) + harf
    return harf


def label_below(cell_text: CellText, shape: Shape) -> str:
    """Şeklin altındaki (ya da içindeki) ilk okul numarası: satır alt+1…alt+3."""
    for row in range(shape.row_bottom, shape.row_bottom + 4):
        for col in range(shape.col_left, max(shape.col_left, shape.col_right) + 1):
            numara = student_number_from_text(cell_text(row, col))
            if numara:
                return numara
    return ""


class CellText:
    """xlrd sayfasının güvenli hücre okuyucusu (aralık dışı → '')."""

    def __init__(self, sheet: object) -> None:
        self._sheet = sheet

    def __call__(self, row: int, col: int) -> object:
        sheet = self._sheet
        nrows = int(getattr(sheet, "nrows", 0))
        ncols = int(getattr(sheet, "ncols", 0))
        if row < 0 or col < 0 or row >= nrows or col >= ncols:
            return ""
        return sheet.cell_value(row, col)  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# Dosya
# --------------------------------------------------------------------------- #


def build_photo_sheet(
    shapes: list[Shape], blips: dict[int, Blip], cell_text: CellText
) -> PhotoSheet:
    """Şekilleri okul numaralarıyla eşler; yer tutucuları işaretler (SAF)."""
    kullanim = Counter(s.pib for s in shapes)
    sonuc = PhotoSheet()
    for shape in sorted(shapes, key=lambda s: (s.row_top, s.col_left)):
        blip = blips.get(shape.pib)
        if blip is None:
            continue
        numara = label_below(cell_text, shape)
        konum = (shape.row_top + 1, column_letter(shape.col_left))
        if not numara:
            sonuc.unlabeled.append(konum)
            continue
        sonuc.photos.append(
            PhotoCell(
                row=konum[0],
                col=konum[1],
                student_number=numara,
                kind=blip.kind,
                data=blip.data,
                placeholder=(
                    kullanim[shape.pib] > 1 or blip.kind not in ("jpeg", "png") or not blip.data
                ),
            )
        )
    return sonuc


def parse_photo_workbook(file_bytes: bytes) -> PhotoSheet:
    """e-Okul fotoğraflı liste .XLS'i → fotoğraflar; biçim bozuksa Türkçe `ParserError`."""
    import xlrd
    from xlrd import compdoc

    try:
        ole = compdoc.CompDoc(file_bytes, logfile=_Sessiz())
        stream = ole.get_named_stream("Workbook") or ole.get_named_stream("Book")
    except Exception as exc:  # noqa: BLE001 — xlrd'nin kendi hata sınıfları dağınık
        raise ParserError(
            "Dosya e-Okul Excel raporu olarak okunamadı. e-Okul'dan fotoğraflı öğrenci "
            "listesini (OOG01001R080) Excel olarak indirip olduğu gibi yükleyin."
        ) from exc
    if not stream:
        raise ParserError("Dosyada Excel çalışma kitabı bulunamadı.")
    altlar = split_substreams(bytes(stream))
    if len(altlar) < 2:
        raise ParserError("Excel dosyasında sayfa bulunamadı.")
    blips = parse_blip_store(_joined(altlar[0], _MSODRAWINGGROUP))
    if not blips:
        raise ParserError(
            "Bu Excel dosyasında fotoğraf yok — e-Okul'un fotoğraflı öğrenci listesi "
            "(OOG01001R080) raporu olmayabilir."
        )
    try:
        kitap = xlrd.open_workbook(file_contents=file_bytes, on_demand=True, logfile=_Sessiz())
    except Exception as exc:  # noqa: BLE001
        raise ParserError("Excel dosyasının hücreleri okunamadı.") from exc
    sonuc = PhotoSheet()
    for sira, alt in enumerate(altlar[1:]):
        if sira >= kitap.nsheets:
            break
        cizim = _joined(alt, _MSODRAWING)
        if not cizim:
            continue
        sayfa_sonucu = build_photo_sheet(
            parse_sheet_shapes(cizim), blips, CellText(kitap.sheet_by_index(sira))
        )
        sonuc.photos.extend(sayfa_sonucu.photos)
        sonuc.unlabeled.extend(sayfa_sonucu.unlabeled)
    return sonuc


class _Sessiz:
    """xlrd'nin tanı çıktısını yutar (içerik günlüğe sızmasın)."""

    def write(self, *_args: object) -> None:
        return None
