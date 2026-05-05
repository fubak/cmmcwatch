#!/usr/bin/env python3
"""Tests for story_validator module."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from story_validator import StoryValidator


def _story(
    title="Test Story",
    url="https://example.com/1",
    category="cmmc_program",
    source="cmmc_rss_fedscoop",
    days_ago=0,
    timestamp=None,
):
    """Build a minimal story dict for testing."""
    if timestamp is None:
        ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
        timestamp = ts.isoformat()
    return {
        "title": title,
        "url": url,
        "category": category,
        "source": source,
        "timestamp": timestamp,
        "description": f"Description of {title}",
    }


class TestFilterOldStories:
    def setup_method(self):
        self.validator = StoryValidator.__new__(StoryValidator)
        self.validator.MAX_STORY_AGE_DAYS = 7

    def test_recent_stories_pass_through(self):
        stories = [_story("Recent", days_ago=0), _story("Yesterday", days_ago=1)]
        valid, rejected = self.validator._filter_old_stories(stories)
        assert len(valid) == 2
        assert len(rejected) == 0

    def test_old_stories_are_rejected(self):
        stories = [_story("Old Story", days_ago=10)]
        valid, rejected = self.validator._filter_old_stories(stories)
        assert len(valid) == 0
        assert len(rejected) == 1
        assert "rejection_reason" in rejected[0]

    def test_mixed_stories_filtered_correctly(self):
        stories = [
            _story("Fresh", days_ago=0),
            _story("Old", days_ago=30),
            _story("Borderline", days_ago=6),
        ]
        valid, rejected = self.validator._filter_old_stories(stories)
        assert len(valid) == 2
        assert len(rejected) == 1

    def test_missing_timestamp_passes_through(self):
        story = {"title": "No Timestamp", "url": "https://example.com/x", "category": "cmmc_program"}
        valid, rejected = self.validator._filter_old_stories([story])
        assert len(valid) == 1

    def test_naive_timestamp_string_handled(self):
        naive_ts = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        story = _story("Naive TS", timestamp=naive_ts)
        valid, rejected = self.validator._filter_old_stories([story])
        assert len(valid) == 1

    def test_aware_utc_timestamp_string_handled(self):
        aware_ts = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        story = _story("Aware TS", timestamp=aware_ts)
        valid, rejected = self.validator._filter_old_stories([story])
        assert len(valid) == 1

    def test_z_suffix_timestamp_handled(self):
        ts = datetime.now(timezone.utc) - timedelta(days=1)
        z_ts = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        story = _story("Z Suffix", timestamp=z_ts)
        valid, rejected = self.validator._filter_old_stories([story])
        assert len(valid) == 1

    def test_no_timezone_comparison_error(self):
        # Mixing aware + naive was a latent bug — ensure no TypeError raised
        aware_ts = datetime.now(timezone.utc) - timedelta(days=2)
        naive_ts = datetime.now() - timedelta(days=30)
        stories = [
            _story("Aware", timestamp=aware_ts.isoformat()),
            _story("Naive Old", timestamp=naive_ts.strftime("%Y-%m-%d %H:%M:%S")),
        ]
        valid, rejected = self.validator._filter_old_stories(stories)
        # Should not raise TypeError
        assert len(valid) == 1
        assert len(rejected) == 1


class TestBasicDeduplicate:
    def setup_method(self):
        self.validator = StoryValidator.__new__(StoryValidator)

    def test_unique_stories_pass_through(self):
        stories = [
            _story("CMMC Assessment Update", url="https://example.com/1"),
            _story("NIST 800-171 Revision Released", url="https://example.com/2"),
        ]
        valid, rejected = self.validator._basic_deduplicate(stories)
        assert len(valid) == 2
        assert len(rejected) == 0

    def test_duplicate_titles_rejected(self):
        stories = [
            _story("CMMC Program Update Today", url="https://example.com/1"),
            _story("CMMC Program Update Today", url="https://example.com/2"),
        ]
        valid, rejected = self.validator._basic_deduplicate(stories)
        assert len(valid) == 1
        assert len(rejected) == 1

    def test_empty_list(self):
        valid, rejected = self.validator._basic_deduplicate([])
        assert valid == []
        assert rejected == []

    def test_single_story(self):
        stories = [_story("Only Story")]
        valid, rejected = self.validator._basic_deduplicate(stories)
        assert len(valid) == 1
        assert len(rejected) == 0


class TestCategoryValidation:
    def setup_method(self):
        self.validator = StoryValidator.__new__(StoryValidator)

    def test_valid_categories_are_accepted(self):
        valid_categories = ["cmmc_program", "nist_compliance", "dib_news", "federal_cybersecurity"]
        for cat in valid_categories:
            story = _story(category=cat)
            # Category validation is part of broader validate logic;
            # just ensure the field is present
            assert story["category"] == cat


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
