// Tema (açık/karanlık) durumu (CLAUDE.md §7.5 — karanlık tema V2'de token'lar
// üzerinden açılır).
//
// İlk değer mantığı:
//   1. localStorage tercihi (kullanıcı manuel seçmişse)
//   2. tarayıcı `prefers-color-scheme: dark` medya sorgusu
//   3. varsayılan: "light"
//
// Tema değiştiğinde <html data-theme="dark"> attribute'u yazılır → index.css'teki
// alternatif token set devreye girer. Bileşenler tek satır kod değişmeden uyum
// sağlar (token tüketiyorlar).
//
// SSR yok (LAN SPA) — `document.documentElement` her zaman erişilebilir.

import { useCallback, useEffect, useState } from "react";

export type ThemeMode = "light" | "dark";
const STORAGE_KEY = "oys-theme";

declare global {
  interface Window {
    pywebview?: {
      api?: {
        set_titlebar_theme?: (dark: boolean) => Promise<boolean>;
      };
    };
  }
}

function readSavedTheme(): ThemeMode | null {
  if (typeof window === "undefined") return null;
  const v = window.localStorage.getItem(STORAGE_KEY);
  return v === "dark" || v === "light" ? v : null;
}

function systemPrefersDark(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyTheme(mode: ThemeMode): void {
  const root = document.documentElement;
  if (mode === "dark") root.setAttribute("data-theme", "dark");
  else root.removeAttribute("data-theme");
}

function syncNativeTitlebar(mode: ThemeMode): void {
  const setter = window.pywebview?.api?.set_titlebar_theme;
  if (!setter) return;
  void setter(mode === "dark").catch(() => undefined);
}

/** İlk yükleme (uygulama açılır açılmaz uygulanır — FOUC önler). */
export function initThemeFromStorage(): ThemeMode {
  const saved = readSavedTheme();
  const mode: ThemeMode = saved ?? (systemPrefersDark() ? "dark" : "light");
  applyTheme(mode);
  return mode;
}

export function useTheme() {
  const [mode, setMode] = useState<ThemeMode>(() => {
    if (typeof document === "undefined") return "light";
    // initThemeFromStorage main.tsx'te çağrılır → attribute zaten doğru.
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  });

  useEffect(() => {
    syncNativeTitlebar(mode);
  }, [mode]);

  // Kullanıcı bir tercih yapmadıysa sistem temasını canlı takip et.
  useEffect(() => {
    if (readSavedTheme()) return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e: MediaQueryListEvent) => {
      const next: ThemeMode = e.matches ? "dark" : "light";
      applyTheme(next);
      setMode(next);
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const toggle = useCallback(() => {
    setMode((prev) => {
      const next: ThemeMode = prev === "dark" ? "light" : "dark";
      applyTheme(next);
      window.localStorage.setItem(STORAGE_KEY, next);
      return next;
    });
  }, []);

  return { mode, toggle, isDark: mode === "dark" };
}
