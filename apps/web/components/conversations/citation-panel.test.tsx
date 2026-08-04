import { describe, expect, it, vi } from "vitest";

import { render, screen, userEvent } from "../../test/test-utils";
import type { ConversationCitation } from "../../lib/api/types";
import { CitationChipList, CitationDrawer } from "./citation-panel";

const citation: ConversationCitation = {
  id: "citation-1",
  assistant_id: "assistant-1",
  citation_index: 1,
  chunk_id: "chunk-1",
  document_id: "document-1",
  document_version_id: "version-1",
  similarity_score: 0.8765,
  source_title: "Onboarding Guide",
  source_type: "pdf",
  page_number: 4,
  section_title: "Activation",
  quoted_text: "Invite the first workspace members before launch.",
  created_at: "2026-07-12T02:00:00.000Z",
};

describe("CitationChipList", () => {
  it("renders a compact, keyboard-accessible chip per citation", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<CitationChipList citations={[citation]} onSelectCitation={onSelect} />);

    const chip = screen.getByRole("button", { name: "Open citation 1: Onboarding Guide" });
    chip.focus();
    expect(chip).toHaveFocus();
    await user.keyboard("{Enter}");

    expect(onSelect).toHaveBeenCalledWith(citation);
  });

  it("renders an explanatory empty state when there are no citations", () => {
    render(<CitationChipList citations={[]} onSelectCitation={vi.fn()} />);
    expect(screen.getByText(/No citations were returned/)).toBeTruthy();
  });
});

describe("CitationDrawer", () => {
  it("renders nothing when no citation is selected", () => {
    const { container } = render(<CitationDrawer citation={null} onClose={vi.fn()} />);
    expect(container.textContent).toBe("");
  });

  it("renders full source detail and calls onClose", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<CitationDrawer citation={citation} onClose={onClose} />);

    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByText("Invite the first workspace members before launch.")).toBeTruthy();
    expect(screen.getByText("Activation")).toBeTruthy();
    expect(screen.getByText("0.876")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Close citation details" }));
    expect(onClose).toHaveBeenCalled();
  });
});
