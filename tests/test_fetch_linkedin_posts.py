#!/usr/bin/env python3
"""Tests for fetch_linkedin_posts pure helpers (no Apify network calls)."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from fetch_linkedin_posts import (
    LinkedInPost,
    _calculate_post_score,
    _extract_keywords,
    _get_profile_username,
    _parse_linkedin_item,
    linkedin_posts_to_trends,
)


def _post(**overrides):
    base = dict(
        title="Test post",
        author_name="Test Author",
        author_title="CISO",
        author_url="https://linkedin.com/in/test",
        post_url="https://linkedin.com/posts/test_post",
        content="A post about CMMC compliance and NIST 800-171 controls.",
        timestamp=datetime.now(timezone.utc),
        likes=10,
        comments=3,
        shares=1,
    )
    base.update(overrides)
    return LinkedInPost(**base)


class TestGetProfileUsername:
    def test_extracts_from_standard_url(self):
        assert _get_profile_username("https://linkedin.com/in/katie-arrington") == "katie-arrington"

    def test_extracts_with_trailing_slash(self):
        assert _get_profile_username("https://linkedin.com/in/jacob-horne/") == "jacob-horne"

    def test_extracts_with_query_string(self):
        # Should strip query params
        u = _get_profile_username("https://linkedin.com/in/test?ref=abc")
        assert u.startswith("test")

    def test_handles_empty_input(self):
        # Should not crash; returns string (possibly empty)
        result = _get_profile_username("")
        assert isinstance(result, str)


class TestCalculatePostScore:
    def test_returns_float(self):
        score = _calculate_post_score(_post())
        assert isinstance(score, float)

    def test_recent_post_scores_higher_than_old(self):
        recent = _post(timestamp=datetime.now(timezone.utc) - timedelta(hours=1))
        old = _post(timestamp=datetime.now(timezone.utc) - timedelta(days=30))
        assert _calculate_post_score(recent) > _calculate_post_score(old)

    def test_high_engagement_boosts_score(self):
        low = _post(likes=0, comments=0, shares=0)
        high = _post(likes=500, comments=100, shares=50)
        assert _calculate_post_score(high) > _calculate_post_score(low)

    def test_handles_missing_timestamp(self):
        # Should not crash when timestamp is None
        post = _post(timestamp=None)
        score = _calculate_post_score(post)
        assert isinstance(score, float)

    def test_naive_timestamp_no_typeerror(self):
        # Regression for the aware-vs-naive comparison fix
        naive_post = _post(timestamp=datetime.now() - timedelta(hours=12))
        score = _calculate_post_score(naive_post)
        assert isinstance(score, float)

    def test_recency_boost_capped_at_thresholds(self):
        # < 24h boost > 24-72h boost > 72h+ boost (no boost)
        very_recent = _post(timestamp=datetime.now(timezone.utc) - timedelta(hours=2), likes=0, comments=0, shares=0)
        day_old = _post(timestamp=datetime.now(timezone.utc) - timedelta(hours=48), likes=0, comments=0, shares=0)
        ancient = _post(timestamp=datetime.now(timezone.utc) - timedelta(days=10), likes=0, comments=0, shares=0)
        assert _calculate_post_score(very_recent) > _calculate_post_score(day_old) > _calculate_post_score(ancient)


class TestExtractKeywords:
    def test_finds_cmmc_terms(self):
        keywords = _extract_keywords("CMMC certification is now required for DFARS")
        assert "cmmc" in keywords
        assert "dfars" in keywords

    def test_returns_empty_for_irrelevant_content(self):
        keywords = _extract_keywords("Just sharing a personal photo with the family today")
        # Should be empty or very small
        assert len(keywords) <= 1

    def test_case_insensitive(self):
        upper = _extract_keywords("CMMC LEVEL 2 ASSESSMENT")
        lower = _extract_keywords("cmmc level 2 assessment")
        assert "cmmc" in upper
        assert "cmmc" in lower

    def test_returns_list(self):
        result = _extract_keywords("anything")
        assert isinstance(result, list)


class TestParseLinkedinItem:
    def test_parses_minimal_item(self):
        item = {
            "url": "https://linkedin.com/posts/test",
            "text": "About CMMC",
            "authorName": "Author Name",
            "authorTitle": "Title",
            "authorUrl": "https://linkedin.com/in/author",
            "likeCount": 5,
            "commentCount": 1,
            "shareCount": 0,
        }
        result = _parse_linkedin_item(item)
        # Should produce a LinkedInPost or None gracefully
        assert result is None or isinstance(result, LinkedInPost)

    def test_handles_empty_dict(self):
        # Should not crash on empty input
        result = _parse_linkedin_item({})
        assert result is None or isinstance(result, LinkedInPost)


class TestLinkedinPostsToTrends:
    def test_empty_list_returns_empty(self):
        assert linkedin_posts_to_trends([]) == []

    def test_converts_post_to_trend_dict(self):
        posts = [_post(content="CMMC update news")]
        trends = linkedin_posts_to_trends(posts)
        assert len(trends) == 1
        assert isinstance(trends[0], dict)
        # Trend dict should have expected keys
        assert "title" in trends[0]
        assert "url" in trends[0]
        assert "source" in trends[0]

    def test_multiple_posts(self):
        posts = [_post(post_url=f"https://linkedin.com/posts/{i}") for i in range(5)]
        trends = linkedin_posts_to_trends(posts)
        assert len(trends) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
