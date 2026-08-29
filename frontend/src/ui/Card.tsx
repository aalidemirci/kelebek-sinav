// M3 kart (CLAUDE.md §7.5): surface-container-low yüzey (M3 elevated card resting
// seviyesi), shape-lg köşe, opsiyonel elevation. Tonal elevation: yükselen yüzey daha
// yüksek surface-container seviyesinde oturur (gölgeye değil, tona yaslanır — Tur 312).

import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  elevation?: 0 | 1 | 2;
}

const ELEVATION: Record<0 | 1 | 2, string> = {
  0: "",
  1: "shadow-elevation-1",
  2: "shadow-elevation-2",
};

export default function Card({ children, className = "", elevation = 0 }: CardProps) {
  return (
    <div
      className={`rounded-shape-lg border border-outline-variant/70 bg-surface-container-lowest ${ELEVATION[elevation]} ${className}`}
    >
      {children}
    </div>
  );
}
