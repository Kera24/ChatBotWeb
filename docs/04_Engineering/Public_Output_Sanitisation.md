# Public Output Sanitisation

TASK-063B4 adds the public output security boundary used by the widget message endpoint. The boundary sits between the internal RAG Orchestrator result and the public idempotency response snapshot.

## Output Format

The MVP public response remains `plain_text`. A restricted-Markdown path is defined for future work, but the current API does not return trusted HTML and does not rely on the widget UI to make unsafe backend output safe.

Allowed future restricted Markdown elements are paragraphs, line breaks, unordered and ordered lists, bold, italics, safe inline code, and validated HTTPS links. Raw HTML, images, iframes, embedded objects, forms, style attributes, event handlers, SVG, data URLs, JavaScript URLs, file URLs, protocol-relative URLs, and unsafe custom entities are not allowed.

## Sanitisation Approach

The implementation uses Python standard-library parsing rather than a browser/backend HTML framework dependency:

- `html.parser.HTMLParser` extracts text while dropping blocked elements such as script/style/iframe/object/embed/svg/math.
- URL validation uses `urllib.parse` and accepts HTTPS URLs only.
- Markdown links are converted to readable text plus URL only after validation.
- The public response is HTML-escaped plain text.

No new backend sanitisation dependency was added. The widget UI must still render defensively as defence in depth.

## Link Policy

Allowed links are HTTPS only, with a hostname and no userinfo. The sanitiser rejects or removes JavaScript, data, file, vbscript, blob, ftp, protocol-relative, malformed, control-character, and overlong URLs. Future UI rendering should add `rel="noopener noreferrer nofollow"` and own target handling.

## Limits

The sanitiser enforces bounded public answers:

- maximum answer characters
- maximum UTF-8 bytes
- maximum paragraphs
- maximum list items
- maximum links
- maximum URL length
- maximum inline-code length

Truncated responses use a safe `[Response truncated]` indicator.

## Leakage Checks

The sanitiser redacts exact known internal values supplied by the public RAG adapter, including tenant/workspace/credential/session/conversation/idempotency/message/execution/model/provider/prompt values. It also removes high-confidence patterns for database URLs, Redis URLs, API-key-like secrets, stack traces, Python/SQL exception text, local filesystem paths, storage paths, prompt metadata, token/cost metadata, and execution metadata.

High-confidence system/developer instruction leakage replaces the answer with a fixed safe fallback and removes citations.

## Citation Rules

Only RAG Orchestrator citations are accepted. Public citations are ordered, deduplicated, capped, bounded, and stripped of document/chunk/version IDs, similarity scores, storage paths, local paths, raw URLs, and internal metadata. Citation markers use `[1]`, `[2]`, etc. Unsupported markers are removed and answered states may downgrade to `low_confidence`.

Fallback answers return zero citations.

## Idempotency

The sanitised public response is stored in `public_message_requests.response_snapshot_json`. Completed duplicate requests return the stored sanitised snapshot unchanged. Sanitiser version changes do not silently mutate historical completed snapshots.

## Events

Safe events include output sanitisation start/completion, truncation, unsafe link removal, citation removal, citation-marker rewriting, leakage detection, fallback replacement, and sanitisation failure. Events do not include raw answer text, removed content, links, secrets, prompts, or internal values.

## Testing

Focused tests:

```text
cd apps/api
python -m pytest tests/test_public_output_sanitisation.py tests/test_public_widget_message_endpoint.py -q
```

Full verification remains:

```text
npm run api:test
npm run web:test
npm run verify
python -m compileall apps/api/app
```