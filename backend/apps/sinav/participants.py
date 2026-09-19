"""Katılımcı veri yapıları — F2 kesiti (motor girdi sözleşmesi).

OYS `participants.py`'nin SAF çekirdeği: `Participant`/`CourseResolution`/
`SessionResolution` dataclass'ları + çakışma grubu anahtarı. Motor (engine)
ve doğrulayıcı yalnız bunları görür.

Çözümleyici (`resolve_session`) OYS'den UYARLA: seviye/şube katılımcı çözümü,
mükerrer tespiti ve örtüşen oturum uyarıları; GROUPS tipi alınmadı (TB7).
Yerine seçmeli ders öğrenci listesi (19.09.2026, `dersler.CourseEnrollment`):
SECTIONS satırında listeli şubeden yalnız listedekiler, listesiz şubeden
şubenin tamamı gelir; LEVEL satırı listeyi uygulamaz ama varlığını uyarır.
Dağıtılmış oturumda yerleşim güncel çözümle `placement_drift` ile karşılaştırılır.
Öğrenci verisi okul köprüsünden okunur; burada hiçbir şey YAZILMAZ ve kişisel
veri SAKLANMAZ — liste anlık türetilir.

Çakışma grubu üretimi (motor sözleşmesi, CLAUDE.md §3): her öğrenciye TEK grup
atanır — `"<course_id>:<level>"`; ortak kitapçıkta tüm seviyeler tek gruptur
(`"<course_id>:*"`). Dağıtım motoru yalnız bu grupları görür; şube bilgisi
kısıt değildir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.dersler.selectors import EnrollmentIndex
    from apps.okul.models import Student
    from apps.sinav.models import ExamSession, ExamSessionCourse

#: shared_booklet grubunda seviye yerine kullanılan joker (tek kitapçık).
SHARED_LEVEL_KEY = "*"


@dataclass(frozen=True)
class Participant:
    """Çözümlenmiş tek katılımcı (anlık görünüm; DB'ye yazılmaz)."""

    student_id: int
    full_name: str
    student_number: str
    class_level: int
    class_section: str
    course_id: int
    course_name: str
    conflict_group: str  # "<course_id>:<level>" veya "<course_id>:*"


@dataclass
class CourseResolution:
    """Tek oturum dersinin çözümü."""

    session_course_id: int
    course_id: int
    course_name: str
    participants: list[Participant] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    #: Öğrenci listesiyle (şubenin bir kısmı) çözülen şubelerin etiketleri ('9/A').
    listed_sections: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.participants)


