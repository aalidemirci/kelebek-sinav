#!/usr/bin/env bash
# =============================================================================
# packaging/linux/build.sh — Linux paketlerini üretir (.deb + taşınabilir .tar.gz)
# =============================================================================
# BU BETİK KONTEYNER İÇİNDE ÇALIŞIR. Doğru kullanım host'tan:
#
#     bash packaging/linux/docker-build.sh
#
# Doğrudan çalıştırmak yalnız `python:3.12-bullseye` (veya Debian 11 tabanlı)
# bir kap içinde anlamlıdır. Tasarım §5.2: derleme YALNIZ bullseye'da yapılır
# çünkü glibc 2.31, Pardus 21'in tabanıdır — daha yeni bir glibc'de derlenen
# paket Pardus 21'de açılmaz ("GLIBC_2.34 not found").
#
# Adımlar:
#   1. Sistem bağımlılıkları (yalnız DERLEME için; pakete girmez)
#   2. Python bağımlılıkları
#   3. PyInstaller onedir
#   4. Duman testleri: `--autotest` (çıkış 0) + `--pdf-duman` (Türkçe PDF)
#   5. .deb sargısı (dpkg-deb)
#   6. Taşınabilir .tar.gz (+ kur.sh)
#   7. SHA256SUMS.txt
#
# Ortam değişkenleri:
#   KS_WITH_QT=0  → PyQt5/QtWebEngine paketlenmez (hızlı doğrulama derlemesi;
#                   pencere açılmaz, yalnız `--autotest`/`--pdf-duman` çalışır)
#   KS_SKIP_PIP=1 → pip adımını atlar (bağımlılıklar zaten kurulu)
# =============================================================================
set -euo pipefail

DEPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$DEPO"

QT_ILE="${KS_WITH_QT:-1}"
CIKTI="$DEPO/dist/cikti"
PAKET_KOKU="$DEPO/dist/paket"
CALISMA="$DEPO/dist/_build"
GECICI_PAKETLEME="$(mktemp -d)"
trap 'rm -rf "$GECICI_PAKETLEME"' EXIT
DEB_AGACI="$GECICI_PAKETLEME/deb"

SURUM="$(tr -d '[:space:]' < "$DEPO/VERSION")"
# Debian sürüm dizgisinde "-" yukarı akış/revizyon ayırıcısıdır; ön-sürüm
# işareti "~" ile verilir ve "~" kesin sürümden ÖNCE sıralanır (2026.7.0~dev
# < 2026.7.0). Bu sayede dev paketin üstüne kesin sürüm yükseltme sayılır.
DEB_SURUM="${SURUM/-/\~}"
DEB_ADI="kelebek-sinav_${DEB_SURUM}_amd64.deb"
TAR_ADI="kelebek-sinav-${SURUM}-linux-x64.tar.gz"

# .deb bağımlılıkları — tasarım §5.2. Pango/glib/fontconfig Linux'ta BUNDLE
# EDİLMEZ (sistem sürümüyle çakışır); dağıtımın kendi paketleri kullanılır.
# Hepsi Debian 11 ve 12 ana deposunda mevcuttur.
DEPENDS_TEMEL="libpango-1.0-0, libpangoft2-1.0-0, libharfbuzz0b, libfontconfig1, libglib2.0-0, fonts-dejavu-core"
# Qt WebEngine'in sistemden beklediği X/GL/ses kütüphaneleri (PyQt5 tekerleği
# Qt'nin kendisini taşır, ama bu sistem kütüphanelerini taşımaz).
DEPENDS_QT="libgl1, libegl1, libxkbcommon0, libxkbcommon-x11-0, libdbus-1-3, libnss3, libnspr4, libxcomposite1, libxdamage1, libxrandr2, libxtst6, libxi6, libasound2, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0, libxcb-xinerama0, libxcb-xkb1"

