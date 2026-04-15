"""Tests for normalize_doc() in pass1_extract_pre.py.

Each test targets one of the 12 transformation steps independently.
No file I/O — plain strings only.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "pr-audit-engine"))

from pass1_extract_pre import normalize_doc  # noqa: E402


def test_step1_removes_html_comments():
    """Step 1: Remove HTML comments."""
    assert normalize_doc("before <!-- a comment --> after") == "before  after"
    assert normalize_doc("<!-- multiline\ncomment -->text") == "text"


def test_step2_removes_badge_image_links():
    """Step 2: Remove badge/image links (shields.io etc)."""
    assert normalize_doc("![Build](https://shields.io/badge/build-passing-green)") == ""
    assert normalize_doc("prefix ![img](http://example.com/img.png) suffix") == "prefix  suffix"


def test_step3_strips_heading_markers():
    """Step 3: Strip markdown headings — keep label text."""
    assert normalize_doc("# Heading One") == "Heading One"
    assert normalize_doc("## Heading Two") == "Heading Two"
    assert normalize_doc("### Heading Three") == "Heading Three"
    assert normalize_doc("###### Heading Six") == "Heading Six"


def test_step4_strips_bold_italic_markers():
    """Step 4: Strip bold/italic markers — keep inner text."""
    assert normalize_doc("**bold text**") == "bold text"
    assert normalize_doc("*italic text*") == "italic text"
    assert normalize_doc("***bold italic***") == "bold italic"


def test_step5_strips_inline_code_markers():
    """Step 5: Strip inline code markers — keep inner text."""
    assert normalize_doc("`inline code`") == "inline code"
    assert normalize_doc("run `git status` here") == "run git status here"


def test_step6_removes_code_fences():
    """Step 6: Remove code fences (entire block including content)."""
    assert normalize_doc("```\nsome code here\n```") == ""
    assert normalize_doc("```python\nx = 1\n```") == ""
    assert normalize_doc("before\n```\ncode\n```\nafter") == "before\n\nafter"


def test_step7_strips_link_syntax():
    """Step 7: Strip link syntax — keep display text, drop URL."""
    assert normalize_doc("[link text](https://example.com)") == "link text"
    assert normalize_doc("see [docs](https://example.com/docs) for details") == (
        "see docs for details"
    )


def test_step8_strips_blockquote_markers():
    """Step 8: Strip blockquote markers."""
    assert normalize_doc("> quoted line") == "quoted line"
    assert normalize_doc("> line one\n> line two") == "line one\nline two"


def test_step9_removes_horizontal_rules():
    """Step 9: Remove horizontal rules."""
    assert normalize_doc("---") == ""
    assert normalize_doc("___") == ""
    assert normalize_doc("----") == ""
    assert normalize_doc("line\n---\nline") == "line\n\nline"


def test_step10_strips_trailing_whitespace():
    """Step 10: Strip trailing whitespace per line."""
    result = normalize_doc("line one   \nline two  ")
    assert result == "line one\nline two"


def test_step11_collapses_excessive_blank_lines():
    """Step 11: Collapse 3+ consecutive blank lines to 2."""
    assert normalize_doc("line one\n\n\n\nline two") == "line one\n\nline two"
    assert normalize_doc("a\n\n\n\n\nb") == "a\n\nb"
    # Exactly 2 blank lines (3 newlines) should collapse to 2 newlines
    assert normalize_doc("a\n\n\nb") == "a\n\nb"


def test_step12_strips_leading_trailing_whitespace():
    """Step 12: Strip leading/trailing whitespace from result."""
    assert normalize_doc("\n\nsome content\n\n") == "some content"
    assert normalize_doc("   text   ") == "text"
