"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  Activity,
  BarChart3,
  Bell,
  Bot,
  Building2,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Command,
  CreditCard,
  Database,
  FileQuestion,
  LayoutDashboard,
  MessageSquareText,
  PanelLeft,
  Plus,
  Radar,
  RefreshCw,
  ScrollText,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Users,
  Workflow,
  X,
  type LucideIcon,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, type ReactNode, useEffect, useMemo, useState } from "react";

import { getDashboardApiBaseUrl } from "../lib/api/client";
import type { ApiEnvelope } from "../lib/api/types";
import type { AuthContext } from "../lib/auth/development-session";
import { navigationItems } from "../lib/navigation";
import { AssistantSwitcher } from "./assistants/assistant-switcher";
import { LogoutButton } from "./logout-button";

type DashboardShellProps = {
  children: ReactNode;
  workspaceName?: string | null;
};

const navIcons: Record<string, LucideIcon> = {
  "/dashboard": Bot,
  "/knowledge": Database,
  "/chatbot": MessageSquareText,
  "/widgets": Workflow,
  "/analytics": BarChart3,
  "/conversations": Activity,
  "/review/unanswered": FileQuestion,
  "/evaluation": ClipboardCheck,
  "/observability": Radar,
  "/feedback-loop": RefreshCw,
  "/prompts": ScrollText,
  "/users": Users,
  "/settings": Settings,
  "/billing": CreditCard,
};

const quickActions = [
  { label: "Create Assistant", href: "/assistants/new", icon: Plus },
  { label: "Upload Knowledge", href: "/knowledge", icon: Database },
  { label: "Open Playground", href: "/chatbot", icon: MessageSquareText },
  { label: "Review Gaps", href: "/review/unanswered", icon: FileQuestion },
] as const;

