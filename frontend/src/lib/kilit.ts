// "Kilit kapısı" olayı — backend kilit kapısının (`apps/okul/lock_middleware`)
// arayüz ayağı. Oturum ortasında bir istek 423 `locked` ya da
// `guvenlik_dosyasi_kayip` alırsa program arayüzün haberi olmadan kilitlenmiş
// ya da güvenlik dosyası kaybolmuştur (kapı anahtar bellekteyken de kapanır).
// `lib/api.ts` bu kodları görünce olayı yayınlar; güvenlik kapısı
// (`modules/guvenlik/GuvenlikKapisi`) dinler ve durumu sunucudan yeniden okur,
// böylece ilgili ekran (kilit ya da "Güvenlik dosyası bulunamadı") hemen görünür.
// `lib/restart.ts` deseni.

export const KILIT_KAPISI_OLAYI = "ks:kilit-kapisi";

/** 423 gövdesindeki kodlar (`lock_middleware`, `shared.exceptions.LockedResponse`). */
export const KILIT_KAPISI_KODLARI: ReadonlySet<string> = new Set([
  "locked",
  "guvenlik_dosyasi_kayip",
]);

export function kilitKapisiYayinla(): void {
  window.dispatchEvent(new CustomEvent(KILIT_KAPISI_OLAYI));
}
