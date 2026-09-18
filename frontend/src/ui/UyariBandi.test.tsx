// UyariBandi testleri: kalıcı uyarı bandı kibar canlı bölgedir (role=status),
// kapatma çağırana bırakılır ve boş listede hiçbir şey çizilmez.

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import UyariBandi from "./UyariBandi";

describe("UyariBandi", () => {
  it("uyarıları başlığıyla adlandırılmış kibar canlı bölgede listeler", () => {
    render(
      <UyariBandi
        title="Yerleştirme uyarıları"
        messages={["Birinci uyarı.", "İkinci uyarı."]}
        onClose={() => {}}
      />,
    );

    const bant = screen.getByRole("status", { name: "Yerleştirme uyarıları" });
    const maddeler = within(bant).getAllByRole("listitem");
    expect(maddeler.map((li) => li.textContent)).toEqual(["Birinci uyarı.", "İkinci uyarı."]);
    // Uyarı hata DEĞİLDİR: assertive (alert) bölge kullanılmaz.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("tek uyarıyı madde imi olmadan düz cümle olarak basar", () => {
    render(<UyariBandi title="Uyarılar" messages={["Tek uyarı."]} onClose={() => {}} />);

    expect(screen.getByText("Tek uyarı.")).toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("“Kapat” çağıranın onClose'unu tetikler; etiket değiştirilebilir", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const { rerender } = render(
      <UyariBandi title="Uyarılar" messages={["Uyarı."]} onClose={onClose} />,
    );

    await user.click(screen.getByRole("button", { name: "Kapat" }));
    expect(onClose).toHaveBeenCalledTimes(1);

    rerender(
      <UyariBandi title="Uyarılar" messages={["Uyarı."]} onClose={onClose} closeLabel="Okudum" />,
    );
    expect(screen.getByRole("button", { name: "Okudum" })).toBeInTheDocument();
  });

  it("uyarı yokken hiçbir şey çizmez", () => {
    const { container } = render(<UyariBandi title="Uyarılar" messages={[]} onClose={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });
});
