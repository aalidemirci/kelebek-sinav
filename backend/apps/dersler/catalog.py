"""Okul türü çizelgeleri — program dosyaları, yürürlük (kademeli) kuralı, seviye ataması, birleştirme.

Tasarım §7.2 (03.09.2026). Ders havuzu tek bir "MEB kataloğu" değil, okulun
YÜRÜRLÜKTEKİ çizelgelerinden türetilen bir kesittir:

- Her TTK haftalık ders çizelgesi bir **program dosyasıdır**
  (`data/ders-cizelgeleri/<program_key>.md`): üstte `- anahtar: değer` meta
  bloğu, altında `| Ders | Seviyeler | Tür | Sınav |` tabloları
  (`catalog_parser`). Meta alanları `ProgramMeta`'dadır.
- **Yürürlük kuralı** dosyada yaşar, kodda değil: `yururluk` (başlangıç ders
  yılı) + `kademeli` (evet → başlangıç yılında `kademeli_ilk_seviyeler`den
  başlayıp her yıl bir üst seviyeye taşınır). TTK 09.05.2025/5 (AL/Fen/SBL) tüm
  seviyelere aynı anda girer; TTK 09.05.2025/6-7-9-10 (GSL/Spor) ORTAK dersler
  bölümünü hazırlık-9-10'dan başlayarak kademeli, seçmelileri hemen uygular;
  MTAL çerçeve programları (2023-40 → 2024-41 → 2026-85) hazırlık+9'dan
  başlayarak kademelidir — aynı okulda üç neslin aynı anda yürürlükte olması
  olağandır. `covers()` bu üç kalıbı tek kuralla verir.
- **Seviye ataması**: okul türü + hazırlık bayrağı + ders yılından
  `default_assignment` türetir; `SchoolConfig.level_programs` sözlüğü seviye
  bazında EZER (kademeli tür dönüşümü: "9 → Fen, 10-12 → AL"; çok programlı
  okul: aynı seviyede birden çok program). Bölümlü türlerde (GSL: Görsel
  Sanatlar/Tiyatro/Müzik/Türk Müziği) varsayılan, türün bütün bölümlerinin
  birleşimidir; okul matristen istemediğini bırakır.
- **Birleştirme** (`effective_rows`): (ders adı) → seviye kümesi birleşimi.
  Aynı ad iki programda farklı türdeyse SEÇMELİ kazanır (havuz otomatik
  doldurması ORTAK+YAZILI çeker; şüphede fazla değil eksik doldurmak, idareci
  seçmeli diyaloğundan ekler — AL dosyasındaki "Bilişim Teknolojileri ve
  Yazılım" emsali). Sınav biçiminde YOK > UYGULAMA > YAZILI.

Kişisel veri içermez; dosya sistemi dışında hiçbir şeye bağımlı değildir
(DB'ye dokunmaz — senkron `services.sync_catalog`'dadır).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings

from apps.dersler.catalog_parser import parse_markdown_catalog, parse_program_meta
from apps.dersler.models import PREP_COURSE_LEVEL, CourseExamMode, CourseType
from apps.dersler.services import CourseRow
from apps.okul.models import SchoolType

#: Katalog dizininde program sayılmayan dosyalar.
SKIPPED_FILES = frozenset({"readme.md", "ders-adi-takma-adlari.md"})

#: Sınav biçimi çatışmasında "daha kısıtlayıcı" kazanır.
_EXAM_MODE_RANK: dict[str, int] = {
    CourseExamMode.WRITTEN: 0,
    CourseExamMode.PRACTICE: 1,
    CourseExamMode.NONE: 2,
}

_YEAR_RE = re.compile(r"^\s*(\d{4})(?:\s*[-/–]\s*\d{4})?\s*$")
_LEVELS_RE = re.compile(r"\d+")


def _yes(value: str, *, default: bool) -> bool:
    v = value.strip().casefold()
    if not v:
        return default
    return v in {"evet", "e", "var", "true", "1", "yes"}


def _start_year(value: str) -> int | None:
    m = _YEAR_RE.match(value)
    return int(m.group(1)) if m else None


@dataclass(frozen=True)
class CatalogProgram:
    """Tek çizelge program dosyası — meta + satırlar (+ ayrıştırma hataları)."""

    key: str
    name: str
    # Uygulandığı okul türleri (SchoolType değerleri). Boş = her okul türüne
    # uygulanan genel dosya. Çok Programlı AL gibi türler başka türlerin
    # çizelgelerini paylaşır: dosya `okul_turu: ANADOLU_LISESI, COK_PROGRAMLI_ANADOLU_LISESI`.
    school_types: tuple[str, ...]
    has_prep: bool
    department: str  # bölüm/varyant etiketi (GSL: "Müzik"); "" = tek bölüm
    source: str  # dayanak (TTK karar tarih/sayı + bağlantı)
    start_year: int | None  # yürürlük başlangıç ders yılının ilk yılı (2025 = 2025-2026)
    phased: bool
    phased_first_levels: tuple[int, ...]
    elective_phased: bool
    default_included: bool
    rows: tuple[CourseRow, ...]
    path: Path
    errors: tuple[str, ...] = ()
    digest: str = ""

    @property
    def school_type(self) -> str:
        """Birincil okul türü (dosyanın ait olduğu tür); genel dosyada ''."""
        return self.school_types[0] if self.school_types else ""

    @property
    def school_type_label(self) -> str:
        try:
            return str(SchoolType(self.school_type).label)
        except ValueError:
            return "Genel"

    def applies_to(self, school_type: str) -> bool:
        return not self.school_types or school_type in self.school_types

    def covers(self, level: int, year: int, *, course_type: str) -> bool:
        """Bu program `year` ders yılında `level` seviyesinde `course_type` satırlarını kapsar mı?

        - Yürürlük başlamamışsa hayır.
        - Kademesiz program (`kademeli: hayır`) tüm seviyeleri kapsar.
        - Kademeli program: seçmeliler `secmeli_kademeli: hayır` ise hemen; ortak
          dersler başlangıç yılında `kademeli_ilk_seviyeler`, her sonraki yıl
          bir üst seviye (kohort ilerler). Hazırlık (0) başlangıç yılından itibaren.
        """
        if self.start_year is None:
            return True  # yürürlük yazılmamış (genel/elle dosya) — sınırsız
        if year < self.start_year:
            return False
        if not self.phased:
            return True
        if course_type == CourseType.ELECTIVE and not self.elective_phased:
            return True
        if level == PREP_COURSE_LEVEL:
            return True  # hazırlık sınıfı kademeli çizelgeye başlangıç yılında girer
        top = max((lv for lv in self.phased_first_levels if lv >= 9), default=9)
        return level <= top + (year - self.start_year)

    def covers_any(self, level: int, year: int) -> bool:
        return any(
            self.covers(level, year, course_type=ct)
            for ct in (CourseType.COMMON, CourseType.ELECTIVE)
        )


def _program_from_file(path: Path) -> CatalogProgram:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    meta = parse_program_meta(text)
    parsed = parse_markdown_catalog(text, source_name=path.name)
    key = meta.get("program_key", "").strip() or path.stem
    first_levels_raw = meta.get("kademeli_ilk_seviyeler", "")
    first_levels = tuple(sorted({int(n) for n in _LEVELS_RE.findall(first_levels_raw)})) or (
        PREP_COURSE_LEVEL,
        9,
    )
    school_types = tuple(
        part.strip() for part in meta.get("okul_turu", "").split(",") if part.strip()
    )
    return CatalogProgram(
        key=key,
        name=meta.get("ad", "").strip() or key,
        school_types=school_types,
        has_prep=_yes(meta.get("hazirlik", ""), default=False),
        department=meta.get("bolum", "").strip(),
        source=meta.get("kaynak", "").strip(),
        start_year=_start_year(meta.get("yururluk", "")),
        phased=_yes(meta.get("kademeli", ""), default=False),
        phased_first_levels=first_levels,
        elective_phased=_yes(meta.get("secmeli_kademeli", ""), default=False),
        default_included=_yes(meta.get("varsayilan", ""), default=True),
        rows=tuple(parsed.rows),
        path=path,
        errors=tuple(parsed.errors),
        digest=hashlib.sha256(raw).hexdigest(),
    )


def load_programs(root: str | Path | None = None) -> dict[str, CatalogProgram]:
    """Katalog dizinindeki program dosyaları (`program_key` → program). Dizin yoksa boş.

    Bir dosya yolu verilirse yalnız o dosya yüklenir (testler). Aynı anahtar iki
    dosyada geçerse dosya adına göre son gelen kazanır — bilinçli bir durum
    değildir, `program_errors` listesine yazılır.
    """
    base = Path(root if root is not None else settings.CATALOG_DIR)
    if base.is_file():
        files = [base]
    elif base.is_dir():
        files = sorted(f for f in base.glob("*.md") if f.name.lower() not in SKIPPED_FILES)
    else:
        return {}
    programs: dict[str, CatalogProgram] = {}
    for file in files:
        program = _program_from_file(file)
        if not program.rows and not program.errors:
            continue  # tablo içermeyen açıklama dosyası
        programs[program.key] = program
    return programs


@dataclass(frozen=True)
class LevelPlan:
    """Bir seviyede uygulanan program(lar) — birleştirme ve durum ekranı girdisi."""

    level: int
    common_from: tuple[str, ...]  # ORTAK satırları veren program anahtarları
    elective_from: tuple[str, ...]  # SEÇMELİ satırları veren program anahtarları
    explicit: bool  # SchoolConfig.level_programs ile mi belirlendi
    warnings: tuple[str, ...] = ()

    @property
    def program_keys(self) -> tuple[str, ...]:
        seen: list[str] = []
        for key in (*self.common_from, *self.elective_from):
            if key not in seen:
                seen.append(key)
        return tuple(seen)


def level_label(level: int) -> str:
    return "Hazırlık" if level == PREP_COURSE_LEVEL else f"{level}. sınıf"


def candidates_for(
    programs: Mapping[str, CatalogProgram], *, school_type: str, has_prep: bool
) -> list[CatalogProgram]:
    """Okul türüne ait (ve genel) programlar; bölüm başına hazırlık varyantı süzülür.

    Bölüm grubunda hazırlık bayrağı okulla EŞLEŞEN dosya varsa yalnız onlar
    kalır; yoksa öbür varyant kullanılır (AİHL tek dosyadır: hazırlık sütunlu
    çizelge hazırlıksız okulda da doğrudur, 0. seviye okul seviye kümesince
    zaten düşer).
    """
    typed = [p for p in programs.values() if p.default_included and p.applies_to(school_type)]
    by_dept: dict[tuple[str, str], list[CatalogProgram]] = {}
    for p in typed:
        by_dept.setdefault((p.school_type, p.department), []).append(p)
    chosen: list[CatalogProgram] = []
    for group in by_dept.values():
        matching = [p for p in group if p.has_prep == has_prep]
        chosen.extend(matching or group)
    return chosen


def _newest_covering(
    group: Iterable[CatalogProgram], level: int, year: int, course_type: str
) -> CatalogProgram | None:
    covering = [p for p in group if p.covers(level, year, course_type=course_type)]
    if not covering:
        return None
    return max(covering, key=lambda p: (p.start_year or -1, p.key))


def default_assignment(
    programs: Mapping[str, CatalogProgram],
    *,
    school_type: str,
    has_prep: bool,
    levels: Iterable[int],
    year: int,
) -> dict[int, LevelPlan]:
    """Okul türü + hazırlık + ders yılından seviye → program planı (yürürlük kuralıyla).

    Aynı bölüm grubunda birden çok nesil varsa her (seviye, tür) için EN YENİ
    kapsayan nesil seçilir. Hiçbir nesil kapsamıyorsa (önceki çizelge bu
    sürümde aktarılmamış olabilir) en yeni program yedek olarak kullanılır ve
    plan bir UYARI taşır — sessiz düşmenin panzehiri.
    """
    candidates = candidates_for(programs, school_type=school_type, has_prep=has_prep)
    groups: dict[tuple[str, str], list[CatalogProgram]] = {}
    for p in candidates:
        groups.setdefault((p.school_type, p.department), []).append(p)
    plans: dict[int, LevelPlan] = {}
    for level in sorted(set(levels)):
        common: list[str] = []
        elective: list[str] = []
        warnings: list[str] = []
        for group in groups.values():
            has_level = [p for p in group if any(level in r.levels for r in p.rows)]
            if not has_level:
                continue
            for course_type, bucket in (
                (CourseType.COMMON, common),
                (CourseType.ELECTIVE, elective),
            ):
                pick = _newest_covering(has_level, level, year, course_type)
                if pick is None:
                    pick = max(has_level, key=lambda p: (p.start_year or -1, p.key))
                    tur = "ortak" if course_type == CourseType.COMMON else "seçmeli"
                    warnings.append(
                        f"{level_label(level)} {tur} dersleri için {year}-{year + 1} yılında "
                        f"yürürlükteki önceki çizelge bu sürümde yok; '{pick.name}' kullanıldı."
                    )
                if pick.key not in bucket:
                    bucket.append(pick.key)
        plans[level] = LevelPlan(
            level=level,
            common_from=tuple(common),
            elective_from=tuple(elective),
            explicit=False,
            warnings=tuple(warnings),
        )
    return plans


def apply_overrides(
    plans: Mapping[int, LevelPlan],
    overrides: Mapping[str, object] | None,
    programs: Mapping[str, CatalogProgram],
) -> tuple[dict[int, LevelPlan], list[str]]:
    """`SchoolConfig.level_programs` sözlüğünü plana işler; bilinmeyen anahtar uyarıya düşer.

    Açık atama yürürlük süzgecinden GEÇMEZ: idareci "bu seviyede bu program"
    dediyse o programın o seviyedeki tüm satırları uygulanır.
    """
    result = dict(plans)
    warnings: list[str] = []
    for raw_level, raw_keys in (overrides or {}).items():
        try:
            level = int(raw_level)
        except (TypeError, ValueError):
            warnings.append(f"Seviye anahtarı sayısal değil: {raw_level!r}.")
            continue
        if level not in result:
            continue  # okulun seviye kümesinde olmayan seviye — yok sayılır
        keys: list[str] = []
        for key in raw_keys if isinstance(raw_keys, list | tuple) else []:
            if str(key) in programs:
                keys.append(str(key))
            else:
                warnings.append(f"{level_label(level)}: '{key}' adlı çizelge programı bulunamadı.")
        result[level] = LevelPlan(
            level=level,
            common_from=tuple(keys),
            elective_from=tuple(keys),
            explicit=True,
            warnings=(),
        )
    return result, warnings


def effective_rows(
    plans: Mapping[int, LevelPlan], programs: Mapping[str, CatalogProgram]
) -> list[CourseRow]:
    """Seviye planından okulun etkin ders satırları (ad → seviye birleşimi)."""
    levels_by_name: dict[str, set[int]] = {}
    type_by_name: dict[str, str] = {}
    exam_by_name: dict[str, str] = {}

    def _add(row: CourseRow, level: int) -> None:
        levels_by_name.setdefault(row.name, set()).add(level)
        prev = type_by_name.get(row.name)
        if prev is None or row.course_type == CourseType.ELECTIVE:
            type_by_name[row.name] = row.course_type
        prev_exam = exam_by_name.get(row.name)
        if prev_exam is None or _EXAM_MODE_RANK[row.exam_mode] > _EXAM_MODE_RANK[prev_exam]:
            exam_by_name[row.name] = row.exam_mode

    for level, plan in plans.items():
        for course_type, keys in (
            (CourseType.COMMON, plan.common_from),
            (CourseType.ELECTIVE, plan.elective_from),
        ):
            for key in keys:
                program = programs.get(key)
                if program is None:
                    continue
                for row in program.rows:
                    if row.course_type == course_type and level in row.levels:
                        _add(row, level)
    return [
        CourseRow(
            name=name,
            levels=tuple(sorted(levels_by_name[name])),
            course_type=type_by_name[name],
            exam_mode=exam_by_name[name],
        )
        for name in sorted(levels_by_name)
    ]


def compute_stamp(
    *,
    year: int,
    school_type: str,
    has_prep: bool,
    levels: Iterable[int],
    overrides: Mapping[str, object] | None,
    programs: Mapping[str, CatalogProgram],
) -> str:
    """Senkron girdisinin özeti — değişmediyse katalog yeniden türetilmez."""
    payload = {
        "v": 2,
        "year": year,
        "school_type": school_type,
        "has_prep": has_prep,
        "levels": sorted(set(levels)),
        "overrides": overrides or {},
        "files": {key: p.digest for key, p in sorted(programs.items())},
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


@dataclass
class CatalogPlan:
    """Tek okul için çözülmüş plan — senkron ve durum ekranı ortak tüketir."""

    year: int
    school_type: str
    has_prep: bool
    levels: tuple[int, ...]
    plans: dict[int, LevelPlan]
    programs: dict[str, CatalogProgram]
    warnings: list[str] = field(default_factory=list)
    stamp: str = ""

    @property
    def transitional(self) -> bool:
        """Seviyeler arasında farklı program kümeleri var mı (kademeli dönüşüm)?"""
        seen = {tuple(sorted(p.program_keys)) for p in self.plans.values()}
        return len(seen) > 1

    def rows(self) -> list[CourseRow]:
        return effective_rows(self.plans, self.programs)


def resolve_plan(
    *,
    school_type: str,
    has_prep: bool,
    levels: Iterable[int],
    year: int,
    overrides: Mapping[str, object] | None,
    root: str | Path | None = None,
) -> CatalogPlan:
    """Dosyaları yükle, varsayılanı türet, açık atamaları işle, damgayı hesapla."""
    programs = load_programs(root)
    level_tuple = tuple(sorted(set(levels)))
    plans = default_assignment(
        programs, school_type=school_type, has_prep=has_prep, levels=level_tuple, year=year
    )
    plans, warnings = apply_overrides(plans, overrides, programs)
    for plan in plans.values():
        warnings.extend(plan.warnings)
    for program in programs.values():
        warnings.extend(program.errors)
    return CatalogPlan(
        year=year,
        school_type=school_type,
        has_prep=has_prep,
        levels=level_tuple,
        plans=plans,
        programs=programs,
        warnings=warnings,
        stamp=compute_stamp(
            year=year,
            school_type=school_type,
            has_prep=has_prep,
            levels=level_tuple,
            overrides=overrides,
            programs=programs,
        ),
    )


def school_type_options(programs: Mapping[str, CatalogProgram]) -> list[dict[str, object]]:
    """Kurulum/ayarlar seçicisi: her okul türü + bu sürümde çizelge verisi var mı."""
    options: list[dict[str, object]] = []
    for school_type in SchoolType:
        typed = [p for p in programs.values() if str(school_type) in p.school_types]
        options.append(
            {
                "value": str(school_type),
                "label": str(school_type.label),
                "available": bool(typed),
                "program_keys": sorted(p.key for p in typed),
            }
        )
    return options
