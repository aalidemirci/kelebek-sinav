#!/usr/bin/env bash
# =============================================================================
# packaging/linux/test-kurulum.sh — .deb'i TEMİZ Debian kaplarında sınar
# =============================================================================
# Tasarım §12 F9 kapısı: paket, derlendiği kapta değil, hiçbir geliştirme
# bağımlılığı olmayan TEMİZ bir sistemde kurulup açılabilmelidir.
#
#   debian:11 (bullseye) → Pardus 21 provası
#   debian:12 (bookworm) → Pardus 23 provası
#
# Kullanım (depo kökünden, önce `docker-build.sh` koşmuş olmalı):
#     bash packaging/linux/test-kurulum.sh
#     bash packaging/linux/test-kurulum.sh 12        # yalnız bookworm
# =============================================================================
set -euo pipefail

# Git Bash (Windows) MSYS yol dönüşümü `/paketler` gibi konteyner yollarını
# Windows yoluna çevirip koşuyu kırar (gates.sh ile aynı koruma).
export MSYS_NO_PATHCONV=1

DEPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CIKTI="$DEPO/dist/cikti"
SURUMLER=("${@:-}")
if [ -z "${1:-}" ]; then
    SURUMLER=(11 12)
fi

if ! ls "$CIKTI"/*.deb >/dev/null 2>&1; then
    echo "HATA: $CIKTI içinde .deb yok. Önce: bash packaging/linux/docker-build.sh" >&2
    exit 1
fi

for surum in "${SURUMLER[@]}"; do
    echo
    echo "############ debian:$surum ############"
    docker run --rm \
        -v "$CIKTI:/paketler:ro" \
        -v "$DEPO/packaging/linux/kap-ici-test.sh:/test.sh:ro" \
        "debian:$surum" \
        bash /test.sh
done

echo
echo "== Tüm kurulum provaları başarılı =="
