// Generic salt-okunur tablo (Faz 1a — oab/parts.tsx'ten ui/'a terfi, frontend-m3.md M5).
// Heterojen listeler için tek kaynak; tıklanabilir satır (ClickableRow) + satıra özgü
// erişilebilir ad. Yalnız M3 token'ları (ham renk/px yok).

import type { ReactNode } from "react";

import Card from "./Card";
import ClickableRow from "./ClickableRow";

export interface Column<T> {
  header: ReactNode;
  cell: (row: T) => ReactNode;
  align?: "right";
}

export default function DataTable<T extends { id: number }>({
  columns,
  rows,
  onRowClick,
  rowLabel,
}: {
  columns: Column<T>[];
  rows: T[];
  onRowClick?: (row: T) => void;
  /** Satıra özgü erişilebilir ad (ekran okuyucu) — verilmezse generic "Detayı aç". */
  rowLabel?: (row: T) => string;
}) {
  return (
    <Card elevation={0} className="overflow-x-auto p-0 shadow-elevation-1 scrollbar-thin">
      <table className="w-full min-w-table border-collapse text-body-small">
        <thead className="sticky top-0 z-10 bg-surface-container-low">
          <tr className="border-b border-outline-variant text-left text-label-medium text-on-surface-variant">
            {columns.map((c, i) => (
              <th
                key={i}
                className={`px-4 py-3 font-semibold ${c.align === "right" ? "text-right" : ""}`}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const cells = columns.map((c, i) => (
              <td key={i} className={`px-4 py-3 ${c.align === "right" ? "text-right" : ""}`}>
                {c.cell(row)}
              </td>
            ));
            return onRowClick ? (
              <ClickableRow
                key={row.id}
                onActivate={() => onRowClick(row)}
                ariaLabel={rowLabel ? rowLabel(row) : "Detayı aç"}
                className="border-t border-outline-variant/50"
              >
                {cells}
              </ClickableRow>
            ) : (
              <tr key={row.id} className="border-t border-outline-variant/50">
                {cells}
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}
