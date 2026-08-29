# Ders Çizelgeleri (sınav ders havuzu kaynağı)

Bu dizindeki `.md` dosyaları `import_course_catalog` komutunun kaynağıdır
(ADR-0016 K6). MEB haftalık ders çizelgeleri değiştikçe dosyayı güncelleyip
komutu yeniden çalıştırmak yeterlidir (idempotent):

```bash
docker compose exec backend python manage.py import_course_catalog
docker compose exec backend python manage.py import_course_catalog --dry-run   # prova
```

> Dizin `data/` altında çünkü backend konteyneri yalnız `./backend` ve
> `./data`'yı mount eder; `docs/` konteynerden görünmez.

## Dosya formatı (markdown tablo)

```markdown
| Ders | Seviyeler | Tür |
|---|---|---|
| Türk Dili ve Edebiyatı | 9-12 | ORTAK |
| Coğrafya | 9, 10 | ORTAK |
| Seçmeli İngilizce | 11-12 | SECMELI |
```

- **Ders:** havuzdaki benzersiz ad (eşleştirme anahtarı — yeniden adlandırma
  yeni ders sayılır).
- **Seviyeler:** virgüllü liste ve/veya aralık: `9, 10` · `9-12` · `0, 9-12`.
  Geçerli düzeyler: **0 (Hazırlık — ADR-0012)**, 9, 10, 11, 12.
- **Tür:** `ORTAK` veya `SECMELI` (Seçmeli yazımı da kabul edilir).

Tablo dışı satırlar (başlık, açıklama) yok sayılır; hatalı satırlar import'u
durdurmaz, komut çıktısında satır numarasıyla raporlanır. Bir dosyada birden
çok tablo olabilir. PDF/XLSX çizelge desteği gerçek dosyalar temin edilince
eklenecek (ADR-0016 Riskler).

`README.md` import'ta atlanır. Gerçek çizelge: `anadolu-lisesi-2025-2026.md`
(TTK 09.05.2025 — AL + Hazırlık AL birleşik; Tur 237).
