"""sinav modelleri — salon (F2) + oturum (F3) + kitapçık (F5) + takvim (F6) + gözetmen (F7).

OYS `sinav_islemleri/models.py`'den UYARLA (tasarım §11): `created_by` ve User
FK'ları düşer (onay/beyan damgaları ad-snapshot + zaman olarak kalır — B12),
`linked_section` → okul.ClassSection, Course → dersler.Course, Semester →
okul.SchoolTerm; SeatAssignment/ExamAttendanceRecord ad snapshot'ları
EncryptedCharField (U3). Gözetmen modelleri F7 ile tamamlandı.
"""

from __future__ import annotations

from django.db import models

from shared.crypto import EncryptedCharField
from shared.models import BaseModel


class NumberingScheme(models.TextChoices):
    """Koltuk numaralandırma düzeni (dönemlik kılavuz: S düzeni varsayılan)."""

    S_PATTERN = "S_PATTERN", "S düzeni"
    STRAIGHT = "STRAIGHT", "Düz"


class DeskType(models.TextChoices):
    SINGLE = "SINGLE", "Tekli"
    DOUBLE = "DOUBLE", "İkili"
    TRIPLE = "TRIPLE", "Üçlü"


class FurnitureKind(models.TextChoices):
    DOOR = "DOOR", "Kapı"
    BLACKBOARD = "BLACKBOARD", "Yazı tahtası"
    SMART_BOARD = "SMART_BOARD", "Akıllı tahta"
    TEACHER_DESK = "TEACHER_DESK", "Öğretmen masası"


class ExamRoom(BaseModel):
    """Sınav salonu — 2D yerleşim planı + numaralandırma düzeni.

    `layout_plan` JSON şeması SERVİS katmanında doğrulanır (`layout.py`);
    kapasite plandaki aktif sıra hücrelerinden hesaplanır, ayrıca alan olarak
    tutulmaz. `linked_section` "bu salon 11-C'nin dersliğidir" eşlemesidir —
    klasik (kendi dersliğinde) düzenin ve KENDI_DERSLIGINDE sabit kuralının
    temeli. Kişisel veri içermez.
    """

    name = models.CharField(
        "salon adı",
        max_length=80,
        db_index=True,
        help_text="Örn. 'D-204', 'Fen Laboratuvarı'.",
    )
    block = models.CharField(
        "blok / kat",
        max_length=80,
        blank=True,
        default="",
        help_text="Serbest konum bilgisi (örn. 'A Blok 2. Kat').",
    )
    linked_section = models.ForeignKey(
        "okul.ClassSection",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="exam_rooms",
        verbose_name="bağlı şube",
        help_text="Salon bir şubenin dersliğiyse o şube (klasik düzen eşlemesi).",
    )
    layout_plan = models.JSONField(
        "yerleşim planı",
        default=dict,
        blank=True,
        help_text="2D plan: grid + sıralar (tekli/ikili/üçlü) + mobilya. "
        "Şema layout.validate_layout_plan ile doğrulanır.",
    )
    numbering_scheme = models.CharField(
        "numaralandırma",
        max_length=10,
        choices=NumberingScheme.choices,
        default=NumberingScheme.S_PATTERN,
    )
    is_active = models.BooleanField(
        "aktif",
        default=True,
        help_text="Pasif salon yeni oturum planlamasında seçilemez; kayıt silinmez.",
    )

    class Meta:
        verbose_name = "sınav salonu"
        verbose_name_plural = "sınav salonları"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_examroom_name_alive",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class ExamSessionType(models.TextChoices):
    SCHOOL = "SCHOOL", "Okul"
    DISTRICT = "DISTRICT", "İlçe"
    PROVINCE = "PROVINCE", "İl"
    NATIONAL = "NATIONAL", "Ülke"


class LayoutMode(models.TextChoices):
    """Oturum düzeyinde düzen — kelebek veya kendi dersliğinde (K16)."""

    BUTTERFLY = "BUTTERFLY", "Kelebek"
    HOME_CLASSROOM = "HOME_CLASSROOM", "Kendi dersliğinde"


class ExamSessionStatus(models.TextChoices):
    DRAFT = "DRAFT", "Taslak"
    DISTRIBUTED = "DISTRIBUTED", "Dağıtıldı"
    APPROVED = "APPROVED", "Onaylandı"
    ARCHIVED = "ARCHIVED", "Arşiv"


class ParticipantType(models.TextChoices):
    """Oturum dersi katılımcı atama yolu.

    OYS'deki üçüncü tip (GROUPS — şube içi ders grupları) ALINMADI: gruplar
    OYS'de ders programı çekirdeğinden (LessonGroup/SectionGroup) türer ve o
    zincir KS'ye taşınmadı (tasarım §11 ALMA). LEVEL + SECTIONS lise ortak
    sınav pratiğini karşılar; sapma teknik borç kütüğüne işlendi (TB7).
    """

    LEVEL = "LEVEL", "Seviye geneli"
    SECTIONS = "SECTIONS", "Şube şube"


