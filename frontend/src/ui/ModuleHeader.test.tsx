import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import ModuleHeader from "./ModuleHeader";

function renderAt(initial: string) {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route
          path="/zumre/takip"
          element={<ModuleHeader backTo="/zumre" moduleLabel="Zümre" title="Takip Matrisi" />}
        />
        <Route path="/zumre" element={<div>ZÜMRE HUB</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ModuleHeader", () => {
  it("başlık ve modül adını basar", () => {
    renderAt("/zumre/takip");
    expect(screen.getByRole("heading", { name: "Takip Matrisi" })).toBeInTheDocument();
    expect(screen.getByText("Zümre")).toBeInTheDocument();
  });

  it("geri butonu modül köküne gider (erişilebilir ad ile)", async () => {
    renderAt("/zumre/takip");
    const back = screen.getByRole("link", { name: "Zümre ana sayfasına dön" });
    await userEvent.click(back);
    expect(screen.getByText("ZÜMRE HUB")).toBeInTheDocument();
  });
});
