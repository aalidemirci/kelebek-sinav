"""Ders havuzu iş mantığı — katalog tohumu, elle ekleme, takma adlar, birleştirme.

OYS `ders_yapisi.services`'ten KELEBEK KESİTİ (tasarım §7 + §11):
- `ensure_meb_catalog` + `ensure_course_aliases`: idempotent tembel tohum —
  katalog listesi ilk kez açıldığında koşar; veri dosyası yoksa SESSİZCE atlar.
  Çevrimdışı güncelleme yolu = uygulama sürümüyle gelen yeni md dosyası (K5).
- `import_course_rows`: ada göre idempotent upsert; **`is_active` bilinçle
  korunur** — idarenin pasifleştirdiği ders import'la sessizce geri açılmaz.
  `exam_mode` bu korumanın DIŞINDADIR (çizelge verisidir; gerekçe fonksiyon
  docstring'inde).
- `consolidate_duplicate_course`: referans taşıma KS kesitine indirildi
  (takma adlar + sınav dersleri; sınav modeli F3'te geldiğinden `get_model`
  çağrısı yokluğa dayanıklıdır).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.dersler import text
from apps.dersler.models import (
    PREP_COURSE_LEVEL,
    VALID_COURSE_LEVELS,
    Course,
    CourseAlias,
    CourseExamMode,
    CourseSource,
    CourseType,
)


@dataclass(frozen=True)
class CourseRow:
    """Çizelge dosyasından ayrıştırılmış tek ders satırı.

    `exam_mode` VARSAYILANLI ve SON alandır: çizelgenin 4. sütunu isteğe
    bağlıdır (3 sütunlu dosyalar bozulmadan okunmalı) ve mevcut konumsal
    çağrılar kırılmamalıdır.
    """

    name: str
    levels: tuple[int, ...]
    course_type: str  # CourseType değeri
    exam_mode: str = CourseExamMode.WRITTEN  # CourseExamMode değeri


@dataclass
class CatalogImportResult:
    """`import_course_rows` özeti."""

    created: int = 0
    updated: int = 0
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)


def normalize_levels(levels: object) -> list[int]:
    """Seviye listesini doğrula ve normalize et (tekrarsız, artan sıralı).

    Geçersiz girdi Türkçe mesajlı ``ValidationError`` fırlatır. 0 = Hazırlık.
    Doğrulama TÜM okul türlerinin birleşim kümesine karşıdır (models notu).
    """
    if not isinstance(levels, list | tuple) or not levels:
        raise ValidationError("Seviyeler boş olamaz; en az bir sınıf düzeyi verin (örn. [9]).")
    normalized: set[int] = set()
    for item in levels:
        if isinstance(item, bool) or not isinstance(item, int):
            raise ValidationError(f"Geçersiz seviye değeri: {item!r}. Tam sayı bekleniyor.")
        if item not in VALID_COURSE_LEVELS:
            raise ValidationError(
                f"Geçersiz seviye: {item}. Geçerli düzeyler: Hazırlık (0), 9, 10, 11, 12."
            )
        normalized.add(item)
    return sorted(normalized)


def level_label(level: int) -> str:
    """Seviye görünüm etiketi: 0 → 'Hazırlık', diğerleri → '9. Sınıf'."""
    return "Hazırlık" if level == PREP_COURSE_LEVEL else f"{level}. Sınıf"


@transaction.atomic
def create_course(
    *,
    name: str,
    levels: list[int],
    course_type: str = CourseType.COMMON,
    exam_mode: str = CourseExamMode.WRITTEN,
    source: str = CourseSource.MANUAL,
    is_active: bool = True,
) -> Course:
    """Havuza yeni ders ekle. Aynı adla canlı kayıt varsa Türkçe hata.

    `is_active` serializer alanları arasında olduğundan burada da KABUL EDİLİR:
    view `validated_data`'nın tamamını kwargs olarak açar (views.py), imza
    eksik kalırsa gövdesinde `is_active` gönderen POST 500 verirdi.
    """
    cleaned = text.normalize_course_name(name)
    if Course.objects.filter(name=cleaned).exists():
        raise ValidationError(f"'{cleaned}' adlı ders zaten havuzda var.")
    course: Course = Course.objects.create(
        name=cleaned,
        levels=normalize_levels(levels),
        course_type=course_type,
        exam_mode=exam_mode,
        source=source,
        is_active=is_active,
    )
    return course


@transaction.atomic
def update_course(
    course: Course,
    *,
    name: str | None = None,
    levels: list[int] | None = None,
    course_type: str | None = None,
    exam_mode: str | None = None,
    is_active: bool | None = None,
) -> Course:
    """Ders alanlarını güncelle (kısmi). `source` elle değiştirilemez."""
    if name is not None:
        cleaned = text.normalize_course_name(name)
        if Course.objects.exclude(pk=course.pk).filter(name=cleaned).exists():
            raise ValidationError(f"'{cleaned}' adlı ders zaten havuzda var.")
        course.name = cleaned
    if levels is not None:
        course.levels = normalize_levels(levels)
    if course_type is not None:
        course.course_type = course_type
    if exam_mode is not None:
        course.exam_mode = exam_mode
    if is_active is not None:
        course.is_active = is_active
    course.save()
    return course


def import_course_rows(rows: list[CourseRow]) -> CatalogImportResult:
    """Çizelge satırlarını kataloğa idempotent uygula.

    Eşleştirme canlı kayıtta **ders adına göre**: yoksa oluşturulur
    (`source=MEB_CATALOG`); varsa seviye/tür/sınav biçimi farkı güncellenir
    (elle girilmiş aynı adlı ders MEB kaydına dönüştürülür — MEB kaynağı
    kazanır); fark yoksa dokunulmaz. `is_active` bilinçle korunur. Hatalı
    satırlar `errors`'ta.

    `exam_mode` bilerek `is_active` gibi DEĞİL, `levels`/`course_type` gibi
    davranır: sınav biçimi ÇİZELGE VERİSİDİR (dersin uygulamalı olup olmaması
    MEB çizelgesinin kararıdır), `is_active` ise idari karardır. Çizelgede
    'UYGULAMA' yazan ama DB'de 'WRITTEN' duran bir ders karşılaştırmaya
    girmezse `unchanged` sayılır ve hiç düzelmezdi.
    """
    result = CatalogImportResult()
    with transaction.atomic():
        for row in rows:
            try:
                cleaned = text.normalize_course_name(row.name)
                levels = normalize_levels(list(row.levels))
            except ValidationError as exc:
                result.errors.append(f"{row.name!r}: {'; '.join(exc.messages)}")
                continue
            existing = Course.objects.filter(name=cleaned).first()
            if existing is None:
                Course.objects.create(
                    name=cleaned,
                    levels=levels,
                    course_type=row.course_type,
                    exam_mode=row.exam_mode,
                    source=CourseSource.MEB_CATALOG,
                )
                result.created += 1
                continue
            if (
                existing.levels == levels
                and existing.course_type == row.course_type
                and existing.exam_mode == row.exam_mode
                and existing.source == CourseSource.MEB_CATALOG
            ):
                result.unchanged += 1
                continue
            existing.levels = levels
            existing.course_type = row.course_type
            existing.exam_mode = row.exam_mode
            existing.source = CourseSource.MEB_CATALOG
            existing.save()
            result.updated += 1
    return result


def ensure_meb_catalog(*, path: str | None = None) -> CatalogImportResult:
    """MEB ders kataloğu YOKSA veri dosyalarından yükler (idempotent tembel tohum).

    Katalog zaten varsa hızlıca döner; yoksa `settings.CATALOG_DIR/*.md`
    dosyalarını yükler (README ve takma ad dosyası hariç). Dosya yoksa SESSİZCE
    atlar — elle ekleme yolu her durumda açık kalır (TB2).
    """
    from pathlib import Path

    from apps.dersler.catalog_parser import parse_markdown_catalog

    if Course.objects.filter(source=CourseSource.MEB_CATALOG).exists():
        return CatalogImportResult()  # zaten yüklü
    root = Path(path if path is not None else settings.CATALOG_DIR)
    if root.is_dir():
        skip = {"readme.md", "ders-adi-takma-adlari.md"}
        files = sorted(f for f in root.glob("*.md") if f.name.lower() not in skip)
    elif root.is_file():
        files = [root]
    else:
        return CatalogImportResult()  # dosya yok → atla
    rows: list[CourseRow] = []
    for file in files:
        parsed = parse_markdown_catalog(file.read_text(encoding="utf-8"), source_name=file.name)
        rows.extend(parsed.rows)
    if not rows:
        return CatalogImportResult()
    return import_course_rows(rows)


def learn_course_alias(
    *,
    name: str,
    course: Course,
    source: str = CourseAlias.Source.OPERATOR,
) -> CourseAlias | None:
    """Takma ad öğren (idempotent). None = yazılmadı.

    Kurallar: ÖZ-ALIAS yazılmaz; aynı anahtara mevcut kayıt varsa OPERATOR
    günceller (operatör kararı üstündür), SEED asla ezmez; aynı derse işaret
    eden mevcut kayıt aynen döner.
    """
    key = text.course_match_key(name)
    if not key or key == text.course_match_key(course.name):
        return None  # boş ya da öz-alias
    display = " ".join(name.split())[:200]
    existing: CourseAlias | None = CourseAlias.objects.filter(alias_key=key).first()
    if existing is None:
        alias: CourseAlias = CourseAlias.objects.create(
            alias_key=key,
            display_name=display,
            course=course,
            source=source,
        )
        return alias
    if existing.course_id == course.pk:
        return existing  # idempotent — aynı hedef
    if source == CourseAlias.Source.OPERATOR:
        existing.course = course
        existing.source = CourseAlias.Source.OPERATOR
        existing.display_name = display
        existing.save(update_fields=["course", "source", "display_name", "updated_at"])
        return existing
    return None  # SEED mevcut kaydı ezmez


def ensure_course_aliases(*, path: str | None = None) -> int:
    """Seed takma adlarını eksikse yükler (satır-bazlı idempotent; OYS Tur 653 dersi).

    Kanonik ad katalogda bulunamazsa satır SESSİZCE atlanır (dosya yoksa da).
    YENİ yazılan SEED kaydı sayısını döner; SEED hiçbir mevcut alias'ı ezmez.
    """
    from pathlib import Path

    from apps.dersler import selectors
    from apps.dersler.catalog_parser import parse_alias_table

    file = Path(path if path is not None else settings.COURSE_ALIAS_FILE)
    if not file.is_file():
        return 0
    existing_seed_pks: set[int] = set(
        CourseAlias.objects.filter(source=CourseAlias.Source.SEED).values_list("pk", flat=True)
    )
    created: set[int] = set()
    parsed = parse_alias_table(file.read_text(encoding="utf-8"), source_name=file.name)
    for alias_name, canonical in parsed.rows:
        course = selectors.meb_course_by_normalized_name(canonical) or (
            selectors.course_by_normalized_name(canonical)
        )
        if course is None or not course.is_active:
            continue  # kanonik ad katalogda yok — satır atlanır
        alias = learn_course_alias(name=alias_name, course=course, source=CourseAlias.Source.SEED)
        if (
            alias is not None
            and alias.source == CourseAlias.Source.SEED
            and alias.pk not in existing_seed_pks
        ):
            created.add(alias.pk)
    return len(created)


def ensure_seeded() -> None:
    """Tembel tohum girişi — katalog listesi açılırken çağrılır (K5)."""
    ensure_meb_catalog()
    ensure_course_aliases()


@transaction.atomic
def consolidate_duplicate_course(*, duplicate: Course, canonical: Course) -> dict[str, int]:
    """Mükerrer dersi kanonik derse birleştirir — referansları taşır.

    - Takma adlar kanoniğe taşınır; sınav dersleri (F3'te gelir) varsa
      `get_model` ile taşınır — model yokken sessizce 0.
    - Kanonik `levels`, kopyanınkiyle BİRLEŞTİRİLİR (seviye kaybı yok).
    - Kopya adı → kanonik için CourseAlias öğrenilir (sonraki importlar tekrar
      mükerrer üretmez); kopya soft-delete edilir.
    """
    from django.apps import apps as django_apps

    if duplicate.pk == canonical.pk:
        raise ValidationError("Kaynak ve hedef ders aynı olamaz.")
    if canonical.deleted_at is not None:
        raise ValidationError("Hedef ders silinmiş olamaz.")
    if duplicate.deleted_at is not None:
        raise ValidationError("Kaynak ders zaten silinmiş.")

    now = timezone.now()
    moved_aliases = CourseAlias.objects.filter(course=duplicate).update(
        course=canonical, updated_at=now
    )

    moved_exams = 0
    dropped_exams = 0
    try:
        esc = django_apps.get_model("sinav", "ExamSessionCourse")
    except LookupError:
        esc = None  # sınav modülü F3'te gelir
    if esc is not None:
        for sc in esc.objects.filter(course=duplicate, deleted_at__isnull=True):
            clash = esc.objects.filter(
                session_id=sc.session_id,
                course=canonical,
                level=sc.level,
                deleted_at__isnull=True,
            ).exists()
            if clash:
                sc.delete()
                dropped_exams += 1
            else:
                sc.course = canonical
                sc.save(update_fields=["course", "updated_at"])
                moved_exams += 1

    canon_levels = sorted(int(lvl) for lvl in (canonical.levels or []))
    merged = sorted({*canon_levels, *(int(lvl) for lvl in (duplicate.levels or []))})
    if merged != canon_levels:
        canonical.levels = merged
        canonical.save(update_fields=["levels", "updated_at"])

    learn_course_alias(name=duplicate.name, course=canonical)
    duplicate.delete()

    return {
        "aliases": moved_aliases,
        "exams": moved_exams,
        "dropped_exams": dropped_exams,
    }
