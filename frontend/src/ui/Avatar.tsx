// M3 Avatar (Tur 548) — öğrenci/kişi görseli: foto (data-URI/objectURL) varsa
// gösterir, yoksa baş-harf fallback. Dekoratif kullanım varsayılan (ad zaten
// satırda yazar) → aria-hidden; anlam taşıyorsa `label` verilir. Token tüketir
// (CLAUDE.md §7.5): ham renk/px yok; boyutlar Tailwind 4px ölçeğinden.

export type AvatarSize = "sm" | "md" | "lg";

const SIZE_CLASS: Record<AvatarSize, string> = {
  sm: "h-10 w-10 text-label-medium", // 40px — liste satırı
  md: "h-12 w-12 text-label-large", // 48px — kart başlığı
  lg: "h-24 w-24 text-headline-small", // 96px — sicil dialogu
};

interface AvatarProps {
  /** Foto kaynağı (data-URI veya objectURL); yoksa baş-harf fallback. */
  src?: string | null;
  /** Baş-harf üretimi için ad (fallback'te ilk harf büyütülür). */
  name: string;
  size?: AvatarSize;
  /** Anlam taşıyan kullanım için erişilebilir ad; verilmezse dekoratif (aria-hidden). */
  label?: string;
  className?: string;
}

function initial(name: string): string {
  const trimmed = name.trim();
  return trimmed ? trimmed[0].toLocaleUpperCase("tr-TR") : "?";
}

export default function Avatar({ src, name, size = "sm", label, className = "" }: AvatarProps) {
  const base =
    `inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full ` +
    `bg-secondary-container text-on-secondary-container ${SIZE_CLASS[size]} ${className}`;
  if (src) {
    return (
      <img
        src={src}
        alt={label ?? ""}
        aria-hidden={label ? undefined : true}
        className={`${base} object-cover`}
      />
    );
  }
  return (
    <span
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={base}
    >
      {initial(name)}
    </span>
  );
}