APT_TEMEL="libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libfontconfig1 libglib2.0-0 fonts-dejavu-core binutils"
# libharfbuzz-subset0 Debian 11'DE YOKTUR (bookworm ile geldi). WeasyPrint font
# alt-kümeleme için arar, bulamazsa fontu tam gömer — PDF büyür ama üretilir.
# Bu yüzden hem burada hem .deb Depends'inde ZORUNLU DEĞİLDİR (tasarım §5.2'nin
# bağımlılık listesiyle birebir uyumlu).
APT_ISTEGE_BAGLI="libharfbuzz-subset0"
APT_QT="libgl1 libegl1 libxkbcommon0 libxkbcommon-x11-0 libdbus-1-3 libnss3 libnspr4 libxcomposite1 libxdamage1 libxrandr2 libxtst6 libxi6 libasound2 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libxcb-xkb1"

bilgi() { echo "== $*"; }

# --- 1. Sistem bağımlılıkları (derleme kabında) ------------------------------
bilgi "sistem bağımlılıkları"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
# shellcheck disable=SC2086
apt-get install -y -qq --no-install-recommends $APT_TEMEL
# shellcheck disable=SC2086
apt-get install -y -qq --no-install-recommends $APT_ISTEGE_BAGLI 2>/dev/null || \
    echo "   (libharfbuzz-subset0 bu dağıtımda yok — atlandı)"
if [ "$QT_ILE" != "0" ]; then
    # PyInstaller PyQt5'i ÇÖZÜMLEMEK için import eder; libGL olmadan import
    # patlar ("libGL.so.1: cannot open shared object file").
    # shellcheck disable=SC2086
    apt-get install -y -qq --no-install-recommends $APT_QT
fi

# --- 2. Python bağımlılıkları ------------------------------------------------
if [ "${KS_SKIP_PIP:-0}" != "1" ]; then
    bilgi "python bağımlılıkları"
    pip install --no-cache-dir -q -r "$DEPO/backend/requirements.txt"
    PAKETLEME_GEREKSINIM="$DEPO/packaging/requirements-paketleme.txt"
    if [ "$QT_ILE" = "0" ]; then
        # Qt satırlarını atla (indirmesi ~200 MB, doğrulama derlemesinde gereksiz).
        PAKETLEME_GEREKSINIM="$(mktemp)"
        grep -v -E '^(PyQt5|PyQtWebEngine)' \
            "$DEPO/packaging/requirements-paketleme.txt" > "$PAKETLEME_GEREKSINIM"
    fi
    pip install --no-cache-dir -q -r "$PAKETLEME_GEREKSINIM"
fi

# --- 3. Ön koşul: derlenmiş arayüz ------------------------------------------
if [ ! -f "$DEPO/frontend/dist/index.html" ]; then
    echo "HATA: frontend/dist/index.html yok. Önce arayüzü derleyin:" >&2
    echo "      docker compose run --rm frontend npm run build" >&2
    exit 1
fi

# --- 4. PyInstaller ----------------------------------------------------------
bilgi "PyInstaller onedir (Qt: $QT_ILE)"
rm -rf "$PAKET_KOKU" "$CALISMA" "$DEB_AGACI"
mkdir -p "$CIKTI"
KS_WITH_QT="$QT_ILE" pyinstaller \
    --noconfirm --clean --log-level WARN \
    --distpath "$PAKET_KOKU" \
    --workpath "$CALISMA" \
    "$DEPO/packaging/pyinstaller/kelebek_sinav.spec"

UYGULAMA="$PAKET_KOKU/kelebek-sinav/kelebek-sinav"
[ -x "$UYGULAMA" ] || { echo "HATA: çalıştırılabilir üretilmedi: $UYGULAMA" >&2; exit 1; }

bilgi "paket kişisel veri sızıntısı denetimi"
python "$DEPO/packaging/veri_sizintisi.py" "$PAKET_KOKU/kelebek-sinav"

# --- 5. Duman testleri (paketlenmiş çalıştırılabilir üzerinden) --------------
bilgi "duman testi: --pdf-duman"
"$UYGULAMA" --pdf-duman "$CIKTI/pdf-duman.pdf"

bilgi "duman testi: --autotest"
GECICI_VERI="$(mktemp -d)"
KS_APP_HOME="$GECICI_VERI" "$UYGULAMA" --autotest
rm -rf "$GECICI_VERI"

