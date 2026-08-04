import { describe, expect, it, vi } from "vitest";

import { render, screen, waitFor } from "../test/test-utils";
import { DashboardShell } from "./dashboard-shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

describe("DashboardShell", () => {
  it("fetches the authenticated workspace name when no workspace prop is supplied", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/auth/me")) {
          return { ok: true, json: async () => ({ data: { workspace: { name: "Fetched Workspace" } } }) };
        }
        return { ok: true, json: async () => ({ data: [] }) };
      }),
    );

    render(
      <DashboardShell>
        <div>content</div>
      </DashboardShell>,
    );

    await waitFor(() => {
      expect(screen.getByLabelText("Current workspace").textContent).toContain("Fetched Workspace");
    });
  });

  it("falls back to Workspace when the auth request fails and no prop is supplied", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    render(
      <DashboardShell>
        <div>content</div>
      </DashboardShell>,
    );

    await waitFor(() => {
      expect(screen.getByLabelText("Current workspace").textContent).toContain("Workspace");
    });
  });

  it("shows the authenticated workspace name in the workspace card", () => {
    render(
      <DashboardShell workspaceName="Admissions Workspace">
        <div>content</div>
      </DashboardShell>,
    );
    const workspaceCard = screen.getByLabelText("Current workspace");
    expect(workspaceCard.textContent).toContain("Admissions Workspace");
    expect(workspaceCard.textContent).not.toContain("Command Center");
  });

  it("falls back to a generic Workspace label when no workspace context is available", () => {
    render(
      <DashboardShell workspaceName={null}>
        <div>content</div>
      </DashboardShell>,
    );
    const workspaceCard = screen.getByLabelText("Current workspace");
    expect(workspaceCard.textContent).toContain("Workspace");
    expect(workspaceCard.textContent).not.toContain("Command Center");
  });
});
