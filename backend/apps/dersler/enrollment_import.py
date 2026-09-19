"""e-Okul "Seçmeli Ders Öğrencileri" (OOK10002R010) PDF içe aktarması (19.09.2026).

e-Okul yolu: Öğrenci Seçmeli Derslerini Belirle ekranı → Raporlar →
OOK10002R010 - Seçmeli Ders Öğrencileri. Rapor her seçmeli ders için bir grup
basar: sayfa başında ``SEÇMELİ <DERS> DERSİ ÖĞRENCİLERİ`` başlığı, altında
``Öğr.No · Adı Soyadı · Sınıfı`` satırları. pypdf'in varsayılan metin çıkarımı
satırı ``<okul no> <ad soyad…> <AL - 9. Sınıf / D Şubesi (…)> <sıra no>``
düzeninde verir.

Neden PDF (Excel değil): aynı raporun e-Okul Excel ihracı ders grubu
başlıklarını DÜŞÜRÜR — satırlar gelir ama hangi derse ait oldukları yazmaz.
Gerçek bir okul raporunda (25 ders, 8.385 satır) PDF'ten okunan her grubun
okul numarası kümesi ve sınıf etiketleri Excel ihracıyla birebir doğrulandı
(19.09.2026); TB1'deki "e-Okul PDF'i v1'de alınmaz" kararının istisnasıdır ve
yalnız bu rapor içindir.

KVKK: öğrenci ADI hiç okunmaz ve saklanmaz — eşleştirme okul numarasıyladır.
Uyarı metinleri okul numarası ve sayfa/satır konumu taşır, ad taşımaz.

Yazma kuralı — KAPSAM (19.09.2026): raporun kapsadığı şubeler, raporda satırı
geçen şubelerdir (hangi derste olursa olsun). e-Okul raporu okulun tamamı, bir
sınıf düzeyi ya da tek şube için alınabilir; rapordaki her ders için liste ve
şube kapsamı (`CourseSectionOffering`) YALNIZ kapsanan şubelerde rapora çekilir:
kapsanan şubede öğrencisi raporda yoksa şube dersten çıkar, kapsam dışı şubenin
listesine ve kapsamına dokunulmaz. Raporda hiç olmayan derslere de dokunulmaz;
listesi olup raporda yer almayanlar önizlemede ayrıca gösterilir (ders bazında
süzülmüş bir rapor başka derslerin listesini silmesin). Bedeli: hiçbir seçmeliyi
almayan şube (raporda satırı yok) kapsanmaz — eski listesi varsa kalır, Ders
Havuzu'ndan elle temizlenir.

Önizleme deseni öğrenci içe aktarmasıyla AYNIDIR: gerçek yazım atomik blokta
koşar ve geri alınır (%100 sonuç paritesi), ardından kalıcı PREVIEWED izi.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from io import BytesIO
from typing import Any

from django.db import transaction
from django.db.models import Q

from apps.dersler import selectors as ders_selectors
from apps.dersler.models import Course, CourseEnrollment, CourseSectionOffering, CourseType
from apps.dersler.text import course_match_key, level_label
from apps.okul import eokul, normalize
from apps.okul.excel_ogrenci import ParserError

#: Uyarı listesi sınırı: öğrenci listesi hiç aktarılmamış bir kurulumda binlerce
#: "okul no bulunamadı" satırı raporu okunmaz kılardı — kalanı sayıyla özetlenir.
ISSUE_LIMIT = 60

#: Ders grubu başlığı: 'SEÇMELİ KUR`AN-I KERİM DERSİ ÖĞRENCİLERİ'.
_BASLIK_RE = re.compile(r"^(?P<ad>.+?)\s+DERS[İI]\s+ÖĞRENC[İI]LER[İI]$")
#: Öğrenci satırı — ad soyad kısmı YAKALANMAZ (KVKK: gerekmeyen veri okunmaz).
_SATIR_RE = re.compile(
    r"^(?P<no>\d{1,10})\s+.+?\s+"
    r"(?P<sinif>\S+\s*-\s*(?:\d{1,2}\s*\.\s*Sınıf|Hazırlık\s+Sınıfı)\s*/\s*\S+\s+Şubesi"
    r"(?:\s*\(.*\))?)\s+(?P<sira>\d{1,5})$"
)
#: Aday öğrenci satırı: rakamla başlayıp boşlukla devam eden satır. Sayfa altı
#: tarih damgası (tek sözcük, rakamla başlar) aday sayılmaz.
_ADAY_RE = re.compile(r"^\d+\s")
#: e-Okul ders adında kesme işaretinin ters tırnak/tipografik biçimleri.
_KESME = str.maketrans({"`": "'", "´": "'", "’": "'", "‘": "'"})
_SECMELI_ONEK = "seçmeli "


@dataclass(frozen=True)
class ReportLine:
    """Rapordaki tek öğrenci satırı — ad TAŞIMAZ."""

    page: int
    line: int
    student_number: str
    class_level: int
    class_section: str


@dataclass
class ReportGroup:
    """Bir ders grubu: e-Okul başlığı (kişisel değil) + satırları."""

    title: str
    lines: list[ReportLine] = field(default_factory=list)


@dataclass
class ParsedReport:
    pages: int
    groups: list[ReportGroup] = field(default_factory=list)
    #: Rakamla başlayıp satır düzenine uymayan satırların (sayfa, satır) konumu.
    unreadable: list[tuple[int, int]] = field(default_factory=list)

    @property
    def total_rows(self) -> int:
        return sum(len(g.lines) for g in self.groups)


# --------------------------------------------------------------------------- #
# Saf ayrıştırma — metinden gruplara (DB yok)
# --------------------------------------------------------------------------- #


def _sinif(metin: str) -> tuple[int, str] | None:
    """'AL -  9. Sınıf / İ Şubesi (…)' → (9, 'İ'); hazırlık → (0, 'A')."""
    kanonik = eokul.blok_sinifi([metin])
    if kanonik is None:
        return None
    return normalize.normalize_class_section(kanonik, valid_levels=(0, 9, 10, 11, 12))


def parse_report_pages(pages: Iterable[str]) -> ParsedReport:
    """Sayfa metinlerinden ders gruplarını çıkarır — SAF (testler sentetik metinle koşar).

    Başlık her sayfada yinelenir; ardışık aynı başlık tek gruptur. Başlıktan
    ÖNCE gelen öğrenci satırı (bozuk dosya) okunamaz sayılır.
    """
    rapor = ParsedReport(pages=0)
    for sayfa_no, metin in enumerate(pages, start=1):
        rapor.pages = sayfa_no
        for satir_no, ham in enumerate((metin or "").splitlines(), start=1):
            satir = " ".join(ham.split())
            if not satir:
                continue
            baslik = _BASLIK_RE.match(satir)
            if baslik is not None:
                ad = baslik.group("ad")
                if not rapor.groups or rapor.groups[-1].title != ad:
                    rapor.groups.append(ReportGroup(title=ad))
                continue
            if not _ADAY_RE.match(satir):
                continue
            eslesme = _SATIR_RE.match(satir)
            sinif = _sinif(eslesme.group("sinif")) if eslesme is not None else None
            if eslesme is None or sinif is None or not rapor.groups:
                rapor.unreadable.append((sayfa_no, satir_no))
                continue
            rapor.groups[-1].lines.append(
                ReportLine(
                    page=sayfa_no,
                    line=satir_no,
                    student_number=eslesme.group("no"),
                    class_level=sinif[0],
                    class_section=sinif[1],
                )
            )
    return rapor


def parse_report_pdf(file_bytes: bytes) -> ParsedReport:
    """PDF baytlarından rapor; PDF değilse ya da başlık yoksa Türkçe `ParserError`."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        okuyucu = PdfReader(BytesIO(file_bytes))
        sayfalar = [sayfa.extract_text() or "" for sayfa in okuyucu.pages]
    except (PdfReadError, ValueError, OSError) as exc:
        raise ParserError(
            "Dosya PDF olarak okunamadı. e-Okul'da 'Öğrenci Seçmeli Derslerini Belirle' "
            "ekranının Raporlar menüsünden OOK10002R010 - Seçmeli Ders Öğrencileri "
            "raporunu PDF olarak kaydedin."
        ) from exc
    rapor = parse_report_pages(sayfalar)
    if not rapor.groups:
        raise ParserError(
            "Bu dosyada 'SEÇMELİ … DERSİ ÖĞRENCİLERİ' başlığı bulunamadı — e-Okul "
            "OOK10002R010 - Seçmeli Ders Öğrencileri raporu olmayabilir. Excel ihracı ders "
            "adlarını içermediği için raporun PDF biçimi gerekir."
        )
    return rapor


