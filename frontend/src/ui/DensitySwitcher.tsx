import { useDensity } from "../hooks/useDensity";
import Icon from "./Icon";

interface DensitySwitcherProps {
  collapsed?: boolean;
  className?: string;
}

export default function DensitySwitcher({
  collapsed = false,
  className = "",
}: DensitySwitcherProps) {
  const { isComfortable, toggle } = useDensity();
  const label = isComfortable ? "Kompakt görünüme geç" : "Rahat görünüme geç";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      aria-pressed={isComfortable}
      className={`group relative flex min-h-[var(--ks-control-height)] items-center overflow-hidden rounded-shape-md text-label-large text-on-surface-variant transition hover:bg-on-surface/8 hover:text-on-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
        collapsed ? "w-full justify-center px-2" : "w-full gap-3 px-3"
      } ${className}`}
    >
      <Icon name={isComfortable ? "density_small" : "density_medium"} size="lg" />
      {!collapsed && <span>{isComfortable ? "Rahat görünüm" : "Kompakt görünüm"}</span>}
    </button>
  );
}
