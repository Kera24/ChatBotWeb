"""Regression tests for the ChunkingStrategy abstraction (Knowledge Pipeline
V2, Phases 2-4/9): FixedWordChunkingStrategy (rollback baseline),
StructureAwareChunkingStrategy, SemanticChunkingStrategy. Pure
strategy.chunk(text, config=...) calls - no DB needed."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.services.chunking import split_text_into_chunks
from app.services.chunking_strategies import (
    ChunkingConfig,
    FixedWordChunkingStrategy,
    SemanticChunkingStrategy,
    StructureAwareChunkingStrategy,
)
from app.services.chunking_strategies.registry import UnknownChunkingStrategy, build_chunking_strategy


@dataclass(frozen=True)
class ControlledEmbeddingProvider:
    """Same rationale as tests/test_vector_search_similarity_threshold.py's
    provider of the same name: exact, hand-picked vectors per exact input
    text, so a test can force a known cosine similarity between two units,
    independent of any real model's semantic quality."""

    vectors: dict[str, list[float]] = field(default_factory=dict)
    dimension: int = 2
    provider_name: str = "controlled-test"
    model_name: str = "controlled-test-v1"

    def embed(self, text: str) -> list[float]:
        return self.vectors[text]


def _config(**overrides) -> ChunkingConfig:
    defaults = dict(chunk_size_words=60, chunk_overlap_words=10, min_chunk_size_words=15, max_chunk_size_words=90, source_type="txt")
    defaults.update(overrides)
    return ChunkingConfig(**defaults)


# --- rollback: FixedWordChunkingStrategy is byte-identical to today's baseline


def test_fixed_word_strategy_matches_split_text_into_chunks_exactly() -> None:
    text = " ".join(f"word{i}" for i in range(250))
    config = _config(chunk_size_words=80, chunk_overlap_words=15)
    strategy = FixedWordChunkingStrategy()

    spans = strategy.chunk(text, config=config)
    direct = split_text_into_chunks(text, chunk_size_words=80, chunk_overlap_words=15)

    assert [span.content for span in spans] == direct
    assert all(span.heading_path is None and span.section_title is None for span in spans)


def test_fixed_word_strategy_key_and_version_match_the_recorded_baseline_constant() -> None:
    from app.services.chunking import CHUNKING_STRATEGY_VERSION

    strategy = FixedWordChunkingStrategy()
    assert strategy.strategy_key == "fixed_word"
    assert strategy.strategy_version == CHUNKING_STRATEGY_VERSION


# --- heading preservation ------------------------------------------------------


def test_structure_aware_preserves_heading_path_hierarchy() -> None:
    text = "# Handbook\n\n## Vacation Policy\n\nEmployees accrue vacation time monthly under this policy for full details."
    strategy = StructureAwareChunkingStrategy()
    spans = strategy.chunk(text, config=_config())
    assert any(span.heading_path == "Handbook > Vacation Policy" for span in spans)
    assert any(span.section_title == "Vacation Policy" for span in spans)


def test_structure_aware_content_before_first_heading_has_no_fabricated_heading() -> None:
    text = "Just a plain paragraph with no heading anywhere in this document at all for this test."
    strategy = StructureAwareChunkingStrategy()
    spans = strategy.chunk(text, config=_config())
    assert all(span.heading_path is None and span.section_title is None for span in spans)


# --- paragraph boundaries -------------------------------------------------------


def test_structure_aware_keeps_distinct_paragraphs_within_one_chunk_when_small() -> None:
    text = "# Section\n\nFirst paragraph text here for this test case scenario overall.\n\nSecond distinct paragraph text here for the same scenario."
    strategy = StructureAwareChunkingStrategy()
    spans = strategy.chunk(text, config=_config())
    assert len(spans) == 1
    assert "First paragraph" in spans[0].content
    assert "Second distinct paragraph" in spans[0].content


# --- long-section splitting / maximum-size enforcement --------------------------


