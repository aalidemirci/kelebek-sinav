#!/usr/bin/env bash
# =============================================================================
# kap-ici-test.sh — TEMİZ bir Debian kabında .deb kurulum provası
# =============================================================================
# `test-kurulum.sh` tarafından debian:11 ve debian:12 kaplarının İÇİNDE
# çalıştırılır (tasarım §12 F9: "kap-ici-test debian 11+12" — Pardus 21 bullseye,
# Pardus 23 bookworm tabanlıdır).
#
# Sınananlar:
#   1. dpkg -i + apt-get -f install ile bağımlılıkların gerçekten çözülmesi
#   2. `--autotest` → ÇIKIŞ KODU 0 (açılış zinciri: kilit, yedek, göç, sunucu)
#   3. `--bagimlilik-duman` → üçüncü taraf modüller pakette mi (K7)
#   4. `--pdf-duman` → Türkçe metinli PDF üretimi + pypdf ile geri okuma
#   5. Dosya yerleşimi (menü kaydı, ikon, /usr/bin bağlantısı)
#   6. Temiz kaldırma
# =============================================================================
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

# Yerelde `test-kurulum.sh` paketleri /paketler'e bağlar; CI'da artefakt başka
# bir dizine iner → PAKET_DIZINI ile geçersiz kılınır.
PAKET_DIZINI="${PAKET_DIZINI:-/paketler}"

echo "== dağıtım"
head -2 /etc/os-release

DEB="$(find "$PAKET_DIZINI" -maxdepth 1 -name '*.deb' | sort | head -1)"
[ -n "$DEB" ] || { echo "HATA: $PAKET_DIZINI içinde .deb yok" >&2; exit 1; }
echo "== paket: $DEB"

echo "== dpkg -i (bağımlılıklar eksik olabilir)"
dpkg -i "$DEB" || true

echo "== apt-get -f install (bağımlılık çözümü)"
# `apt_dene` her denemede önce `apt-get update` koşar; ayrı update adımı
# yoktur — ayna tutarsızlığında listeler tazelenip yeniden denenir.
. "$(dirname "${BASH_SOURCE[0]}")/apt_dene.sh"
apt_dene apt-get -f install -y -qq

echo "== paket durumu"
dpkg -s kelebek-sinav | grep -E '^(Package|Version|Status|Depends)'

echo "== dosya yerleşimi"
test -x /opt/kelebek-sinav/kelebek-sinav
test -L /usr/bin/kelebek-sinav
test -f /usr/share/applications/kelebek-sinav.desktop
test -f /usr/share/icons/hicolor/48x48/apps/kelebek-sinav.png
# MEB çizelge verisi (K5): spec Tree yolu bozulursa tohum SESSİZCE boş kalırdı
# (TB2 düşüşü) — dosyanın varlığı ve boş olmadığı burada sabitlenir.
test -s /opt/kelebek-sinav/_internal/data/ders-cizelgeleri/anadolu-lisesi-2025.md
test -s /opt/kelebek-sinav/_internal/data/ders-cizelgeleri/ders-adi-takma-adlari.md

echo "== --bagimlilik-duman (K7: üçüncü taraf modüller pakette mi)"
kelebek-sinav --bagimlilik-duman

echo "== --pdf-duman (Türkçe PDF + font doğrulaması)"
kelebek-sinav --pdf-duman /tmp/duman.pdf
test -s /tmp/duman.pdf

echo "== --autotest (açılış zinciri; çıkış kodu 0 beklenir)"
kelebek-sinav --autotest

echo "== ikinci --autotest (var olan veritabanı üzerinde)"
kelebek-sinav --autotest

echo "== kaldırma"
dpkg -r kelebek-sinav
test ! -e /opt/kelebek-sinav
test ! -e /usr/bin/kelebek-sinav

echo "TAMAM"
