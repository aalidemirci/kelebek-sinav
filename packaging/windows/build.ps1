<#
=============================================================================
 packaging/windows/build.ps1 — Windows paketlerini üretir
=============================================================================
 BU BETİK BU ORTAMDA DOĞRULANMADI — ilk Windows koşusunda sınanacak.
 (Linux'ta yalnız sözdizimi gözden geçirmesi yapıldı; PowerShell çalıştırılmadı.)

 Ön koşullar:
   * Python 3.12 (PATH'te)
   * MSYS2 + `pacman -S mingw-w64-x86_64-pango mingw-w64-x86_64-fontconfig
     mingw-w64-x86_64-ntldd-git`
   * Inno Setup 6.3+ (`iscc.exe` PATH'te) — kurulum paketi için
   * `frontend/dist` derlenmiş olmalı (`npm run build`)

 Kullanım (depo kökünden):
     powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1

 Çıktılar: dist\cikti\
   kelebek-sinav-<sürüm>-win64-setup.exe      (Inno, yönetici GEREKTİRMEZ)
   kelebek-sinav-<sürüm>-win64-portable.zip   (taşınabilir)
   SHA256SUMS.txt
=============================================================================
#>
[CmdletBinding()]
param(
    [string]$MingwBin = "C:\msys64\mingw64\bin",
    # Kullanilacak Python. Bos birakilirsa PATH'ten cozulur AMA mingw64\bin
    # altindakiler ELENIR: MSYS2'nin python.exe'si ayni dizinde durur, PATH'te
    # onde oldugunda gercek Python'u golgeler ve pip bulunamaz (ilk CI
    # kosusunda tam olarak bu oldu).
    [string]$PythonExe = "",
    [switch]$SkipDeps,
    [switch]$SkipInno,
    [switch]$WithoutQt
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Version = (Get-Content (Join-Path $Repo "VERSION") -Raw).Trim()
# Windows sürüm kaynağı yalnız sayı kabul eder ("2026.7.0-dev" → "2026.7.0.0").
$NumericVersion = ($Version -split "-")[0]
while (($NumericVersion -split "\.").Count -lt 4) { $NumericVersion += ".0" }

$DistRoot   = Join-Path $Repo "dist"
$Output     = Join-Path $DistRoot "cikti"
# Ara dizinler platforma özel: Linux derlemesi (docker-build.sh) aynı depoda eş
# zamanlı koşarsa ortak `dist/paket` ağacında ÇARPIŞIRLARDI (build.ps1'in
# Remove-Item'ı kabın yazdığı ağacı siler). Nihai artefaktlar yine dist/cikti'de.
$PackageDir = Join-Path $DistRoot "paket-win"
$WorkDir    = Join-Path $DistRoot "_build-win"
$DllDir     = Join-Path $Repo "packaging\windows\dll"
$AppDir     = Join-Path $PackageDir "kelebek-sinav"
$AppExe     = Join-Path $AppDir "kelebek-sinav.exe"

function Write-Adim([string]$Mesaj) { Write-Host "== $Mesaj" -ForegroundColor Cyan }

# Pencereli (GUI) bir uygulama `&` ile çağrıldığında PowerShell BEKLEMEZ ve
# $LASTEXITCODE anlamsız olur. Paketlenmiş exe `console=False` ile derlendiği
# için duman testleri MUTLAKA bu yardımcıdan geçmelidir.
function Invoke-Uygulama([string]$Yol, [string[]]$Argumanlar, [hashtable]$Ortam = @{}) {
    $eski = @{}
    foreach ($anahtar in $Ortam.Keys) {
        $eski[$anahtar] = [Environment]::GetEnvironmentVariable($anahtar)
        [Environment]::SetEnvironmentVariable($anahtar, $Ortam[$anahtar])
    }
    try {
        $surec = Start-Process -FilePath $Yol -ArgumentList $Argumanlar -Wait -PassThru -NoNewWindow
        return $surec.ExitCode
    } finally {
        foreach ($anahtar in $Ortam.Keys) {
            [Environment]::SetEnvironmentVariable($anahtar, $eski[$anahtar])
        }
    }
}

# --- 1. Ön koşullar ---------------------------------------------------------
Write-Adim "ön koşullar"

if (-not $PythonExe) {
    $mingwTam = try { (Resolve-Path $MingwBin -ErrorAction Stop).Path } catch { $MingwBin }
    $PythonExe = Get-Command python -All -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -and -not $_.Source.StartsWith($mingwTam, "OrdinalIgnoreCase") } |
        Select-Object -First 1 -ExpandProperty Source
}
if (-not $PythonExe) { throw "Python bulunamadı (mingw64 dışında bir python.exe gerekli)." }
& $PythonExe -c "import sys" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Python çalıştırılamadı: $PythonExe" }
Write-Host "    python: $PythonExe"
if (-not (Test-Path (Join-Path $Repo "frontend\dist\index.html"))) {
    throw "frontend/dist/index.html yok. Önce arayüzü derleyin: npm run build"
}

# --- 2. Python bağımlılıkları ----------------------------------------------
if (-not $SkipDeps) {
    Write-Adim "python bağımlılıkları"
    & $PythonExe -m pip install --disable-pip-version-check -q `
        -r (Join-Path $Repo "backend\requirements.txt") `
        -r (Join-Path $Repo "packaging\requirements-paketleme.txt")
    if ($LASTEXITCODE -ne 0) { throw "pip install başarısız." }
}

# --- 3. WeasyPrint DLL kapanışı --------------------------------------------
Write-Adim "DLL kapanışı ($MingwBin)"
# `dll_kapanisi.py` ntldd/objdump aracını PATH'ten çözer. CI bunu zaten yapar;
# yerel kurulumda yalnız -MingwBin verilmiş olabileceği için burada da ekle.
if (-not (($env:PATH -split ";") -contains $MingwBin)) {
    $env:PATH = "$env:PATH;$MingwBin"
}
& $PythonExe (Join-Path $Repo "packaging\windows\dll_kapanisi.py") --mingw-bin $MingwBin --cikti $DllDir
if ($LASTEXITCODE -ne 0) { throw "DLL kapanışı başarısız." }

# --- 4. PyInstaller ---------------------------------------------------------
Write-Adim "PyInstaller onedir"
Remove-Item -Recurse -Force $PackageDir, $WorkDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Output | Out-Null
$env:KS_WITH_QT = if ($WithoutQt) { "0" } else { "1" }
$env:KS_DLL_DIR = $DllDir
& $PythonExe -m PyInstaller --noconfirm --clean --log-level WARN `
    --distpath $PackageDir --workpath $WorkDir `
    (Join-Path $Repo "packaging\pyinstaller\kelebek_sinav.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller başarısız." }
if (-not (Test-Path $AppExe)) { throw "Çalıştırılabilir üretilmedi: $AppExe" }

# Paketleme tanımına yanlışlıkla gerçek veritabanı, medya veya Excel dosyası
# eklenirse dağıtımı burada durdur.
Write-Adim "paket kişisel veri sızıntısı denetimi"
& $PythonExe (Join-Path $Repo "packaging\veri_sizintisi.py") $AppDir
if ($LASTEXITCODE -ne 0) { throw "Paket kişisel veri denetimi başarısız." }

# MEB çizelge verisi (K5): spec Tree yolu bozulursa tohum SESSİZCE boş kalırdı
# (TB2 düşüşü) — pakette dosyanın varlığı ve boş olmadığı burada sabitlenir.
Write-Adim "paket içi katalog verisi denetimi"
$Katalog = Join-Path $AppDir "_internal\data\ders-cizelgeleri\anadolu-lisesi-2025-2026.md"
if (-not (Test-Path $Katalog) -or (Get-Item $Katalog).Length -eq 0) {
    throw "MEB çizelge verisi pakette yok/boş: $Katalog (spec Tree yolu bozulmuş olabilir)."
}

# --- 4b. Paket içi fontconfig yapılandırması --------------------------------
# PyInstaller MSYS2'nin etc/fonts/ ağacını pakete gömüyor ve Windows'ta
# libfontconfig yapılandırmayı DLL'in yanındaki O AĞAÇTAN çözüyor;
# FONTCONFIG_FILE ortam değişkenini dinlemiyor (FC_DEBUG çıktısıyla kanıtlandı).
# Gömülen varsayılan Windows font dizinini tarıyor → Türkçe evrak sistem
# fontuyla diziliyordu. Bu yüzden fontconfig'in baktığı dosyayı biz yazıyoruz.
$FontsConfHedef = Join-Path $AppDir "_internal\etc\fonts\fonts.conf"
$FontsConfKaynak = Join-Path $Repo "packaging\pyinstaller\fonts.paket.conf"
Write-Adim "paket içi fontconfig ($FontsConfHedef)"
New-Item -ItemType Directory -Force -Path (Split-Path $FontsConfHedef) | Out-Null
Copy-Item -Force $FontsConfKaynak $FontsConfHedef
# conf.d bilinçli olarak KORUNUR: içindekiler yalnız çizim tercihleri
# (hinting/antialias); font DİZİNİ eklemezler.

# --- 5. Duman testleri ------------------------------------------------------
# ÖNCE bağımlılık kapısı: eksik bir hiddenimport'u burada yakalamak, sonraki
# testlerin anlaşılmaz hatalarını okumaktan ucuzdur (K7 — CLAUDE.md §2).
Write-Adim "duman testi: --bagimlilik-duman (K7 hiddenimports)"
$kod = Invoke-Uygulama $AppExe @("--bagimlilik-duman")
if ($kod -ne 0) {
    throw "Bağımlılık duman testi BAŞARISIZ (çıkış $kod). spec hiddenimports eksik."
}

Write-Adim "duman testi: --pdf-duman (Türkçe PDF)"
$pdf = Join-Path $Output "pdf-duman.pdf"
$kod = Invoke-Uygulama $AppExe @("--pdf-duman", $pdf)
if ($kod -ne 0) {
    throw "PDF duman testi BAŞARISIZ (çıkış $kod). WeasyPrint DLL kapanışı veya fontconfig eksik."
}
if (-not (Test-Path $pdf)) { throw "PDF üretilmedi: $pdf" }

Write-Adim "duman testi: --autotest"
$gecici = Join-Path ([System.IO.Path]::GetTempPath()) ("ks-" + [Guid]::NewGuid().ToString("N"))
$kod = Invoke-Uygulama $AppExe @("--autotest") @{ "KS_APP_HOME" = $gecici }
Remove-Item -Recurse -Force $gecici -ErrorAction SilentlyContinue
if ($kod -ne 0) { throw "Açılış denetimi BAŞARISIZ (çıkış $kod)." }

# --- 6. Taşınabilir zip -----------------------------------------------------
Write-Adim "taşınabilir zip"
$zip = Join-Path $Output "kelebek-sinav-$Version-win64-portable.zip"
Remove-Item -Force $zip -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $AppDir "*") -DestinationPath $zip

# --- 7. Inno Setup kurulum paketi -------------------------------------------
if (-not $SkipInno) {
    # WebView2 Evergreen önyükleyicisi kurucuya gömülür (tasarım §12 F9 "WebView2
    # gömülü"). Daha önce yalnız CI indiriyordu; yerel/elle üretilen her setup.exe
    # onsuz çıkıyor ve .iss önişlemcisi bunu SESSİZCE düşürüyordu. İndirilemezse
    # paket yine üretilir (iss artık uyarı basar); program ilk açılışta Türkçe
    # yönlendirme verir (desktop/window.py).
    $WebView2Yolu = Join-Path $Repo "packaging\windows\MicrosoftEdgeWebView2Setup.exe"
    if (-not (Test-Path $WebView2Yolu)) {
        Write-Adim "WebView2 Evergreen kurucusu indiriliyor"
        try {
            Invoke-WebRequest -Uri "https://go.microsoft.com/fwlink/p/?LinkId=2124703" `
                -OutFile $WebView2Yolu
        } catch {
            Write-Host "    UYARI: WebView2 kurucusu indirilemedi — paket onsuz üretilecek." -ForegroundColor Yellow
        }
    }

    Write-Adim "Inno Setup"
    $iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue)
    if ($null -eq $iscc) {
        $isccAdaylari = @(
            (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
            (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
            (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
        )
        $isccYolu = $isccAdaylari | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
        if ($isccYolu) {
            $iscc = [PSCustomObject]@{ Source = $isccYolu }
        } else {
            throw "iscc.exe bulunamadı. Inno Setup 6.3+ kurun (choco install innosetup)."
        }
    }
    & $iscc.Source `
        "/DAppVersion=$Version" `
        "/DNumericVersion=$NumericVersion" `
        "/DSourceDir=$AppDir" `
        "/DOutputDir=$Output" `
        (Join-Path $Repo "packaging\windows\kelebek-sinav.iss")
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup başarısız." }
}

# --- 8. Sağlama toplamları --------------------------------------------------
Write-Adim "SHA256SUMS.txt"
$satirlar = @()
Get-ChildItem -Path $Output -Include *.exe, *.zip -File -Recurse | Sort-Object Name | ForEach-Object {
    $ozet = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower()
    $satirlar += "$ozet  $($_.Name)"
}
$satirlar | Set-Content -Path (Join-Path $Output "SHA256SUMS.txt") -Encoding ascii

Write-Adim "bitti — çıktılar: $Output"
Get-ChildItem $Output
