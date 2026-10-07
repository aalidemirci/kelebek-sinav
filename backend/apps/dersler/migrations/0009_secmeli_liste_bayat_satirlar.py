# Elle yazılmıştır (auto-generated DEĞİL) — 07.10.2026 öncesinden kalan seçmeli
# ders öğrenci listesi artıklarını toparlar.
#
# NEDEN GEREKLİ: 07.10.2026'ya kadar öğrenci şube değiştirince ya da okuldan
# ayrılınca `CourseEnrollment` satırı SİLİNMİYOR, okunurken süzülüyordu. Yeni
# kural (şube değişikliğinde eski satır silinir, yeni şubesi seçmeliyi bölünerek
# okutan öğrenci SEÇİM BEKLER — `services.handle_student_section_changes`)
# olaya bağlıdır: güncellemeden ÖNCE şube değiştirmiş öğrenciye hiç uğramaz.
# Bu göç o öğrencileri bir kez yakalar:
#
# 1. Ayrılmış ya da silinmiş öğrencinin bütün satırları silinir (KVKK md. 7/1 —
#    fotoğraf ve BEP kaydı emsali; yeni `forget_student_enrollments` kancası).
# 2. Aktif ders yılında, satırın şubesi öğrencinin GÜNCEL şubesi değilse satır
#    silinir; öğrencinin yeni şubesinde öğrenci listeli seçmeli varsa öğrenci
#    seçim bekler (eski dersleri öneri olarak tutulur).
#
# ŞİFRELİ ALANA DOKUNMAZ: göçler açılışta, uygulama parolası henüz girilmeden
# koşabilir (CLAUDE.md §2) — öğrenciden yalnız AÇIK alanlar (`values_list`)
# okunur. Uygulama kodu import edilmez (göç dondurulmuş kalmalı).
#
# `_base_manager` BİLİNÇLİDİR: göç geçmiş modelle de, testte gerçek modelle de
# (`django_apps`) koşar. Gerçek modelin `objects`i silinmişleri süzer ve
# `delete()`i YUMUŞAK siler; temel yönetici ikisinde de süzmez ve gerçekten siler.

from django.db import migrations


def toparla(apps, schema_editor):
    SchoolYear = apps.get_model("okul", "SchoolYear")
    ClassSection = apps.get_model("okul", "ClassSection")
    Student = apps.get_model("okul", "Student")
    CourseEnrollment = apps.get_model("dersler", "CourseEnrollment")
    PendingElectiveChoice = apps.get_model("dersler", "PendingElectiveChoice")

    ogrenciler = {
        pk: (seviye, sube, durum, silinme)
        for pk, seviye, sube, durum, silinme in Student._base_manager.values_list(
            "pk", "class_level", "class_section", "status", "deleted_at"
        )
    }
    # 1. Ayrılan/silinen öğrenci — bütün yıllar.
    gidenler = [
        pk for pk, (_, _, durum, silinme) in ogrenciler.items() if durum != "ACTIVE" or silinme
    ]
    if gidenler:
        CourseEnrollment._base_manager.filter(student_id__in=gidenler).delete()

    yil = SchoolYear._base_manager.filter(is_active=True, deleted_at__isnull=True).first()
    if yil is None:
        return
    subeler = {
        pk: (seviye, harf, silinme)
        for pk, seviye, harf, silinme in ClassSection._base_manager.filter(school_year=yil).values_list(
            "pk", "class_level", "class_section", "deleted_at"
        )
    }
    # 2. Şube değiştirmiş öğrencinin eski şube satırları.
    bayat_satirlar: list[int] = []
    eski_dersler: dict[int, set[int]] = {}
    for satir_pk, ogrenci_pk, sube_pk, ders_pk in CourseEnrollment._base_manager.filter(
        school_year=yil, deleted_at__isnull=True
    ).values_list("pk", "student_id", "section_id", "course_id"):
        ogrenci = ogrenciler.get(ogrenci_pk)
        sube = subeler.get(sube_pk)
        if ogrenci is None or sube is None:
            continue
        if (ogrenci[0], ogrenci[1]) != (sube[0], sube[1]):
            bayat_satirlar.append(satir_pk)
            eski_dersler.setdefault(ogrenci_pk, set()).add(ders_pk)
    if not bayat_satirlar:
        return
    CourseEnrollment._base_manager.filter(pk__in=bayat_satirlar).delete()

    # Yeni şube CANLI katalog kaydından aranır (silinmiş eşi aynı adı taşıyabilir).
    sube_kimligi = {
        (seviye, harf): pk for pk, (seviye, harf, silinme) in subeler.items() if silinme is None
    }
    listeli_subeler = set(
        CourseEnrollment._base_manager.filter(school_year=yil, deleted_at__isnull=True).values_list(
            "section_id", flat=True
        )
    )
    for ogrenci_pk, dersler in eski_dersler.items():
        seviye, harf, _, _ = ogrenciler[ogrenci_pk]
        yeni_sube = sube_kimligi.get((seviye, harf))
        if yeni_sube is None or yeni_sube not in listeli_subeler:
            continue
        if PendingElectiveChoice._base_manager.filter(
            student_id=ogrenci_pk, school_year=yil, deleted_at__isnull=True
        ).exists():
            continue
        PendingElectiveChoice._base_manager.create(
            student_id=ogrenci_pk,
            school_year=yil,
            section_id=yeni_sube,
            previous_course_ids=sorted(dersler),
        )


class Migration(migrations.Migration):

    dependencies = [
        ('dersler', '0008_pendingelectivechoice'),
    ]

    operations = [
        # Geri alma NOOP: silinen satırlar zaten okunurken süzülen artıklardı;
        # geri sarmak onları yeniden yaratamaz, yaratması da istenmez.
        migrations.RunPython(toparla, migrations.RunPython.noop),
    ]
