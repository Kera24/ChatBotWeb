import { AlertOctagon, CheckCircle2, Clock3, Inbox, Loader2, Rocket, Wrench, type LucideIcon } from "lucide-react";

import type { OverviewData } from "../../lib/api/overview";
import type { WidgetDetail } from "../../lib/api/widgets";
import { assistantLifecycle } from "../assistants/assistant-management";

export type PlatformHealthKey =
  | "no-assistants"
  | "document-failures"
  | "review-backlog"
  | "unpublished-assistants"
  | "setup-incomplete"
  | "knowledge-processing"
  | "attention-required"
  | "healthy";

export type PlatformHealthTone = "success" | "info" | "warning" | "danger" | "neutral";

export type PlatformHealth = {
  key: PlatformHealthKey;
  tone: PlatformHealthTone;
  label: string;
  detail: string;
};

const HEALTH_META: Record<PlatformHealthKey, { label: string; icon: LucideIcon; tone: PlatformHealthTone }> = {
  "no-assistants": { label: "No assistants", icon: Inbox, tone: "neutral" },
  "document-failures": { label: "Document failures", icon: AlertOctagon, tone: "danger" },
  "review-backlog": { label: "Review backlog", icon: Clock3, tone: "warning" },
  "unpublished-assistants": { label: "Unpublished assistants", icon: Rocket, tone: "warning" },
  "setup-incomplete": { label: "Setup incomplete", icon: Wrench, tone: "warning" },
  "knowledge-processing": { label: "Knowledge processing", icon: Loader2, tone: "info" },
  "attention-required": { label: "Attention required", icon: AlertOctagon, tone: "warning" },
  healthy: { label: "Healthy", icon: CheckCircle2, tone: "success" },
};

export function derivePlatformHealth(data: OverviewData, assistants: WidgetDetail[]): PlatformHealth {
  if (assistants.length === 0) {
    return { key: "no-assistants", tone: HEALTH_META["no-assistants"].tone, label: HEALTH_META["no-assistants"].label, detail: "Create your first assistant to start building a knowledge base and testing answers." };
  }

  const failedDocuments = data.documents.filter((document) => document.status === "failed").length;
  const processingDocuments = data.documents.filter((document) => ["uploaded", "processing"].includes(document.status)).length;
  const publishedAssistants = assistants.filter((assistant) => assistantLifecycle(assistant) === "Published").length;
  const assistantsWithoutKnowledge = assistants.filter((assistant) => (assistant.draft?.configuration.knowledge_scope_json.length ?? 0) === 0).length;

  const issues: PlatformHealthKey[] = [];
  if (failedDocuments > 0) issues.push("document-failures");
  if (data.reviewTotal > 0) issues.push("review-backlog");
  if (publishedAssistants === 0) issues.push("unpublished-assistants");
  if (assistantsWithoutKnowledge > 0) issues.push("setup-incomplete");

  if (issues.length === 0) {
    if (processingDocuments > 0) {
      return { key: "knowledge-processing", tone: HEALTH_META["knowledge-processing"].tone, label: HEALTH_META["knowledge-processing"].label, detail: `${processingDocuments} document${processingDocuments === 1 ? " is" : "s are"} still processing. Retrieval quality will improve once processing completes.` };
    }
    return { key: "healthy", tone: HEALTH_META.healthy.tone, label: HEALTH_META.healthy.label, detail: "No document failures, no open knowledge gaps, and at least one assistant is published with knowledge assigned." };
  }

  if (issues.length === 1) {
    const key = issues[0];
    return { key, tone: HEALTH_META[key].tone, label: HEALTH_META[key].label, detail: detailFor(key, { failedDocuments, reviewTotal: data.reviewTotal, publishedAssistants, assistantsWithoutKnowledge, totalAssistants: assistants.length }) };
  }

  const tone: PlatformHealthTone = failedDocuments > 0 ? "danger" : "warning";
  return {
    key: "attention-required",
    tone,
    label: HEALTH_META["attention-required"].label,
    detail: `${issues.length} operational signals need review: ${issues.map((issue) => HEALTH_META[issue].label.toLowerCase()).join(", ")}.`,
  };
}

function detailFor(key: PlatformHealthKey, counts: { failedDocuments: number; reviewTotal: number; publishedAssistants: number; assistantsWithoutKnowledge: number; totalAssistants: number }) {
  switch (key) {
    case "document-failures":
      return `${counts.failedDocuments} document${counts.failedDocuments === 1 ? "" : "s"} failed processing and need${counts.failedDocuments === 1 ? "s" : ""} investigation.`;
    case "review-backlog":
      return `${counts.reviewTotal} unanswered item${counts.reviewTotal === 1 ? " is" : "s are"} open for review.`;
    case "unpublished-assistants":
      return `None of ${counts.totalAssistants} assistant${counts.totalAssistants === 1 ? "" : "s"} is published yet.`;
    case "setup-incomplete":
      return `${counts.assistantsWithoutKnowledge} assistant${counts.assistantsWithoutKnowledge === 1 ? " has" : "s have"} no knowledge assigned.`;
    default:
      return "";
  }
}

export function PlatformHealthBadge({ health }: { health: PlatformHealth }) {
  const Icon = HEALTH_META[health.key].icon;
  return (
    <span className={`platformHealthBadge tone-${health.tone}`} role="status" aria-label={`Platform health: ${health.label}. ${health.detail}`}>
      <Icon size={15} aria-hidden="true" className={health.key === "knowledge-processing" ? "spinIcon" : undefined} />
      {health.label}
    </span>
  );
}

export function PlatformHealthPanel({ health }: { health: PlatformHealth }) {
  const Icon = HEALTH_META[health.key].icon;
  return (
    <section className="platformHealthPanel" aria-labelledby="health-title">
      <div className="overviewPanelHeader">
        <div>
          <p className="sectionKicker">Platform health</p>
          <h3 id="health-title">Operational status</h3>
        </div>
      </div>
      <div className={`platformHealthSummary tone-${health.tone}`}>
        <span className="platformHealthIcon" aria-hidden="true"><Icon size={22} className={health.key === "knowledge-processing" ? "spinIcon" : undefined} /></span>
        <div>
          <strong>{health.label}</strong>
          <p>{health.detail}</p>
        </div>
      </div>
    </section>
  );
}
