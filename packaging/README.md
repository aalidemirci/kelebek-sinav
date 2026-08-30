# packaging/ — paket üretimi

Kullanıcıya yönelik kurulum kılavuzu: **`docs/kurulum.md`**.
Bu dosya paketi ÜRETEN kişi içindir.

## Dosya haritası

```
packaging/
├── requirements-paketleme.txt   PyInstaller + pywebview + (Linux) PyQt5
├── pyinstaller/
│   ├── kelebek_sinav.spec    Windows + Linux ORTAK spec
│   ├── giris.py                 paket giriş noktası + `--pdf-duman` teşhis kipi
│   ├── rthook_ks.py             çalışma-zamanı kancası (DLL/fontconfig/SPA yolu)
│   ├── fonts.conf.tmpl          Windows fontconfig şablonu (gömülü DejaVu)
│   └── fonts.paket.conf         paket içi fontconfig — build.ps1 adım 4b bunu
│                                `_internal/etc/fonts/fonts.conf` üzerine kopyalar
├── fontlar/                     DejaVu Sans 4 kesim + lisans (pakete gömülür)
├── ikonlar/                     logo_uret.py + kelebek-sinav-logo.png +
│                                ikon_uret.py + PNG kesimleri + .ico
├── linux/
│   ├── docker-build.sh          HOST'tan çalıştırılan sarmalayıcı  ← BURADAN BAŞLA
│   ├── build.sh                 kap İÇİNDE koşan asıl derleme
│   ├── test-kurulum.sh          debian:11 + debian:12 kurulum provası
│   ├── kap-ici-test.sh          prova kabının içinde koşan betik
│   ├── debian-control.tmpl      .deb üstverisi (@VERSION@/@SIZE@/@DEPENDS@)
│   ├── postinst / prerm         bakım betikleri (ASCII — aşağıdaki nota bakın)
│   ├── kelebek-sinav.desktop menü kaydı
│   ├── kur.sh / kaldir.sh       taşınabilir .tar.gz kurucusu
│   └── BENIOKU.txt              .tar.gz içindeki kullanıcı notu
└── windows/
    ├── build.ps1                DLL kapanışı + PyInstaller + duman testi + Inno
    ├── dll_kapanisi.py          ntldd/objdump ile WeasyPrint DLL kapanışı
    ├── kelebek-sinav.iss     Inno Setup (yönetici GEREKTİRMEZ)
    └── NOTLAR.md                DOĞRULANMAMIŞ varsayımlar + ilk koşu çek-listesi
```

## Linux paketi üretme

```bash
docker compose run --rm frontend npm run build     # frontend/dist şart
bash packaging/linux/docker-build.sh               # .deb + .tar.gz
bash packaging/linux/test-kurulum.sh               # debian:11 + debian:12 provası
```

Hızlı doğrulama derlemesi (PyQt5 indirilmez, ~5 dk yerine ~2 dk; pencere
açılmaz, yalnız `--autotest`/`--pdf-duman` çalışır):

```bash
KS_WITH_QT=0 bash packaging/linux/docker-build.sh
```

Çıktılar `dist/cikti/` altındadır (`dist/` .gitignore'da).

### Linux tarafında DOĞRULANMAMIŞ kalan

CI/derleme kaplarında ekran (X11/Wayland) yok; **pencere hiç açılmadı**.
KS'nin 29.08.2026 CI koşusunda (TB5) doğrulananlar: paket üretimi, `.deb`
kurulumu (debian:11 + debian:12), `--autotest` zinciri ve Türkçe PDF üretimi.
Doğrulanmayanlar:

* **Qt penceresinin gerçekten açılması.** İlk Pardus koşusunda `kelebek-sinav`
  menüden açılıp arayüzün geldiği görülmelidir.
* **Wayland oturumu.** PyInstaller derlemesinde `libwayland-*` ve `libpulse*`
  uyarıları çıkar; bunlar Qt'nin wayland ve multimedya eklentilerine aittir ve
  paketlenmezler. Pardus varsayılan olarak X11 (`xcb` eklentisi) kullandığı için
  beklenen davranış budur. Wayland oturumunda pencere açılmazsa çözüm
  `QT_QPA_PLATFORM=xcb` ortam değişkenidir; gerekirse `.desktop` dosyasının
  `Exec` satırına eklenir.
* **Qt bağımlılık listesinin eksiksizliği.** `.deb` `Depends` alanındaki X/GL
  paketleri temiz debian:11 + debian:12 kaplarında ÇÖZÜLDÜ (kurulum provası
  yeşil), ama pencere açılmadığı için "yeterli mi" sorusu ancak gerçek bir
  masaüstünde yanıtlanır.

## Windows paketi üretme

Bu depo Linux + Docker üzerinde geliştirilir; Windows paketi **ancak bir
Windows makinede veya CI'da** üretilebilir. Adımlar ve doğrulanmamış
varsayımlar: `packaging/windows/NOTLAR.md`.

## Sürüm

Tek doğruluk kaynağı depo kökündeki **`VERSION`** dosyasıdır (CalVer:
`YYYY.M.N`, ön-sürümde `-dev`). Buradan türetilenler:

* paketlenmiş uygulamanın sürüm damgası (`desktop/version.py`),
* `.deb` sürümü — `-` yerine `~` konur (`2026.7.0-dev` → `2026.7.0~dev`), çünkü
  Debian sıralamasında `~` kesin sürümden ÖNCE gelir,
* artefakt dosya adları,
* `v*` etiketi ile GitHub Release.

## İki dil kuralı

* **Python tanımlayıcıları İngilizce** (depo geneliyle aynı), yorumlar ve
  kullanıcıya görünen iletiler Türkçe.
* **Kabuk betikleri**: değişken adları Türkçe, çıktılar Türkçe.
* **`postinst`/`prerm` ASCII'dir.** Bu iki dosya `/bin/sh` (dash) ile çalışır;
  dash'in ASCII-dışı bayt davranışı dağıtımdan dağıtıma değiştiği için bakım
  betiklerinde Türkçe karakter kullanılmaz. Kullanıcı yalnız `dpkg` çıktısını
  görür, bu betiklerin metnini görmez.

## Yeni bir üçüncü taraf bağımlılık eklerken

`backend/` ağacı pakete **kaynak dosya** olarak kopyalanır; PyInstaller'ın
statik çözümleyicisi orayı TARAMAZ. Backend yeni bir üçüncü taraf paket
import ediyorsa `kelebek_sinav.spec` içindeki `hiddenimports` listesine de
eklenmelidir — yoksa paket geliştirmede çalışır, kurulumda çöker. Gerekçe ve
ayrıntı spec dosyasının başındaki açıklamada.
