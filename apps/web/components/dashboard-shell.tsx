"use client";

import { motion } from "framer-motion";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { navigationItems } from "../lib/navigation";
import { LogoutButton } from "./logout-button";

type DashboardShellProps = {
  children: ReactNode;
};

export function DashboardShell({ children }: DashboardShellProps) {
  const pathname = usePathname();

  if (pathname === "/") return <>{children}</>;

  return (
    <div className="shell">
      <motion.aside
        className="sidebar"
        aria-label="Primary navigation"
        initial={{ opacity: 0, x: -16 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.34, ease: [0.22, 1, 0.36, 1] }}
      >
        <Link className="brandBlock" href="/" aria-label="Yoranix overview">
          <Image className="brandMark" src="/brand/yoranix-logo.png" alt="" aria-hidden="true" width={52} height={52} priority />
          <div>
            <p className="brandKicker">Yoranix</p>
            <p className="brandName">Knowledge Platform</p>
          </div>
        </Link>

        <nav className="navList">
          {navigationItems.map((item, index) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <motion.div
                key={item.href}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.26, delay: 0.03 * index }}
              >
                <Link className={`navLink${active ? " navLinkActive" : ""}`} href={item.href} aria-current={active ? "page" : undefined}>
                  <span className="navGlyph" aria-hidden="true">
                    {item.glyph}
                  </span>
                  <span>{item.label}</span>
                </Link>
              </motion.div>
            );
          })}
        </nav>

        <div className="sidebarNote" aria-label="Workspace status">
          <span className="statusDot" aria-hidden="true" />
          <div>
            <p>Workspace ready</p>
            <span>Knowledge, testing, deployment, and analytics are managed from one secure operating surface.</span>
          </div>
        </div>
      </motion.aside>

      <main className="mainArea">
        <motion.div
          className="topbar"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
        >
          <div>
            <p className="workspaceLabel">AI Knowledge Platform</p>
            <h1>Yoranix Command Center</h1>
          </div>
          <div className="topbarActions">
            <div className="trustBadge" aria-label="Trust guardrails">Source-grounded by design</div>
            <LogoutButton />
          </div>
        </motion.div>

        <motion.div
          className="pageMotion"
          key={pathname}
          initial={{ opacity: 0, y: 14, scale: 0.995 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
        >
          {children}
        </motion.div>
      </main>
    </div>
  );
}

