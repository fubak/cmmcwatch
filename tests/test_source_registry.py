#!/usr/bin/env python3
"""Tests for source_registry module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from source_registry import (
    _humanize_source,
    format_source_label,
    get_source_metadata,
    source_metadata_dict,
    source_quality_multiplier,
)


class TestGetSourceMetadata:
    def test_returns_metadata_for_known_source(self):
        meta = get_source_metadata("cmmc_rss_fedscoop")
        assert meta is not None
        assert meta.tier > 0

    def test_unknown_source_returns_default(self):
        # Should fall through to DEFAULT_SOURCE_METADATA
        meta = get_source_metadata("totally_unknown_source")
        assert meta is not None
        assert isinstance(meta.tier, int)

    def test_metadata_has_required_fields(self):
        meta = get_source_metadata("cmmc_rss_fedscoop")
        for attr in ("tier", "source_type", "risk", "language", "parser"):
            assert hasattr(meta, attr)


class TestSourceMetadataDict:
    def test_returns_dict(self):
        d = source_metadata_dict("cmmc_rss_fedscoop")
        assert isinstance(d, dict)

    def test_has_expected_keys(self):
        d = source_metadata_dict("cmmc_rss_fedscoop")
        for key in ("tier", "type", "risk", "language", "parser", "display_name"):
            assert key in d, f"missing {key}"

    def test_display_name_filled_for_unknown_source(self):
        d = source_metadata_dict("unknown_xyz")
        # _humanize_source provides a fallback
        assert d["display_name"]


class TestFormatSourceLabel:
    def test_returns_string_with_tier_and_risk(self):
        label = format_source_label("cmmc_rss_fedscoop")
        assert isinstance(label, str)
        assert "[T" in label
        assert "/" in label
        assert label.endswith("]")

    def test_humanizes_unknown_source(self):
        label = format_source_label("cmmc_rss_some_new_source")
        assert isinstance(label, str)
        # Some readable text before the tag
        assert label.split("[")[0].strip()


class TestSourceQualityMultiplier:
    def test_returns_float(self):
        m = source_quality_multiplier("cmmc_rss_fedscoop")
        assert isinstance(m, float)
        assert m > 0

    def test_higher_tier_higher_multiplier(self):
        m_known = source_quality_multiplier("cmmc_rss_fedscoop")
        m_unknown = source_quality_multiplier("totally_random_source")
        # Known good sources should rank >= unknown defaults (tier 4)
        assert m_known >= m_unknown


class TestHumanizeSource:
    def test_returns_source_for_empty(self):
        assert _humanize_source("") == "Source"

    def test_capitalizes_long_words(self):
        result = _humanize_source("federal_news_network")
        # "Federal" "News" "Network" — all capitalized
        assert "Federal" in result
        assert "Network" in result

    def test_uppercases_short_words(self):
        # 3-char or shorter words go uppercase
        result = _humanize_source("dod_news")
        assert "DOD" in result

    def test_strips_underscores(self):
        result = _humanize_source("a_b_c")
        assert "_" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