def test_structure_aware_splits_an_oversized_section_and_respects_max_size() -> None:
    body = " ".join(f"word{i}" for i in range(400))
    text = f"# Big Section\n\n{body}"
    config = _config(chunk_size_words=60, chunk_overlap_words=10, max_chunk_size_words=90)
    strategy = StructureAwareChunkingStrategy()
    spans = strategy.chunk(text, config=config)

    assert len(spans) > 1
    for span in spans:
        assert len(span.content.split()) <= config.max_chunk_size_words
        assert span.heading_path == "Big Section"


def test_structure_aware_oversized_block_split_preserves_overlap_behavior() -> None:
    body = " ".join(f"word{i}" for i in range(300))
    config = _config(chunk_size_words=60, chunk_overlap_words=10, max_chunk_size_words=90)
    strategy = StructureAwareChunkingStrategy()
    spans = strategy.chunk(body, config=config)

    # The tail of chunk N should reappear at the head of chunk N+1 (the same
    # overlap contract split_text_into_chunks has always provided).
    first_tail = spans[0].content.split()[-10:]
    second_head = spans[1].content.split()[:10]
    assert first_tail == second_head


# --- no tiny fragment chunks -----------------------------------------------------


def test_structure_aware_never_emits_a_chunk_below_the_minimum_when_mergeable() -> None:
    text = "# Parent\n\n## Child\n\nSome real body content for the child section goes here for this specific test."
    config = _config(min_chunk_size_words=15)
    strategy = StructureAwareChunkingStrategy()
    spans = strategy.chunk(text, config=config)
    for span in spans:
        assert len(span.content.split()) >= config.min_chunk_size_words


# --- deterministic output --------------------------------------------------------


def test_structure_aware_output_is_deterministic() -> None:
    text = "# Title\n\nParagraph one goes here for this determinism test case scenario.\n\n- item a\n- item b\n\nParagraph two goes here as well."
    strategy = StructureAwareChunkingStrategy()
    config = _config()
    first = strategy.chunk(text, config=config)
    second = strategy.chunk(text, config=config)
    assert [(s.content, s.heading_path, s.section_title) for s in first] == [(s.content, s.heading_path, s.section_title) for s in second]


# --- metadata preservation --------------------------------------------------------


def test_structure_aware_metadata_records_strategy_relevant_fields() -> None:
    text = "# Title\n\nParagraph text here for the metadata preservation test case."
    strategy = StructureAwareChunkingStrategy()
    spans = strategy.chunk(text, config=_config())
    assert all("section_key" in span.metadata for span in spans)
    assert all("split_reason" in span.metadata for span in spans)


# --- empty/degenerate documents ---------------------------------------------------


@pytest.mark.parametrize("text", ["", "   ", "\n\n\n", "\t \t"])
def test_structure_aware_handles_empty_or_whitespace_only_documents(text: str) -> None:
    strategy = StructureAwareChunkingStrategy()
    assert strategy.chunk(text, config=_config()) == []


def test_structure_aware_handles_a_single_word_document() -> None:
    strategy = StructureAwareChunkingStrategy()
    spans = strategy.chunk("Hello", config=_config())
    assert len(spans) == 1
    assert spans[0].content == "Hello"


# --- very long paragraphs (single block far exceeding max size) -------------------


def test_structure_aware_splits_a_single_very_long_paragraph() -> None:
    long_paragraph = " ".join(f"token{i}" for i in range(500))
    config = _config(chunk_size_words=60, chunk_overlap_words=10, max_chunk_size_words=90)
    strategy = StructureAwareChunkingStrategy()
    spans = strategy.chunk(long_paragraph, config=config)
    assert len(spans) > 1
    assert all(len(s.content.split()) <= config.max_chunk_size_words for s in spans)


# --- lists/tables/code blocks are preserved atomically when they fit --------------


def test_structure_aware_keeps_a_small_list_block_intact_in_one_chunk() -> None:
    text = "# Steps\n\n- Step one goes here\n- Step two goes here\n- Step three goes here"
    strategy = StructureAwareChunkingStrategy()
    spans = strategy.chunk(text, config=_config())
    assert len(spans) == 1
    assert "Step one" in spans[0].content and "Step three" in spans[0].content


