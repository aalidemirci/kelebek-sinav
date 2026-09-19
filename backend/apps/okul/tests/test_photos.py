"""Öğrenci fotoğrafları (19.09.2026) — e-Okul OOG01001R080 okuyucusu + saklama + aktarım.

KVKK: bütün veri SENTETİKTİR. Fotoğraflar Pillow ile üretilmiş düz renk
kareleridir, okul numaraları uydurmadır; e-Okul biçimi (OfficeArt BLIP deposu +
hücre çapaları) test içinde bayt bayt kurulur — depoya ikili fixture girmez.
Gerçek raporla prova ayrı yapılır (430 fotoğraf, 6 yer tutucu — tasarım notu).
"""

from __future__ import annotations

import base64
import io
import struct

import pytest
from django.db import connection
from PIL import Image
from rest_framework.test import APIClient

from apps.okul import eokul_foto
from apps.okul.eokul_foto import PhotoCell, PhotoSheet
from apps.okul.excel_ogrenci import ParserError
from apps.okul.models import ImportRun, ImportSourceType, Student, StudentPhoto, StudentStatus
from apps.okul.services import persons, photos
from apps.sinav.tests.oturum_yardim import sube
from shared import crypto

pytestmark = pytest.mark.django_db


def _jpeg(renk: tuple[int, int, int], boyut: tuple[int, int] = (131, 169)) -> bytes:
    tampon = io.BytesIO()
    Image.new("RGB", boyut, renk).save(tampon, format="JPEG", quality=90)
    return tampon.getvalue()


KIRMIZI = _jpeg((200, 30, 30))
MAVI = _jpeg((30, 30, 200))
YESIL = _jpeg((30, 200, 30))


# ===========================================================================
# OfficeArt kurucuları (test içi) — e-Okul Excel'inin görsel kayıtları
# ===========================================================================


def _kayit(tur: int, veri: bytes, *, ver: int = 0, inst: int = 0) -> bytes:
    return struct.pack("<HHI", (inst << 4) | ver, tur, len(veri)) + veri


def _kapsayici(tur: int, *cocuklar: bytes) -> bytes:
    return _kayit(tur, b"".join(cocuklar), ver=0xF)


def _fbse_jpeg(jpeg: bytes) -> bytes:
    blip = _kayit(0xF01D, b"\x00" * 16 + b"\xff" + jpeg, inst=0x46A)
    # btWin32, btMacOS, rgbUid(16), tag(2), size(4), cRef(4), foDelay(4), unused, cbName=0, unused×2
    govde = bytes([5, 5]) + b"\x00" * 16 + struct.pack("<HIIi", 0xFF, len(blip), 1, 0) + b"\x00" * 4
    return _kayit(0xF007, govde + blip, ver=2, inst=5)


def _blip_deposu(*jpegler: bytes) -> bytes:
    return _kapsayici(0xF000, _kapsayici(0xF001, *(_fbse_jpeg(j) for j in jpegler)))


def _sekil(pib: int, satir: int, sutun: int) -> bytes:
    fopt = _kayit(0xF00B, struct.pack("<HI", 0x4104, pib), ver=3, inst=1)
    capa = _kayit(0xF010, struct.pack("<9H", 0, sutun, 0, satir, 0, sutun + 1, 0, satir, 0))
    return _kapsayici(0xF004, _kayit(0xF00A, b"\x00" * 8, ver=2), fopt, capa)


def _cizim(*sekiller: bytes) -> bytes:
    return _kapsayici(0xF002, _kapsayici(0xF003, *sekiller))


class _Hucreler:
    """xlrd sayfası yerine geçen sahte hücre tablosu."""

    def __init__(self, degerler: dict[tuple[int, int], object]) -> None:
        self._d = degerler
        self.nrows = 1 + max((r for r, _ in degerler), default=0)
        self.ncols = 1 + max((c for _, c in degerler), default=0)

    def cell_value(self, row: int, col: int) -> object:
        return self._d.get((row, col), "")


# ===========================================================================
# Saf okuma
# ===========================================================================


def test_okul_numarasi_hucre_metninin_sonundan_okunur_ad_donmez() -> None:
    oku = eokul_foto.student_number_from_text
    assert oku("AD SOYAD 1234") == "1234"
    assert oku("AD ORTA SOYAD\n56") == "56"
    assert oku(1234.0) == "1234"
    assert oku("AD SOYAD") == ""
    assert oku("") == ""
    assert eokul_foto.column_letter(0) == "A" and eokul_foto.column_letter(27) == "AB"


def test_blip_deposu_ve_sekil_capalari_okunur() -> None:
    depo = eokul_foto.parse_blip_store(_blip_deposu(KIRMIZI, MAVI))
    assert sorted(depo) == [1, 2]
    assert depo[1].kind == "jpeg" and depo[1].data == KIRMIZI
    assert depo[2].data == MAVI

    sekiller = eokul_foto.parse_sheet_shapes(_cizim(_sekil(1, 6, 0), _sekil(2, 6, 2)))
    assert [(s.pib, s.row_top, s.col_left) for s in sekiller] == [(1, 6, 0), (2, 6, 2)]


