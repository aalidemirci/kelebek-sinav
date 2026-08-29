import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import DataTable from "./DataTable";

interface Row {
  id: number;
  name: string;
}
const rows: Row[] = [
  { id: 1, name: "Ali" },
  { id: 2, name: "Veli" },
];
const columns = [{ header: "Ad", cell: (r: Row) => r.name }];

describe("DataTable", () => {
  it("sütun başlığı + satırları render eder", () => {
    render(<DataTable columns={columns} rows={rows} />);
    expect(screen.getByText("Ad")).toBeInTheDocument();
    expect(screen.getByText("Ali")).toBeInTheDocument();
    expect(screen.getByText("Veli")).toBeInTheDocument();
  });

  it("onRowClick satır etkinleşince tetiklenir + rowLabel satıra özgü erişilebilir ad verir", async () => {
    const onRowClick = vi.fn();
    render(
      <DataTable
        columns={columns}
        rows={rows}
        onRowClick={onRowClick}
        rowLabel={(r) => `${r.name} satırını aç`}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Ali satırını aç" }));
    expect(onRowClick).toHaveBeenCalledWith(rows[0]);
  });
});
