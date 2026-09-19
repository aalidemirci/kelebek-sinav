# Elle yazılmıştır (auto-generated DEĞİL) — AİHL B grubu çizelge programı yedi
# program dosyasına bölündü (19.09.2026); kayıtlı `level_programs` atamalarındaki
# ESKİ anahtar yenilerine çevrilir.
#
# NEDEN GEREKLİ: çizelge DOSYASI değişikliği veri göçü gerektirmez (katalog
# damgayla yeniden türetilir — `dersler.services.ensure_catalog_synced`), ama bu
# kez bir PROGRAM ANAHTARI kalktı ve anahtar `SchoolConfig.level_programs`
# içinde kayıtlıdır. Göç olmasaydı eski anahtarı işaretlemiş kurulumda:
#   1. plan anahtarı bulamaz, B grubu dersleri çizelge dışına düşerdi;
#   2. `SchoolConfigSerializer.validate_level_programs` bilinmeyen anahtarı
#      REDDETTİĞİ için Okul Bilgileri hiçbir alanıyla kaydedilemezdi;
#   3. çizelge matrisi yalnız bilinen programlara kutu çizdiğinden bayat anahtar
#      arayüzden kaldırılamazdı ("Varsayılana dön" dışında çıkış yok).
#
# DAVRANIŞ KORUNUR: eski dosya yedi programın derslerini birlikte taşıyordu;
# eski anahtar yedi yeni anahtarın HEPSİNE açılır, havuz aynı kalır. Okul
# uygulamadığı programları matristen sonradan bırakır. Tek bilinçli fark:
# B grubu dosyaları "Osmanlı Türkçesi"ni seçmeli satırıyla taşır (kararın
# açıklamaları — program/proje okulunda ders zorunlu değildir), bu kurulumlarda
# ders bir sonraki senkronda seçmeliye döner.
#
# ANAHTARLAR İNLİNE KOPYADIR: göç dondurulmuş olmalıdır; `data/ders-cizelgeleri`
# dosyaları ya da `apps.dersler.catalog` ileride değişse de bu göçün davranışı
# kaymamalı (emsal: `dersler/0003_course_exam_mode_data`). Yedek geri yükleme de
# kapsanır: eski yedek açılışta `migrate`den geçer (`desktop/django_bootstrap`).

from django.db import migrations

_ESKI_ANAHTAR = "anadolu-imam-hatip-lisesi-program-proje-2025"

# Sıra kararın B grubu tablosundaki program sırasıdır.
_YENI_ANAHTARLAR = (
    "anadolu-imam-hatip-lisesi-spor-2025",
    "anadolu-imam-hatip-lisesi-musiki-2025",
    "anadolu-imam-hatip-lisesi-gorsel-sanatlar-2025",
    "anadolu-imam-hatip-lisesi-ilahiyat-odakli-hafizlik-2025",
    "anadolu-imam-hatip-lisesi-fen-ve-teknoloji-2025",
    "anadolu-imam-hatip-lisesi-cocuk-gelisimi-2025",
    "anadolu-imam-hatip-lisesi-kuran-egitim-merkezi-2025",
)


def _anahtarlari_ac(level_programs):
    """Eski anahtarı yedi yeni anahtara açar → (yeni sözlük, değişti mi).

    Sıra korunur ve yinelenen anahtar tek yazılır (idareci yeni anahtarlardan
    birini elle eklemiş olabilir). Beklenmeyen biçimdeki değere dokunulmaz —
    onu düzeltmek bu göçün işi değildir.
    """
    if not isinstance(level_programs, dict):
        return level_programs, False
    sonuc = {}
    degisti = False
    for seviye, anahtarlar in level_programs.items():
        if not isinstance(anahtarlar, list) or _ESKI_ANAHTAR not in anahtarlar:
            sonuc[seviye] = anahtarlar
            continue
        acik = []
        for anahtar in anahtarlar:
            for hedef in _YENI_ANAHTARLAR if anahtar == _ESKI_ANAHTAR else (anahtar,):
                if hedef not in acik:
                    acik.append(hedef)
        sonuc[seviye] = acik
        degisti = True
    return sonuc, degisti


def b_grubu_anahtarini_bol(apps, schema_editor):
    """Kayıtlı seviye atamalarında eski B grubu anahtarını yenileriyle değiştir.

    `catalog_stamp`e dokunulmaz: damga atamaları ve dosya özetlerini içerir,
    ikisi de değiştiği için ilk API çağrısında senkron kendiliğinden koşar.
    `update_fields` bilerek `updated_at`i dışarıda bırakır — bu bir anahtar
    çevirisidir, idari bir düzenleme değil.
    """
    SchoolConfig = apps.get_model("okul", "SchoolConfig")
    for config in SchoolConfig.objects.all():
        yeni, degisti = _anahtarlari_ac(config.level_programs)
        if degisti:
            config.level_programs = yeni
            config.save(update_fields=["level_programs"])


class Migration(migrations.Migration):

    dependencies = [
        ("okul", "0006_schoolconfig_daily_period_count_and_more"),
    ]

    operations = [
        # Geri alma NOOP: uygulamanın geri sürüm yolu yoktur ve yedi anahtarı tek
        # anahtara toplamak idarecinin sonradan bıraktığı programları geri
        # getirirdi — geri sarmak atamayı bozmamalı.
        migrations.RunPython(b_grubu_anahtarini_bol, migrations.RunPython.noop),
    ]
