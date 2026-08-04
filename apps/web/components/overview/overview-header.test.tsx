import { describe, expect, it } from "vitest";

import { render, screen, within } from "../../test/test-utils";
import { OverviewHeader } from "./overview-header";
import { derivePlatformHealth } from "./platform-health";

const health = derivePlatformHealth({ documents: [], conversations: [], widgets: [], reviewItems: [], reviewTotal: 0 }, []);

describe("OverviewHeader", () => {
  it("shows workspace identity, organisation context, environment, and role", () => {
    render(<OverviewHeader workspaceName="Admissions Workspace" organisationName="Yoranix College" environment="staging" role="client_admin" health={health} latestKnowledgeUpdateLabel="2 hours ago" primaryAssistantId="assistant-1" />);

    expect(screen.getByRole("heading", { name: "Admissions Workspace" })).toBeTruthy();
    expect(screen.getByText(/Yoranix College/)).toBeTruthy();
    expect(screen.getByText("staging environment")).toBeTruthy();
    expect(screen.getByText("client admin")).toBeTruthy();
    expect(screen.getByText("Latest knowledge activity 2 hours ago")).toBeTruthy();
  });

  it("always shows assistant-agnostic quick actions", () => {
    render(<OverviewHeader workspaceName="Admissions Workspace" organisationName="Yoranix College" environment="staging" role="client_admin" health={health} latestKnowledgeUpdateLabel="none yet" primaryAssistantId={null} />);

    const nav = screen.getByRole("navigation", { name: "Executive quick actions" });
    expect(within(nav).getByRole("link", { name: /Create assistant/ }).getAttribute("href")).toBe("/assistants/new");
    expect(within(nav).getByRole("link", { name: /Review knowledge gaps/ }).getAttribute("href")).toBe("/review/unanswered");
    expect(within(nav).getByRole("link", { name: /Manage assistants/ }).getAttribute("href")).toBe("/dashboard");
  });

  it("omits assistant-specific quick actions when no assistant can be safely resolved", () => {
    render(<OverviewHeader workspaceName="Admissions Workspace" organisationName="Yoranix College" environment="staging" role="client_admin" health={health} latestKnowledgeUpdateLabel="none yet" primaryAssistantId={null} />);
    expect(screen.queryByRole("link", { name: /Upload knowledge/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Open Playground/ })).not.toBeInTheDocument();
  });

  it("shows assistant-specific quick actions with preserved assistant context when resolvable", () => {
    render(<OverviewHeader workspaceName="Admissions Workspace" organisationName="Yoranix College" environment="staging" role="client_admin" health={health} latestKnowledgeUpdateLabel="none yet" primaryAssistantId="assistant-1" />);
    expect(screen.getByRole("link", { name: /Upload knowledge/ }).getAttribute("href")).toBe("/knowledge?assistant=assistant-1");
    expect(screen.getByRole("link", { name: /Open Playground/ }).getAttribute("href")).toBe("/chatbot?assistant=assistant-1");
  });
});
