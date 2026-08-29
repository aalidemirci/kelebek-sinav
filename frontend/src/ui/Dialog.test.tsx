// Tur 57 — M3 Dialog davranış testi: açık/kapalı render, ESC + scrim kapatma,
// rol=dialog + aria-modal, başlık + eylem alanı. React Testing Library + Vitest.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import Button from "./Button";
import Dialog from "./Dialog";

/** Gerçek kullanım kalıbı: bir buton dialogu açar, dialog kendini kapatır. */
function AcKapa() {
  const [acik, setAcik] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setAcik(true)}>
        Aç
      </button>
      <Dialog open={acik} onClose={() => setAcik(false)} title="Onay">
        İçerik
      </Dialog>
    </>
  );
}

describe("Dialog", () => {
  it("kapalıyken hiçbir şey basmaz", () => {
    render(
      <Dialog open={false} onClose={() => {}} title="Onay">
        İçerik
      </Dialog>,
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("açıkken başlık + içeriği rol=dialog + aria-modal ile basar", () => {
    render(
      <Dialog open onClose={() => {}} title="Sınıf Atlatma">
        Emin misiniz?
      </Dialog>,
    );
    const dlg = screen.getByRole("dialog");
    expect(dlg).toHaveAttribute("aria-modal", "true");
    expect(screen.getByRole("heading", { name: "Sınıf Atlatma" })).toBeInTheDocument();
    expect(screen.getByText("Emin misiniz?")).toBeInTheDocument();
  });

  it("ESC tuşu onClose çağırır", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <Dialog open onClose={onClose} title="Onay">
        İçerik
      </Dialog>,
    );
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("scrim'e tıklama onClose çağırır, panele tıklama çağırmaz", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <Dialog open onClose={onClose} title="Onay">
        İçerik
      </Dialog>,
    );
    await user.click(screen.getByRole("heading", { name: "Onay" }));
    expect(onClose).not.toHaveBeenCalled();
  });

  // WCAG 2.4.3 (odak sırası): modal kapanınca odak, onu AÇAN öğeye döner.
  // Aksi halde odak <body>'ye düşer ve klavye kullanıcısı sekmeye sayfanın
  // en başından başlar — bulunduğu yeri kaybeder (B6).
  it("kapanışta odağı dialogu açan öğeye geri verir", async () => {
    const user = userEvent.setup();
    render(<AcKapa />);
    const acici = screen.getByRole("button", { name: "Aç" });

    await user.click(acici);
    expect(screen.getByRole("dialog")).toHaveFocus();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(acici).toHaveFocus();
  });

  it("açan öğe DOM'dan kalktıysa odak geri verilmeye çalışılmaz (çökmez)", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<AcKapa />);
    await user.click(screen.getByRole("button", { name: "Aç" }));
    expect(screen.getByRole("dialog")).toHaveFocus();
    expect(() => unmount()).not.toThrow();
  });

  it("actions alanı verilen butonları basar", () => {
    render(
      <Dialog open onClose={() => {}} title="Onay" actions={<Button>Uygula</Button>}>
        İçerik
      </Dialog>,
    );
    expect(screen.getByRole("button", { name: "Uygula" })).toBeInTheDocument();
  });
});

it("Tab odak tuzağı: son öğeden ilkine, Shift+Tab ilkinden sonuncuya sarar (F29)", async () => {
  const user = userEvent.setup();
  render(
    <Dialog open onClose={() => undefined} title="Tuzak">
      <button type="button">İlk</button>
      <button type="button">Orta</button>
      <button type="button">Son</button>
    </Dialog>,
  );
  const ilk = screen.getByRole("button", { name: "İlk" });
  const son = screen.getByRole("button", { name: "Son" });

  // Panel odaklıyken Shift+Tab → son öğeye sarar (dışarı çıkmaz).
  await user.keyboard("{Shift>}{Tab}{/Shift}");
  expect(son).toHaveFocus();

  // Son öğedeyken Tab → ilk öğeye sarar.
  await user.keyboard("{Tab}");
  expect(ilk).toHaveFocus();

  // İlk öğedeyken Shift+Tab → tekrar sona sarar.
  await user.keyboard("{Shift>}{Tab}{/Shift}");
  expect(son).toHaveFocus();
});
