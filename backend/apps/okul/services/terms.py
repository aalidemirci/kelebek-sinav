"""Ders yılı dönemlerinin kurulması ve tarih çözümlemesi."""

from __future__ import annotations

from datetime import date

from django.db import transaction

from apps.okul.models import SchoolTerm, SchoolYear


def validate_term_dates(
    school_year: SchoolYear,
    *,
    first_end: date,
    second_start: date,
) -> None:
    if first_end < school_year.start_date:
        raise ValueError("1. dönem bitişi ders yılı başlangıcından önce olamaz.")
    if second_start > school_year.end_date:
        raise ValueError("2. dönem başlangıcı ders yılı bitişinden sonra olamaz.")
    if second_start <= first_end:
        raise ValueError("2. dönem, 1. dönem bittikten sonra başlamalıdır.")


@transaction.atomic
def configure_terms(
    school_year: SchoolYear,
    *,
    first_end: date,
    second_start: date,
) -> list[SchoolTerm]:
    """İki dönemi tek işlemde oluşturur veya günceller."""

    validate_term_dates(school_year, first_end=first_end, second_start=second_start)
    values = (
        (1, school_year.start_date, first_end),
        (2, second_start, school_year.end_date),
    )
    terms: list[SchoolTerm] = []
    for sequence, start_date, end_date in values:
        term, _ = SchoolTerm.objects.update_or_create(
            school_year=school_year,
            sequence=sequence,
            defaults={"start_date": start_date, "end_date": end_date},
        )
        terms.append(term)
    return terms


def term_for_date(school_year: SchoolYear, value: date) -> SchoolTerm | None:
    return SchoolTerm.objects.filter(
        school_year=school_year,
        start_date__lte=value,
        end_date__gte=value,
    ).first()


def require_term_for_date(school_year: SchoolYear, value: date) -> SchoolTerm:
    term = term_for_date(school_year, value)
    if term is None:
        if not SchoolTerm.objects.filter(school_year=school_year).exists():
            raise ValueError(
                "Bu ders yılının dönem tarihleri tanımlanmamış. "
                "Önce ders yılı dönemlerini yapılandırın."
            )
        raise ValueError("İşlem tarihi ders yılının bir dönemine denk gelmiyor.")
    return term
