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

/**
 * İndirilen dosyanın adı: belge adı + oturum/takvim adı + tarih (docs/sozluk.md §3).
 * `dosyaAdi(["Salon Sınav Evrakı", "1. Ortak Sınav", "16.11.2026"], "pdf")`
 * → `Salon-Sınav-Evrakı_1-Ortak-Sınav_16.11.2026.pdf`. Kimlik numaralı eski
 * adlar (`r7_oturum_3.pdf`) masaüstünde hangi sınava ait olduğunu söylemiyordu.
 * Türkçe harfler korunur; yalnız dosya sistemlerinin yasakladığı karakterler
 * atılır, boşluklar tireye döner, boş parça düşer.
 */
export function dosyaAdi(parts: (string | null | undefined)[], ext: string): string {
  const temiz = parts
    .map((part) =>
      (part ?? "")
        // Windows'un yasakladığı dokuz karakter; ters bölü de dahil (yol ayracıdır).
        .replace(/[\\/:*?"<>|]/g, "")
        .replace(/[.\s]+$/g, "")
        .trim()
        .replace(/\s+/g, "-")
        .replace(/-{2,}/g, "-")
        .replace(/\.-/g, "-"),
    )
    .filter(Boolean);
  const govde = temiz.join("_") || "belge";
  return `${govde}.${ext.replace(/^\./, "")}`;
}
