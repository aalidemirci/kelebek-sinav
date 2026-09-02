// Yeniden başlat örtüsü: olay gelene kadar HİÇBİR ŞEY çizmez; olay gelince tam
// ekran, kapatılamaz yönlendirme gösterir (kapatma düğmesi bilinçli olarak yok
// — bayat oturumda çalışmaya davet olurdu).

import { act, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { yenidenBaslatGerekliYayinla } from "../../lib/restart";
import YenidenBaslatEkrani from "./YenidenBaslatEkrani";

describe("YenidenBaslatEkrani", () => {
  it("olay gelmeden görünmez, olayla tam ekran yönlendirme gösterir", () => {
    const { container } = render(<YenidenBaslatEkrani />);
    expect(container.firstChild).toBeNull();

    act(() => yenidenBaslatGerekliYayinla());

    const ekran = screen.getByRole("alertdialog", { name: "Programı yeniden başlatın" });
    expect(ekran).toHaveTextContent("Programı kapatıp yeniden açın");
    expect(ekran).toHaveTextContent("db-onceki-");
    // Kapatma düğmesi yok: tek çıkış programı yeniden başlatmaktır.
    expect(screen.queryByRole("button")).toBeNull();
  });
});
