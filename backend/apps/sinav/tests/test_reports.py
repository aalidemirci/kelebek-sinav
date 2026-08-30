"""F4 evrak testleri — R1-R5 + R7-R9 + boş plan + tümü-ZIP (WeasyPrint + pypdf).

Kapı (tasarım §12 F4):
- her raporda TR karakter duman testi (DD `test_documents.py` emsali —
  pypdf metin çıkarma; dar kapsama fontta Ğ/Ş/İ sessizce düşer),
- `text-transform` tarama testi (WeasyPrint TR i→I tuzağı — CLAUDE.md §2),
- `|unlocalize` denetimi (TR locale ondalığı virgülle basar; CSS genişliği
  yutulur — OYS F25/T244 bulgusu).
Durum kapıları (taslak reddi, arşivden yeniden basım) ve R8 seed sözleşmesi
(CLAUDE.md §3) burada sabitlenir.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from openpyxl import load_workbook
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.okul.models import SchoolConfig
from apps.sinav import reports, services
from apps.sinav.models import ExamSession, ExamSessionRoom
from apps.sinav.tests.oturum_yardim import dagitilmis_oturum, oturum, salon

pytestmark = pytest.mark.django_db

#: DD emsali duman metni — Türkçe glifler kayıpsız çıkmalı.
TURKCE_DUMAN = "ĞÜŞİÖÇ ığüşiöç"
OKUL_ADI = f"{TURKCE_DUMAN} Anadolu Lisesi"

#: PDF üreten oturum raporları (r5 Excel, r6 F7'de).
PDF_CODES = ("r1", "r2", "r2k", "r3", "r4", "r7", "r8", "r9")

SESSIONS_URL = "/api/v1/exam-sessions/"
ROOMS_URL = "/api/v1/exam-rooms/"


def _pdf_text(pdf_bytes: bytes) -> str:
    """PDF gövde metni (DD `_pdf_text` deseni)."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _okul() -> None:
    """Rapor başlığına Türkçe duman metnini okul adı üzerinden enjekte eder."""
    SchoolConfig.objects.create(pk=SchoolConfig.SINGLETON_PK, school_name=OKUL_ADI)


def _evrak_oturumu(**kwargs: Any) -> ExamSession:
    """Okul yapılandırması + dağıtılmış oturum (evrak üretimine hazır)."""
    _okul()
    return dagitilmis_oturum(**kwargs)


# ===========================================================================
# TR karakter duman testi — her raporda (F4 kapısı)
# ===========================================================================


@pytest.mark.parametrize("code", PDF_CODES)
def test_pdf_raporlarda_turkce_duman(code: str) -> None:
    session = _evrak_oturumu()
    rf = services.render_session_report(session, code)

    _title, stem = reports.REPORT_TITLES[code]
    assert rf.filename == f"{stem}_oturum_{session.pk}.pdf"
    assert rf.content_type == "application/pdf"
    assert rf.content.startswith(b"%PDF")

    text = _pdf_text(rf.content)
    # DD deseni: boşluk hariç HARF HARF (extract_text satır sonu ekleyebilir).
    eksik = [harf for harf in TURKCE_DUMAN if harf != " " and harf not in text]
    assert not eksik, f"{code} çıktısında Türkçe glif kaybı: {eksik}"


def test_bos_salon_plani_turkce_duman() -> None:
    _okul()
    s = salon("Şölen İçi Derslik")  # salon adı da Türkçe glif taşır
    rf = services.render_room_layout_pdf(s)

    assert rf.filename == f"salon_yerlesim_plani_{s.pk}.pdf"
    assert rf.content.startswith(b"%PDF")
    text = _pdf_text(rf.content)
    eksik = [harf for harf in TURKCE_DUMAN if harf != " " and harf not in text]
    assert not eksik, f"Boş plan çıktısında Türkçe glif kaybı: {eksik}"
    assert "Şölen İçi Derslik" in text


def test_r5_excel_cizelge_turkce_duman() -> None:
    session = _evrak_oturumu()
    rf = services.render_session_report(session, "r5")

    assert rf.filename == f"r5_dagitim_cizelgesi_oturum_{session.pk}.xlsx"
    assert rf.content_type == ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    wb = load_workbook(io.BytesIO(rf.content))
    ws = wb["Dagitim"]
    assert ws.freeze_panes == "A5"
    baslik = str(ws["A1"].value)
    assert OKUL_ADI in baslik and "TOPLU DAĞITIM ÇİZELGESİ" in baslik
    kolonlar = tuple(ws.cell(row=4, column=c).value for c in range(1, 8))
    assert kolonlar == ("Okul No", "Ad Soyad", "Şube", "Ders", "Salon", "Koltuk No", "Durum")
    # 2 seviye × 3 öğrenci = 6 veri satırı (5. satırdan itibaren).
    assert ws.max_row == 4 + 6


