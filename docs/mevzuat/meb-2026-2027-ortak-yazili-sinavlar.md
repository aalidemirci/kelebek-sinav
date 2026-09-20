---
mevzuat-adi: "2026-2027 Eğitim Öğretim Yılı Ortak Yazılı Sınavları (MEB ÖDSHGM yazısı)"
belge-turu: "yazı"
sayi-tarih: "E-26614336-480.99-168561496 / 10.09.2026"
kaynak: "MEB Ölçme, Değerlendirme ve Sınav Hizmetleri Genel Müdürlüğü — Dağıtım Yerlerine"
kapsam: "yazının metni ve eki (Ülke Geneli Ortak Yazılı Sınav Takvimi); iletişim ve e-imza satırları alınmadı"
ilgili-moduller: [sinav]
etiketler: [ortak-yazili-sinav, sinav-takvimi, sinav-haftasi, gunluk-sinav-sayisi, bep]
---

> **Programdaki karşılığı (19.09.2026):**
>
> - Dört sınav haftası → `backend/apps/sinav/official_windows.py`
>   (`OFFICIAL_WINDOWS[2026]`). Yeni takvimin ön tarihleri ve takvim sayfasındaki
>   "Bakanlık tarihlerini kullan" önerisi buradan gelir. **Varsayılandır, kısıt
>   değil:** tarihleri idareci değiştirebilir.
> - Madde 6 (günde en çok iki yazılı) → zaten uygulanıyordu: 3. sınav uyarı,
>   4. sınav ret (`services_calendar._daily_exam_load`).
> - Madde 7 (son günden başlanarak planlama) → otomatik yerleştirmenin "Son
>   günden başlayarak yerleştir" tercihi (varsayılan açık, kapatılabilir).
> - Madde 8 (BEP'li öğrencinin sınavı BEP'i doğrultusunda ders öğretmenince
>   hazırlanır) → "BEP kapsamındaki öğrenciler" listesi + oturumda "bireysel soru
>   dosyası" (20.09.2026 — `services_individual`): seçilen öğrencinin kitapçığı
>   kendi PDF'inden ADINA basılır, salona giden hiçbir evrakta ayıran işaret yoktur;
>   basılı bilgi yalnız idare özetidir. KVKK değerlendirmesi: `kvkk-6698.md`
>   "Değerlendirme notları — BEP".
> - Madde 11 (merkezî sınav haftası) → Kullanım Kılavuzu notu.
> - Ek (Ülke Geneli Ortak Yazılı Sınav Takvimi) → `official_windows.NATIONAL_EXAMS`.
>   Takvim oluşturulurken okulun sınıf düzeylerindeki sınavlar Bakanlık sınavı
>   olarak resmî gününe, okulun ilk sınav saatiyle SABİTLENİR; ekte ders saati
>   yoktur (uygulama esasları ayrıca duyurulacak — yazının son paragrafı), saati
>   idareci düzeltir. Eski taslak takvimlerde takvim sayfasındaki "Takvime
>   uygula" (`services_calendar.apply_national_exams`, 19.09.2026).

---

**Sayı:** E-26614336-480.99-168561496
**Tarih:** 10.09.2026
**Konu:** 2026-2027 Eğitim Öğretim Yılı Ortak Yazılı Sınavları

DAĞITIM YERLERİNE

**İlgi:**
a) Millî Eğitim Bakanlığının 2026/68 sayılı Genelgesi.
b) Bakanlık Makamının 18.08.2026 tarihli ve E-57750415-020-166330009 sayılı Olur'u.
c) Bakanlık Makamının 09.09.2026 tarihli ve E-26614336-020-168472744 sayılı Olur'u.

İlgi (a)'da kayıtlı Genelge ile 2026-2027 eğitim öğretim yılı çalışma takviminde
belirlenen ortak yazılı sınav tarihleri, yapılan değerlendirmeler neticesinde eğitim
öğretim faaliyetlerinin daha verimli bir şekilde yürütülmesi amacıyla güncellenerek;

- 1. dönem 1. yazılı sınavlarının 2 Kasım-13 Kasım 2026,
- 1. dönem 2. yazılı sınavlarının 4 Ocak-15 Ocak 2027,
- 2. dönem 1. yazılı sınavlarının 29 Mart-9 Nisan 2027,
- 2. dönem 2. yazılı sınavlarının 7 Haziran-18 Haziran 2027

tarihlerinde gerçekleştirilmesi ve ortak yazılı sınavlara ilişkin iş ve işlemlerin bu
tarihler esas alınarak yürütülmesi Bakanlık Makamının İlgi (b)'de kayıtlı Olur'u ve
2026-2027 eğitim öğretim yılında yapılacak ülke geneli ortak yazılı sınavların Ek
listede yer alan sınıf düzeyleri, ders ve tarihlerde gerçekleştirilmesi Bakanlık
Makamının İlgi (c)'de kayıtlı Olur'u ile uygun görülmüştür.

Bu bağlamda;

1- Ülke geneli ortak yazılı sınavlar dışındaki yazılı sınavların okul geneli ortak
yazılı sınav olarak yapılması,

2- Genel Müdürlüğümüzce 2026-2027 eğitim öğretim yılı birinci dönem okul geneli ortak
yazılı sınavlar için konu soru dağılım tablosu ve senaryolar hazırlanarak
https://meb.ai/ksdt2026 adresinde yayımlanmış olup konu soru dağılım tablosu
yayımlanan derslerde, okul geneli ortak yazılı sınavlarda söz konusu tabloların esas
alınması ve bu dersler için il sınıf/alan zümrelerince ayrıca konu soru dağılım
tablosu hazırlanmaması,

