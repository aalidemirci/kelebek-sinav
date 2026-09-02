// Salon Editörü 2.0 (T10 — yol haritası §8.1): grid üzerinde TIKLA-YERLEŞTİR
// (ADR-0016 kullanıcı kararı — DnD kütüphanesi yok). Palet aracı seçilir,
// hücreye tıklanınca uygulanır; canlı kapasite sayacı + S düzeni numara
// önizlemesi (backend preview-seats — numaralandırma iş kuralı backend'de,
// CLAUDE.md §10). Kroki raporuyla (R1) birebir aynı grid kimliği kullanılır.
// Mürekkep (ADR-0048) token'ları: ham renk/px yok; hücreler ≥36px fare hedefi.

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import { saveBlob } from "../../lib/download";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import type { SelectOption } from "../../ui/Select";
import TextField from "../../ui/TextField";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { ExamRoom, LayoutPlan, NumberingSchemeCode } from "./api";
import { examRoomApi } from "./api";
import type { Tool } from "./planEdit";
import {
  DESK_LABELS,
  DESK_SEAT_COUNT,
  FURNITURE_ICONS,
  FURNITURE_LABELS,
  applyTool,
  capacityOf,
  cellContent,
  deskRowCount,
  resizeDeskArea,
} from "./planEdit";

interface RoomEditorProps {
  room: ExamRoom;
  sectionOptions: SelectOption[];
  onSaved: (room: ExamRoom) => void;
  onBack: () => void;
}

interface PaletteItem {
  key: string;
  label: string;
  icon: string;
  tool: Tool;
}

const PALETTE: PaletteItem[] = [
  {
    key: "SINGLE",
    label: DESK_LABELS.SINGLE,
    icon: "chair",
    tool: { kind: "desk", deskType: "SINGLE" },
  },
  {
    key: "DOUBLE",
    label: DESK_LABELS.DOUBLE,
    icon: "weekend",
    tool: { kind: "desk", deskType: "DOUBLE" },
  },
  {
    key: "TRIPLE",
    label: DESK_LABELS.TRIPLE,
    icon: "event_seat",
    tool: { kind: "desk", deskType: "TRIPLE" },
  },
  {
    key: "TEACHER_DESK",
    label: FURNITURE_LABELS.TEACHER_DESK,
    icon: FURNITURE_ICONS.TEACHER_DESK,
    tool: { kind: "furniture", furniture: "TEACHER_DESK" },
  },
  {
    key: "BLACKBOARD",
    label: FURNITURE_LABELS.BLACKBOARD,
    icon: FURNITURE_ICONS.BLACKBOARD,
    tool: { kind: "furniture", furniture: "BLACKBOARD" },
  },
  {
    key: "SMART_BOARD",
    label: FURNITURE_LABELS.SMART_BOARD,
    icon: FURNITURE_ICONS.SMART_BOARD,
    tool: { kind: "furniture", furniture: "SMART_BOARD" },
  },
  {
    key: "DOOR",
    label: FURNITURE_LABELS.DOOR,
    icon: FURNITURE_ICONS.DOOR,
    tool: { kind: "furniture", furniture: "DOOR" },
  },
  {
    key: "toggle",
    label: "Kullanım dışı (aç/kapa)",
    icon: "block",
    tool: { kind: "toggle-disabled" },
  },
  { key: "erase", label: "Sil", icon: "ink_eraser", tool: { kind: "erase" } },
];

/** Hücrenin ekran okuyucu etiketi — konum + içerik. */
function cellLabel(plan: LayoutPlan, row: number, col: number): string {
  const { desk, furniture } = cellContent(plan, row, col);
  // Ön cephe bandı (satır 0) ayrı adlandırılır; öğrenci sıraları 1'den sayılır.
  const pos = row === 0 ? `Ön cephe, sütun ${col + 1}` : `Sıra ${row}, sütun ${col + 1}`;
  if (desk) {
    return `${pos} — ${DESK_LABELS[desk.type]}${desk.disabled ? " (kullanım dışı)" : ""}`;
  }
  if (furniture) return `${pos} — ${FURNITURE_LABELS[furniture.kind]}`;
  return `${pos} — boş`;
}

