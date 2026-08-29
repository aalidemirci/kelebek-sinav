import { describe, it, expect } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { z } from "zod";

import { useFormErrors } from "./useFormErrors";
import { ApiError } from "../lib/api";

const schema = z.object({
  title: z.string().trim().min(1, "Başlık zorunlu."),
  count: z.number().min(1, "En az 1 olmalı."),
});

describe("useFormErrors", () => {
  it("validate: geçersiz değerlerde alan-bazlı hata + false döner", () => {
    const { result } = renderHook(() => useFormErrors());
    let ok = true;
    act(() => {
      ok = result.current.validate(schema, { title: "", count: 0 });
    });
    expect(ok).toBe(false);
    expect(result.current.errors.title).toBe("Başlık zorunlu.");
    expect(result.current.errors.count).toBe("En az 1 olmalı.");
  });

  it("validate: geçerli değerlerde hataları temizler + true döner", () => {
    const { result } = renderHook(() => useFormErrors());
    act(() => {
      result.current.setFieldError("title", "eski hata");
    });
    let ok = false;
    act(() => {
      ok = result.current.validate(schema, { title: "X", count: 3 });
    });
    expect(ok).toBe(true);
    expect(result.current.errors.title).toBeUndefined();
  });

  it("applyApiError: backend fields'i alan-bazlı errors'a yansıtır + ilk alanı döner", () => {
    const { result } = renderHook(() => useFormErrors());
    let first: string | null = null;
    act(() => {
      first = result.current.applyApiError(
        new ApiError(400, "validation_error", "hata", {
          title: ["Sunucu: başlık çakışıyor."],
          count: "Geçersiz sayı.",
        }),
      );
    });
    expect(first).toBe("title");
    expect(result.current.errors.title).toBe("Sunucu: başlık çakışıyor.");
    expect(result.current.errors.count).toBe("Geçersiz sayı.");
  });

  it("applyApiError: ApiError olmayan girdide null döner, errors değişmez", () => {
    const { result } = renderHook(() => useFormErrors());
    let first: string | null = "x";
    act(() => {
      first = result.current.applyApiError(new Error("ağ hatası"));
    });
    expect(first).toBeNull();
    expect(result.current.errors).toEqual({});
  });

  it("clearErrors: tüm hataları temizler", () => {
    const { result } = renderHook(() => useFormErrors());
    act(() => {
      result.current.setFieldError("title", "hata");
    });
    expect(result.current.errors.title).toBe("hata");
    act(() => {
      result.current.clearErrors();
    });
    expect(result.current.errors).toEqual({});
  });
});