# --- 6. .deb sargısı ---------------------------------------------------------
bilgi ".deb üretimi ($DEB_SURUM)"
mkdir -p "$DEB_AGACI/opt" "$DEB_AGACI/usr/bin" "$DEB_AGACI/usr/share/applications" "$DEB_AGACI/DEBIAN"
cp -a "$PAKET_KOKU/kelebek-sinav" "$DEB_AGACI/opt/kelebek-sinav"
ln -sf /opt/kelebek-sinav/kelebek-sinav "$DEB_AGACI/usr/bin/kelebek-sinav"
cp "$DEPO/packaging/linux/kelebek-sinav.desktop" "$DEB_AGACI/usr/share/applications/"

for boyut in 16 24 32 48 64 128 256; do
    hedef="$DEB_AGACI/usr/share/icons/hicolor/${boyut}x${boyut}/apps"
    mkdir -p "$hedef"
    cp "$DEPO/packaging/ikonlar/kelebek-sinav-${boyut}.png" "$hedef/kelebek-sinav.png"
done

DEPENDS="$DEPENDS_TEMEL"
if [ "$QT_ILE" != "0" ]; then
    DEPENDS="$DEPENDS, $DEPENDS_QT"
fi
BOYUT_KB="$(du -sk "$DEB_AGACI" | cut -f1)"

sed -e "s|@VERSION@|${DEB_SURUM}|" \
    -e "s|@SIZE@|${BOYUT_KB}|" \
    -e "s|@DEPENDS@|${DEPENDS}|" \
    "$DEPO/packaging/linux/debian-control.tmpl" > "$DEB_AGACI/DEBIAN/control"
install -m 0755 "$DEPO/packaging/linux/postinst" "$DEB_AGACI/DEBIAN/postinst"
install -m 0755 "$DEPO/packaging/linux/prerm" "$DEB_AGACI/DEBIAN/prerm"
chmod 0755 "$DEB_AGACI/DEBIAN"

dpkg-deb --root-owner-group --build "$DEB_AGACI" "$CIKTI/$DEB_ADI"

# --- 7. Taşınabilir .tar.gz --------------------------------------------------
bilgi "taşınabilir arşiv"
TAR_KOKU="$GECICI_PAKETLEME/tar"
TAR_AGACI="$TAR_KOKU/kelebek-sinav-${SURUM}"
mkdir -p "$TAR_AGACI"
cp -a "$PAKET_KOKU/kelebek-sinav" "$TAR_AGACI/uygulama"
install -m 0755 "$DEPO/packaging/linux/kur.sh" "$TAR_AGACI/kur.sh"
install -m 0755 "$DEPO/packaging/linux/kaldir.sh" "$TAR_AGACI/kaldir.sh"
cp "$DEPO/packaging/linux/BENIOKU.txt" "$TAR_AGACI/BENIOKU.txt"
cp "$DEPO/packaging/linux/kelebek-sinav.desktop" "$TAR_AGACI/"
mkdir -p "$TAR_AGACI/ikonlar"
cp "$DEPO/packaging/ikonlar/kelebek-sinav-"*.png "$TAR_AGACI/ikonlar/"
tar -czf "$CIKTI/$TAR_ADI" -C "$TAR_KOKU" "kelebek-sinav-${SURUM}"

# --- 8. Sağlama toplamları ---------------------------------------------------
bilgi "SHA256SUMS.txt"
( cd "$CIKTI" && sha256sum "$DEB_ADI" "$TAR_ADI" > SHA256SUMS.txt )

# --- 9. Dosya sahipliğini host kullanıcısına geri ver ------------------------
# Kap root olarak çalışır; aksi hâlde host'ta `dist/` root'a ait kalır ve
# sonraki koşu silemez.
if [ -n "${HOST_UID:-}" ] && [ -n "${HOST_GID:-}" ]; then
    chown -R "$HOST_UID:$HOST_GID" "$DEPO/dist" || true
fi

bilgi "bitti — çıktılar: $CIKTI"
ls -la "$CIKTI"
