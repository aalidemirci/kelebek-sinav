import { describe, expect, it } from "vitest";

import { unwrap, type Paginated } from "./pagination";

describe("unwrap", () => {
  it("sayfalı yanıttan results dizisini çıkarır", () => {
    const page: Paginated<number> = { count: 2, next: null, previous: null, results: [1, 2] };
    expect(unwrap(page)).toEqual([1, 2]);
  });

  it("düz diziyi olduğu gibi döndürür", () => {
    expect(unwrap([3, 4])).toEqual([3, 4]);
  });

  it("boş sonuç listesini korur", () => {
    const page: Paginated<string> = { count: 0, next: null, previous: null, results: [] };
    expect(unwrap(page)).toEqual([]);
  });
});
