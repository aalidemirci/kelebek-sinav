# Müfredat Çerçeveleri (sürümlü haftalık ders çizelgesi kaynağı)

Bu dizindeki `.md` dosyaları **`import_curriculum`** komutunun kaynağıdır
(ADR-0037 T2). Bir dosya = bir **`CurriculumFramework`** (sürümlü, seviye-bazlı
haftalık saat matrisi).

> **Bir üst dizindeki (`data/ders-cizelgeleri/*.md`) katalog dosyalarından farklı.**
> O katmandaki `catalog_parser` yalnız `Ders | Seviyeler | Tür` okur (ders KATALOĞU).
> Buradaki `curriculum_parser` ise seviye-bazlı **haftalık SAAT** matrisini okur
> (müfredat ÇERÇEVESİ). `import_course_catalog` bu alt dizini görmez (glob özyinelemesiz).

```bash
docker compose exec backend python manage.py import_course_catalog   # ÖNCE katalog (Course)
docker compose exec backend python manage.py import_curriculum        # SONRA çerçeveler
docker compose exec backend python manage.py import_curriculum --dry-run
```

Çerçeve satırlarının `course_id` FK'si mevcut `Course` kaydına bağlanır; bu
yüzden **önce `import_course_catalog`** çalıştırılmalıdır. Kataloğda bulunmayan
ders adı satırı atlanır (komut çıktısında raporlanır), import durmaz.

## Dosya formatı

Üstte `- anahtar: değer` meta blok, altta **tek** markdown tablo:

```markdown
- ad: Anadolu Lisesi Haftalık Ders Çizelgesi (2025)
- program_key: anadolu-lisesi
- version: 2025
- source: MEB_CATALOG        # MEB_CATALOG | MANUAL (varsayılan MANUAL)
- notes: TTK 09.05.2025/05

| Ders | Hazırlık | 9 | 10 | 11 | 12 | Tür |
|---|:--:|:--:|:--:|:--:|:--:|---|
| Matematik | 3 | 6 | 6 | - | - | ORTAK |
```

- **Meta:** `ad`, `program_key`, `version` zorunlu. `(program_key, version)`
  canlıda benzersiz (idempotent upsert anahtarı).
- **Seviye sütunları:** başlık hücresi `Hazırlık` (veya `0`), `9`, `10`, `11`,
  `12`. **0 = Hazırlık** (ADR-0012). Hücre `-` veya boş = o seviyede yok.
  Sayısal hücre = o seviyedeki **haftalık saat** (≥ 1).
- **Tür sütunu:** `ORTAK` / `SECMELI`. Aynı ders farklı seviyede farklı tür
  olabilir (ör. Bilişim Teknolojileri Hazırlık'ta ORTAK, 9-12'de seçmeli) —
  bu yüzden tür satır (çerçeve×ders×seviye) bazındadır, katalogdan bağımsız.
- **Kapsam (T2):** çerçeveler yalnız **ORTAK** dersleri (sabit haftalık saat)
  taşır. Seçmeliler öğrenci seçimine bağlı değişken saatlidir; katalogda
  (`Course.levels`) izlenir. Seviye başına seçmeli saat =
  `40 − ortak_toplam − rehberlik`.

## Kademeli / hazırlık kontrolü

Hangi ders yılında hangi seviyenin hangi çerçeveye tabi olduğu
**`CurriculumAssignment`** (yıl × seviye → çerçeve) ile yönetilir; kontrol/atama:

```bash
docker compose exec backend python manage.py curriculum_plan                 # aktif yıl raporu
docker compose exec backend python manage.py curriculum_plan --year 2027-2028 \
    --assign 0=anadolu-lisesi-hazirlik --assign 9=anadolu-lisesi              # atama + rapor
```

Okul sonradan hazırlık açarsa: 0. seviye `anadolu-lisesi-hazirlik` çerçevesine
atanır, mevcut 9-12 kohortları `anadolu-lisesi` çerçevesinde kalır. `curriculum_plan`
`SchoolConfig.prep_class_enabled` kapalıyken 0. seviyeyi listelemez.
