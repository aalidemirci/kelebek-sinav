# Spor Lisesi Haftalık Ders Çizelgesi (2026-2027 →, tüm sınıf seviyeleri)

- program_key: spor-lisesi-2026
- ad: Spor Lisesi Haftalık Ders Çizelgesi (TTK 02.09.2026/102)
- okul_turu: SPOR_LISESI
- hazirlik: hayır
- kaynak: TTK 02.09.2026 tarihli ve 102 sayılı karar, s. 2 — https://ttkb.meb.gov.tr/meb_iys_dosyalar/2026_09/6aa10af7e5e37220778699_Spor_Lisesi_Haftal%C4%B1k_Ders_%C3%87izelgesi.pdf
- yururluk: 2026-2027
- kademeli: hayır

Kürasyon notları:

- Karar metni: çizelgenin "2026-2027 eğitim ve öğretim yılından itibaren tüm
  sınıf seviyelerinde ekli örneğine göre uygulanması"; 09.05.2025/9 çizelgesinin
  aynı yıldan itibaren "tüm sınıf seviyelerinde uygulamadan kaldırılması". Kademe
  YOKTUR: 2026-2027'de 9-12'nin tamamı bu dosyadan çözülür, `spor-lisesi-2025`
  yalnız 2025-2026 ders yılı için kalır (program en yeni kapsayan nesli seçer).
  2025/9'un kademeli takvimi yüzünden 2026-2027'de 12. sınıf için görünen
  "önceki çizelge bu sürümde yok" uyarısı da böylece kalkar.
