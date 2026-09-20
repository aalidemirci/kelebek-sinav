"""Kız/erkek ayrışması — servis düzeyi (20.09.2026 kullanıcı isteği).

Motor/doğrulayıcı birimi `test_engine.py`de, çıktının bit bit kilidi
`test_altin_kayit.py`de. Burada UÇTAN UCA sözleşme sınanır: anahtarı servis
üretir, kip oturumdan gelir, snapshot yazılır, kural KAPALIYKEN hiçbir şey
değişmez ve kullanıcı kararları (K2-K6) korunur.

KVKK: bütün adlar ve numaralar uydurmadır; testler cinsiyeti KOD üzerinden
kurar (fixture dosyası yok).
"""

from __future__ import annotations

import io

import pytest
from django.core.exceptions import ValidationError
from pypdf import PdfReader

from apps.okul.models import SchoolConfig, SeparationMode, Student
from apps.sinav import services
from apps.sinav.models import (
    ExamSession,
    LayoutMode,
    ParticipantType,
    SeatAssignment,
)
from apps.sinav.tests.oturum_yardim import ders, oturum, salon, sube

pytestmark = pytest.mark.django_db


def _cinsiyet_ata(desen: str = "KE") -> None:
    """Aktif öğrencilere sırayla cinsiyet yazar ("KE" → bir kız, bir erkek)."""
    for i, ogrenci in enumerate(Student.objects.order_by("student_number")):
        ogrenci.gender = desen[i % len(desen)]
        ogrenci.save(update_fields=["gender"])


def _oturum(
    *,
    separation: str = SeparationMode.NONE,
    rooms: int = 1,
    per_level: int = 4,
    layout_mode: str = LayoutMode.BUTTERFLY,
) -> ExamSession:
    """İki seviyeli (iki çakışma grubu) taslak oturum + salonlar."""
    sube(9, "A", students=per_level, start_no=101)
    sube(10, "A", students=per_level, start_no=201)
    course = ders("Coğrafya", levels=[9, 10])
    session = oturum(separation_mode=separation, layout_mode=layout_mode)
    for level in (9, 10):
        services.add_session_course(
            session, course_id=course.pk, participant_type=ParticipantType.LEVEL, level=level
        )
    salonlar = [salon(f"D-20{i}") for i in range(1, rooms + 1)]
    services.set_session_rooms(session, [{"room_id": s.pk} for s in salonlar])
    return session


def _sira_anahtarlari(session: ExamSession) -> list[set[str]]:
    """Her sıradaki (desk) ayrışma anahtarları — karışık sıra arıyoruz."""
    siralar: dict[tuple[int, int, int], set[str]] = {}
    for a in SeatAssignment.objects.filter(session=session):
        siralar.setdefault((a.room_id, a.desk_row, a.desk_col), set()).add(a.separation_key)
    return list(siralar.values())


# ===========================================================================
# Varsayılan KAPALI — kural açılmadan hiçbir şey değişmez
# ===========================================================================


def test_varsayilan_kapali_cinsiyet_hic_okunmaz() -> None:
    """Kural kapalıyken anahtar üretilmez: snapshot boş, rapor temiz."""
    session = _oturum()
    _cinsiyet_ata()

    session, result, report = services.distribute_session(session, seed=42)

    assert report.is_valid, report.hard_violations
    assert {a.separation_key for a in SeatAssignment.objects.filter(session=session)} == {""}
    assert session.distribution_params["separation_mode"] == SeparationMode.NONE
    assert not any("cinsiyet" in w for w in result.warnings)


def test_okul_varsayilani_yeni_oturuma_gecer() -> None:
    """K2: ihtiyacı olan okul bir kez ayarlar, her oturumda yeniden seçmez."""
    SchoolConfig.objects.create(
        pk=SchoolConfig.SINGLETON_PK, default_separation_mode=SeparationMode.DESK
    )
    yeni = oturum(name="Varsayılandan Doğan")
    assert yeni.separation_mode == SeparationMode.DESK

    # Açıkça verilen değer varsayılanı EZER (oturum bazlı seçim korunur).
    ozel = oturum(name="Elle Kapatılan", separation_mode=SeparationMode.NONE)
    assert ozel.separation_mode == SeparationMode.NONE


# ===========================================================================
# Aynı sıraya oturtma (DESK)
# ===========================================================================


