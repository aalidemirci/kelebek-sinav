import { useCallback, useEffect, useState } from "react";

export type DensityMode = "compact" | "comfortable";

const STORAGE_KEY = "kelebek-sinav-density";
const CHANGE_EVENT = "kelebek-sinav-density-change";

function readSavedDensity(): DensityMode {
  if (typeof window === "undefined") return "compact";
  return window.localStorage.getItem(STORAGE_KEY) === "comfortable" ? "comfortable" : "compact";
}

function applyDensity(mode: DensityMode): void {
  document.documentElement.setAttribute("data-density", mode);
}

export function initDensityFromStorage(): DensityMode {
  const mode = readSavedDensity();
  applyDensity(mode);
  return mode;
}

export function useDensity() {
  const [mode, setMode] = useState<DensityMode>(() => {
    if (typeof document === "undefined") return "compact";
    return document.documentElement.getAttribute("data-density") === "comfortable"
      ? "comfortable"
      : "compact";
  });

  useEffect(() => {
    const sync = () => setMode(readSavedDensity());
    window.addEventListener(CHANGE_EVENT, sync);
    return () => window.removeEventListener(CHANGE_EVENT, sync);
  }, []);

  const toggle = useCallback(() => {
    setMode((current) => {
      const next: DensityMode = current === "compact" ? "comfortable" : "compact";
      applyDensity(next);
      window.localStorage.setItem(STORAGE_KEY, next);
      window.dispatchEvent(new Event(CHANGE_EVENT));
      return next;
    });
  }, []);

  return { mode, toggle, isComfortable: mode === "comfortable" };
}
