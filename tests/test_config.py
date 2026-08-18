#!/usr/bin/env python3
"""Tests for configuration module."""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from config import (
    CMMC_CORE_KEYWORDS,
    CMMC_KEYWORDS,
    CMMC_LINKEDIN_PROFILES,
    CMMC_RSS_FEEDS,
    LIMITS,
    NIST_KEYWORDS,
    SITE_NAME,
    SITE_URL,
    keyword_in_text,
)
from source_catalog import COLLECTOR_SOURCES


class TestConfig:
    """Test configuration values."""

    def test_site_config(self):
        """Test basic site configuration."""
        assert SITE_NAME == "CMMC Watch"
        assert SITE_URL == "https://cmmcwatch.com"

    def test_rss_feeds_exist(self):
        """Test that RSS feeds are configured."""
        assert len(CMMC_RSS_FEEDS) > 0
        assert isinstance(CMMC_RSS_FEEDS, dict)

        # Check at least some key feeds
        assert "FedScoop" in CMMC_RSS_FEEDS
        assert "NIST CSRC" in CMMC_RSS_FEEDS
        assert "Cyber-AB News" in CMMC_RSS_FEEDS

    def test_linkedin_profiles_exist(self):
        """Test that LinkedIn profiles are configured."""
        assert len(CMMC_LINKEDIN_PROFILES) > 0
        assert isinstance(CMMC_LINKEDIN_PROFILES, list)

        # Check that profiles are valid URLs
        for profile in CMMC_LINKEDIN_PROFILES:
            assert profile.startswith("https://www.linkedin.com/")

    def test_keywords_exist(self):
        """Test that keyword lists are configured."""
        assert len(CMMC_CORE_KEYWORDS) > 0
        assert len(NIST_KEYWORDS) > 0
        assert len(CMMC_KEYWORDS) > 0

        # Check for critical keywords
        assert "cmmc" in [k.lower() for k in CMMC_CORE_KEYWORDS]
        assert "nist 800-171" in [k.lower() for k in NIST_KEYWORDS]

    def test_limits_configured(self):
        """Test that rate limits are configured."""
        assert isinstance(LIMITS, dict)
        assert "cmmc_rss" in LIMITS
        assert LIMITS["cmmc_rss"] > 0

    def test_rss_feeds_match_catalog(self):
        catalog = {s.name: s.url for s in COLLECTOR_SOURCES if s.collector == "cmmc_rss"}
        assert CMMC_RSS_FEEDS == catalog

    def test_keyword_in_text_word_boundaries(self):
        """CW-CLASS-02 / CW-FILTER-01: short tokens must not match inside words."""
        assert keyword_in_text("cmmc", "New CMMC rule published")
        assert not keyword_in_text("pla", "The platform update shipped")
        assert not keyword_in_text("dia", "media reports said")
        assert not keyword_in_text("nsa", "unnecessary delay")
        assert not keyword_in_text("ato", "laboratory tests")
        assert keyword_in_text("apt", "APT group attributed")
        assert keyword_in_text("nist 800-171", "Updates to NIST 800-171 Rev 3")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
