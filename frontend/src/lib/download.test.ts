// saveBlob DOM akışı testi (Tur 535): createObjectURL → <a download> → revoke.

import { afterEach, describe, expect, it, vi } from "vitest";

import { saveBlob } from "./download";

describe("saveBlob", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("blob için geçici URL açar, bağlantıyı tıklar ve URL'yi gecikmeli bırakır", () => {
    vi.useFakeTimers();
    const createObjectURL = vi.fn(() => "blob:test-url");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL,
      revokeObjectURL,
    });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    saveBlob(new Blob(["test"]), "dosya.xlsx");

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(click).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).not.toHaveBeenCalled();
    // Bağlantı DOM'da bırakılmadı.
    expect(document.querySelector("a[download]")).toBeNull();

    vi.advanceTimersByTime(1_000);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:test-url");
  });
});
