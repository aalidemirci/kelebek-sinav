"""Evrak şablonlarının örneğini UYDURMA veriyle basar — tasarım deneme aracı.

Şablona dokunan herkes çıktıyı gözle görebilsin diye vardır: veritabanı,
oturum ve dağıtım gerekmez; bağlamlar `reports.py`den doğrudan kurulur.

Kullanım (depo kökünden):

    docker compose run --rm backend python manage.py evrak_ornek
    docker compose run --rm backend python manage.py evrak_ornek \\
        --ogrenci 44 --satir 8 --sutun 3 --ders 1

Çıktı varsayılan olarak `/repo/.ornek-evrak` (depo kökünde `.ornek-evrak/`,
`.gitignore` ile dışarıda). Sayfa sayıları da basılır: salon evrakı 40
öğrenciye kadar İKİ yaprak olmalıdır (CLAUDE.md §2 sayfa bütçesi kuralı;
garanti `test_reports.py::test_r1_salon_evraki_iki_yaprak`).

Salon evrakının oturma planı fotoğraflıdır (19.09.2026): örnekte her
öğrenciye ÇİZİLMİŞ bir siluet verilir, her yedinci öğrencide fotoğraf yoktur
(evraktaki "fotoğraf yok" kutusu görünsün). `--fotografsiz` hepsini kaldırır.

KVKK: bu komut gerçek öğrenci verisine BAKMAZ — adlar, numaralar ve
"fotoğraflar" uydurmadır (Pillow ile çizilir).
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.sinav import layout, reports

#: Uydurma adlar — uzun Türkçe adlar sarma davranışını da gösterir.
ADLAR = (
    "ZEYNEP GÜLŞAH KARAOĞLU",
    "MEHMET ALİ ÇAĞLAYAN",
    "ABDÜLKADİR ŞAHİNKAYA",
    "ÖZGE NUR BÜYÜKKAYA",
    "AHMET EFE YILDIRIMLI",
    "ELİF SUDE DEMİRÖZ",
)
#: Gerçek etiket biçimi: aynı ders birden çok seviyedeyse ad seviyeyle basılır
#: (`services._seat_course_names`), tek seviyede yalın ad. Eski örnek seviyeyi
#: ders ADINA gömüyordu ("Coğrafya 9") ve karma seviye kusurunu gizliyordu.
DERSLER = ("Coğrafya — 9. Sınıf", "Coğrafya — 10. Sınıf", "Matematik")
#: Ders bazlı süre oturum süresini ezebilir — örnekte üçüncü ders 60 dk.
SURELER = (40, 40, 60)
ODA = "A-201 Dersliği"
GOZETMEN = "Nurten ÖZDEMİRCİ"

BASLIK = reports.ReportHeader(
    school_name="ÖRNEK ANADOLU LİSESİ",
    year_label="2026-2027",
    semester_label="1. Dönem",
    exam_name="1. Ortak Yazılı Sınav",
    exam_date="16.11.2026",
    start_time="09:00",
    generated_at="16.11.2026 08:30",
    duration_label="40 dk",
)


class Command(BaseCommand):
    help = "Evrak şablonlarının örneğini uydurma veriyle PDF olarak basar."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--ogrenci", type=int, default=40, help="Salondaki öğrenci sayısı.")
        parser.add_argument("--satir", type=int, default=5, help="Derslikteki sıra satırı.")
        parser.add_argument("--sutun", type=int, default=4, help="Satır başına ikili sıra.")
        parser.add_argument(
            "--ders", type=int, default=2, help="Salondaki farklı ders sayısı (1-3)."
        )
        parser.add_argument(
            "--cikti", default="/repo/.ornek-evrak", help="Çıktı klasörü (varsayılan depo kökü)."
        )
        parser.add_argument(
            "--fotografsiz",
            action="store_true",
            help="Oturma planını fotoğrafsız bas (fotoğraf aktarılmamış okul).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        ogrenci = max(1, int(options["ogrenci"]))
        satir = max(1, int(options["satir"]))
        sutun = max(1, int(options["sutun"]))
        ders_sayisi = min(max(1, int(options["ders"])), len(DERSLER))
        cikti = Path(str(options["cikti"]))
        try:
            cikti.mkdir(parents=True, exist_ok=True)
        except OSError as exc:  # yazılamayan yol → Türkçe hata
            raise CommandError(f"Çıktı klasörü açılamadı: {exc}") from exc

        dersler = DERSLER[:ders_sayisi]
        # 0. satır demirbaş (öğretmen masası · akıllı tahta · kapı), altı sıra.
        plan_dict: dict[str, Any] = {
            "grid": {"rows": satir + 1, "cols": sutun},
            "desks": [
                {"row": r, "col": c, "type": "DOUBLE"}
                for r in range(1, satir + 1)
                for c in range(sutun)
            ],
            "furniture": [{"row": 0, "col": 0, "kind": "TEACHER_DESK"}]
            + ([{"row": 0, "col": sutun - 1, "kind": "SMART_BOARD"}] if sutun > 1 else []),
        }
        plan = layout.validate_layout_plan(plan_dict)
        satirlar = self._satirlar(ogrenci, dersler)

        sheet = reports.RoomSheet(
            room_name=ODA,
            block="A Blok · 2. kat",
            plan=plan,
            numbering_scheme="S_PATTERN",
            rows=tuple(satirlar),
        )
        proctors = {ODA: GOZETMEN}
        fotograflar = {} if options["fotografsiz"] else self._fotograflar(satirlar)

        self._bas(
            cikti,
            "1-salon-sinav-evraki.pdf",
            "sinav/reports/r1_salon_evraki.html",
            {
                "header": BASLIK,
                "title": reports.REPORT_TITLES["r1"][0],
                "sheets": reports.build_room_documents(
                    [sheet], proctor_names=proctors, photos=fotograflar
                ),
            },
            beklenen=2,
        )

        # Duyuru tek şubeyi üç salona dağıtır — salon dağılımı özeti görünsün.
        duyuru = [
            reports.SeatRow(
                **{**vars(row), "class_label": "9/A", "room_name": f"A-20{i % 3 + 1} Dersliği"}
            )
            for i, row in enumerate(satirlar)
        ]
        self._bas(
            cikti,
            "2-sube-sinav-duyurusu.pdf",
            "sinav/reports/r4_announcement.html",
            {
                "header": BASLIK,
                "title": reports.REPORT_TITLES["r4"][0],
                "sheets": reports.build_announcements(duyuru),
            },
            beklenen=1,
        )

        self._bas(
            cikti,
            "3-ihlal-ve-kopya-tutanagi.pdf",
            "sinav/reports/r7_tutanak.html",
            {
                "header": BASLIK,
                "title": reports.REPORT_TITLES["r7"][0],
                "sheets": reports.build_tutanak_sheets(satirlar, proctor_names=proctors),
            },
            beklenen=1,
        )

        self._bas(
            cikti,
            "4-gozetmen-gorevlendirme.pdf",
            "sinav/reports/r6_assignment.html",
            {
                "header": BASLIK,
                "title": reports.REPORT_TITLES["r6"][0],
                "duty": reports.build_assignment_context(self._gorevliler()),
            },
            beklenen=1,
        )

        self._bas(
            cikti,
            "5-dagitim-dogrulama-raporu.pdf",
            "sinav/reports/r8_validation.html",
            {
                "header": BASLIK,
                "title": reports.REPORT_TITLES["r8"][0],
                "report": self._dogrulama(),
            },
            beklenen=1,
        )

        bos = reports.RoomSheet(
            room_name=ODA, block="A Blok · 2. kat", plan=plan, numbering_scheme="S_PATTERN", rows=()
        )
        self._bas(
            cikti,
            "6-bos-salon-yerlesim-plani.pdf",
            "sinav/reports/room_layout.html",
            {
                "header": {
                    "school_name": BASLIK.school_name,
                    "generated_at": BASLIK.generated_at,
                    "exam_name": "",
                },
                "room": reports.build_room_kroki(bos, box_height_px=reports.KROKI_BOX_LAYOUT_PX),
            },
            beklenen=1,
        )

        self.stdout.write(
            f"\n{ogrenci} öğrenci · {satir}×{sutun} derslik · {ders_sayisi} ders "
            f"→ {cikti} altında altı örnek evrak."
        )

    # -- yardımcılar -------------------------------------------------------
    def _satirlar(self, adet: int, dersler: tuple[str, ...]) -> list[reports.SeatRow]:
        return [
            reports.SeatRow(
                full_name=ADLAR[i % len(ADLAR)],
                student_number=str(1200 + i),
                class_label=f"{9 + i % 3}/{'ABÇ'[i % 3]}",
                room_name=ODA,
                seat_no=i + 1,
                # 0. satır ön cephe bandıdır (öğretmen masası/tahta); sıralar 1'den başlar.
                # Eski `i // 8` ilk sekiz öğrenciyi mobilya satırına koyuyor, örnek kroki
                # onları gösteremiyordu.
                desk_row=1 + i // 8,
                desk_col=(i % 8) // 2,
                slot=i % 2,
                course_name=dersler[i % len(dersler)],
                status="NORMAL",
                duration_minutes=SURELER[i % len(dersler)],
                student_id=i + 1,
            )
            for i in range(adet)
        ]

    def _fotograflar(self, satirlar: list[reports.SeatRow]) -> dict[int, str]:
        """Uydurma vesikalık: düz zemin üstüne gri siluet (baş + omuz).

        Her yedinci öğrenci fotoğrafsız bırakılır. Zemin rengi öğrenciye göre
        değişir: WeasyPrint aynı görseli TEK nesne olarak gömer, özdeş
        fotoğraflar evrakta ayırt edilemezdi.
        """
        import base64

        from PIL import Image, ImageDraw

        zeminler = ((214, 226, 240), (228, 222, 238), (222, 236, 226), (240, 232, 214))
        sonuc: dict[int, str] = {}
        for i, satir in enumerate(satirlar):
            if satir.student_id is None or i % 7 == 6:
                continue
            r, g, b = zeminler[i % len(zeminler)]
            resim = Image.new("RGB", (131, 169), (r, g, b - i % 11))
            kalem = ImageDraw.Draw(resim)
            kalem.ellipse((40, 30, 91, 90), fill=(120, 124, 132))  # baş
            kalem.ellipse((12, 98, 119, 210), fill=(120, 124, 132))  # omuzlar
            tampon = io.BytesIO()
            resim.save(tampon, format="JPEG", quality=85)
            sonuc[satir.student_id] = "data:image/jpeg;base64," + base64.b64encode(
                tampon.getvalue()
            ).decode("ascii")
        return sonuc

    def _gorevliler(self) -> list[reports.ProctorRow]:
        return [
            reports.ProctorRow(
                teacher_name=ADLAR[i % len(ADLAR)],
                role="PROCTOR" if i < 8 else "RESERVE",
                role_label="Gözetmen" if i < 8 else "Yedek Gözetmen",
                room_name=f"A-2{i:02d} Dersliği" if i < 8 else "",
            )
            for i in range(10)
        ]

    def _dogrulama(self) -> dict[str, object]:
        return reports.build_validation_context(
            is_valid=True,
            hard_violations=[],
            first_ring_pairs=0,
            min_distances={"7:9": 2.0, "7:10": 2.24},
            proximity_score=1.2345,
            params={
                "layout_mode_label": "Kelebek",
                "seed": 987654,
                "strict": True,
                "checkerboard": True,
                "placed": 240,
                "pinned": 3,
            },
            group_labels={"7:9": "Coğrafya (9. sınıf)", "7:10": "Coğrafya (10. sınıf)"},
            warnings=["A-205 dersliği %100 doluluğa ulaştı."],
            cross_section_pairs=2,
            occupancy=[
                {
                    "room_name": f"A-20{i} Dersliği",
                    "capacity": 40,
                    "placed": 40 - i,
                    "percent": (40 - i) * 100 / 40,
                }
                for i in range(1, 7)
            ],
        )

    def _bas(
        self,
        cikti: Path,
        ad: str,
        sablon: str,
        context: dict[str, object],
        *,
        beklenen: int,
    ) -> None:
        """Şablonu basar ve sayfa sayısını beklenenle karşılaştırır."""
        from pypdf import PdfReader  # tembel import — yalnız bu araçta gerekir

        pdf = reports.render_pdf(sablon, context)
        (cikti / ad).write_bytes(pdf)
        sayfa = len(PdfReader(io.BytesIO(pdf)).pages)
        uyari = "" if sayfa == beklenen else f"  ← DİKKAT: {beklenen} bekleniyordu (sayfa taştı)"
        self.stdout.write(f"{ad:34s} {sayfa} sayfa{uyari}")
