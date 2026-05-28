#!/usr/bin/env python3
"""Tests for editorial_generator pure helpers (no AI calls)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from editorial_generator import EditorialGenerator


@pytest.fixture
def generator(tmp_path):
    g = EditorialGenerator.__new__(EditorialGenerator)
    g.public_dir = tmp_path
    g.session = MagicMock()
    return g


class TestSanitizeSlug:
    def test_lowercases_and_replaces_spaces(self, generator):
        assert generator._sanitize_slug("My Article Title") == "my-article-title"

    def test_strips_special_chars(self, generator):
        assert generator._sanitize_slug("CMMC 2.0: Now What?") == "cmmc-2-0-now-what"

    def test_collapses_multiple_dashes(self, generator):
        assert generator._sanitize_slug("a--b---c") == "a-b-c"

    def test_strips_leading_trailing_dashes(self, generator):
        assert generator._sanitize_slug("---hello---") == "hello"

    def test_truncates_to_60_chars(self, generator):
        long_title = "a" * 100
        assert len(generator._sanitize_slug(long_title)) == 60

    def test_empty_returns_default(self, generator):
        assert generator._sanitize_slug("") == "daily-editorial"

    def test_only_special_chars_returns_default(self, generator):
        assert generator._sanitize_slug("!!!@@@###") == "daily-editorial"

    def test_preserves_digits(self, generator):
        assert generator._sanitize_slug("CMMC Level 2 Update") == "cmmc-level-2-update"

    def test_unicode_replaced_with_dash(self, generator):
        # Non-ASCII chars become dashes per the regex
        assert generator._sanitize_slug("café update") == "caf-update"


class TestRepairAndParseDelegates:
    """Verify the repair/parse methods correctly delegate to json_utils."""

    def test_repair_json_delegates(self, generator):
        # The wrapper should accept and return strings
        result = generator._repair_json('{"a": 1,}')
        assert isinstance(result, str)
        # Repaired form should parse cleanly
        import json

        assert json.loads(result) == {"a": 1}

    def test_parse_json_response_returns_dict(self, generator):
        result = generator._parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_response_returns_none_for_garbage(self, generator):
        assert generator._parse_json_response("not json !!!") is None

    def test_parse_json_response_handles_empty(self, generator):
        assert generator._parse_json_response("") is None
        assert generator._parse_json_response(None) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
