# Kelebek Sınav — Kurulum ve Sorun Giderme Kılavuzu

Bu kılavuz programı kuracak kişi içindir; okul bilişim sorumlusuna da "Çıkış
kodları" bölümü ayrılmıştır. Program **tamamen çevrimdışı** çalışır: hiçbir
veri okul dışına çıkmaz, telemetri yoktur. Tek dış istek, siz Ayarlar →
Güncelleme'den denetlediğinizde (veya açılışta bağlantı varsa) GitHub'daki son
sürümü soran anonim istektir — kişisel veri taşımaz, çevrimdışıyken sessizce
atlanır.

## 1. Hangi dosyayı indirmeliyim?

GitHub Releases sayfasındaki dosyalar:

| Dosya | Kimin için |
|---|---|
| `kelebek-sinav-<sürüm>-win64-setup.exe` | Windows 10/11 — önerilen kurulum |
| `kelebek-sinav-<sürüm>-win64-portable.zip` | Windows — kurulumsuz, USB'den |
| `kelebek-sinav_<sürüm>_amd64.deb` | Pardus 21/23 ve Debian tabanlılar — önerilen |
| `kelebek-sinav-<sürüm>-linux-x64.tar.gz` | Linux — yönetici parolası olmadan |
| `SHA256SUMS.txt` | İndirilen dosyayı doğrulamak için (bkz. §8) |

## 2. Windows kurulumu

### 2.1 Kurulum paketi ile (önerilen)

1. `kelebek-sinav-<sürüm>-win64-setup.exe` dosyasını indirin ve çalıştırın.
2. Kurulum **yönetici parolası istemez**; program
   `%LOCALAPPDATA%\Programs\Kelebek Sınav` altına kurulur.
