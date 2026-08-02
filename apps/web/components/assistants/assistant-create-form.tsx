"use client";

import { motion, useReducedMotion } from "framer-motion";
import { ArrowLeft, Bot, Globe2, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";

import { isDashboardApiError } from "../../lib/api/errors";
import { createWidget, type WidgetConfigurationPayload } from "../../lib/api/widgets";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

const DEFAULT_CONFIGURATION: Partial<WidgetConfigurationPayload> = {
  welcome_message: "Ask a question and receive a source-grounded answer from approved company knowledge.",
  launcher_label: "Ask AI",
  primary_colour: "#1B2A4A",
  secondary_colour: "#E8ECF4",
  logo_path: null,
  avatar_path: null,
  position: "bottom_right",
  theme_mode: "system",
  language: "en",
  suggested_questions_json: ["What can you help me with?", "Where can I find company information?"],
  fallback_contact_text: "Contact the team for help with this question.",
  privacy_notice_text: "Answers are generated from approved Yoranix workspace knowledge.",
  privacy_notice_url: null,
  terms_url: null,
  show_citations: true,
  allow_conversation_history: true,
  max_initial_suggestions: 2,
  knowledge_scope_json: [],
};

export function AssistantCreateForm({ session }: { session: DevelopmentDashboardSession }) {
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  const [name, setName] = useState("Customer Support Assistant");
  const [description, setDescription] = useState("Answers customer questions using approved workspace knowledge.");
  const [language, setLanguage] = useState("en");
  const [environment, setEnvironment] = useState("production");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = useMemo(() => name.trim().length >= 3 && description.trim().length >= 10 && !submitting, [description, name, submitting]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const displayName = name.trim();
      const response = await createWidget(session, {
        display_name: displayName,
        environment,
        initial_configuration: {
          ...DEFAULT_CONFIGURATION,
          bot_name: displayName,
          welcome_message: description.trim(),
          language,
        },
      });
      router.push(`/assistants/${response.data.id}`);
      router.refresh();
    } catch (caught) {
      setError(messageForCreateError(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="assistantCreatePage" aria-labelledby="create-assistant-title">
      <Link className="assistantBackLink" href="/dashboard"><ArrowLeft size={16} aria-hidden="true" />Back to assistants</Link>
      <motion.div
        className="assistantCreateShell"
        initial={reduceMotion ? false : { opacity: 0, y: 16 }}
        animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="assistantCreateIntro">
          <div className="assistantCreateIcon" aria-hidden="true"><Bot size={28} /></div>
          <p className="eyebrow">New assistant</p>
          <h2 id="create-assistant-title">Create an AI Assistant</h2>
          <p>Define the assistant shell now. Knowledge, testing, publishing, and analytics are managed from the assistant detail page.</p>
          <div className="assistantCreateSignals" aria-label="Assistant defaults">
            <span><Sparkles size={15} aria-hidden="true" />Source-grounded</span>
            <span><Globe2 size={15} aria-hidden="true" />Widget-ready</span>
          </div>
        </div>

        <form className="assistantCreateForm" onSubmit={onSubmit} aria-describedby={error ? "assistant-create-error" : undefined}>
          <div className="formField">
            <label htmlFor="assistant-name">Assistant name</label>
            <input id="assistant-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={160} required />
            <p>Use a clear internal name, such as Admissions Assistant or Support Assistant.</p>
          </div>
          <div className="formField">
            <label htmlFor="assistant-description">Assistant description</label>
            <textarea id="assistant-description" value={description} onChange={(event) => setDescription(event.target.value)} rows={4} required />
            <p>This seeds the first welcome message and sets the assistant&apos;s operating intent.</p>
          </div>
          <div className="assistantCreateGrid">
            <div className="formField">
              <label htmlFor="assistant-language">Default language</label>
              <select id="assistant-language" value={language} onChange={(event) => setLanguage(event.target.value)}>
                <option value="en">English</option>
                <option value="en-AU">English (Australia)</option>
                <option value="en-US">English (United States)</option>
              </select>
            </div>
            <div className="formField">
              <label htmlFor="assistant-environment">Publishing environment</label>
              <select id="assistant-environment" value={environment} onChange={(event) => setEnvironment(event.target.value)}>
                <option value="production">Production</option>
                <option value="development">Development</option>
                <option value="test">Test</option>
              </select>
            </div>
          </div>
          {error ? <p className="errorText" id="assistant-create-error" role="alert">{error}</p> : null}
          <div className="formActions">
            <button className="actionButton" type="submit" disabled={!canSubmit}>{submitting ? "Creating" : "Create Assistant"}</button>
          </div>
        </form>
      </motion.div>
    </section>
  );
}

function messageForCreateError(error: unknown) {
  if (isDashboardApiError(error)) {
    if (error.kind === "validation") return "Check the assistant details and try again.";
    if (error.kind === "forbidden") return "You do not have permission to create assistants in this workspace.";
    if (error.kind === "conflict") return "An assistant with this configuration already exists.";
  }
  return "Assistant could not be created.";
}