# --------------------------------------------------------------------------- #
# Ders adı çözümü — e-Okul başlığı → havuzdaki SEÇMELİ ders
# --------------------------------------------------------------------------- #


def _adaylar(baslik: str) -> list[Course]:
    """Sıralı aday dersler (tekrarsız): tam ad → takma ad → öneksiz → 'Seçmeli <takma hedef>'.

    e-Okul her seçmeliye 'SEÇMELİ' öneki koyar; resmî adı öneksiz olan ders
    ('Adabımuaşeret') takma ad tablosundan, resmî adı önekli olan ('Seçmeli
    Matematik') doğrudan bulunur. 'SEÇMELİ YABANCI DİL' ise takma ad zincirinde
    zorunlu 'Birinci Yabancı Dil'e düşerdi; doğrusu 'Seçmeli Birinci Yabancı
    Dil'dir — dördüncü adım bu yüzden takma ad hedefinin ÖNEKLİ biçimini dener.
    """
    tam = baslik.translate(_KESME)
    anahtar = course_match_key(tam)
    oneksiz = anahtar.removeprefix(_SECMELI_ONEK) if anahtar.startswith(_SECMELI_ONEK) else ""
    sirali: list[Course | None] = [
        ders_selectors.course_by_normalized_name(tam),
        ders_selectors.course_by_alias(tam),
    ]
    if oneksiz:
        sirali.append(ders_selectors.course_by_normalized_name(oneksiz))
        hedef = ders_selectors.course_by_alias(oneksiz)
        if hedef is not None:
            sirali.append(ders_selectors.course_by_normalized_name(f"Seçmeli {hedef.name}"))
            sirali.append(hedef)
    gorulen: set[int] = set()
    sonuc: list[Course] = []
    for ders in sirali:
        if ders is not None and ders.pk not in gorulen:
            gorulen.add(ders.pk)
            sonuc.append(ders)
    return sonuc


