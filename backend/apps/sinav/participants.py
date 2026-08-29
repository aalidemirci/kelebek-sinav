"""Katılımcı veri yapıları — F2 kesiti (motor girdi sözleşmesi).

OYS `participants.py`'nin SAF çekirdeği: `Participant`/`CourseResolution`/
`SessionResolution` dataclass'ları + çakışma grubu anahtarı. Motor (engine)
ve doğrulayıcı yalnız bunları görür.

ÇÖZÜMLEYİCİ F3'TE GELİR: `resolve_session` (seviye/şube/grup katılımcı
çözümü, mükerrer tespiti, örtüşen oturum uyarıları) OYS'den oturum modelleriyle
birlikte taşınacak — bu dosya o taşımada OYS paritesine tamamlanır.

Çakışma grubu üretimi (motor sözleşmesi, CLAUDE.md §3): her öğrenciye TEK grup
atanır — `"<course_id>:<level>"`; ortak kitapçıkta tüm seviyeler tek gruptur
(`"<course_id>:*"`). Dağıtım motoru yalnız bu grupları görür; şube bilgisi
kısıt değildir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
