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
import json
import re
from collections.abc import Callable

import pytest
from django.core.exceptions import ValidationError
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.okul import selectors as okul_selectors
from apps.okul.models import SchoolConfig, SeparationMode, Student
from apps.sinav import layout, services
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


def _karisik_siraya_tasi(session: ExamSession) -> tuple[SeatAssignment, SeatAssignment]:
    """Elle bozma: bir öğrenciyi farklı anahtarlı birinin sırasına taşır."""
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
    return kaynak, hedef


def _karisik_salona_tasi(session: ExamSession) -> tuple[SeatAssignment, SeatAssignment]:
    """Elle bozma: bir öğrenciyi öteki anahtarın salonuna taşır."""
    satirlar = list(SeatAssignment.objects.filter(session=session).order_by("seat_no"))
    kaynak = satirlar[0]
    hedef = next(a for a in satirlar if a.room_id != kaynak.room_id)
    SeatAssignment.objects.filter(pk=kaynak.pk).update(room_id=hedef.room_id, seat_no=99)
    return kaynak, hedef


def _r8_metni(session: ExamSession) -> str:
    """R8 PDF'inin boşlukları sadeleştirilmiş metni."""
    sayfalar = PdfReader(io.BytesIO(services.render_session_report(session, "r8").content)).pages
    return " ".join(" ".join(s.extract_text() or "" for s in sayfalar).split())


def _okul_no_gecmez(metin: str, *satirlar: SeatAssignment) -> None:
    """Satırların okul numarası metinde yok ("D-201" salon adı numara sayılmaz)."""
    for satir in satirlar:
        assert not re.search(rf"(?<![\w-]){satir.student_number}(?!\w)", metin)


#: Cinsiyet izi: büyük/küçük harf ve ASCII yazım dâhil ("sekiz" sözcüğü yakalanmaz).
_CINSIYET_IZI = re.compile(r"\bk[ıi]z|erkek|cinsiyet", re.IGNORECASE)

#: R8 dağıtım bilgilerindeki satırın başlığı — kuralın ADI; izin verilen tek geçiş.
_KURAL_ADI = "Kız/erkek ayrışması"

#: Ham anahtar yerine kullanılan iz harfleri. "K"/"E" metinde aranamaz (her evrakta geçen
#: harflerdir, `_CINSIYET_IZI` de yakalamaz); Türkçe evrakta hiç geçmeyen bu iki harf
#: anahtar sızarsa kesin yakalanır. Alan tek karakterliktir (`max_length=1`).
_IZ_ANAHTARLARI = ("Ж", "Щ")


def _beklenen_ihlal(kip: str, hedef: SeatAssignment) -> str:
    """Bozulan koltuk için beklenen ihlal satırı — konum kilidi."""
    if kip == SeparationMode.DESK:
        konum = layout.desk_position_label(hedef.desk_row, hedef.desk_col)
        return f"Ayrı oturma kuralı ihlali: {hedef.room.name}, {konum}."
    mevcut = SeatAssignment.objects.filter(session=hedef.session, room_id=hedef.room_id).count()
    return f"Ayrı salon kuralı ihlali: {hedef.room.name}, salon mevcudu {mevcut}."


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
    assert session.distribution_params["separation_unknown"] == 0
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
    """K3 SERT: kural sağlanamamışsa oturum onaylanamaz — idarenin kabulüyle DE.

    31.10.2026'dan beri kelebek komşuluğu ihlali kabulle onaylanabilir; kız/erkek
    ayrışması bu gevşemenin DIŞINDADIR (kuralın güvencesi).
    """
    session = _oturum(separation=SeparationMode.DESK)
    _cinsiyet_ata()
    session, _result, _report = services.distribute_session(session, seed=42)

    _kaynak, hedef = _karisik_siraya_tasi(session)

    rapor = services.seating_report(session)
    assert not rapor.is_valid and not rapor.acceptable
    konum = layout.desk_position_label(hedef.desk_row, hedef.desk_col)
    assert f"Ayrı oturma kuralı ihlali: {hedef.room.name}, {konum}." in rapor.blocking_violations
    with pytest.raises(ValidationError, match="onayla kabul edilemeyen"):
        services.approve_session(session)
    with pytest.raises(ValidationError, match="kuralı değiştirin"):
        services.approve_session(session, accept_violations=True)


