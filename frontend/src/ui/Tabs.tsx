// M3 sekme çubuğu (CLAUDE.md §7.5): alt-çizgi göstergeli sekmeler. role="tablist"
// + role="tab" + aria-selected; aktif sekme border-b-2 border-primary. Dokunma
// hedefi h-12 (48px). Token tüketir, ham renk yok. (DenetimPage deseni buradan.)
//
// Erişilebilirlik (Tur 116, C3 — WAI-ARIA tabs deseni): roving tabindex (yalnız aktif
// sekme Tab ile odaklanır) + Sol/Sağ ok ile sekme değişimi (otomatik etkinleştirme) +
// Home/End ilk/son. Klavye odağı görünür focus halkasıyla işaretlenir (focus-visible).
//
// Panel bağı (Tur 136, C5 — WAI-ARIA tabpanel linkage): `idBase` verilirse her sekme
// `id` + `aria-controls` alır; tüketici panel kabına `tabPanelProps(idBase, active)`
// yayar (role=tabpanel + id + aria-labelledby). Tek-panel (içerik-değişen) deseni:
// tek panel id'si, `aria-labelledby` aktif sekmeye işaret eder.
//
// M3 "scrollable tabs" (Tur 315, Ek A): çok sekme dar ekrana sığmaz → yatay kaydırma.
// Native kaydırma çubuğu GİZLİ (.scrollbar-none); taşma kenar solmasıyla (edge fade —
// kaydırma konumuna göre sol/sağ/iki) bildirilir. Dikey tekerlek yatay kaydırmaya
// çevrilir (trackpad'siz okul PC'leri). Aktif sekme görünür değilse görünüre kaydırılır
// (her zaman DEĞİL → açılışta ilk sekmeyi itmez). overflow-y gizli (çapraz-eksen çubuğu).

