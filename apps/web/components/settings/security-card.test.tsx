import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { SecurityCard } from "./security-card";

const operational = {
  environment: "staging",
  service_name: "chatbotweb-api",
  version: "abc123",
  phase: "controlled-pilot",
  public_widgets_enabled: true,
  public_widget_messages_enabled: false,
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

const capabilities = {
  editable_fields: ["workspace.name", "workspace.default_language"],
  read_only_fields: ["organisation.name", "workspace.slug"],
  environment_controlled_fields: ["embedding_model", "retrieval_max_context_chunks"],
  secret_managed_fields: ["database_url", "redis_url", "application_insights_connection_string"],
  unsupported_fields: ["provider_secret_editing", "notification_preferences"],
};

describe("SecurityCard", () => {
  it("renders the current role and public-widget rollout flags", () => {
    render(<SecurityCard operational={operational} capabilities={capabilities} currentRole="client_admin" />);

    expect(screen.getByText("client admin")).toBeTruthy();
    expect(screen.getAllByText("Enabled").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Disabled")).toBeTruthy();
  });

  it("shows secret-managed fields as name-only chips, never as values", () => {
    render(<SecurityCard operational={operational} capabilities={capabilities} currentRole="client_admin" />);

    expect(screen.getByText("database url")).toBeTruthy();
    expect(screen.getByText(/stored securely outside the dashboard/i)).toBeTruthy();
    expect(screen.queryByText(/postgres:\/\/|redis:\/\//i)).not.toBeInTheDocument();
  });

  it("lists fields that are not available in this dashboard", () => {
    render(<SecurityCard operational={operational} capabilities={capabilities} currentRole="client_admin" />);
    expect(screen.getByText("provider secret editing")).toBeTruthy();
  });

  it("omits the secret block entirely when there are no secret-managed fields", () => {
    render(<SecurityCard operational={operational} capabilities={{ ...capabilities, secret_managed_fields: [] }} currentRole="client_admin" />);
    expect(screen.queryByText(/Environment-managed secrets/)).not.toBeInTheDocument();
  });
});
