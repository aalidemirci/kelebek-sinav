// Liste satır stilleri (Tur 196, talep f) — tek doğruluk kaynağı.
//
// Proje genelinde ortak bir Table bileşeni yok; listeler heterojen markup ile
// (<tr>, tıklanabilir <button>/<Link>, <li>) render ediliyor. Tutarlı "imleç hangi
// satırdaysa o satır hafifçe renklenir" (hover-follow) davranışı için bu sabit tüm
// liste satırlarına uygulanır.
//
// M3: hover state layer %8 opaklıkta on-surface örtüsü (frontend-m3.md "State layer").
// %8 değeri --md-state-hover token'ıyla aynı (Tur 313). Bu satır-tinti deseni (örtü
// span'ı YERİNE doğrudan bg) tablo satırları için bilinçli — heterojen satır markup'ına
// absolute örtü span'ı eklemek pratik değil; `.state-layer` sınıfı `group relative
// overflow-hidden` kaplar içindir (Button/NavMenu/Snackbar vb.).
// `transition-colors` yumuşak geçiş (prefers-reduced-motion'a Tailwind saygı duyar).
// Focus halkasını/satır kenarlığını DEĞİŞTİRMEZ — yalnız hover örtüsü ekler.
export const ROW_HOVER = "transition-colors hover:bg-on-surface/8";
