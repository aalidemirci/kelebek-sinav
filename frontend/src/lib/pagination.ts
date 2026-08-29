// DRF sayfalı yanıt tipi + çözücü (Tur 615 — F-fe DRY konsolidasyonu).
// 20+ modül api.ts'i kendi `Paginated<T>` kopyasını, 10'u özdeş `unwrap`
// kopyasını taşıyordu — tek doğruluk kaynağı burası. Yeni kod bunu kullanır.

/** DRF PageNumber/LimitOffset sayfalı liste yanıtı (kanonik tam şekil). */
export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/** DRF list uçları sayfalıdır; bazı özel action'lar düz dizi döndürür —
 * iki biçimi de diziye indirger. */
export function unwrap<T>(data: Paginated<T> | T[]): T[] {
  return Array.isArray(data) ? data : data.results;
}
