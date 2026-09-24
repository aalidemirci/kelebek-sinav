# Sürüm notları

Paketler GitHub Releases'ta ve indir.okulapp.org'dadır. En yeni sürüm en üsttedir;
yayımlanmamış değişiklikler "Yayımlanmadı (taslak)" başlığı altında toplanır ve
sürüm çıkarılırken bu başlık sürüm numarası ve tarihle değiştirilir.

## 2026.9.0-beta.13 — 24.09.2026

### Güvenlik

Bu sürüme geçmeniz önerilir. Aşağıdaki düzeltmeler programın çalıştığı
bilgisayardaki yerel dosyalarla ilgilidir; ağ üzerinden erişim gerektirmez ve
mevcut şifreli kayıtlarınızı etkilemez. Güncellemeden sonra yapmanız gereken bir
işlem yoktur.

- **Güvenlik dosyası kilidi güçlendirildi.** Uygulama parolası kuruluyken
  veri klasöründeki güvenlik dosyası (`guvenlik.json`) bulunamaz ya da
  okunamazsa program artık "Güvenlik dosyası bulunamadı ya da okunamıyor"
  ekranını açar ve yeni parola kurulmasına izin vermez. Ekran iki çıkış yolu
  gösterir: dosyanın sağlam kopyasını geri koymak ya da bir yedeği geri
  yüklemek (her şifreli yedek güvenlik dosyasını da içinde taşır).
- **Şifreli alanların korunması güçlendirildi.** Uygulama parolası kuruluyken
  kilit açılmadan kişisel veri alanlarına yazılamaz. Parolasız kullanım
  değişmedi.
- **Parola kurulurken eski kayıt kalıntıları temizlenir.** Kayıtlar
  şifrelendikten sonra veritabanı dosyası yeniden düzenlenir; şifrelemeden
  önceki sürümler dosyada kalmaz.
- **Kurtarma anahtarı yenilenebilir (görev devri).** Ayarlar → Güvenlik'teki
  "Kurtarma anahtarını yenile" ile, uygulama parolanızı girerek yeni bir
  kurtarma anahtarı üretebilirsiniz; eski anahtar bu bilgisayardaki kayıtların
  kilidini artık açmaz. Parolayı değiştirmek kurtarma anahtarını
  değiştirmez — kurtarma anahtarını elinde tutan kişi görevden ayrıldıysa bu
  işlemi ayrıca yapın. Yenilemeden önce alınmış yedekler eski anahtarla
  açılmaya devam eder; ekran ve kılavuz bunu ayrıntılı anlatır.

### Yedekleme

- Güvenlik dosyası kullanılamadığı gün otomatik yedek alınmaz ve eski yedekler
  silinmez; açılamayacak bir yedek üretmek yerine sağlam eski yedekler korunur.
- Oturum sürerken program kilitlenirse ya da güvenlik dosyası kaybolursa ekran
  hemen ilgili sayfaya (kilit ya da güvenlik dosyası) geçer.

### Belgeler

- Kılavuz ve kurulum belgesine görev devri ve güvenlik dosyası bölümleri
  eklendi.
- Örnek verilerdeki ilçe adı tarafsız bir örnekle değiştirildi.
