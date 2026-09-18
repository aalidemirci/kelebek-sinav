// M3 yatay aşama rayı (CLAUDE.md §7.5): süreç adımlarını durum renkleriyle gösterir.
// Erişilebilirlik için <ol> + aria-current="step". Token tüketir, ham renk yok.
// Dar ekranda yatay kayar.
//
// `onSelect` verilirse TAMAMLANMIŞ ("done") adımlar düğmeye dönüşür: kullanıcı
// "Geri"ye art arda basmadan istediği adıma döner (18.09.2026 değerlendirmesi —
// "Stepper tıklanamıyor"). Yalnız tamamlanmış adım tıklanır: gelecek adımın kendi
// kaydet/doğrula kapısı vardır, "atlandı" adımın ise gösterecek ekranı yoktur.
// `onSelect` verilmezse ray eskisi gibi salt görseldir.

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

const BODY = "flex min-w-16 flex-col items-center gap-1 text-center";

export default function Stepper({
  items,
  ariaLabel,
  onSelect,
}: {
  items: StepperItem[];
  ariaLabel?: string;
  /** Tamamlanmış bir adıma tıklanınca (ya da Enter/Boşluk ile) çağrılır. */
  onSelect?: (key: string, index: number) => void;
}) {
  return (
    <ol aria-label={ariaLabel} className="flex items-start gap-1 overflow-x-auto pb-1">
      {items.map((item, i) => {
        const body = (
          <>
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
          </>
        );
        const selectable = onSelect !== undefined && item.status === "done";
        return (
          <li
            key={item.key}
            className="flex min-w-0 flex-1 items-start"
            aria-current={item.status === "current" ? "step" : undefined}
          >
            {selectable ? (
              // Yerel <button>: Tab ile odaklanır, Enter/Boşluk ile çalışır. Erişilebilir
              // ad görünür etiketi İÇERİR (WCAG 2.5.3) ve ne yapacağını söyler.
              <button
                type="button"
                onClick={() => onSelect(item.key, i)}
                aria-label={`${item.label} adımına dön`}
                className={`${BODY} rounded-shape-sm p-1 hover:bg-on-surface/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary`}
              >
                {body}
              </button>
            ) : (
              <div className={`${BODY} p-1`}>{body}</div>
            )}
            {i < items.length - 1 && (
              <span
                aria-hidden="true"
                className={`mt-5 h-0.5 min-w-4 flex-1 ${
                  item.status === "done" ? "bg-primary" : "bg-outline-variant"
                }`}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
