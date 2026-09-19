"""Öğrenci fotoğrafları — saklama + e-Okul OOG01001R080 aktarımı (19.09.2026).

Kaynak: e-Okul'un fotoğraflı öğrenci listesi, SINIF DÜZEYİ başına ayrı Excel
dosyası (`apps.okul.eokul_foto`). Her dosya ayrı bir aktarımdır; eşleşme okul
numarasıyla (şube bilgisi öğrenci kaydından gelir).

Akış öğrenci aktarımıyla aynıdır: önizleme gerçek yazımı yapıp GERİ ALIR
(%100 sonuç paritesi), rapor okunur, sonra "Aktar". MÜKERRER YÜKLEME (kullanıcı
kararı 19.09.2026 — "uyarı verip hangi verinin korunmasını istediğini sor"):
aynı fotoğraf sessizce geçilir; öğrencinin kayıtlı fotoğrafı yenisinden FARKLIYSA
önizleme bunları sayar ve listeler, idareci aktarırken "mevcutları koru" ya da
"yenileriyle değiştir" seçer (`on_conflict`). Aynı dosyanın ikinci kez
yüklenmesi ayrıca `already_imported` ile bildirilir.

KVKK: fotoğraf kişisel veridir — saklama `StudentPhoto` docstring'indeki
kurallarla (parolada şifreli, yeniden kodlanmış, ayrılınca KATI silinir).
Rapor ve hata metinleri Excel konumu + okul numarası taşır, ad taşımaz.
"""

from __future__ import annotations

import base64
import hashlib
import io
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

from django.db import transaction

from apps.okul.eokul_foto import PhotoSheet, parse_photo_workbook
from apps.okul.excel_ogrenci import ParserError
from apps.okul.models import ImportSourceType, Student, StudentPhoto, StudentStatus
from apps.okul.services import imports as okul_imports

#: Saklanan fotoğrafın en büyük ölçüsü (piksel). e-Okul küçük resmi ~131×169'dur;
#: sınır büyük bir dosyanın veritabanını şişirmesini önler.
MAX_WIDTH = 240
MAX_HEIGHT = 320
JPEG_QUALITY = 85
#: Rapordaki satır sorunları/çakışma listesi sınırı — kalanı sayıyla özetlenir.
ISSUE_LIMIT = 60

ON_CONFLICT_KEEP = "keep"
ON_CONFLICT_REPLACE = "replace"
ON_CONFLICT_CHOICES = (ON_CONFLICT_KEEP, ON_CONFLICT_REPLACE)


# --------------------------------------------------------------------------- #
# Saklama
# --------------------------------------------------------------------------- #