class ExamSession(BaseModel):
    """Sınav oturumu — tarih/saat + düzen + durum.

    Düzen oturum düzeyindedir (K3); gözetmen opsiyoneldir (U2, varsayılan
    kapalı). Adım 0 nakil ön kontrol onayı beyan damgasıyla oturuma yazılır
    (transfer_check_* — B10: veri sorgusu yok, kullanıcı beyanı + ad + zaman).
    Yalnız TASLAK durumda düzenlenebilir; durum geçişleri serviste. Onay
    damgaları (approved_*) tek kullanıcıda da KORUNUR — basılı evrakın resmî
    değeri damgaya dayanır (tasarım B12). Oturum tanımı kişisel veri içermez;
    öğrenci verisi snapshot ALT-modellerindedir.
    """

    name = models.CharField("oturum adı", max_length=120)
    exam_date = models.DateField("sınav tarihi", db_index=True)
    start_time = models.TimeField("başlangıç saati")
    duration_minutes = models.PositiveSmallIntegerField(
        "süre (dk)",
        default=40,
        help_text="Oturumun varsayılan süresi (40 dk); ders bazlı süre ezilebilir.",
    )
    session_type = models.CharField(
        "tür", max_length=10, choices=ExamSessionType.choices, default=ExamSessionType.SCHOOL
    )
    layout_mode = models.CharField(
        "düzen", max_length=14, choices=LayoutMode.choices, default=LayoutMode.BUTTERFLY
    )
    proctors_enabled = models.BooleanField(
        "gözetmen modülü", default=False, help_text="U2 — varsayılan kapalı."
    )
    semester = models.ForeignKey(
        "okul.SchoolTerm",
        on_delete=models.PROTECT,
        related_name="exam_sessions",
        verbose_name="dönem",
    )
    status = models.CharField(
        "durum",
        max_length=12,
        choices=ExamSessionStatus.choices,
        default=ExamSessionStatus.DRAFT,
        db_index=True,
    )
    distribution_params = models.JSONField(
        "dağıtım parametreleri",
        default=dict,
        blank=True,
        help_text="Seed, mod ve opsiyonlar (dağıtım motoru yazar; seed R8'de basılır).",
    )
    # Adım 0 — nakil ön kontrol beyanı (Yönerge md. 5/1-v): kim/ne zaman.
    # OYS'de User FK'siydi; tek kullanıcıda beyan sahibi ad SNAPSHOT'ı yeter.
    transfer_check_confirmed_by_name = models.CharField(
        "nakil kontrolünü onaylayan", max_length=128, blank=True, default=""
    )
    transfer_check_confirmed_at = models.DateTimeField(
        "nakil kontrolü onay zamanı", null=True, blank=True
    )
    approved_by_name = models.CharField("onaylayan", max_length=128, blank=True, default="")
    approved_at = models.DateTimeField("onay zamanı", null=True, blank=True)
    # F27: arşiv saklama süresi dolunca snapshot'lar anonimleştirilir (geri
    # dönüşsüz — F8'de elle tetikli); damga doluysa oturum anonimleşmiştir.
    anonymized_at = models.DateTimeField("anonimleştirme zamanı", null=True, blank=True)

    class Meta:
        verbose_name = "sınav oturumu"
        verbose_name_plural = "sınav oturumları"
        ordering = ["-exam_date", "start_time"]

    def __str__(self) -> str:
        return f"{self.name} — {self.exam_date}"

    @property
    def is_draft(self) -> bool:
        return self.status == ExamSessionStatus.DRAFT


class ExamSessionCourse(BaseModel):
    """Oturumdaki bir ders + TEK seviye + katılımcı tanımı.

    OYS Tur 241 dersi (CLAUDE.md §3): her satır tek seviyeye bağlıdır —
    "Matematik — 9. Sınıf" ve "Matematik — 10. Sınıf" ayrı satırlar. Soru
    dosyası ve çakışma grubu satır bazında seviyeye ayrışır. Katılımcı
    referansları JSON id listeleridir (`section_ids`) — nihai öğrenci listesi
    katılımcı çözümleyiciden anlık türetilir, burada KİŞİSEL VERİ TUTULMAZ.
    `shared_booklet` ("ortak kitapçık"): aynı dersin oturumdaki TÜM satırları
    tek kitapçıkla giriyorsa tek çakışma grubu sayılır — bayrak kardeş
    satırlarda senkron tutulur (servis doğrular).
    """

    session = models.ForeignKey(
        ExamSession, on_delete=models.CASCADE, related_name="courses", verbose_name="oturum"
    )
    course = models.ForeignKey(
        "dersler.Course",
        on_delete=models.PROTECT,
        related_name="session_courses",
        verbose_name="ders",
    )
    duration_minutes = models.PositiveSmallIntegerField(
        "süre (dk)", null=True, blank=True, help_text="Boş = oturum süresi."
    )
    participant_type = models.CharField(
        "katılımcı tipi", max_length=10, choices=ParticipantType.choices
    )
    level = models.PositiveSmallIntegerField(
        "seviye",
        null=True,
        blank=True,
        help_text="Satırın tek seviyesi (0 = Hazırlık). Servis katmanı zorunlu kılar.",
    )
    section_ids = models.JSONField(
        "şube id'leri",
        default=list,
        blank=True,
        help_text="SECTIONS tipi için okul.ClassSection id.",
    )
    shared_booklet = models.BooleanField(
        "ortak kitapçık",
        default=False,
        help_text="Karma seviyeler tek kitapçık/tek çakışma grubu.",
    )

    class Meta:
        verbose_name = "oturum dersi"
        verbose_name_plural = "oturum dersleri"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "course", "level"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_examsessioncourse_level_alive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.session_id} — {self.course} ({self.level})"


