"""`okul` DRF serializer'ları — doğrulama + normalize burada, yazma serviste.

Elle giriş, içe aktarmayla AYNI normalize edicilerden geçer (`apps.okul.normalize`):
şube harfi Türkçe büyük harfe çevrilir (`tr_upper` — 'ş' → 'Ş', 'i' → 'İ'; ASCII'ye
KATLANMAZ, 10/I ile 10/İ ayrı şubelerdir), seviye kümesi okul türünden (U4).
Hatalar Türkçedir (`{code, message, fields}` sözleşmesi).
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.okul import normalize, selectors
from apps.okul.models import (
    ClassSection,
    ClassSectionGroup,
    Personnel,
    SchoolConfig,
    SchoolTerm,
    SchoolYear,
    Student,
    SubjectDepartment,
)


def _validate_level(value: int) -> int:
    """Seviyeyi okul türünün geçerli kümesine karşı doğrular (U4 — sabit aralık yok)."""
    levels = selectors.grade_level_values()
    if value not in levels:
        etiketler = ", ".join("Hazırlık" if lvl == 0 else str(lvl) for lvl in levels)
        raise serializers.ValidationError(f"Sınıf şu seviyelerden biri olmalıdır: {etiketler}.")
    return value


class SchoolConfigSerializer(serializers.ModelSerializer[SchoolConfig]):
    """Kurum künyesi. `level_programs` seviye → çizelge program anahtarları (kademeli dönüşüm).

    Doğrulama: anahtar geçerli bir sınıf düzeyi (0, 9-12), değer bilinen
    program anahtarlarının listesi. Boş sözlük = varsayılan atama. Okulun
    seviye kümesi dışındaki seviye (ör. hazırlıksız okulda 0) reddedilmez —
    plan onu yok sayar; hazırlık sonradan açılırsa atama hazır durur.
    """

    level_programs = serializers.JSONField(required=False)
    # Ders saati ayarları: asıl doğrulama servistedir (`update_school_config`)
    # — aralık kuralı günlük saat sayısıyla birlikte değerlendirilir, tek alanı
    # tek başına doğrulayan serializer dalı ikisini ayrıştırırdı.
    exam_period_nos = serializers.JSONField(required=False)

    class Meta:
        model = SchoolConfig
        fields = [
            "school_name",
            "province",
            "district",
            "principal_name",
            "school_type",
            "has_prep_class",
            "level_programs",
            "daily_period_count",
            "exam_period_nos",
            "setup_completed",
        ]
        read_only_fields = ["setup_completed"]

    def validate_level_programs(self, value: Any) -> dict[str, list[str]]:
        from apps.dersler import catalog as catalog_mod
        from apps.dersler.models import VALID_COURSE_LEVELS

        if value in (None, ""):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Seviye atamaları sözlük olmalıdır: {'9': ['fen-lisesi-2025']}."
            )
        known = catalog_mod.load_programs()
        cleaned: dict[str, list[str]] = {}
        for raw_level, raw_keys in value.items():
            try:
                level = int(raw_level)
            except (TypeError, ValueError) as exc:
                raise serializers.ValidationError(
                    f"Seviye anahtarı sayısal olmalıdır: {raw_level!r}."
                ) from exc
            if level not in VALID_COURSE_LEVELS:
                raise serializers.ValidationError(
                    f"Geçersiz seviye: {level}. Geçerli düzeyler: Hazırlık (0), 9, 10, 11, 12."
                )
            if not isinstance(raw_keys, list):
                raise serializers.ValidationError(
                    f"{level}. seviye için program listesi bekleniyor."
                )
            keys: list[str] = []
            for key in raw_keys:
                if not isinstance(key, str) or key not in known:
                    raise serializers.ValidationError(f"Bilinmeyen çizelge programı: {key!r}.")
                if key not in keys:
                    keys.append(key)
            cleaned[str(level)] = keys
        return cleaned


class SchoolYearSerializer(serializers.ModelSerializer[SchoolYear]):
    class Meta:
        model = SchoolYear
        fields = ["id", "name", "start_date", "end_date", "is_active"]
        read_only_fields = ["is_active"]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_date": "Bitiş tarihi başlangıçtan sonra olmalıdır."}
            )
        return attrs


class SchoolTermSerializer(serializers.ModelSerializer[SchoolTerm]):
    name = serializers.CharField(read_only=True)

    class Meta:
        model = SchoolTerm
        fields = ["id", "school_year", "sequence", "name", "start_date", "end_date"]
        read_only_fields = fields


class SchoolTermConfigurationSerializer(serializers.Serializer[dict[str, Any]]):
    first_term_end = serializers.DateField()
    second_term_start = serializers.DateField()


class PersonnelSerializer(serializers.ModelSerializer[Personnel]):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Personnel
        fields = ["id", "first_name", "last_name", "title", "branch", "is_active", "full_name"]


class ClassSectionGroupSerializer(serializers.ModelSerializer[ClassSectionGroup]):
    """Şube kümesi (SAY/EA/DİL) — YALNIZ seçim kolaylığı etiketi.

    Teklik denetimi burada Türkçe mesajla yapılır; alan elle tanımlanır ki DRF
    modeldeki tek alanlı UniqueConstraint'ten ALAN düzeyinde bir UniqueValidator
    türetip İngilizce mesaj basmasın (SubjectDepartmentSerializer emsali).
    """

    name = serializers.CharField(max_length=60, validators=[])
    section_count = serializers.SerializerMethodField()

    class Meta:
        model = ClassSectionGroup
        validators: list[Any] = []
        fields = ["id", "name", "order", "section_count"]

    def get_section_count(self, obj: ClassSectionGroup) -> int:
        return int(obj.sections.count())

    def validate_name(self, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise serializers.ValidationError("Küme adı zorunludur.")
        return cleaned

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        instance = self.instance if isinstance(self.instance, ClassSectionGroup) else None
        name = attrs.get("name", getattr(instance, "name", ""))
        if name:
            duplicate = ClassSectionGroup.objects.filter(name=name)
            if instance is not None:
                duplicate = duplicate.exclude(pk=instance.pk)
            if duplicate.exists():
                raise serializers.ValidationError({"name": "Bu küme zaten kayıtlı."})
        return attrs


class SectionGroupAssignSerializer(serializers.Serializer[dict[str, Any]]):
    """Toplu küme ataması — asıl seçim maliyetini düşüren uç."""

    section_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)
    group = serializers.PrimaryKeyRelatedField(
        queryset=ClassSectionGroup.objects.all(), allow_null=True
    )


class ClassSectionSerializer(serializers.ModelSerializer[ClassSection]):
    school_year_name = serializers.CharField(source="school_year.name", read_only=True)
    class_label = serializers.CharField(read_only=True)
    group_name = serializers.SerializerMethodField()

    class Meta:
        model = ClassSection
        validators: list[Any] = []
        fields = [
            "id",
            "school_year",
            "school_year_name",
            "class_level",
            "class_section",
            "class_label",
            "group",
            "group_name",
        ]

    def get_group_name(self, obj: ClassSection) -> str:
        return obj.group.name if obj.group is not None else ""

    def validate_class_level(self, value: int) -> int:
        return _validate_level(value)

    def validate_class_section(self, value: str) -> str:
        normalized = normalize.tr_upper(value.strip())
        if not normalized:
            raise serializers.ValidationError("Şube zorunludur.")
        return normalized

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        instance = self.instance if isinstance(self.instance, ClassSection) else None
        year = attrs.get("school_year", getattr(instance, "school_year", None))
        level = attrs.get("class_level", getattr(instance, "class_level", None))
        section = attrs.get("class_section", getattr(instance, "class_section", ""))
        if year is not None and level is not None and section:
            duplicate = ClassSection.objects.filter(
                school_year=year,
                class_level=level,
                class_section=section,
            )
            if instance is not None:
                duplicate = duplicate.exclude(pk=instance.pk)
            if duplicate.exists():
                raise serializers.ValidationError(
                    {"class_section": "Bu ders yılı için şube zaten kayıtlı."}
                )
        return attrs


class SubjectDepartmentSerializer(serializers.ModelSerializer[SubjectDepartment]):
    """Zümre — okul zümre başkanları kurulu üyeliği + başkan seçimi.

    Başkan adı şifreli alandan türetilir (`Personnel.full_name`); yazma tarafı
    yalnız `head` pk'sini alır. Zümre adı BÜYÜK HARFE ÇEVRİLMEZ (`tr_upper` şube
    harfine özgüdür) — yalnız fazla boşluk katlanır.
    """

    # DRF, modeldeki tek alanlı UniqueConstraint'ten ALAN düzeyinde bir
    # UniqueValidator türetir; `Meta.validators = []` yalnız Meta düzeyindekini
    # (unique_together) siler. Alan burada elle tanımlanır ki teklik mesajı
    # depo üslubunda Türkçe olsun (`validate` içinde) — ham DRF çevirisi değil.
    name = serializers.CharField(max_length=80, validators=[])
    # `CharField(source="head.full_name", default="")` DEĞİL: `head` boşken DRF
    # `get_default()`e düşer ve partial (PATCH) serializer'da SkipField fırlatır —
    # anahtar yanıttan tamamen kaybolurdu. Method alanı her durumda dizge döner.
    head_name = serializers.SerializerMethodField()

    class Meta:
        model = SubjectDepartment
        validators: list[Any] = []
        fields = ["id", "name", "head", "head_name", "is_board_member"]

    def get_head_name(self, obj: SubjectDepartment) -> str:
        return obj.head.full_name if obj.head is not None else ""

    def validate_name(self, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise serializers.ValidationError("Zümre adı zorunludur.")
        return cleaned

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        instance = self.instance if isinstance(self.instance, SubjectDepartment) else None
        name = attrs.get("name", getattr(instance, "name", ""))
        if name:
            duplicate = SubjectDepartment.objects.filter(name=name)
            if instance is not None:
                duplicate = duplicate.exclude(pk=instance.pk)
            if duplicate.exists():
                raise serializers.ValidationError({"name": "Bu zümre zaten kayıtlı."})
        return attrs


class StudentSerializer(serializers.ModelSerializer[Student]):
    full_name = serializers.CharField(read_only=True)
    class_label = serializers.CharField(read_only=True)

    class Meta:
        model = Student
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "student_number",
            "class_level",
            "class_section",
            "class_label",
            "status",
        ]

    def validate_class_level(self, value: int | None) -> int | None:
        if value is None:
            return None
        return _validate_level(value)

    def validate_class_section(self, value: str) -> str:
        # İçe aktarmayla aynı katlama: Türkçe büyük harf ('ş' → 'Ş', 'i' → 'İ').
        if not value.strip():
            return ""
        return normalize.tr_upper(value.strip())


class ImportRequestSerializer(serializers.Serializer[dict[str, Any]]):
    """İçe aktarma girdisi: Excel dosyası (e-Okul .xls / şablon .xlsx) VEYA pano metni."""

    file = serializers.FileField(required=False)
    text = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        has_file = attrs.get("file") is not None
        has_text = bool(str(attrs.get("text", "")).strip())
        if has_file == has_text:  # ikisi birden veya hiçbiri
            raise serializers.ValidationError(
                "Dosya (file) veya yapıştırılan metin (text) alanlarından tam olarak biri gerekli."
            )
        return attrs
