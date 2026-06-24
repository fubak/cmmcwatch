#!/usr/bin/env python3
"""Tests for DesignGenerator's deterministic (non-AI) logic.

Covers the rng-seeded variety selectors (each personality may only produce its
allowed visual options; unknown personalities fall back to a safe default), the
headline/subheadline builders, AI-response normalization, the theme-history
window (which drives design variety and is preserved across CI runs), and the
combinatorics count — i.e. the parts of design generation that need no live AI.
"""

import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from generate_design import DesignGenerator, calculate_combinations


def _gen(tmp_path=None):
    g = DesignGenerator.__new__(DesignGenerator)
    if tmp_path is not None:
        g.history_path = tmp_path / "design_history.json"
    return g


class TestSelectors:
    def test_background_pattern_within_allowed_set(self):
        g = _gen()
        rng = random.Random(0)
        allowed = {"grid", "dots", "noise", "gradient_radial"}
        for _ in range(25):
            assert g._select_background_pattern("tech", rng) in allowed

    def test_minimal_personality_is_always_plain(self):
        g = _gen()
        rng = random.Random(7)
        for _ in range(25):
            assert g._select_background_pattern("minimal", rng) == "none"

    def test_unknown_personality_falls_back_to_default(self):
        g = _gen()
        assert g._select_background_pattern("nope", random.Random(1)) == "none"
        assert g._select_accent_style("nope", random.Random(1)) == "none"
        assert g._select_special_mode("nope", {}, random.Random(1)) == "standard"

    def test_same_seed_is_deterministic(self):
        g = _gen()
        assert g._select_special_mode("tech", {}, random.Random(42)) == g._select_special_mode(
            "tech", {}, random.Random(42)
        )


class TestHeadlineSubheadline:
    def test_headline_uses_top_trend_title(self):
        g = _gen()
        assert g._create_headline([{"title": "DoD finalizes CMMC rule"}], random.Random(0)) == "DoD finalizes CMMC rule"

    def test_headline_fallback_when_no_trends(self):
        g = _gen()
        assert g._create_headline([], random.Random(0)) == "What's Trending"

    def test_subheadline_is_nonempty_string(self):
        g = _gen()
        for seed in range(8):
            out = g._create_subheadline(["CMMC", "NIST", "DFARS"], random.Random(seed))
            assert isinstance(out, str) and out


class TestParseAiResponse:
    def test_single_variant_normalized_to_variants_list(self):
        g = _gen()
        data = g._parse_ai_response('{"theme_name": "X", "headline": "H", "cta": "Go"}')
        assert "variants" in data and len(data["variants"]) == 1
        assert data["variants"][0]["theme_name"] == "X"

    def test_multi_variant_passes_through(self):
        g = _gen()
        data = g._parse_ai_response('{"variants": [{"theme_name": "A"}, {"theme_name": "B"}]}')
        assert len(data["variants"]) == 2

    def test_garbage_returns_none(self):
        g = _gen()
        assert g._parse_ai_response("not json at all") is None


class TestThemeHistory:
    def test_store_then_load_roundtrip(self, tmp_path):
        g = _gen(tmp_path)
        g._store_theme("Quantum Compliance")
        assert "quantum compliance" in g._load_recent_themes()

    def test_old_themes_outside_window_are_ignored(self, tmp_path):
        # Only recent themes should count, so variety isn't blocked forever.
        g = _gen(tmp_path)
        old_ts = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        g.history_path.write_text(json.dumps([{"theme": "Ancient", "timestamp": old_ts}]))
        assert g._load_recent_themes(days=7) == []

    def test_missing_history_file_returns_empty(self, tmp_path):
        assert _gen(tmp_path)._load_recent_themes() == []


class TestCalculateCombinations:
    def test_is_a_large_positive_count(self):
        total = calculate_combinations()
        assert isinstance(total, int)
        assert total > 1000  # the design space is intended to be in the thousands
