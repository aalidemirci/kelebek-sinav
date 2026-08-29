/** @type {import('tailwindcss').Config} */
// Material Design 3 tasarım token'ları (CLAUDE.md §7.5). Renkler index.css'teki
// CSS değişkenlerinden (RGB kanal) gelir → opaklık modifiyeleri (state layer) çalışır
// ve karanlık tema ileride tek yerden açılır.

const color = (name) => `rgb(var(--md-${name}) / <alpha-value>)`;

// Storybook M3Tokens showcase'i dinamik (`bg-${name}`) class adları kullanır;
// Tailwind JIT bu desenleri statik tarayamadığı için showcase'te görülen
// renk rollerini açıkça safelist'e alıyoruz. Üretim bundle'ı sadece bu liste
// + içerik taramasından gelenleri içerir (gereksiz büyüme yok).
const M3_ROLE_TOKENS = [
  "primary",
  "on-primary",
  "primary-container",
  "on-primary-container",
  "secondary",
  "on-secondary",
  "secondary-container",
  "on-secondary-container",
  "tertiary",
  "on-tertiary",
  "tertiary-container",
  "on-tertiary-container",
  "error",
  "on-error",
  "error-container",
  "on-error-container",
  "surface",
  "on-surface",
  "surface-variant",
  "on-surface-variant",
  "surface-container-lowest",
  "surface-container-low",
  "surface-container",
  "surface-container-high",
  "surface-container-highest",
  "surface-dim",
  "surface-bright",
  "surface-tint",
  "outline",
  "outline-variant",
  "inverse-surface",
  "inverse-on-surface",
  "inverse-primary",
];

