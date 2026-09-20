"""Zümre kataloğu yazma işlemleri (SubjectDepartment).

İnce servis katmanı — doğrulama serializer'da (ad boşluk katlaması, teklik),
yazma burada (`sections.py` emsali). İmza bloğu seçimi sinav tarafındadır
(`ExamCalendar.signatory_departments`); burada yalnız katalog tutulur.

BRANŞTAN ÜRETİM (20.09.2026, kullanıcı isteği): zümreler e-Okul öğretmen
listesindeki branş bilgisinden üretilir; sonradan ekleme/çıkarma serbesttir.
- Eşleşme YAZIMA değil ANAHTARA göredir (`branch_key`): "COĞRAFYA", "Coğrafya"
  ve "coğrafya " aynı branştır; "Ahlâk" ile "Ahlak" da.
- Üretim İDEMPOTENTTİR: branşı zaten bir zümrede olan aday atlanır; adı branşla
  aynı olan zümre yeniden yaratılmaz, branş ona BAĞLANIR (başkan seçicisi elle
  açılmış eski zümrelerde de süzülsün; ad tekliği de çiğnenmez).
- Kendiliğinden üretim YALNIZ katalog BOŞKEN olur (öğretmen aktarımının commit
  ucu çağırır — `generate_if_catalog_empty`). Katalogda tek zümre bile varsa
  idarecinin elle kurduğu düzen sayılır ve dokunulmaz: kaldırılan bir zümre
  sonraki aktarımda sessizce geri gelmez. O durumda üretim Ayarlar → Zümreler'deki
  düğmeyle, adaylar görülerek yapılır.
- Aday branşlar AKTİF öğretmenlerden okunur; branşı boş kayıt (memur, hizmetli)
  aday üretmez.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.okul import normalize
from apps.okul.excel_ogrenci import normalize_header
from apps.okul.models import Personnel, SubjectDepartment
from shared.text import tr_lower, tr_title

#: Şapkalı harfler anahtar üretiminde düz harfe iner ('Ahlâk' = 'Ahlak').
_CIRCUMFLEX = str.maketrans("ÂâÎîÛû", "AaIiUu")

#: Bir zümreye bağlanabilecek en çok branş (bozuk gövdeye karşı üst sınır).
MAX_BRANCHES = 20

STATUS_NEW = "NEW"
STATUS_LINKABLE = "LINKABLE"
STATUS_COVERED = "COVERED"


def branch_key(value: object) -> str:
    """Branş eşleştirme anahtarı: harf büyüklüğü, Türkçe harf, şapka ve boşluk farkını katlar."""
    return normalize_header(str(value or "").translate(_CIRCUMFLEX))


def clean_branches(values: object) -> list[str]:
    """Branş listesini doğrular: metin listesi, boşluk katlanır, ANAHTARA göre tekilleşir."""
    if values is None:
        return []
    if not isinstance(values, list | tuple):
        raise ValidationError("Branşlar liste olmalıdır.")
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise ValidationError("Branş adı metin olmalıdır.")
        text = " ".join(value.split())
        key = branch_key(text)
        if not key or key in seen:
            continue
        if len(text) > 64:
            raise ValidationError("Branş adı en çok 64 karakter olabilir.")
        seen.add(key)
        cleaned.append(text)
    if len(cleaned) > MAX_BRANCHES:
        raise ValidationError(f"Bir zümreye en çok {MAX_BRANCHES} branş bağlanabilir.")
    return cleaned


def department_branch_keys(department: SubjectDepartment) -> list[str]:
    """Zümrenin branş anahtarları (bozuk/eski kayıt toleranslı)."""
    raw = department.branches if isinstance(department.branches, list) else []
    return [key for key in (branch_key(value) for value in raw) if key]


def _ensure_branches_free(branches: list[str], *, exclude_pk: int | None) -> None:
    """Bir branş EN ÇOK bir zümrededir — başkan adayı iki zümrede birden listelenmesin."""
    wanted = {branch_key(value): value for value in branches}
    if not wanted:
        return
    for other in SubjectDepartment.objects.all():
        if other.pk == exclude_pk:
            continue
        clash = [wanted[key] for key in department_branch_keys(other) if key in wanted]
        if clash:
            raise ValidationError(
                {
                    "branches": (
                        f"“{clash[0]}” branşı “{other.name}” zümresinde kayıtlı; "
                        "bir branş yalnız bir zümrede olabilir."
                    )
                }
            )


@transaction.atomic
def create_subject_department(**fields: Any) -> SubjectDepartment:
    if "branches" in fields:
        fields["branches"] = clean_branches(fields["branches"])
        _ensure_branches_free(fields["branches"], exclude_pk=None)
    department: SubjectDepartment = SubjectDepartment.objects.create(**fields)
    return department


@transaction.atomic
def update_subject_department(department: SubjectDepartment, **fields: Any) -> SubjectDepartment:
    """Yalnız DEĞİŞEN alanları yazar; `updated_at` elle eklenir (auto_now tuzağı)."""
    if "branches" in fields:
        fields["branches"] = clean_branches(fields["branches"])
        _ensure_branches_free(fields["branches"], exclude_pk=department.pk)
    changed = [name for name, value in fields.items() if getattr(department, name) != value]
    if changed:
        for name in changed:
            setattr(department, name, fields[name])
        department.save(update_fields=[*changed, "updated_at"])
    return department


@transaction.atomic
def delete_subject_department(department: SubjectDepartment) -> None:
    department.delete()  # soft delete (BaseModel)


# ---------------------------------------------------------------------------
# Branştan üretim
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BranchCandidate:
    """Öğretmen sicilindeki bir branş ve zümre kataloğundaki karşılığı.

    `status`: NEW → zümresi yok, üretilebilir · LINKABLE → aynı adlı zümre var ama
    bu branş ona bağlı değil; üretim yeni zümre açmaz, branşı ona EKLER ·
    COVERED → branş zaten bir zümrede.
    """

    key: str
    name: str
    teacher_count: int
    status: str
    department_id: int | None
    department_name: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _display_name(spellings: Counter[str]) -> str:
    """Branşın zümre adı olacak yazımı.

    Önce karışık harfli en sık yazım ('Coğrafya'); yazımların hepsi tamamen
    büyük ya da tamamen küçükse başlık biçimine çevrilir ('TÜRK DİLİ VE
    EDEBİYATI' → 'Türk Dili ve Edebiyatı') — ad takvimin imza bloğuna
    "<ad> Zümre Başkanı" diye basılır.
    """
    ordered = [text for text, _count in spellings.most_common()]
    mixed = [
        text for text in ordered if text != normalize.tr_upper(text) and text != tr_lower(text)
    ]
    # Tamamı büyük ya da tamamı küçük yazım başlık biçimine çevrilir.
    return mixed[0] if mixed else tr_title(ordered[0])


def branch_candidates() -> list[BranchCandidate]:
    """AKTİF öğretmenlerin branşları + katalogdaki durumları (Türk alfabesi sırasıyla)."""
    spellings: dict[str, Counter[str]] = {}
    for branch in Personnel.objects.filter(is_active=True).values_list("branch", flat=True):
        text = " ".join(str(branch or "").split())
        key = branch_key(text)
        if key:
            spellings.setdefault(key, Counter())[text] += 1

    departments = list(SubjectDepartment.objects.all().order_by("pk"))
    covered: dict[str, SubjectDepartment] = {}
    for department in departments:
        for key in department_branch_keys(department):
            covered.setdefault(key, department)
    # Adı branşla aynı zümre yeniden yaratılmaz, BAĞLANIR (aynı adda ilk kayıt kazanır).
    linkable = {branch_key(d.name): d for d in reversed(departments)}

    candidates: list[BranchCandidate] = []
    for key, counter in spellings.items():
        owner = covered.get(key)
        target = owner or linkable.get(key)
        candidates.append(
            BranchCandidate(
                key=key,
                name=_display_name(counter),
                teacher_count=sum(counter.values()),
                status=(
                    STATUS_COVERED
                    if owner is not None
                    else STATUS_LINKABLE
                    if target is not None
                    else STATUS_NEW
                ),
                department_id=target.pk if target is not None else None,
                department_name=target.name if target is not None else "",
            )
        )
    candidates.sort(key=lambda c: normalize.tr_sort_key(c.name))
    return candidates


@transaction.atomic
def generate_from_branches(keys: list[str] | None = None) -> dict[str, list[str]]:
    """Branşlardan zümre üretir; `keys` verilirse YALNIZ o branşlar (anahtar) işlenir.

    Dönüş zümre ADLARIDIR: `created` yeni açılanlar, `linked` aynı adlı olup
    branşı bağlananlar, `skipped` branşı zaten bir zümrede olanlar. İdempotent.
    """
    wanted = None if keys is None else {branch_key(key) for key in keys}
    result: dict[str, list[str]] = {"created": [], "linked": [], "skipped": []}
    for candidate in branch_candidates():
        if wanted is not None and candidate.key not in wanted:
            continue
        if candidate.status == STATUS_COVERED:
            result["skipped"].append(candidate.department_name)
            continue
        if candidate.status == STATUS_LINKABLE and candidate.department_id is not None:
            department = SubjectDepartment.objects.get(pk=candidate.department_id)
            existing = department.branches if isinstance(department.branches, list) else []
            update_subject_department(department, branches=[*existing, candidate.name])
            result["linked"].append(department.name)
            continue
        created = create_subject_department(name=candidate.name, branches=[candidate.name])
        result["created"].append(created.name)
    return result


def generate_if_catalog_empty() -> dict[str, list[str]] | None:
    """Katalog BOŞSA branşlardan zümre üretir; değilse `None` (elle kurulan düzene dokunulmaz).

    Öğretmen aktarımının commit ucu çağırır: ilk kurulumda öğretmen listesi
    yüklenince zümreler hazır gelir. Katalogda zümre varken sessizce bir şey
    eklemek, idarecinin bilerek kaldırdığı zümreyi geri getirirdi.
    """
    if SubjectDepartment.objects.exists():
        return None
    return generate_from_branches()