# ===========================================================================
# R8 sözleşmesi — seed basılır (CLAUDE.md §3)
# ===========================================================================


def test_r8_seed_ve_ders_etiketi_basilir() -> None:
    session = _evrak_oturumu(seed=987654)
    text = _pdf_text(services.render_session_report(session, "r8").content)
    assert "987654" in text, "R8 dağıtım seed'ini basmalı (aynı seed → aynı dağıtım kanıtı)"
    # Çakışma grubu anahtarı ham değil, ders adlı etiketle görünmeli.
    assert "Coğrafya" in text


# ===========================================================================
# Tümü-ZIP
# ===========================================================================


def test_zip_tum_evrak() -> None:
    session = _evrak_oturumu()
    rf = services.render_session_reports_zip(session)

    assert rf.filename == f"sinav_evraki_oturum_{session.pk}.zip"
    assert rf.content_type == "application/zip"
    with zipfile.ZipFile(io.BytesIO(rf.content)) as zf:
        adlar = sorted(zf.namelist())
    beklenen = sorted(
        f"{reports.REPORT_TITLES[code][1]}_oturum_{session.pk}"
        + (".xlsx" if code == "r5" else ".pdf")
        for code in services.REPORT_CODES
        if code != "r6"  # görevlendirme modeli F7'de — r6 pakete girmez
    )
    assert adlar == beklenen


# ===========================================================================
# Durum kapıları + hata yolları
# ===========================================================================


def test_taslak_oturumda_evrak_reddedilir() -> None:
    _okul()
    draft = oturum(name="Taslak Oturum")
    with pytest.raises(ValidationError, match="Önce dağıtım"):
        services.render_session_report(draft, "r1")


def test_arsivden_yeniden_basim_acik() -> None:
    session = _evrak_oturumu()
    session = services.approve_session(session, approved_by_name="Örnek MÜDÜR")
    session = services.archive_session(session)
    rf = services.render_session_report(session, "r1")
    assert rf.content.startswith(b"%PDF")
    zip_rf = services.render_session_reports_zip(session)
    assert zip_rf.content_type == "application/zip"


def test_bilinmeyen_rapor_kodu() -> None:
    session = _evrak_oturumu()
    with pytest.raises(ValidationError, match="Bilinmeyen rapor kodu"):
        services.render_session_report(session, "r99")


def test_r6_f4te_uretilmez() -> None:
    kapali = _evrak_oturumu()
    with pytest.raises(ValidationError, match="kapalı"):
        services.render_session_report(kapali, "r6")

    # Gözetmen ayarı açık ama görevlendirme modeli F7'de — guard durumdan
    # hemen sonra çalıştığından yerleşimsiz DAĞITILDI kabuğu yeterli.
    acik = oturum(name="Gözetmenli Oturum", proctors_enabled=True)
    acik.status = kapali.status
    acik.save(update_fields=["status"])
    with pytest.raises(ValidationError, match="Görevlendirme yapılmamış"):
        services.render_session_report(acik, "r6")


def test_salon_filtresi() -> None:
    session = _evrak_oturumu(rooms=2, per_level=6)
    oturum_salonlari = list(
        ExamSessionRoom.objects.filter(session=session).select_related("room").order_by("order")
    )
    ilk = oturum_salonlari[0].room

    text = _pdf_text(services.render_session_report(session, "r1", room_id=ilk.pk).content)
    assert ilk.name in text
    digerleri = [sr.room.name for sr in oturum_salonlari[1:]]
    assert all(ad not in text for ad in digerleri)

    with pytest.raises(ValidationError, match="salon bazlı"):
        services.render_session_report(session, "r4", room_id=ilk.pk)
    with pytest.raises(ValidationError, match="tanımlı değil"):
        services.render_session_report(session, "r1", room_id=999999)


# ===========================================================================
# API uçları
# ===========================================================================


def test_api_rapor_indirme() -> None:
    session = _evrak_oturumu()
    client = APIClient()

    resp = client.get(f"{SESSIONS_URL}{session.pk}/reports/r1/")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert f'filename="r1_oturma_plani_oturum_{session.pk}.pdf"' in resp["Content-Disposition"]
    assert resp.content.startswith(b"%PDF")

    resp = client.get(f"{SESSIONS_URL}{session.pk}/reports/zip/")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/zip"

    resp = client.get(f"{SESSIONS_URL}{session.pk}/reports/r99/")
    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"

    # Taslakta Türkçe 400 (servis kapısı uca yansır).
    draft = oturum(name="Taslak Oturum")
    resp = client.get(f"{SESSIONS_URL}{draft.pk}/reports/r1/")
    assert resp.status_code == 400