def resolve_report_course(baslik: str) -> tuple[Course | None, str]:
    """(seçmeli ders, "") ya da (None, gerekçe) — gerekçe kullanıcıya gösterilir."""
    adaylar = _adaylar(baslik)
    for ders in adaylar:
        if ders.course_type == CourseType.ELECTIVE:
            return ders, ""
    if adaylar:
        return None, (
            f"Ders havuzunda '{adaylar[0].name}' zorunlu ders olarak kayıtlı; öğrenci listesi "
            "yalnız seçmeli derslerde tutulur."
        )
    return None, (
        "Ders havuzunda karşılığı bulunamadı — dersi Ders Havuzu'na ekleyip raporu yeniden "
        "aktarın."
    )


# --------------------------------------------------------------------------- #
# Rapor (arayüz + ImportRun.report)
# --------------------------------------------------------------------------- #


@dataclass
class ReportIssue:
    """Satır sorunu — sayfa/satır konumu + okul no (ad YOK)."""

    page: int
    line: int
    issue: str
    value: str = ""


@dataclass
class CourseSummary:
    title: str  # e-Okul başlığı (örn. 'SEÇMELİ KUR'AN-I KERİM')
    status: str  # "matched" | "unmatched"
    course_id: int | None = None
    course_name: str = ""
    note: str = ""
    report_rows: int = 0
    students: int = 0
    sections: list[str] = field(default_factory=list)  # '9/A' etiketleri, Türk alfabesiyle


