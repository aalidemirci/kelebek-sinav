// Yerleşim krokisi (F3) — OYS T11 panelinden UYARLANDI: salon sekmeli kroki,
// çakışma grupları RENK KODLU (kelebek deseni gözle doğrulanır), TIKLA-TAKAS
// yalnız DAĞITILDI durumunda (iki dolu koltuk seçilir → backend swap-seats;
// doğrulayıcı raporu anında döner, sert ihlal kırmızı snackbar). DnD yok.
// Kroki grid KİMLİĞİNDEN çizilir (desk_row, desk_col, slot) — R1 ile birebir.
// Geometri salonlar modülünden (pasif salonlar DAHİL — arşiv görünümü: salon
// sonradan pasifleşse de eski oturumun krokisi çizilebilmeli). Gözetmen izleri
// KS'de bilinçle yoktur (F3 kapsamı).

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import Card from "../../ui/Card";
import { SkeletonList } from "../../ui/Skeleton";
import Tabs, { tabPanelProps } from "../../ui/Tabs";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { examRoomApi } from "../salonlar/api";
import type { ExamSession, SeatAssignmentRow, ValidationReport } from "./api";
import { examSessionApi } from "./api";

/** Çakışma grubu → tonal renk sınıfı (M3 token döngüsü — ham renk yok).
 *
 * 6 ayrık ton; error-container BİLİNÇLE dışarıda — kırmızı dolgu panelde
 * "ihlal" okunur. 6'dan fazla grupta döngü başa döner ve ikinci turdaki
 * gruplara iç halka (ring) ayracı eklenir (nadir durum).
 */
const GROUP_TONES = [
  "bg-primary-container text-on-primary-container",
  "bg-secondary-container text-on-secondary-container",
  "bg-tertiary-container text-on-tertiary-container",
  "bg-surface-container-high text-on-surface",
  "bg-inverse-surface text-inverse-on-surface",
  "bg-surface-container-low text-on-surface border border-outline",
] as const;