3. Bilgisayarda Microsoft Edge WebView2 yoksa kurucu sessizce kurar
   (paketle gelir; Windows 11'de genellikle zaten kuruludur).
4. Program açıkken yükseltme yapmayın — kurucu açık programı algılar ve
   kapatmanızı ister.

İmzasız paket olduğu için SmartScreen "tanınmayan uygulama" uyarısı verebilir:
"Ek bilgi" → "Yine de çalıştır". Kuruluma güvenmek için önce §8'deki SHA-256
doğrulamasını yapın.

### 2.2 Taşınabilir sürüm (kurulum yapmadan)

`...portable.zip` dosyasını bir klasöre açın, `kelebek-sinav.exe`'yi
çalıştırın. Veriler yine `%LOCALAPPDATA%\KelebekSinav` altına yazılır — zip'i
silmek verileri silmez.

## 3. Pardus / Linux kurulumu

### 3.1 `.deb` paketi ile (önerilen)

```bash
sudo apt install ./kelebek-sinav_<sürüm>_amd64.deb
```

Bağımlılıklar (pango, fontconfig, DejaVu fontları, Qt sistem kütüphaneleri)
dağıtımın deposundan otomatik kurulur. Program menüde "Kelebek Sınav" olarak
görünür; uçbirimden `kelebek-sinav` ile de açılır.

### 3.2 Taşınabilir arşiv ile (yönetici parolası olmadan)

```bash
tar -xzf kelebek-sinav-<sürüm>-linux-x64.tar.gz
cd kelebek-sinav-<sürüm>
./kur.sh
```

`kur.sh` programı `~/.local/opt` altına kopyalar, menü kaydını ve
`~/.local/bin/kelebek-sinav` bağlantısını ekler. Kaldırmak için `./kaldir.sh`.

## 4. İlk açılış

1. Program yerel bir pencere açar (tarayıcı gerekmez; hiçbir port dışarıya
   açılmaz — sunucu yalnız 127.0.0.1'de, rastgele boş bir portta çalışır).
2. Kurulum sihirbazı okul bilgilerini, ders yılını ve dönemleri sorar.
3. Öğrenci/öğretmen listelerini e-Okul'dan aldığınız xlsx dosyasıyla veya
   panoya kopyala-yapıştır ile aktarırsınız (TCKN hiç istenmez ve tutulmaz).
4. Ders havuzu MEB çizelgesinden kendiliğinden dolar (v1: Anadolu Lisesi).
5. İsterseniz Ayarlar → Güvenlik'ten **uygulama parolası** kurarsınız: ad-soyad
   alanları şifrelenir, size TEK SEFERLİK bir kurtarma anahtarı verilir —
   yazdırıp güvenli bir yerde saklayın.

## 5. Verileriniz nerede? Yedekleme

| İçerik | Windows | Pardus/Linux |
|---|---|---|
| Veritabanı + ayarlar | `%LOCALAPPDATA%\KelebekSinav\data` | `~/.local/share/kelebek-sinav/data` |
| Otomatik yedekler | `%LOCALAPPDATA%\KelebekSinav\backups` | `~/.local/share/kelebek-sinav/backups` |
| Günlükler | `%LOCALAPPDATA%\KelebekSinav\logs` | `~/.local/state/kelebek-sinav/logs` |

Program **her gün ilk açılışta** otomatik yedek alır (`gunluk-<tarih>.ksbak`),
yedekleri 14 gün saklar ve her sürüm güncellemesinden önce ayrıca bir yedek
bırakır (`pre-migrate-<sürüm>-<tarih>.ksbak`, son 5 adet).

Yedeğin biçimi güvenlik ayarınıza bağlıdır:

* **Uygulama parolası KURULU DEĞİLSE** yedek düz bir SQLite kopyasıdır —
  §5.1'deki yeniden adlandırma yöntemiyle doğrudan geri dönülür.
* **Uygulama parolası KURULUYSA** yedek X25519 + AES-256-GCM ile şifrelidir;
  içeriği ancak parolanız (veya kurtarma anahtarınız) ile açılabilir. Ayarlar →
  Güvenlik'ten istediğiniz an elle şifreli yedek indirip USB'ye alabilirsiniz.

Yedekler bilgisayarın kendisindedir: ayda bir `backups` klasörünü USB belleğe
kopyalamayı alışkanlık edinin.

### 5.1 Yedekten geri dönme

Program yedekten dönüş için kendi aracını taşır — düz VE şifreli yedekleri
açar, elle dosya kopyalamak gerekmez:

* **Windows:** Başlat menüsündeki **"Kelebek Sınav — Yedekten Geri Yükle"**
  kısayolunu çalıştırın (veya komut isteminden `kelebek-sinav --geri-yukle`).
* **Pardus/Linux:** uçbirimden `kelebek-sinav --geri-yukle`

Araç yedekleri en yeniden eskiye listeler; seçtiğiniz yedek veritabanının
yerine konur. Şifreli yedekler için uygulama parolanız (parola sonradan
değiştiyse yedeğin alındığı dönemdeki parola da denenebilir) ya da kurtarma
anahtarınız sorulur. Mevcut (bozuk) veritabanı SİLİNMEZ — `db-onceki-<tarih>`
adıyla `data` klasöründe saklanır. İşlem bitince programı normal açın.

Parolasız kipte alınmış (düz) bir yedeği elle de döndürebilirsiniz: programı
kapatıp yedeği `data` klasörüne `db.sqlite3` adıyla kopyalamak yeterlidir;
ama aracı kullanmak her iki kipte de daha güvenlidir.

### 5.2 Bütün verileri silip temiz başlama

Programı kapatın ve yukarıdaki tablodaki üç klasörü silin. Bu işlem GERİ
ALINAMAZ — önce `backups` klasörünü bir yere kopyalayın.

## 6. Sık karşılaşılan sorunlar

### 6.1 "Microsoft Edge WebView2 bulunamadı" (Windows)

Kurulum paketi WebView2'yi kendisi kurar; taşınabilir sürümde eksikse program
Türkçe yönlendirme verir. Microsoft'un sayfasından "Evergreen Bootstrapper"
indirip kurun, programı yeniden açın.

### 6.2 "Kelebek Sınav zaten çalışıyor"

Aynı anda tek kopya açılabilir. Pencere görünmüyorsa oturumu kapatıp açın veya
görev yöneticisinden `kelebek-sinav` sürecini sonlandırın.

### 6.3 "Veri dosyası bozuk görünüyor"

Program veriyi korumak için açılmamıştır. §5.1'deki adımlarla son sağlam
yedeğe dönün. Bozuk dosyayı silmeyin; bir kopyasını saklayın.

### 6.4 "Bu veri, programın daha yeni bir sürümüyle oluşturulmuş"

Bilgisayardaki program eski, veri yeni. Programı son sürüme güncelleyin
(Releases sayfası); veri dosyasına dokunmayın.

### 6.5 PDF üretilmiyor veya Türkçe karakterler bozuk

Uçbirimden/komut isteminden teşhis kipini çalıştırın:

```bash
kelebek-sinav --pdf-duman deneme.pdf
```

Çıkış kodu 0 değilse günlük dosyasıyla birlikte bildirin. Windows'ta bu durum
genellikle paket bozulmasına işaret eder — programı kaldırıp yeniden kurun.

### 6.6 Program hiç açılmıyor, hata da vermiyor

`logs/uygulama.log` dosyasının son satırlarına bakın ve bilişim sorumlusuna
iletin. Veri klasörü OneDrive/Dropbox gibi bir eşitleme klasörünün altındaysa
program uyarı günlükler — eşitleme açık SQLite dosyasını bozabilir; veri
klasörünü eşitleme kapsamından çıkarın.

## 7. Çıkış kodları (bilişim sorumlusu için)

`kelebek-sinav --autotest` pencere açmadan tüm açılış zincirini koşar ve
aşağıdaki kodlardan biriyle çıkar:

| Kod | Anlamı | Yapılacak |
|---|---|---|
| 0 | Açılış sağlıklı | — |
| 1 | Beklenmeyen hata | `logs/uygulama.log` son satırları |
| 2 | Program zaten çalışıyor | §6.2 |
| 3 | Veritabanı bozuk | §5.1 yedekten dönüş |
| 4 | Veri, programdan yeni sürümle yazılmış | programı güncelle (§6.4) |
| 5 | Veritabanı güncellenemedi (migrate) | `backups` içindeki `pre-migrate-*` yedeğine §5.1 ile dönüş* |
| 6 | Yerel sunucu başlatılamadı | güvenlik yazılımı 127.0.0.1'i engelliyor olabilir |
| 7 | WebView2/pencere motoru yok | §6.1 |
| 8 | PDF duman testi başarısız | §6.5 |
| 9 | Geri yükleme (`--geri-yukle`) başarısız | parola/kurtarma anahtarını doğrulayıp yeniden deneyin; `logs/uygulama.log` |

\* Yedekler şifreli de olsa geri yükleme aracı açar — §5.1.

## 8. İndirilen dosyayı doğrulama

Paketler imzasızdır; bütünlüğü `SHA256SUMS.txt` ile doğrulayın.

Windows (PowerShell):

```powershell
Get-FileHash .\kelebek-sinav-<sürüm>-win64-setup.exe -Algorithm SHA256
```

Linux:

```bash
sha256sum -c SHA256SUMS.txt --ignore-missing
```

Çıkan özet `SHA256SUMS.txt` içindeki satırla birebir aynı olmalıdır.

## 9. Programı kaldırma

* **Windows (kurulum paketi):** Ayarlar → Uygulamalar → Kelebek Sınav →
  Kaldır.
* **Windows (taşınabilir):** klasörü silin.
* **Pardus/Linux (.deb):** `sudo apt remove kelebek-sinav`
* **Linux (taşınabilir):** arşivdeki `./kaldir.sh`

Kaldırma işlemi **verilerinizi silmez** — sınav kayıtları ve yedekler §5'teki
klasörlerde durmaya devam eder.
