# Real Local Embedding Provider (Ollama)

Version: 1.0
Related: [Evaluation Framework](./Evaluation_Framework.md), [Real-Embedding Final Report](./Evaluation_Real_Embedding_Final_Report.md)

## Why this exists

The deterministic mock embedding provider (`local-mock`) hashes text with SHA-256 and carries no semantic content - it cannot validate any retrieval-similarity-threshold decision (see [Score Distribution Analysis](./Evaluation_Score_Distribution_Analysis.md) for the empirical proof). This document covers using a **real, local, credential-free semantic embedding model via [Ollama](https://ollama.com)** for evaluation - never for production customer document embedding in this cycle (see "Production implications" below).

## Environment variables

All prefixed `EVAL_EMBEDDING_*` - completely separate from the app-wide `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`/`EMBEDDING_DIMENSION` settings (which control real customer document embedding and are unaffected by any of this):

| Variable | Meaning | Default |
| --- | --- | --- |
| `EVAL_EMBEDDING_PROVIDER` | `local-mock` (default) or `ollama` | `local-mock` |
| `EVAL_EMBEDDING_MODEL` | Ollama model name (no default - must be set explicitly for `ollama`) | unset |
| `EVAL_EMBEDDING_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `EVAL_EMBEDDING_DIMENSION` | Must match the model's actual output dimension exactly (verify, do not assume) | `768` |

`RETRIEVAL_MIN_SIMILARITY_SCORE` (app-wide, `app/core/config.py`) stays at its safe default of `0.0` (off) - it is **not** overridden globally by any of this; `eval_run.py --real` applies the evidence-based value (`0.25` for `nomic-embed-text-v2-moe`) automatically per run instead, via `app/evaluation/embedding_config.py::recommended_min_similarity_score`. Override any single run with `--min-similarity-score <float>`.

## No silent fallback, fails clearly

`build_real_eval_embedding_provider()` and every `--real`-flagged CLI command raise a clear, actionable `EvalEmbeddingNotConfiguredError`/`EmbeddingProviderError` and exit non-zero if: `EVAL_EMBEDDING_PROVIDER` is unset or `local-mock`; `EVAL_EMBEDDING_MODEL` is unset; the Ollama runtime is unreachable; the requested model is not installed; the model does not report an `embedding` capability; or the model returns a vector of an unexpected dimension. None of these ever silently fall back to the mock provider.

## Setup

### 1. Install Ollama and an embedding model

Windows PowerShell and Linux/bash are identical here (Ollama itself is cross-platform):

```
# Check Ollama is installed and see what's already available:
ollama list

# If no embedding-capable model is installed, pull one (any Ollama embedding
# model works - do not assume this specific one is what's on your machine):
ollama pull nomic-embed-text-v2-moe

# Start the runtime if it is not already running:
ollama serve
```

### 2. Verify the installed model and its dimension (never assume)

```bash
# bash
curl -s http://localhost:11434/api/tags | python -m json.tool
curl -s http://localhost:11434/api/embed -d '{"model": "nomic-embed-text-v2-moe", "input": ["probe"]}' | python -c "import json,sys; print(len(json.load(sys.stdin)['embeddings'][0]))"
```

```powershell
# PowerShell
Invoke-RestMethod http://localhost:11434/api/tags | ConvertTo-Json -Depth 5
$response = Invoke-RestMethod -Uri http://localhost:11434/api/embed -Method Post -Body (@{model="nomic-embed-text-v2-moe"; input=@("probe")} | ConvertTo-Json) -ContentType "application/json"
$response.embeddings[0].Count
```

Set `EVAL_EMBEDDING_DIMENSION` to whatever number that prints - if it does not match `768`, the fixture-seeding and evaluation-run steps below will fail clearly (dimension mismatch) rather than silently producing wrong results.

### 3. Rebuild the evaluation corpus with real embeddings

```bash
# bash
cd apps/api
EVAL_EMBEDDING_PROVIDER=ollama EVAL_EMBEDDING_MODEL=nomic-embed-text-v2-moe EVAL_EMBEDDING_DIMENSION=768 \
  python -m app.operations.eval_golden_setup --real
```

```powershell
# PowerShell
cd apps/api
$env:EVAL_EMBEDDING_PROVIDER = "ollama"
$env:EVAL_EMBEDDING_MODEL = "nomic-embed-text-v2-moe"
$env:EVAL_EMBEDDING_DIMENSION = "768"
python -m app.operations.eval_golden_setup --real
```

This prints `organisation_id`/`workspace_id`/`dataset_id`/`assistant_id` - copy these for every command below. It seeds into a **separate** database file (`apps/api/golden-eval-real.db`) from the mock-embedding fixture (`golden-eval.db`), so the two never collide.

### 4. Run the real baseline

```bash
# bash
DATABASE_URL="sqlite:///./golden-eval-real.db" python -m app.operations.eval_run \
  --dataset <dataset_id> --assistant <assistant_id> --organisation <organisation_id> --workspace <workspace_id> \
  --real --case-timeout 120 --format json
```

```powershell
# PowerShell
$env:DATABASE_URL = "sqlite:///./golden-eval-real.db"
python -m app.operations.eval_run --dataset <dataset_id> --assistant <assistant_id> --organisation <organisation_id> --workspace <workspace_id> --real --case-timeout 120 --format json
```

`--case-timeout 120` is recommended for real runs: SQLite recomputes every chunk's embedding live on every query (see `app.services.vector_search._search_sqlite`), so a real embedding call is meaningfully slower than the mock's in-process hash - the default 30s timeout, tuned for the mock provider, is too tight for a 13-document corpus under real embedding load.

### 5. Run a focused category

```bash
python -m app.operations.eval_run --dataset <id> --assistant <id> --organisation <id> --workspace <id> --real --category prompt_injection --format text
```

### 6. Run a threshold experiment

```bash
python -m app.operations.eval_run --dataset <id> --assistant <id> --organisation <id> --workspace <id> --real --min-similarity-score 0.25 --format json
```

### 7. Run the score-distribution analysis

```bash
python -m app.operations.eval_score_distribution --dataset <id> --assistant <id> --organisation <id> --workspace <id> --format text
```

### 8. Run the final full evaluation (accepted configuration)

```bash
python -m app.operations.eval_run --dataset <id> --assistant <id> --organisation <id> --workspace <id> --real --case-timeout 120 --format json
```

(No `--min-similarity-score` needed - `--real` auto-applies the evidence-based `0.25` for `nomic-embed-text-v2-moe`; override explicitly for a different model or experiment.)

### 9. Compare baseline and final

```bash
DATABASE_URL="sqlite:///./golden-eval-real.db" python -m app.operations.eval_report \
  --run <final_run_id> --baseline <baseline_run_id> --organisation <id> --workspace <id> --format json
```

### 10. Apply the launch gate

```bash
DATABASE_URL="sqlite:///./golden-eval-real.db" python -m app.operations.eval_report --run <run_id> --organisation <id> --workspace <id> --gate
```

### 11. Clean up the fixture

```bash
python -m app.operations.eval_golden_setup --real --teardown
```

```powershell
python -m app.operations.eval_golden_setup --real --teardown
```

## Production implications

- **Nothing in this cycle changes production behaviour.** `EMBEDDING_PROVIDER` (the setting real customer document embedding actually uses) remains `local-mock` by default, untouched.
- If/when a real embedding provider is adopted for production, it will need: (1) a PostgreSQL migration widening `chunks.embedding_vector` from `vector(1536)` to the new model's dimension, plus re-embedding every existing customer document (a deliberate, scheduled maintenance operation - not something to do casually); (2) re-running the exact score-distribution + controlled-experiment process this document describes against that specific model, since `RETRIEVAL_MIN_SIMILARITY_SCORE = 0.25` is calibrated for `nomic-embed-text-v2-moe` specifically and is not a universal constant; (3) setting the production `RETRIEVAL_MIN_SIMILARITY_SCORE` env var to the newly-derived value at the same time the new provider goes live, not before (an unmatched threshold/provider pair silently misbehaves).
- Ollama itself is a local development/evaluation tool in this design, not a proposed production embedding runtime. A production real-embedding provider would more likely be a hosted API (subject to its own credential/cost/compliance evaluation, not attempted in this cycle) or a self-hosted inference server appropriate for the target VPS/Docker Compose deployment - Azure compatibility is unaffected either way, since no Azure-specific dependency is introduced anywhere in this change.

## Tests

Deterministic tests (`apps/api/tests/test_ollama_embedding_provider.py`) always run and never require Ollama - they validate configuration errors and the "no silent fallback" guarantee using unreachable endpoints. A small number of tests in the same file are marked to skip cleanly (not fail) when no local Ollama runtime is reachable, and self-configure to whatever embedding-capable model is actually installed rather than hardcoding one.