function ReportSummary({ report }: { report: ValidationReport }) {
  return (
    <div
      className={`rounded-shape-md border p-3 text-body-medium ${
        report.is_valid ? "border-outline-variant text-on-surface" : "border-error text-error"
      }`}
      role={report.is_valid ? undefined : "alert"}
    >
      <p className="font-medium">
        {report.is_valid
          ? "Sert kısıt ihlali yok (İHLAL = 0)."
          : `DİKKAT: ${report.hard_violations.length} sert kısıt ihlali!`}
      </p>
      <p className="text-body-small">
        1. halka aynı-grup çifti: {report.first_ring_same_group_pairs} · Yakınlık skoru:{" "}
        {report.proximity_score} (düşük iyidir) · Aynı şubeden farklı-grup komşu çifti:{" "}
        {report.cross_group_same_section_first_ring_pairs}
      </p>
      {!report.is_valid && (
        <ul className="mt-1 list-disc pl-5 text-body-small">
          {report.hard_violations.slice(0, 5).map((v) => (
            <li key={v}>{v}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function YerlesimPaneli({ session }: { session: ExamSession }) {
  const snackbar = useSnackbar();
  const qc = useQueryClient();
  const seating = useQuery({
    queryKey: ["exam-seating", session.id],
    queryFn: () => examSessionApi.seating(session.id),
  });
  // Kroki geometrisi salon planından (pasif salonlar dahil — arşiv görünümü).
  const rooms = useQuery({ queryKey: ["exam-rooms-all"], queryFn: () => examRoomApi.list(true) });
  const [activeRoom, setActiveRoom] = useState<string>("");
  const [picked, setPicked] = useState<SeatAssignmentRow | null>(null);

  const swappable = session.status === "DISTRIBUTED";

  const swap = useMutation({
    mutationFn: (pair: { a: number; b: number }) =>
      examSessionApi.swapSeats(session.id, pair.a, pair.b),
    onSuccess: (result) => {
      setPicked(null);
      void qc.invalidateQueries({ queryKey: ["exam-seating", session.id] });
      if (result.report.is_valid) {
        snackbar.success("Takas yapıldı — ihlal yok.");
      } else {
        snackbar.error(
          `Takas yapıldı ama ${result.report.hard_violations.length} sert ihlal oluştu!`,
        );
      }
    },
    onError: (e) => {
      setPicked(null);
      snackbar.error(e instanceof ApiError ? e.message : "Takas yapılamadı.");
    },
  });

  const groupTone = useMemo(() => {
    const map = new Map<string, string>();
    for (const room of seating.data?.rooms ?? []) {
      for (const a of room.assignments) {
        if (!map.has(a.conflict_group)) {
          const tone = GROUP_TONES[map.size % GROUP_TONES.length];
          // İkinci ton döngüsü: ring ayracıyla görsel ayrım korunur (7+ grup).
          const cycled =
            map.size >= GROUP_TONES.length ? `${tone} ring-2 ring-inset ring-outline` : tone;
          map.set(a.conflict_group, cycled);
        }
      }
    }
    return map;
  }, [seating.data]);

  if (seating.isPending || rooms.isPending) {
    return <SkeletonList rows={3} />;
  }
  if (seating.isError) {
    return (
      <p role="alert" className="text-body-medium text-error">
        Yerleşim yüklenemedi:{" "}
        {seating.error instanceof ApiError ? seating.error.message : "beklenmeyen hata."}
      </p>
    );
  }
  const data = seating.data;
  if (!data || data.rooms.length === 0) {
    return <p className="text-body-medium text-on-surface-variant">Oturumda yerleşim yok.</p>;
  }

  const roomTabs = data.rooms.map((r) => ({ key: String(r.room_id), label: r.room_name }));
  const currentKey = activeRoom || roomTabs[0].key;
  const currentRoom = data.rooms.find((r) => String(r.room_id) === currentKey) ?? data.rooms[0];
  const plan = rooms.data?.results.find((r) => r.id === currentRoom.room_id)?.layout_plan;

  const byKey = new Map(
    currentRoom.assignments.map((a) => [`${a.desk_row}:${a.desk_col}:${a.slot}`, a]),
  );

  const handleSeatClick = (assignment: SeatAssignmentRow) => {
    if (!swappable) return;
    if (picked === null) {
      setPicked(assignment);
      return;
    }
    if (picked.id === assignment.id) {
      setPicked(null);
      return;
    }
    swap.mutate({ a: picked.id, b: assignment.id });
  };

  const usedSeed = data.distribution_params.seed;

  return (
    <div className="flex flex-col gap-4">
      <ReportSummary report={data.report} />
      {/* Salon doluluk çipleri — kapasite/yerleşen/yüzde (K1 deseni). */}
      {data.occupancy.length > 0 && (
        <div role="group" className="flex flex-wrap gap-2" aria-label="Salon doluluk özeti">
          {data.occupancy.map((o) => (
            <span
              key={o.room_id}
              className="rounded-full bg-surface-container-high px-3 py-1 text-label-small text-on-surface"
            >
              {o.room_name}: {o.placed}/{o.capacity} (%{o.percent})
            </span>
          ))}
        </div>
      )}
      {usedSeed !== undefined && usedSeed !== null && (
        <p className="text-body-small text-on-surface-variant">
          Kullanılan seed: <span className="font-medium text-on-surface">{String(usedSeed)}</span> —
          aynı seed ile dağıtım birebir yeniden üretilir.
        </p>
      )}
      {swappable && (
        <p className="text-body-small text-on-surface-variant">
          Takas: bir öğrenciye tıklayın (seçili halkayla vurgulanır), sonra takas edileceği
          öğrenciye tıklayın. Her takasta doğrulayıcı anında çalışır.
        </p>
      )}
      <Tabs
        items={roomTabs}
        active={currentKey}
        onChange={setActiveRoom}
        idBase="yerlesim-salon"
        ariaLabel="Salonlar"
      />

      <div {...tabPanelProps("yerlesim-salon", currentKey)}>
        {!plan ? (
          <p className="text-body-medium text-on-surface-variant">Salon planı bulunamadı.</p>
        ) : (
          <Card elevation={1} className="overflow-x-auto p-4">
            {/* Dinamik sütun sayısı — RoomEditor'la aynı yapısal inline istisna. */}
            <div
              role="group"
              aria-label={`${currentRoom.room_name} oturma planı`}
              className="grid w-max gap-1"
              style={{
                gridTemplateColumns: `repeat(${plan.grid.cols}, minmax(3rem, max-content))`,
              }}
            >
              {Array.from({ length: plan.grid.rows }, (_, row) =>
                Array.from({ length: plan.grid.cols }, (_, col) => {
                  const desk = plan.desks.find((d) => d.row === row && d.col === col);
                  const furniture = plan.furniture.find((f) => f.row === row && f.col === col);
                  if (furniture) {
                    return (
                      <div
                        key={`${row}:${col}`}
                        className="flex min-h-12 min-w-12 items-center justify-center rounded-shape-sm bg-secondary-container p-1 text-label-small text-on-secondary-container"
                      >
                        {furniture.kind === "TEACHER_DESK"
                          ? "Öğrt. Masası"
                          : furniture.kind === "DOOR"
                            ? "Kapı"
                            : "Tahta"}
                      </div>
                    );
                  }
                  if (!desk) {
                    return <div key={`${row}:${col}`} className="min-h-12 min-w-12" />;
                  }
                  const size = desk.type === "TRIPLE" ? 3 : desk.type === "DOUBLE" ? 2 : 1;
                  return (
                    <div
                      key={`${row}:${col}`}
                      className="flex min-h-12 gap-1 rounded-shape-sm border border-outline-variant bg-surface p-1"
                    >
                      {Array.from({ length: size }, (_, slot) => {
                        const a = byKey.get(`${row}:${col}:${slot}`);
                        if (!a) {
                          return (
                            <span
                              key={slot}
                              className="flex min-h-10 w-20 items-center justify-center rounded-shape-xs border border-dashed border-outline-variant text-label-small text-on-surface-variant"
                            >
                              Boş
                            </span>
                          );
                        }
                        const tone = groupTone.get(a.conflict_group) ?? GROUP_TONES[0];
                        const isPicked = picked?.id === a.id;
                        return (
                          <button
                            key={slot}
                            type="button"
                            disabled={!swappable}
                            onClick={() => handleSeatClick(a)}
                            aria-pressed={isPicked}
                            aria-label={`Koltuk ${a.seat_no} — ${a.full_name} (${a.class_label})${
                              isPicked ? " — takas için seçili" : ""
                            }`}
                            className={`flex min-h-12 w-24 flex-col items-center justify-center rounded-shape-xs px-1 text-center transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-default ${tone} ${
                              isPicked ? "ring-2 ring-tertiary" : ""
                            }`}
                          >
                            <span className="text-label-large">{a.seat_no}</span>
                            <span className="w-full truncate text-label-small">{a.full_name}</span>
                            <span className="text-label-small opacity-80">
                              {a.class_label}
                              {a.status === "PINNED" && " · Sabit"}
                              {a.status === "MANUAL" && " · Elle"}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  );
                }),
              )}
            </div>
          </Card>
        )}
      </div>

      {/* Renk açıklaması: insan-okur ders + seviye etiketi (conflict_group_labels). */}
      <div className="flex flex-wrap gap-2">
        {[...groupTone.entries()].map(([group, tone]) => (
          <span key={group} className={`rounded-full px-3 py-1 text-label-small ${tone}`}>
            {data.conflict_group_labels[group] ?? `Grup ${group}`}
          </span>
        ))}
      </div>
    </div>
  );
}
