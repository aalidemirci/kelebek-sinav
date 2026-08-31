# Elle yazılmıştır (auto-generated DEĞİL) — mevcut kurulumların ders kataloğunu
# sınav biçimine göre sınıflar.
#
# NEDEN GEREKLİ: `services.ensure_meb_catalog` yalnız hiç MEB_CATALOG kaydı
# YOKKEN dosyaları okur ("zaten yüklü" erken dönüşü). Yani çizelge dosyasına
# "Sınav" sütunu eklemek KURULU bir veritabanını hiç güncellemez — yalnız
# sıfırdan kurulan makineleri etkiler. Bu göç o boşluğu ada göre kapatır.
#
# NORMALIZE İNLİNE KOPYADIR: `apps.dersler.text` import edilseydi `_MATCH_TABLE`
# ileride değiştiğinde bu (dondurulmuş olması gereken) göçün davranışı sessizce
# kayardı. Django'nun kanonik tavsiyesi de göçlerin uygulama koduna bağlanmaması
# yönündedir; kesit yedi satır, kopyalamanın bedeli yok.
#
# EŞLEŞTİRME `canon_course_key` DAVRANIŞIYLA: `course_match_key`'in üstüne
# baştaki 'seçmeli ' önekinin atılması eklenir. Gerekçe: e-Okul bu iki dersi
# 'SEÇMELİ SPOR EĞİTİMİ' / 'SEÇMELİ SANAT EĞİTİMİ' diye yazar
# (`ders-adi-takma-adlari.md`) ve operatörün elle açtığı MANUAL kayıt bu adı
# taşıyor olabilir; öneksiz anahtar onu kaçırırdı. Ters yönde risk yok: önekli
# uydurma bir ad da uygulamalı sayılır, zararsız.

from django.db import migrations

# `apps.dersler.text._MATCH_TABLE` kesiti (yalnız eşleştirme içindir).
_MATCH_TABLE = str.maketrans(
    {
        "İ": "i",
        "I": "ı",
        "Ş": "ş",
        "Ğ": "ğ",
        "Ü": "ü",
        "Ö": "ö",
        "Ç": "ç",
        "Â": "a",
        "â": "a",
        "Î": "i",
        "î": "i",
        "Û": "u",
        "û": "u",
    }
)

# Uygulama sınavıyla değerlendirilen dersler — kelebek düzeninde salon/sıra
# planı gerektirmezler, ortak yazılı takvimine otomatik girmemeliler.
_UYGULAMA_ANAHTARLARI = frozenset(
    {
        "beden eğitimi ve spor",
        "görsel sanatlar/müzik",
        "beden eğitimi ve spor/görsel sanatlar/müzik",
        "görsel sanatlar",
        "müzik",
        "spor eğitimi",
        "sanat eğitimi",
    }
)

# Sınav havuzuna GİRMEYECEK dersler. İkisi de katalogda yalnız e-Okul ders
# programı doğrulamasını beslemek için durur (Tur 362 kürasyon notu):
# "Rehberlik ve Yönlendirme" notla değerlendirilmez; genel "Yabancı Dil" ise
# "Birinci Yabancı Dil"in e-Okul yazımıdır (`ders-adi-takma-adlari.md` takma ad
# tablosu) — YAZILI kalsaydı otomatik tohumlanan havuza her seviyede kopya
# satır düşerdi (31.08.2026 denetimi). Kendi 'Yabancı Dil' kaydını sınavlı
# tutmak isteyen okul, ders havuzundaki "Sınav" alanından geri çevirir.
_SINAVSIZ_ANAHTARLAR = frozenset({"rehberlik ve yönlendirme", "yabancı dil"})


def _canon_key(name):
    """Ders adı → eşleştirme anahtarı (TR-duyarlı küçük harf + şapka + 'seçmeli ' öneksiz)."""
    key = " ".join(str(name).translate(_MATCH_TABLE).lower().split())
    return key.removeprefix("seçmeli ")


def _sinav_bicimi(name):
    """Ada göre sınav biçimi; sınıflanamayan ad için None (kayda dokunulmaz)."""
    key = _canon_key(name)
    if key in _UYGULAMA_ANAHTARLARI:
        return "PRACTICE"
    if key in _SINAVSIZ_ANAHTARLAR:
        return "NONE"
    return None


def sinav_bicimlerini_ata(apps, schema_editor):
    """Katalogdaki uygulama/sınavsız dersleri işaretle; kalan hepsi WRITTEN kalır.

    Soft-delete edilmiş ve pasifleştirilmiş kayıtlar da sınıflanır: göçteki
    historical manager düz `models.Manager`'dır (`SoftDeleteManager`
    `use_in_migrations` kurmaz), pasif ders de ileride yeniden aktifleşebilir.
    Toplu `update()` bilerek `updated_at`'e dokunmaz (auto_now yalnız save'de
    çalışır) — bu bir şema tamamlaması, idari bir düzenleme değil.
    """
    Course = apps.get_model("dersler", "Course")
    hedef = {}
    for pk, name in Course.objects.values_list("pk", "name"):
        bicim = _sinav_bicimi(name)
        if bicim is not None:
            hedef.setdefault(bicim, []).append(pk)
    for bicim, pks in hedef.items():
        Course.objects.filter(pk__in=pks).update(exam_mode=bicim)


class Migration(migrations.Migration):

    dependencies = [
        ('dersler', '0002_course_exam_mode'),
    ]

    operations = [
        # Geri alma NOOP: sütun 0002'nin geri alınmasıyla zaten düşer. "Hepsini
        # WRITTEN yap" seçeneği idarecinin arayüzden verdiği değerleri de
        # silerdi — geri sarmak veri kaybettirmemeli.
        migrations.RunPython(sinav_bicimlerini_ata, migrations.RunPython.noop),
    ]
