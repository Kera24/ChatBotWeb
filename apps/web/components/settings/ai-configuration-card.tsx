import { ShieldCheck } from "lucide-react";

import type { SettingsOperational } from "../../lib/api/settings";

export function AiConfigurationCard({ operational }: { operational: SettingsOperational }) {
  return (
    <section className="settingsPanel" aria-labelledby="ai-settings-title">
      <div className="settingsPanelHeader">
        <div>
          <p className="sectionKicker">AI and retrieval</p>
          <h3 id="ai-settings-title">Environment-controlled configuration</h3>
        </div>
      </div>
      <p className="settingsManagedNotice"><ShieldCheck size={14} aria-hidden="true" />These settings are managed by Conversa administrators and cannot be changed from this dashboard.</p>
      <dl className="settingsFacts compactFacts">
        <div><dt>Provider</dt><dd>{operational.default_ai_provider_key}</dd></div>
        <div><dt>Model</dt><dd>{operational.default_ai_model_key}</dd></div>
        <div><dt>Request timeout</dt><dd>{operational.ai_request_timeout_seconds}s</dd></div>
        <div><dt>Embedding provider</dt><dd>{operational.embedding_provider}</dd></div>
        <div><dt>Embedding model</dt><dd>{operational.embedding_model}</dd></div>
        <div><dt>Embedding dimension</dt><dd>{operational.embedding_dimension}</dd></div>
        <div><dt>Top context chunks</dt><dd>{operational.retrieval_max_context_chunks}</dd></div>
        <div><dt>Context character cap</dt><dd>{operational.retrieval_max_context_chars}</dd></div>
        <div><dt>Chunk size</dt><dd>{operational.chunk_size_words} words</dd></div>
        <div><dt>Chunk overlap</dt><dd>{operational.chunk_overlap_words} words</dd></div>
      </dl>
    </section>
  );
}