export default function RoomEditor({ room, sectionOptions, onSaved, onBack }: RoomEditorProps) {
  const snackbar = useSnackbar();
  const [name, setName] = useState(room.name);
  const [block, setBlock] = useState(room.block);
  const [scheme, setScheme] = useState<NumberingSchemeCode>(room.numbering_scheme);
  const [linkedSectionId, setLinkedSectionId] = useState<string>(
    room.linked_section_id === null ? "" : String(room.linked_section_id),
  );
  const [isActive, setIsActive] = useState(room.is_active);
  const [plan, setPlan] = useState<LayoutPlan>(room.layout_plan);
  const [tool, setTool] = useState<Tool>({ kind: "desk", deskType: "DOUBLE" });
  const [toolKey, setToolKey] = useState("DOUBLE");
  const [showNumbers, setShowNumbers] = useState(true);

  // Numara önizlemesi backend'den (kayıt YAZILMAZ); plan/düzen değişince tazelenir.
  const preview = useQuery({
    queryKey: ["exam-room-preview", room.id, scheme, plan],
    queryFn: () => examRoomApi.previewSeats(plan, scheme),
    enabled: showNumbers,
    placeholderData: (prev) => prev,
  });

  const seatNoByKey = useMemo(() => {
    const map = new Map<string, number>();
    for (const seat of preview.data?.seats ?? []) {
      map.set(`${seat.desk_row}:${seat.desk_col}:${seat.slot}`, seat.seat_no);
    }
    return map;
  }, [preview.data]);

  // Canlı sayaç: önizleme yüklüyse kesin değer, değilse yerel toplam.
  const capacity = showNumbers && preview.data ? preview.data.capacity : capacityOf(plan);

  const save = useMutation({
    mutationFn: () =>
      examRoomApi.update(room.id, {
        name,
        block,
        numbering_scheme: scheme,
        linked_section_id: linkedSectionId === "" ? null : Number(linkedSectionId),
        layout_plan: plan,
        is_active: isActive,
      }),
    onSuccess: (updated) => {
      snackbar.success("Salon kaydedildi.");
      onSaved(updated);
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Salon kaydedilemedi."),
  });

  // Varsayılan şablonu SALONUN MEVCUT ÖLÇÜSÜNDE uygular: okul içinde salonlar
  // benzer, okullar arasında farklıdır — 4×5 sabitlemek yerine ızgara kullanıcıda
  // kalır. Şablonu backend üretir (tek doğruluk kaynağı); kayıt "Kaydet" ile olur.
  const applyTemplate = useMutation({
    mutationFn: () => examRoomApi.defaultPlan(Math.max(1, deskRowCount(plan)), plan.grid.cols),
    onSuccess: (result) => {
      setPlan(result.layout_plan);
      snackbar.success("Varsayılan şablon uygulandı — kaydetmezseniz kalıcı olmaz.");
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Şablon alınamadı."),
  });

  // Kullanıcının girdiği sayılar ÖĞRENCİ ALANINI tarif eder; ön cephe bandı
  // (öğretmen masası/tahta/kapı satırı) sayıma girmez (saha bulgusu).
  const handleResize = (deskRows: number, cols: number) => {
    if (deskRows < 1 || deskRows > 29 || cols < 1 || cols > 30) return;
    setPlan((p) => resizeDeskArea(p, deskRows, cols));
  };

  const renderCell = (row: number, col: number) => {
    const { desk, furniture } = cellContent(plan, row, col);
    let body;
    if (desk) {
      const size = DESK_SEAT_COUNT[desk.type];
      body = desk.disabled ? (
        <span className="flex flex-col items-center text-on-surface-variant">
          <Icon name="block" aria-hidden="true" size="lg" />
          <span className="text-label-small">Kullanım dışı</span>
        </span>
      ) : (
        <span className="flex gap-0.5">
          {Array.from({ length: size }, (_, slot) => (
            <span
              key={slot}
              className="flex h-9 w-9 items-center justify-center rounded-shape-sm border border-outline-variant bg-surface-container-lowest text-label-medium font-semibold tabular-nums text-on-surface shadow-sm"
            >
              {showNumbers ? (seatNoByKey.get(`${row}:${col}:${slot}`) ?? "·") : "·"}
            </span>
          ))}
        </span>
      );
    } else if (furniture) {
      body = (
        <span className="flex flex-col items-center text-on-secondary-container">
          <Icon name={FURNITURE_ICONS[furniture.kind]} aria-hidden="true" size="lg" />
          <span className="text-label-small">{FURNITURE_LABELS[furniture.kind]}</span>
        </span>
      );
    } else {
      body = (
        <span aria-hidden="true" className="text-on-surface-variant/40">
          +
        </span>
      );
    }

    const surface = furniture
      ? "bg-secondary-container"
      : desk
        ? desk.disabled
          ? "bg-surface-container"
          : "bg-surface-container-low"
        : "bg-surface";
    return (
      <button
        key={`${row}:${col}`}
        type="button"
        aria-label={cellLabel(plan, row, col)}
        onClick={() => setPlan((p) => applyTool(p, row, col, tool))}
        className={`flex min-h-11 min-w-11 items-center justify-center rounded-shape-md border border-outline-variant p-1.5 transition hover:border-outline hover:bg-on-surface/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${surface}`}
      >
        {body}
      </button>
    );
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Button variant="text" icon="arrow_back" onClick={onBack}>
          Salon listesi
        </Button>
        <h2 className="text-title-large text-on-surface">{room.name}</h2>
        <span className="ml-auto rounded-full bg-primary-container px-4 py-2 text-label-large text-on-primary-container">
          Kapasite: {capacity}
        </span>
        <Button
          variant="tonal"
          icon="print"
          title="Kaydedilmiş planı indirir — kaydedilmemiş değişiklikler PDF'e yansımaz."
          onClick={() =>
            void examRoomApi
              .layoutPdfBlob(room.id)
              .then((b) => saveBlob(b, `salon_yerlesim_plani_${room.id}.pdf`))
              .catch(() => snackbar.error("Yerleşim planı indirilemedi."))
          }
        >
          Yerleşim planı (PDF)
        </Button>
        <Button onClick={() => save.mutate()} disabled={save.isPending} icon="save">
          {save.isPending ? "Kaydediliyor…" : "Kaydet"}
        </Button>
      </div>

      {/* Araç paleti — tam genişlik üst şerit (Tur 244, talep 8: solda erişim zordu) */}
      <Card elevation={1} className="mb-4 p-3">
        <div
          className="flex flex-wrap items-center gap-2"
          role="radiogroup"
          aria-label="Yerleştirme aracı"
        >
          <span className="mr-1 text-title-small text-on-surface">Araç paleti</span>
          {PALETTE.map((item) => {
            const active = toolKey === item.key;
            return (
              <button
                key={item.key}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => {
                  setTool(item.tool);
                  setToolKey(item.key);
                }}
                className={`flex min-h-9 items-center gap-2 rounded-shape-sm px-3 text-label-large transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                  active
                    ? "bg-secondary-container text-on-secondary-container"
                    : "text-on-surface hover:bg-on-surface/5"
                }`}
              >
                <Icon name={item.icon} aria-hidden="true" />
                {item.label}
              </button>
            );
          })}
        </div>
        <p className="mt-1 text-body-small text-on-surface-variant">
          Araç seçin, sonra plandaki hücreye tıklayın.
        </p>
      </Card>

      <div className="grid gap-4 lg:grid-cols-[18rem_1fr]">
        {/* Sol panel: salon bilgileri */}
        <div className="flex flex-col gap-4">
          <Card elevation={1} className="flex flex-col gap-3 p-4 self-start">
            <h3 className="text-title-small text-on-surface">Salon bilgileri</h3>
            <TextField
              label="Salon adı"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
            <TextField
              label="Blok / kat"
              value={block}
              onChange={(e) => setBlock(e.target.value)}
            />
            <Select
              label="Numaralandırma"
              options={[
                { value: "S_PATTERN", label: "S düzeni" },
                { value: "STRAIGHT", label: "Düz" },
              ]}
              value={scheme}
              onChange={(e) => setScheme(e.target.value as NumberingSchemeCode)}
            />
            <Select
              label="Bağlı şube (derslik eşlemesi)"
              options={sectionOptions}
              placeholder="— Eşleme yok —"
              value={linkedSectionId}
              onChange={(e) => setLinkedSectionId(e.target.value)}
              helperText="Klasik (kendi dersliğinde) düzenin temelidir."
            />
            <label className="flex min-h-9 cursor-pointer items-center gap-3 text-body-medium text-on-surface">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="h-5 w-5 accent-primary"
              />
              Salon aktif (oturum planlamasında seçilebilir)
            </label>
          </Card>
        </div>

        {/* Sağ panel: grid + boyut + önizleme anahtarı */}
        <Card elevation={1} className="p-4">
          <div className="mb-3 flex flex-wrap items-end gap-3">
            <TextField
              label="Sıra satırı"
              type="number"
              min={1}
              max={29}
              value={deskRowCount(plan)}
              onChange={(e) => handleResize(Number(e.target.value), plan.grid.cols)}
              className="w-28"
              helperText="Öğrenci sırası"
            />
            <TextField
              label="Sıra sütunu"
              type="number"
              min={1}
              max={30}
              value={plan.grid.cols}
              onChange={(e) => handleResize(deskRowCount(plan), Number(e.target.value))}
              className="w-28"
              helperText="Öğrenci sırası"
            />
            <Button
              variant="text"
              icon="grid_view"
              disabled={applyTemplate.isPending}
              onClick={() => applyTemplate.mutate()}
            >
              Varsayılan şablon
            </Button>
            <label className="ml-auto flex min-h-9 cursor-pointer items-center gap-3 text-body-medium text-on-surface">
              <input
                type="checkbox"
                checked={showNumbers}
                onChange={(e) => setShowNumbers(e.target.checked)}
                className="h-5 w-5 accent-primary"
              />
              Koltuk numarası önizlemesi
            </label>
          </div>
          {showNumbers && preview.isError && (
            <p role="alert" className="mb-2 text-body-small text-error">
              Önizleme alınamadı:{" "}
              {preview.error instanceof ApiError
                ? preview.error.message
                : "plan geçersiz olabilir."}
            </p>
          )}
          <p className="mb-2 text-body-small text-on-surface-variant">
            En üstteki şerit salonun <strong>ön cephesidir</strong> — öğretmen masası, tahta ve kapı
            oraya konur ve <strong>satır sayımına girmez</strong>. Numaralar öğretmen masasına en
            yakın sıradan başlar; çizim kroki (R1) ile birebirdir.{" "}
            <strong>Varsayılan şablon</strong> masayı ön-sola koyar ve ızgarayı ikili sıralarla
            doldurur — mevcut planın yerine geçer.
          </p>
          <div className="overflow-x-auto pb-2">
            {/* Sütun sayısı kullanıcı verisi (1-30) — Tailwind sınıfı dinamik
                üretilemez; yapısal grid şablonu inline verilir (renk/ölçü token
                ihlali değil; 3rem = 48px dokunma hedefi tabanı). */}
            <div className="w-max">
              {/* ÖN CEPHE bandı — ızgaranın 0. satırı; öğrenci alanından
                  görsel olarak ayrılır ki satır sayımıyla karışmasın. */}
              <p className="mb-1 text-center text-label-small font-semibold uppercase tracking-widest text-on-surface-variant">
                Ön cephe · tahta ve öğretmen masası
              </p>
              <div
                role="group"
                aria-label="Ön cephe: öğretmen masası, tahta ve kapı"
                className="grid gap-1 rounded-shape-md bg-surface-container-low p-1"
                style={{
                  gridTemplateColumns: `repeat(${plan.grid.cols}, minmax(3.25rem, max-content))`,
                }}
              >
                {Array.from({ length: plan.grid.cols }, (_, col) => renderCell(0, col))}
              </div>

              <div className="my-2 border-t-2 border-dashed border-outline-variant" />

              <div
                role="group"
                aria-label={`Öğrenci sıraları: ${deskRowCount(plan)} satır × ${plan.grid.cols} sütun`}
                className="grid gap-1"
                style={{
                  gridTemplateColumns: `repeat(${plan.grid.cols}, minmax(3.25rem, max-content))`,
                }}
              >
                {Array.from({ length: deskRowCount(plan) }, (_, i) =>
                  Array.from({ length: plan.grid.cols }, (_, col) => renderCell(i + 1, col)),
                )}
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
