// Tur 122 — M3 Skeleton (yükleme iskeleti) testi: dekoratif (aria-hidden) nabız
// bloğu, boyut sınıfları, circle varyantı. React Testing Library + Vitest.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Skeleton, { SkeletonList } from "./Skeleton";

describe("Skeleton", () => {
  it("aria-hidden dekoratif nabız bloğu + boyut sınıfları basar", () => {
    const { container } = render(<Skeleton className="h-4 w-32" />);
    const el = container.querySelector("span");
    expect(el).toHaveAttribute("aria-hidden", "true");
    expect(el).toHaveClass("animate-pulse", "h-4", "w-32");
  });

  it("varsayılan köşe rounded-shape-sm", () => {
    const { container } = render(<Skeleton />);
    expect(container.querySelector("span")).toHaveClass("rounded-shape-sm");
  });

  it("circle=true rounded-full uygular", () => {
    const { container } = render(<Skeleton circle className="h-10 w-10" />);
    const el = container.querySelector("span");
    expect(el).toHaveClass("rounded-full");
    expect(el).not.toHaveClass("rounded-shape-sm");
  });

  it("SkeletonList: role=status + aria-busy + sr-only 'Yükleniyor…' + N satır", () => {
    render(<SkeletonList rows={3} />);
    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-busy", "true");
    expect(region).toHaveTextContent("Yükleniyor…");
    expect(region.querySelectorAll("span.animate-pulse")).toHaveLength(3);
  });
});
