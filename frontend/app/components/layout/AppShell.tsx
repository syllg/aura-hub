"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { checkApi, USE_MOCK_DATA } from "@/app/lib/api-client";
import Icon, { type IconName } from "../Icon";
import StatusBadge from "../feedback/StatusBadge";

const navItems: Array<{ href: string; label: string; icon: IconName }> = [
  { href: "/chat", label: "AuraHub Assistant", icon: "bot" },
  { href: "/analytics", label: "Sales Analytics", icon: "analytics" },
];

function Navigation({ pathname, onNavigate, collapsed = false }: { pathname: string; onNavigate?: () => void; collapsed?: boolean }) {
  return (
    <nav className="primary-nav" aria-label="Navigasi utama">
      {!collapsed ? <p className="nav-kicker">Workspace</p> : null}
      {navItems.map((item) => {
        const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link key={item.href} className={`nav-link${active ? " is-active" : ""}`} href={item.href} aria-current={active ? "page" : undefined} onClick={onNavigate} title={collapsed ? item.label : undefined}>
            <Icon name={item.icon} size={20} />
            {!collapsed ? <span>{item.label}</span> : <span className="visually-hidden">{item.label}</span>}
          </Link>
        );
      })}
    </nav>
  );
}

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link className={`brand${compact ? " is-compact" : ""}`} href="/" aria-label="Aura Hub — halaman overview">
      <span className="brand-mark" aria-hidden="true"><span /><span /><span /></span>
      {!compact ? <span className="brand-copy"><strong translate="no">AURA HUB</strong><small>Retail Intelligence</small></span> : null}
    </Link>
  );
}

export default function AppShell({
  children,
  title,
  description,
  action,
}: {
  children: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const drawerRef = useRef<HTMLDialogElement>(null);
  const api = useQuery({ queryKey: ["api-status"], queryFn: ({ signal }) => checkApi(signal), refetchInterval: 30_000 });

  useEffect(() => {
    const dialog = drawerRef.current;
    const closeOnRoute = () => dialog?.open && dialog.close();
    closeOnRoute();
  }, [pathname]);

  const status = USE_MOCK_DATA ? "demo" : api.isPending ? "connecting" : api.isSuccess ? "connected" : "disconnected";

  return (
    <div className={`app-shell${collapsed ? " sidebar-collapsed" : ""}`}>
      <a className="skip-link" href="#main-content">Lewati ke Konten Utama</a>

      <aside className="sidebar" aria-label="Sidebar aplikasi">
        <Brand compact={collapsed} />
        <Navigation pathname={pathname} collapsed={collapsed} />
        <div className="sidebar-footer">
          {!collapsed ? (
            <div className="api-summary">
              <span className={`connection-dot ${status}`} aria-hidden="true" />
              <div><strong>Status API</strong><span>{status === "connected" ? "Terhubung" : status === "connecting" ? "Menghubungkan…" : status === "demo" ? "Mode demo" : "Terputus"}</span></div>
            </div>
          ) : null}
          {!collapsed ? <span className="app-version">Aura Hub v1.0.0</span> : null}
          <button className="sidebar-collapse" type="button" onClick={() => setCollapsed((value) => !value)} aria-label={collapsed ? "Perluas sidebar" : "Ciutkan sidebar"} aria-expanded={!collapsed}>
            <Icon name={collapsed ? "expand" : "collapse"} size={19} />
            {!collapsed ? <span>Ciutkan Sidebar</span> : null}
          </button>
        </div>
      </aside>

      <dialog ref={drawerRef} className="mobile-drawer" aria-label="Menu navigasi">
        <div className="drawer-head"><Brand /><button className="icon-button" type="button" onClick={() => drawerRef.current?.close()} aria-label="Tutup menu"><Icon name="close" /></button></div>
        <Navigation pathname={pathname} onNavigate={() => drawerRef.current?.close()} />
        <div className="drawer-footer"><span>Aura Hub v1.0.0</span><StatusBadge tone={status === "connected" || status === "demo" ? "success" : status === "connecting" ? "info" : "danger"}>{status === "demo" ? "Demo Data" : status === "connected" ? "API Connected" : status === "connecting" ? "Connecting" : "Disconnected"}</StatusBadge></div>
      </dialog>

      <div className="workspace">
        <header className="topbar">
          <button className="icon-button mobile-menu-button" type="button" onClick={() => drawerRef.current?.showModal()} aria-label="Buka menu navigasi"><Icon name="menu" /></button>
          <div className="topbar-title"><h1>{title}</h1><p>{description}</p></div>
          <div className="topbar-actions">
            <StatusBadge tone={status === "connected" || status === "demo" ? "success" : status === "connecting" ? "info" : "danger"}>
              {status === "demo" ? "Demo Data" : status === "connected" ? "API Connected" : status === "connecting" ? "Connecting" : "Disconnected"}
            </StatusBadge>
            {action}
            <div className="internal-user" aria-label="Pengguna internal"><span className="avatar">SL</span><span><strong>Sylvie Lee</strong><small>Tim Operasional</small></span></div>
          </div>
        </header>

        <main id="main-content" tabIndex={-1} className="main-content">{children}</main>
      </div>
    </div>
  );
}
