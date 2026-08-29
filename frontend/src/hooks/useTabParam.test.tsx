import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { useTabParam } from "./useTabParam";

const TABS = ["program", "import", "validation"] as const;
type Tab = (typeof TABS)[number];

function wrapperFor(initial: string) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter initialEntries={[initial]}>{children}</MemoryRouter>;
  };
}

/** Kancayı ve o anki URL'i birlikte döndürür — parametre yazımını doğrulamak için. */
function renderTab(initial: string) {
  return renderHook(
    () => ({
      tab: useTabParam<Tab>("tab", TABS, "program"),
      search: useLocation().search,
    }),
    { wrapper: wrapperFor(initial) },
  );
}

describe("useTabParam", () => {
  it("URL'deki geçerli değeri okur", () => {
    const { result } = renderTab("/program?tab=validation");
    expect(result.current.tab[0]).toBe("validation");
  });

  it("parametre yoksa varsayılana düşer", () => {
    const { result } = renderTab("/program");
    expect(result.current.tab[0]).toBe("program");
  });

  it("tanınmayan değer sessizce varsayılana düşer (kırık bağlantı hata üretmez)", () => {
    const { result } = renderTab("/program?tab=olmayan-sekme");
    expect(result.current.tab[0]).toBe("program");
  });

  it("sekme değişimini URL'e yazar", () => {
    const { result } = renderTab("/program");
    act(() => result.current.tab[1]("import"));
    expect(result.current.tab[0]).toBe("import");
    expect(result.current.search).toBe("?tab=import");
  });

  it("varsayılana dönünce parametreyi URL'den siler", () => {
    const { result } = renderTab("/program?tab=import");
    act(() => result.current.tab[1]("program"));
    expect(result.current.search).toBe("");
  });

  it("diğer query parametrelerini korur", () => {
    const { result } = renderTab("/program?kind=teacher&tab=import");
    act(() => result.current.tab[1]("validation"));
    expect(result.current.search).toContain("kind=teacher");
    expect(result.current.search).toContain("tab=validation");
  });
});