3- Genel Müdürlüğümüzce konu soru dağılım tablosu yayımlanmayan diğer derslere ait
tablo ve senaryoların, ilgili mevzuat hükümleri doğrultusunda il sınıf/alan
zümrelerince, ölçme ve değerlendirme merkezi müdürlüklerinin görüşü alınarak
hazırlanması,

4- Okul geneli ortak yazılı sınavlarda kullanılacak senaryoların, ilgili dersin eğitim
kurumu sınıf/alan zümrelerince belirlenmesi ve eğitim öğretim yılı başında okul
müdürlüklerince öğrenci ve velilere duyurulması,

5- Okul geneli ortak yazılı sınavların, Türkiye Yüzyılı Maarif Modeli uygulanan
derslerde öğrenme çıktılarını, diğer derslerde ise kazanımları ölçen açık uçlu veya
açık uçlu ve kısa cevaplı sorulardan oluşturulması,

6- Zorunlu hâller dışında bir sınıf düzeyinde bir günde yapılacak yazılı sınav
sayısının ikiyi geçmemesi,

7- Okul geneli ortak yazılı sınav tarihlerinin; derslerin konu kapsamı, öğretim
sürecinin ilerleyişi ve kapsam geçerliğinin sağlanması birlikte göz önünde
bulundurularak sınav uygulama haftalarının son gününden başlanarak planlanması,

8- Kaynaştırma/bütünleştirme yoluyla eğitim ve öğretimlerine devam eden öğrencilere
yönelik ölçme ve değerlendirme süreçlerinde Bireyselleştirilmiş Eğitim Programı (BEP)
esas alınması ve bu öğrencilerin sınavlarının, BEP'leri doğrultusunda ilgili
sınıf/ders öğretmenleri tarafından hazırlanması,

9- Ortak yazılı sınavlarda; öğrencilerin öğrenme çıktıları/kazanımları edinme
düzeylerinin belirlenmesi, öğrenme eksikliklerinin ortaya konulması ve öğretim
süreçlerinin geliştirilmesine yönelik geri bildirim sağlanması ve bu doğrultuda ortak
yazılı sınav sonuçlarının yalnızca bir puan olarak değerlendirilmeyerek öğrenme
süreçlerinin güçlendirilmesine yönelik bir geri bildirim kaynağı olarak kullanılması,

10- Ülke ve okul geneli ortak yazılı sınav sonuçlarının toplu listeler halinde
yayımlanmaması,

11- Merkezî olarak gerçekleştirilen seçme ve yerleştirme sınavlarının, ikinci dönem
ikinci yazılı sınavlarının uygulanacağı haftaya denk gelmesi hâlinde, söz konusu
merkezî sınavlara katılacak öğrencilerin yazılı sınavlarının okul yönetimince
alınacak tedbirler doğrultusunda planlanması

gerekmektedir.

Ülke geneli ortak yazılı sınavlara ilişkin konu soru dağılım tabloları ve uygulamaya
ilişkin esaslar Genel Müdürlüğümüzce ayrıca duyurulacak olup 2026-2027 eğitim öğretim
yılında gerçekleştirilecek ortak yazılı sınavların yukarıda belirtilen esaslar
doğrultusunda gerçekleştirilmesi hususunda bilgilerini ve gereğini arz/rica ederim.

Bakan a.
Ölçme, Değerlendirme ve Sınav Hizmetleri Genel Müdürü

**Ek:** Ülke Geneli Ortak Yazılı Sınav Takvimi (1 Sayfa)

---

## Ek — 2026-2027 Eğitim Öğretim Yılı Ülke Geneli Ortak Yazılı Sınav Takvimi

> Kaynak: ÖDSHGM, `https://odsgm.meb.gov.tr/meb_iys_dosyalar/2026_09/6aa2d6b17db57454479127_Ulke_Geneli_Ortak_Yazılı_Sınav_Takvimi.pdf`
> (MEB'in 10.09.2026 tarihli "Ülke Geneli Ortak Yazılı Sınav Takvimi Belli Oldu"
> haberindeki bağlantı; erişim 19.09.2026). Belge form başlığı: T.C. Millî Eğitim
> Bakanlığı Ölçme, Değerlendirme ve Sınav Hizmetleri Genel Müdürlüğü — Doküman
> Kodu İMD / FR0144/R.000, Sayfa 1/1. Tablolar birebir; ekte saat/ders saati yoktur.

**1. Dönem 1. Yazılı Sınavları**

| Sınıf | Ders Adı | Sınav Tarihi |
|---|---|---|
| 6. Sınıf | Matematik | 11 Kasım 2026 Çarşamba |
| 10. Sınıf | Türk Dili ve Edebiyatı | 12 Kasım 2026 Perşembe |

**1. Dönem 2. Yazılı Sınavları**

| Sınıf | Ders Adı | Sınav Tarihi |
|---|---|---|
| 7. Sınıf | Türkçe | 5 Ocak 2027 Salı |
| 9. Sınıf | Matematik | 6 Ocak 2027 Çarşamba |

**2. Dönem 1. Yazılı Sınavları**

| Sınıf | Ders Adı | Sınav Tarihi |
|---|---|---|
| 7. Sınıf | Matematik | 6 Nisan 2027 Salı |
| 9. Sınıf | Türk Dili ve Edebiyatı | 7 Nisan 2027 Çarşamba |

**2. Dönem 2. Yazılı Sınavları**

| Sınıf | Ders Adı | Sınav Tarihi |
|---|---|---|
| 6. Sınıf | Türkçe | 8 Haziran 2027 Salı |
| 10. Sınıf | Matematik | 9 Haziran 2027 Çarşamba |
