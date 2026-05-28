#!/usr/bin/env python3
"""Tests for generate_design pure helpers (no AI calls)."""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from generate_design import DesignGenerator, DesignSpec


@pytest.fixture
def generator(tmp_path):
    g = DesignGenerator.__new__(DesignGenerator)
    g.session = MagicMock()
    g.history_path = tmp_path / "design_history.json"
    return g


class TestDesignSpecDefaults:
    def test_construct_with_no_args_uses_defaults(self):
        spec = DesignSpec()
        assert spec.theme_name == "Default"
        assert spec.is_dark_mode is True
        assert spec.color_bg == "#0a0a0a"

    def test_post_init_fills_generated_at(self):
        spec = DesignSpec()
        # Should be a UTC-aware ISO timestamp
        assert spec.generated_at
        assert "+00:00" in spec.generated_at or spec.generated_at.endswith("Z")

    def test_post_init_fills_design_seed(self):
        spec = DesignSpec()
        # YYYY-MM-DD format
        assert len(spec.design_seed) == 10
        # Should parse as a date
        datetime.strptime(spec.design_seed, "%Y-%m-%d")

    def test_explicit_seed_preserved(self):
        spec = DesignSpec(design_seed="2026-01-01")
        assert spec.design_seed == "2026-01-01"

    def test_cta_primary_defaults_to_first_option(self):
        spec = DesignSpec(cta_options=["Read More", "Subscribe", "Share"])
        assert spec.cta_primary == "Read More"

    def test_cta_primary_unchanged_if_set(self):
        spec = DesignSpec(cta_options=["A", "B"], cta_primary="Custom")
        assert spec.cta_primary == "Custom"

    def test_no_cta_primary_when_no_options(self):
        spec = DesignSpec()
        # Empty list, no primary set → stays empty
        assert spec.cta_primary == ""


class TestParseAiResponseNormalization:
    """The wrapper should normalize single-variant responses to {variants: [...]}."""

    def test_already_has_variants_passes_through(self, generator):
        response = '{"variants": [{"theme_name": "minimal"}]}'
        result = generator._parse_ai_response(response)
        assert result is not None
        assert "variants" in result
        assert len(result["variants"]) == 1

    def test_single_variant_gets_normalized(self, generator):
        response = '{"theme_name": "Cyber Slate", "headline": "Today", "color_accent": "#3a82f6"}'
        result = generator._parse_ai_response(response)
        assert result is not None
        assert "variants" in result
        assert result["variants"][0]["theme_name"] == "Cyber Slate"
        assert result["variants"][0]["color_accent"] == "#3a82f6"

    def test_cta_field_falls_back_to_cta_primary(self, generator):
        response = '{"theme_name": "x", "cta_primary": "Subscribe"}'
        result = generator._parse_ai_response(response)
        assert result["variants"][0]["cta"] == "Subscribe"

    def test_garbage_returns_none(self, generator):
        # Non-JSON input should return None gracefully
        assert generator._parse_ai_response("not json at all") is None

    def test_handles_extra_prose_around_json(self, generator):
        response = 'Sure, here is the design:\n{"theme_name": "x"}\nLet me know if you need changes.'
        result = generator._parse_ai_response(response)
        assert result is not None
        assert result["variants"][0]["theme_name"] == "x"


class TestDesignSpecConstrainedFields:
    def test_card_radius_accepts_any_value(self):
        # No validation is enforced; just verify dataclass accepts the field
        spec = DesignSpec(card_radius="2rem")
        assert spec.card_radius == "2rem"

    def test_animation_level_accepts_any_value(self):
        spec = DesignSpec(animation_level="moderate")
        assert spec.animation_level == "moderate"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