import { useCallback, useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";

import Icon from "./Icon";

export interface TabItem {
  key: string;
  label: string;
  /** Material Symbols ikon adı (opsiyonel). */
  icon?: string;
}

interface TabsProps {
  items: TabItem[];
  active: string;
  onChange: (key: string) => void;
  /** Sekme çubuğunun erişilebilir adı. */
  ariaLabel?: string;
  /**
   * Sekme/panel WAI-ARIA bağı (C5) için benzersiz önek. Verilirse her sekme
   * `id={`${idBase}-tab-${key}`}` + `aria-controls={`${idBase}-panel`}` alır;
   * panel kabı `tabPanelProps(idBase, active)` ile eşlenir. Verilmezse bağ
   * eklenmez (geriye uyum).
   */
  idBase?: string;
}

/**
 * Bir `Tabs` (aynı `idBase`) ile eşlenen panel kabının WAI-ARIA öznitelikleri.
 * Tüketici, sekmelerin altındaki içerik bölgesine yayar:
 *   <div {...tabPanelProps("denetim", tab)}>{panel}</div>
 * Tek-panel (içerik-değişen) deseni: tek `id`, `aria-labelledby` aktif sekmeye
 * işaret eder. Panel'ler odaklanabilir içerik taşıdığı için `tabIndex` eklenmez
 * (WAI-ARIA APG: odaklanabilir içerikli tabpanel sekme sırasına alınmaz).
 */
export function tabPanelProps(idBase: string, activeKey: string) {
  return {
    role: "tabpanel" as const,
    id: `${idBase}-panel`,
    "aria-labelledby": `${idBase}-tab-${activeKey}`,
  };
}

export default function Tabs({ items, active, onChange, ariaLabel, idBase }: TabsProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const activeIndex = items.findIndex((i) => i.key === active);
  // Kenar solması durumu (kaydırma konumuna göre). Taşma yokken solma yok →
  // ilk/son sekme dinlenme halinde kırpılmaz.
  const [fade, setFade] = useState<{ left: boolean; right: boolean }>({
    left: false,
    right: false,
  });

  const updateFade = useCallback(() => {
    const el = listRef.current;
    if (el === null) return;
    const left = el.scrollLeft > 1;
    const right = el.scrollLeft + el.clientWidth < el.scrollWidth - 1;
    setFade((prev) => (prev.left === left && prev.right === right ? prev : { left, right }));
  }, []);

  // Kaydırma / yeniden boyutlandırma / öğe sayısı değişiminde solmayı güncelle.
  useEffect(() => {
    updateFade();
    const el = listRef.current;
    if (el === null) return;
    el.addEventListener("scroll", updateFade, { passive: true });
    window.addEventListener("resize", updateFade);
    return () => {
      el.removeEventListener("scroll", updateFade);
      window.removeEventListener("resize", updateFade);
    };
  }, [updateFade, items.length]);

  // Dikey fare tekerleğini yatay kaydırmaya çevir (trackpad'siz okul PC'leri).
  // Non-passive listener → preventDefault çalışır (React onWheel passive olabilir).
  useEffect(() => {
    const el = listRef.current;
    if (el === null) return;
    const onWheel = (e: WheelEvent) => {
      if (e.deltaY === 0 || el.scrollWidth <= el.clientWidth) return;
      e.preventDefault();
      el.scrollLeft += e.deltaY;
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  // Aktif sekme görünür DEĞİLSE görünüre kaydır (her zaman değil → açılışta ilk
  // sekmeyi itmez; kırpılmanın olası sebebi agresif scrollIntoView'di). Kaydırma
  // yumuşaklığı/azaltılmış-hareket container'ın scroll-smooth/motion-reduce sınıfından.
  useEffect(() => {
    const el = tabRefs.current[activeIndex];
    const container = listRef.current;
    if (el === null || el === undefined || container === null || activeIndex < 0) return;
    const er = el.getBoundingClientRect();
    const cr = container.getBoundingClientRect();
    if (er.left < cr.left || er.right > cr.right) {
      el.scrollIntoView({ inline: "nearest", block: "nearest" });
    }
  }, [active, activeIndex]);

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const count = items.length;
    if (count === 0) return;
    const current = activeIndex < 0 ? 0 : activeIndex;
    let next: number;
    switch (e.key) {
      case "ArrowRight":
        next = (current + 1) % count;
        break;
      case "ArrowLeft":
        next = (current - 1 + count) % count;
        break;
      case "Home":
        next = 0;
        break;
      case "End":
        next = count - 1;
        break;
      default:
        return;
    }
    e.preventDefault();
    onChange(items[next].key);
    // preventScroll: native odak kaydırmasını engelle → görünürlük kaydırması
    // yukarıdaki aktif-sekme efektinden gelir (tek, koşullu yol).
    tabRefs.current[next]?.focus({ preventScroll: true });
  };

  const fadeClass =
    fade.left && fade.right
      ? "tab-fade-both"
      : fade.left
        ? "tab-fade-left"
        : fade.right
          ? "tab-fade-right"
          : "";

  return (
    <div
      ref={listRef}
      role="tablist"
      aria-label={ariaLabel}
      onKeyDown={handleKeyDown}
      // Sekmeler shrink-0 + whitespace-nowrap ile sıkışmaz; focus halkası ring-inset
      // olduğu için overflow ile kırpılmaz. overflow-y gizli (çapraz-eksen çubuğu önlenir).
      // Native çubuk .scrollbar-none ile gizli; taşma fadeClass ile bildirilir. scroll-px-4
      // → kaydırılan sekme kenar solmasının altında kalmaz. Kaydırma reduced-motion'a saygılı.
      className={`flex gap-1 overflow-x-auto overflow-y-hidden rounded-shape-md bg-surface-container p-1 scroll-px-4 scrollbar-none scroll-smooth motion-reduce:scroll-auto ${fadeClass}`}
    >
      {items.map((item, idx) => {
        const isActive = item.key === active;
        return (
          <button
            key={item.key}
            ref={(el) => {
              tabRefs.current[idx] = el;
            }}
            type="button"
            role="tab"
            id={idBase ? `${idBase}-tab-${item.key}` : undefined}
            aria-selected={isActive}
            aria-controls={idBase ? `${idBase}-panel` : undefined}
            tabIndex={isActive ? 0 : -1}
            onClick={() => onChange(item.key)}
            className={`relative flex h-[var(--ks-control-height)] shrink-0 items-center gap-2 whitespace-nowrap rounded-shape-sm px-3 text-label-large transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary ${
              isActive
                ? "bg-surface-container-lowest font-semibold text-primary shadow-sm"
                : "text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface"
            }`}
          >
            {item.icon && <Icon name={item.icon} size="lg" />}
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