def test_evrakta_cinsiyet_izi_yok() -> None:
    """KORUMA TESTİ: kural açıkken bile öğrenciyi ayıran hiçbir işaret basılmaz.

    R8'e YALNIZ kuralın adı girer (aşağıdaki testlerde); salon evrakı, duyuru,
    tutanak ve yoklama cinsiyetten habersizdir. Oturum temiz olduğu için bu test
    ihlal metnini GÖRMEZ: ihlal satırı R8'de ve ekranda ayrıca sınanır.
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


def test_ihlalli_onaysiz_oturumun_r8inde_cinsiyet_ve_okul_no_yok() -> None:
    """KORUMA TESTİ: ihlal satırı R8'e kuralın adı + konumla girer.

    Eski metin "kız ve erkek öğrenci ... okul no X ve okul no Y" basıyor, kişiyle
    cinsiyeti eşliyordu; temiz oturumda ihlal listesi boş olduğu için hiçbir test
    bunu göremedi.
    """
    session = _oturum(separation=SeparationMode.DESK)
    _cinsiyet_ata()
    session, _result, _report = services.distribute_session(session, seed=42)
    kaynak, hedef = _karisik_siraya_tasi(session)

    metin = _r8_metni(session)

    konum = layout.desk_position_label(hedef.desk_row, hedef.desk_col)
    assert f"Ayrı oturma kuralı ihlali: {hedef.room.name}, {konum}." in metin
    assert metin.count(_KURAL_ADI) == 1
    assert not _CINSIYET_IZI.search(metin.replace(_KURAL_ADI, ""))
    assert "okul no" not in metin.lower()
    _okul_no_gecmez(metin, kaynak, hedef)


def test_ayri_salon_ihlali_r8de_salon_ve_sayiyla_basilir() -> None:
    """Ayrı salonlar kipinde satır salon adı + öğrenci sayısıdır; cinsiyet sözcüğü yok."""
    session = _oturum(separation=SeparationMode.ROOM, rooms=2, per_level=4)
    _cinsiyet_ata()
    session, _result, _report = services.distribute_session(session, seed=42)
    kaynak, hedef = _karisik_salona_tasi(session)

    (ihlal,) = [
        v
        for v in services.seating_report(session).hard_violations
        if v.startswith("Ayrı salon kuralı")
    ]
    adet = SeatAssignment.objects.filter(session=session, room_id=hedef.room_id).count()
    assert ihlal == f"Ayrı salon kuralı ihlali: {hedef.room.name}, salon mevcudu {adet}."

    metin = _r8_metni(session)
    assert ihlal in metin
    assert not _CINSIYET_IZI.search(metin.replace(_KURAL_ADI, ""))
    _okul_no_gecmez(metin, kaynak, hedef)


@pytest.mark.parametrize(
    ("kip", "salon_sayisi", "bozma"),
    [
        (SeparationMode.DESK, 1, _karisik_siraya_tasi),
        (SeparationMode.ROOM, 2, _karisik_salona_tasi),
    ],
)
def test_ihlalli_oturumun_yerlesim_ekraninda_cinsiyet_izi_yok(
    kip: str,
    salon_sayisi: int,
    bozma: Callable[[ExamSession], tuple[SeatAssignment, SeatAssignment]],
) -> None:
    """Ekran yanıtı R8 ile aynı metni taşır: anahtar da sözcük de dışarı çıkmaz."""
    session = _oturum(separation=kip, rooms=salon_sayisi)
    _cinsiyet_ata()
    session, _result, _report = services.distribute_session(session, seed=42)
    kaynak, hedef = bozma(session)

    client = APIClient()
    yerlesim = client.get(f"/api/v1/exam-sessions/{session.pk}/seating/")
    onay = client.get(f"/api/v1/exam-sessions/{session.pk}/approval-check/")
    assert yerlesim.status_code == 200 and onay.status_code == 200

    ham = json.dumps(yerlesim.json(), ensure_ascii=False)
    assert not _CINSIYET_IZI.search(ham)
    assert "separation_key" not in ham

    ihlaller = yerlesim.json()["report"]["hard_violations"]
    assert onay.json()["violations"] == ihlaller
    # Konum uçta da kilitli: idareci hangi sırayı düzelteceğini buradan öğrenir.
    assert _beklenen_ihlal(kip, hedef) in ihlaller
    metin = " ".join(ihlaller)
    assert "okul no" not in metin
    assert not _CINSIYET_IZI.search(metin)
    _okul_no_gecmez(metin, kaynak, hedef)


@pytest.mark.parametrize(
    ("kip", "salon_sayisi", "bozma"),
    [
        (SeparationMode.DESK, 1, _karisik_siraya_tasi),
        (SeparationMode.ROOM, 2, _karisik_salona_tasi),
    ],
)
def test_ham_ayrisma_anahtari_hicbir_metne_dusmez(
    monkeypatch: pytest.MonkeyPatch,
    kip: str,
    salon_sayisi: int,
    bozma: Callable[[ExamSession], tuple[SeatAssignment, SeatAssignment]],
) -> None:
    """KORUMA TESTİ: anahtar uyarıya, kayda, ekrana ya da R8'e metin olarak geçmez.

    `_CINSIYET_IZI` sözcük arar; "D-201: K" gibi ham anahtarı görmez. Bu yüzden anahtarlar
    iz harfleriyle değiştirilir (motor ve doğrulayıcı anahtarın ne olduğunu bilmez) ve
    temiz dağıtımdan ihlalli hâle kadar her çıkış taranır. Veritabanındaki anlık kopya
    kapsam dışıdır: orası anahtarın meşru yeridir.
    """

    def iz_ata(ogrenci_idleri: list[int]) -> dict[int, str]:
        sirali = sorted(ogrenci_idleri)
        return {pk: _IZ_ANAHTARLARI[i % 2] for i, pk in enumerate(sirali)}

    monkeypatch.setattr(okul_selectors, "student_genders", iz_ata)
    session = _oturum(separation=kip, rooms=salon_sayisi)
    session, result, _report = services.distribute_session(session, seed=42)
    assert {a.separation_key for a in SeatAssignment.objects.filter(session=session)} == set(
        _IZ_ANAHTARLARI
    )

    def cikislar() -> str:
        client = APIClient()
        yanitlar = [
            client.get(f"/api/v1/exam-sessions/{session.pk}/seating/").json(),
            client.get(f"/api/v1/exam-sessions/{session.pk}/approval-check/").json(),
        ]
        return " ".join(
            [json.dumps(yanitlar, ensure_ascii=False), _r8_metni(session), *result.warnings]
        )

    temiz = cikislar()
    bozma(session)
    ihlalli = cikislar()

    assert "kuralı ihlali" in ihlalli  # denetim gerçekten ihlalli hâli gördü
    for iz in _IZ_ANAHTARLARI:
        assert iz not in temiz
        assert iz not in ihlalli


def test_cinsiyeti_bilinmeyen_uyarisi_r8e_basilmaz() -> None:
    """Uyarı ekranda ve kayıtta kalır; R8'e kuraldan yalnız adı girer."""
    session = _oturum(separation=SeparationMode.DESK)
    _cinsiyet_ata()
    eksik = Student.objects.order_by("student_number").first()
    assert eksik is not None
    Student.objects.filter(pk=eksik.pk).update(gender="")

    session, result, _report = services.distribute_session(session, seed=42)

    assert any("cinsiyet bilgisi yok" in w for w in result.warnings)
    assert any("cinsiyet bilgisi yok" in w for w in session.distribution_params["warnings"])
    # Kalıcı görünürlük: Yerleşim sekmesi bu sayıyı okur; kimlik taşımaz.
    yerlesim = APIClient().get(f"/api/v1/exam-sessions/{session.pk}/seating/").json()
    assert yerlesim["distribution_params"]["separation_unknown"] == 1
    metin = _r8_metni(session)
    assert metin.count(_KURAL_ADI) == 1
    assert not _CINSIYET_IZI.search(metin.replace(_KURAL_ADI, ""))


