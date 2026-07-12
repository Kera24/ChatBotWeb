import type { ConversationMessage } from "../../lib/api/types";

type TechnicalDetailsProps = {
  message: ConversationMessage;
};

export function TechnicalDetails({ message }: TechnicalDetailsProps) {
  const hasDetails = Boolean(
    message.model_key ||
      message.provider_key ||
      message.prompt_key ||
      message.execution_id ||
      message.total_tokens ||
      message.latency_ms ||
      message.finish_reason,
  );

  if (!hasDetails) return null;

  return (
    <details className="technicalDetails">
      <summary>Technical details</summary>
      <dl>
        <Detail label="Model" value={message.model_key} />
        <Detail label="Provider" value={message.provider_key} />
        <Detail label="Provider model" value={message.provider_model_name} />
        <Detail label="Prompt" value={message.prompt_key} />
        <Detail label="Prompt version" value={message.prompt_version} />
        <Detail label="Prompt hash" value={message.prompt_hash} />
        <Detail label="Execution" value={message.execution_id} />
        <Detail label="Input tokens" value={message.input_tokens} />
        <Detail label="Output tokens" value={message.output_tokens} />
        <Detail label="Total tokens" value={message.total_tokens} />
        <Detail label="Estimated cost" value={message.estimated_cost} />
        <Detail label="Latency" value={message.latency_ms === null ? null : `${message.latency_ms} ms`} />
        <Detail label="Finish" value={message.finish_reason} />
        <Detail label="Error code" value={message.error_code} />
      </dl>
    </details>
  );
}

function Detail({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