@dataclass
class SessionResolution:
    """Oturumun tam çözümü — katılımcılar + çakışmalar + uyarılar."""

    courses: list[CourseResolution] = field(default_factory=list)
    # Öğrenci iki derse düştü: student_id → o öğrencinin düştüğü ders adları.
    duplicate_students: dict[int, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def participants(self) -> list[Participant]:
        """Tüm derslerin katılımcıları (çakışanlar dahil — raporlama için)."""
        return [p for course in self.courses for p in course.participants]

    @property
    def total_count(self) -> int:
        return len(self.participants)

    @property
    def has_blocking_conflicts(self) -> bool:
        """Sert çakışma var mı (öğrenci iki derste) — dağıtım engellenir."""
        return bool(self.duplicate_students)


def conflict_group_key(course_id: int, level: int, *, shared_booklet: bool = False) -> str:
    """Çakışma grubu anahtarı — soru dosyası, kitapçık ve R8 hep bununla eşleşir."""
    if shared_booklet:
        return f"{course_id}:{SHARED_LEVEL_KEY}"
    return f"{course_id}:{level}"


# ---------------------------------------------------------------------------
# Çözümleyici (F3) — OYS resolve_session'dan UYARLA: core köprüleri okul'a,
# GROUPS tipi alınmadı (TB7), Section → ClassSection.
# ---------------------------------------------------------------------------


def _conflict_group(sc: ExamSessionCourse, level: int) -> str:
    if sc.shared_booklet:
        return f"{sc.course_id}:{SHARED_LEVEL_KEY}"
    return f"{sc.course_id}:{level}"


def _roster(class_level: int, class_section: str | None = None) -> list[Student]:
    """Aktif öğrenci listesi — okul köprüsü (şifreli ad çözülmüş döner)."""
    from apps.okul import selectors as okul_selectors

    rows = okul_selectors.student_list(
        class_level=class_level,
        class_section=class_section or "",
        only_active=True,
    )
    return list(rows)


def _append_students(
    resolution: CourseResolution,
    sc: ExamSessionCourse,
    students: list[Student],
    *,
    class_level: int,
) -> None:
    for student in students:
        resolution.participants.append(
            Participant(
                student_id=student.pk,
                full_name=student.full_name,
                student_number=student.student_number,
                class_level=class_level,
                class_section=student.class_section,
                course_id=sc.course_id,
                course_name=resolution.course_name,
                conflict_group=_conflict_group(sc, class_level),
            )
        )


def _resolve_level(
    sc: ExamSessionCourse, resolution: CourseResolution, index: EnrollmentIndex
) -> None:
    # OYS Tur 241: satır TEK seviyeli — `level` alanı servis katmanında zorunlu.
    if sc.level is None:
        resolution.warnings.append(
            f"'{sc.course.name}' dersinin sınıf düzeyi eksik — dersi çıkarıp yeniden ekleyin."
        )
        return
    level = int(sc.level)
    students = _roster(level)
    if not students:
        resolution.warnings.append(f"{level}. seviyede kayıtlı aktif öğrenci yok.")
    if _has_list_at_level(index, sc.course_id, level):
        # "Sınıf düzeyinin tamamı" açık bir idari seçimdir; liste SESSİZCE
        # uygulanmaz (katılımcı tipinin anlamı değişmesin) ama unutulmasın diye
        # söylenir — doğru yol şube kapsamıdır.
        resolution.warnings.append(
            f"'{sc.course.name}' dersinin bu sınıf düzeyinde öğrenci listesi var, ama katılımcı "
            "'Sınıf düzeyinin tamamı' seçildiği için liste kullanılmadı. Dersi yalnız alan "
            "öğrenciler girecekse 'Seçili şubeler'i seçin."
        )
    _append_students(resolution, sc, students, class_level=level)


def _has_list_at_level(index: EnrollmentIndex, course_id: int, level: int) -> bool:
    """Dersin bu sınıf düzeyindeki şubelerinden birinde öğrenci listesi var mı?"""
    from apps.okul.models import ClassSection

    listeli = [sid for (cid, sid) in index.lists if cid == course_id]
    if not listeli:
        return False
    return ClassSection.objects.filter(pk__in=listeli, class_level=level).exists()


def _resolve_sections(
    sc: ExamSessionCourse, resolution: CourseResolution, index: EnrollmentIndex
) -> None:
    """Şube kapsamı — şubede dersin öğrenci listesi varsa YALNIZ listedekiler.

    Kural şube bazındadır (`dersler.CourseEnrollment`): listesiz şubeyi dersi
    tamamen alır (bugünkü davranış). Listedeki öğrenci artık o şubede değilse
    (şube değiştirmiş, ayrılmış) atlanır ve SAYIYLA uyarılır — ad yazılmaz.
    """
    from apps.okul import selectors as okul_selectors

    for section_id in sc.section_ids:
        section = okul_selectors.get_class_section(int(section_id))
        if section is None:
            resolution.warnings.append(
                "Katılımcı tanımındaki bir şube artık yok (silinmiş); o şube atlandı."
            )
            continue
        students = _roster(section.class_level, section.class_section)
        if not students:
            resolution.warnings.append(f"{section.class_label} şubesinde kayıtlı öğrenci yok.")
        uyeler = index.members(sc.course_id, int(section.pk))
        if uyeler is not None:
            resolution.listed_sections.append(section.class_label)
            mevcut = {int(s.pk) for s in students}
            students = [s for s in students if int(s.pk) in uyeler]
            gitmis = len(uyeler - mevcut)
            if gitmis:
                resolution.warnings.append(
                    f"{section.class_label} şubesinde '{sc.course.name}' listesindeki {gitmis} "
                    "öğrenci artık bu şubede değil (şube değiştirmiş ya da ayrılmış); atlandı."
                )
            if not students:
                resolution.warnings.append(
                    f"{section.class_label} şubesinde '{sc.course.name}' listesinden bu şubede "
                    "kalan öğrenci yok."
                )
        _append_students(resolution, sc, students, class_level=section.class_level)


def _dedupe_within_course(resolution: CourseResolution) -> None:
    """Aynı ders içinde mükerrer öğrenci (iki şubeyle gelen) sessizce teklenir."""
    seen: set[int] = set()
    unique: list[Participant] = []
    for p in resolution.participants:
        if p.student_id in seen:
            continue
        seen.add(p.student_id)
        unique.append(p)
    resolution.participants = unique


def resolve_session(session: ExamSession) -> SessionResolution:
    """Oturumun tüm derslerini çözer; çakışma ve uyarıları toplar.

    Sert çakışma (öğrenci iki derste) `duplicate_students`'a yazılır —
    dağıtım `has_blocking_conflicts` doluyken başlatılamaz.
    """
    from apps.dersler import selectors as ders_selectors
    from apps.sinav.models import ParticipantType

    resolvers = {
        ParticipantType.LEVEL: _resolve_level,
        ParticipantType.SECTIONS: _resolve_sections,
    }
    result = SessionResolution()
    student_courses: dict[int, list[str]] = {}
    student_numbers: dict[int, str] = {}
    satirlar = list(session.courses.select_related("course").all())
    # Öğrenci listeleri oturumun DÖNEMİNİN ders yılından okunur (tek sorgu).
    index = ders_selectors.enrollment_index(
        session.semester.school_year_id, course_ids=[sc.course_id for sc in satirlar]
    )

    for sc in satirlar:
        resolution = CourseResolution(
            session_course_id=sc.pk, course_id=sc.course_id, course_name=sc.course.name
        )
        resolvers[ParticipantType(sc.participant_type)](sc, resolution, index)
        _dedupe_within_course(resolution)
        result.courses.append(resolution)
        for p in resolution.participants:
            student_courses.setdefault(p.student_id, []).append(p.course_name)
            student_numbers[p.student_id] = p.student_number

    result.duplicate_students = {
        sid: courses for sid, courses in student_courses.items() if len(courses) > 1
    }
    # Uyarı metinleri AD İÇERMEZ (KVKK — metin 400 gövdesine/loga sızabilir);
    # okul no yeterli eylem bilgisidir, ad UI'da student_id'den çözülür.
    for sid, courses in result.duplicate_students.items():
        result.warnings.append(
            f"Okul No {student_numbers[sid]} aynı oturumda {len(courses)} derse düşüyor: "
            f"{', '.join(courses)}."
        )
    if not result.courses:
        result.warnings.append("Oturumda ders tanımlı değil.")
    return result


@dataclass(frozen=True)
class PlacementDrift:
    """Dağıtımdan sonra katılımcı kümesinin yerleşim kaydından sapması (yalnız SAYI)."""

    added: int  # yerleşimde olmayan yeni katılımcı
    removed: int  # yerleşimde olup artık katılımcı olmayan
    changed: int  # hâlâ katılımcı ama dersi/kitapçık grubu değişmiş

    @property
    def outdated(self) -> bool:
        return bool(self.added or self.removed or self.changed)

    def message(self) -> str:
        parcalar = []
        if self.added:
            parcalar.append(f"{self.added} öğrenci eklendi")
        if self.removed:
            parcalar.append(f"{self.removed} öğrenci çıktı")
        if self.changed:
            parcalar.append(f"{self.changed} öğrencinin dersi değişti")
        return (
            "Dağıtımdan sonra katılımcılar değişti (" + ", ".join(parcalar) + "). Yerleşim ve "
            "kitapçıklar eski listeye göre — oturumu yeniden dağıtın (onaylı oturumda önce "
            "“Yeniden aç”)."
        )


def placement_drift(session: ExamSession, resolution: SessionResolution) -> PlacementDrift | None:
    """Yerleşim SNAPSHOT'ı ile güncel katılımcı çözümünü karşılaştırır (dağıtılmış oturumda).

    Seçmeli ders listesi, öğrenci aktarımı ya da nakil dağıtımdan SONRA
    değişirse yerleşim ve kitapçık eski kümeye göre kalır; bu sessizce
    geçmesin. Yerleşim yoksa (taslak) ya da oturum arşivdeyse (anonimleşmiş
    kayıtlar, geçmişin kaydı) None döner. Karşılaştırma kimlikledir, ad yok.
    """
    from apps.sinav.models import ExamSessionStatus, SeatAssignment

    if session.status not in (ExamSessionStatus.DISTRIBUTED, ExamSessionStatus.APPROVED):
        return None
    yerlesim = {
        (int(sid), grup)
        for sid, grup in SeatAssignment.objects.filter(session=session)
        .exclude(student=None)
        .values_list("student_id", "conflict_group")
    }
    if not yerlesim:
        return None
    guncel = {(p.student_id, p.conflict_group) for p in resolution.participants}
    yer_ogr = {sid for sid, _ in yerlesim}
    gun_ogr = {sid for sid, _ in guncel}
    return PlacementDrift(
        added=len(gun_ogr - yer_ogr),
        removed=len(yer_ogr - gun_ogr),
        changed=len(
            {sid for sid, grup in guncel if sid in yer_ogr and (sid, grup) not in yerlesim}
        ),
    )


def overlapping_session_conflicts(session: ExamSession) -> list[str]:
    """Aynı tarihte ZAMAN ARALIĞI çakışan diğer oturumlarla ortak öğrenciler (K3).

    Uyarı listesi döner (Türkçe); boş liste = çakışma yok. Saat aralığı
    [start, start+duration) olarak karşılaştırılır.
    """
    from datetime import date, datetime, timedelta

    from apps.sinav.models import ExamSession

    def _interval(s: ExamSession) -> tuple[datetime, datetime]:
        start = datetime.combine(date.min, s.start_time)
        return start, start + timedelta(minutes=s.duration_minutes)

    own_start, own_end = _interval(session)
    own_students = {p.student_id: p.student_number for p in resolve_session(session).participants}
    if not own_students:
        return []

    conflicts: list[str] = []
    others = ExamSession.objects.filter(exam_date=session.exam_date).exclude(pk=session.pk)
    for other in others:
        other_start, other_end = _interval(other)
        if own_start >= other_end or other_start >= own_end:
            continue  # zaman kesişmiyor
        other_ids = {p.student_id for p in resolve_session(other).participants}
        shared = sorted(set(own_students) & other_ids)
        if shared:
            # Ad değil okul no listelenir (KVKK — uyarı metni log/iletiye sızabilir).
            numbers = ", ".join(own_students[sid] for sid in shared[:5])
            suffix = " …" if len(shared) > 5 else ""
            conflicts.append(
                f"'{other.name}' oturumuyla aynı zaman diliminde {len(shared)} ortak "
                f"öğrenci var (No: {numbers}{suffix})."
            )
    return conflicts
