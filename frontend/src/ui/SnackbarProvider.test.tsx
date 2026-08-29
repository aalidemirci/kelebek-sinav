// Tur 122 — SnackbarProvider + useSnackbar davranış testi: hook kapsamı, success/
// error gösterimi, otomatik kapanma (fake timer), tek-anda-bir + FIFO kuyruk, elle
// kapatınca kuyruğun ilerlemesi. React Testing Library + Vitest.

import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SnackbarProvider, useSnackbar } from "./SnackbarProvider";

// Hook'u tetikleyen küçük yardımcı: her buton bir snackbar açar.
function Harness() {
  const sb = useSnackbar();
  return (
    <div>
      <button onClick={() => sb.success("Kaydedildi.")}>basari</button>
      <button onClick={() => sb.error("Hata oluştu.")}>hata</button>
    </div>
  );
}

function renderWithProvider() {
  return render(
    <SnackbarProvider>
      <Harness />
    </SnackbarProvider>,
  );
}

describe("useSnackbar", () => {
  it("SnackbarProvider dışında çağrılırsa hata fırlatır", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    function Bad() {
      useSnackbar();
      return null;
    }
    expect(() => render(<Bad />)).toThrow(/SnackbarProvider/);
    spy.mockRestore();
  });
});

describe("SnackbarProvider", () => {
  it("success çağrısı mesajı gösterir", async () => {
    const user = userEvent.setup();
    renderWithProvider();
    await user.click(screen.getByText("basari"));
    expect(await screen.findByText("Kaydedildi.")).toBeInTheDocument();
  });

  it("error çağrısı role=alert (assertive) ile gösterir", async () => {
    const user = userEvent.setup();
    renderWithProvider();
    await user.click(screen.getByText("hata"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Hata oluştu.");
  });

  it("otomatik kapanma: varsayılan süre (4 sn) dolunca snackbar kalkar", () => {
    vi.useFakeTimers();
    try {
      renderWithProvider();
      act(() => {
        fireEvent.click(screen.getByText("basari"));
      });
      expect(screen.getByText("Kaydedildi.")).toBeInTheDocument();
      act(() => {
        vi.advanceTimersByTime(4000);
      });
      expect(screen.queryByText("Kaydedildi.")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("kuyruk: aynı anda tek snackbar; kapatınca sıradaki görünür", async () => {
    const user = userEvent.setup();
    renderWithProvider();
    await user.click(screen.getByText("basari")); // "Kaydedildi."
    await user.click(screen.getByText("hata")); // kuyruğa "Hata oluştu."

    expect(screen.getByText("Kaydedildi.")).toBeInTheDocument();
    expect(screen.queryByText("Hata oluştu.")).toBeNull(); // henüz görünmez (tek-anda-bir)

    await user.click(screen.getByRole("button", { name: "Kapat" }));
    expect(await screen.findByText("Hata oluştu.")).toBeInTheDocument();
  });
});