def test_api_bos_salon_plani() -> None:
    _okul()
    s = salon("D-101")
    resp = APIClient().get(f"{ROOMS_URL}{s.pk}/layout-pdf/")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert f'filename="salon_yerlesim_plani_{s.pk}.pdf"' in resp["Content-Disposition"]


# ===========================================================================
# Şablon tarama kapıları (F4) — dosya sistemi denetimleri
# ===========================================================================

_TEMPLATES_DIR = Path(settings.BASE_DIR) / "templates"


#: Yorum blokları taramadan düşülür — yasak hatırlatma metinleri serbest,
#: aranan GERÇEK CSS bildirimidir.
_YORUM_KALIBI = re.compile(
    r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}|<!--.*?-->|/\*.*?\*/", re.DOTALL
)


def test_sablonlarda_text_transform_yasak() -> None:
    """`text-transform:` bildirimi YASAK — WeasyPrint TR i→I basar (CLAUDE.md §2)."""
    ihlaller: list[str] = []
    for dosya in sorted(_TEMPLATES_DIR.rglob("*")):
        if dosya.suffix not in (".html", ".css"):
            continue
        icerik = _YORUM_KALIBI.sub("", dosya.read_text(encoding="utf-8"))
        if re.search(r"text-transform\s*:", icerik):
            ihlaller.append(str(dosya.relative_to(_TEMPLATES_DIR)))
    assert not ihlaller, f"text-transform bildirimi bulunan şablonlar: {ihlaller}"


def test_unlocalize_denetimi() -> None:
    """CSS'e giren ondalıklı değişkenler `|unlocalize` taşımalı (F25/T244).

    TR locale `25.0`'ı `25,0` basar; `width: 25,0%` sessizce yutulur ve
    kroki tablosu çöker. Kural: `pct`/`percent` adlı her şablon değişkeni
    unlocalize'lı olmalı; bilinen üç kullanım da yerinde sabitlenir.
    """
    for dosya in sorted(_TEMPLATES_DIR.rglob("*.html")):
        icerik = dosya.read_text(encoding="utf-8")
        for degisken in re.findall(r"\{\{[^}]*\}\}", icerik):
            if ("pct" in degisken or "percent" in degisken) and "|unlocalize" not in degisken:
                pytest.fail(f"{dosya.name}: unlocalize'sız ondalık değişken: {degisken}")

    reports_dir = _TEMPLATES_DIR / "sinav" / "reports"
    assert "col_width_pct|unlocalize" in (reports_dir / "r1_kroki.html").read_text("utf-8")
    assert "col_width_pct|unlocalize" in (reports_dir / "room_layout.html").read_text("utf-8")
    assert "percent|unlocalize" in (reports_dir / "r8_validation.html").read_text("utf-8")


def test_design_css_ayni_kaldi() -> None:
    """`_design.css` içine Django etiketi yazılamaz (kendini include — OYS Tur 238)."""
    icerik = (_TEMPLATES_DIR / "print" / "_design.css").read_text(encoding="utf-8")
    assert "{%" not in icerik and "{{" not in icerik
    assert "--pr-ink" in icerik  # token seti yerinde


def test_sube_sirasi_turk_alfabesine_gore() -> None:
    """R2k/R4 şube sayfaları Türk alfabesi sırasında dizilir (kod noktası DEĞİL).

    Şube harfi artık ASCII'ye katlanmadığı için (gerçek e-Okul verisinde hem
    10/I hem 10/İ şubesi var), ham `str` karşılaştırması Ç/Ğ/İ/Ö/Ş/Ü'yü 'Z'den
    sonraya atıyordu: 10/Ç ve 10/İ evrakın sonuna düşer, 10/I ile 10/İ iki uca
    ayrılırdı.
    """
    etiketler = ["10/Z", "10/İ", "10/I", "10/Ç", "10/C", "9/B", "9/A", "11/A"]
    assert sorted(etiketler, key=reports.class_label_sort_key) == [
        "9/A",
        "9/B",
        "10/C",
        "10/Ç",
        "10/I",
        "10/İ",
        "10/Z",
        "11/A",
    ]


def test_sube_sirasi_seviye_sayisal_kalir() -> None:
    """Seviye sıralaması alfabetik DEĞİL sayısaldır (9 < 10 < 11) — davranış korundu."""
    assert sorted(["10/A", "9/A", "11/A"], key=reports.class_label_sort_key) == [
        "9/A",
        "10/A",
        "11/A",
    ]
    # Sayısal olmayan başlık (Hazırlık) daima sona düşer.
    assert sorted(["Hazırlık/A", "9/A"], key=reports.class_label_sort_key) == [
        "9/A",
        "Hazırlık/A",
    ]
