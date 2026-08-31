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
    class Meta:
        model = SchoolConfig
        fields = [
            "school_name",
            "province",
            "district",
            "principal_name",
            "school_type",
            "has_prep_class",
            "setup_completed",
        ]
        read_only_fields = ["setup_completed"]


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


class ClassSectionSerializer(serializers.ModelSerializer[ClassSection]):
    school_year_name = serializers.CharField(source="school_year.name", read_only=True)
    class_label = serializers.CharField(read_only=True)

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
        ]

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