class ExamSessionRoom(BaseModel):
    """Oturumda kullanılacak salon."""

    session = models.ForeignKey(
        ExamSession, on_delete=models.CASCADE, related_name="rooms", verbose_name="oturum"
    )
    room = models.ForeignKey(
        ExamRoom, on_delete=models.PROTECT, related_name="session_rooms", verbose_name="salon"
    )
    order = models.PositiveSmallIntegerField(
        "kullanım sırası", default=0, help_text="Dağıtım/paketleme salon sırası."
    )
    capacity_override = models.PositiveSmallIntegerField(
        "kapasite sınırı",
        null=True,
        blank=True,
        help_text="Boş = plandan hesaplanan kapasite.",
    )

    class Meta:
        verbose_name = "oturum salonu"
        verbose_name_plural = "oturum salonları"
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "room"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_examsessionroom_alive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.session_id} — {self.room}"


class SeatStatus(models.TextChoices):
    NORMAL = "NORMAL", "Normal"
    PINNED = "PINNED", "Sabit"  # yerleştirme kuralı yerleştirmesi
    MANUAL = "MANUAL", "Elle taşındı"  # önizleme takası


class SeatAssignment(BaseModel):
    """Yerleşim — bir öğrencinin oturumdaki koltuğu (SNAPSHOT deseni).

    Ad/no/şube SNAPSHOT'tır: yerleşim arşivi yıllar sonra denetimde açılabilir;
    kaynak kayıt değişse de evrak tutarlı kalır. `full_name` snapshot'ı
    ŞİFRELİDİR (U3, tasarım §5 — kaynak şifreli olup kopya düz kalsaydı
    şifreleme anlamsızlaşırdı); okul no ve sınıf etiketi düz kalır (süzgeç ve
    sıralama bunlara dayanır). Koltuk kimliği (desk_row, desk_col, slot) +
    rota numarası (seat_no) salon planından gelir; koordinatlar plandan
    yeniden türetilir, burada tutulmaz.
    """

    session = models.ForeignKey(
        ExamSession,
        on_delete=models.CASCADE,
        related_name="seat_assignments",
        verbose_name="oturum",
    )
    student = models.ForeignKey(
        "okul.Student",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="exam_seat_assignments",
        verbose_name="öğrenci",
        help_text="Anonimleştirilmiş arşivde boş (F27) — canlı yerleşimde her zaman dolu.",
    )
    # Snapshot alanları (arşiv tutarlılığı — kaynak değişse de evrak sabit).
    full_name = EncryptedCharField("ad soyad (snapshot)", max_length=150)
    student_number = models.CharField("okul no (snapshot)", max_length=20)
    class_label = models.CharField("sınıf/şube (snapshot)", max_length=12)
    room = models.ForeignKey(
        ExamRoom,
        on_delete=models.PROTECT,
        related_name="seat_assignments",
        verbose_name="salon",
    )
    desk_row = models.PositiveSmallIntegerField("sıra satırı")
    desk_col = models.PositiveSmallIntegerField("sıra sütunu")
    slot = models.PositiveSmallIntegerField("sıra içi pozisyon")
    seat_no = models.PositiveSmallIntegerField("koltuk no")
    status = models.CharField(
        "durum", max_length=8, choices=SeatStatus.choices, default=SeatStatus.NORMAL
    )
    conflict_group = models.CharField(
        "çakışma grubu",
        max_length=24,
        help_text="Motor anahtarı: '<course_id>:<level>' veya '<course_id>:*'.",
    )

    class Meta:
        verbose_name = "yerleşim"
        verbose_name_plural = "yerleşimler"
        ordering = ["room_id", "seat_no"]
        constraints = [
            # Bir koltuğa tek öğrenci; bir öğrenciye oturumda tek koltuk (canlı).
            models.UniqueConstraint(
                fields=["session", "room", "seat_no"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_seat_session_room_seat_alive",
            ),
            models.UniqueConstraint(
                fields=["session", "student"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_seat_session_student_alive",
            ),
        ]
        indexes = [
            models.Index(fields=["session", "room"], name="sinav_seat_session_room_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.session_id}/{self.room_id} #{self.seat_no} — No {self.student_number}"


class ExcuseStatus(models.TextChoices):
    PENDING = "PENDING", "Beklemede"
    EXCUSED = "EXCUSED", "Özürlü"
    UNEXCUSED = "UNEXCUSED", "Özürsüz"


class ExamAttendanceRecord(BaseModel):
    """Sınava GİRMEYEN öğrenci kaydı + mazeret durumu.

    Yalnız DURUM kaydı — belge dosyası YÜKLENMEZ; `note` alanına belge
    no/tarih yazılır (mevzuat: mazeret sınav tarihinden itibaren en geç 5 iş
    günü içinde yazılı bildirilir — Yönerge md. 5/1-y). Snapshot alanları
    SeatAssignment deseniyle; `full_name` ŞİFRELİDİR (U3). İşaretleme yalnız
    ONAYLI/ARŞİV oturumda (yerleşim kesinleşmeden yoklama anlamsız); mazeret
    güncellemesi ARŞİVDE DE açıktır — belge günler sonra gelir, arşiv
    salt-okunurluğu yerleşim evrakı içindir, idari yoklama süreci değil.
    """

    session = models.ForeignKey(
        ExamSession,
        on_delete=models.CASCADE,
        related_name="attendance_records",
        verbose_name="oturum",
    )
    student = models.ForeignKey(
        "okul.Student",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="exam_attendance_records",
        verbose_name="öğrenci",
        help_text="Anonimleştirilmiş arşivde boş (F27).",
    )
    # Snapshot (SeatAssignment deseni — arşiv tutarlılığı).
    full_name = EncryptedCharField("ad soyad (snapshot)", max_length=150)
    student_number = models.CharField("okul no (snapshot)", max_length=20)
    class_label = models.CharField("sınıf/şube (snapshot)", max_length=12)
    room = models.ForeignKey(
        ExamRoom,
        on_delete=models.PROTECT,
        related_name="attendance_records",
        verbose_name="salon",
    )
    seat_no = models.PositiveSmallIntegerField("koltuk no")
    excuse_status = models.CharField(
        "mazeret durumu",
        max_length=10,
        choices=ExcuseStatus.choices,
        default=ExcuseStatus.PENDING,
        db_index=True,
    )
    note = models.TextField(
        "açıklama",
        blank=True,
        default="",
        help_text=(
            "Belge no/tarih gibi serbest metin (örn. 'Rapor no 123, 10.06.2026'). "
            "SAĞLIK TANISI YAZMAYIN — KVKK Madde 6 özel nitelikli veridir."
        ),
    )

    class Meta:
        verbose_name = "sınav yoklama kaydı"
        verbose_name_plural = "sınav yoklama kayıtları"
        ordering = ["room_id", "seat_no"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "student"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_examattendance_session_student_alive",
            ),
        ]
        indexes = [
            models.Index(fields=["session", "room"], name="sinav_attend_sess_room_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.session_id} — #{self.seat_no} girmedi ({self.excuse_status})"


class RuleScope(models.TextChoices):
    SESSION = "SESSION", "Oturum"
    PERMANENT = "PERMANENT", "Kalıcı"


class RuleType(models.TextChoices):
    HOME_CLASSROOM = "HOME_CLASSROOM", "Kendi dersliğinde"
    FIXED_ROOM = "FIXED_ROOM", "Belirli salon"
    FRONT_ROW = "FRONT_ROW", "Ön sıra"
    SEPARATE_ROOM = "SEPARATE_ROOM", "Ayrı salon"


class RuleReason(models.TextChoices):
    """Gerekçe YALNIZ kategori — tanı/rapor detayı ASLA tutulmaz (KVKK Madde 6)."""

    DISABILITY = "DISABILITY", "Engel durumu"
    IEP = "IEP", "BEP"
    HEALTH = "HEALTH", "Sağlık"
    OTHER = "OTHER", "Diğer"


class PlacementRule(BaseModel):
    """Sabit yerleştirme kuralı.

    ÖZEL NİTELİKLİ VERİYE İŞARET EDER (KVKK Madde 6): `reason_category`
    kategori düzeyinde bile engel/BEP/sağlık bilgisini ima eder — yalnız
    kategori tutulur, serbest metin alanı BİLİNÇLE YOKTUR (OYS tasarımı aynen).

    Kapsam: SESSION → yalnız o oturumda (session zorunlu); PERMANENT → tüm
    oturumlarda (session boş). Oturum kuralı kalıcı kuralı EZER. Dağıtımda
    kural sahibi öğrenci PINNED statüsüyle yerleşir; kelebek motoru taşıyamaz.
    """

    student = models.ForeignKey(
        "okul.Student",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="exam_placement_rules",
        verbose_name="öğrenci",
        help_text="Anonimleştirilmiş arşivin oturum-kurallarında boş (F27).",
    )
    scope = models.CharField(
        "kapsam", max_length=10, choices=RuleScope.choices, default=RuleScope.PERMANENT
    )
    session = models.ForeignKey(
        ExamSession,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="placement_rules",
        verbose_name="oturum",
        help_text="Yalnız SESSION kapsamında dolu.",
    )
    rule_type = models.CharField("kural tipi", max_length=14, choices=RuleType.choices)
    target_room = models.ForeignKey(
        ExamRoom,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="placement_rules",
        verbose_name="hedef salon",
        help_text="BELIRLI_SALON / AYRI_SALON için zorunlu.",
    )
    reason_category = models.CharField(
        "gerekçe kategorisi",
        max_length=10,
        choices=RuleReason.choices,
        default=RuleReason.OTHER,
    )

    class Meta:
        verbose_name = "yerleştirme kuralı"
        verbose_name_plural = "yerleştirme kuralları"
        ordering = ["-created_at"]
        constraints = [
            # Öğrenci başına tek canlı KALICI kural; oturum başına tek canlı kural.
            models.UniqueConstraint(
                fields=["student"],
                condition=models.Q(deleted_at__isnull=True, session__isnull=True),
                name="uq_placementrule_permanent_alive",
            ),
            models.UniqueConstraint(
                fields=["student", "session"],
                condition=models.Q(deleted_at__isnull=True, session__isnull=False),
                name="uq_placementrule_session_alive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student_id} — {self.get_rule_type_display()} ({self.get_scope_display()})"


class ScoreMode(models.TextChoices):
    """Başlık puan bölümü (K5): tek kutu varsayılan; soru sayısı girilirse tablo."""

    SINGLE_BOX = "SINGLE_BOX", "Tek puan kutusu"
    QUESTION_TABLE = "QUESTION_TABLE", "Soru bazlı puan tablosu"


class QuestionDocument(BaseModel):
    """Oturum dersinin soru dosyası (F5 — OYS §4.5/T7'den UYARLA).

    Sınav öncesi gizlilik: dosya yalnız yerel API üzerinden (X-KS-Token)
    sunulur, media URL'i yoktur. Kişisel veri içermez (sorular), ama üretilen
    kitapçıklar içerir (BookletRun'a bakınız).
    """

    # FK + kısmi unique (OneToOne DEĞİL): yeniden yükleme eskisini soft-delete
    # eder; sert unique sütunu silinmiş satırla çakışırdı (DD soft-delete izi).
    session_course = models.ForeignKey(
        ExamSessionCourse,
        on_delete=models.CASCADE,
        related_name="question_documents",
        verbose_name="oturum dersi",
    )
    file = models.FileField("soru PDF'i", upload_to="exam_questions/%Y/%m/")
    page_count = models.PositiveSmallIntegerField("sayfa sayısı")
    sha256 = models.CharField("içerik özeti", max_length=64)
    score_mode = models.CharField(
        "puan bölümü", max_length=14, choices=ScoreMode.choices, default=ScoreMode.SINGLE_BOX
    )
    question_count = models.PositiveSmallIntegerField(
        "soru sayısı", null=True, blank=True, help_text="Puan tablosu için (K5)."
    )
    # scaling_enabled alanı OYS Tur 239'da kaldırılmıştı; KS'ye hiç girmedi —
    # ölçekleme yok, bant sabit 4 cm.

    class Meta:
        verbose_name = "soru dosyası"
        verbose_name_plural = "soru dosyaları"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["session_course"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_questiondoc_sessioncourse_alive",
            ),
        ]

    def __str__(self) -> str:
        return f"Soru dosyası — oturum dersi {self.session_course_id}"


class BookletRunStatus(models.TextChoices):
    PENDING = "PENDING", "Bekliyor"
    IN_PROGRESS = "IN_PROGRESS", "Üretiliyor"
    COMPLETED = "COMPLETED", "Tamamlandı"
    FAILED = "FAILED", "Başarısız"


class BookletRun(BaseModel):
    """Kişiselleştirilmiş kitapçık üretim koşusu (R10 — OYS T7'den UYARLA).

    KS'de üretim SENKRONDUR (Celery yok): koşu tek çağrıda COMPLETED/FAILED'a
    iner; PENDING/IN_PROGRESS değerleri durum sözlüğü OYS ile birebir kalsın
    diye korunur. Çıktı ZIP salon bazlı birleşik PDF'ler taşır ve KİŞİSEL VERİ
    İÇERİR (kitapçık başlığında ad/no/şube) — dosya yalnız API'den sunulur.
    """

    session = models.ForeignKey(
        ExamSession, on_delete=models.CASCADE, related_name="booklet_runs", verbose_name="oturum"
    )
    status = models.CharField(
        "durum",
        max_length=12,
        choices=BookletRunStatus.choices,
        default=BookletRunStatus.PENDING,
        db_index=True,
    )
    file = models.FileField("ZIP", upload_to="exam_booklets/%Y/%m/", blank=True)
    backup_copies = models.PositiveSmallIntegerField(
        "isimsiz yedek kopya", default=0, help_text="Salon başına isimsiz kitapçık adedi."
    )
    manifest = models.JSONField(
        "manifest",
        default=dict,
        blank=True,
        help_text="Salon → dosya adı/kitapçık/sayfa sayıları (PII yok).",
    )
    error_message = models.TextField("hata", blank=True, default="")
    completed_at = models.DateTimeField("tamamlanma", null=True, blank=True)

    class Meta:
        verbose_name = "kitapçık koşusu"
        verbose_name_plural = "kitapçık koşuları"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Kitapçık koşusu #{self.pk} — oturum {self.session_id} ({self.status})"


# ===========================================================================
# F6 — sınav takvimi + süreç takibi (OYS FAZ T / ADR-0044'ten UYARLA)
# ===========================================================================


class ExamCalendarStatus(models.TextChoices):
    DRAFT = "DRAFT", "Taslak"
    SUBMITTED = "SUBMITTED", "Onaya Sunuldu"
    APPROVED = "APPROVED", "Onaylandı"


class ExamKind(models.TextChoices):
    """Sınav türü — yazılı / uygulama (Excel '[UYGULAMA SINAVI]' ayrı slot)."""

    WRITTEN = "WRITTEN", "Yazılı"
    PRACTICE = "PRACTICE", "Uygulama"


class ExamTrackMarkStatus(models.TextChoices):
    """Süreç takip işareti — 'yapılmadı' = kayıt yokluğu (üçüncü durum tutulmaz)."""

    DONE = "DONE", "Yapıldı"
    NOT_APPLICABLE = "NOT_APPLICABLE", "Kapsam dışı"


class ExamCalendar(BaseModel):
    """Ortak sınav takvimi — dönem+tur bazlı (OYS ADR-0044'ten UYARLA).

    DRAFT → SUBMITTED → APPROVED (reopen ile geri alınır); havuz/yerleştirme
    yalnız DRAFT'ta değişir. KS uyarlaması (B12): iki-kişilik "hazırlayan
    onaylayamaz" akışı tek kullanıcıya indi — SUBMITTED tek tıkla geçilir;
    APPROVED kilidi ve onay damgaları (ad-snapshot + zaman) KORUNUR (resmî
    evrak değeri — risk #10). `school_year` FK'sı düştü: dönem (SchoolTerm)
    yılı zaten taşır, teklik (dönem, tur) üstünden. `description_text` create
    sırasında varsayılan mevzuat-dayanaklı metinden kopyalanır (şablon
    güncellenirse eski takvimler etkilenmez).
    """

    semester = models.ForeignKey(
        "okul.SchoolTerm",
        on_delete=models.PROTECT,
        related_name="exam_calendars",
        verbose_name="dönem",
    )
    round = models.PositiveSmallIntegerField(
        "sınav turu",
        help_text="Dönem içi kaçıncı ortak sınav (1-3; 3 = haftalık ≥6 saatlik derste).",
    )
    name = models.CharField(
        "takvim adı",
        max_length=120,
        help_text="Otomatik '1. Dönem 1. Sınav Takvimi'; düzenlenebilir.",
    )
    start_date = models.DateField("başlangıç tarihi")
    end_date = models.DateField("bitiş tarihi")
    status = models.CharField(
        "durum",
        max_length=12,
        choices=ExamCalendarStatus.choices,
        default=ExamCalendarStatus.DRAFT,
        db_index=True,
    )
    description_text = models.TextField(
        "açıklama metni",
        blank=True,
        default="",
        help_text="Takvim ile imza bloğu arasındaki açıklamalar (mazeret, 'G', vb.).",
    )
    submitted_at = models.DateTimeField("onaya sunulma zamanı", null=True, blank=True)
    approved_by_name = models.CharField(
        "onaylayan (ad-snapshot)", max_length=128, blank=True, default=""
    )
    approved_at = models.DateTimeField("onay zamanı", null=True, blank=True)

    class Meta:
        verbose_name = "sınav takvimi"
        verbose_name_plural = "sınav takvimleri"
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["semester", "round"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_examcalendar_sem_round_alive",
            ),
            models.CheckConstraint(
                condition=models.Q(start_date__lte=models.F("end_date")),
                name="ck_examcalendar_date_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_status_display()})"

    @property
    def is_draft(self) -> bool:
        return self.status == ExamCalendarStatus.DRAFT


class ExamCalendarEntry(BaseModel):
    """Takvim havuzu + yerleştirme birimi — (ders, seviye, tür) (ADR-0044).

    Havuzdayken `placed_date`/`period_no` boştur; ızgaraya yerleştirilince
    ikisi de dolar (CheckConstraint çifti). `is_butterfly=False` "Kelebek Değil"
    (kendi sınıfında/ders saatinde). `session` bağı slot→oturum üretiminde
    yazılır (SET_NULL — oturum silinirse slot yeniden üretilebilir). Katılımcı
    listesi anlık türetilir; burada KİŞİSEL VERİ YOK.
    """

    calendar = models.ForeignKey(
        ExamCalendar,
        on_delete=models.CASCADE,
        related_name="entries",
        verbose_name="takvim",
    )
    course = models.ForeignKey(
        "dersler.Course",
        on_delete=models.PROTECT,
        related_name="exam_calendar_entries",
        verbose_name="ders",
    )
    level = models.PositiveSmallIntegerField("seviye", help_text="Sınıf düzeyi (0=Hazırlık, 9-12).")
    exam_kind = models.CharField(
        "sınav türü", max_length=10, choices=ExamKind.choices, default=ExamKind.WRITTEN
    )
    is_butterfly = models.BooleanField(
        "kelebek", default=True, help_text="False = kendi sınıfında (Kelebek Değil)."
    )
    placed_date = models.DateField("yerleştirme tarihi", null=True, blank=True, db_index=True)
    period_no = models.PositiveSmallIntegerField(
        "ders saati", null=True, blank=True, help_text="Ders saati listesindeki saat no (B6)."
    )
    session = models.ForeignKey(
        ExamSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calendar_entries",
        verbose_name="üretilen oturum",
    )
    note = models.CharField("not", max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "sınav takvimi girdisi"
        verbose_name_plural = "sınav takvimi girdileri"
        indexes = [
            models.Index(fields=["calendar", "placed_date"], name="sinav_calentry_cal_date_idx")
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["calendar", "course", "level", "exam_kind"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_examcalentry_alive",
            ),
            # Yerleştirme çifti: tarih ve ders saati ya birlikte boş ya birlikte dolu.
            models.CheckConstraint(
                condition=(
                    models.Q(placed_date__isnull=True, period_no__isnull=True)
                    | models.Q(placed_date__isnull=False, period_no__isnull=False)
                ),
                name="ck_examcalentry_slot_pair",
            ),
        ]

    def __str__(self) -> str:
        return f"Takvim #{self.calendar_id} — ders {self.course_id} / {self.level}"


class ExamTrackItem(BaseModel):
    """Sınav süreç takip kalemi kataloğu — GLOBAL, düzenlenebilir.

    Excel 'Sınav Takip' sürecinin sistem karşılığı (KSD ilanı → soru+CA teslimi
    → basım → paketleme → uygulama → 'G' girişi → puan girişi → analiz raporu).
    Kişisel veri yok; silme yerine is_active=False (marks PROTECT ile bağlı).
    """

    name = models.CharField("kalem adı", max_length=160)
    order = models.PositiveSmallIntegerField("sıra", default=0)
    is_active = models.BooleanField("aktif", default=True)
    description = models.CharField("açıklama", max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "sınav süreç kalemi"
        verbose_name_plural = "sınav süreç kalemleri"
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_examtrackitem_name_alive",
            )
        ]

    def __str__(self) -> str:
        return self.name


class ExamTrackMark(BaseModel):
    """Takvim girdisi × süreç kalemi işareti (ADR-0044).

    'Yapılmadı' = kayıt yokluğu; işaret kaldırma soft-delete. `marked_by_name`
    ad-snapshot'tır (KS'de User yok — B17); varsayılanı yapılandırmadaki müdür
    adından servis doldurur.
    """

    entry = models.ForeignKey(
        ExamCalendarEntry,
        on_delete=models.CASCADE,
        related_name="track_marks",
        verbose_name="takvim girdisi",
    )
    item = models.ForeignKey(
        ExamTrackItem,
        on_delete=models.PROTECT,
        related_name="marks",
        verbose_name="kalem",
    )
    status = models.CharField("durum", max_length=16, choices=ExamTrackMarkStatus.choices)
    marked_by_name = models.CharField(
        "işaretleyen (ad-snapshot)", max_length=128, blank=True, default=""
    )
    marked_at = models.DateTimeField("işaret zamanı")
    note = models.CharField("not", max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "sınav süreç işareti"
        verbose_name_plural = "sınav süreç işaretleri"
        constraints = [
            models.UniqueConstraint(
                fields=["entry", "item"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_examtrackmark_alive",
            )
        ]

    def __str__(self) -> str:
        return f"Girdi #{self.entry_id} × {self.item_id}: {self.status}"


# ===========================================================================
# F7 — gözetmen görevlendirme (OYS T9b'den UYARLA; U2: elle atama, oto YOK)
# ===========================================================================


class ProctorRole(models.TextChoices):
    """Görev rolü — CHIEF (salon başkanı) OYS Tur 235'te kalktı: okul içi
    sınavda salona TEK öğretmen; devamsızlık ihtimali için salonsuz YEDEK."""

    PROCTOR = "PROCTOR", "Gözetmen"
    RESERVE = "RESERVE", "Yedek"


class ProctorAssignment(BaseModel):
    """Gözetmen görevlendirmesi — SNAPSHOT desenli (arşiv evrak sabitliği).

    KS uyarlaması: `teacher` OYS'deki core.User yerine okul.Personnel'e bağlanır
    (F27 anonimleştirmesinde koparılabilsin diye null/blank); `teacher_name`
    ŞİFRELİ ad-snapshot'tır (tasarım §5 U3 listesi — kaynak şifreliyken kopya
    düz kalamaz). Ada dayalı sıralama/teklik ORM'e yazılmaz (TB3) — teklik FK
    üstünden, sıralama bellekte (`build_assignment_context`).
    """

    session = models.ForeignKey(
        ExamSession,
        on_delete=models.CASCADE,
        related_name="proctor_assignments",
        verbose_name="oturum",
    )
    room = models.ForeignKey(
        ExamRoom,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="proctor_assignments",
        verbose_name="salon",
        help_text="YEDEK rolünde boş; gözetmende zorunlu (servis doğrular).",
    )
    teacher = models.ForeignKey(
        "okul.Personnel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="proctor_assignments",
        verbose_name="öğretmen",
        help_text="Anonimleştirilmiş arşivde boş (F27).",
    )
    teacher_name = EncryptedCharField("öğretmen adı (snapshot)", max_length=150)
    role = models.CharField(
        "rol", max_length=8, choices=ProctorRole.choices, default=ProctorRole.PROCTOR
    )
    acknowledged = models.BooleanField("tebellüğ edildi", default=False)
    acknowledged_at = models.DateTimeField("tebellüğ zamanı", null=True, blank=True)

    class Meta:
        verbose_name = "gözetmen görevlendirmesi"
        verbose_name_plural = "gözetmen görevlendirmeleri"
        ordering = ["room_id", "id"]
        indexes = [models.Index(fields=["session", "room"], name="sinav_proctor_sess_room_idx")]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "teacher"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_proctor_session_teacher_alive",
            ),
            # Salon başına TAM 1 canlı GÖZETMEN (yedekler room=NULL — kapsam dışı).
            models.UniqueConstraint(
                fields=["session", "room"],
                condition=models.Q(deleted_at__isnull=True, role="PROCTOR"),
                name="uq_proctor_session_room_proctor_alive",
            ),
        ]

    def __str__(self) -> str:
        return f"Oturum {self.session_id} — {self.get_role_display()} (salon {self.room_id})"


class ExemptionReason(models.TextChoices):
    """Muafiyet gerekçesi — YALNIZ kategori (KVKK md. 6; PlacementRule emsali)."""

    HEALTH = "HEALTH", "Sağlık"
    DUTY = "DUTY", "İdari görev"
    OTHER = "OTHER", "Diğer"


class ProctorExemption(BaseModel):
    """Gözetmenlik muafiyeti — kapsam oturum ya da kalıcı; gerekçe yalnız kategori.

    HEALTH kategorisi özel nitelikli veriye İŞARET eder — tanı/rapor serbest
    metni BİLİNÇLE YOKTUR (KVKK md. 6). Elle atamada bile muafiyet SERTTİR.
    """

    teacher = models.ForeignKey(
        "okul.Personnel",
        on_delete=models.PROTECT,
        related_name="exam_proctor_exemptions",
        verbose_name="öğretmen",
    )
    scope = models.CharField(
        "kapsam", max_length=10, choices=RuleScope.choices, default=RuleScope.PERMANENT
    )
    session = models.ForeignKey(
        ExamSession,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="proctor_exemptions",
        verbose_name="oturum",
        help_text="Yalnız SESSION kapsamında dolu.",
    )
    reason_category = models.CharField(
        "gerekçe kategorisi",
        max_length=10,
        choices=ExemptionReason.choices,
        default=ExemptionReason.OTHER,
    )

    class Meta:
        verbose_name = "gözetmenlik muafiyeti"
        verbose_name_plural = "gözetmenlik muafiyetleri"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["teacher"],
                condition=models.Q(deleted_at__isnull=True, session__isnull=True),
                name="uq_proctorexemption_permanent_alive",
            ),
            models.UniqueConstraint(
                fields=["teacher", "session"],
                condition=models.Q(deleted_at__isnull=True, session__isnull=False),
                name="uq_proctorexemption_session_alive",
            ),
        ]

    def __str__(self) -> str:
        return f"Muafiyet — personel {self.teacher_id} ({self.get_scope_display()})"
