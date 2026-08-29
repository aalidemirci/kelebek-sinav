// useAutosave — sunucu-taraflı oto-kayıt hook'u (Tur 147) birim testi.
// Kapsam: debounce + coalesce, başarı durumu, hata → pending korunur + retry,
// flush (debounce beklemeden), enabled=false, markSaved.
//
// Fake timer + async: vi.advanceTimersByTimeAsync hem zamanlayıcıyı tetikler hem
// mikrotask kuyruğunu boşaltır (save Promise'i çözülür).

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAutosave } from "./useAutosave";

describe("useAutosave", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("debounce ile birden fazla değişikliği tek kayıtta birleştirir", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() =>
      useAutosave<{ a: string; b: string }>({ save, delayMs: 1000 }),
    );

    act(() => {
      result.current.notifyChange({ a: "1" });
      result.current.notifyChange({ b: "2" });
    });
    expect(result.current.status).toBe("pending");
    expect(save).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(save).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledWith({ a: "1", b: "2" });
    expect(result.current.status).toBe("saved");
    expect(result.current.lastSavedAt).toBeInstanceOf(Date);
  });

  it("hata → status 'error', pending korunur, retry yeniden dener", async () => {
    const save = vi
      .fn()
      .mockRejectedValueOnce(new Error("ağ hatası"))
      .mockResolvedValueOnce(undefined);
    const { result } = renderHook(() => useAutosave<{ a: string }>({ save, delayMs: 500 }));

    act(() => result.current.notifyChange({ a: "x" }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(result.current.status).toBe("error");
    expect(save).toHaveBeenCalledTimes(1);

    await act(async () => {
      result.current.retry();
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.status).toBe("saved");
    expect(save).toHaveBeenCalledTimes(2);
    expect(save).toHaveBeenLastCalledWith({ a: "x" });
  });

  it("flush bekleyeni hemen yazar (debounce beklemeden)", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useAutosave<{ a: string }>({ save, delayMs: 5000 }));

    act(() => result.current.notifyChange({ a: "hemen" }));
    let ok: boolean | undefined;
    await act(async () => {
      ok = await result.current.flush();
    });
    expect(ok).toBe(true);
    expect(save).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledWith({ a: "hemen" });
  });

  it("enabled=false iken notifyChange yok sayılır", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() =>
      useAutosave<{ a: string }>({ save, delayMs: 100, enabled: false }),
    );
    act(() => result.current.notifyChange({ a: "x" }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(save).not.toHaveBeenCalled();
    expect(result.current.status).toBe("idle");
  });

  it("markSaved pending'i temizler ve 'saved' gösterir", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useAutosave<{ a: string }>({ save, delayMs: 5000 }));
    act(() => result.current.notifyChange({ a: "x" }));
    act(() => result.current.markSaved());
    expect(result.current.status).toBe("saved");
    // pending temizlendi → debounce dolsa da save çağrılmaz.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(save).not.toHaveBeenCalled();
  });
});
