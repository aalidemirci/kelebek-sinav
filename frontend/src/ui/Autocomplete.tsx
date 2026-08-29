// M3 stilinde generic combobox/autocomplete bileşeni (Tur 35).
//
// Davranış: kullanıcı yazdıkça `search(query)` çağrılır (300 ms debounce);
// sonuç listesi açılır, klavyeyle (↑↓ Enter Esc) gezilir, seçim yapılınca
// dropdown kapanır ve `onSelect(item)` çağrılır. Mevcut bir değer varsa
// (`selected`) etiketi gösterilen "chip" kart olarak görünür; X'e basınca
// `onClear` ile temizlenir.
//
// KVKK: arama sorguları sunucuya gider; sunucu yetki + KVKK-güvenli serileştirme
// uygular (yalnız id + ad-soyad döner). UI bu garantiyi gösterilemez ama
// sonuçları ekstra alan göstermez.

import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";

import Icon from "./Icon";

interface AutocompleteProps<T> {
  /** Üst etiket — boş geçilirse etiket alanı render edilmez. */
  label: string;
  /** Placeholder metni (henüz seçim yokken). */
  placeholder?: string;
  /** Şu an seçili değer (chip olarak gösterilir); null/undefined ise input açık. */
  selected: T | null | undefined;
  /** Sunucu araması; en az `minChars` karakter sonrası çağrılır. */
  search: (query: string) => Promise<T[]>;
  /** Sonuç bir öğesi seçildiğinde tetiklenir. */
  onSelect: (item: T) => void;
  /** Seçimi temizlemek için (X düğmesi). */
  onClear: () => void;
  /** Liste satırının görsel etiketi. */
  getLabel: (item: T) => string;
  /** Liste satırının alt-etiketi (opsiyonel: sınıf, rol, vb.). */
  getSublabel?: (item: T) => string;
  /** Liste anahtarı (genelde `id`). */
  getKey: (item: T) => string | number;
  /**
   * Öğe seçilemezse NEDENİNİ döndürür (örn. "muaf", "aynı saatte görevli");
   * undefined = seçilebilir. Devre dışı öğe listede görünür ama tıklanamaz/
   * Enter ile seçilemez (Tur 242 — gözetmen adayları deseni).
   */
  getDisabled?: (item: T) => string | undefined;
  /** Seçili chip altında gösterilecek yardımcı metin (KVKK uyarısı vb.). */
  helperText?: ReactNode;
  /** Alan-bazlı hata mesajı (kırmızı çerçeve + metin + aria-invalid). TextField/Select ile eşdeğer. */
  error?: string;
  /** Form doğrulaması için zorunluluk işareti (görsel). */
  required?: boolean;
  /** Aramada minimum karakter sayısı (varsayılan 2). */
  minChars?: number;
  /** Debounce süresi ms (varsayılan 300). */
  debounceMs?: number;
  /** Boş sonuçta gösterilecek metin. */
  emptyText?: string;
  /** Hiç sonuç yokken serbest metin kabul edilsin mi (örn. "Diğer" payaşları). */
  allowFreeText?: boolean;
  /** allowFreeText=true ise serbest yazıldıkça çağrılır. */
  onFreeText?: (text: string) => void;
  /** allowFreeText=true ise mevcut serbest metin değeri (input'a yazılır). */
  freeText?: string;
  /** Form etiketleme — useId() ile otomatik üretilir; opsiyonel override. */
  id?: string;
  /**
   * Görsel etiket (`label`) boş geçilen kullanımlarda ekran okuyucu için
   * erişilebilir ad (C16). `label` doluysa yok sayılır (htmlFor bağı yeter).
   */
  ariaLabel?: string;
  disabled?: boolean;
}

