import type { OverviewData } from "../../lib/api/overview";
import type { WidgetDetail } from "../../lib/api/widgets";
import { assistantLifecycle } from "../assistants/assistant-management";

export type ExecutiveMetric = {
  key: string;
  label: string;
  value: string;
  detail: string;
};

export function buildExecutiveMetrics(data: OverviewData, assistants: WidgetDetail[], recentWindowLimit: number): ExecutiveMetric[] {
  const readyDocuments = data.documents.filter((document) => document.status === "ready").length;
  const failedDocuments = data.documents.filter((document) => document.status === "failed").length;
  const processingDocuments = data.documents.filter((document) => ["uploaded", "processing"].includes(document.status)).length;
  const publishedAssistants = assistants.filter((assistant) => assistantLifecycle(assistant) === "Published").length;
  const activeWidgets = data.widgets.filter((widget) => widget.operational_status === "enabled" && widget.publication_status === "published").length;

  return [
    { key: "assistants", label: "Total assistants", value: String(assistants.length), detail: "Assistants configured in this workspace." },
    { key: "published-assistants", label: "Published assistants", value: `${publishedAssistants}/${assistants.length}`, detail: "Assistants live and available to customers." },
    { key: "documents", label: "Total documents", value: String(data.documents.length), detail: "Documents across the knowledge lifecycle." },
    { key: "ready-documents", label: "Ready documents", value: String(readyDocuments), detail: "Documents available for retrieval." },
    { key: "processing-documents", label: "Processing", value: String(processingDocuments), detail: "Uploaded or processing documents." },
    { key: "failed-documents", label: "Failed documents", value: String(failedDocuments), detail: "Documents needing attention." },
    { key: "conversations", label: "Recent conversations", value: String(data.conversations.length), detail: `Returned from a recent window of up to ${recentWindowLimit} per assistant.` },
    { key: "knowledge-gaps", label: "Open knowledge gaps", value: String(data.reviewTotal), detail: "Unanswered review items still open." },
    { key: "active-widgets", label: "Active widgets", value: `${activeWidgets}/${data.widgets.length}`, detail: "Published and operational widgets." },
  ];
}

export function OverviewMetrics({ metrics }: { metrics: ExecutiveMetric[] }) {
  return (
    <section className="overviewMetricGrid" aria-label="Executive metrics">
      {metrics.map((metric) => (
        <article className="overviewMetricCard" key={metric.key}>
          <span>{metric.label}</span>
          <strong>{metric.value}</strong>
          <p>{metric.detail}</p>
        </article>
      ))}
    </section>
  );
}
