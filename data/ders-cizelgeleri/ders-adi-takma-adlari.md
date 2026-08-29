# Ders Adı Takma Adları (Seed)

e-Okul ihracı ve dış AI çıktılarında sık görülen ders adı KISALTMALARINI
MEB kataloğundaki (`anadolu-lisesi-2025-2026.md`) kanonik ada bağlar
(Tur 565, AI-import sağlamlaştırma T6 / FAZ D).

- Bu dosya **katalog değildir** — `ensure_meb_catalog` bu dosyayı ada göre
  dışlar; `ensure_course_aliases` yükler (idempotent: SEED kaydı varsa atlar).
- Kanonik ad katalogda yoksa satır sessizce atlanır (import bozulmaz).
- Operatörün Çizelge Doğrulama "Bağla" işleminden öğrenilen (OPERATOR)
  kayıtlar bu listedekileri EZEBİLİR; tersi olmaz.
- Slash'lı kombine dersler ("Görsel Sanatlar/Müzik") bilinçle listede YOK —
  tekil ad eşleşmesi doğrulama dizininde ayrıca çözülür (F-elective-common-dup).
- **"Seçmeli X" öneki (Tur 653):** e-Okul programı TÜM seçmelileri BÜYÜK HARF
  "SEÇMELİ X" önekiyle yazar; resmi çizelgede adı ÖNEKSİZ olan her seçmeli için
  `Seçmeli <Ad> → <Ad>` satırı eklendi (mükerrer Course koruması). Resmi adı
  zaten "Seçmeli X" olan 9 ders (Seçmeli Fizik vb.) listeye ALINMAZ — onlar
  MEB-eşleşmeyle doğrudan çözülür. Kapsam testi:
  `apps/ders_yapisi/tests/test_course_alias.py::test_seed_dosyasi_oneksiz_resmi_secmelileri_kapsar`.

| Takma ad | Kanonik ad |
|---|---|
| Din Kül. ve Ah. Bil. | Din Kültürü ve Ahlak Bilgisi |
| Din Kül. Ahl. Bil. | Din Kültürü ve Ahlak Bilgisi |
| Din Kültürü ve Ahlâk Bilgisi | Din Kültürü ve Ahlak Bilgisi |
| T.C. İnk. Tar. ve Atatürkçülük | T.C. İnkılap Tarihi ve Atatürkçülük |
| T.C. İnkılâp Tarihi ve Atatürkçülük | T.C. İnkılap Tarihi ve Atatürkçülük |
| İnkılap Tarihi | T.C. İnkılap Tarihi ve Atatürkçülük |
| Türk Dili ve Ed. | Türk Dili ve Edebiyatı |
| T. Dili ve Edebiyatı | Türk Dili ve Edebiyatı |
| TDE | Türk Dili ve Edebiyatı |
| Beden Eğt. ve Spor | Beden Eğitimi ve Spor |
| Beden Eğitimi | Beden Eğitimi ve Spor |
| Sağ. Bil. ve Trafik Kül. | Sağlık Bilgisi ve Trafik Kültürü |
| Sağlık Bilgisi | Sağlık Bilgisi ve Trafik Kültürü |
| Reh. ve Yönlendirme | Rehberlik ve Yönlendirme |
| Rehberlik | Rehberlik ve Yönlendirme |
| 1. Yabancı Dil | Birinci Yabancı Dil |
| Yabancı Dil | Birinci Yabancı Dil |
| 2. Yabancı Dil | İkinci Yabancı Dil |
| Çağdaş Türk ve Dünya Tar. | Çağdaş Türk ve Dünya Tarihi |
| Haz. Türk Dili ve Edebiyatı | Hazırlık Sınıfı Türk Dili ve Edebiyatı |
| Astronomi | Astronomi ve Uzay Bilimleri |
| Seçmeli Temel Matematik | Temel Matematik |
| Seçmeli Çağdaş Türk ve Dünya Tarihi | Çağdaş Türk ve Dünya Tarihi |
| Seçmeli Psikoloji | Psikoloji |
| Seçmeli Sosyoloji | Sosyoloji |
| Seçmeli Mantık | Mantık |
| Seçmeli Hedef Temelli Destek Eğitimi | Hedef Temelli Destek Eğitimi |
| Seçmeli Fen Bilimleri Uygulamaları | Fen Bilimleri Uygulamaları |
| Seçmeli Matematik Uygulamaları | Matematik Uygulamaları |
| Seçmeli Astronomi ve Uzay Bilimleri | Astronomi ve Uzay Bilimleri |
| Seçmeli Sosyal Bilim Çalışmaları | Sosyal Bilim Çalışmaları |
| Seçmeli Bilişim Teknolojileri ve Yazılım | Bilişim Teknolojileri ve Yazılım |
| Seçmeli Proje Tasarımı ve Uygulamaları | Proje Tasarımı ve Uygulamaları |
| Seçmeli Düşünme Eğitimi | Düşünme Eğitimi |
| Seçmeli Demokrasi ve İnsan Hakları | Demokrasi ve İnsan Hakları |
| Seçmeli Sürdürülebilir Tarım ve Gıda Güvenliği | Sürdürülebilir Tarım ve Gıda Güvenliği |
| Seçmeli İklim, Çevre ve Yenilikçi Çözümler | İklim, Çevre ve Yenilikçi Çözümler |
| Seçmeli Temel Hukuk Bilgisi | Temel Hukuk Bilgisi |
| Seçmeli Girişimcilik | Girişimcilik |
| Seçmeli Metin Tahlilleri | Metin Tahlilleri |
| Seçmeli Osmanlı Türkçesi | Osmanlı Türkçesi |
| Seçmeli Türk Dünyası Coğrafyası | Türk Dünyası Coğrafyası |
| Seçmeli Ortak Türk Edebiyatı | Ortak Türk Edebiyatı |
| Seçmeli Ortak Türk Tarihi | Ortak Türk Tarihi |
| Seçmeli Kur'an-ı Kerim | Kur'an-ı Kerim |
| Seçmeli Kur'an-ı Kerim'in Anlam Dünyası | Kur'an-ı Kerim'in Anlam Dünyası |
| Seçmeli Peygamberimizin Hayatı | Peygamberimizin Hayatı |
| Seçmeli Temel Dinî Bilgiler | Temel Dinî Bilgiler |
| Seçmeli Türk Düşünce Tarihi | Türk Düşünce Tarihi |
| Seçmeli Klasik Ahlak Metinleri | Klasik Ahlak Metinleri |
| Seçmeli Adabımuaşeret | Adabımuaşeret |
| Seçmeli Türk Sosyal Hayatında Aile | Türk Sosyal Hayatında Aile |
| Seçmeli İslam Bilim Tarihi | İslam Bilim Tarihi |
| Seçmeli Türk Kültür ve Medeniyet Tarihi | Türk Kültür ve Medeniyet Tarihi |
| Seçmeli İslam Kültür ve Medeniyeti | İslam Kültür ve Medeniyeti |
| Seçmeli Spor Eğitimi | Spor Eğitimi |
| Seçmeli Sanat Eğitimi | Sanat Eğitimi |
