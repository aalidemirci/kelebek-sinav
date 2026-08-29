// Material Symbols (self-host) sarmalayıcı (CLAUDE.md §7.5). Boyut `size` prop'u
// ile merkezî eşlemden gelir (F32 — sayfalarda ham text-* ölçeği yazılmaz);
// verilmezse bağlamın font-size'ı geçerlidir (varsayılan 24px = M3 standart, Tur 314).
// İkon-only kullanımda `label` ile erişilebilir ad verin.

export type IconSize = "xs" | "sm" | "base" | "lg" | "xl" | "2xl" | "3xl" | "4xl" | "5xl";

// Tek doğruluk kaynağı: ikon boyutu ↔ tip ölçeği eşlemesi. Sayfalar yalnız
// anlamlı `size` değeri geçer; Tailwind sınıfı burada üretilir.
const SIZE_CLASS: Record<IconSize, string> = {
  xs: "text-xs",
  sm: "text-sm",
  base: "text-base",
  lg: "text-lg",
  xl: "text-xl",
  "2xl": "text-2xl",
  "3xl": "text-3xl",
  "4xl": "text-4xl",
  "5xl": "text-5xl",
};

interface IconProps {
  name: string;
  size?: IconSize;
  className?: string;
  filled?: boolean;
  label?: string;
}

export default function Icon({ name, size, className = "", filled = false, label }: IconProps) {
  const sizeClass = size ? SIZE_CLASS[size] : "";
  return (
    <span
      className={`material-symbols-outlined ${sizeClass} ${className}`.replace(/\s+/g, " ").trim()}
      style={filled ? { fontVariationSettings: '"FILL" 1' } : undefined}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      {name}
    </span>
  );
}
