// Masaüstü butonu: kompakt modda 36px, rahat/dokunmatik modda 48px.

import type { ButtonHTMLAttributes, ReactNode } from "react";

import Icon from "./Icon";

type Variant = "filled" | "tonal" | "outlined" | "text";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  icon?: string;
  block?: boolean;
  children: ReactNode;
}

const VARIANT: Record<Variant, string> = {
  filled: "bg-primary text-on-primary shadow-elevation-1 hover:shadow-elevation-2",
  tonal:
    "border border-secondary/10 bg-secondary-container text-on-secondary-container hover:border-secondary/20",
  outlined:
    "border border-outline-variant bg-surface-container-lowest text-primary hover:border-primary/40",
  text: "text-primary hover:bg-primary/8",
};

export default function Button({
  variant = "filled",
  icon,
  block = false,
  children,
  className = "",
  ...rest
}: ButtonProps) {
  const pad = variant === "text" ? "px-2.5" : "px-4";
  return (
    <button
      className={`group relative inline-flex min-h-[var(--ks-control-height)] items-center justify-center gap-2 overflow-hidden rounded-shape-md ${pad} text-label-large font-semibold transition-all duration-short-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:pointer-events-none disabled:opacity-40 disabled:shadow-none ${VARIANT[variant]} ${block ? "w-full" : ""} ${className}`}
      {...rest}
    >
      <span aria-hidden="true" className="state-layer" />
      {icon && <Icon name={icon} size="lg" className="relative z-10" />}
      <span className="relative z-10">{children}</span>
    </button>
  );
}
