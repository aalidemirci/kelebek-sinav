# packaging/ — paket üretimi

Kullanıcıya yönelik kurulum kılavuzu: **`docs/kurulum.md`**.
Bu dosya paketi ÜRETEN kişi içindir.

## Dosya haritası

```
packaging/
├── requirements-paketleme.txt   PyInstaller + pywebview + (Linux) PyQt5
├── pyinstaller/
│   ├── kelebek_sinav.spec    Windows + Linux ORTAK spec
│   ├── giris.py                 paket giriş noktası + teşhis kipleri
│   │                            (`--pdf-duman`, `--bagimlilik-duman`)
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
açılmaz, yalnız `--autotest`/`--pdf-duman`/`--bagimlilik-duman` çalışır):

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

### apt komutları ayna tutarsızlığına karşı sarmalı

Linux tarafındaki her `apt-get install`, `packaging/linux/apt_dene.sh` içindeki
`apt_dene` sarmalından geçer: başarısızlıkta `/var/lib/apt/lists/*` silinir ve
artan beklemeyle üç kez denenir. Gerekçe 04.09.2026 vakasıdır — `v2026.9.0-beta.5`
etiket koşusu, kurulum provasının `git` adımında `libperl5.32` için **404 Not
Found** alıp düştü; kap imajının apt indeksi aynadan kaldırılmış bir güvenlik
güncellemesine işaret ediyordu. Aynı commit yeniden denemede sorunsuz geçti.

Listelerin silinmesi kasıtlıdır: tek başına `apt-get update` önbellekteki aynı
bayat indeksi geri getirebilir. `Acquire::Retries` ağ kesintisini kapsar, 404'ü
kapsamaz — ikisi ayrı sorun sınıfıdır. İSTEĞE BAĞLI paketler (Debian 11'de
bulunmayan `libharfbuzz-subset0`) sarmala GİRMEZ: yokluğu beklenen durumdur.

İş akışındaki `git` adımı sarmalı İNLİNE taşır, çünkü o adım checkout'tan önce
koşar ve betik henüz diskte yoktur. Davranış `packaging/tests/test_apt_dene.py`
ile sabitlenir (sahte `apt-get` ile: kurtarma, pes etme, deneme sayısı).

### Yayın hattı (etiket push'undan sonra)

`v*` etiketi `paketleme.yml`'nin `yayin` işini tetikler; iş sırasıyla
`SHA256SUMS.txt` üretir, GitHub Release'i açar ve paketleri **Cloudflare R2**
kovasına (`okulapp-indirme/kelebek-sinav/`) yükler — okullar siteden indirir,
MEB ağında GitHub sık sık engellidir. Kovadaki `SHA256SUMS` dosyası SÜRÜMLÜ
adla yazılır (`SHA256SUMS-<sürüm>.txt`): sabit ad her yayında eski sürümlerin
özetini silerdi.

R2 adımı iki secret ister — `CLOUDFLARE_API_TOKEN` (R2 *Object Read & Write*
izni) ve `CLOUDFLARE_ACCOUNT_ID`. Tanımlı değilse adım uyarı basıp ATLANIR:
secret'ı olmayan bir çatalda da sürüm çıkarılabilmelidir; paketler o durumda
yalnız GitHub Release'te kalır.

Yükleme sonrası **elle kalan tek iş**, `okulapp.org` deposundaki
`src/data/ks-release.json` dosyasını (sürüm, tarih, boyutlar) güncellemektir;
site indirme kartı oradan üretilir ve o deponun `npm run check-releases`
kapısı bayat kalırsa uyarır.

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
