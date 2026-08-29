import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { initDensityFromStorage, useDensity } from "./useDensity";

describe("useDensity", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-density");
  });

  it("kayıtlı tercih yoksa kompakt yoğunluğu uygular", () => {
    expect(initDensityFromStorage()).toBe("compact");
    expect(document.documentElement).toHaveAttribute("data-density", "compact");
  });

  it("rahat yoğunluğu kalıcı olarak saklar", () => {
    initDensityFromStorage();
    const { result } = renderHook(() => useDensity());

    act(() => result.current.toggle());

    expect(result.current.isComfortable).toBe(true);
    expect(window.localStorage.getItem("kelebek-sinav-density")).toBe("comfortable");
    expect(document.documentElement).toHaveAttribute("data-density", "comfortable");
  });
});