def test_ayni_siraya_oturtma_karisik_sira_birakmaz() -> None:
    session = _oturum(separation=SeparationMode.DESK, per_level=4)
    _cinsiyet_ata()

    session, _result, report = services.distribute_session(session, seed=42)

    assert report.is_valid, report.hard_violations
    assert all(len(anahtarlar) == 1 for anahtarlar in _sira_anahtarlari(session))
    # Snapshot yazıldı: arşiv yeniden doğrulaması canlı veriye bağlı değil.
    assert {a.separation_key for a in SeatAssignment.objects.filter(session=session)} == {"K", "E"}
    assert session.distribution_params["separation_mode"] == SeparationMode.DESK


def test_snapshot_sonradan_degisen_cinsiyetten_etkilenmez() -> None:
    """Dağıtımdan sonra düzeltilen cinsiyet basılmış evrakı geriye dönük bozmaz."""
    session = _oturum(separation=SeparationMode.DESK)
    _cinsiyet_ata()
    session, _result, _report = services.distribute_session(session, seed=42)
    onceki = services.seating_report(session)
    assert onceki.is_valid

    Student.objects.all().update(gender="K")  # sicil düzeltildi
    assert services.seating_report(session).is_valid  # snapshot'a bakar, karışmaz


def test_cinsiyeti_bilinmeyen_ogrenci_dagitimi_durdurmaz() -> None:
    """K4: joker öğrenci kurala girmez; uyarı SAYIYLA çıkar, kimlik taşımaz."""
    session = _oturum(separation=SeparationMode.DESK)
    _cinsiyet_ata()
    eksik = Student.objects.order_by("student_number").first()
    assert eksik is not None
    Student.objects.filter(pk=eksik.pk).update(gender="")

    session, result, report = services.distribute_session(session, seed=42)

    assert report.is_valid, report.hard_violations
    uyari = next(w for w in result.warnings if "cinsiyet bilgisi yok" in w)
    assert "1 öğrencinin" in uyari
    assert eksik.student_number not in uyari and eksik.full_name not in uyari


def test_klasik_duzende_kural_uygulanmaz() -> None:
    """K6: kendi dersliğinde düzeninde ayar açık olsa da kip NONE'a düşer."""
    sinif = sube(9, "A", students=4, start_no=101)
    ders("Coğrafya", levels=[9])
    session = oturum(separation_mode=SeparationMode.DESK, layout_mode=LayoutMode.HOME_CLASSROOM)
    services.add_session_course(
        session,
        course_id=ders("Coğrafya", levels=[9]).pk,
        participant_type=ParticipantType.LEVEL,
        level=9,
    )
    salon("9/A Dersliği", linked_section_id=sinif.pk)
    _cinsiyet_ata()

    assert services.effective_separation_mode(session) == SeparationMode.NONE
    session, _result, report = services.distribute_session(session, seed=42)
    assert report.is_valid
    assert session.distribution_params["separation_mode"] == SeparationMode.NONE
    assert {a.separation_key for a in SeatAssignment.objects.filter(session=session)} == {""}


# ===========================================================================
# Ayrı salonlar (ROOM)
# ===========================================================================


def test_ayri_salonlar_salonlari_boler() -> None:
    session = _oturum(separation=SeparationMode.ROOM, rooms=2, per_level=4)
    _cinsiyet_ata()

    session, _result, report = services.distribute_session(session, seed=42)

    assert report.is_valid, report.hard_violations
    salon_anahtarlari: dict[int, set[str]] = {}
    for a in SeatAssignment.objects.filter(session=session):
        salon_anahtarlari.setdefault(a.room_id, set()).add(a.separation_key)
    assert len(salon_anahtarlari) == 2
    assert all(len(v) == 1 for v in salon_anahtarlari.values())


def test_ayri_salonlar_kapasite_yetmezse_gerekcesiyle_reddeder() -> None:
    """Tek salonda iki anahtar bölüşülemez: ret metni SAYIYLA konuşur, kimlikle değil."""
    session = _oturum(separation=SeparationMode.ROOM, rooms=1, per_level=4)
    _cinsiyet_ata()

    with pytest.raises(ValidationError) as excinfo:
        services.distribute_session(session, seed=42)

    mesaj = str(excinfo.value)
    assert "Ayrı salon kuralı uygulanamıyor" in mesaj
    assert "koltuk" in mesaj and "Salon ekleyin" in mesaj
    assert "id=" not in mesaj and "ROOM" not in mesaj


def test_ayri_salonlar_tek_anahtarda_olagan_dagitima_duser() -> None:
    """Okulun tamamı aynıysa (ör. kız lisesi) kip fiilen etkisizdir, ret YOK."""
    session = _oturum(separation=SeparationMode.ROOM, rooms=1, per_level=4)
    _cinsiyet_ata("K")

    session, _result, report = services.distribute_session(session, seed=42)
    assert report.is_valid, report.hard_violations


