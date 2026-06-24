#!/usr/bin/env python3
"""Golden-output test for the extracted article HTML renderer.

``render_article_html`` was moved verbatim out of
``EditorialGenerator._generate_article_html``. This test pins the exact byte
output for a fixed article + design tokens, so the extraction (and any future
edit) cannot silently change the rendered article page — escaping, JSON-LD
structured data, CSS, and layout are all covered. The inputs deliberately
include ``<``, ``>``, ``&``, quotes, and a ``</script>`` payload to exercise the
two distinct escaping contexts (HTML attributes vs. JSON-LD inside <script>).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

FIXTURE = Path(__file__).parent / "fixtures" / "article_golden.html"


def sample_article():
    """Fixed article with adversarial characters in escaped fields."""
    from editorial_generator import EditorialArticle

    return EditorialArticle(
        title='CMMC & "Phase 3" <Rollout> Begins',
        slug="cmmc-phase-3-rollout-begins",
        date="2026-06-24",
        summary="DoD finalizes the rule; primes & subs must meet NIST 800-171 <controls>.",
        content=(
            "<p>Body paragraph one.</p>\n"
            "<h2>Why it matters</h2>\n"
            "<p>Second paragraph with <strong>emphasis</strong>.</p>"
        ),
        word_count=812,
        top_stories=[
            "DoD publishes final CMMC rule",
            'Analyst note: "</script>" injection risk in feeds',
        ],
        keywords=["CMMC", "NIST 800-171", "DFARS", "compliance & audits"],
        mood="urgent",
        url="/articles/2026/06/24/cmmc-phase-3-rollout-begins/",
    )


def sample_tokens():
    """Fixed design tokens covering every key the renderer reads."""
    return {
        "font_primary": "Space Grotesk",
        "font_secondary": "Inter",
        "primary_color": "#6d28d9",
        "accent_color": "#22d3ee",
        "bg_color": "#0a0a0a",
        "text_color": "#ffffff",
        "muted_color": "#a1a1aa",
        "border_color": "#27272a",
        "card_bg": "#18181b",
        "base_mode": "dark-mode",
    }


def sample_related():
    """Two related articles to exercise the related-cards branch."""
    return [
        {
            "date": "2026-06-20",
            "title": "C3PAO assessment backlog grows",
            "summary": "Assessors report a multi-month queue as demand spikes ahead of the deadline.",
            "url": "/articles/2026/06/20/c3pao-assessment-backlog/",
        },
        {
            "date": "2026-06-18",
            "title": "Summit 7 webinar recap",
            "summary": "Key takeaways for primes preparing System Security Plans.",
            "url": "/articles/2026/06/18/summit-7-webinar-recap/",
        },
    ]


def test_render_article_html_matches_golden():
    """The extracted renderer must reproduce the article page byte-for-byte.

    The fixture was captured from the original
    ``EditorialGenerator._generate_article_html`` before the extraction. Any
    drift in escaping, structured data, CSS, or markup fails here — which is the
    point: this proves the move changed structure, not output.
    """
    from article_renderer import render_article_html

    out = render_article_html(sample_article(), sample_tokens(), sample_related())
    assert out == FIXTURE.read_text(encoding="utf-8")


# --- articles index page ----------------------------------------------------

INDEX_FIXTURE = Path(__file__).parent / "fixtures" / "articles_index_golden.html"


def sample_index_articles():
    """Fixed article metadata (the shape get_all_articles returns)."""
    return [
        {
            "title": "DoD publishes final CMMC rule",
            "date": "2026-06-24",
            "url": "/articles/2026/06/24/dod-final-cmmc-rule/",
            "summary": "The long-awaited rule lands; <primes> & subs must comply.",
            "mood": "urgent",
            "word_count": 812,
            "keywords": ["CMMC", "DFARS"],
        },
        {
            "title": "C3PAO assessment backlog grows",
            "date": "2026-06-20",
            "url": "/articles/2026/06/20/c3pao-backlog/",
            "summary": "Assessors report a multi-month queue.",
            "mood": "informative",
            "word_count": 540,
            "keywords": ["C3PAO", "assessment"],
        },
        {
            "title": "Summit 7 webinar recap",
            "date": "2026-06-18",
            "url": "/articles/2026/06/18/summit-7-recap/",
            "summary": "Takeaways for primes preparing SSPs.",
            "mood": "informative",
            "word_count": 410,
            "keywords": ["SSP", "Summit 7"],
        },
    ]


def _frozen_datetime():
    """datetime subclass whose now() is fixed, so the index page (which embeds
    today's date in the shared header/footer) renders deterministically."""
    from datetime import datetime as _dt

    class _Frozen(_dt):
        @classmethod
        def now(cls, tz=None):
            return _dt(2026, 6, 24, 12, 0, 0)

    return _Frozen


def test_generate_articles_index_matches_golden(tmp_path, monkeypatch):
    """The extracted index renderer must reproduce the index page byte-for-byte.

    Driven end-to-end through the public method (get_all_articles stubbed,
    datetime.now() frozen). The fixture was captured from the original inline
    f-string before the extraction, so a pass proves output is unchanged.
    """
    import articles_index_renderer
    import editorial_generator as eg

    monkeypatch.setattr(articles_index_renderer, "datetime", _frozen_datetime())
    gen = eg.EditorialGenerator(public_dir=tmp_path)
    monkeypatch.setattr(gen, "get_all_articles", lambda: sample_index_articles())

    out = gen.generate_articles_index(design=None)
    assert out == INDEX_FIXTURE.read_text(encoding="utf-8")
