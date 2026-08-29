// Vitest global setup (Tur 43, Tur 46).
// `@testing-library/jest-dom` ek matcher'ları (toBeInTheDocument vb.) Vitest'e
// kayıt eder. tsconfig.json `types` listesinde de tanımlı.

import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// Tur 46: jsdom `window.matchMedia` sağlamıyor; ThemeSwitcher/`useTheme` sistem
// tema sorgusu için ona ihtiyaç duyar. Varsayılan açık tema yanıtı ile mock.
if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

// Her testten sonra render edilen DOM'u temizle (yan etki sızıntısını önler).
afterEach(() => {
  cleanup();
});
