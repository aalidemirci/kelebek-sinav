// M3 yükleme iskeleti (CLAUDE.md §7.5): içerik inerken yer tutan nabız bloğu.
// "Yükleniyor…" metni yerine sayfanın gerçek düzenini taklit eden gri bloklar →
// algılanan hız + düzen kayması (CLS) azalır.
//
// - Zemin `on-surface/10`: her iki temada (açık/koyu) uyumlu, ince placeholder.
// - `animate-pulse`: index.css'teki global prefers-reduced-motion kuralı süreyi
//   sıfırladığı için hareket hassas kullanıcıda durur (ek `motion-reduce:` gerekmez).
// - `aria-hidden`: iskelet dekoratiftir. Erişilebilir "yükleniyor" duyurusu çağrı
//   yerinde `role="status"` + `aria-busy` + `sr-only` metinle verilir (örnekler
//   KurumBilgisiPage / BildirimPage). Boyut Tailwind genişlik/yükseklik
//   yardımcılarıyla (`h-4 w-32`) verilir; ham px yok.

interface SkeletonProps {
  /** Boyut + ek yerleşim sınıfları (örn. "h-4 w-32"). */
  className?: string;
  /** Yuvarlak iskelet (avatar/ikon yer tutucu). */
  circle?: boolean;
}

export default function Skeleton({ className = "", circle = false }: SkeletonProps) {
  return (
    <span
      aria-hidden="true"
      className={`block animate-pulse bg-on-surface/10 ${circle ? "rounded-full" : "rounded-shape-sm"} ${className}`}
    />
  );
}

interface SkeletonListProps {
  /** Satır (placeholder blok) sayısı. */
  rows?: number;
  /** Dış sarmalayıcıya ek sınıf (örn. kart içi `p-4` boşluğu). */
  className?: string;
}

/**
 * Liste/panel yükleme deseni: erişilebilir bölge (role=status + aria-busy +
 * sr-only "Yükleniyor…") + N satır iskeleti. "Yükleniyor…" metnini değiştirmek
 * için tek satırlık drop-in (C8 rollout). İçerik gating'i ÇAĞRI YERİNDE kalır —
 * bu yalnız yükleme yer-tutucusunu değiştirir.
 */
export function SkeletonList({ rows = 4, className = "" }: SkeletonListProps) {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-live="polite"
      className={`space-y-2 ${className}`.trim()}
    >
      <span className="sr-only">Yükleniyor…</span>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  );
}
