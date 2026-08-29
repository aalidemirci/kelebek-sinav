// Tur 137 — ConfirmProvider + useConfirm davranış testi: hook kapsamı, dialog
// açılması (rol=dialog + mesaj + eylem butonları), Onayla→true / Vazgeç→false /
// ESC→false ve dialog kapanışı. React Testing Library + Vitest.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConfirmProvider, useConfirm } from "./ConfirmProvider";

// Hook'u tetikleyen yardımcı: "tetikle"ye basınca confirm() çözülünce sonucu bildirir.
function Harness({ onResult }: { onResult: (ok: boolean) => void }) {
  const confirm = useConfirm();
  return (
    <button
      onClick={async () =>
        onResult(await confirm({ message: "Silinsin mi?", confirmLabel: "Sil" }))
      }
    >
      tetikle
    </button>
  );
}

function renderWithProvider(onResult: (ok: boolean) => void = () => {}) {
  return render(
    <ConfirmProvider>
      <Harness onResult={onResult} />
    </ConfirmProvider>,
  );
}

describe("useConfirm", () => {
  it("ConfirmProvider dışında çağrılırsa hata fırlatır", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    function Bad() {
      useConfirm();
      return null;
    }
    expect(() => render(<Bad />)).toThrow(/ConfirmProvider/);
    spy.mockRestore();
  });
});

describe("ConfirmProvider", () => {
  it("tetikleyince onay dialog'u mesaj + butonlarla açılır", async () => {
    const user = userEvent.setup();
    renderWithProvider();
    await user.click(screen.getByText("tetikle"));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Silinsin mi?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sil" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Vazgeç" })).toBeInTheDocument();
  });

  it("Onayla butonu Promise'i true çözer ve dialog kapanır", async () => {
    const user = userEvent.setup();
    const onResult = vi.fn();
    renderWithProvider(onResult);
    await user.click(screen.getByText("tetikle"));
    await user.click(await screen.findByRole("button", { name: "Sil" }));
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(true));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("Vazgeç butonu Promise'i false çözer", async () => {
    const user = userEvent.setup();
    const onResult = vi.fn();
    renderWithProvider(onResult);
    await user.click(screen.getByText("tetikle"));
    await user.click(await screen.findByRole("button", { name: "Vazgeç" }));
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(false));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("ESC tuşu Promise'i false çözer", async () => {
    const user = userEvent.setup();
    const onResult = vi.fn();
    renderWithProvider(onResult);
    await user.click(screen.getByText("tetikle"));
    await screen.findByRole("dialog");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(false));
  });
});
