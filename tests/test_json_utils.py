#!/usr/bin/env python3
"""Tests for json_utils — shared LLM-JSON repair helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from json_utils import escape_control_chars_in_strings, parse_llm_json, repair_json


class TestRepairJson:
    def test_passes_valid_json_unchanged(self):
        valid = '{"key": "value", "num": 42}'
        # Should be parseable after repair (idempotent on valid input)
        import json

        repaired = repair_json(valid)
        assert json.loads(repaired) == {"key": "value", "num": 42}

    def test_fixes_trailing_comma_in_object(self):
        broken = '{"a": 1,}'
        import json

        assert json.loads(repair_json(broken)) == {"a": 1}

    def test_fixes_trailing_comma_in_array(self):
        broken = "[1, 2, 3,]"
        import json

        assert json.loads(repair_json(broken)) == [1, 2, 3]

    def test_closes_truncated_object(self):
        broken = '{"key": "value", "other": "incomplete'
        import json

        result = json.loads(repair_json(broken))
        assert result["key"] == "value"

    def test_closes_truncated_array(self):
        # Truncation mid-string is recoverable; mid-number is not (algorithm
        # appends `"` when it can't tell). Test the recoverable case.
        broken = '{"items": [1, 2, "thr'
        import json

        # The algorithm closes the open string, then the array, then the object
        result = json.loads(repair_json(broken))
        assert result["items"][0] == 1
        assert len(result["items"]) == 3


class TestEscapeControlChars:
    def test_escapes_literal_newline_in_string(self):
        broken = '{"text": "line1\nline2"}'
        import json

        # Raw newline inside string — invalid JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(broken)

        fixed = escape_control_chars_in_strings(broken)
        assert json.loads(fixed)["text"] == "line1\nline2"

    def test_escapes_literal_tab_in_string(self):
        broken = '{"text": "col1\tcol2"}'
        import json

        fixed = escape_control_chars_in_strings(broken)
        assert json.loads(fixed)["text"] == "col1\tcol2"

    def test_preserves_valid_escape_sequences(self):
        valid = '{"text": "already\\nescaped"}'
        import json

        # Should not double-escape — output remains valid
        result = json.loads(escape_control_chars_in_strings(valid))
        assert result["text"] == "already\nescaped"


class TestParseLlmJson:
    def test_returns_none_for_empty(self):
        assert parse_llm_json("") is None
        assert parse_llm_json(None) is None

    def test_parses_clean_json(self):
        result = parse_llm_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_extracts_json_from_surrounding_text(self):
        # LLM often wraps JSON in prose
        response = 'Here is the JSON:\n{"theme": "minimal", "color": "#fff"}\n\nLet me know!'
        result = parse_llm_json(response)
        assert result == {"theme": "minimal", "color": "#fff"}

    def test_repairs_trailing_comma(self):
        result = parse_llm_json('{"key": "value",}')
        assert result == {"key": "value"}

    def test_repairs_truncated_response(self):
        result = parse_llm_json('{"key": "value", "other": "tru')
        assert result is not None
        assert result["key"] == "value"

    def test_handles_literal_newline_in_string(self):
        result = parse_llm_json('{"text": "multi\nline content"}')
        assert result is not None
        assert "multi" in result["text"]
        assert "line" in result["text"]

    def test_returns_none_for_garbage(self):
        assert parse_llm_json("this is not json at all !!!") is None

    def test_handles_nested_structures(self):
        response = '{"outer": {"inner": [1, 2, {"deep": "value"}]}}'
        result = parse_llm_json(response)
        assert result["outer"]["inner"][2]["deep"] == "value"

    def test_recovers_from_missing_comma_between_keys(self):
        # Common LLM mistake: forgetting comma between fields
        broken = '{"a": "first"\n"b": "second"}'
        result = parse_llm_json(broken)
        assert result is not None
        # Both keys should be present after repair
        assert "a" in result and "b" in result

    def test_multiple_objects_returns_none_or_first(self):
        # Greedy `{.*}` regex captures from first `{` to last `}` —
        # which spans the prose between two objects and isn't valid JSON.
        # The function should fail gracefully (return None), not crash.
        response = '{"first": 1} and another {"second": 2}'
        result = parse_llm_json(response)
        # Either gracefully returns None (current behavior) or extracts one;
        # critically it must not raise.
        assert result is None or isinstance(result, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