def test_biff_alt_akislari_ve_continue_birlesir() -> None:
    def rec(tur: int, veri: bytes) -> bytes:
        return struct.pack("<HH", tur, len(veri)) + veri

    akis = (
        rec(0x0809, b"g")
        + rec(0x00EB, b"AB")
        + rec(0x003C, b"CD")
        + rec(0x000A, b"")
        + rec(0x0809, b"s")
        + rec(0x00EC, b"XY")
        + rec(0x000A, b"")
    )
    altlar = eokul_foto.split_substreams(akis)
    assert len(altlar) == 2
    assert eokul_foto._joined(altlar[0], 0x00EB) == b"ABCD"
    assert eokul_foto._joined(altlar[1], 0x00EC) == b"XY"


def test_fotograflar_numarayla_eslesir_yer_tutucu_ve_numarasiz_ayrilir() -> None:
    depo = eokul_foto.parse_blip_store(_blip_deposu(KIRMIZI, MAVI, YESIL))
    sekiller = eokul_foto.parse_sheet_shapes(
        _cizim(
            _sekil(1, 6, 0),  # 101 — kendi fotoğrafı
            _sekil(3, 6, 2),  # 102 ┐ aynı görsel iki öğrencide → "fotoğraf yok"
            _sekil(3, 6, 4),  # 103 ┘
            _sekil(2, 12, 0),  # altında numara yok (başlık logosu gibi)
        )
    )
    hucreler = _Hucreler({(7, 0): "AD SOYAD 101", (7, 2): "AD SOYAD 102", (7, 4): "AD SOYAD 103"})

    sayfa = eokul_foto.build_photo_sheet(sekiller, depo, eokul_foto.CellText(hucreler))

    assert [(p.student_number, p.placeholder) for p in sayfa.photos] == [
        ("101", False),
        ("102", True),
        ("103", True),
    ]
    assert sayfa.photos[0].row == 7 and sayfa.photos[0].col == "A"  # Excel'deki satır: 1 tabanlı
    assert sayfa.unlabeled == [(13, "A")]
    assert sayfa.placeholder_count == 2
    assert "AD" not in repr(sayfa.photos[0])


def test_excel_olmayan_dosya_turkce_hata_verir() -> None:
    with pytest.raises(ParserError, match="e-Okul Excel raporu olarak okunamadı"):
        eokul_foto.parse_photo_workbook(b"bu bir excel degil")


# ===========================================================================
# Saklama
# ===========================================================================


def test_gorsel_yeniden_kodlanir_meta_atilir_olcu_sinirlanir() -> None:
    buyuk = Image.new("RGB", (1200, 1600), (10, 120, 10))
    exif = Image.Exif()
    exif[0x010E] = "gizli aciklama"  # ImageDescription
    tampon = io.BytesIO()
    buyuk.save(tampon, format="JPEG", exif=exif.tobytes())

    jpeg, genislik, yukseklik = photos.normalize_image(tampon.getvalue())

    assert (genislik, yukseklik) == (240, 320)
    assert b"gizli aciklama" not in jpeg
    assert jpeg.startswith(b"\xff\xd8")
    with pytest.raises(ValueError):
        photos.normalize_image(b"resim degil")


def _ogrenciler() -> dict[str, Student]:
    sube(9, "A", students=3, start_no=101)
    sube(9, "B", students=1, start_no=201)
    return {s.student_number: s for s in Student.objects.all()}


def _sayfa(*hucreler: tuple[str, bytes, bool]) -> PhotoSheet:
    return PhotoSheet(
        photos=[
            PhotoCell(
                row=8,
                col=eokul_foto.column_letter(2 * i),
                student_number=no,
                kind="jpeg",
                data=veri,
                placeholder=yer_tutucu,
            )
            for i, (no, veri, yer_tutucu) in enumerate(hucreler)
        ]
    )


def _aktar(
    sayfa: PhotoSheet, *, on_conflict: str = photos.ON_CONFLICT_KEEP
) -> photos.PhotoImportReport:
    return photos._ingest(sayfa, source_hash="h" * 64, file_name="", on_conflict=on_conflict)


def test_onizleme_yazmaz_aktarim_yazar_ve_duzeyi_bildirir() -> None:
    from django.db import transaction

    _ogrenciler()
    sayfa = _sayfa(("101", KIRMIZI, False), ("102", MAVI, False), ("103", YESIL, True))

    with transaction.atomic():
        on = _aktar(sayfa)
        transaction.set_rollback(True)
    assert on.created == 2 and not StudentPhoto.objects.exists()

    rapor = _aktar(sayfa)

    assert (rapor.total, rapor.matched, rapor.created, rapor.placeholders) == (3, 2, 2, 1)
    assert rapor.levels == ["9. Sınıf"] and rapor.sections == ["9/A"]
    # 103 (e-Okul'da fotoğrafı yok) + 201 (9/B dosyada yok) hâlâ fotoğrafsız.
    assert rapor.missing_in_levels == 2
    assert StudentPhoto.objects.count() == 2
    assert ImportRun.objects.filter(source_type=ImportSourceType.PHOTOS).exists()


