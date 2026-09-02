// "Yeniden başlat gerekli" olayı — backend `restart_gate`'in arayüz ayağı.
// Yedekten geri yükleme uygulandıktan sonra backend TÜM API isteklerini
// 503 `restart_required` ile keser; `lib/api.ts` bu kodu görünce olayı
// yayınlar (sayfa yenilense bile ilk API çağrısında ekran geri gelir),
// geri yükleme akışı da başarıda olayı doğrudan yayınlar. Dinleyen tek yer
// `modules/guvenlik/YenidenBaslatEkrani`dir.

export const YENIDEN_BASLAT_OLAYI = "ks:yeniden-baslat-gerekli";

export function yenidenBaslatGerekliYayinla(): void {
  window.dispatchEvent(new CustomEvent(YENIDEN_BASLAT_OLAYI));
}
