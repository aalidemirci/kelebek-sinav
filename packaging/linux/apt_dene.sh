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

# Debian 11 güvenlik deposunun SON TUTARLI anlık görüntüsü. İş akışındaki
# kurulum provası adımı (checkout'tan ÖNCE koştuğu için bu dosyayı okuyamaz)
# aynı tarihi taşır — ikisi BİRLİKTE değişir (koruma: test_apt_dene.py).
APT_BULLSEYE_GUVENLIK_ANLIK="${APT_BULLSEYE_GUVENLIK_ANLIK:-20260903T000000Z}"

# apt_bullseye_guvenlik_kaynagini_sabitle
# 19.09.2026 vakası: v2026.9.0-beta.6 etiket koşusu Linux paketinde düştü —
# `libglib2.0-0_2.66.8-1+deb11u8` için 404, ÜÇ denemede de. Bu kez sebep geçici
# ayna tutarsızlığı DEĞİL: Debian 11 (bullseye) uzun dönem desteği 31.08.2026'da
# bitti ve `bullseye-security` deposunun paket havuzu 03-05.09.2026 arasında
# boşaltıldı; dizini (Packages) ise hâlâ silinen .deb'lere işaret ediyor. Canlı
# kaynak açık kaldıkça `apt-get install` KALICI 404 alır, yeniden deneme çözmez
# (04.09.2026'daki libperl 404'ü aynı boşaltmanın ilk belirtisiydi).
#
# Kaynağı KAPATMAK çözüm değildir (denendi): temiz `debian:11` imajında temel
# paketler güvenlik sürümünde kuruludur; ana depodaki eşleri birebir sürüm ister
# (perl ↔ perl-base) ve `git` kurulumu "held broken packages" ile düşer. Çözüm
# kaynağı Debian'ın tarihli arşivine (snapshot.debian.org) SABİTLEMEKTİR: o
# tarihte dizin ve havuz eksiksizdir ve hiç değişmez. `check-valid-until=no`
# şarttır — arşivdeki Release dosyasının geçerlilik süresi dolmuştur.
#
# Ürüne etkisi yoktur: pango/glib/fontconfig pakete GÖMÜLMEZ, hedef makinenin
# (Pardus 21) kendi deposundan gelir. Yalnız tek satırlı `deb …` biçimi işlenir —
# bullseye imajları deb822 (`*.sources`) kullanmaz; başka dağıtımda işlev
# etkisizdir. `APT_KAYNAK_KOKU` testler içindir (gerçek /etc/apt'ye dokunmadan).
apt_bullseye_guvenlik_kaynagini_sabitle() {
    local kok="${APT_KAYNAK_KOKU:-/etc/apt}"
    local yeni="deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/${APT_BULLSEYE_GUVENLIK_ANLIK} bullseye-security main"
    local dosya
    for dosya in "$kok/sources.list" "$kok"/sources.list.d/*.list; do
        if [ ! -f "$dosya" ] || [ ! -w "$dosya" ]; then
            continue
        fi
        # Yalnız CANLI aynaya bakan etkin satır değişir; arşive çevrilmiş satır
        # ikinci çağrıda eşleşmez (idempotent), yorum satırlarına dokunulmaz.
        if grep -E '^[[:space:]]*deb[[:space:]].*bullseye-security' "$dosya" |
            grep -qv 'snapshot\.debian\.org'; then
            sed -i -E "/snapshot\.debian\.org/! s#^[[:space:]]*deb[[:space:]].*bullseye-security.*\$#${yeni}#" "$dosya"
            echo "BİLGİ: $dosya içindeki bullseye-security kaynağı tarihli arşive sabitlendi" \
                "(${APT_BULLSEYE_GUVENLIK_ANLIK}; Debian 11 LTS bitti, canlı havuz boş)." >&2
        fi
    done
}

# apt_dene <apt komutu ve argümanları>
# Her denemede: apt-get update + verilen komut. Başarısızlıkta listeler silinip
# artan bekleme ile yeniden denenir. Deneme sayısı APT_AZAMI_DENEME ile değişir.
apt_dene() {
    local azami="${APT_AZAMI_DENEME:-3}"
    local bekleme="${APT_BEKLEME_SANIYE:-10}"
    local deneme=1

    # Kalıcı 404 kaynağı önce arşive sabitlenir (idempotent; bullseye dışında etkisiz).
    apt_bullseye_guvenlik_kaynagini_sabitle

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