def test_ayni_seed_ayni_dagitim_kural_acikken_de() -> None:
    """Sözleşme korunur: alt seed'ler ana seed'den türetilir (ROOM kipi dâhil)."""
    session = _oturum(separation=SeparationMode.ROOM, rooms=2, per_level=4)
    _cinsiyet_ata()

    def yerlesim(s: ExamSession) -> list[tuple[str, int, int]]:
        return sorted(
            (a.student_number, a.room_id, a.seat_no)
            for a in SeatAssignment.objects.filter(session=s)
        )

    session, _r1, _rep1 = services.distribute_session(session, seed=7)
    ilk = yerlesim(session)
    session, _r2, _rep2 = services.distribute_session(session, seed=7)
    assert yerlesim(session) == ilk


# ===========================================================================
# Onay kapısı + evrak (K3 ve "hiçbir çıktıya basılmaz")
# ===========================================================================


def test_ihlalli_yerlesim_onaylanamaz() -> None:
    """K3 SERT: kural sağlanamamışsa oturum onaylanamaz."""
    session = _oturum(separation=SeparationMode.DESK)
    _cinsiyet_ata()
    session, _result, _report = services.distribute_session(session, seed=42)

    # Elle bozma: bir öğrenciyi farklı anahtarlı birinin sırasına taşı.
    satirlar = list(SeatAssignment.objects.filter(session=session).order_by("seat_no"))
    kaynak = satirlar[0]
    hedef = next(a for a in satirlar if a.separation_key != kaynak.separation_key)
    SeatAssignment.objects.filter(pk=kaynak.pk).update(
        room_id=hedef.room_id,
        desk_row=hedef.desk_row,
        desk_col=hedef.desk_col,
        slot=0 if hedef.slot == 1 else 1,
        seat_no=99,
    )

    rapor = services.seating_report(session)
    assert not rapor.is_valid
    assert any("aynı sırada oturuyor" in v for v in rapor.hard_violations)
    with pytest.raises(ValidationError, match="kural ihlali var"):
        services.approve_session(session)


def test_evrakta_cinsiyet_izi_yok() -> None:
    """KORUMA TESTİ: kural açıkken bile öğrenciyi ayıran hiçbir işaret basılmaz.

    R8'e YALNIZ kuralın adı girer (aşağıdaki testte); salon evrakı, duyuru,
    tutanak ve yoklama cinsiyetten habersizdir.
    """
    session = _oturum(separation=SeparationMode.DESK)
    _cinsiyet_ata()
    session, _result, _report = services.distribute_session(session, seed=42)

    for code in ("r1", "r4", "r5", "r7"):
        icerik = services.render_session_report(session, code).content
        if code == "r5":  # Excel — ham baytta ara
            metin = icerik.decode("latin-1", errors="ignore")
        else:
            sayfalar = PdfReader(io.BytesIO(icerik)).pages
            metin = " ".join(" ".join(s.extract_text() or "" for s in sayfalar).split())
        for yasak in ("Kız", "Erkek", "Cinsiyet", "ayrışma"):
            assert yasak not in metin, f"{code}: {yasak}"


def test_r8de_yalniz_kuralin_adi_basilir() -> None:
    """R8 dağıtım bilgilerinde kuralın ADI vardır; iç kod ve sayım YOKTUR."""
    session = _oturum(separation=SeparationMode.DESK)
    _cinsiyet_ata()
    session, _result, _report = services.distribute_session(session, seed=42)

    metin = " ".join(
        " ".join(
            s.extract_text() or ""
            for s in PdfReader(
                io.BytesIO(services.render_session_report(session, "r8").content)
            ).pages
        ).split()
    )
    assert "Kız/erkek ayrışması Aynı sıraya oturtma" in metin
    for yasak in ("DESK", "ROOM", "separation"):
        assert yasak not in metin


def test_anonimlestirme_ayrisma_anahtarini_bosaltir() -> None:
    """F27: anonim arşivde kuralın yeniden doğrulanması gerekmez."""
    session = _oturum(separation=SeparationMode.DESK)
    _cinsiyet_ata()
    session, _result, _report = services.distribute_session(session, seed=42)
    services.approve_session(session)
    session = services.archive_session(session)

    services.anonymize_exam_session(session)

    assert {a.separation_key for a in SeatAssignment.all_objects.filter(session=session)} == {""}
