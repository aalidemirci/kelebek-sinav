// Paylaşılan sıralama şeridi (Tur 364) — "kolon başlığı" gibi davranan, anında
// uygulanan sıralama kontrolü. Öğrenci listesindeki StudentSortHeader (Tur 168)
// deseninden genelleştirildi; personel/proje/kulüp gibi adlı kayıt listeleri de
// kullanır. Sıralama backend'de (ICU Türkçe collation) yapılır → sayfalar arası
// tutarlı. Sıralama değeri "<alan>" (artan) / "-<alan>" (azalan) sözleşmesini izler.
//
// Erişilebilirlik (§7.5): role=group + yön bilgili aria-label/aria-pressed,
// 48px dokunma hedefi, görünür focus halkası. Yalnız M3 token.

import Icon from "./Icon";

export type SortField = { key: string; label: string };

// Tıklanan alanın sıradaki değerini hesaplar: aynı alan → yön çevir (artan↔azalan);
// yeni alan → artan ile başla. Saf fonksiyon (test edilebilir).
export function nextSort(current: string, field: string): string {
  const active = current === field || current === `-${field}`;
  const desc = current.startsWith("-");
  if (active) return desc ? field : `-${field}`;
  return field;
}

export default function SortHeader({
  fields,
  value,
  onChange,
  label = "Sırala:",
  ariaLabel = "Listeyi sırala",
}: {
  fields: SortField[];
  value: string;
  onChange: (next: string) => void;
  label?: string;
  ariaLabel?: string;
}) {
  const activeField = value.startsWith("-") ? value.slice(1) : value;
  const desc = value.startsWith("-");
  return (
    <div className="flex items-center gap-1" role="group" aria-label={ariaLabel}>
      <span className="mr-1 text-body-small text-on-surface-variant">{label}</span>
      {fields.map((f) => (
        <SortChip
          key={f.key}
          label={f.label}
          active={activeField === f.key}
          desc={desc}
          onClick={() => onChange(nextSort(value, f.key))}
        />
      ))}
    </div>
  );
}

function SortChip({
  label,
  active,
  desc,
  onClick,
}: {
  label: string;
  active: boolean;
  desc: boolean;
  onClick: () => void;
}) {
  const dirLabel = active ? (desc ? "azalan sıralı" : "artan sıralı") : "sıralamak için tıkla";
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      aria-label={`${label} — ${dirLabel}`}
      className={`inline-flex min-h-12 items-center gap-1 rounded-full px-3 text-label-large outline-none transition focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 focus-visible:ring-offset-surface ${
        active
          ? "bg-secondary-container text-on-secondary-container"
          : "text-on-surface-variant hover:bg-on-surface/8"
      }`}
    >
      <span>{label}</span>
      {active && <Icon name={desc ? "arrow_downward" : "arrow_upward"} size="base" />}
    </button>
  );
}
