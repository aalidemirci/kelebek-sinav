// M3 açılır seçim (CLAUDE.md §7.5 — outlined). Etiket + yardımcı/hata metni.
// Yerel <select> erişilebilirlik için korunur; M3 token'larıyla biçimlenir.

import { useId } from "react";
import type { ReactNode, SelectHTMLAttributes } from "react";

export interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "id" | "children"> {
  label: string;
  options: SelectOption[];
  placeholder?: string;
  helperText?: ReactNode;
  error?: string;
}

export default function Select({
  label,
  options,
  placeholder,
  helperText,
  error,
  className = "",
  required,
  ...rest
}: SelectProps) {
  const id = useId();
  const describedBy = error || helperText ? `${id}-desc` : undefined;
  const ring = error
    ? "border-error focus-within:border-error focus-within:ring-2 focus-within:ring-error"
    : "border-outline-variant hover:border-outline focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20";

  return (
    <div className={className}>
      {/* Boş label ile boş <label> render edilmez (Tur 245 — m3-ui-reviewer);
          görsel etiketsiz kullanımda erişilebilir ad aria-label ile verilir. */}
      {label && (
        <label
          htmlFor={id}
          className="mb-1.5 block text-label-medium font-semibold text-on-surface-variant"
        >
          {label}
          {required && <span className="text-error"> *</span>}
        </label>
      )}
      <div
        className={`flex h-[var(--ks-field-height)] items-center rounded-shape-md border bg-surface-container-lowest px-2.5 shadow-sm transition-colors ${ring}`}
      >
        <select
          id={id}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className="w-full appearance-none bg-transparent px-1 text-body-medium text-on-surface outline-none disabled:opacity-50"
          {...rest}
        >
          {placeholder !== undefined && <option value="">{placeholder}</option>}
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <span className="material-symbols-outlined pointer-events-none text-on-surface-variant">
          arrow_drop_down
        </span>
      </div>
      {(error || helperText) && (
        <p
          id={describedBy}
          className={`mt-1 text-body-small ${error ? "text-error" : "text-on-surface-variant"}`}
        >
          {error || helperText}
        </p>
      )}
    </div>
  );
}
