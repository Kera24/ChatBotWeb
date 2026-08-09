"""Unit tests for app.services.chunking_strategies.structure_parser -
Knowledge Pipeline V2 Phase 3/9. Pure text-in/blocks-out, no DB needed."""

from app.services.chunking_strategies.structure_parser import BlockType, parse_structural_blocks


def test_empty_text_returns_no_blocks() -> None:
    assert parse_structural_blocks("") == []
    assert parse_structural_blocks("   \n\n   ") == []


def test_markdown_headings_are_detected_with_correct_levels() -> None:
    text = "# Title\n\n## Subtitle\n\nSome body text here that is long enough to be a paragraph.\n\n### Sub-subtitle\n"
    blocks = parse_structural_blocks(text, source_type="txt")
    headings = [b for b in blocks if b.block_type == BlockType.HEADING]
    assert [(h.text, h.heading_level) for h in headings] == [("Title", 1), ("Subtitle", 2), ("Sub-subtitle", 3)]


def test_heuristic_heading_detected_for_isolated_short_capitalised_line() -> None:
    text = "Intro paragraph text goes here as filler content for this test case.\n\nSUPPORT HOURS\n\nSupport is available weekdays."
    blocks = parse_structural_blocks(text, source_type="txt")
    headings = [b for b in blocks if b.block_type == BlockType.HEADING]
    assert any(h.text == "SUPPORT HOURS" for h in headings)


def test_heuristic_heading_not_triggered_by_a_normal_sentence() -> None:
    text = "This is a normal paragraph that happens to be reasonably short in length."
    blocks = parse_structural_blocks(text, source_type="txt")
    assert all(b.block_type != BlockType.HEADING for b in blocks)


def test_heuristic_heading_requires_isolation_for_blank_line_delimited_sources() -> None:
    # "Title Case Line" here is sandwiched between other content with no
    # blank-line isolation - must NOT be misdetected as a heading for pdf/txt.
    text = "Some Preceding Content\nA Short Title Case Line\nSome Following Content"
    blocks = parse_structural_blocks(text, source_type="txt")
    # The whole thing collapses into one paragraph (no blank line anywhere).
    assert len(blocks) == 1
    assert blocks[0].block_type == BlockType.PARAGRAPH


def test_docx_every_line_is_its_own_paragraph_boundary() -> None:
    text = "First paragraph text here.\nSecond, distinct paragraph text here.\nThird paragraph."
    blocks = parse_structural_blocks(text, source_type="docx")
    paragraphs = [b for b in blocks if b.block_type == BlockType.PARAGRAPH]
    assert len(paragraphs) == 3


def test_docx_short_standalone_line_is_a_heading_without_blank_line_isolation() -> None:
    text = "Introduction\nBody text for the introduction section goes here.\nConclusion\nBody text for the conclusion."
    blocks = parse_structural_blocks(text, source_type="docx")
    headings = [b.text for b in blocks if b.block_type == BlockType.HEADING]
    assert headings == ["Introduction", "Conclusion"]


def test_pdf_soft_wrapped_lines_are_rejoined_into_one_paragraph() -> None:
    # pypdf inserts a newline at each visual line, not each logical
    # paragraph - a blank line is the real paragraph separator for pdf.
    text = "This sentence wraps\nacross several visual\nlines within one page.\n\nThis is a separate paragraph."
    blocks = parse_structural_blocks(text, source_type="pdf")
    paragraphs = [b for b in blocks if b.block_type == BlockType.PARAGRAPH]
    assert len(paragraphs) == 2
    assert "wraps across several visual lines" in paragraphs[0].text


def test_list_items_are_grouped_into_one_list_block() -> None:
    text = "Intro paragraph text goes here as filler for the test.\n\n- First item\n- Second item\n- Third item\n\nClosing paragraph text."
    blocks = parse_structural_blocks(text, source_type="txt")
    list_blocks = [b for b in blocks if b.block_type == BlockType.LIST_BLOCK]
    assert len(list_blocks) == 1
    assert list_blocks[0].text.count("\n") == 2  # three items, two internal newlines


def test_numbered_list_items_are_detected() -> None:
    text = "1. First step\n2. Second step\n3. Third step"
    blocks = parse_structural_blocks(text, source_type="txt")
    assert len(blocks) == 1
    assert blocks[0].block_type == BlockType.LIST_BLOCK


def test_pipe_table_rows_are_grouped_into_one_table_block() -> None:
    text = "| Plan | Price |\n| --- | --- |\n| Monthly | $10 |\n| Annual | $100 |"
    blocks = parse_structural_blocks(text, source_type="txt")
    assert len(blocks) == 1
    assert blocks[0].block_type == BlockType.TABLE_BLOCK
    assert blocks[0].text.count("\n") == 3


def test_fenced_code_block_stays_atomic_including_internal_blank_lines() -> None:
    text = "Intro text for the test paragraph here as filler content.\n\n```\ndef example():\n\n    return 1\n```\n\nClosing paragraph text goes here."
    blocks = parse_structural_blocks(text, source_type="txt")
    code_blocks = [b for b in blocks if b.block_type == BlockType.CODE_BLOCK]
    assert len(code_blocks) == 1
    assert "def example()" in code_blocks[0].text
    assert "return 1" in code_blocks[0].text


def test_unterminated_code_fence_does_not_crash_and_consumes_rest_of_text() -> None:
    text = "Paragraph text goes here as filler for this specific test case.\n\n```\ndef unterminated():\n    pass"
    blocks = parse_structural_blocks(text, source_type="txt")
    assert any(b.block_type == BlockType.CODE_BLOCK for b in blocks)


def test_mixed_document_preserves_block_order() -> None:
    text = "# Heading\n\nParagraph one text goes here as filler content for this case.\n\n- item one\n- item two\n\nParagraph two text goes here as more filler content."
    blocks = parse_structural_blocks(text, source_type="txt")
    assert [b.block_type for b in blocks] == [
        BlockType.HEADING,
        BlockType.PARAGRAPH,
        BlockType.LIST_BLOCK,
        BlockType.PARAGRAPH,
    ]


def test_parsing_is_deterministic() -> None:
    text = "# Title\n\nParagraph text here for the deterministic-output test case.\n\n- a\n- b\n"
    first = parse_structural_blocks(text, source_type="txt")
    second = parse_structural_blocks(text, source_type="txt")
    assert [(b.block_type, b.text, b.heading_level) for b in first] == [(b.block_type, b.text, b.heading_level) for b in second]
