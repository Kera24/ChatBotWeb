import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { AiConfigurationCard } from "./ai-configuration-card";

const operational = {
  environment: "staging",
  service_name: "chatbotweb-api",
  version: "abc123",
  phase: "controlled-pilot",
  public_widgets_enabled: true,
  public_widget_messages_enabled: true,
  public_widget_pilot_enforcement_enabled: true,
  retrieval_max_context_chunks: 10,
  retrieval_max_context_chars: 12000,
  chunk_size_words: 300,
  chunk_overlap_words: 50,
  embedding_provider: "azure-openai",
  embedding_model: "text-embedding-3-small",
  embedding_dimension: 1536,
  default_ai_provider_key: "azure-openai",
  default_ai_model_key: "gpt-4.1-mini",
  ai_request_timeout_seconds: 30,
};

describe("AiConfigurationCard", () => {
  it("renders provider, retrieval, and embedding fields as read-only", () => {
    render(<AiConfigurationCard operational={operational} />);

    expect(screen.getAllByText("azure-openai").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("gpt-4.1-mini")).toBeTruthy();
    expect(screen.getByText("text-embedding-3-small")).toBeTruthy();
    expect(screen.getByText("1536")).toBeTruthy();
    expect(screen.getByText("10")).toBeTruthy();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("explains that these settings are managed by Conversa administrators", () => {
    render(<AiConfigurationCard operational={operational} />);
    expect(screen.getByText(/managed by Conversa administrators/i)).toBeTruthy();
  });
});
