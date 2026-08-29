# Teknik borç kütüğü

Buraya giren her kalem **biliniyor ve kabul edilmiş** demektir; denetimlerde
yeniden raporlanmaz (gerekçenin kendisi çürütülmedikçe).

## Açık

- **TB1 — e-Okul PDF parser'ları yok (v1 kararı, B18):** şube listesi
  (OOG01001R070) ve personel listesi (OOK01001R1) PDF'leri v1'de içe
  aktarılamaz; yol xlsx + pano. Gerekçe: pypdf glif/bitişme riskleri OYS
  kodunda belgeli. v2 adayı.
- **TB2 — Ders çizelgesi verisi yalnız Anadolu Lisesi (U4):** diğer okul
  türlerinde havuz boş başlar; elle ekleme + md veri dosyası ekleme yolu açık.
- **TB3 — Şifreli kipte ad-temelli DB sorgusu yok (U3 bedeli):** arama/
  sıralama/teklik selector katmanında Python ile; yeni ad sorgusu ORM
  filtresiyle yazılamaz (DD F5-D5 dersi).
- **TB4 — Gözetmen oto-atama yok (U2):** ders programı verisi olmadığından
  elle seçim; OYS'deki adil-yük sayacı alınmadı.
- **TB6 — Logo v1 geometrik yer tutucu:** `logo_uret.py` koltuk-karesi
  kelebeği üretiyor; markalaşmış bir çizim istenirse `kelebek-sinav-logo.png`
  değiştirilip `ikon_uret.py` yeniden koşulur (sözleşme hazır).

## Kapanan

- **TB5 — F0 paket kapısı (29.08.2026):** paketleme.yml ilk CI koşusu uçtan uca
  YEŞİL — Windows setup.exe + portable.zip, Linux .deb + .tar.gz, debian 11/12
  temiz kurulum provaları ve her iki platformda Türkçe PDF duman testi geçti
  (run 33257833345). DD `NOTLAR.md` W1-W9 varsayımlarından W1/W5 fiilen doğrulandı.
