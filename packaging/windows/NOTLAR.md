> **GÜNCELLEME 24.07.2026:** Windows yolu artık CI'da uçtan uca YEŞİL (setup.exe + portable.zip üretiliyor, Türkçe PDF duman testi gömülü DejaVu ile geçiyor, `--autotest` çıkış 0). Aşağıdaki varsayım tablosu ilk koşudan önce yazılmıştı; doğrulananlar artık kesindir. Koşuda bulunan üç gerçek kusur (PS1 BOM'suzluğu, MSYS2 python gölgelemesi, paket içi fontconfig) düzeltildi.

# Windows paketleme — doğrulanmamış varsayımlar ve ilk koşu çek-listesi

> **Bu klasördeki hiçbir dosya Windows'ta çalıştırılmadı.** Geliştirme ortamı
> Linux + Docker'dır; Windows paketi ancak bir Windows makinede veya GitHub
> Actions `windows-latest` koşucusunda üretilebilir. Aşağıdaki maddeler
> "yazıldı ama sınanmadı" durumundadır; ilk Windows koşusunda sırayla
> doğrulanmalı ve bu dosya güncellenmelidir.

## 1. Doğrulanması gereken varsayımlar

| # | Varsayım | Nerede | Yanlışsa belirtisi |
|---|---|---|---|
| W1 | MSYS2 `mingw-w64-x86_64-ntldd-git` paket adı doğru | CI iş akışı, `dll_kapanisi.py` | pacman "target not found"; `objdump` yedeğine düşülür (betik bunu zaten yapar) |
| W2 | WeasyPrint'in aradığı DLL adları `libpango-1.0-0.dll`, `libpangoft2-1.0-0.dll`, `libharfbuzz-0.dll`, `libgobject-2.0-0.dll`, `libfontconfig-1.dll` desenlerine uyuyor | `dll_kapanisi.py::SEED_PATTERNS` | `--pdf-duman` "cannot load library" ile çöker |
| W3 | `WEASYPRINT_DLL_DIRECTORIES` paket kökünü göstermek yeterli (WeasyPrint ≥60) | `rthook_ks.py` | aynı hata; alternatif `os.add_dll_directory()` |
| W4 | fontconfig `<dir>` mutlak yol + `<cachedir>` yazılabilir dizin kabul ediyor | `fonts.conf.tmpl` | PDF üretilir ama font DejaVu değildir → `--pdf-duman` "gömülü DejaVu ile dizilmemiş" hatası verir (duman testi bunu YAKALAR) |
| W5 | WebView2 Evergreen bootstrapper bağlantısı `https://go.microsoft.com/fwlink/p/?LinkId=2124703` | CI iş akışı | indirme 404; elle indirilip `packaging/windows/` altına konur |
| W6 | Inno Setup 6.3+ `ArchitecturesAllowed=x64compatible` destekliyor | `kelebek-sinav.iss` | derleme hatası → `x64` yazılır (6.2 ve öncesi) |
| W7 | `compiler:Languages\Turkish.isl` Inno kurulumunda mevcut | `kelebek-sinav.iss` | derleme hatası → dosya Inno deposundan indirilip eklenir |
| W8 | `PrivilegesRequired=lowest` ile `{autopf}` = `%LOCALAPPDATA%\Programs` | `kelebek-sinav.iss` | kurulum `Program Files`e gitmeye çalışıp yetki ister |
| W9 | pywebview `edgechromium` arka ucu `pythonnet` ile çalışıyor ve PyInstaller ile paketleniyor | `requirements-paketleme.txt`, spec | pencere açılmaz; `webview/lib/*.dll` elle `datas`'a eklenmesi gerekebilir |

## 2. Bilinen Windows tuzakları (kodda karşılığı var)

* **GUI exe'yi PowerShell beklemez.** `console=False` ile derlenen exe `&` ile
  çağrılınca PowerShell hemen döner ve `$LASTEXITCODE` anlamsızdır. `build.ps1`
  bu yüzden duman testlerini `Start-Process -Wait -PassThru` ile koşturur.
* **`sys.stdout`/`sys.stderr` `None`'dır.** Penceresiz derlemede konsol yoktur;
  `print()` `AttributeError` üretir. `giris.py` bu yüzden `print` kullanmaz,
  `sys.stderr`'i `None` kontrolüyle yazar. `desktop/logging_setup.py`
  `--autotest` kipinde `StreamHandler(sys.stderr)` kuruyor; Windows'ta bu
  handler sessizce hiçbir şey yazmaz (çökmez, ama Windows'ta `--autotest`
  çıktısı YALNIZ günlük dosyasındadır — kabuk sahibine bildirildi).
* **MSHTML düşüşü.** pywebview WebView2 bulamazsa eski IE motoruna düşer ve
  React 18 çalışmaz (beyaz pencere). `desktop/window.py` motoru açıkça
  `edgechromium` verir ve registry denetimi yapar — düşüş KODLA ENGELLİ.
* **`%APPDATA%` (Roaming) kullanılmaz.** Gezici profil/OneDrive senkronu açık
  SQLite dosyasını bozar; veri `%LOCALAPPDATA%` altındadır (`desktop/paths.py`).

## 3. İlk Windows koşusu çek-listesi

1. `npm run build` → `frontend\dist` oluştu mu?
2. `powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1`
3. `dist\cikti\pdf-duman.pdf` açılıyor mu, "ĞÜŞİÖÇ ığüşiöç" düzgün görünüyor mu?
   (Duman testi metni zaten pypdf ile doğrular; gözle de bakılmalı.)
4. Kurulum paketini **yönetici olmayan** bir hesapta çalıştır → hiç UAC
   istemesin, `%LOCALAPPDATA%\Programs\Kelebek Sınav` altına kursun.
5. **WebView2 kurulu OLMAYAN** bir makinede/VM'de aç → Türkçe yönlendirme
   diyaloğu çıksın, program çıkış kodu 7 versin (beyaz pencere DEĞİL).
6. Taşınabilir zip'i USB'den çalıştır → MotW olmadığından SmartScreen çıkmamalı.
7. Program açıkken ikinci kez çalıştır → "zaten çalışıyor" (çıkış kodu 2).
8. Defender/AV taraması: onedir olduğu için imzasız da olsa engellenmemeli;
   engellenirse `docs/kurulum.md`'deki istisna adımları güncellenmeli.

## 4. Sonraki sürüm (v2) için

* **Kod imzalama** — Azure Trusted Signing veya SignPath (açık kaynak ücretsiz
  katmanı). İmzalanınca SmartScreen uyarısı ve AV yanlış-pozitif riski düşer.
* **Fixed-Version WebView2** — kilitli/çevrimdışı okul bilgisayarları için
  WebView2'nin sabit sürümünü paketin içine gömen "full" zip varyantı
  (tasarım §5.1). Bu varyant henüz üretilmiyor.
