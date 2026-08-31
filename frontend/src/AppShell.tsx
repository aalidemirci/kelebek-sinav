import { useState } from "react";
import type { ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";

import UpdateBanner from "./modules/guncelleme/UpdateBanner";
import DensitySwitcher from "./ui/DensitySwitcher";
import Icon from "./ui/Icon";
import ThemeSwitcher from "./ui/ThemeSwitcher";

interface NavItem {
  to: string;
  label: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Panel", icon: "space_dashboard" },
  { to: "/takvimler", label: "Takvimler", icon: "calendar_month" },
  { to: "/oturumlar", label: "Oturumlar", icon: "event_seat" },
  { to: "/salonlar", label: "Salonlar", icon: "meeting_room" },
  { to: "/kisiler", label: "Kişiler", icon: "group" },
  { to: "/dersler", label: "Ders Havuzu", icon: "menu_book" },
  { to: "/ayarlar", label: "Ayarlar", icon: "settings" },
  { to: "/kilavuz", label: "Kılavuz", icon: "auto_stories" },
];

const PAGE_TITLES: Array<[prefix: string, title: string]> = [
  ["/takvimler", "Sınav takvimleri"],
  ["/oturumlar", "Sınav oturumları"],
  ["/salonlar", "Sınav salonları"],
  ["/kisiler", "Kişiler"],
  ["/dersler", "Ders havuzu"],
  ["/ayarlar", "Ayarlar"],
  ["/kilavuz", "Kullanım Kılavuzu"],
  ["/hakkinda", "Hakkında ve Lisans"],
  ["/kurulum", "Kurulum"],
  ["/", "Genel bakış"],
];

const COLLAPSE_KEY = "kelebek-sinav-sidebar-collapsed";

function pageTitle(pathname: string): string {
  return (
    PAGE_TITLES.find(([prefix]) =>
      prefix === "/" ? pathname === "/" : pathname.startsWith(prefix),
    )?.[1] ?? "Kelebek Sınav"
  );
}

function navLinkClass(isActive: boolean, collapsed: boolean): string {
  const base = `group relative flex min-h-11 items-center overflow-hidden rounded-shape-md text-label-large font-medium transition-all duration-short-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
    collapsed ? "justify-center px-2" : "gap-3 px-3"
  }`;
  return isActive
    ? `${base} bg-sidebar-active text-white shadow-elevation-1`
    : `${base} text-on-sidebar-muted hover:bg-white/8 hover:text-on-sidebar`;
}

function SidebarContent({
  collapsed,
  onNavigate,
}: {
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  return (
    <>
      <div
        className={`flex h-20 shrink-0 items-center border-b border-white/10 ${
          collapsed ? "justify-center px-2" : "gap-3 px-4"
        }`}
      >
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-shape-lg bg-white/95 shadow-elevation-2">
          <img src="/app-logo.png" alt="" className="h-10 w-10 object-contain" />
        </span>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-title-medium font-semibold tracking-tight text-on-sidebar">
              Kelebek Sınav
            </p>
          </div>
        )}
      </div>

      {!collapsed && (
        <p className="px-5 pb-2 pt-5 text-label-small font-semibold uppercase tracking-widest text-on-sidebar-muted/70">
          Çalışma alanı
        </p>
      )}
      <nav aria-label="Ana gezinme" className="flex flex-1 flex-col gap-1.5 px-3 py-2">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            title={collapsed ? item.label : undefined}
            aria-label={collapsed ? item.label : undefined}
            onClick={onNavigate}
            className={({ isActive }) => navLinkClass(isActive, collapsed)}
          >
            <span aria-hidden="true" className="state-layer" />
            <Icon name={item.icon} size="xl" filled className="relative z-10 shrink-0 opacity-95" />
            {!collapsed && <span className="relative z-10 truncate">{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="space-y-1 border-t border-white/10 p-3">
        {!collapsed && (
          <div className="mb-2 rounded-shape-md border border-white/10 bg-white/5 px-3 py-2.5">
            <p className="flex items-center gap-2 text-label-medium text-on-sidebar">
              <span className="h-2 w-2 rounded-full bg-success" />
              Yerel çalışma
            </p>
            <p className="mt-0.5 text-body-small text-on-sidebar-muted">Veriler bu cihazda</p>
          </div>
        )}
        <NavLink
          to="/hakkinda"
          title={collapsed ? "Hakkında ve Lisans" : undefined}
          aria-label={collapsed ? "Hakkında ve Lisans" : undefined}
          onClick={onNavigate}
          className={({ isActive }) => navLinkClass(isActive, collapsed)}
        >
          <span aria-hidden="true" className="state-layer" />
          <Icon name="info" size="xl" filled className="relative z-10 shrink-0 opacity-95" />
          {!collapsed && <span className="relative z-10 truncate">Hakkında ve Lisans</span>}
        </NavLink>
        <DensitySwitcher
          collapsed={collapsed}
          className="text-on-sidebar-muted hover:bg-white/8 hover:text-on-sidebar"
        />
        <div
          className={`flex min-h-10 items-center rounded-shape-md ${
            collapsed ? "justify-center" : "gap-1 px-1"
          }`}
        >
          <ThemeSwitcher className="text-on-sidebar-muted hover:bg-white/8 hover:text-on-sidebar" />
          {!collapsed && <span className="text-label-large text-on-sidebar-muted">Tema</span>}
        </div>
      </div>
    </>
  );
}

export default function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(
    () => window.localStorage.getItem(COLLAPSE_KEY) === "true",
  );
  const [mobileOpen, setMobileOpen] = useState(false);
  const title = pageTitle(location.pathname);

  const toggleCollapsed = () => {
    setCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem(COLLAPSE_KEY, String(next));
      return next;
    });
  };

  return (
    <div className="flex min-h-screen bg-surface text-on-surface">
      <aside
        className={`ks-sidebar-glow sticky top-0 z-40 hidden h-screen shrink-0 flex-col transition-[width] duration-medium-1 ease-emphasized lg:flex ${
          collapsed ? "w-[4.75rem]" : "w-60"
        }`}
      >
        <SidebarContent collapsed={collapsed} />
        <button
          type="button"
          onClick={toggleCollapsed}
          aria-label={collapsed ? "Kenar çubuğunu genişlet" : "Kenar çubuğunu daralt"}
          title={collapsed ? "Kenar çubuğunu genişlet" : "Kenar çubuğunu daralt"}
          className="absolute -right-3 top-24 flex h-7 w-7 items-center justify-center rounded-full border border-outline-variant bg-surface-container-lowest text-on-surface-variant shadow-elevation-2 transition hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <Icon name={collapsed ? "chevron_right" : "chevron_left"} size="sm" />
        </button>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-outline-variant/70 bg-surface-container-lowest/95 px-4 backdrop-blur-md sm:px-5 lg:px-7">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            aria-label="Gezinme menüsünü aç"
            className="ks-icon-button lg:hidden"
          >
            <Icon name="menu" />
          </button>
          <img src="/app-logo.png" alt="" className="h-9 w-9 shrink-0 object-contain lg:hidden" />
          <div className="min-w-0 lg:w-48">
            <p className="truncate text-title-medium font-semibold text-on-surface">{title}</p>
            <p className="hidden truncate text-body-small text-on-surface-variant lg:block">
              Kelebek Sınav
            </p>
          </div>

          {/* F0 notu: genel arama (öğrenci/oturum) F3'te, "Yeni Sınav" hızlı
              eylemi sihirbazla birlikte F3'te gelir — DD kabuğundaki arama
              formu ve birincil eylem düğmesi o fazda geri eklenecek. */}
          <ThemeSwitcher className="ml-auto" />
        </header>

        <main className="min-w-0 flex-1 overflow-x-hidden px-4 py-5 sm:px-5 lg:px-7 lg:py-6">
          <div className="mx-auto w-full max-w-[100rem]">
            {/* F8: GitHub sürüm denetimi — kabuk remount olmadığından denetim
                uygulama ömründe bir kez koşar; çevrimdışıysa sessizce gizli. */}
            <UpdateBanner />
            {children}
          </div>
        </main>
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 animate-scrim-in bg-scrim/50 backdrop-blur-sm"
            aria-label="Gezinme menüsünü kapat"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="ks-sidebar-glow relative flex h-full w-72 animate-dialog-in flex-col shadow-elevation-4">
            <SidebarContent collapsed={false} onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}
    </div>
  );
}