- 2025/9'a göre satır farkları (ders · seviye · tür): "Spor Uygulamaları"
  (ortak, 9-12) çizelgeden ÇIKTI; "Müsabaka Analizi" ortak bölümden (10) çıktı,
  seçmeli bölümdeki ders artık öneksiz "Müsabaka Analizi" adıyla 11-12'de
  (2025/9'da "Seçmeli Müsabaka Analizi"); "Beden Eğitimi ve Spor Tarihi" ortaktan
  (12) seçmeliye (12, Akademik Çalışmalar) geçti; "Rehberlik ve Yönlendirme"
  9. sınıfa da indi (9-12). Öbür derslerin adı, seviyesi ve türü aynıdır.
  Haftalık toplam 43 → 40 saate indi (ortak toplam 37-37-35-31; Birinci Yabancı
  Dil 9-10'da 3, Temel Spor Eğitimi 2, Spor ve Beslenme 1 saat) — saatler bu
  dosyada tutulmaz, yalnız farkın kaynağını belgelemek için yazıldı.
- Aktarım: PDF, DYS çıktısıdır (sayfa tek Form XObject'e sarılı, üstünde indirme
  filigranı) — pypdf düzen kipi forma inmediğinden metin form açılarak döküldü
  (README "Yeni çizelge nasıl eklenir"). `scripts/cizelge_metninden_tablo.py`
  bu dizgide beş satırda sütun kaydırdı; hücreler tek tek metin çizim
  işlemlerinin x-koordinatından sütuna atanarak teyit edildi ve ortak blok sütun
  toplamları çizelgenin "Ortak Ders Saati Toplamı" satırıyla (37-37-35-31)
  sağlandı.
- Ortak kültür bölümünde beden eğitimi yoktur; "Görsel Sanatlar/Müzik" 9-12
  ortaktır.
- Sınav sütunu kürasyondur (ilkeler `spor-lisesi-2025.md` ile aynı):
  antrenman/uygulama dersleri `UYGULAMA`; anatomi, antrenman bilgisi, spor
  tarihi, yönetim, psikoloji, beslenme, müsabaka analizi gibi kuram dersleri
  `YAZILI`; Hedef Temelli Destek Eğitimi `YOK` (Açıklamalar md. 9: "Ders notla
  değerlendirilmez").

## Ortak dersler

| Ders | Seviyeler | Tür | Sınav |
|---|---|---|---|
| Türk Dili ve Edebiyatı | 9-12 | ORTAK | YAZILI |
| Din Kültürü ve Ahlak Bilgisi | 9-12 | ORTAK | YAZILI |
| Tarih | 9-11 | ORTAK | YAZILI |
| T.C. İnkılap Tarihi ve Atatürkçülük | 12 | ORTAK | YAZILI |
| Coğrafya | 9, 10 | ORTAK | YAZILI |
| Matematik | 9, 10 | ORTAK | YAZILI |
| Fizik | 9, 10 | ORTAK | YAZILI |
| Kimya | 9, 10 | ORTAK | YAZILI |
| Biyoloji | 9, 10 | ORTAK | YAZILI |
| Felsefe | 10, 11 | ORTAK | YAZILI |
| Birinci Yabancı Dil | 9-12 | ORTAK | YAZILI |
| Görsel Sanatlar/Müzik | 9-12 | ORTAK | UYGULAMA |
| Sağlık Bilgisi ve Trafik Kültürü | 9 | ORTAK | YAZILI |
| Temel Spor Eğitimi | 9 | ORTAK | UYGULAMA |
| Spor Anatomisi ve Fizyolojisi | 11 | ORTAK | YAZILI |
| Antrenman Bilgisi | 12 | ORTAK | YAZILI |
| Antrenörlük Eğitimi | 12 | ORTAK | YAZILI |
| Sporcu Sağlığı | 11 | ORTAK | YAZILI |
| Spor Yönetimi ve Organizasyonu | 12 | ORTAK | YAZILI |
| Spor Psikolojisi ve Sosyolojisi | 12 | ORTAK | YAZILI |
| Spor ve Beslenme | 9 | ORTAK | YAZILI |
| Eğitsel Oyunlar | 11 | ORTAK | UYGULAMA |
| Genel Jimnastik | 9 | ORTAK | UYGULAMA |
| Ritim Eğitimi ve Halk Dansları | 11 | ORTAK | UYGULAMA |
| Atletizm | 11, 12 | ORTAK | UYGULAMA |
| Takım Sporları | 9-12 | ORTAK | UYGULAMA |
| Bireysel Sporlar | 10-12 | ORTAK | UYGULAMA |
| Rehberlik ve Yönlendirme | 9-12 | ORTAK | YOK |

## Seçmeli dersler — Akademik Çalışmalar

| Ders | Seviyeler | Tür | Sınav |
|---|---|---|---|
| Seçmeli Matematik | 11, 12 | SECMELI | YAZILI |
| Temel Matematik | 11, 12 | SECMELI | YAZILI |
| Seçmeli Fizik | 11, 12 | SECMELI | YAZILI |
| Seçmeli Kimya | 11, 12 | SECMELI | YAZILI |
| Seçmeli Biyoloji | 11, 12 | SECMELI | YAZILI |
| Seçmeli Türk Dili ve Edebiyatı | 11, 12 | SECMELI | YAZILI |
| Seçmeli Tarih | 11, 12 | SECMELI | YAZILI |
| Çağdaş Türk ve Dünya Tarihi | 12 | SECMELI | YAZILI |
| Seçmeli Coğrafya | 11, 12 | SECMELI | YAZILI |
| Psikoloji | 11, 12 | SECMELI | YAZILI |
| Sosyoloji | 11, 12 | SECMELI | YAZILI |
| Mantık | 11, 12 | SECMELI | YAZILI |
| Seçmeli Birinci Yabancı Dil | 11, 12 | SECMELI | YAZILI |
| Artistik Jimnastik | 11, 12 | SECMELI | UYGULAMA |
| Müsabaka Analizi | 11, 12 | SECMELI | YAZILI |
| Beden Eğitimi ve Spor Tarihi | 12 | SECMELI | YAZILI |
| Hedef Temelli Destek Eğitimi | 12 | SECMELI | YOK |
| Fen Bilimleri Uygulamaları | 11, 12 | SECMELI | YAZILI |

## Seçmeli dersler — İnsan, Toplum ve Bilim

| Ders | Seviyeler | Tür | Sınav |
|---|---|---|---|
| Astronomi ve Uzay Bilimleri | 9-12 | SECMELI | YAZILI |
| Sosyal Bilim Çalışmaları | 9-12 | SECMELI | YAZILI |
| Bilişim Teknolojileri ve Yazılım | 9-12 | SECMELI | YAZILI |
| Proje Tasarımı ve Uygulamaları | 9-12 | SECMELI | YAZILI |
| Düşünme Eğitimi | 9, 10 | SECMELI | YAZILI |
| Demokrasi ve İnsan Hakları | 9-12 | SECMELI | YAZILI |
| Sürdürülebilir Tarım ve Gıda Güvenliği | 9-12 | SECMELI | YAZILI |
| İklim, Çevre ve Yenilikçi Çözümler | 10-12 | SECMELI | YAZILI |
| Temel Hukuk Bilgisi | 10-12 | SECMELI | YAZILI |
| Girişimcilik | 11, 12 | SECMELI | YAZILI |
| Metin Tahlilleri | 9-12 | SECMELI | YAZILI |
| Seçmeli İkinci Yabancı Dil | 9-12 | SECMELI | YAZILI |
| Osmanlı Türkçesi | 9-12 | SECMELI | YAZILI |
| Türk Dünyası Coğrafyası | 10, 11 | SECMELI | YAZILI |
| Ortak Türk Edebiyatı | 10, 11 | SECMELI | YAZILI |
| Ortak Türk Tarihi | 10, 11 | SECMELI | YAZILI |

## Seçmeli dersler — Din, Ahlak ve Değer

| Ders | Seviyeler | Tür | Sınav |
|---|---|---|---|
| Kur'an-ı Kerim | 9-12 | SECMELI | YAZILI |
| Kur'an-ı Kerim'in Anlam Dünyası | 11, 12 | SECMELI | YAZILI |
| Peygamberimizin Hayatı | 9-12 | SECMELI | YAZILI |
| Temel Dinî Bilgiler | 9-12 | SECMELI | YAZILI |
| Türk Düşünce Tarihi | 10-12 | SECMELI | YAZILI |
| Klasik Ahlak Metinleri | 9-12 | SECMELI | YAZILI |
| Adabımuaşeret | 11 | SECMELI | YAZILI |
| Türk Sosyal Hayatında Aile | 11, 12 | SECMELI | YAZILI |
| İslam Bilim Tarihi | 11, 12 | SECMELI | YAZILI |

## Seçmeli dersler — Kültür, Sanat ve Spor

| Ders | Seviyeler | Tür | Sınav |
|---|---|---|---|
| Türk Kültür ve Medeniyet Tarihi | 11, 12 | SECMELI | YAZILI |
| İslam Kültür ve Medeniyeti | 11, 12 | SECMELI | YAZILI |
| Spor Eğitimi | 11, 12 | SECMELI | UYGULAMA |
| Sanat Eğitimi | 11, 12 | SECMELI | UYGULAMA |
