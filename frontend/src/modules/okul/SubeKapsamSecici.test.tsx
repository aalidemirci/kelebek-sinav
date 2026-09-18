// Şube kapsamı seçicisi testleri: sözlük sözcükleri (tek kaynak), katılımcı
// özeti, küme çipi + şube kutusu geri çağrıları ve dar ekran ızgarası.
// KVKK: şube adları uydurmadır; öğrenci verisi yok.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import SubeSecici, {
  KAPSAM_SECENEKLERI,
  KATILIMCILAR_ETIKETI,
  katilimciOzeti,
} from "./SubeKapsamSecici";

const SUBELER = [
  { id: 1, class_label: "9/A" },
  { id: 2, class_label: "9/B" },
];

describe("SubeKapsamSecici", () => {
  it("katılımcı sözcükleri arayüz sözlüğüyle birebirdir", () => {
    // docs/sozluk.md: alan "Katılımcılar"; "Seviye geneli" / "Şube seç" kullanılmaz.
    expect(KATILIMCILAR_ETIKETI).toBe("Katılımcılar");
    expect(KAPSAM_SECENEKLERI).toEqual([
      { value: "LEVEL", label: "Sınıf düzeyinin tamamı" },
      { value: "SECTIONS", label: "Seçili şubeler" },
    ]);
  });

  it("katılımcı özeti tipten ve şube sayısından üretilir", () => {
    expect(katilimciOzeti("LEVEL", 0)).toBe("Sınıf düzeyinin tamamı");
    expect(katilimciOzeti("SECTIONS", 3)).toBe("3 şube");
  });

  it("şube kutusu ve küme çipi geri çağrıları tetikler", async () => {
    const user = userEvent.setup();
    const onToggleSection = vi.fn();
    const onApplyGroup = vi.fn();
    render(
      <SubeSecici
        adPreki="Almanca"
        sectionIds={[2]}
        sections={SUBELER}
        groups={[{ id: 7, name: "Sayısal" }]}
        onToggleSection={onToggleSection}
        onApplyGroup={onApplyGroup}
      />,
    );

    expect(screen.getByRole("checkbox", { name: "Almanca: 9/B" })).toBeChecked();
    await user.click(screen.getByRole("checkbox", { name: "Almanca: 9/A" }));
    expect(onToggleSection).toHaveBeenCalledWith(1);

    await user.click(screen.getByRole("button", { name: "Almanca: Sayısal kümesini ekle" }));
    expect(onApplyGroup).toHaveBeenCalledWith(7);
  });

  it("şube ızgarası dar ekranda iki, genişte üç sütundur", () => {
    render(
      <SubeSecici
        adPreki="Almanca"
        sectionIds={[]}
        sections={SUBELER}
        groups={[]}
        onToggleSection={() => {}}
        onApplyGroup={() => {}}
      />,
    );

    const izgara = screen.getByRole("checkbox", { name: "Almanca: 9/A" }).closest("div");
    expect(izgara).toHaveClass("grid-cols-2", "sm:grid-cols-3");
  });

  it("şubesi olmayan sınıf düzeyinde yönlendirme metni çıkar", () => {
    render(
      <SubeSecici
        adPreki="Almanca"
        sectionIds={[]}
        sections={[]}
        groups={[]}
        onToggleSection={() => {}}
        onApplyGroup={() => {}}
      />,
    );

    expect(screen.getByText(/Bu sınıf düzeyinde tanımlı şube yok/)).toBeInTheDocument();
  });
});
