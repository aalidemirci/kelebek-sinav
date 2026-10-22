"""Bakanlığın ilan ettiği ortak yazılı sınav haftaları (19.09.2026).

Ölçme ve Değerlendirme Yönetmeliği md. 5/1-ç sınav zamanını AY düzeyinde verir;
program bunu "ayın son pazartesisinden itibaren iki hafta" diye hesaplar
(`services_calendar.statutory_window`). Bakanlık ise her ders yılı için tarihleri
ayrıca ilan eder ve ilan kural hesabından farklı olabilir: 2026-2027'de 1. dönem
1. yazılı kural hesabıyla 26 Ekim-6 Kasım, ilanla 2-13 Kasım'dır. İlan edilmiş
yılda varsayılan pencere İLANDIR; ilan yoksa kural hesabı çalışır.

VARSAYILANDIR, KISIT DEĞİL (kullanıcı kararı 19.09.2026): takvim tarihleri
idarecinin kararıdır ve her zaman düzenlenebilir. Buradaki tarihler yalnız yeni
takvimin ön değeri ve takvim sayfasındaki öneridir; hiçbir yerleştirme bunlara
göre reddedilmez. Yeni yılın ilanı gelince tabloya bir yıl eklenir ve yazının
metni `docs/mevzuat/` altına girer (atıf depodaki metinden doğrulanır).

Aynı modülde iki Bakanlık takvimi daha durur: ülke geneli ortak yazılı sınavlar
(`NATIONAL_EXAMS` — gün verir) ve OYSS okul geneli ortak yazılı sınav uygulama
takvimi (`OYSS_SCHEDULES`, 22.10.2026 — gün + ders saati verir).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class OfficialWindow:
    """Bir dönem + sınav turu için ilan edilmiş sınav haftaları."""

    start: date
    end: date
    #: Kullanıcıya gösterilen dayanak (yazının tarihi ve sayısı).
    source: str


_YAZI_2026 = (
    "MEB Ölçme, Değerlendirme ve Sınav Hizmetleri Genel Müdürlüğünün 10.09.2026 "
    "tarihli ve E-26614336-480.99-168561496 sayılı yazısı"
)

#: Ders yılının başladığı takvim yılı → (dönem, sınav turu) → ilan edilen pencere.
#: Metin: docs/mevzuat/meb-2026-2027-ortak-yazili-sinavlar.md.
OFFICIAL_WINDOWS: dict[int, dict[tuple[int, int], OfficialWindow]] = {
    2026: {
        (1, 1): OfficialWindow(date(2026, 11, 2), date(2026, 11, 13), _YAZI_2026),
        (1, 2): OfficialWindow(date(2027, 1, 4), date(2027, 1, 15), _YAZI_2026),
        (2, 1): OfficialWindow(date(2027, 3, 29), date(2027, 4, 9), _YAZI_2026),
        (2, 2): OfficialWindow(date(2027, 6, 7), date(2027, 6, 18), _YAZI_2026),
    },
}


def official_window(school_year_start: int, donem: int, round_: int) -> OfficialWindow | None:
    """İlan edilmiş pencere; o yıl, dönem ya da tur için ilan yoksa None."""
    return OFFICIAL_WINDOWS.get(int(school_year_start), {}).get((int(donem), int(round_)))


# ---------------------------------------------------------------------------
# Ülke geneli ortak yazılı sınavlar (Bakanlığın hazırladığı; 19.09.2026)
# ---------------------------------------------------------------------------
# Kaynak: aynı yazının eki "2026-2027 Eğitim Öğretim Yılı Ülke Geneli Ortak Yazılı
# Sınav Takvimi" (tek sayfa; metni docs/mevzuat/meb-2026-2027-ortak-yazili-sinavlar.md).
# Takvim GÜN verir, ders saati VERMEZ — saat Bakanlığın uygulama esaslarıyla ayrıca
# duyurulur. Program sınavı resmî gününe okulun ilk sınav saatiyle koyar; saati
# idareci düzeltir (kullanıcı kararı 19.09.2026, `services_calendar.apply_national_exams`).
# Ortaokul satırları (6-7. sınıf) veri bütünlüğü için durur; program yalnız okulun
# sınıf düzeylerindekini kullanır.


@dataclass(frozen=True)
class NationalExam:
    """Bir ülke geneli ortak yazılı sınav: sınıf düzeyi + ders + gün."""

    level: int
    #: Bakanlık takvimindeki ders adı — ders havuzundaki adla eşleştirilir.
    course_name: str
    on_date: date
    source: str


_EK_2026 = f"{_YAZI_2026} eki (Ülke Geneli Ortak Yazılı Sınav Takvimi)"

#: Ders yılının başladığı takvim yılı → (dönem, sınav turu) → o turun sınavları.
NATIONAL_EXAMS: dict[int, dict[tuple[int, int], tuple[NationalExam, ...]]] = {
    2026: {
        (1, 1): (
            NationalExam(6, "Matematik", date(2026, 11, 11), _EK_2026),
            NationalExam(10, "Türk Dili ve Edebiyatı", date(2026, 11, 12), _EK_2026),
        ),
        (1, 2): (
            NationalExam(7, "Türkçe", date(2027, 1, 5), _EK_2026),
            NationalExam(9, "Matematik", date(2027, 1, 6), _EK_2026),
        ),
        (2, 1): (
            NationalExam(7, "Matematik", date(2027, 4, 6), _EK_2026),
            NationalExam(9, "Türk Dili ve Edebiyatı", date(2027, 4, 7), _EK_2026),
        ),
        (2, 2): (
            NationalExam(6, "Türkçe", date(2027, 6, 8), _EK_2026),
            NationalExam(10, "Matematik", date(2027, 6, 9), _EK_2026),
        ),
    },
}


def national_exams(school_year_start: int, donem: int, round_: int) -> tuple[NationalExam, ...]:
    """O yıl, dönem ve turun ülke geneli sınavları; ilan yoksa boş."""
    return NATIONAL_EXAMS.get(int(school_year_start), {}).get((int(donem), int(round_)), ())


# ---------------------------------------------------------------------------
# OYSS — okul geneli ortak yazılı sınav uygulama takvimi (22.10.2026)
# ---------------------------------------------------------------------------
# Kaynak: Ortak Yazılı Sınav Sistemi (OYSS) Uygulama Kılavuzu ile "Okul Geneli Ortak
# Yazılı Sınav Uygulama Takvimi" (ÖDSHGM, PDF'leri 19.10.2026; metni
# docs/mevzuat/meb-2026-2027-oyss.md). 2026-2027'den itibaren Türkiye Yüzyılı Maarif
# Modeli'nin uygulandığı sınıf düzeylerinde (lisede 9-11, ortaokulda 5-7) on derste
# okul geneli ortak yazılı sınav OYSS üzerinden hazırlanır ve GÜNÜNÜ Bakanlık
# belirler. Ülke geneli takvimden iki farkı var: sınav OKUL sınavıdır (makam okul,
# soruları zümre OYSS'de hazırlar) ve takvim ders saatini de verir — günde tek
# sınav 2. ders saatinde, iki sınav 2. ve 4. ders saatlerinde, 40 dakika. Okul
# müdürlüğü ihtiyaç hâlinde başka ders saati planlayabilir: program sınavı resmî
# gün + saate SABİTLER, saati idareci yerleştirme çizelgesinde değiştirir
# (`services_calendar.apply_oyss_schedule`). Ortaokul satırları veri bütünlüğü için
# durur; program yalnız okulun sınıf düzeylerindekini kullanır. Bakanlık sonraki
# turların takvimini yayımladıkça tabloya eklenir (önce metin docs/mevzuat/e).


@dataclass(frozen=True)
class OyssExam:
    """OYSS uygulama takviminin bir satırı: sınıf düzeyleri + ders + gün."""

    levels: tuple[int, ...]
    #: Bakanlık takvimindeki ders adı.
    course_name: str
    on_date: date
    #: Ders havuzunda Bakanlığın adı o sınıf düzeyinde yoksa SIRAYLA denenen adlar.
    #: Çizelge aynı dersi başka adla yazar: "İngilizce" çizelgede "Birinci Yabancı
    #: Dil"dir (AİHL ve MTAL'de "Yabancı Dil"); 11. sınıfta Matematik, Fizik, Kimya,
    #: Biyoloji ve Coğrafya çoğu okul türünde yalnız "Seçmeli X" olarak okutulur
    #: (TTK 2025 çizelgeleri, data/ders-cizelgeleri). Asıl ad hep önce denenir.
    pool_names: tuple[str, ...] = ()
    #: Ders havuzdaki BAŞKA adla eşleşince bantta gösterilen not (boşsa not yok).
    pool_note: str = ""


@dataclass(frozen=True)
class OyssSchedule:
    """Bir dönem + sınav turunun OYSS uygulama takvimi ve ders saati kuralı."""

    #: Tablo SIRASIYLA: aynı gün iki sınavı olan sınıf düzeyinde ilk satır 2., ikinci
    #: satır 4. ders saatine düşer (belge sırayı söylemez — tablo sırası varsayılandır).
    exams: tuple[OyssExam, ...]
    #: OYSS uygulanmayan (sınıf düzeyi, ders adı) çiftleri — o sınavı okul kendisi planlar.
    excluded: frozenset[tuple[int, str]]
    #: Sınıf düzeyinin o günkü OYSS sınavı sayısı → ders saatleri (tablo sırasıyla).
    periods_by_count: tuple[tuple[int, tuple[int, ...]], ...]
    #: Güne özgü ders saati (yalnız TEK sınavlı günde) — 10 Kasım'da 4. ders saati.
    day_periods: tuple[tuple[date, int], ...]
    duration_minutes: int
    #: Mazeret sınavlarının aralığı (okul müdürlüğünün planlamasıyla, OYSS üzerinden).
    makeup_start: date
    makeup_end: date
    #: Kullanıcıya gösterilen dayanak.
    source: str

    def periods_for(self, on_date: date, count: int) -> tuple[int, ...]:
        """Sınıf düzeyinin o günkü `count` OYSS sınavının ders saatleri (tablo sırasıyla)."""
        if count == 1:
            for gun, saat in self.day_periods:
                if gun == on_date:
                    return (saat,)
        return dict(self.periods_by_count).get(count, ())


_OYSS_TAKVIMI_2026 = (
    "Okul Geneli Ortak Yazılı Sınav Uygulama Takvimi (Ortak Yazılı Sınav Sistemi, "
    "2026-2027 1. dönem 1. yazılı sınavlar; ÖDSHGM, Ekim 2026)"
)

_LISE = (9, 10, 11)
_ORTAOKUL = (5, 6, 7)
#: 11. sınıfta zorunlusu olmayan derslerin seçmeli adı (Anadolu Lisesi vb.).
_SECMELI_DERSLER = frozenset({"Biyoloji", "Kimya", "Matematik", "Fizik", "Coğrafya"})
_SECMELI_NOTU = (
    "11. sınıfta zorunlusu olmayan ders seçmeli adıyla bağlandı; sınava yalnız dersi "
    "alan şubeler girer (şube kapsamı Ders Havuzu'ndan gelir)."
)
_YABANCI_DIL = ("Birinci Yabancı Dil", "Yabancı Dil")
#: Çizelge dersin dilini söylemez — İngilizce dışı yabancı dil okutan okul uyarılır.
_YABANCI_DIL_NOTU = (
    "İngilizce sınavı ders havuzundaki yabancı dil dersine bağlandı; okulunuzda bu ders "
    "İngilizce değilse OYSS kapsamında değildir — girdiyi havuza geri alıp kendi "
    "tarihinize yerleştirin."
)


def _satir(levels: tuple[int, ...], course_name: str, on_date: date) -> OyssExam:
    """Takvim satırı — havuzdaki karşılık adları ve notu dersten türer."""
    if course_name == "İngilizce":
        return OyssExam(levels, course_name, on_date, _YABANCI_DIL, _YABANCI_DIL_NOTU)
    if levels == _LISE and course_name in _SECMELI_DERSLER:
        return OyssExam(levels, course_name, on_date, (f"Seçmeli {course_name}",), _SECMELI_NOTU)
    return OyssExam(levels, course_name, on_date)


#: Ders yılının başladığı takvim yılı → (dönem, sınav turu) → OYSS uygulama takvimi.
#: 10 Kasım: takvim "4. ders saatinde uygulanabilecektir" der — program 4'ü kullanır
#: (10 Kasım anma programı sabah saatlerini kaplar); okul 2. saati seçerse taşır.
OYSS_SCHEDULES: dict[int, dict[tuple[int, int], OyssSchedule]] = {
    2026: {
        (1, 1): OyssSchedule(
            exams=(
                # Tablo 2 — Liseler İçin Sınav Uygulama Takvimi (9, 10 ve 11. Sınıf).
                _satir(_LISE, "Biyoloji", date(2026, 11, 3)),
                _satir(_LISE, "Kimya", date(2026, 11, 4)),
                _satir(_LISE, "Tarih", date(2026, 11, 4)),
                _satir(_LISE, "Matematik", date(2026, 11, 5)),
                _satir(_LISE, "Fizik", date(2026, 11, 6)),
                _satir(_LISE, "Felsefe", date(2026, 11, 6)),
                _satir(_LISE, "Coğrafya", date(2026, 11, 10)),
                _satir(_LISE, "Türk Dili ve Edebiyatı", date(2026, 11, 11)),
                _satir(_LISE, "Din Kültürü ve Ahlak Bilgisi", date(2026, 11, 11)),
                _satir(_LISE, "İngilizce", date(2026, 11, 13)),
                # Tablo 1 — Ortaokullar İçin Sınav Uygulama Takvimi (5, 6 ve 7. Sınıf).
                _satir(_ORTAOKUL, "Fen Bilimleri", date(2026, 11, 3)),
                _satir(_ORTAOKUL, "Matematik", date(2026, 11, 5)),
                _satir(_ORTAOKUL, "Sosyal Bilgiler", date(2026, 11, 6)),
                _satir(_ORTAOKUL, "Türkçe", date(2026, 11, 10)),
                _satir(_ORTAOKUL, "İngilizce", date(2026, 11, 12)),
                _satir(_ORTAOKUL, "Din Kültürü ve Ahlak Bilgisi", date(2026, 11, 13)),
            ),
            # "7 ve 11. sınıf İngilizce derslerinde Ortak Yazılı Sınav Sistemi
            # uygulaması yapılmayacaktır." Tabloların notlarındaki ülke geneli
            # sınavlar (6. Matematik, 10. TDE) NATIONAL_EXAMS'tan düşer.
            excluded=frozenset({(7, "İngilizce"), (11, "İngilizce")}),
            periods_by_count=((1, (2,)), (2, (2, 4))),
            day_periods=((date(2026, 11, 10), 4),),
            duration_minutes=40,
            makeup_start=date(2026, 11, 23),
            makeup_end=date(2026, 11, 27),
            source=_OYSS_TAKVIMI_2026,
        ),
    },
}


def oyss_schedule(school_year_start: int, donem: int, round_: int) -> OyssSchedule | None:
    """O yıl, dönem ve turun OYSS uygulama takvimi; yayımlanmadıysa None."""
    return OYSS_SCHEDULES.get(int(school_year_start), {}).get((int(donem), int(round_)))
