// M3 yatay aşama rayı (CLAUDE.md §7.5): süreç adımlarını durum renkleriyle gösterir.
// Salt-görsel (etkileşimsiz) → 48px dokunma hedefi gerekmez; erişilebilirlik için
// <ol> + aria-current="step". Token tüketir, ham renk yok. Dar ekranda yatay kayar.

import Icon from "./Icon";

export type StepperStatus = "done" | "current" | "upcoming" | "skipped";

export interface StepperItem {
  key: string;
  label: string;
  /** Material Symbols ikon adı (done durumunda yerine onay işareti gösterilir). */
  icon?: string;
  status: StepperStatus;
}

const NODE: Record<StepperStatus, string> = {
  done: "bg-primary text-on-primary",
  current: "bg-primary-container text-on-primary-container ring-2 ring-inset ring-primary",
  upcoming: "bg-surface-container-high text-on-surface-variant",
  skipped: "bg-surface-container text-on-surface-variant opacity-60",
};

const LABEL: Record<StepperStatus, string> = {
  done: "text-on-surface",
  current: "text-primary font-medium",
  upcoming: "text-on-surface-variant",
  skipped: "text-on-surface-variant",
};

export default function Stepper({
  items,
  ariaLabel,
}: {
  items: StepperItem[];
  ariaLabel?: string;
}) {
  return (
    <ol aria-label={ariaLabel} className="flex items-start gap-1 overflow-x-auto pb-1">
      {items.map((item, i) => (
        <li
          key={item.key}
          className="flex min-w-0 flex-1 items-start"
          aria-current={item.status === "current" ? "step" : undefined}
        >
          <div className="flex min-w-16 flex-col items-center gap-1 text-center">
            <span
              className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-label-medium ${NODE[item.status]}`}
            >
              {item.status === "done" ? (
                <Icon name="check" size="lg" />
              ) : item.icon ? (
                <Icon name={item.icon} size="lg" />
              ) : (
                i + 1
              )}
            </span>
            <span className={`text-label-small leading-tight ${LABEL[item.status]}`}>
              {item.label}
            </span>
            {item.status === "skipped" && (
              <span className="text-label-small text-on-surface-variant">atlandı</span>
            )}
          </div>
          {i < items.length - 1 && (
            <span
              aria-hidden="true"
              className={`mt-4 h-0.5 min-w-4 flex-1 ${
                item.status === "done" ? "bg-primary" : "bg-outline-variant"
              }`}
            />
          )}
        </li>
      ))}
    </ol>
  );
}
