import { describe, expect, it } from "vitest";

import { render, screen, userEvent } from "../../test/test-utils";
import { ConversationFilters } from "./conversation-filters";

describe("ConversationFilters", () => {
  it("renders labelled filter controls with expected state", async () => {
    const user = userEvent.setup();
    render(<ConversationFilters status="active" channel="dashboard_test" limit={20} />);

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
});