export default function Autocomplete<T>({
  label,
  placeholder = "Yazmaya başlayın…",
  selected,
  search,
  onSelect,
  onClear,
  getLabel,
  getSublabel,
  getKey,
  getDisabled,
  helperText,
  error,
  required,
  minChars = 2,
  debounceMs = 300,
  emptyText = "Sonuç bulunamadı.",
  allowFreeText = false,
  onFreeText,
  freeText = "",
  id,
  ariaLabel,
  disabled,
}: AutocompleteProps<T>) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const listId = `${inputId}-listbox`;
  const descId = error || helperText ? `${inputId}-desc` : undefined;

  const [query, setQuery] = useState(freeText);
  const [results, setResults] = useState<T[]>([]);
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(0);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // freeText prop'u dışarıdan değişirse input'u sıfırla (form reset senaryosu).
  useEffect(() => {
    if (!selected && freeText !== query) {
      setQuery(freeText);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [freeText, selected]);

  // Debounce'lu arama
  useEffect(() => {
    if (selected) return; // seçim varsa arama yok
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    if (query.trim().length < minChars) {
      setResults([]);
      setOpen(false);
      return;
    }
    debounceRef.current = window.setTimeout(() => {
      setLoading(true);
      search(query.trim())
        .then((items) => {
          setResults(items);
          setHighlighted(0);
          setOpen(true);
        })
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, debounceMs);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, [query, minChars, debounceMs, search, selected]);

  // Dışarı tıklayınca kapansın
  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const handleKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (!open && (e.key === "ArrowDown" || e.key === "ArrowUp") && results.length) {
      setOpen(true);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlighted((h) => Math.min(h + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlighted((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      if (open && results[highlighted]) {
        e.preventDefault();
        pick(results[highlighted]);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  const pick = (item: T) => {
    if (getDisabled?.(item)) return; // seçilemez öğe — görünür ama tıklanamaz
    onSelect(item);
    setOpen(false);
    setResults([]);
    setQuery(getLabel(item));
  };

  // Eşleşen alt-metni vurgulamak için basit highlight
  const highlight = (text: string): ReactNode => {
    if (!query.trim()) return text;
    const idx = text.toLocaleLowerCase("tr").indexOf(query.trim().toLocaleLowerCase("tr"));
    if (idx < 0) return text;
    return (
      <>
        {text.slice(0, idx)}
        <mark className="bg-tertiary-container text-on-tertiary-container">
          {text.slice(idx, idx + query.trim().length)}
        </mark>
        {text.slice(idx + query.trim().length)}
      </>
    );
  };

  // --- Render ---

  return (
    <div ref={containerRef} className="relative">
      {label && (
        <label htmlFor={inputId} className="mb-1 block text-label-large text-on-surface-variant">
          {label}
          {required && <span className="text-error"> *</span>}
        </label>
      )}

      {selected ? (
        // Seçili chip görünümü
        <div className="flex items-center justify-between gap-3 rounded-shape-md bg-secondary-container px-4 py-2 text-body-medium text-on-secondary-container">
          <div className="min-w-0">
            <p className="truncate font-medium">{getLabel(selected)}</p>
            {getSublabel && getSublabel(selected) && (
              <p className="truncate text-label-small opacity-80">{getSublabel(selected)}</p>
            )}
          </div>
          {!disabled && (
            <button
              type="button"
              onClick={() => {
                onClear();
                setQuery("");
                setResults([]);
                setTimeout(() => inputRef.current?.focus(), 0);
              }}
              className="-my-2 -mr-2 flex min-h-12 min-w-12 shrink-0 items-center justify-center rounded-full hover:bg-on-secondary-container/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              aria-label="Seçimi temizle"
            >
              <Icon name="close" size="base" />
            </button>
          )}
        </div>
      ) : (
        // Arama input'u
        <div
          className={`flex h-14 items-center rounded-shape-xs border bg-surface px-4 ${
            error
              ? "border-error focus-within:border-error focus-within:ring-2 focus-within:ring-error"
              : "border-outline focus-within:border-primary focus-within:ring-2 focus-within:ring-primary"
          }`}
          role="combobox"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-controls={listId}
        >
          <Icon name="search" size="base" className="mr-2 text-on-surface-variant" />
          <input
            ref={inputRef}
            id={inputId}
            type="text"
            autoComplete="off"
            disabled={disabled}
            required={required && !allowFreeText}
            aria-invalid={error ? true : undefined}
            aria-label={!label ? ariaLabel : undefined}
            aria-describedby={descId}
            value={query}
            placeholder={placeholder}
            onChange={(e) => {
              const v = e.target.value;
              setQuery(v);
              if (allowFreeText) onFreeText?.(v);
            }}
            onFocus={() => {
              if (results.length > 0) setOpen(true);
            }}
            onKeyDown={handleKey}
            aria-autocomplete="list"
            aria-activedescendant={
              open && results[highlighted] ? `${listId}-opt-${highlighted}` : undefined
            }
            className="w-full bg-transparent text-body-large text-on-surface outline-none placeholder:text-on-surface-variant/60 disabled:opacity-50"
          />
          {loading && (
            <span className="ml-2 text-label-small text-on-surface-variant">aranıyor…</span>
          )}
          {!loading && query && (
            <button
              type="button"
              onClick={() => {
                setQuery("");
                setResults([]);
                setOpen(false);
                if (allowFreeText) onFreeText?.("");
              }}
              className="-mr-2 ml-1 flex min-h-12 min-w-12 items-center justify-center rounded-full text-on-surface-variant hover:bg-on-surface/10"
              aria-label="Temizle"
              tabIndex={-1}
            >
              <Icon name="close" size="base" />
            </button>
          )}
        </div>
      )}

      {/* Sonuç listesi */}
      {!selected && open && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-30 mt-1 max-h-72 w-full overflow-y-auto rounded-shape-sm border border-outline-variant bg-surface-container-high shadow-elevation-2"
        >
          {results.length === 0 && !loading ? (
            <li className="px-4 py-3 text-body-medium text-on-surface-variant">
              {emptyText}
              {allowFreeText && query.trim() && (
                <span className="ml-2 text-label-small">
                  ("{query.trim()}" serbest metin olarak kalır)
                </span>
              )}
            </li>
          ) : (
            results.map((item, i) => {
              const disabledReason = getDisabled?.(item);
              return (
                <li
                  key={getKey(item)}
                  id={`${listId}-opt-${i}`}
                  role="option"
                  aria-selected={i === highlighted}
                  aria-disabled={disabledReason ? true : undefined}
                  onMouseEnter={() => setHighlighted(i)}
                  onMouseDown={(e) => {
                    // mousedown: input'tan focus düşmeden seçimi tamamla
                    e.preventDefault();
                    pick(item);
                  }}
                  className={`px-4 py-2 text-body-medium ${
                    disabledReason
                      ? "cursor-not-allowed opacity-50"
                      : i === highlighted
                        ? "cursor-pointer bg-secondary-container text-on-secondary-container"
                        : "cursor-pointer text-on-surface hover:bg-surface-container-low"
                  }`}
                >
                  <p className="truncate">{highlight(getLabel(item))}</p>
                  {(disabledReason || (getSublabel && getSublabel(item))) && (
                    <p className="truncate text-label-small opacity-75">
                      {getSublabel?.(item)}
                      {disabledReason && <span className="text-error"> — {disabledReason}</span>}
                    </p>
                  )}
                </li>
              );
            })
          )}
        </ul>
      )}

      {(error || helperText) && (
        <p
          id={descId}
          className={`mt-1 text-body-small ${error ? "text-error" : "text-on-surface-variant"}`}
        >
          {error || helperText}
        </p>
      )}
    </div>
  );
}
