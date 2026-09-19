// Fotoğraflı yoklama planı (19.09.2026, kullanıcı kararı: "yoklama/imza işlemi
// doğrudan bu plan üzerinde olsun" — basılı evrakla birlikte uygulamada da).
//
// Salonun gerçek ızgarası (desk_row, desk_col, slot — R1 ve yerleşim paneliyle
// aynı kimlik) çizilir; her koltuk kartında fotoğraf, ad, okul no · şube. Karta
// basmak öğrenciyi "Girmedi" işaretler; işaretli karta basmak onaydan geçip
// işareti kaldırır. Mazeret durumu/notu üstteki "Sınava girmeyenler" listesinde
// yönetilir (YoklamaPaneli). Fotoğraf yoksa baş harf rozeti çizilir.
//
// KVKK: fotoğraflar yalnız bu ekranda, yerel sunucudan data URI olarak gelir;
// tarayıcı önbelleğine dosya olarak yazılmaz.

import type { SeatAssignmentRow } from "./api";
import type { LayoutPlan } from "../salonlar/api";
import { FURNITURE_LABELS } from "../salonlar/planEdit";

function basHarfler(ad: string): string {
  return ad
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p.charAt(0))
    .join("");
}

export default function YoklamaPlani({
  roomName,
  plan,
  assignments,
  photos,
  absentStudentIds,
  busy,
  onToggle,
}: {
  roomName: string;
  plan: LayoutPlan;
  assignments: SeatAssignmentRow[];
  photos: Record<string, string>;
  absentStudentIds: Set<number>;
  busy: boolean;
  /** Karta basıldı: işaretliyse kaldırma, değilse "Girmedi" işaretleme isteği. */
  onToggle: (assignment: SeatAssignmentRow, absent: boolean) => void;
}) {
  const byKey = new Map(assignments.map((a) => [`${a.desk_row}:${a.desk_col}:${a.slot}`, a]));
  // Plan dağıtımdan sonra değişmişse koltuğu planda olmayan öğrenci kaybolmasın.
  const yersiz = assignments.filter((a) => {
    const desk = plan.desks.find((d) => d.row === a.desk_row && d.col === a.desk_col);
    const size = desk ? (desk.type === "TRIPLE" ? 3 : desk.type === "DOUBLE" ? 2 : 1) : 0;
    return !desk || desk.disabled || a.slot >= size;
  });

  const kart = (a: SeatAssignmentRow) => {
    // F27 anonim arşivde student_id null'dur — hiçbir zaman "girmedi" eşleşmez.
    const absent = a.student_id !== null && absentStudentIds.has(a.student_id);
    const foto = a.student_id !== null ? photos[String(a.student_id)] : undefined;
    return (
      <button
        key={a.id}
        type="button"
        disabled={busy || a.student_id === null}
        aria-pressed={absent}
        aria-label={`${a.seat_no}. koltuk, ${a.full_name}, ${a.student_number} — ${
          absent ? "girmedi (işareti kaldırmak için basın)" : "girmedi olarak işaretle"
        }`}
        onClick={() => onToggle(a, absent)}
        className={`flex w-24 flex-col items-center gap-1 rounded-shape-sm border p-1 text-center transition-colors disabled:opacity-60 ${
          absent
            ? "border-error bg-error-container text-on-error-container"
            : "border-outline-variant bg-surface hover:bg-on-surface/5"
        }`}
      >
        <span className="flex w-full items-center justify-between text-label-small">
          <span className="font-medium">{a.seat_no}</span>
          {absent && <span className="font-medium">Girmedi</span>}
        </span>
        {foto ? (
          <img
            src={foto}
            alt=""
            className={`h-20 w-16 rounded-shape-xs object-cover ${absent ? "opacity-50 grayscale" : ""}`}
          />
        ) : (
          <span
            aria-hidden="true"
            className="flex h-20 w-16 items-center justify-center rounded-shape-xs bg-surface-container-high text-title-medium text-on-surface-variant"
          >
            {basHarfler(a.full_name)}
          </span>
        )}
        <span className="line-clamp-2 text-label-small leading-tight">{a.full_name}</span>
        <span className="text-label-small text-on-surface-variant">
          {a.student_number} · {a.class_label}
        </span>
      </button>
    );
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-x-auto">
        {/* Dinamik sütun sayısı — yerleşim paneliyle aynı yapısal inline istisna. */}
        <div
          role="group"
          aria-label={`${roomName} yoklama planı`}
          className="grid w-max gap-1"
          style={{ gridTemplateColumns: `repeat(${plan.grid.cols}, max-content)` }}
        >
          {Array.from({ length: plan.grid.rows }, (_, row) =>
            Array.from({ length: plan.grid.cols }, (_, col) => {
              const desk = plan.desks.find((d) => d.row === row && d.col === col);
              const furniture = plan.furniture.find((f) => f.row === row && f.col === col);
              if (furniture) {
                return (
                  <div
                    key={`${row}:${col}`}
                    className="flex min-h-10 items-center justify-center rounded-shape-sm bg-secondary-container p-1 text-center text-label-small text-on-secondary-container"
                  >
                    {FURNITURE_LABELS[furniture.kind]}
                  </div>
                );
              }
              if (!desk || desk.disabled) {
                return <div key={`${row}:${col}`} className="min-h-10 min-w-10" />;
              }
              const size = desk.type === "TRIPLE" ? 3 : desk.type === "DOUBLE" ? 2 : 1;
              return (
                <div
                  key={`${row}:${col}`}
                  className="flex gap-1 rounded-shape-sm border border-outline p-1"
                >
                  {Array.from({ length: size }, (_, slot) => {
                    const a = byKey.get(`${row}:${col}:${slot}`);
                    return a ? (
                      kart(a)
                    ) : (
                      <span
                        key={slot}
                        className="flex w-24 items-center justify-center rounded-shape-sm border border-dashed border-outline-variant text-label-small text-on-surface-variant"
                      >
                        Boş
                      </span>
                    );
                  })}
                </div>
              );
            }),
          )}
        </div>
      </div>
      {yersiz.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-body-small text-error">
            {yersiz.length} öğrencinin koltuğu güncel salon planında yok (plan dağıtımdan sonra
            değiştirilmiş) — yoklamaları buradan alın; oturumu yeniden dağıtın.
          </p>
          <div className="flex flex-wrap gap-1">{yersiz.map(kart)}</div>
        </div>
      )}
    </div>
  );
}