// Ders programı ders renk paleti (Tur 282) — index.css `--md-subject-1..12`.
const SUBJECT_TOKENS = Array.from({ length: 12 }, (_, i) => `subject-${i + 1}`);

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  safelist: [
    ...M3_ROLE_TOKENS.flatMap((t) => [`bg-${t}`, `text-${t}`]),
    // subjectColor() dinamik `bg-subject-N` üretir → JIT statik tarayamaz, safelist'le.
    ...SUBJECT_TOKENS.map((t) => `bg-${t}`),
    "rounded-shape-xs",
    "rounded-shape-sm",
    "rounded-shape-md",
    "rounded-shape-lg",
    "rounded-shape-xl",
    "shadow-elevation-1",
    "shadow-elevation-2",
    "shadow-elevation-3",
    "shadow-elevation-4",
    "shadow-elevation-5",
  ],
  theme: {
    extend: {
      colors: {
        primary: color("primary"),
        "on-primary": color("on-primary"),
        "primary-container": color("primary-container"),
        "on-primary-container": color("on-primary-container"),
        secondary: color("secondary"),
        "on-secondary": color("on-secondary"),
        "secondary-container": color("secondary-container"),
        "on-secondary-container": color("on-secondary-container"),
        tertiary: color("tertiary"),
        "on-tertiary": color("on-tertiary"),
        "tertiary-container": color("tertiary-container"),
        "on-tertiary-container": color("on-tertiary-container"),
        error: color("error"),
        "on-error": color("on-error"),
        "error-container": color("error-container"),
        "on-error-container": color("on-error-container"),
        surface: color("surface"),
        "on-surface": color("on-surface"),
        "surface-variant": color("surface-variant"),
        "on-surface-variant": color("on-surface-variant"),
        "surface-container-lowest": color("surface-container-lowest"),
        "surface-container-low": color("surface-container-low"),
        "surface-container": color("surface-container"),
        "surface-container-high": color("surface-container-high"),
        "surface-container-highest": color("surface-container-highest"),
        "surface-dim": color("surface-dim"),
        "surface-bright": color("surface-bright"),
        "surface-tint": color("surface-tint"),
        outline: color("outline"),
        "outline-variant": color("outline-variant"),
        "inverse-surface": color("inverse-surface"),
        "inverse-on-surface": color("inverse-on-surface"),
        "inverse-primary": color("inverse-primary"),
        scrim: color("scrim"),
        sidebar: "rgb(var(--ks-sidebar) / <alpha-value>)",
        "sidebar-raised": "rgb(var(--ks-sidebar-raised) / <alpha-value>)",
        "on-sidebar": "rgb(var(--ks-on-sidebar) / <alpha-value>)",
        "on-sidebar-muted": "rgb(var(--ks-on-sidebar-muted) / <alpha-value>)",
        "sidebar-active": "rgb(var(--ks-sidebar-active) / <alpha-value>)",
        success: "rgb(var(--ks-success) / <alpha-value>)",
        "success-container": "rgb(var(--ks-success-container) / <alpha-value>)",
        "on-success-container": "rgb(var(--ks-on-success-container) / <alpha-value>)",
        ...Object.fromEntries(SUBJECT_TOKENS.map((t) => [t, color(t)])),
      },
      fontFamily: {
        sans: [
          "Segoe UI Variable",
          "Segoe UI",
          "Inter",
          "Roboto",
          "system-ui",
          "Arial",
          "sans-serif",
        ],
      },
      // M3 tip ölçeği: [boyut, { satır yüksekliği, harf aralığı, ağırlık }]
      fontSize: {
        "display-large": ["57px", { lineHeight: "64px", letterSpacing: "-0.25px" }],
        "display-medium": ["45px", { lineHeight: "52px" }],
        "display-small": ["36px", { lineHeight: "44px" }],
        "headline-large": ["32px", { lineHeight: "40px" }],
        "headline-medium": ["28px", { lineHeight: "36px" }],
        "headline-small": ["24px", { lineHeight: "32px" }],
        "title-large": ["22px", { lineHeight: "28px" }],
        "title-medium": [
          "16px",
          { lineHeight: "24px", letterSpacing: "0.15px", fontWeight: "500" },
        ],
        "title-small": ["14px", { lineHeight: "20px", letterSpacing: "0.1px", fontWeight: "500" }],
        "body-large": ["16px", { lineHeight: "24px", letterSpacing: "0.5px" }],
        "body-medium": ["14px", { lineHeight: "20px", letterSpacing: "0.25px" }],
        "body-small": ["12px", { lineHeight: "16px", letterSpacing: "0.4px" }],
        "label-large": ["14px", { lineHeight: "20px", letterSpacing: "0.1px", fontWeight: "500" }],
        "label-medium": ["12px", { lineHeight: "16px", letterSpacing: "0.5px", fontWeight: "500" }],
        "label-small": ["11px", { lineHeight: "16px", letterSpacing: "0.5px", fontWeight: "500" }],
        // Kiosk saat ölçekleri (C31, Tur 615) — M3 display üstü, tahta-özel;
        // uzaktan okunabilirlik için amaca-özel token (ham arbitrary değer yasak, §7.5).
        "kiosk-clock": ["6rem", { lineHeight: "1" }],
        "kiosk-clock-lg": ["9rem", { lineHeight: "1" }],
      },
      // M3 şekil ölçeği (köşe yarıçapı). "Full" (tam yuvarlak / hap) durağı
      // BİLİNÇLİ olarak burada yok: Tailwind'in yerleşik `rounded-full` token'ı
      // aynı şeydir ve kod tabanında zaten tek idiom odur — ikinci bir ad
      // (`shape-full`) eşanlamlı token yaratıp ölçeği çatallardı.
      borderRadius: {
        "shape-xs": "4px",
        "shape-sm": "8px",
        "shape-md": "12px",
        "shape-lg": "16px",
        "shape-xl": "28px",
      },
      // M3 state layer opaklıkları (hover %8, focus/pressed %12) — index.css
      // `--md-state-*` ile aynı değerler. Tailwind'in varsayılan opaklık ölçeği
      // 5'er adımlıdır (…/5, /10, /20); 8 ve 12 orada YOKTUR, dolayısıyla
      // `bg-on-surface/8` yazılınca JIT sessizce hiçbir kural üretmezdi
      // (satır hover'ı hiç görünmüyordu). Ölçeğe eklenerek düzeltilir.
      opacity: {
        8: "0.08",
        12: "0.12",
      },
      // M3 hareket (motion) — easing eğrileri (Tur 311, öneri §1). Değerler
      // index.css `--md-easing-*` değişkenlerinden gelir → tek doğruluk kaynağı.
      // Kullanım: `ease-standard`, `ease-emphasized-decelerate`…
      transitionTimingFunction: {
        standard: "var(--md-easing-standard)",
        "standard-decelerate": "var(--md-easing-standard-decelerate)",
        "standard-accelerate": "var(--md-easing-standard-accelerate)",
        emphasized: "var(--md-easing-emphasized)",
        "emphasized-decelerate": "var(--md-easing-emphasized-decelerate)",
        "emphasized-accelerate": "var(--md-easing-emphasized-accelerate)",
      },
      // M3 süre ölçeği — `--md-duration-*` değişkenlerinden. Tailwind'in sayısal
      // `duration-150` default'ları korunur; bunlar ek olarak gelir
      // (`duration-short-3`, `duration-medium-2`…).
      transitionDuration: {
        "short-1": "var(--md-duration-short-1)",
        "short-2": "var(--md-duration-short-2)",
        "short-3": "var(--md-duration-short-3)",
        "short-4": "var(--md-duration-short-4)",
        "medium-1": "var(--md-duration-medium-1)",
        "medium-2": "var(--md-duration-medium-2)",
        "medium-3": "var(--md-duration-medium-3)",
        "medium-4": "var(--md-duration-medium-4)",
        "long-1": "var(--md-duration-long-1)",
        "long-2": "var(--md-duration-long-2)",
        "long-3": "var(--md-duration-long-3)",
        "long-4": "var(--md-duration-long-4)",
      },
      // M3 giriş animasyonları (Tur 314) — Dialog/menü gibi yüzeyler için. Easing
      // emphasized-decelerate (vurgulu giriş), süre Faz A token'larından. Çıkış
      // bileşen unmount'la olur (ayrı çıkış animasyonu yok). prefers-reduced-motion
      // global bloğu animation-duration'ı sıfırlar → hareket-hassas kullanıcıda anında.
      keyframes: {
        "scrim-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "dialog-in": {
          from: { opacity: "0", transform: "scale(0.95)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
      },
      animation: {
        "scrim-in": "scrim-in var(--md-duration-short-4) var(--md-easing-standard)",
        "dialog-in": "dialog-in var(--md-duration-medium-2) var(--md-easing-emphasized-decelerate)",
      },
      // M3 yükselti (elevation 1–5) — yumuşak gölge yaklaşımları.
      boxShadow: {
        "elevation-1":
          "0 1px 2px rgb(15 42 61 / 0.04), 0 6px 18px rgb(15 42 61 / 0.05)",
        "elevation-2":
          "0 2px 4px rgb(15 42 61 / 0.06), 0 12px 28px rgb(15 42 61 / 0.08)",
        "elevation-3":
          "0 4px 8px rgb(15 42 61 / 0.08), 0 20px 48px rgb(15 42 61 / 0.14)",
        "elevation-4":
          "0 8px 16px rgb(15 42 61 / 0.1), 0 28px 64px rgb(15 42 61 / 0.16)",
        "elevation-5":
          "0 12px 24px rgb(15 42 61 / 0.12), 0 36px 80px rgb(15 42 61 / 0.18)",
      },
      // Master/detail (liste + detay) düzen token'ları (C7) — markup'taki arbitrary
      // `grid-cols-[minmax(...)]` yerine adlı, merkezî layout token'ları. fr-oranlı
      // (list-detail / detail-list) + sabit-yan-panel (pane-sm/md/lg: 320/420/520px).
      gridTemplateColumns: {
        "list-detail": "minmax(0, 2fr) minmax(0, 3fr)",
        "detail-list": "minmax(0, 3fr) minmax(0, 2fr)",
        "pane-sm": "minmax(0, 320px) minmax(0, 1fr)",
        "pane-md": "minmax(0, 420px) minmax(0, 1fr)",
        "pane-lg": "minmax(0, 520px) minmax(0, 1fr)",
      },
      // min-width: Tailwind varsayılanında boşluk ölçeği yok (yalnız 0/full/min/max/
      // fit). min-height ile tutarlı olsun ve arbitrary `min-w-[Npx]` yerine ölçek
      // kullanılabilsin diye 4px-tabanlı boşluk ölçeğini ekliyoruz (C10).
      // `table`: geniş tabloların responsive kırılma alt sınırı (F28, Tur 247 —
      // C7 emsali: layout kısıtı markup'ta arbitrary değil, token katmanında).
      minWidth: ({ theme }) => ({ ...theme("spacing"), table: "37.5rem" }),
    },
  },
  plugins: [],
};
