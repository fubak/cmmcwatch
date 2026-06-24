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
