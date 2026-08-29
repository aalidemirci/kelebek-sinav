import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import EmptyState from "./EmptyState";

describe("EmptyState", () => {
  it("başlık + açıklama gösterir", () => {
    render(<EmptyState title="Kayıt yok" description="Buradan ekleyin." />);
    expect(screen.getByRole("heading", { name: "Kayıt yok" })).toBeInTheDocument();
    expect(screen.getByText("Buradan ekleyin.")).toBeInTheDocument();
  });

  it("birincil eylem (action) render eder", () => {
    render(<EmptyState title="Boş" action={<button type="button">Ekle</button>} />);
    expect(screen.getByRole("button", { name: "Ekle" })).toBeInTheDocument();
  });

  it("compact varyant tek satır (başlık h3 kartı yok)", () => {
    const { container } = render(<EmptyState compact title="Satır yok" />);
    expect(screen.getByText("Satır yok")).toBeInTheDocument();
    expect(container.querySelector("h3")).toBeNull();
  });
});