def test_anonimlestirme_ayrisma_anahtarini_bosaltir() -> None:
    """F27: anonim arşivde kuralın yeniden doğrulanması gerekmez."""
    session = _oturum(separation=SeparationMode.DESK)
    _cinsiyet_ata()
    session, _result, _report = services.distribute_session(session, seed=42)
    services.approve_session(session)
    session = services.archive_session(session)

    services.anonymize_exam_session(session)

    assert {a.separation_key for a in SeatAssignment.all_objects.filter(session=session)} == {""}


def test_ayri_salonlar_uyarisi_ders_adini_soyler() -> None:
    """Ayrı salonlar yolu motora grup etiketlerini geçirir (25.10.2026): sıra
    yetmediğinde uyarı iç anahtarı ("12:10") değil ders adını söyler — eskiden
    bu yol etiket geçirmiyordu (CLAUDE.md: iç kimlik kullanıcı metninde geçmez)."""
    from dataclasses import replace

    from apps.sinav.tests.test_engine import _grid_room, _participant

    kizlar = [replace(_participant(i, "12:10", level=10), separation_key="K") for i in range(8)]
    erkekler = [
        replace(_participant(100 + i, "13:9", level=9), separation_key="E") for i in range(2)
    ]
    result = services._distribute_separate_rooms(
        kizlar + erkekler,
        [_grid_room(1, 2, 2), _grid_room(2, 2, 2)],  # 2 × (4 ikili sıra)
        seed=1,
        strict=False,
        preplaced=[],
        previous={},
        group_labels={"12:10": "Coğrafya — 10. Sınıf", "13:9": "Tarih — 9. Sınıf"},
    )

    assert any("Coğrafya — 10. Sınıf sınavına 8 öğrenci" in w for w in result.warnings)
    assert not any("12:10" in w for w in result.warnings)
