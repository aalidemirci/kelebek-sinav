"""Ders havuzu modelleri — MEB haftalık ders çizelgesi kataloğu + takma adlar.

OYS `ders_yapisi.Course`/`CourseAlias`'tan uyarlandı (tasarım §4/§7):
- `db_table='sinav_islemleri_course'` bagajı ATILDI (B14) — tablo adı doğal.
- `short_code`/`default_weekly_hours` alınmadı: sınav planlama haftalık saati
  HİÇ kullanmıyor (keşif raporu), kısa kod aSc/program importuna aitti.
- `levels` JSON listedir; SQLite'ta `levels__contains` yok → seviye süzgeci
  Python tarafında (K11, selectors.courses_for_level).
Kişisel veri içermez (KVKK bayrağı gerekmez).
"""

from __future__ import annotations

from django.db import models

from shared.models import BaseModel

# Geçerli sınıf düzeyleri — TÜM okul türlerinin birleşimi (katalog verisi okul
# türünden bağımsız doğrulanır; UI süzgeci okulun kendi kümesine ayrıca daraltır:
# `apps.okul.models.SchoolConfig.grade_levels`, U4). 0 = Hazırlık.
PREP_COURSE_LEVEL = 0
VALID_COURSE_LEVELS: tuple[int, ...] = (PREP_COURSE_LEVEL, 9, 10, 11, 12)


class CourseType(models.TextChoices):
    COMMON = "COMMON", "Ortak"
    ELECTIVE = "ELECTIVE", "Seçmeli"


class CourseExamMode(models.TextChoices):
    """Dersin sınav biçimi — havuz doldurmanın SÜZGECİ.

    Ortak sınav takvimi yalnız YAZILI dersler üzerine kurulur: uygulama sınavı
    yapılan dersler (Beden Eğitimi, Görsel Sanatlar/Müzik, Spor/Sanat Eğitimi)
    kelebek düzeninde salon/sıra planı gerektirmez, sınavı hiç olmayan ders
    (Rehberlik ve Yönlendirme) ise nota dönmez. İkisi de havuza OTOMATİK
    girmez; idareci kenar durumda (zorunlu hâl) elle ekleyebilir.
    """

    WRITTEN = "WRITTEN", "Yazılı"
    PRACTICE = "PRACTICE", "Uygulama"
    NONE = "NONE", "Sınav yok"


class CourseSource(models.TextChoices):
    MEB_CATALOG = "MEB_CATALOG", "MEB çizelgesi"
    MANUAL = "MANUAL", "Elle giriş"


class Course(BaseModel):
    """Ders kataloğu — MEB haftalık ders çizelgesinden veya elle beslenir.

    Sınav planlamasında (F3) `ExamSessionCourse` bu katalogdan seçim yapar;
    çakışma grubu `(course, level)` çiftidir (motor sözleşmesi).
    """

    name = models.CharField(
        "ders adı",
        max_length=120,
        db_index=True,
        help_text="Örn. 'Türk Dili ve Edebiyatı', 'Seçmeli İngilizce'.",
    )
    levels = models.JSONField(
        "seviyeler",
        default=list,
        help_text="Dersin okutulduğu sınıf düzeyleri, artan sıralı liste (örn. [9, 10]).",
    )
    course_type = models.CharField(
        "tür",
        max_length=10,
        choices=CourseType.choices,
        default=CourseType.COMMON,
    )
    exam_mode = models.CharField(
        "sınav biçimi",
        max_length=10,
        choices=CourseExamMode.choices,
        default=CourseExamMode.WRITTEN,
        help_text=(
            "Takvim havuzunun otomatik doldurulması yalnız 'Yazılı' dersleri alır; "
            "'Uygulama' ve 'Sınav yok' dersleri gerekirse elle eklenir."
        ),
    )
    source = models.CharField(
        "kaynak",
        max_length=12,
        choices=CourseSource.choices,
        default=CourseSource.MANUAL,
        help_text="MEB çizelge import'u dokunduğu kaydı MEB_CATALOG olarak işaretler.",
    )
    is_active = models.BooleanField(
        "aktif",
        default=True,
        help_text="Pasif ders yeni planlamada seçilemez; kayıt silinmez.",
    )
    # Katalog senkronu (`services.sync_catalog`) okulun yürürlükteki çizelgesinde
    # ARTIK bulunmayan MEB dersini pasifleştirirken bu bayrağı kaldırır; ders
    # çizelgeye geri girerse yalnız bu bayraklı kayıt yeniden AÇILIR. İdarecinin
    # elle pasifleştirdiği ders (bayraksız) senkronla asla geri açılmaz —
    # `is_active` idari karardır (K5), bu alan onun ayrımını taşır.
    catalog_excluded = models.BooleanField(
        "çizelge dışı",
        default=False,
        help_text="Okulun yürürlükteki MEB çizelgesinde yok; senkron pasifleştirdi.",
    )

    class Meta:
        verbose_name = "ders"
        verbose_name_plural = "dersler"
        ordering = ["name"]
        constraints = [
            # Aynı ders adı iki kez canlı olamaz; soft-delete edilenler ayrı sayılır.
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_course_name_alive",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class CourseAlias(BaseModel):
    """Ders adı takma adı — xlsx/pano listesindeki varyantı kanonik derse bağlar.

    Çözüm zincirinde MEB-eşleşme SONRASINDA bakılır: 'Din Kül. ve Ah. Bil.'
    gibi varyantlar mükerrer Course üretmek yerine kanonik kayda iner. İki
    kaynak: SEED (`ders-adi-takma-adlari.md`) ve OPERATOR (mükerrer birleştirme
    öğrenmesi). OPERATOR kaydı SEED'i ezebilir; tersi olmaz.
    `alias_key` `text.course_match_key` normalize'ıyla yazılır (Türkçe-duyarsız;
    'seçmeli' önek ayrımı korunur). Kişisel veri içermez.
    """

    alias_key = models.CharField(
        "takma ad anahtarı",
        max_length=200,
        db_index=True,
        help_text="Normalize edilmiş takma ad (course_match_key çıktısı).",
    )
    display_name = models.CharField(
        "takma ad (görünen)",
        max_length=200,
        help_text="Listede görüldüğü haliyle takma ad (örn. 'Din Kül. ve Ah. Bil.').",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name="aliases",
        verbose_name="kanonik ders",
    )

    class Source(models.TextChoices):
        OPERATOR = "OPERATOR", "Operatör (birleştirme öğrenmesi)"
        SEED = "SEED", "Seed listesi"

    source = models.CharField(
        "kaynak",
        max_length=10,
        choices=Source.choices,
        default=Source.OPERATOR,
    )

    class Meta:
        verbose_name = "ders takma adı"
        verbose_name_plural = "ders takma adları"
        ordering = ["alias_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["alias_key"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_course_alias_key_alive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.display_name} → {self.course}"
