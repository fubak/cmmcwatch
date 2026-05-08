#!/usr/bin/env python3
"""Tests for editorial_generator XSS escaping in article HTML rendering.

Targets the regression where article.title/summary/mood/keywords/top_stories
were interpolated raw into HTML — opening a stored-XSS path via attacker-
influenced upstream feed content.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from editorial_generator import EditorialArticle, EditorialGenerator


def _hostile_article():
    """Article with HTML-injection payloads in every user-controllable field."""
    return EditorialArticle(
        title="<script>alert('title')</script>",
        slug="hostile",
        date="2026-05-08",
        summary='"><img src=x onerror=alert("summary")>',
        content="<p>Legitimate content stays.</p>",  # intentionally not escaped
        word_count=100,
        top_stories=["<script>alert('story')</script>", "Normal Story"],
        keywords=["<script>alert('kw')</script>", "cmmc"],
        mood='" autofocus onfocus="alert(1)',
        url="/articles/2026/05/08/hostile/",
    )


def _design_tokens():
    """Minimal tokens dict that _generate_article_html expects."""
    return {
        "base_mode": "dark-mode",
        "bg_color": "#0a0a0a",
        "text_color": "#ffffff",
        "primary_color": "#6366f1",
        "accent_color": "#7c3aed",
        "card_bg": "#18181b",
        "border_color": "#27272a",
        "muted_color": "#a1a1aa",
        "font_primary": "Space Grotesk",
        "font_secondary": "Inter",
        "radius": "1rem",
        "transition": "200ms",
    }


@pytest.fixture
def generator(tmp_path):
    """Build EditorialGenerator with a real public_dir."""
    g = EditorialGenerator.__new__(EditorialGenerator)
    g.public_dir = tmp_path
    g.session = MagicMock()
    return g


class TestArticleHtmlXssEscaping:
    def test_script_in_title_is_escaped(self, generator):
        article = _hostile_article()
        html = generator._generate_article_html(article, _design_tokens())
        # Raw script tag from title must not appear
        assert "<script>alert('title')</script>" not in html
        # Escaped form should be present (in either body h1 or <title> meta)
        assert "&lt;script&gt;alert(" in html

    def test_script_in_summary_is_escaped(self, generator):
        article = _hostile_article()
        html = generator._generate_article_html(article, _design_tokens())
        # The img-onerror payload from summary must not survive as raw HTML
        assert '<img src=x onerror=alert("summary")>' not in html

    def test_script_in_top_stories_is_escaped(self, generator):
        article = _hostile_article()
        html = generator._generate_article_html(article, _design_tokens())
        assert "<script>alert('story')</script>" not in html
        assert "&lt;script&gt;alert(&#x27;story&#x27;)" in html or "&lt;script&gt;alert('story')" in html

    def test_script_in_keywords_is_escaped(self, generator):
        article = _hostile_article()
        html = generator._generate_article_html(article, _design_tokens())
        assert "<script>alert('kw')</script>" not in html

    def test_attribute_breakout_in_mood_blocked(self, generator):
        article = _hostile_article()
        html = generator._generate_article_html(article, _design_tokens())
        # mood goes inside <span>...</span> text content, not an attribute,
        # but escaping should still neutralize the payload
        assert 'autofocus onfocus="alert(1)' not in html

    def test_legitimate_content_passes_through(self, generator):
        article = _hostile_article()
        html = generator._generate_article_html(article, _design_tokens())
        # article.content is intentionally NOT escaped (it holds rendered markdown
        # HTML produced by our trusted pipeline), so legitimate content stays.
        assert "<p>Legitimate content stays.</p>" in html

    def test_normal_story_title_is_present(self, generator):
        article = _hostile_article()
        html = generator._generate_article_html(article, _design_tokens())
        assert "Normal Story" in html

    def test_normal_keyword_is_present(self, generator):
        article = _hostile_article()
        html = generator._generate_article_html(article, _design_tokens())
        assert ">cmmc<" in html


class TestJsonLdEscaping:
    def test_quote_in_title_is_json_escaped_in_jsonld(self, generator):
        article = EditorialArticle(
            title='Title with "quote" and \\backslash',
            slug="x",
            date="2026-05-08",
            summary="S",
            content="C",
            word_count=10,
            top_stories=[],
            keywords=[],
            mood="neutral",
            url="/x/",
        )
        html = generator._generate_article_html(article, _design_tokens())
        # JSON-LD should NOT contain unescaped " inside the headline value —
        # it would break the JSON. Check the headline appears with \" form.
        assert '\\"quote\\"' in html

    def test_backslash_in_title_is_json_escaped(self, generator):
        article = EditorialArticle(
            title="C:\\path\\title",
            slug="x",
            date="2026-05-08",
            summary="S",
            content="C",
            word_count=10,
            top_stories=[],
            keywords=[],
            mood="neutral",
            url="/x/",
        )
        html = generator._generate_article_html(article, _design_tokens())
        # \\ should be doubled in JSON output
        assert "C:\\\\path\\\\title" in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
