// M3 tema değiştirici — Top App Bar'a yerleştirilir. Açık/karanlık ikon arasında
// geçiş yapar; tercih localStorage'a yazılır (CLAUDE.md §7.5).
//
// Erişilebilirlik: yoğunluğa duyarlı hedef, aria-label, görünür focus halkası.

import { useTheme } from "../hooks/useTheme";
import Icon from "./Icon";

interface Props {
  className?: string;
}

export default function ThemeSwitcher({ className = "" }: Props) {
  const { isDark, toggle } = useTheme();
  const label = isDark ? "Açık temaya geç" : "Karanlık temaya geç";
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      aria-pressed={isDark}
      className={`group relative inline-flex h-[var(--ks-control-height)] w-[var(--ks-control-height)] items-center justify-center overflow-hidden rounded-shape-sm text-on-surface-variant transition hover:bg-on-surface/8 hover:text-on-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${className}`}
    >
      {/* M3 state layer — parent overflow-hidden + rounded-full örtüyü kırpar. */}
      <span aria-hidden="true" className="state-layer" />
      <Icon name={isDark ? "light_mode" : "dark_mode"} />
    </button>
  );
}
