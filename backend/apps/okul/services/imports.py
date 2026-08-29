"""Öğrenci/Personel toplu içe aktarma — preview (dry-run) + commit.

DD `services/imports.py` (OYS kökenli) kalıbından KS'ye uyarlandı (tasarım §6):

- TCKN ve veli zinciri TAMAMEN YOK — öğrenci upsert anahtarı OKUL NUMARASIDIR
  (aktif canlı kayıtlar arasında; numara alanı düz olduğundan DB filtresi
  şifreli kipte de çalışır — TB3 dolambacı burada gerekmez).
- Sınıf/şube ayrıştırması okul türünden gelen seviye kümesiyle parametrik (U4).
- xlsx ve pano yapıştırması AYNI boru hattı: her girişten önce `rows` matrisi
  üretilir (`read_sheet` / `text_to_grid`), gerisi ortak.
- Idempotency UYARIDIR, ENGEL DEĞİL: aynı içerik (sha256) yeniden commit
  edilebilir — `already_imported=True` uyarısıyla MEVCUT COMPLETED `ImportRun`
  satırı güncellenir (koşullu unique bozulmaz).
- Önizleme deseni AYNEN: gerçek ingest atomic blokta koşulur ve
  `set_rollback(True)` ile geri alınır — %100 sonuç paritesi; ardından kalıcı
  PREVIEWED izi yazılır. Ingest zincirine `transaction.on_commit` EKLENEMEZ.
- Boş/çözülemeyen hücre mevcut veriyi SİLMEZ (import silmez ilkesi).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any
from zipfile import BadZipFile

from django.db import transaction
from django.utils import timezone
from openpyxl.utils.exceptions import InvalidFileException

from apps.okul import excel_ogrenci, excel_personel
from apps.okul.excel_ogrenci import ColumnMapping, ParsedRow, ParserError
from apps.okul.excel_personel import ParsedPersonnelRow, PersonnelColumnMapping
from apps.okul.models import (
    ClassSection,
    ImportRun,
    ImportSourceType,
    ImportStatus,
    Personnel,
    SchoolConfig,
    SchoolYear,
    Student,
    StudentStatus,
)


@dataclass
class ImportIssue:
    """İçe aktarmada bir satır sorunu (atlama veya uyarı)."""

    row_number: int
    field: str
    issue: str
    raw_value: str = ""


@dataclass
class StudentImportReport:
    """Öğrenci içe aktarma özeti (UI raporu + ImportRun.report JSON'ı)."""

    file_hash: str
    file_name: str = ""
    total_rows: int = 0
    processed: int = 0
    created_students: int = 0
    updated_students: int = 0
    unchanged_students: int = 0
    already_imported: bool = False
    dry_run: bool = False
    warnings: list[ImportIssue] = field(default_factory=list)
    skipped: list[ImportIssue] = field(default_factory=list)

    def add_warning(self, row: int, field_name: str, issue: str, raw: str = "") -> None:
        self.warnings.append(ImportIssue(row, field_name, issue, raw))

    def add_skip(self, row: int, field_name: str, issue: str, raw: str = "") -> None:
        self.skipped.append(ImportIssue(row, field_name, issue, raw))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary_tr(self) -> str:
        return (
            f"İçe aktarma: {self.processed}/{self.total_rows} satır işlendi — "
            f"{self.created_students} yeni, {self.updated_students} güncellenen, "
            f"{self.unchanged_students} değişmeyen öğrenci; "
            f"{len(self.warnings)} uyarı, {len(self.skipped)} atlanan."
        )


@dataclass
class PersonnelImportReport:
    """Personel içe aktarma özeti (UI raporu + ImportRun.report JSON'ı)."""

    file_hash: str
    file_name: str = ""
    total_rows: int = 0
    processed: int = 0
    created_personnel: int = 0
    updated_personnel: int = 0
    unchanged_personnel: int = 0
    already_imported: bool = False
    dry_run: bool = False
    warnings: list[ImportIssue] = field(default_factory=list)
    skipped: list[ImportIssue] = field(default_factory=list)

    def add_warning(self, row: int, field_name: str, issue: str, raw: str = "") -> None:
        self.warnings.append(ImportIssue(row, field_name, issue, raw))

    def add_skip(self, row: int, field_name: str, issue: str, raw: str = "") -> None:
        self.skipped.append(ImportIssue(row, field_name, issue, raw))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary_tr(self) -> str:
        return (
            f"Personel içe aktarma: {self.processed}/{self.total_rows} satır — "
            f"{self.created_personnel} yeni, {self.updated_personnel} güncellenen, "
            f"{self.unchanged_personnel} değişmeyen; "
            f"{len(self.warnings)} uyarı, {len(self.skipped)} atlanan."
        )


# ---------------------------------------------------------------------------
# Girdi normalize — dosya ve pano aynı matris biçimine iner
# ---------------------------------------------------------------------------
def file_hash(file_bytes: bytes) -> str:
    """Yüklenen dosyanın SHA256 özeti (aynı içerik tespiti için)."""
    return hashlib.sha256(file_bytes).hexdigest()


def text_hash(text: str) -> str:
    """Yapıştırılan metnin SHA256 özeti (satır sonları normalize edilir)."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def text_to_grid(text: str) -> list[list[Any]]:
    """Pano metnini satır matrisine çevirir (tab ayraçlı — Excel kopyala/yapıştır)."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return [list(line.split("\t")) for line in normalized.split("\n")]


def _grid_from_file(file_bytes: bytes) -> list[list[Any]]:
    """xlsx baytlarını matrise çevirir; xlsx olmayan içerik ParserError olur."""
    try:
        return excel_ogrenci.read_sheet(file_bytes)
    except (BadZipFile, InvalidFileException) as exc:
        raise ParserError(
            "Dosya .xlsx biçiminde okunamadı; uygulamadaki güncel Excel şablonunu kullanın "
            "(.xls veya CSV desteklenmez)."
        ) from exc


def _valid_levels() -> tuple[int, ...]:
    """Okul türünden geçerli seviye kümesi (U4 — parser'a parametre geçilir)."""
    return SchoolConfig.load().grade_levels


def _parse_student_grid(grid: list[list[Any]]) -> tuple[ColumnMapping, list[ParsedRow]]:
    """Matristen (mapping, satırlar); kritik sütun eksikse ParserError."""
    mapping = excel_ogrenci.detect_columns(grid)
    if not mapping.is_usable:
        missing = ", ".join(mapping.missing_critical)
        raise ParserError(f"Zorunlu sütun(lar) bulunamadı: {missing}.")
    return mapping, excel_ogrenci.parse_rows(grid, mapping, valid_levels=_valid_levels())


def _parse_personnel_grid(
    grid: list[list[Any]],
) -> tuple[PersonnelColumnMapping, list[ParsedPersonnelRow]]:
    mapping = excel_personel.detect_columns(grid)
    if not mapping.is_usable:
        missing = ", ".join(mapping.missing_critical)
        raise ParserError(f"Zorunlu sütun(lar) bulunamadı: {missing}.")
    return mapping, excel_personel.parse_rows(grid, mapping)


# ---------------------------------------------------------------------------
# ImportRun yaşam döngüsü (idempotency uyarısı + koşullu unique koruması)
# ---------------------------------------------------------------------------
def _open_run(*, source_type: str, source_hash: str, file_name: str) -> tuple[ImportRun, bool]:
    """Koşu kaydını açar → (run, zaten_tamamlanmış_mı)."""
    existing: ImportRun | None = ImportRun.objects.filter(
        source_type=source_type, file_hash=source_hash, status=ImportStatus.COMPLETED
    ).first()
    if existing is not None:
        existing.status = ImportStatus.RUNNING
        existing.started_at = timezone.now()
        existing.finished_at = None
        if file_name:
            existing.file_name = file_name
        existing.save(
            update_fields=["status", "started_at", "finished_at", "file_name", "updated_at"]
        )
        return existing, True
    run = ImportRun.objects.create(
        source_type=source_type,
        file_name=file_name,
        file_hash=source_hash,
        status=ImportStatus.RUNNING,
    )
    return run, False


def _close_run(run: ImportRun, report_dict: dict[str, Any]) -> None:
    run.status = ImportStatus.COMPLETED
    run.finished_at = timezone.now()
    run.report = report_dict
    run.save(update_fields=["status", "finished_at", "report", "updated_at"])


# ---------------------------------------------------------------------------
# Öğrenci içe aktarma
# ---------------------------------------------------------------------------
@transaction.atomic
def _ingest_students(
    *, grid: list[list[Any]], source_hash: str, file_name: str = ""
) -> StudentImportReport:
    """Matristeki öğrenci satırlarını Student kayıtlarına yazar (okul no upsert)."""
    mapping, rows = _parse_student_grid(grid)
    report = StudentImportReport(file_hash=source_hash, file_name=file_name, total_rows=len(rows))
    run, already = _open_run(
        source_type=ImportSourceType.STUDENTS, source_hash=source_hash, file_name=file_name
    )
    report.already_imported = already
    for header_warning in mapping.warnings:
        report.add_warning(mapping.header_row + 1, "header", header_warning)

    for row in rows:
        _process_student_row(row, report=report)

    _ensure_class_sections()
    _close_run(run, report.to_dict())
    return report


def _process_student_row(row: ParsedRow, *, report: StudentImportReport) -> None:
    """Tek satır: doğrula → okul numarasıyla bul/oluştur/güncelle."""
    if not row.student_number:
        report.add_skip(row.row_number, "number", "Okul numarası bulunamadı.")
        return
    if row.class_level is None:
        report.add_skip(row.row_number, "class", "Sınıf/şube çözülemedi", row.raw_class)
        return
    if not row.student_first and not row.student_last:
        report.add_skip(row.row_number, "student_name", "Öğrenci adı boş; satır atlandı.")
        return

    fields: dict[str, Any] = {
        "first_name": row.student_first,
        "last_name": row.student_last,
        "class_level": row.class_level,
        "class_section": row.class_section,
        "student_number": row.student_number,
    }

    # Tekillik DB kısıtıyla garanti (`uq_student_number_active_alive`) — aktif
    # canlı kayıtlar arasında numara tekil olduğundan çift-eşleşme dalı yoktur.
    student = Student.objects.filter(
        student_number=row.student_number, status=StudentStatus.ACTIVE
    ).first()
    if student is None:
        Student.objects.create(**fields)
        report.created_students += 1
    else:
        changed = [name for name, value in fields.items() if getattr(student, name) != value]
        if changed:
            for name in changed:
                setattr(student, name, fields[name])
            student.save(update_fields=[*changed, "updated_at"])
            report.updated_students += 1
        else:
            report.unchanged_students += 1
    report.processed += 1


def _ensure_class_sections() -> None:
    """Sicildeki aktif öğrenci şubelerini aktif yılın şube kataloğuna ekler."""
    year = SchoolYear.objects.filter(is_active=True).first()
    if year is None:
        return
    class_pairs = set(
        Student.objects.filter(status=StudentStatus.ACTIVE)
        .exclude(class_level=None)
        .exclude(class_section="")
        .values_list("class_level", "class_section")
    )
    for level, section in sorted(class_pairs):
        ClassSection.objects.get_or_create(
            school_year=year,
            class_level=level,
            class_section=section,
        )


# ---------------------------------------------------------------------------
# Personel içe aktarma
# ---------------------------------------------------------------------------
@transaction.atomic
def _ingest_personnel(
    *, grid: list[list[Any]], source_hash: str, file_name: str = ""
) -> PersonnelImportReport:
    """Matristeki personel satırlarını Personnel kayıtlarına yazar (ada göre upsert).

    Eşleşme anahtarı normalize edilmiş ad-soyaddır (`normalize_header`) — ad
    ŞİFRELİ saklandığından dizin daima Python tarafında kurulur (çözülmüş
    değerlerle; kilitliyken API kapısı zaten 423 verir). Yerel ölçekte (≤100
    personel) yeterli; adaş çakışmasında son kayıt kazanır, elle düzeltilir.
    """
    mapping, rows = _parse_personnel_grid(grid)
    report = PersonnelImportReport(file_hash=source_hash, file_name=file_name, total_rows=len(rows))
    run, already = _open_run(
        source_type=ImportSourceType.PERSONNEL, source_hash=source_hash, file_name=file_name
    )
    report.already_imported = already
    for header_warning in mapping.warnings:
        report.add_warning(mapping.header_row + 1, "header", header_warning)

    name_index: dict[str, Personnel] = {
        excel_ogrenci.normalize_header(p.full_name): p for p in Personnel.objects.all()
    }
    for row in rows:
        _process_personnel_row(row, report=report, name_index=name_index)

    _close_run(run, report.to_dict())
    return report


def _process_personnel_row(
    row: ParsedPersonnelRow, *, report: PersonnelImportReport, name_index: dict[str, Personnel]
) -> None:
    """Tek personel satırı: ada göre bul/oluştur; boş hücre mevcut veriyi silmez."""
    if not row.first_name and not row.last_name:
        report.add_skip(row.row_number, "full_name", "Ad-soyad boş; satır atlandı.")
        return

    key = excel_ogrenci.normalize_header(row.raw_full_name)
    person = name_index.get(key)
    if person is None:
        person = Personnel.objects.create(
            first_name=row.first_name,
            last_name=row.last_name,
            title=row.title,
            branch=row.branch,
        )
        name_index[key] = person
        report.created_personnel += 1
    else:
        changed: list[str] = []
        if row.title and person.title != row.title:
            person.title = row.title
            changed.append("title")
        if row.branch and person.branch != row.branch:
            person.branch = row.branch
            changed.append("branch")
        if changed:
            person.save(update_fields=[*changed, "updated_at"])
            report.updated_personnel += 1
        else:
            report.unchanged_personnel += 1
    report.processed += 1


# ---------------------------------------------------------------------------
# Kamu API — dosya ve pano girişleri (preview/commit)
# ---------------------------------------------------------------------------
def commit_students_file(*, file_bytes: bytes, file_name: str = "") -> StudentImportReport:
    return _student_entry(
        lambda: _grid_from_file(file_bytes), file_hash(file_bytes), file_name, preview=False
    )


def commit_students_text(*, text: str) -> StudentImportReport:
    return _student_entry(lambda: text_to_grid(text), text_hash(text), "", preview=False)


def preview_students_file(*, file_bytes: bytes, file_name: str = "") -> StudentImportReport:
    return _student_entry(
        lambda: _grid_from_file(file_bytes), file_hash(file_bytes), file_name, preview=True
    )


def preview_students_text(*, text: str) -> StudentImportReport:
    return _student_entry(lambda: text_to_grid(text), text_hash(text), "", preview=True)


def commit_personnel_file(*, file_bytes: bytes, file_name: str = "") -> PersonnelImportReport:
    return _personnel_entry(
        lambda: _grid_from_file(file_bytes), file_hash(file_bytes), file_name, preview=False
    )


def commit_personnel_text(*, text: str) -> PersonnelImportReport:
    return _personnel_entry(lambda: text_to_grid(text), text_hash(text), "", preview=False)


def preview_personnel_file(*, file_bytes: bytes, file_name: str = "") -> PersonnelImportReport:
    return _personnel_entry(
        lambda: _grid_from_file(file_bytes), file_hash(file_bytes), file_name, preview=True
    )


def preview_personnel_text(*, text: str) -> PersonnelImportReport:
    return _personnel_entry(lambda: text_to_grid(text), text_hash(text), "", preview=True)


def _student_entry(
    grid_supplier: Callable[[], list[list[Any]]],
    source_hash: str,
    file_name: str,
    *,
    preview: bool,
) -> StudentImportReport:
    """Ortak giriş: ParserError'da kalıcı FAILED izi bırakır ve hatayı yükseltir.

    Ingest atomiktir — hata rollback'i RUNNING satırını da siler; FAILED izi bu
    yüzden transaction DIŞINDA, burada yazılır (geçmiş görünümü boş kalmasın).
    """
    try:
        grid = grid_supplier()
        if preview:
            return _preview_students(grid=grid, source_hash=source_hash, file_name=file_name)
        return _ingest_students(grid=grid, source_hash=source_hash, file_name=file_name)
    except ParserError as exc:
        _record_failed(ImportSourceType.STUDENTS, source_hash, file_name, exc)
        raise


def _personnel_entry(
    grid_supplier: Callable[[], list[list[Any]]],
    source_hash: str,
    file_name: str,
    *,
    preview: bool,
) -> PersonnelImportReport:
    try:
        grid = grid_supplier()
        if preview:
            return _preview_personnel(grid=grid, source_hash=source_hash, file_name=file_name)
        return _ingest_personnel(grid=grid, source_hash=source_hash, file_name=file_name)
    except ParserError as exc:
        _record_failed(ImportSourceType.PERSONNEL, source_hash, file_name, exc)
        raise


def _preview_students(
    *, grid: list[list[Any]], source_hash: str, file_name: str = ""
) -> StudentImportReport:
    """Öğrenci importunu YAZMADAN simüle eder (gerçek ingest + rollback)."""
    with transaction.atomic():
        report = _ingest_students(grid=grid, source_hash=source_hash, file_name=file_name)
        transaction.set_rollback(True)
    report.dry_run = True
    _record_preview(ImportSourceType.STUDENTS, report.file_hash, file_name, report.to_dict())
    return report


def _preview_personnel(
    *, grid: list[list[Any]], source_hash: str, file_name: str = ""
) -> PersonnelImportReport:
    with transaction.atomic():
        report = _ingest_personnel(grid=grid, source_hash=source_hash, file_name=file_name)
        transaction.set_rollback(True)
    report.dry_run = True
    _record_preview(ImportSourceType.PERSONNEL, report.file_hash, file_name, report.to_dict())
    return report


def _record_preview(
    source_type: str, source_hash: str, file_name: str, report_dict: dict[str, Any]
) -> None:
    """Kalıcı PREVIEWED izi (geçmiş görünümü) — rollback DIŞINDA yazılır."""
    ImportRun.objects.create(
        source_type=source_type,
        file_name=file_name,
        file_hash=source_hash,
        status=ImportStatus.PREVIEWED,
        finished_at=timezone.now(),
        report=report_dict,
    )


def _record_failed(source_type: str, source_hash: str, file_name: str, error: Exception) -> None:
    """Kalıcı FAILED izi. `error` metni yalnız yapısal bilgidir (sütun adları) — PII yok."""
    ImportRun.objects.create(
        source_type=source_type,
        file_name=file_name,
        file_hash=source_hash,
        status=ImportStatus.FAILED,
        finished_at=timezone.now(),
        report={"error": str(error)},
    )
