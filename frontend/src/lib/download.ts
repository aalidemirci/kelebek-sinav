// Blob'u tarayıcıda/pywebview penceresinde dosya olarak indirtir (Tur 535, ADR-0034).
// Tüm Excel, PDF, ek ve kurtarma anahtarı indirmelerinin ortak hedefidir.
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // WebView indirme isteğini olay döngüsünün sonunda devralır. URL'yi aynı çağrı
  // yığını içinde bırakmak bazı motorlarda indirmeyi başlamadan iptal edebilir.
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
}