@dataclass
class ElectiveImportReport:
    file_hash: str
    file_name: str = ""
    school_year: str = ""
    pages: int = 0
    total_rows: int = 0
    processed: int = 0
    already_imported: bool = False
    dry_run: bool = False
    courses: list[CourseSummary] = field(default_factory=list)
    #: Raporun kapsadığı şube sayısı ve sınıf düzeyleri ("9. Sınıf") — yenileme
    #: yalnız bu şubelerde yapılır (süzülmüş rapor öbür şubeleri silmesin).
    covered_section_count: int = 0
    covered_levels: list[str] = field(default_factory=list)
    #: Listesi olup bu raporda YER ALMAYAN dersler — dokunulmadı.
    untouched_courses: list[str] = field(default_factory=list)
    warnings: list[ReportIssue] = field(default_factory=list)
    skipped: list[ReportIssue] = field(default_factory=list)
    #: Sınırı aşıp listeye yazılmayan sorun sayıları (rapor okunur kalsın).
    warnings_truncated: int = 0
    skipped_truncated: int = 0

    def add_warning(self, page: int, line: int, issue: str, value: str = "") -> None:
        if len(self.warnings) < ISSUE_LIMIT:
            self.warnings.append(ReportIssue(page, line, issue, value))
        else:
            self.warnings_truncated += 1

    def add_skip(self, page: int, line: int, issue: str, value: str = "") -> None:
        if len(self.skipped) < ISSUE_LIMIT:
            self.skipped.append(ReportIssue(page, line, issue, value))
        else:
            self.skipped_truncated += 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Yazım (commit) + önizleme
# --------------------------------------------------------------------------- #


def _sinif_etiketi(level: int, section: str) -> str:
    return f"Hz/{section}" if level == 0 else f"{level}/{section}"


