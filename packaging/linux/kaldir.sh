#!/usr/bin/env bash
# =============================================================================
# kaldir.sh — Taşınabilir kurulumu kaldırır (VERİLER SİLİNMEZ)
# =============================================================================
# Program dosyalarını, kısayolu ve ikonları siler. Sınav kayıtları, yedekler
# ve günlükler ev dizinindeki veri klasöründe KALIR:
#
#     ~/.local/share/kelebek-sinav     (veritabanı + yedekler)
#     ~/.local/state/kelebek-sinav     (günlükler)
#     ~/.cache/kelebek-sinav           (geçici dosyalar)
#
# Veriyi de silmek isterseniz bu klasörleri elle silin — geri dönüşü YOKTUR.
# =============================================================================
set -euo pipefail

HEDEF="$HOME/.local/opt/kelebek-sinav"
BIN="$HOME/.local/bin/kelebek-sinav"
KISAYOL="$HOME/.local/share/applications/kelebek-sinav.desktop"
IKON_KOKU="$HOME/.local/share/icons/hicolor"

rm -rf "$HEDEF"
rm -f "$BIN" "$KISAYOL"
for boyut in 16 24 32 48 64 128 256; do
    rm -f "$IKON_KOKU/${boyut}x${boyut}/apps/kelebek-sinav.png"
done

command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database -q "$HOME/.local/share/applications" || true

echo "Program kaldırıldı. Verileriniz duruyor:"
echo "  $HOME/.local/share/kelebek-sinav"
