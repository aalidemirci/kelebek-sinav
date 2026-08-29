// Masaüstü metin alanı. Yoğunluk ölçüsü CSS değişkeninden gelir.

import { useId } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  label: string;
  helperText?: ReactNode;
  error?: string;
}

export default function TextField({
  label,
  helperText,
  error,
  className = "",
  required,
  ...rest
}: TextFieldProps) {
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
        className={`flex h-[var(--ks-field-height)] items-center rounded-shape-md border bg-surface-container-lowest px-3 shadow-sm transition-colors ${ring}`}
      >
        <input
          id={id}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className="w-full bg-transparent text-body-medium text-on-surface outline-none placeholder:text-on-surface-variant/60 disabled:opacity-50"
          {...rest}
        />
      </div>
      {(error || helperText) && (
        <p
          id={describedBy}
          // Hata metni BELİRDİĞİNDE ekran okuyucuya duyurulur (Tur 704, m3-ui-reviewer).
          // Yalnız `aria-describedby` yetmiyordu: bazı ekran okuyucular o içeriği
          // ancak alana YENİDEN odaklanınca okur — oysa gönderimden sonra odak
          // alanda kalıyor, dolayısıyla "PIN hatalı" sessizce geçebiliyordu.
          // Yardımcı metin (helperText) statiktir, duyurulmaz.
          role={error ? "alert" : undefined}
          className={`mt-1 text-body-small ${error ? "text-error" : "text-on-surface-variant"}`}
        >
          {error || helperText}
        </p>
      )}
    </div>
  );
}
