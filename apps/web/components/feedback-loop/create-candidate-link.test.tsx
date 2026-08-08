import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { CreateCandidateLink } from "./create-candidate-link";

describe("CreateCandidateLink", () => {
  it("builds a link carrying source type, id, and assistant", () => {
    render(<CreateCandidateLink sourceType="trace" sourceId="trace-1" assistantId="assistant-1" />);
    const link = screen.getByRole("link", { name: /Create evaluation candidate/ });
    expect(link.getAttribute("href")).toBe("/feedback-loop/candidates/new?source_type=trace&source_id=trace-1&assistant=assistant-1");
  });

  it("carries prefilled question/response text instead of a source id for eval results", () => {
    render(<CreateCandidateLink sourceType="eval_result" assistantId="assistant-1" prefillQuestion="What is the refund window?" prefillResponse="I don't know." />);
    const link = screen.getByRole("link", { name: /Create evaluation candidate/ });
    const url = new URL(link.getAttribute("href") ?? "", "http://localhost");
    expect(url.searchParams.get("source_type")).toBe("eval_result");
    expect(url.searchParams.get("source_id")).toBeNull();
    expect(url.searchParams.get("prefill_question")).toBe("What is the refund window?");
    expect(url.searchParams.get("prefill_response")).toBe("I don't know.");
  });
});