def test_mukerrer_yukleme_ayni_foto_gecilir_farkli_foto_secime_gore() -> None:
    ogr = _ogrenciler()
    _aktar(_sayfa(("101", KIRMIZI, False), ("102", MAVI, False)))

    # 101 aynı, 102 farklı → korunur (varsayılan).
    korunan = _aktar(_sayfa(("101", KIRMIZI, False), ("102", YESIL, False)))
    assert (korunan.same, korunan.conflicts, korunan.kept, korunan.replaced) == (1, 1, 1, 0)
    assert korunan.conflict_students == [{"student_number": "102", "class_label": "9/A"}]
    eski_ozet = StudentPhoto.objects.get(student=ogr["102"]).sha256

    degisen = _aktar(_sayfa(("102", YESIL, False)), on_conflict=photos.ON_CONFLICT_REPLACE)
    assert (degisen.conflicts, degisen.replaced) == (1, 1)
    assert StudentPhoto.objects.get(student=ogr["102"]).sha256 != eski_ozet


def test_yer_tutucu_kayitli_fotografi_silmez_bilinmeyen_numara_konumla_raporlanir() -> None:
    ogr = _ogrenciler()
    _aktar(_sayfa(("101", KIRMIZI, False)))

    rapor = _aktar(_sayfa(("101", MAVI, True), ("999", MAVI, False)))

    assert StudentPhoto.objects.filter(student=ogr["101"]).exists()
    assert rapor.placeholders == 1
    atlanan = rapor.skipped[0]
    assert atlanan.value == "999" and atlanan.location == "C8"
    assert "aktif öğrenci kaydı yok" in atlanan.issue


def test_parola_acikken_fotograf_sifreli_saklanir_kilitliyken_basilmaz() -> None:
    ogr = _ogrenciler()
    crypto.load_key(crypto.new_data_key())
    try:
        _aktar(_sayfa(("101", KIRMIZI, False)))
        with connection.cursor() as imlec:
            imlec.execute("SELECT image FROM okul_studentphoto")
            ham = str(imlec.fetchone()[0])
        assert not ham.startswith("/9j/")  # düz base64 JPEG değil — Fernet token'ı
        uri = photos.photo_data_uris([ogr["101"].pk])[ogr["101"].pk]
        assert uri.startswith("data:image/jpeg;base64,/9j/")
    finally:
        crypto.unload_key()
    # Kilitli: token çözülemez → fotoğraf yok sayılır (evrak patlamaz).
    assert photos.photo_data_uris([ogr["101"].pk]) == {}


def test_ayrilan_ve_silinen_ogrencinin_fotografi_kati_silinir() -> None:
    ogr = _ogrenciler()
    _aktar(_sayfa(("101", KIRMIZI, False), ("102", MAVI, False), ("103", YESIL, False)))

    persons.update_student(ogr["101"], status=StudentStatus.LEFT)
    persons.delete_student(ogr["102"])

    kalan = set(StudentPhoto.all_objects.values_list("student__student_number", flat=True))
    assert kalan == {"103"}
    # Elle güncellenmiş eski kayıt (kanca dışı) — sayım ucu temizler.
    Student.objects.filter(pk=ogr["103"].pk).update(status=StudentStatus.LEFT)
    assert photos.purge_stale_photos() == 1
    assert not StudentPhoto.all_objects.exists()


# ===========================================================================
# API
# ===========================================================================


def test_api_sayim_tumunu_sil_ve_hatali_istekler() -> None:
    ogr = _ogrenciler()
    _aktar(_sayfa(("101", KIRMIZI, False)))
    client = APIClient()

    sayim = client.get("/api/v1/student-photos/").json()
    assert sayim == {"with_photo": 1, "active_students": 4, "without_photo": 3}

    from django.core.files.uploadedfile import SimpleUploadedFile

    url = "/api/v1/student-photos/import/preview/"
    assert client.post(url, {}, format="multipart").status_code == 400
    bozuk = client.post(
        url,
        {"file": SimpleUploadedFile("liste.xls", b"x", content_type="application/vnd.ms-excel")},
        format="multipart",
    )
    assert bozuk.status_code == 400
    secim = client.post(
        url,
        {
            "file": SimpleUploadedFile("liste.xls", b"x", content_type="application/vnd.ms-excel"),
            "on_conflict": "sil",
        },
        format="multipart",
    )
    assert secim.status_code == 400

    silinen = client.delete("/api/v1/student-photos/").json()
    assert silinen == {"deleted": 1}
    assert not StudentPhoto.all_objects.filter(student=ogr["101"]).exists()


def test_veri_uri_yalniz_istenen_aktif_ogrencileri_dondurur() -> None:
    ogr = _ogrenciler()
    _aktar(_sayfa(("101", KIRMIZI, False), ("102", MAVI, False)))

    uriler = photos.photo_data_uris([ogr["101"].pk])

    assert list(uriler) == [ogr["101"].pk]
    assert base64.b64decode(uriler[ogr["101"].pk].split(",", 1)[1]).startswith(b"\xff\xd8")
    assert photos.photo_data_uris([]) == {}
