#!/usr/bin/env bash
# =============================================================================
# packaging/linux/apt_dene.sh — apt komutlarını ayna tutarsızlığına karşı sarar
# =============================================================================
# 04.09.2026 vakası: v2026.9.0-beta.5 etiket koşusu `apt-get install git`
# adımında düştü — `libperl5.32_5.32.1-4+deb11u5_amd64.deb` için **404 Not
# Found**. Sebep kodda değil: kap imajının apt indeksi, aynadan kaldırılmış bir
# güvenlik güncellemesine işaret ediyordu (bir edge eski indeksi, depo yeni
# dosyayı sunuyordu). Aynı commit yeniden denemede sorunsuz geçti.
#
# Bu yüzden yeniden deneme ARASINDA `/var/lib/apt/lists/*` SİLİNİR: asıl sorun
# indeksin bayatlığıdır, tek başına `apt-get update` önbellekteki aynı bayat
# indeksi geri getirebilir. `Acquire::Retries` ise ağ kesintisini kapsar ama
# 404'ü kapsamaz (kalıcı hata) — ikisi ayrı sorun sınıfıdır.
#
# Kullanım (kaynak olarak alınır, çalıştırılmaz):
#
#     . "$(dirname "${BASH_SOURCE[0]}")/apt_dene.sh"
#     apt_dene apt-get install -y -qq --no-install-recommends git
#
# `apt-get update` her denemede fonksiyonun KENDİSİ tarafından koşulur; çağıran
# ayrıca update yapmaz.
# =============================================================================

# apt_dene <apt komutu ve argümanları>
# Her denemede: apt-get update + verilen komut. Başarısızlıkta listeler silinip
# artan bekleme ile yeniden denenir. Deneme sayısı APT_AZAMI_DENEME ile değişir.
apt_dene() {
    local azami="${APT_AZAMI_DENEME:-3}"
    local bekleme="${APT_BEKLEME_SANIYE:-10}"
    local deneme=1

    while :; do
        if apt-get update -qq && "$@"; then
            return 0
        fi
        if [ "$deneme" -ge "$azami" ]; then
            echo "HATA: apt komutu $azami denemede de başarısız: $*" >&2
            return 1
        fi
        echo "UYARI: apt $deneme. denemede başarısız (ayna tutarsızlığı olabilir);" \
            "listeler tazelenip yeniden denenecek: $*" >&2
        rm -rf /var/lib/apt/lists/*
        deneme=$((deneme + 1))
        sleep $((deneme * bekleme))
    done
}
