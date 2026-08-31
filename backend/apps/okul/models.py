"""`okul` modelleri — kurum künyesi, ders yılı/dönemler, kişi sicilleri, şube kataloğu, içe aktarma.

DD (disiplin-defteri-codex) `apps/okul/models.py` kalıbından KS'ye uyarlandı
(tasarım §4 + §11 UYARLA):

- `Student`: kelebek yalnız ad-soyad + okul no + sınıf/şube kullanır. TCKN,
  veli ve demografi alanları HİÇ YOKTUR (tasarım §5: en iyi KVKK önlemi veriyi
  hiç edinmemek). U3 kararı gereği ad-soyad `EncryptedCharField`'dır — DD'nin
  aksine burada ad ŞİFRELİDİR ve ad temelli arama Python katmanına taşınmıştır
  (teknik borç TB3; selectors zaten Python tarafında katlayarak arıyor).
- `Personnel`: DD kalıbı + `is_active` (gözetmen havuzu aktif personelden
  türetilir — U2) + şifreli ad-soyad.
- `ClassSection`: DD `ClassResponsibility`'nin sadeleşmiş karşılığı — şube
  kataloğu. Salon-şube eşlemesi (`ExamRoom.linked_section`, F2) ve R2k şube
  yoklaması bu kataloğa bağlanır; import sonrası görülen (seviye, şube)
  çiftleri tohumlanır.
- `ClassSectionGroup`: şube kümesi (SAY/EA/DİL gibi) — YALNIZ seçim kolaylığı;
  şube en çok bir kümededir ve küme kimliği oturum kaydına yazılmaz.
- `SubjectDepartment`: okul zümre başkanları kurulunun zümreleri; başkan
  `Personnel`'e FK'dır. Sınav takvimi imza bloğu buradan seçilir (B7 revizyonu —
  "her ders bir zümre" varsayımı kalktı).
- `SchoolConfig.school_type/has_prep_class`: U4 — geçerli sınıf seviyeleri okul
  türünden türetilir; v1'de tek tür (Anadolu Lisesi) ama sabit kod 9-12 YOKTUR.
- Koşullu UniqueConstraint'ler SQLite partial index ile çalışır (DD'de kanıtlı).
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone

from shared.crypto import EncryptedCharField
from shared.models import BaseModel


class SchoolType(models.TextChoices):
    """Okul türü — ders havuzu fixture'ı ve seviye kümesi bundan türetilir (U4).

    v1'de yalnız Anadolu Lisesi verisi gömülüdür; yeni tür eklemek = yeni
    çizelge veri dosyası + bu listeye bir satır (kod değişikliği gerekmez,
    `grade_levels_for` tek yerden türetir).
    """

    ANADOLU_LISESI = "ANADOLU_LISESI", "Anadolu Lisesi"


#: Okul türü → hazırlıksız seviye listesi. Hazırlık (0) `has_prep_class` ile eklenir.
SCHOOL_TYPE_LEVELS: dict[str, tuple[int, ...]] = {
    SchoolType.ANADOLU_LISESI: (9, 10, 11, 12),
}

#: Hazırlık sınıfının seviye kodu (OYS `ders_yapisi.PREP_COURSE_LEVEL` paritesi).
PREP_LEVEL = 0


def grade_levels_for(school_type: str, *, has_prep_class: bool) -> tuple[int, ...]:
    """Okul türü + hazırlık bayrağından geçerli sınıf seviyeleri (artan sırada)."""
    base = SCHOOL_TYPE_LEVELS.get(school_type, SCHOOL_TYPE_LEVELS[SchoolType.ANADOLU_LISESI])
    return (PREP_LEVEL, *base) if has_prep_class else base


class SchoolConfig(BaseModel):
    """Kurum bilgisi — TEK satır (singleton, pk=1).

    Kurulum sihirbazı doldurur; evrak antedi (okul adı/ilçe/müdür) buradan
    çözülür. `setup_completed` sihirbaz kapısıdır.

    `app_password_hash` (DD F5-D5 kalıbı, tasarım §5): adı tarihsel — içeriği
    parolanın özeti DEĞİLDİR; veri anahtarının (DEK) tek yönlü parmak izini
    tutar (`shared.crypto.key_fingerprint`). Parola/tuz/sarmal `guvenlik.json`
    dosyasındadır; DB ile güvenlik dosyasının eşleşmesi bu damgayla denetlenir
    ve alan şifreleme geçişi bu alanla AYNI işlemde damgalanır.
    """

    SINGLETON_PK = 1

    school_name = models.CharField("okul adı", max_length=255, blank=True, default="")
    province = models.CharField("il", max_length=64, blank=True, default="")
    district = models.CharField("ilçe", max_length=64, blank=True, default="")
    principal_name = models.CharField("müdür adı", max_length=128, blank=True, default="")
    school_type = models.CharField(
        "okul türü",
        max_length=32,
        choices=SchoolType.choices,
        default=SchoolType.ANADOLU_LISESI,
    )
    has_prep_class = models.BooleanField("hazırlık sınıfı var", default=False)
    setup_completed = models.BooleanField("kurulum tamamlandı", default=False)
    app_password_hash = models.CharField(
        "uygulama parolası özeti", max_length=255, blank=True, default=""
    )
    # B6 — program köprüsü SADELEŞTİR: OYS zil çizelgesinin yerini alan
    # düzenlenebilir varsayılan ders saati listesi. Öğe şekli OYS sözleşmesiyle
    # birebir: {"no": int, "name": str, "start": "SS:DD"}. Boş liste →
    # apps.sinav.services_calendar.DEFAULT_BELL_SCHEDULE kullanılır.
    bell_schedule = models.JSONField(
        "ders saati listesi",
        default=list,
        blank=True,
        help_text='[{"no": 1, "name": "1. Ders", "start": "08:30"}, ...] — boşsa varsayılan.',
    )

    class Meta:
        verbose_name = "kurum yapılandırması"
        verbose_name_plural = "kurum yapılandırması"

    def __str__(self) -> str:
        return self.school_name or "Kurulmamış okul"

    @classmethod
    def load(cls) -> SchoolConfig:
        """Singleton satırı döndürür; yoksa KAYDEDİLMEMİŞ varsayılan (okuma yazmaz)."""
        instance: SchoolConfig | None = cls.objects.filter(pk=cls.SINGLETON_PK).first()
        return instance if instance is not None else cls(pk=None)

    @property
    def grade_levels(self) -> tuple[int, ...]:
        """Bu okulda geçerli sınıf seviyeleri (0=Hazırlık dahil olabilir)."""
        return grade_levels_for(self.school_type, has_prep_class=self.has_prep_class)


class SchoolYear(BaseModel):
    """Ders yılı (örn. '2026-2027'). Tek-aktif kuralı hem serviste hem DB kısıtında."""

    name = models.CharField("ad", max_length=32)
    start_date = models.DateField("başlangıç")
    end_date = models.DateField("bitiş")
    is_active = models.BooleanField("aktif", default=False)

    class Meta:
        verbose_name = "ders yılı"
        verbose_name_plural = "ders yılları"
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_schoolyear_name_alive",
            ),
            # Savunma hattı: aktif yıl değişimi serviste "önce eskisini kapat"
            # sırasıyla yapılır; kısıt yarış/hata durumunda ikinci aktifi keser.
            models.UniqueConstraint(
                fields=["is_active"],
                condition=models.Q(is_active=True, deleted_at__isnull=True),
                name="uq_schoolyear_single_active",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class SchoolTerm(BaseModel):
    """Ders yılının iki dönemi.

    Sınav takvimi (F6, `ExamCalendar.semester`) ve dönem bazlı raporlar buna
    bağlanır; mevzuat pencereleri (`statutory_window`) dönem sınırlarına kırpılır.
    """

    school_year = models.ForeignKey(
        SchoolYear,
        on_delete=models.CASCADE,
        related_name="terms",
        verbose_name="ders yılı",
    )
    sequence = models.PositiveSmallIntegerField("dönem", choices=((1, "1. dönem"), (2, "2. dönem")))
    start_date = models.DateField("başlangıç")
    end_date = models.DateField("bitiş")

    class Meta:
        verbose_name = "ders dönemi"
        verbose_name_plural = "ders dönemleri"
        ordering = ["school_year", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["school_year", "sequence"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_schoolterm_year_sequence_alive",
            ),
            models.CheckConstraint(
                condition=models.Q(sequence__in=(1, 2)),
                name="ck_schoolterm_sequence",
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="ck_schoolterm_date_order",
            ),
        ]
        indexes = [
            models.Index(fields=["school_year", "start_date"], name="schoolterm_year_start_idx"),
        ]

    @property
    def name(self) -> str:
        return f"{self.sequence}. dönem"

    def __str__(self) -> str:
        return f"{self.school_year.name} · {self.name}"


class Personnel(BaseModel):
    """Okul personeli — login'siz sicil kaydı.

    Gözetmen aday havuzu (F7) = aktif personel − muaf; `is_active` bu yüzden
    buradadır. Ad-soyad ŞİFRELİDİR (U3) — ada dayalı arama/teklik Python
    katmanında yapılır (TB3), unvan/branş süzgeçleri DB tarafında kalır.
    """

    first_name = EncryptedCharField("ad", max_length=100)
    last_name = EncryptedCharField("soyad", max_length=100)
    title = models.CharField("unvan", max_length=64, blank=True, default="")
    branch = models.CharField("branş", max_length=64, blank=True, default="")
    is_active = models.BooleanField("aktif", default=True)

    class Meta:
        verbose_name = "personel"
        verbose_name_plural = "personel"
        # Şifreli alanda DB sıralaması anlamsızdır (token sırası) — kayıt sırası
        # kararlı olsun diye pk; ad sıralaması selector'da Python ile yapılır.
        ordering = ["pk"]

    def __str__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def get_full_name(self) -> str:
        """OYS `User.get_full_name` paritesi — evrak şablonları (AYNEN kopya) bu adı çağırır."""
        return self.full_name


class ClassSectionGroup(BaseModel):
    """Şube kümesi — "Sayısal", "Eşit Ağırlık", "Dil" gibi seçim kolaylığı etiketi.

    AMACI YALNIZ SEÇİM MALİYETİNİ DÜŞÜRMEKTİR: sınav sihirbazında şubeler tek
    tek işaretlenmek yerine küme çipiyle topluca eklenir. Küme kimliği HİÇBİR
    oturum kaydına yazılmaz — `ExamSessionCourse.section_ids` somut şube
    pk'leri tutmaya devam eder. Aksi hâlde küme sonradan değişince ONAYLANMIŞ
    oturumun katılımcı kümesi geriye dönük kayar; bu SNAPSHOT desenini ve
    "aynı seed → aynı dağıtım" sözleşmesini bozardı.

    Üyelik TEKtir (kullanıcı kararı 31.08.2026): bir şube en çok bir kümededir
    (`ClassSection.group`). Küme yıldan bağımsızdır — "Sayısal" her yıl aynı
    kümedir; yıla bağlanan şubenin kendisidir. Kişisel veri içermez.
    """

    name = models.CharField("küme adı", max_length=60)
    order = models.PositiveSmallIntegerField("sıra", default=0)

    class Meta:
        verbose_name = "şube kümesi"
        verbose_name_plural = "şube kümeleri"
        # Görüntü sıralaması Türk alfabesiyle selector'da; DB sırası kararlı olsun.
        ordering = ["order", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_classsectiongroup_name_alive",
            )
        ]

    def __str__(self) -> str:
        return self.name


class ClassSection(BaseModel):
    """Şube kataloğu — ders yılı içinde görülen (seviye, şube) çiftleri.

    İçe aktarma sonrası tohumlanır (`imports._ensure_class_sections`), elle de
    eklenebilir. F2'de `ExamRoom.linked_section` buna FK verir (klasik düzen ve
    "şube dersliği" eşlemesi); R2k şube yoklaması bu katalogdan üretilir.
    """

    school_year = models.ForeignKey(
        SchoolYear,
        on_delete=models.PROTECT,
        related_name="class_sections",
        verbose_name="ders yılı",
    )
    class_level = models.PositiveSmallIntegerField("sınıf")
    class_section = models.CharField("şube", max_length=8)
    group = models.ForeignKey(
        ClassSectionGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sections",
        verbose_name="şube kümesi",
        help_text="Yalnız seçim kolaylığı; oturum kaydına küme kimliği YAZILMAZ.",
    )

    class Meta:
        verbose_name = "şube"
        verbose_name_plural = "şubeler"
        ordering = ["school_year", "class_level", "class_section"]
        constraints = [
            models.UniqueConstraint(
                fields=["school_year", "class_level", "class_section"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_class_section_alive",
            )
        ]
        indexes = [
            models.Index(
                fields=["school_year", "class_level", "class_section"],
                name="okul_class_section_lookup_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.school_year.name} — {self.class_label}"

    @property
    def class_label(self) -> str:
        if self.class_level == 0:
            return f"Hz/{self.class_section}"
        return f"{self.class_level}/{self.class_section}"


class SubjectDepartment(BaseModel):
    """Zümre — okul zümre başkanları kurulunu oluşturan sınıf/alan zümreleri.

    Mevzuat karşılığı "eğitim kurumu sınıf/alan zümresi": aynı sınıfı okutan
    veya alanı aynı olan öğretmenlerden oluşan zümre (Ölçme ve Değerlendirme
    Yönetmeliği md. 3; Yazılı ve Uygulamalı Sınavlar Yönergesi md. 4). Okul
    geneli ortak yazılı sınavların soru/uygulama/değerlendirme sorumluluğu bu
    zümrelerdedir (Yönerge md. 5), imza bloğu da buradan beslenir.

    B7 revizyonu: sınav takvimi PDF'inin imza bloğu artık "her ders bir zümre"
    varsaymaz — takvime SEÇİLEN zümreler basılır (`ExamCalendar
    .signatory_departments`). Zümre seçilmemiş takvimlerde eski dal (takvimdeki
    derslerden boş imza çizgileri) yedek yol olarak durur.

    Başkan adı `Personnel` üzerindeki ŞİFRELİ alandan okunur; bu modelde ad
    kopyası TUTULMAZ. Zümre adı düz metindir — teklik kısıtı DB'de çalışır.
    """

    name = models.CharField("zümre adı", max_length=80)
    head = models.ForeignKey(
        "okul.Personnel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="chaired_departments",
        verbose_name="zümre başkanı",
        help_text="Personel sicilinden seçilir; boş bırakılırsa evrakta noktalı çizgi basılır.",
    )
    is_board_member = models.BooleanField(
        "kurul üyesi",
        default=True,
        help_text="Okul zümre başkanları kuruluna katılan zümre.",
    )

    class Meta:
        verbose_name = "zümre"
        verbose_name_plural = "zümreler"
        # Ad ŞİFRELİ DEĞİL — Personnel'deki Python dolambacı burada gerekmez.
        # Görüntü sıralaması yine de Python'da (Türk alfabesi, selectors).
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_subjectdepartment_name_alive",
            )
        ]

    def __str__(self) -> str:
        return self.name


class StudentStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Aktif"
    LEFT = "LEFT", "Ayrıldı"


class Student(BaseModel):
    """Öğrenci — kelebek dağıtımının kişi kaydı (tasarım §4).

    Evrak sözleşmesi: `full_name`, `student_number`, `class_label` — OYS
    sinav_islemleri SNAPSHOT alanları (SeatAssignment vb.) bu üçünden kopyalanır.

    ŞİFRELEME KAPSAMI (U3, tasarım §5): `first_name`/`last_name` şifrelidir;
    okul no ve sınıf/şube AÇIKTIR (motor, sıralama, teklik ve süzgeçler bunlara
    dayanır; ad olmadan takma-adlıdırlar). TCKN/veli/demografi alanı YOKTUR.
    """

    first_name = EncryptedCharField("ad", max_length=100)
    last_name = EncryptedCharField("soyad", max_length=100)
    student_number = models.CharField("okul no", max_length=16, blank=True, default="")
    class_level = models.PositiveSmallIntegerField("sınıf", null=True, blank=True)
    class_section = models.CharField("şube", max_length=8, blank=True, default="")
    status = models.CharField(
        "durum", max_length=16, choices=StudentStatus.choices, default=StudentStatus.ACTIVE
    )

    class Meta:
        verbose_name = "öğrenci"
        verbose_name_plural = "öğrenciler"
        # Ad şifreli → DB'de ada sıralanamaz; sınıf/şube/no sıralaması yeter
        # (okul no metin alanıdır, sayısal sıralama selector'da yapılır).
        ordering = ["class_level", "class_section", "student_number"]
        indexes = [
            models.Index(fields=["class_level", "class_section"], name="okul_student_class_idx"),
        ]
        constraints = [
            # Okul numaralı AKTİF canlı kayıt tekil — içe aktarma upsert anahtarı.
            # Ayrılan öğrencinin numarası ileride başka öğrenciye verilebilir.
            models.UniqueConstraint(
                fields=["student_number"],
                condition=(
                    models.Q(deleted_at__isnull=True, status="ACTIVE")
                    & ~models.Q(student_number="")
                ),
                name="uq_student_number_active_alive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.class_label or 'sınıfsız'})"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def class_label(self) -> str:
        """'10/A' — evrak ve arayüzün beklediği sınıf etiketi; sınıfsız → ''."""
        if self.class_level is None or not self.class_section:
            return ""
        if self.class_level == 0:
            return f"Hz/{self.class_section}"
        return f"{self.class_level}/{self.class_section}"


class ImportSourceType(models.TextChoices):
    """İçe aktarma kaynak türü (xlsx ve pano yapıştırma AYNI türdedir)."""

    STUDENTS = "STUDENTS", "Öğrenci"
    PERSONNEL = "PERSONNEL", "Personel"


class ImportStatus(models.TextChoices):
    RUNNING = "RUNNING", "Çalışıyor"
    COMPLETED = "COMPLETED", "Tamamlandı"
    FAILED = "FAILED", "Başarısız"
    PREVIEWED = "PREVIEWED", "Önizlendi"


class ImportRun(BaseModel):
    """Her toplu içe aktarma için bir kayıt (geçmiş izi + idempotency uyarısı).

    DD kalıbı: aynı dosyanın yeniden COMMIT'i ENGELLENMEZ — `already_imported`
    yalnız UYARIDIR (güncelleme meşru). Kısıt bozulmasın diye yeniden commit
    MEVCUT COMPLETED satırı günceller (yeni satır açmaz).
    """

    source_type = models.CharField(
        "kaynak türü", max_length=16, choices=ImportSourceType.choices, db_index=True
    )
    file_name = models.CharField("dosya adı", max_length=255, blank=True, default="")
    file_hash = models.CharField("içerik özeti (SHA256)", max_length=64, db_index=True)
    status = models.CharField(
        "durum", max_length=16, choices=ImportStatus.choices, default=ImportStatus.RUNNING
    )
    started_at = models.DateTimeField("başlangıç", default=timezone.now)
    finished_at = models.DateTimeField("bitiş", null=True, blank=True)
    report = models.JSONField("rapor", default=dict, blank=True)

    class Meta:
        verbose_name = "içe aktarma koşusu"
        verbose_name_plural = "içe aktarma koşuları"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["source_type", "file_hash"], name="okul_importrun_hash_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "file_hash"],
                condition=models.Q(deleted_at__isnull=True, status="COMPLETED"),
                name="uq_importrun_completed_per_hash",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_source_type_display()} — {self.file_name or self.file_hash[:12]}"
