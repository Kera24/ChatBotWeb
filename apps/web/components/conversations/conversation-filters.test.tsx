import { describe, expect, it } from "vitest";

import { render, screen, userEvent } from "../../test/test-utils";
import { ConversationFilters } from "./conversation-filters";

describe("ConversationFilters", () => {
  it("renders labelled filter controls with expected state", async () => {
    const user = userEvent.setup();
    render(<ConversationFilters status="active" channel="dashboard_test" limit={20} assistantId="assistant-1" />);

    const status = screen.getByLabelText("Status") as HTMLSelectElement;
    const channel = screen.getByLabelText("Channel") as HTMLSelectElement;
    const pageSize = screen.getByLabelText("Page size") as HTMLSelectElement;

    expect(status.value).toBe("active");
    expect(channel.value).toBe("dashboard_test");
    expect(pageSize.value).toBe("20");

    await user.selectOptions(status, "completed");
    await user.selectOptions(channel, "api");
    await user.selectOptions(pageSize, "50");

    expect(status.value).toBe("completed");
    expect(channel.value).toBe("api");
    expect(pageSize.value).toBe("50");
    expect(screen.getByRole("button", { name: "Apply conversation filters" })).toBeTruthy();
  });

  it("renders labelled date range controls", () => {
    render(<ConversationFilters limit={20} assistantId="assistant-1" startedAfter="2026-01-01" startedBefore="2026-02-01" />);

    expect((screen.getByLabelText("Started after") as HTMLInputElement).value).toBe("2026-01-01");
    expect((screen.getByLabelText("Started before") as HTMLInputElement).value).toBe("2026-02-01");
  });

  it("preserves assistant context in the hidden field and clear-all link", () => {
    render(<ConversationFilters limit={20} assistantId="assistant-1" />);

    expect(screen.getByDisplayValue("assistant-1")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Clear all conversation filters" }).getAttribute("href")).toBe("/conversations?assistant=assistant-1");
  });

  it("shows active filter chips with links that remove one filter at a time", () => {
    render(<ConversationFilters status="active" channel="widget" limit={20} assistantId="assistant-1" startedAfter="2026-01-01" />);

    const list = screen.getByLabelText("Active conversation filters");
    expect(list).toBeTruthy();
    expect(screen.getByText("Status: Active")).toBeTruthy();
    expect(screen.getByText("Channel: Widget")).toBeTruthy();
    expect(screen.getByText("Started after 2026-01-01")).toBeTruthy();

    const removeStatus = screen.getByRole("link", { name: "Remove filter: Status: Active" });
    const href = removeStatus.getAttribute("href") ?? "";
    expect(href).toContain("assistant=assistant-1");
    expect(href).toContain("channel=widget");
    expect(href).not.toContain("status=");
  });

  it("shows a note when no filters are active", () => {
    render(<ConversationFilters limit={20} assistantId="assistant-1" />);
    expect(screen.getByText(/No filters applied/)).toBeTruthy();
    expect(screen.queryByLabelText("Active conversation filters")).toBeNull();
  });
});
