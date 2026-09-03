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
from typing import Any

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
    """`import_course_rows` / `sync_catalog` özeti.

    `restored`: çizelge dışı (pasif + `catalog_excluded`) iken çizelgeye geri
    girip yeniden açılan; `excluded`: yürürlükteki çizelgede artık bulunmayıp
    pasifleşen MEB dersi. İkisi de yalnız senkronda dolar.
    """

    created: int = 0
    updated: int = 0
    unchanged: int = 0
    restored: int = 0
    excluded: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


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
            # Çizelge dışı kaldığı için senkronun pasifleştirdiği ders çizelgeye
            # geri girdi: yalnız BU bayraklı kayıt yeniden açılır (idarecinin
            # elle pasifleştirdiği ders bayraksızdır, dokunulmaz — K5).
            restored = existing.catalog_excluded
            if restored:
                existing.is_active = True
                existing.catalog_excluded = False
                result.restored += 1
            if (
                not restored
                and existing.levels == levels
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
            if not restored:
                result.updated += 1
    return result


def catalog_year() -> int:
    """Katalog senkronunun ders yılı (ilk yıl): aktif ders yılı, yoksa bugünün yılı.

    Eylül ve sonrası yeni ders yılını başlatır (kurulumun 2. adımından önce
    ders yılı henüz yoktur; ilk senkron takvimden türetir, yıl aktifleşince
    damga değişir ve senkron yenilenir). Yerel tarih (`localdate`) — UTC'den
    yerel tarih türetme yasağı (CLAUDE.md §2).
    """
    from apps.okul import selectors as okul_selectors

    active = okul_selectors.active_school_year()
    if active is not None:
        return int(active.start_date.year)
    today = timezone.localdate()
    return today.year if today.month >= 9 else today.year - 1


def _current_plan(
    *,
    root: str | None = None,
    school_type: str | None = None,
    has_prep: bool | None = None,
    overrides: dict[str, Any] | None = None,
) -> Any:
    """Okulun yapılandırmasından çözülmüş çizelge planı (`catalog.CatalogPlan`).

    `school_type`/`has_prep`/`overrides` verilirse KAYITLI yapılandırma yerine
    onlar kullanılır (önizleme: kurulum/ayar ekranı henüz kaydedilmemiş seçimin
    planını gösterir). Seviye kümesi de önizlenen türden türetilir.
    """
    from apps.dersler import catalog
    from apps.okul.models import SchoolConfig, grade_levels_for

    config = SchoolConfig.load()
    tur = config.school_type if school_type is None else school_type
    prep = config.has_prep_class if has_prep is None else has_prep
    atamalar = config.level_programs if overrides is None else overrides
    return catalog.resolve_plan(
        school_type=tur,
        has_prep=prep,
        levels=grade_levels_for(tur, has_prep_class=prep),
        year=catalog_year(),
        overrides=atamalar,
        root=root,
    )


def sync_catalog(*, plan: Any) -> CatalogImportResult:
    """Kataloğu okulun etkin çizelge satırlarına çeker (idempotent).

    1. Etkin satırlar ada göre upsert edilir (`import_course_rows` — MEB kazanır,
       `is_active` korunur, çizelge dışı bayraklı kayıt geri açılır).
    2. Aktif MEB dersi etkin satırlarda YOKSA pasifleşir ve `catalog_excluded`
       işaretlenir — okul türü/hazırlık/ders yılı değişince eski çizelgenin
       dersleri havuzda kalmasın. Elle (MANUAL) dersler ve idarecinin
       pasifleştirdikleri dokunulmaz.
    3. Okulun türü için HİÇ program dosyası yoksa (TB2: veri sonraki sürümde)
       hiçbir kayda dokunulmaz — "veri yok" sessiz silmeye dönüşmez.
    """
    from apps.dersler import catalog as catalog_mod

    rows = plan.rows()
    result = CatalogImportResult()
    result.warnings = list(plan.warnings)
    candidates = catalog_mod.candidates_for(
        plan.programs, school_type=plan.school_type, has_prep=plan.has_prep
    )
    explicit = any(p.explicit for p in plan.plans.values())
    if not candidates and not explicit:
        result.warnings.append(
            "Bu okul türü için çizelge verisi bu sürümde yok; havuz elle doldurulur."
        )
        return result
    imported = import_course_rows(rows)
    result.created, result.updated, result.unchanged, result.restored = (
        imported.created,
        imported.updated,
        imported.unchanged,
        imported.restored,
    )
    result.errors = imported.errors
    names = {text.normalize_course_name(r.name) for r in rows}
    with transaction.atomic():
        stale = Course.objects.filter(source=CourseSource.MEB_CATALOG, is_active=True).exclude(
            name__in=names
        )
        result.excluded = stale.update(
            is_active=False, catalog_excluded=True, updated_at=timezone.now()
        )
    return result


def ensure_catalog_synced(
    *, root: str | None = None, force: bool = False
) -> CatalogImportResult | None:
    """Katalog damgası değiştiyse senkronu koşar; aynıysa None döner (ucuz yol).

    Damga = okul türü + hazırlık + seviyeler + seviye atamaları + ders yılı +
    program dosyalarının içerik özetleri. Böylece (a) ilk kurulum, (b) ayar
    değişikliği, (c) ders yılı devri ve (d) uygulama sürümüyle gelen yeni/
    değişmiş çizelge dosyası (K5) aynı yoldan kataloğa iner — eski "MEB kaydı
    varsa dosyayı okuma" erken dönüşü ve veri göçü ihtiyacı kalktı.
    Program dosyası hiç yoksa SESSİZCE atlar (TB2 — elle ekleme yolu açık).
    """
    from apps.okul.models import SchoolConfig

    plan = _current_plan(root=root)
    if not plan.programs:
        return None
    config = SchoolConfig.load()
    if not force and config.pk is not None and config.catalog_stamp == plan.stamp:
        return None
    result = sync_catalog(plan=plan)
    with transaction.atomic():
        row, _created = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
        row.catalog_stamp = plan.stamp
        row.save(update_fields=["catalog_stamp", "updated_at"])
    return result


def ensure_meb_catalog(*, path: str | None = None) -> CatalogImportResult:
    """Geriye dönük giriş: verilen kök/dosyadan kataloğu senkronlar (damga ile idempotent)."""
    return ensure_catalog_synced(root=path) or CatalogImportResult()


def catalog_status(
    *,
    root: str | None = None,
    school_type: str | None = None,
    has_prep: bool | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ders havuzu ekranının "yürürlükteki çizelge" paneli + ayar matrisinin verisi.

    Önizleme parametreleri verilirse (`school_type`/`has_prep`/`overrides`) plan
    kaydedilmemiş seçime göre çözülür; `synced` o durumda anlamsızdır (False).
    """
    from apps.dersler import catalog as catalog_mod
    from apps.okul.models import SchoolConfig, SchoolType

    config = SchoolConfig.load()
    preview = school_type is not None or has_prep is not None or overrides is not None
    plan = _current_plan(root=root, school_type=school_type, has_prep=has_prep, overrides=overrides)
    defaults = catalog_mod.default_assignment(
        plan.programs,
        school_type=plan.school_type,
        has_prep=plan.has_prep,
        levels=plan.levels,
        year=plan.year,
    )
    programs_out = [
        {
            "key": p.key,
            "name": p.name,
            "school_type": p.school_type,
            "school_type_label": p.school_type_label,
            "has_prep": p.has_prep,
            "department": p.department,
            "source": p.source,
            "start_year": p.start_year,
            "phased": p.phased,
            "default_included": p.default_included,
            "course_count": len(p.rows),
        }
        for p in sorted(plan.programs.values(), key=lambda p: (p.school_type, p.key))
    ]
    levels_out: list[dict[str, Any]] = []
    for level in plan.levels:
        lp = plan.plans[level]
        roles: dict[str, list[str]] = {}
        for key in lp.common_from:
            roles.setdefault(key, []).append("ortak")
        for key in lp.elective_from:
            roles.setdefault(key, []).append("seçmeli")
        levels_out.append(
            {
                "level": level,
                "label": catalog_mod.level_label(level),
                "explicit": lp.explicit,
                "programs": [
                    {
                        "key": key,
                        "name": plan.programs[key].name if key in plan.programs else key,
                        "source": plan.programs[key].source if key in plan.programs else "",
                        "role": "+".join(role_list),
                    }
                    for key, role_list in roles.items()
                ],
                "default_program_keys": list(defaults[level].program_keys),
                "warnings": list(lp.warnings),
            }
        )
    try:
        type_label = str(SchoolType(plan.school_type).label)
    except ValueError:
        type_label = plan.school_type
    explicit_levels = [lp.level for lp in plan.plans.values() if lp.explicit]
    return {
        "year": plan.year,
        "year_label": f"{plan.year}-{plan.year + 1}",
        "school_type": plan.school_type,
        "school_type_label": type_label,
        "has_prep_class": plan.has_prep,
        "transitional": plan.transitional,
        "custom": bool(explicit_levels),
        "synced": (not preview and config.pk is not None and config.catalog_stamp == plan.stamp),
        "data_available": bool(
            catalog_mod.candidates_for(
                plan.programs, school_type=plan.school_type, has_prep=plan.has_prep
            )
        ),
        "warnings": list(plan.warnings),
        "levels": levels_out,
        "programs": programs_out,
        "school_types": catalog_mod.school_type_options(plan.programs),
    }


def school_type_options(*, root: str | None = None) -> list[dict[str, Any]]:
    """Kurulum/ayar seçicisi: okul türleri + bu sürümde çizelge verisi var mı."""
    from apps.dersler import catalog as catalog_mod

    return catalog_mod.school_type_options(catalog_mod.load_programs(root))


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
    """Tembel tohum girişi — katalog listesi/havuz doldurma öncesi çağrılır (K5).

    Damga eşitse maliyet birkaç dosya özetidir; farklıysa katalog okulun
    yürürlükteki çizelgesine çekilir ve takma adlar tamamlanır.
    """
    ensure_catalog_synced()
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


# --------------------------------------------------------------------------- #
# Seçmeli ders şube kapsamı (03.09.2026) — takvim kapsamının KAYNAĞI
# --------------------------------------------------------------------------- #


def course_section_offerings(*, course_id: int, school_year_id: int) -> dict[int, list[int]]:
    """Tek dersin seviye → CANLI şube listesi eşlemesi (yoksa boş sözlük)."""
    from apps.dersler import selectors as ders_selectors

    return {
        level: sections
        for (cid, level), sections in ders_selectors.course_section_map(school_year_id).items()
        if cid == course_id
    }


@transaction.atomic
def set_course_sections(
    *, course_id: int, school_year_id: int, offerings: list[dict[str, Any]]
) -> dict[int, list[int]]:
    """Dersin şube kapsamını TAMAMEN değiştirir (PUT semantiği) → yeni eşleme.

    `offerings` öğesi `{"level": 9, "section_ids": [1, 2]}`. Gönderilmeyen
    seviyenin kaydı SİLİNİR: diyalog dersin bütün seviyelerini birlikte
    gösterir, kısmi güncelleme "kaldırdım ama gitmedi" şaşkınlığı üretirdi.
    Boş `section_ids` de kaydı siler ("tanımsız" ile "boş" aynı sonuca çıkar;
    ikisi de havuz doldurmada atlanır).

    Kapsam YALNIZ seçmeli derste anlamlıdır: zorunlu ders seviyenin tamamında
    okutulur ve takvim havuzuna seviye geneli (LEVEL) girer.

    Şube denetimi takvim tarafıyla AYNI kalıptadır
    (`services_calendar._validate_entry_participants`): şube canlı olmalı, o
    ders yılına ve verilen seviyeye ait olmalı. Küme kimliği yazılmaz —
    arayüz kümeyi somut şube listesine açar (CLAUDE.md §3).
    """
    from apps.dersler.models import CourseSectionOffering
    from apps.okul.models import ClassSection, SchoolYear

    course = Course.objects.filter(pk=course_id).first()
    if course is None:
        raise ValidationError({"course": "Ders bulunamadı."})
    if course.course_type != CourseType.ELECTIVE:
        raise ValidationError(
            {
                "course": "Şube kapsamı yalnız seçmeli derslerde tanımlanır — zorunlu ders "
                "seviyenin tamamında okutulur."
            }
        )
    if not SchoolYear.objects.filter(pk=school_year_id).exists():
        raise ValidationError({"school_year": "Ders yılı bulunamadı."})

    temiz: dict[int, list[int]] = {}
    for item in offerings:
        try:
            level = int(item["level"])
        except (KeyError, TypeError, ValueError):
            raise ValidationError({"level": f"Geçersiz seviye: {item.get('level')!r}."}) from None
        ids: list[int] = []
        for raw in item.get("section_ids") or []:
            try:
                ids.append(int(raw))
            except (TypeError, ValueError):
                raise ValidationError({"section_ids": f"Geçersiz şube kimliği: {raw!r}."}) from None
        # Sıra korunarak teklenir (oturum/takvim tarafındaki `dict.fromkeys` deseni).
        ids = list(dict.fromkeys(ids))
        for sid in ids:
            section = ClassSection.objects.filter(pk=sid, school_year_id=school_year_id).first()
            if section is None:
                raise ValidationError({"section_ids": f"Şube bulunamadı (id={sid})."})
            if int(section.class_level) != level:
                raise ValidationError(
                    {
                        "section_ids": f"{section.class_label} şubesi {level}. seviyeye ait "
                        "değil — kapsam seviye seviye tanımlanır."
                    }
                )
        if ids:
            temiz[level] = ids

    CourseSectionOffering.objects.filter(course=course, school_year_id=school_year_id).delete()
    for level, ids in temiz.items():
        CourseSectionOffering.objects.create(
            course=course, school_year_id=school_year_id, level=level, section_ids=ids
        )
    return dict(sorted(temiz.items()))
