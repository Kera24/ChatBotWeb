"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { createWidget, type WidgetConfigurationPayload } from "../../lib/api/widgets";
import { isDashboardApiError } from "../../lib/api/errors";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

const DEFAULT_INITIAL_CONFIGURATION: Partial<WidgetConfigurationPayload> = {
  bot_name: "Website Assistant",
  welcome_message: "Ask us a question and we will answer from approved knowledge.",
  launcher_label: "Ask us",
  primary_colour: "#111827",
  position: "bottom_right",
  theme_mode: "system",
  language: "en",
  suggested_questions_json: ["How can you help?"],
  max_initial_suggestions: 1,
  knowledge_scope_json: [],
};

export function WidgetCreateForm({ session }: { session: DevelopmentDashboardSession }) {
  const router = useRouter();
  const [displayName, setDisplayName] = useState("Website Assistant");
  const [environment, setEnvironment] = useState("development");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = useMemo(() => displayName.trim().length > 0 && !submitting, [displayName, submitting]);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const response = await createWidget(session, {
        display_name: displayName.trim(),
        environment,
        initial_configuration: {
          ...DEFAULT_INITIAL_CONFIGURATION,
          bot_name: displayName.trim(),
        },
      });
      router.push(`/widgets/${response.data.id}`);
      router.refresh();
    } catch (caught) {
      setError(messageForFormError(caught, "Widget could not be created."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="widgetForm" onSubmit={onSubmit} aria-describedby={error ? "create-widget-error" : undefined}>
      <div className="formField">
        <label htmlFor="display-name">Internal widget name</label>
        <input
          id="display-name"
          name="display_name"
          maxLength={160}
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
          required
        />
        <p>This name is shown to administrators and seeds the first draft bot name.</p>
      </div>
      <div className="formField">
        <label htmlFor="environment">Environment</label>
        <select id="environment" value={environment} onChange={(event) => setEnvironment(event.target.value)}>
          <option value="development">Development</option>
          <option value="test">Test</option>
          <option value="production">Production</option>
        </select>
        <p>Production widgets require HTTPS origins before publishing.</p>
      </div>
      {error ? <p className="errorText" id="create-widget-error">{error}</p> : null}
      <div className="formActions">
        <button className="actionButton" type="submit" disabled={!canSubmit}>
          {submitting ? "Creating" : "Create widget"}
        </button>
      </div>
    </form>
  );
}

function messageForFormError(error: unknown, fallback: string) {
  if (isDashboardApiError(error)) {
    if (error.kind === "validation") return "Check the widget name and initial configuration.";
    if (error.kind === "conflict") return "The widget conflicts with existing workspace data.";
    if (error.kind === "forbidden") return "This user cannot create widgets in the selected workspace.";
  }
  return fallback;
}