@transaction.atomic
def _ingest(parsed: ParsedReport, *, source_hash: str, file_name: str) -> ElectiveImportReport:
    from apps.dersler import services as ders_services
    from apps.okul.models import ClassSection, ImportSourceType, Student, StudentStatus
    from apps.okul.selectors import active_school_year
    from apps.okul.services import imports as okul_imports

    year = active_school_year()
    if year is None:
        raise ParserError(
            "Aktif ders yılı yok — önce Ayarlar → Ders Yılları'ndan yılı açın; öğrenci "
            "listeleri ders yılına bağlıdır."
        )
    ders_services.ensure_seeded()  # katalog + takma adlar (ad çözümü onlara dayanır)

    rapor = ElectiveImportReport(
        file_hash=source_hash,
        file_name=file_name,
        school_year=year.name,
        pages=parsed.pages,
        total_rows=parsed.total_rows,
    )
    run, already = okul_imports.open_import_run(
        source_type=ImportSourceType.ELECTIVES, source_hash=source_hash, file_name=file_name
    )
    rapor.already_imported = already
    for bozuk_sayfa, bozuk_satir in parsed.unreadable:
        rapor.add_skip(
            bozuk_sayfa, bozuk_satir, "Satır okunamadı (okul no / sınıf düzeni tanınmadı)."
        )

    ogrenciler: dict[str, Student] = {
        s.student_number: s
        for s in Student.objects.filter(status=StudentStatus.ACTIVE).exclude(student_number="")
    }
    subeler: dict[tuple[int, str], ClassSection] = {
        (int(s.class_level), s.class_section): s
        for s in ClassSection.objects.filter(school_year=year)
    }

    # 1. geçiş — satırlar çözülür, HİÇBİR ŞEY YAZILMAZ. Raporun KAPSADIĞI şubeler
    # bütün satırlardan (eşleşmeyen dersler dahil) toplanır: e-Okul raporu bir
    # sınıf düzeyi ya da tek şube için alınmış olabilir; yenileme yalnız bu
    # şubelerde yapılır, kapsam dışı şubenin listesi SİLİNMEZ.
    kapsam: set[int] = set()
    dersler: dict[int, Course] = {}
    ders_ogrencileri: dict[int, dict[int, tuple[ClassSection, int]]] = {}

    for grup in parsed.groups:
        for satir in grup.lines:
            rapordaki = subeler.get((satir.class_level, satir.class_section))
            if rapordaki is not None:
                kapsam.add(int(rapordaki.pk))
        ders, gerekce = resolve_report_course(grup.title)
        ozet = CourseSummary(title=grup.title, status="unmatched", report_rows=len(grup.lines))
        rapor.courses.append(ozet)
        if ders is None:
            ozet.note = gerekce
            ilk = grup.lines[0] if grup.lines else None
            rapor.add_skip(
                ilk.page if ilk else 0,
                ilk.line if ilk else 0,
                f"'{grup.title}' dersi aktarılmadı: {gerekce}",
                "",
            )
            continue
        if ders.pk in ders_ogrencileri:
            # İki başlık aynı derse çözüldü (ör. önekli/öneksiz iki grup) — ikinci
            # grup birincinin listesini EZMESİN diye birleştirilir.
            onceki = next(o for o in rapor.courses if o.course_id == ders.pk and o is not ozet)
            ozet.note = f"'{onceki.title}' grubuyla aynı derse eşleşti; listeler birleştirildi."
        ozet.status = "matched"
        ozet.course_id = ders.pk
        ozet.course_name = ders.name
        if not ders.is_active:
            ozet.note = (ozet.note + " " if ozet.note else "") + (
                "Ders havuzda pasif; liste yine de aktarıldı."
            )
        dersler[int(ders.pk)] = ders

        yeni: dict[int, tuple[ClassSection, int]] = {}  # öğrenci pk → (şube, seviye)
        for satir in grup.lines:
            ogrenci = ogrenciler.get(satir.student_number)
            if ogrenci is None:
                rapor.add_skip(
                    satir.page,
                    satir.line,
                    "Bu okul numarasıyla aktif öğrenci kaydı yok — önce öğrenci listesini "
                    "e-Okul'dan güncelleyin.",
                    satir.student_number,
                )
                continue
            if ogrenci.class_level is None or not ogrenci.class_section:
                rapor.add_skip(
                    satir.page,
                    satir.line,
                    "Öğrencinin kaydında sınıf/şube yok.",
                    satir.student_number,
                )
                continue
            kayit_duzey = int(ogrenci.class_level)
            if (kayit_duzey, ogrenci.class_section) != (satir.class_level, satir.class_section):
                rapor.add_warning(
                    satir.page,
                    satir.line,
                    f"Raporda {_sinif_etiketi(satir.class_level, satir.class_section)}, "
                    f"kayıtta {ogrenci.class_label} — kayıttaki şube kullanıldı.",
                    satir.student_number,
                )
            if kayit_duzey not in (ders.levels or []):
                rapor.add_skip(
                    satir.page,
                    satir.line,
                    f"'{ders.name}' dersi {level_label(kayit_duzey)} düzeyinde okutulmuyor "
                    "(Ders Havuzu tanımı).",
                    satir.student_number,
                )
                continue
            sube = subeler.get((kayit_duzey, ogrenci.class_section))
            if sube is None:
                sube = ClassSection.objects.create(
                    school_year=year, class_level=kayit_duzey, class_section=ogrenci.class_section
                )
                subeler[(kayit_duzey, ogrenci.class_section)] = sube
            kapsam.add(int(sube.pk))
            yeni[int(ogrenci.pk)] = (sube, kayit_duzey)

        ozet.students = len(yeni)
        ozet.sections = sorted({s.class_label for s, _ in yeni.values()}, key=normalize.tr_sort_key)
        ders_ogrencileri.setdefault(int(ders.pk), {}).update(yeni)

    # 2. geçiş — yazım. Kapsanan şubelerde dersin listesi ve şube kapsamı rapora
    # çekilir (raporda öğrencisi olmayan kapsanan şube dersten ÇIKAR); kapsam dışı
    # şubelere dokunulmaz.
    for ders_pk, yeni in ders_ogrencileri.items():
        ders = dersler[ders_pk]
        # Öğrencinin kapsam DIŞI şubede kalmış satırı da silinir (şube değiştirmiş
        # öğrenci) — teklik anahtarı (ders, yıl, öğrenci)'dir.
        CourseEnrollment.all_objects.get_queryset().filter(course=ders, school_year=year).filter(
            Q(section_id__in=kapsam) | Q(student_id__in=list(yeni))
        ).hard_delete()
        CourseEnrollment.objects.bulk_create(
            [
                CourseEnrollment(course=ders, school_year=year, section=sube, student_id=pk)
                for pk, (sube, _duzey) in yeni.items()
            ]
        )
        rapor.processed += len(yeni)

        duzey_subeleri: dict[int, set[int]] = {}
        for sube, duzey in yeni.values():
            duzey_subeleri.setdefault(duzey, set()).add(int(sube.pk))
        kayitlar = {
            int(k.level): k
            for k in CourseSectionOffering.objects.filter(course=ders, school_year=year)
        }
        for duzey in sorted(set(kayitlar) | set(duzey_subeleri)):
            kayit = kayitlar.get(duzey)
            eski = {int(x) for x in (kayit.section_ids or [])} if kayit is not None else set()
            hedef = sorted((eski - kapsam) | duzey_subeleri.get(duzey, set()))
            if kayit is None:
                CourseSectionOffering.objects.create(
                    course=ders, school_year=year, level=duzey, section_ids=hedef
                )
            elif not hedef:
                kayit.delete()
            elif hedef != sorted(eski):
                kayit.section_ids = hedef
                kayit.save(update_fields=["section_ids", "updated_at"])

    kapsanan = sorted(
        (s for s in subeler.values() if int(s.pk) in kapsam),
        key=lambda s: (int(s.class_level), normalize.tr_sort_key(s.class_section)),
    )
    rapor.covered_section_count = len(kapsanan)
    rapor.covered_levels = [level_label(d) for d in sorted({int(s.class_level) for s in kapsanan})]
    listeli = set(
        CourseEnrollment.objects.filter(school_year=year).values_list("course_id", flat=True)
    )
    rapor.untouched_courses = sorted(
        Course.objects.filter(pk__in=listeli - set(ders_ogrencileri)).values_list(
            "name", flat=True
        ),
        key=normalize.tr_sort_key,
    )
    okul_imports.close_import_run(run, rapor.to_dict())
    return rapor


