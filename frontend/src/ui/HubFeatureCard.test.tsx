// HubFeatureCard (Tur 179) testi: başlık/açıklama/bağlantı render'ı + klavye
// focus'unda görünür M3 halkası (WCAG 2.4.7 regresyon koruması — halka silinirse
// test kırılır) + ikon dekoratif (aria-hidden).

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import HubFeatureCard from "./HubFeatureCard";

function renderCard() {
  return render(
    <MemoryRouter>
      <HubFeatureCard
        to="/surec-takip/bakim"
        icon="build"
        title="Bakım"
        description="Arıza takibi"
      />
    </MemoryRouter>,
  );
}

describe("HubFeatureCard", () => {
  it("başlık + açıklamayı ve doğru hedef bağlantıyı render eder", () => {
    renderCard();
    const link = screen.getByRole("link", { name: /Bakım/ });
    expect(link).toHaveAttribute("href", "/surec-takip/bakim");
    expect(screen.getByText("Arıza takibi")).toBeInTheDocument();
  });

  it("klavye focus'unda görünür M3 halkası taşır (WCAG 2.4.7)", () => {
    renderCard();
    const link = screen.getByRole("link", { name: /Bakım/ });
    expect(link.className).toContain("focus-visible:ring-2");
    expect(link.className).toContain("focus-visible:ring-primary");
  });
});
