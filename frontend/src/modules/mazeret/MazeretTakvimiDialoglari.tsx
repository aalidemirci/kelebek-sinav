// Mazeret takvimi diyalogları: parametre formu (yeni takvim + düzenleme) ve tek sınavı
// elle taşıma. Kurallar backend'dedir (`services_makeup_plan`); form yalnız girdiyi toplar.

import { useState } from "react";

import { formatDate } from "../../lib/format";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import Select from "../../ui/Select";
import TextField from "../../ui/TextField";
import type { MakeupPlan, MakeupPlanItem, MakeupPlanParams, PlanPeriod } from "./api";

export const DEFAULT_PLAN_NAME = "Mazeret Sınav Takvimi";

/** Günlük sınır seçenekleri — 2 esastır, 3 yalnız zorunlu hâlde (Yönerge md. 5/1-s). */
const MAX_PER_DAY_OPTIONS = [
  { value: "1", label: "1 sınav" },
  { value: "2", label: "2 sınav (esas olan)" },
  { value: "3", label: "3 sınav (yalnız zorunlu hâlde)" },
];

export interface PlanFormValues extends Required<Omit<MakeupPlanParams, "period_nos">> {
  period_nos: number[];
}

interface PlanFormDialogProps {
  open: boolean;
  onClose: () => void;
  /** Düzenlenen takvim; yoksa yeni takvim formudur. */
  plan: MakeupPlan | null;
  allPeriods: PlanPeriod[];
  defaultPeriodNos: number[];
  maxDayCount: number;
  busy: boolean;
  onSubmit: (values: PlanFormValues) => void;
}

export function PlanFormDialog({
  open,
  onClose,
  plan,
  allPeriods,
  defaultPeriodNos,
  maxDayCount,
  busy,
  onSubmit,
}: PlanFormDialogProps) {
  // Boş `period_nos` "okulun sınav saatleri" demektir; formda o saatler işaretli görünür.
  const [form, setForm] = useState(() => ({
    name: plan?.name ?? DEFAULT_PLAN_NAME,
    start_date: plan?.start_date ?? "",
    day_count: String(plan?.day_count ?? 3),
    max_per_day: String(plan?.max_per_day ?? 2),
    period_nos: plan && plan.period_nos.length > 0 ? plan.period_nos : defaultPeriodNos,
    strict_order: plan?.strict_order ?? true,
  }));

  const dayCount = Number(form.day_count);
  const valid =
    form.start_date !== "" &&
    Number.isInteger(dayCount) &&
    dayCount >= 1 &&
    dayCount <= maxDayCount &&
    form.period_nos.length > 0;

  const togglePeriod = (no: number) =>
    setForm((f) => ({
      ...f,
      period_nos: f.period_nos.includes(no)
        ? f.period_nos.filter((v) => v !== no)
        : [...f.period_nos, no].sort((a, b) => a - b),
    }));

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={plan ? "Takvim parametreleri" : "Yeni mazeret takvimi"}
      actions={
        <>
          <Button variant="text" onClick={onClose}>
            Vazgeç
          </Button>
          <Button
            onClick={() =>
              onSubmit({
                name: form.name.trim(),
                start_date: form.start_date,
                day_count: dayCount,
                max_per_day: Number(form.max_per_day),
                period_nos: form.period_nos,
                strict_order: form.strict_order,
              })
            }
            disabled={busy || !valid}
          >
            {plan ? "Kaydet ve yeniden yerleştir" : "Takvimi oluştur"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <TextField
          label="Takvim adı"
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
        />
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label="İlk mazeret sınavı günü"
            type="date"
            value={form.start_date}
            onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))}
            required
          />
          <TextField
            label="Kaç güne sığsın?"
            type="number"
            min={1}
            max={maxDayCount}
            value={form.day_count}
            onChange={(e) => setForm((f) => ({ ...f, day_count: e.target.value }))}
            helperText="Hafta içi gün sayılır; hafta sonu atlanır."
            required
          />
        </div>
        <Select
          label="Bir öğrenci bir günde en çok"
          options={MAX_PER_DAY_OPTIONS}
          value={form.max_per_day}
          onChange={(e) => setForm((f) => ({ ...f, max_per_day: e.target.value }))}
        />
        <fieldset>
          <legend className="mb-1 text-label-large text-on-surface-variant">
            Mazeret sınavı yapılacak ders saatleri
          </legend>
          <div className="grid grid-cols-2 gap-1 sm:grid-cols-4">
            {allPeriods.map((p) => (
              <label
                key={p.no}
                className="flex min-h-9 cursor-pointer items-center gap-2 rounded-shape-sm border border-outline px-3 text-body-medium text-on-surface"
              >
                <input
                  type="checkbox"
                  className="h-5 w-5 accent-primary"
                  checked={form.period_nos.includes(p.no)}
                  onChange={() => togglePeriod(p.no)}
                />
                {p.name}
                {p.start && (
                  <span className="text-body-small text-on-surface-variant">{p.start}</span>
                )}
              </label>
            ))}
          </div>
        </fieldset>
        <label className="flex min-h-9 cursor-pointer items-start gap-2 text-body-medium text-on-surface">
          <input
            type="checkbox"
            className="mt-0.5 h-5 w-5 accent-primary"
            checked={form.strict_order}
            onChange={(e) => setForm((f) => ({ ...f, strict_order: e.target.checked }))}
          />
          <span>
            Asıl takvim sırasını kesin koru
            <span className="block text-body-small text-on-surface-variant">
              Bir sınav, asıl takvimde kendinden önce gelen hiçbir sınavdan önceye konmaz.
              Kapatırsanız sınavlar boş saatlere öne çekilir (her öğrencinin kendi sırası yine
              korunur) ve takvim daha az güne sığar.
            </span>
          </span>
        </label>
      </div>
    </Dialog>
  );
}