def test_structure_aware_keeps_a_small_table_block_intact_in_one_chunk() -> None:
    text = "# Pricing\n\n| Plan | Price |\n| --- | --- |\n| Monthly | $10 |"
    strategy = StructureAwareChunkingStrategy()
    spans = strategy.chunk(text, config=_config())
    assert len(spans) == 1
    assert "| Monthly | $10 |" in spans[0].content


def test_structure_aware_keeps_a_small_code_block_intact_in_one_chunk() -> None:
    text = "# Example\n\n```\ndef f():\n    return 1\n```"
    strategy = StructureAwareChunkingStrategy()
    spans = strategy.chunk(text, config=_config())
    assert len(spans) == 1
    assert "def f():" in spans[0].content


# --- semantic topic changes -------------------------------------------------------
#
# No heading in these bodies (a "preamble" section) - SemanticChunkingStrategy
# prepends heading text to whichever content unit follows it (see
# app.services.chunking_strategies.semantic._section_to_units's
# "pending_heading_prefix" - a heading is never itself an embedding-compared
# unit), which would otherwise make the exact-match ControlledEmbeddingProvider
# below unpredictable. Heading-path preservation through the semantic path is
# already covered separately (test_semantic_strategy_preserves_heading_path).
# semantic_min_unit_words=1 means every individual sentence is immediately
# its own unit (no merging arithmetic to reason about), so the vectors dict
# below can be keyed by exact sentence text.


def test_semantic_strategy_places_a_boundary_at_a_genuine_topic_shift() -> None:
    alpha_1 = "Alpha topic sentence one here today for this test."
    alpha_2 = "Alpha topic sentence two here today for this test."
    beta_1 = "Beta subject sentence one here today for this test."
    beta_2 = "Beta subject sentence two here today for this test."
    text = f"{alpha_1} {alpha_2} {beta_1} {beta_2}"

    provider = ControlledEmbeddingProvider(
        vectors={alpha_1: [1.0, 0.0], alpha_2: [0.98, 0.02], beta_1: [0.0, 1.0], beta_2: [0.02, 0.98]},
        dimension=2,
    )
    # max_chunk_size_words=25 comfortably holds two ~9-word sentences (so a
    # same-topic pair is never split by size alone) but not all four, so the
    # section is genuinely "oversized" and only a real similarity drop
    # explains the resulting boundary.
    config = _config(chunk_size_words=8, max_chunk_size_words=25, min_chunk_size_words=4, semantic_min_unit_words=1, semantic_similarity_threshold=0.5)
    strategy = SemanticChunkingStrategy(embedding_provider=provider)
    spans = strategy.chunk(text, config=config)

    assert len(spans) == 2
    assert "Alpha" in spans[0].content and "Beta" not in spans[0].content
    assert "Beta" in spans[1].content and "Alpha" not in spans[1].content
    assert spans[0].metadata["split_reason"] == "semantic_boundary"


def test_semantic_strategy_keeps_similar_units_together() -> None:
    unit_1 = "Consistent topic sentence one here today for this test."
    unit_2 = "Consistent topic sentence two here today for this test."
    text = f"{unit_1} {unit_2} {unit_1} {unit_2}"  # long enough to count as "oversized"

    provider = ControlledEmbeddingProvider(vectors={unit_1: [1.0, 0.0], unit_2: [0.99, 0.01]}, dimension=2)
    config = _config(chunk_size_words=8, max_chunk_size_words=40, min_chunk_size_words=4, semantic_min_unit_words=1, semantic_similarity_threshold=0.5)
    strategy = SemanticChunkingStrategy(embedding_provider=provider)
    spans = strategy.chunk(text, config=config)

    assert len(spans) == 1
    assert unit_1 in spans[0].content and unit_2 in spans[0].content


