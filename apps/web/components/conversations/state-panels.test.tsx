import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { AccessDeniedState, EmptyState, ErrorState, LoadingState, MissingTenantConfiguration } from "./state-panels";

describe("conversation state panels", () => {
  it("renders loading, empty, and access-denied states with semantic headings", () => {
    const { rerender } = render(<LoadingState />);
    expect(screen.getByRole("heading", { name: "Loading conversations" })).toBeTruthy();

    rerender(<EmptyState />);
    expect(screen.getByRole("heading", { name: "No conversations have been recorded" })).toBeTruthy();

    rerender(<AccessDeniedState />);
    expect(screen.getByRole("heading", { name: "You cannot view this workspace" })).toBeTruthy();
  });

  it("renders missing and invalid workspace configuration without developer details", () => {
    render(
      <MissingTenantConfiguration
        missing={["NEXT_PUBLIC_DEVELOPMENT_ORGANISATION_ID"]}
        invalid={["NEXT_PUBLIC_DEVELOPMENT_ROLE"]}
      />,
    );

    expect(screen.getByRole("heading", { name: "Workspace access is not ready" })).toBeTruthy();
    expect(screen.getByText("2 configuration items need attention.")).toBeTruthy();
    expect(screen.queryByText("NEXT_PUBLIC_DEVELOPMENT_ORGANISATION_ID")).toBeNull();
    expect(screen.queryByText("NEXT_PUBLIC_DEVELOPMENT_ROLE")).toBeNull();
    expect(screen.queryByText("owner@example.test")).toBeNull();
  });

  it("renders a retryable generic error state", () => {
    render(<ErrorState message="The API could not be reached." retryHref="/conversations" />);

    expect(screen.getByRole("heading", { name: "Something blocked this view" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Retry" }).getAttribute("href")).toBe("/conversations");
  });
});
