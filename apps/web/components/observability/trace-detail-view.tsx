import Link from "next/link";

import { CreateCandidateLink } from "../feedback-loop/create-candidate-link";
import type { AITraceDetail } from "../../lib/api/observability";

type TraceDetailViewProps = {
  trace: AITraceDetail;
  assistantId?: string;
  includeContent: boolean;
};

export function TraceDetailView({ trace, assistantId, includeContent }: TraceDetailViewProps) {
  const { summary, stages, retrieval, model_calls: modelCalls, guardrails } = trace;
  const backHref = assistantId ? `/observability?assistant=${assistantId}` : "/observability";
  const contentHref = `/observability/traces/${summary.trace_id}?${new URLSearchParams({
    ...(assistantId ? { assistant: assistantId } : {}),
    include_content: includeContent ? "false" : "true",
  }).toString()}`;

  return (
    <section className="observabilityPage observabilityTraceDetail" aria-labelledby="trace-detail-title">
      <header className="observabilityHeader">
        <div>
          <p className="sectionKicker">AI Trace</p>
          <h1 id="trace-detail-title">{summary.trace_id}</h1>
          <p className="observabilitySubtitle">
            <span className={`badge answerState-${summary.answer_state ?? "unknown"}`}>{formatEnum(summary.answer_state)}</span>{" "}
            · {formatEnum(summary.channel)} · {formatMs(summary.total_latency_ms)} · {summary.total_tokens?.toLocaleString() ?? "-"} tokens
            {summary.eval_run_id ? <> · evaluation run {summary.eval_run_id.slice(0, 8)}</> : null}
          </p>
        </div>
        <div className="observabilityTraceDetailActions">
          <Link className="actionButton" href={contentHref}>{includeContent ? "Hide content previews" : "Show redacted content previews"}</Link>
          {assistantId ? <CreateCandidateLink sourceType="trace" sourceId={summary.trace_id} assistantId={assistantId} /> : null}
          <Link className="smallButton" href={backHref}>Back to dashboard</Link>
        </div>
      </header>

      <section aria-label="Request timeline">
        <p className="sectionKicker">Request timeline</p>
        <ol className="observabilityTimeline">
          {stages.map((stage) => (
            <li key={`${stage.stage_name}-${stage.sequence_number}`} className={`observabilityTimelineStep observabilityTimelineStep-${stage.status}`}>
              <span className="observabilityTimelineStepName">{formatEnum(stage.stage_name)}</span>
              <span className={`badge stageStatus-${stage.status}`}>{stage.status}</span>
              <span className="observabilityTimelineStepDetail">
                {stage.latency_ms !== null ? `${stage.latency_ms}ms` : "unmeasured"}
                {stage.reason_code ? ` · ${stage.reason_code}` : ""}
              </span>
            </li>
          ))}
        </ol>
      </section>

      <div className="observabilityTraceDetailGrid">
        <section aria-label="Retrieval debugger">
          <p className="sectionKicker">Retrieval debugger</p>
          {retrieval.length === 0 ? (
            <p className="observabilityEmptyNote">No chunks were retrieved for this request.</p>
          ) : (
            <div className="observabilityRetrievalList">
              {retrieval.map((entry, index) => (
                <div key={`${entry.chunk_id ?? "chunk"}-${index}`} className={`card observabilityRetrievalCard ${entry.selected ? "observabilityRetrievalCard-selected" : "observabilityRetrievalCard-rejected"}`}>
                  <div className="observabilityRetrievalCardTop">
                    <span>#{entry.rank} {entry.source_title ?? "Untitled source"}</span>
                    <span className={`badge ${entry.selected ? "answerState-answered" : "answerState-fallback"}`}>{entry.selected ? "Selected" : "Rejected"}</span>
                  </div>
                  <p className="observabilityRetrievalCardMeta">
                    similarity {entry.similarity_score !== null ? Number(entry.similarity_score).toFixed(3) : "n/a"}
                    {entry.rejection_reason ? ` · ${entry.rejection_reason}` : ""}
                  </p>
                  {entry.content_preview ? <p className="observabilityRetrievalCardPreview">{entry.content_preview}</p> : null}
                </div>
              ))}
            </div>
          )}
        </section>

        <section aria-label="Guardrail outcomes">
          <p className="sectionKicker">Guardrail outcomes</p>
          <div className="observabilityGuardrailList">
            {guardrails.map((guardrail, index) => (
              <div key={`${guardrail.guardrail_name}-${index}`} className="card observabilityGuardrailCard">
                <div className="observabilityGuardrailCardTop">
                  <span>Layer {guardrail.layer} · {formatEnum(guardrail.guardrail_name)}</span>
                  <span className={`badge ${guardrail.blocked ? "answerState-fallback" : "answerState-answered"}`}>{guardrail.verdict}</span>
                </div>
                {guardrail.reason_code ? <p className="observabilityGuardrailReason">{guardrail.reason_code}</p> : null}
              </div>
            ))}
            {guardrails.length === 0 ? <p className="observabilityEmptyNote">No guardrail layers were evaluated for this request.</p> : null}
          </div>
        </section>
      </div>

      <section aria-label="Model call and cost breakdown">
        <p className="sectionKicker">Model call &amp; cost breakdown</p>
        {modelCalls.map((call, index) => (
          <div key={index} className="card observabilityModelCallCard">
            <dl className="observabilityModelCallGrid">
              <Field label="Provider / model" value={`${call.provider_key ?? "-"} / ${call.model_key ?? "-"}`} />
              <Field label="Prompt" value={`${call.prompt_key ?? "-"} v${call.prompt_version ?? "-"}`} />
              <Field label="Outcome" value={call.outcome} />
              <Field label="Latency" value={formatMs(call.latency_ms)} />
              <Field label="Tokens (in / out / total)" value={`${call.input_tokens ?? 0} / ${call.output_tokens ?? 0} / ${call.total_tokens ?? 0}`} />
              <Field
                label="Estimated cost"
                value={call.pricing_known ? `$${Number(call.estimated_total_cost ?? 0).toFixed(6)} ${call.cost_currency}` : "Unknown (no pricing configured)"}
              />
              <Field label="Cost calc version" value={call.cost_calc_version ?? "-"} />
              {call.error_code ? <Field label="Error" value={call.error_code} /> : null}
            </dl>
            {includeContent && (call.raw_prompt_preview || call.raw_response_preview) ? (
              <div className="observabilityModelCallContent">
                {call.raw_prompt_preview ? (
                  <div>
                    <p className="sectionKicker">Prompt preview (redacted)</p>
                    <p className="observabilityContentPreview">{call.raw_prompt_preview}</p>
                  </div>
                ) : null}
                {call.raw_response_preview ? (
                  <div>
                    <p className="sectionKicker">Response preview (redacted)</p>
                    <p className="observabilityContentPreview">{call.raw_response_preview}</p>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        ))}
        {modelCalls.length === 0 ? <p className="observabilityEmptyNote">No provider call was made for this request (blocked before generation).</p> : null}
      </section>
    </section>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="observabilityField">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function formatMs(value: number | null): string {
  if (value === null || value === undefined) return "-";
  return `${Math.round(value).toLocaleString()}ms`;
}

function formatEnum(value: string | null | undefined): string {
  return (value ?? "unknown").replace(/_/g, " ");
}
