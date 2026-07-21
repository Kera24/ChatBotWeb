import Link from "next/link";
import type { ReactNode } from "react";

import { navigationItems } from "../lib/navigation";

type DashboardShellProps = {
  children: ReactNode;
};

export function DashboardShell({ children }: DashboardShellProps) {
  return (
    <div className="shell">
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="brandBlock">
          <div className="brandMark" aria-hidden="true">
            YA
          </div>
          <div>
            <p className="brandKicker">Yoranix</p>
            <p className="brandName">AI Platform</p>
          </div>
        </div>

        <nav className="navList">
          {navigationItems.map((item) => (
            <Link className="navLink" href={item.href} key={item.href}>
              <span className="navGlyph" aria-hidden="true">
                {item.glyph}
              </span>
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>

        <div className="sidebarNote" aria-label="Foundation status">
          <span className="statusDot" aria-hidden="true" />
          <div>
            <p>Foundation mode</p>
            <span>Conversation history uses temporary development tenant context.</span>
          </div>
        </div>
      </aside>

      <main className="mainArea">
        <div className="topbar">
          <div>
            <p className="workspaceLabel">Client workspace</p>
            <h1>Admissions Assistant</h1>
          </div>
          <div className="trustBadge" aria-label="Trust guardrails">
            Source-grounded by design
          </div>
        </div>

        {children}
      </main>
    </div>
  );
}