export function DashboardShell({ children, workspaceName: workspaceNameProp }: DashboardShellProps) {
  const pathname = usePathname();
  const reduceMotion = useReducedMotion();
  const [commandOpen, setCommandOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [fetchedWorkspaceName, setFetchedWorkspaceName] = useState<string | null>(null);
  const workspaceName = workspaceNameProp ?? fetchedWorkspaceName;

  useEffect(() => {
    if (workspaceNameProp !== undefined) return;
    let cancelled = false;
    async function loadWorkspaceName() {
      try {
        const response = await fetch(`${getDashboardApiBaseUrl()}/api/v1/auth/me`, { credentials: "include", headers: { Accept: "application/json" } });
        if (!response.ok) return;
        const payload = (await response.json()) as ApiEnvelope<AuthContext>;
        if (!cancelled) setFetchedWorkspaceName(payload.data.workspace.name);
      } catch {
        // Graceful fallback to "Workspace" below; no authenticated context available.
      }
    }
    void loadWorkspaceName();
    return () => {
      cancelled = true;
    };
  }, [workspaceNameProp]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen(true);
      }
      if (event.key === "Escape") setCommandOpen(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const activeItem = useMemo(() => navigationItems.find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`)), [pathname]);
  const filteredItems = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return navigationItems;
    return navigationItems.filter((item) => `${item.label} ${item.description} ${item.group}`.toLowerCase().includes(needle));
  }, [query]);

  if (pathname === "/" || pathname === "/pricing") return <>{children}</>;

  return (
    <div className="shell yoranixShell">
      <motion.aside
        className="sidebar yoranixSidebar"
        aria-label="Primary navigation"
        initial={reduceMotion ? false : { opacity: 0, x: -16 }}
        animate={reduceMotion ? undefined : { opacity: 1, x: 0 }}
        transition={{ duration: 0.34, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="shellBrandGroup">
          <Link className="brandBlock yoranixBrand" href="/dashboard" aria-label="Conversa dashboard">
            <Image className="brandMark" src="/brand/conversa-icon.svg" alt="" aria-hidden="true" width={48} height={48} priority />
            <div>
              <p className="brandKicker">Conversa</p>
              <p className="brandName">AI Knowledge Platform</p>
            </div>
          </Link>
          <button className="shellIconButton mobileOnly" type="button" aria-label="Navigation menu">
            <PanelLeft size={18} aria-hidden="true" />
          </button>
        </div>

        <div className="workspaceCard" aria-label="Current workspace">
          <Building2 size={17} aria-hidden="true" />
          <div>
            <span>Workspace</span>
            <strong>{workspaceName || "Workspace"}</strong>
          </div>
          <CheckCircle2 size={16} aria-label="Workspace ready" />
        </div>

        <nav className="navList yoranixNavList" aria-label="Application sections">
          {navigationItems.map((item, index) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = navIcons[item.href] ?? LayoutDashboard;
            return (
              <motion.div
                key={item.href}
                initial={reduceMotion ? false : { opacity: 0, y: 8 }}
                animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
                transition={{ duration: 0.24, delay: 0.025 * index }}
              >
                <Link className={`navLink yoranixNavLink${active ? " navLinkActive" : ""}`} href={item.href} aria-current={active ? "page" : undefined}>
                  <span className="navGlyph" aria-hidden="true">
                    <Icon size={18} strokeWidth={2.1} />
                  </span>
                  <span className="navText">
                    <strong>{item.label}</strong>
                    <small>{item.group}</small>
                  </span>
                </Link>
              </motion.div>
            );
          })}
        </nav>

        <div className="sidebarNote shellSecurityCard" aria-label="Workspace security status">
          <ShieldCheck size={18} aria-hidden="true" />
          <div>
            <p>Enterprise guarded</p>
            <span>Tenant isolation, source-grounded answers, and role-based access remain active.</span>
          </div>
        </div>
      </motion.aside>

      <main className="mainArea yoranixMainArea">
        <motion.header
          className="topbar yoranixTopbar"
          initial={reduceMotion ? false : { opacity: 0, y: -10 }}
          animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="topbarIdentity">
            <nav className="shellBreadcrumbs" aria-label="Breadcrumb">
              <Link href="/dashboard">Dashboard</Link>
              <ChevronRight size={14} aria-hidden="true" />
              <span>{activeItem?.label ?? "Workspace"}</span>
            </nav>
            <div>
              <p className="workspaceLabel">Authenticated Workspace</p>
              <h1>{activeItem?.label ?? "Conversa Command Center"}</h1>
            </div>
          </div>

          <div className="topbarActions yoranixTopbarActions">
            <button className="commandSearch" type="button" onClick={() => setCommandOpen(true)} aria-label="Open command palette">
              <Search size={17} aria-hidden="true" />
              <span>Search or jump to...</span>
              <kbd>Ctrl K</kbd>
            </button>
            <Suspense fallback={<div className="assistantSwitcherSkeleton" aria-hidden="true" />}>
              <AssistantSwitcher />
            </Suspense>
            <button className="shellIconButton" type="button" aria-label="Notifications">
              <Bell size={18} aria-hidden="true" />
              <span className="notificationDot" aria-hidden="true" />
            </button>
            <div className="userMenuShell" aria-label="User menu">
              <span className="userAvatar" aria-hidden="true">C</span>
              <div>
                <strong>Conversa User</strong>
                <span>Secure session</span>
              </div>
              <LogoutButton />
            </div>
          </div>
        </motion.header>

        <section className="shellQuickActions" aria-label="Quick actions">
          {quickActions.map((action, index) => {
            const Icon = action.icon;
            return (
              <motion.div key={action.href} initial={reduceMotion ? false : { opacity: 0, y: 8 }} animate={reduceMotion ? undefined : { opacity: 1, y: 0 }} transition={{ duration: 0.22, delay: 0.04 * index }}>
                <Link className="quickActionLink" href={action.href}>
                  <Icon size={16} aria-hidden="true" />
                  {action.label}
                </Link>
              </motion.div>
            );
          })}
        </section>

        <motion.div
          className="pageMotion yoranixPageMotion"
          key={pathname}
          initial={reduceMotion ? false : { opacity: 0, y: 14, scale: 0.995 }}
          animate={reduceMotion ? undefined : { opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
        >
          {children}
        </motion.div>
      </main>

      <AnimatePresence>
        {commandOpen ? (
          <motion.div
            className="commandBackdrop"
            role="presentation"
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={reduceMotion ? undefined : { opacity: 1 }}
            exit={reduceMotion ? undefined : { opacity: 0 }}
            onMouseDown={() => setCommandOpen(false)}
          >
            <motion.div
              className="commandPalette"
              role="dialog"
              aria-modal="true"
              aria-labelledby="command-title"
              initial={reduceMotion ? false : { opacity: 0, y: 20, scale: 0.98 }}
              animate={reduceMotion ? undefined : { opacity: 1, y: 0, scale: 1 }}
              exit={reduceMotion ? undefined : { opacity: 0, y: 12, scale: 0.98 }}
              transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
              onMouseDown={(event) => event.stopPropagation()}
            >
              <div className="commandHeader">
                <Command size={18} aria-hidden="true" />
                <label className="srOnly" htmlFor="command-search">Search Conversa</label>
                <input id="command-search" autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search pages, actions, and workspace tools" />
                <button type="button" aria-label="Close command palette" onClick={() => setCommandOpen(false)}>
                  <X size={18} aria-hidden="true" />
                </button>
              </div>
              <div className="commandSection">
                <p>Navigation</p>
                <div role="listbox" aria-label="Navigation results">
                  {filteredItems.map((item) => {
                    const Icon = navIcons[item.href] ?? LayoutDashboard;
                    return (
                      <Link className="commandItem" href={item.href} key={item.href} onClick={() => setCommandOpen(false)}>
                        <span><Icon size={17} aria-hidden="true" /></span>
                        <div>
                          <strong>{item.label}</strong>
                          <small>{item.description}</small>
                        </div>
                        <ChevronRight size={15} aria-hidden="true" />
                      </Link>
                    );
                  })}
                </div>
              </div>
              <div className="commandFooter">
                <Sparkles size={15} aria-hidden="true" />
                <span>Actions preserve your current assistant context where supported.</span>
              </div>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