def normalize_image(data: bytes) -> tuple[bytes, int, int]:
    """Görseli JPEG olarak yeniden kodlar: meta veri atılır, ölçü sınırlanır.

    Aynı girdi aynı çıktıyı verir (özet karşılaştırması buna dayanır). Görsel
    açılamazsa `ValueError`.
    """
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data)) as kaynak:
            resim = kaynak.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("görsel okunamadı") from exc
    resim.thumbnail((MAX_WIDTH, MAX_HEIGHT))
    cikti = io.BytesIO()
    resim.save(cikti, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return cikti.getvalue(), resim.width, resim.height


def _digest(jpeg: bytes) -> str:
    return hashlib.sha256(jpeg).hexdigest()


def _write(photo: StudentPhoto | None, student: Student, jpeg: bytes, w: int, h: int) -> None:
    kodlu = base64.b64encode(jpeg).decode("ascii")
    if photo is None:
        StudentPhoto.objects.create(
            student=student, image=kodlu, sha256=_digest(jpeg), width=w, height=h
        )
        return
    photo.image = kodlu
    photo.sha256 = _digest(jpeg)
    photo.width, photo.height = w, h
    photo.save(update_fields=["image", "sha256", "width", "height", "updated_at"])


def delete_student_photo(student_id: int) -> int:
    """Öğrencinin fotoğrafını KATI siler (ayrılan/silinen öğrenci); silinen sayısı."""
    silinen, _ = StudentPhoto.all_objects.get_queryset().filter(student_id=student_id).hard_delete()
    return int(silinen)


def delete_all_photos() -> int:
    """Bütün fotoğrafları KATI siler ("Tüm fotoğrafları sil": Kişiler ve Ayarlar → Güvenlik)."""
    silinen, _ = StudentPhoto.all_objects.get_queryset().all().hard_delete()
    return int(silinen)


def purge_stale_photos() -> int:
    """Ayrılmış ya da silinmiş öğrencinin kalmış fotoğraflarını KATI siler."""
    silinen, _ = (
        StudentPhoto.all_objects.get_queryset()
        .exclude(student__status=StudentStatus.ACTIVE, student__deleted_at__isnull=True)
        .hard_delete()
    )
    return int(silinen)


def photo_stats() -> dict[str, int]:
    """Ayarlar kartı: fotoğraflı ve fotoğrafsız AKTİF öğrenci sayısı."""
    aktif = Student.objects.filter(status=StudentStatus.ACTIVE)
    fotografli = StudentPhoto.objects.filter(
        student__status=StudentStatus.ACTIVE, student__deleted_at__isnull=True
    ).count()
    toplam = aktif.count()
    return {
        "with_photo": fotografli,
        "active_students": toplam,
        "without_photo": max(0, toplam - fotografli),
    }


def photo_data_uris(student_ids: Iterable[int]) -> dict[int, str]:
    """Öğrenci pk → `data:image/jpeg;base64,…` — evrak ve yoklama planı için.

    Yalnız AKTİF ve silinmemiş öğrencinin fotoğrafı döner. Parola kilitliyken
    şifreli alan çözülemez; çözülemeyen değer JPEG olmadığından atlanır (evrak
    fotoğrafsız basılır, patlamaz).
    """
    ids = {int(i) for i in student_ids}
    if not ids:
        return {}
    sonuc: dict[int, str] = {}
    for foto in StudentPhoto.objects.filter(
        student_id__in=ids,
        student__status=StudentStatus.ACTIVE,
        student__deleted_at__isnull=True,
    ):
        deger = str(foto.image or "")
        try:
            ham = base64.b64decode(deger, validate=True)
        except (ValueError, TypeError):
            continue
        if not ham.startswith(b"\xff\xd8"):
            continue  # JPEG değil (kilitli kipte çözülmemiş token)
        sonuc[int(foto.student_id)] = f"data:image/jpeg;base64,{deger}"
    return sonuc


# --------------------------------------------------------------------------- #
# e-Okul aktarımı
# --------------------------------------------------------------------------- #


@dataclass
class PhotoIssue:
    """Satır sorunu — Excel konumu + okul no (ad YOK)."""

    location: str  # "B8"
    issue: str
    value: str = ""


@dataclass
class PhotoImportReport:
    file_hash: str
    file_name: str = ""
    dry_run: bool = False
    already_imported: bool = False
    on_conflict: str = ON_CONFLICT_KEEP
    #: Okul numarası okunan fotoğraflı hücre sayısı.
    total: int = 0
    #: e-Okul'da fotoğrafı olmayan (yer tutucu) öğrenci sayısı.
    placeholders: int = 0
    matched: int = 0
    created: int = 0
    same: int = 0
    #: Kayıtlı fotoğrafı yenisinden FARKLI öğrenci sayısı (mükerrer yükleme).
    conflicts: int = 0
    replaced: int = 0
    kept: int = 0
    #: Eşleşen öğrencilerin sınıf düzeyleri ("9. Sınıf") ve şubeleri ("9/A").
    levels: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    #: Bu düzeylerde aktarımdan SONRA fotoğrafı olmayan aktif öğrenci sayısı.
    missing_in_levels: int = 0
    conflict_students: list[dict[str, str]] = field(default_factory=list)
    conflicts_truncated: int = 0
    skipped: list[PhotoIssue] = field(default_factory=list)
    skipped_truncated: int = 0

    def add_skip(self, location: str, issue: str, value: str = "") -> None:
        if len(self.skipped) < ISSUE_LIMIT:
            self.skipped.append(PhotoIssue(location, issue, value))
        else:
            self.skipped_truncated += 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@transaction.atomic
def _ingest(
    sheet: PhotoSheet, *, source_hash: str, file_name: str, on_conflict: str
) -> PhotoImportReport:
    from apps.dersler.text import level_label
    from apps.okul.normalize import tr_sort_key

    if on_conflict not in ON_CONFLICT_CHOICES:
        raise ParserError("Mükerrer fotoğraf seçimi geçersiz.")
    rapor = PhotoImportReport(
        file_hash=source_hash, file_name=file_name, on_conflict=on_conflict, total=len(sheet.photos)
    )
    run, already = okul_imports.open_import_run(
        source_type=ImportSourceType.PHOTOS, source_hash=source_hash, file_name=file_name
    )
    rapor.already_imported = already
    for satir, sutun in sheet.unlabeled:
        rapor.add_skip(f"{sutun}{satir}", "Fotoğrafın altında okul numarası bulunamadı.")

    ogrenciler: dict[str, Student] = {
        s.student_number: s
        for s in Student.objects.filter(status=StudentStatus.ACTIVE).exclude(student_number="")
    }
    mevcut: dict[int, StudentPhoto] = {
        int(f.student_id): f for f in StudentPhoto.objects.all().select_related("student")
    }
    gorulen: set[int] = set()
    duzeyler: set[int] = set()
    subeler: set[str] = set()
    for hucre in sheet.photos:
        konum = f"{hucre.col}{hucre.row}"
        ogrenci = ogrenciler.get(hucre.student_number)
        if ogrenci is None:
            rapor.add_skip(
                konum,
                "Bu okul numarasıyla aktif öğrenci kaydı yok — önce öğrenci listesini "
                "e-Okul'dan güncelleyin.",
                hucre.student_number,
            )
            continue
        if ogrenci.class_level is not None:
            duzeyler.add(int(ogrenci.class_level))
        if ogrenci.class_label:
            subeler.add(ogrenci.class_label)
        if hucre.placeholder:
            rapor.placeholders += 1  # e-Okul'da fotoğrafı yok — kayıtlı olana dokunulmaz
            continue
        if ogrenci.pk in gorulen:
            rapor.add_skip(
                konum, "Aynı okul numarası dosyada ikinci kez geçiyor.", hucre.student_number
            )
            continue
        gorulen.add(ogrenci.pk)
        try:
            jpeg, genislik, yukseklik = normalize_image(hucre.data)
        except ValueError:
            rapor.add_skip(konum, "Fotoğraf okunamadı.", hucre.student_number)
            continue
        rapor.matched += 1
        eski = mevcut.get(int(ogrenci.pk))
        if eski is None:
            _write(None, ogrenci, jpeg, genislik, yukseklik)
            rapor.created += 1
        elif eski.sha256 == _digest(jpeg):
            rapor.same += 1
        else:
            rapor.conflicts += 1
            if len(rapor.conflict_students) < ISSUE_LIMIT:
                rapor.conflict_students.append(
                    {"student_number": ogrenci.student_number, "class_label": ogrenci.class_label}
                )
            else:
                rapor.conflicts_truncated += 1
            if on_conflict == ON_CONFLICT_REPLACE:
                _write(eski, ogrenci, jpeg, genislik, yukseklik)
                rapor.replaced += 1
            else:
                rapor.kept += 1

    rapor.levels = [level_label(d) for d in sorted(duzeyler)]
    rapor.sections = sorted(subeler, key=tr_sort_key)
    if duzeyler:
        rapor.missing_in_levels = (
            Student.objects.filter(status=StudentStatus.ACTIVE, class_level__in=duzeyler)
            .exclude(photo__isnull=False)
            .count()
        )
    okul_imports.close_import_run(run, rapor.to_dict())
    return rapor


def _giris(
    file_bytes: bytes, file_name: str, *, preview: bool, on_conflict: str
) -> PhotoImportReport:
    source_hash = okul_imports.file_hash(file_bytes)
    try:
        sheet = parse_photo_workbook(file_bytes)
        if not preview:
            return _ingest(
                sheet, source_hash=source_hash, file_name=file_name, on_conflict=on_conflict
            )
        with transaction.atomic():
            rapor = _ingest(
                sheet, source_hash=source_hash, file_name=file_name, on_conflict=on_conflict
            )
            transaction.set_rollback(True)
        rapor.dry_run = True
        okul_imports.record_import_preview(
            ImportSourceType.PHOTOS, source_hash, file_name, rapor.to_dict()
        )
        return rapor
    except ParserError as exc:
        okul_imports.record_import_failure(ImportSourceType.PHOTOS, source_hash, file_name, exc)
        raise


def preview_photo_import(
    *, file_bytes: bytes, file_name: str = "", on_conflict: str = ON_CONFLICT_KEEP
) -> PhotoImportReport:
    """Yazmadan simüle eder — yeni/aynı/farklı fotoğraf sayıları, sorunlu satırlar."""
    return _giris(file_bytes, file_name, preview=True, on_conflict=on_conflict)


def commit_photo_import(
    *, file_bytes: bytes, file_name: str = "", on_conflict: str = ON_CONFLICT_KEEP
) -> PhotoImportReport:
    """Fotoğrafları yazar; kayıtlı fotoğrafı farklı olanlar `on_conflict`e göre."""
    return _giris(file_bytes, file_name, preview=False, on_conflict=on_conflict)