def _giris(file_bytes: bytes, file_name: str, *, preview: bool) -> ElectiveImportReport:
    """Ortak giriş: ayrıştırma hatasında kalıcı FAILED izi bırakır ve hatayı yükseltir."""
    from apps.okul.models import ImportSourceType
    from apps.okul.services import imports as okul_imports

    source_hash = okul_imports.file_hash(file_bytes)
    try:
        parsed = parse_report_pdf(file_bytes)
        if not preview:
            return _ingest(parsed, source_hash=source_hash, file_name=file_name)
        with transaction.atomic():
            rapor = _ingest(parsed, source_hash=source_hash, file_name=file_name)
            transaction.set_rollback(True)
        rapor.dry_run = True
        okul_imports.record_import_preview(
            ImportSourceType.ELECTIVES, source_hash, file_name, rapor.to_dict()
        )
        return rapor
    except ParserError as exc:
        okul_imports.record_import_failure(ImportSourceType.ELECTIVES, source_hash, file_name, exc)
        raise


def preview_elective_report(*, file_bytes: bytes, file_name: str = "") -> ElectiveImportReport:
    """Yazmadan simüle eder (gerçek yazım + geri alma) — PREVIEWED izi kalır."""
    return _giris(file_bytes, file_name, preview=True)


def commit_elective_report(*, file_bytes: bytes, file_name: str = "") -> ElectiveImportReport:
    """Rapordaki derslerin öğrenci listelerini ve şube kapsamlarını yazar."""
    return _giris(file_bytes, file_name, preview=False)
