#!/usr/bin/env python3
"""Unit tests for content-aware animation selection.

These encode the intent of the sentiment thresholds (e.g. "breaking" needs >= 2
breaking-words; "entertainment" needs >= 3) and the balancing rule that nudges
the chosen animation toward the content sentiment rather than ignoring either
the design's base preference or the news tone.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from content_animation import analyze_content_sentiment, get_content_aware_animation


def _trends(*titles):
    return [{"title": t, "description": ""} for t in titles]


def test_breaking_needs_two_breaking_words():
    assert analyze_content_sentiment(_trends("breaking alert", "urgent developing"), []) == "breaking"
    # a single breaking word is not enough to flip the whole page
    assert analyze_content_sentiment(_trends("breaking news roundup"), []) != "breaking"


def test_entertainment_needs_three_words():
    assert analyze_content_sentiment(_trends("movie music celebrity"), []) == "entertainment"


def test_positive_and_negative_require_a_margin():
    assert analyze_content_sentiment(_trends("success breakthrough wins"), []) == "positive"
    assert analyze_content_sentiment(_trends("crisis disaster crash"), []) == "negative"


def test_default_is_neutral():
    assert analyze_content_sentiment(_trends("quarterly compliance update"), []) == "neutral"


def test_keywords_contribute_to_sentiment():
    # no signal in trends, but keywords push it over the breaking threshold
    assert analyze_content_sentiment(_trends("update"), ["breaking", "urgent"]) == "breaking"


def test_none_title_or_description_is_safe():
    # must not raise on missing/None fields
    assert analyze_content_sentiment([{"title": None, "description": None}], [None]) == "neutral"


def test_animation_balances_base_and_sentiment():
    # neutral sentiment -> "subtle"; balanced against the base preference
    assert get_content_aware_animation([], [], "none") == "subtle"
    assert get_content_aware_animation([], [], "energetic") == "playful"


def test_unknown_base_animation_treated_as_subtle():
    assert get_content_aware_animation([], [], "bogus") == "subtle"