def test_semantic_strategy_preserves_heading_path() -> None:
    class _FixedVectorProvider:
        provider_name = "fixed-test"
        model_name = "fixed-test-v1"
        dimension = 2

        def embed(self, text: str) -> list[float]:
            return [1.0, 0.0]  # every unit "looks the same" - no topic shifts

    body = ". ".join(f"Filler sentence number {i}" for i in range(30)) + "."
    text = f"# Handbook\n\n## Leave Policy\n\n{body}"
    config = _config(
        chunk_size_words=10, chunk_overlap_words=2, max_chunk_size_words=20, min_chunk_size_words=4, semantic_min_unit_words=1, semantic_similarity_threshold=0.5
    )
    strategy = SemanticChunkingStrategy(embedding_provider=_FixedVectorProvider())
    spans = strategy.chunk(text, config=config)

    assert len(spans) > 1
    assert all(span.heading_path == "Handbook > Leave Policy" for span in spans)


def test_semantic_strategy_requires_a_threshold_or_falls_back_to_a_measured_default() -> None:
    provider = ControlledEmbeddingProvider(vectors={}, dimension=2, model_name="some-unlisted-model")
    strategy = SemanticChunkingStrategy(embedding_provider=provider)
    # A short document never reaches the semantic-split path at all, so no
    # embed() call happens and no threshold is needed - just confirms
    # construction/chunking without an explicit threshold doesn't crash.
    spans = strategy.chunk("Short document text here for this specific test case.", config=_config(semantic_similarity_threshold=None))
    assert len(spans) == 1


def test_semantic_strategy_is_deterministic() -> None:
    unit_1 = "Deterministic topic sentence one here today for this test."
    unit_2 = "Different subject sentence two here today for this test."
    text = f"{unit_1} {unit_2} {unit_1} {unit_2}"
    provider = ControlledEmbeddingProvider(vectors={unit_1: [1.0, 0.0], unit_2: [0.0, 1.0]}, dimension=2)
    config = _config(chunk_size_words=8, max_chunk_size_words=25, min_chunk_size_words=3, semantic_min_unit_words=1, semantic_similarity_threshold=0.5)
    strategy = SemanticChunkingStrategy(embedding_provider=provider)
    first = strategy.chunk(text, config=config)
    second = strategy.chunk(text, config=config)
    assert [s.content for s in first] == [s.content for s in second]


def test_semantic_strategy_never_produces_a_chunk_below_minimum_when_mergeable() -> None:
    units = [f"Unit number {i} with sufficient words to count as a real sentence here." for i in range(6)]
    text = " ".join(units)
    # Alternate similar vectors so several adjacent units are called a topic
    # shift, forcing many small groups that must then get merged up to the
    # minimum.
    vectors = {units[i]: ([1.0, 0.0] if i % 2 == 0 else [0.0, 1.0]) for i in range(len(units))}
    provider = ControlledEmbeddingProvider(vectors=vectors, dimension=2)
    config = _config(chunk_size_words=8, max_chunk_size_words=200, min_chunk_size_words=20, semantic_min_unit_words=1, semantic_similarity_threshold=0.5)
    strategy = SemanticChunkingStrategy(embedding_provider=provider)
    spans = strategy.chunk(text, config=config)
    for span in spans:
        assert len(span.content.split()) >= config.min_chunk_size_words


# --- registry ----------------------------------------------------------------------


def test_registry_builds_fixed_word_and_structure_aware_without_a_provider() -> None:
    assert build_chunking_strategy("fixed_word").strategy_key == "fixed_word"
    assert build_chunking_strategy("structure_aware").strategy_key == "structure_aware"


def test_registry_requires_embedding_provider_for_structure_semantic() -> None:
    with pytest.raises(UnknownChunkingStrategy):
        build_chunking_strategy("structure_semantic")


def test_registry_rejects_unknown_strategy_key() -> None:
    with pytest.raises(UnknownChunkingStrategy):
        build_chunking_strategy("not_a_real_strategy")