interface MoveDialogProps {
  open: boolean;
  onClose: () => void;
  plan: MakeupPlan;
  item: MakeupPlanItem;
  busy: boolean;
  onMove: (payload: { placed_date: string; period_no: number; is_pinned: boolean }) => void;
  onUnplace: () => void;
  onRemove: () => void;
}

export function MoveItemDialog({
  open,
  onClose,
  plan,
  item,
  busy,
  onMove,
  onUnplace,
  onRemove,
}: MoveDialogProps) {
  const [date, setDate] = useState(item.placed_date ?? plan.days[0]?.date ?? "");
  const [periodNo, setPeriodNo] = useState(
    String(item.period_no ?? plan.periods[0]?.no ?? plan.all_periods[0]?.no ?? ""),
  );
  const [pin, setPin] = useState(true);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={item.placed_date ? "Sınavı taşı" : "Sınavı takvime koy"}
      actions={
        <>
          <Button variant="text" onClick={onClose}>
            Vazgeç
          </Button>
          <Button
            onClick={() =>
              onMove({ placed_date: date, period_no: Number(periodNo), is_pinned: pin })
            }
            disabled={busy || date === "" || periodNo === ""}
          >
            Kaydet
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-body-medium text-on-surface">
          {item.course_label} · {item.student_count} öğrenci · asıl sınav{" "}
          {formatDate(item.source_date)}
        </p>
        {item.external && (
          <p className="rounded-shape-sm bg-tertiary-container p-2 text-body-small text-on-tertiary-container">
            Ülke, il ya da ilçe geneli sınav: mazeret sınavının tarihini il/ilçe millî eğitim
            müdürlüğü ilan eder. İlan edilen gün ve saati girin.
          </p>
        )}
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label="Mazeret sınavı tarihi"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            required
          />
          <Select
            label="Ders saati"
            options={plan.all_periods.map((p) => ({
              value: String(p.no),
              label: p.start ? `${p.name} · ${p.start}` : p.name,
            }))}
            value={periodNo}
            onChange={(e) => setPeriodNo(e.target.value)}
          />
        </div>
        <label className="flex min-h-9 cursor-pointer items-center gap-2 text-body-medium text-on-surface">
          <input
            type="checkbox"
            className="h-5 w-5 accent-primary"
            checked={pin}
            onChange={(e) => setPin(e.target.checked)}
          />
          Sabitle (“Yeniden yerleştir” bu sınava dokunmasın)
        </label>
        <p className="text-body-small text-on-surface-variant">
          Aynı saatte başka sınavı olan öğrenci varsa taşıma reddedilir. Günlük sınır ve takvim
          sırası dışına çıkarsanız program uyarır; karar sizindir.
        </p>
        <div className="flex flex-wrap gap-2 border-t border-outline-variant pt-3">
          {item.placed_date && (
            <Button variant="text" icon="event_busy" onClick={onUnplace} disabled={busy}>
              Takvim dışına al
            </Button>
          )}
          <Button variant="text" icon="delete" onClick={onRemove} disabled={busy}>
            Takvimden çıkar
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
