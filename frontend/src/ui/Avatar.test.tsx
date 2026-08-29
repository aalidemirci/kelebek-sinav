// Avatar (Tur 548) — foto/fallback + erişilebilirlik testleri.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Avatar from "./Avatar";

const DATA_URI = "data:image/jpeg;base64,dGVzdA==";

describe("Avatar", () => {
  it("src verilince img render eder (dekoratif — aria-hidden)", () => {
    const { container } = render(<Avatar src={DATA_URI} name="Ali Demirci" />);
    const img = container.querySelector("img");
    expect(img).not.toBeNull();
    expect(img).toHaveAttribute("src", DATA_URI);
    expect(img).toHaveAttribute("aria-hidden", "true");
  });

  it("src yoksa baş-harf fallback (Türkçe büyütme)", () => {
    render(<Avatar name="istanbul Veli" />);
    expect(screen.getByText("İ")).toBeInTheDocument();
  });

  it("label verilince erişilebilir ad taşır", () => {
    render(<Avatar src={DATA_URI} name="Ali" label="Ali'nin fotoğrafı" />);
    expect(screen.getByAltText("Ali'nin fotoğrafı")).toBeInTheDocument();
  });

  it("boş ad için ? fallback", () => {
    render(<Avatar name="  " />);
    expect(screen.getByText("?")).toBeInTheDocument();
  });
});
