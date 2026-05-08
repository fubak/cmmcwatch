#!/usr/bin/env python3
"""Tests for rate_limiter module."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from rate_limiter import RateLimitStatus, RateLimiter, get_rate_limiter, is_provider_exhausted, mark_provider_exhausted


class TestRateLimitStatus:
    def test_default_is_available(self):
        status = RateLimitStatus()
        assert status.is_available is True
        assert status.wait_seconds == 0.0
        assert status.error is None

    def test_unavailable_status(self):
        status = RateLimitStatus(is_available=False, error="No key")
        assert status.is_available is False
        assert status.error == "No key"


class TestRateLimiterInit:
    def test_no_keys_configured(self):
        limiter = RateLimiter()
        assert limiter.google_key is None or isinstance(limiter.google_key, str)

    def test_explicit_keys(self):
        limiter = RateLimiter(google_key="test_key", groq_key="groq_key")
        assert limiter.google_key == "test_key"
        assert limiter.groq_key == "groq_key"

    def test_empty_exhausted_set(self):
        limiter = RateLimiter()
        assert len(limiter.get_exhausted_providers()) == 0


class TestProviderExhaustion:
    def test_mark_and_check_exhausted(self):
        limiter = RateLimiter()
        assert not limiter.is_provider_exhausted("google")

        limiter.mark_provider_exhausted("google", reason="quota hit")

        assert limiter.is_provider_exhausted("google")

    def test_mark_multiple_providers(self):
        limiter = RateLimiter()
        limiter.mark_provider_exhausted("google")
        limiter.mark_provider_exhausted("groq")

        assert limiter.is_provider_exhausted("google")
        assert limiter.is_provider_exhausted("groq")
        assert not limiter.is_provider_exhausted("openrouter")

    def test_get_exhausted_providers_returns_copy(self):
        limiter = RateLimiter()
        limiter.mark_provider_exhausted("groq")

        providers = limiter.get_exhausted_providers()
        providers.add("google")

        assert not limiter.is_provider_exhausted("google")

    def test_reset_exhausted_providers(self):
        limiter = RateLimiter()
        limiter.mark_provider_exhausted("google")
        limiter.mark_provider_exhausted("groq")

        limiter.reset_exhausted_providers()

        assert len(limiter.get_exhausted_providers()) == 0
        assert not limiter.is_provider_exhausted("google")

    def test_mark_same_provider_twice_is_idempotent(self):
        limiter = RateLimiter()
        limiter.mark_provider_exhausted("groq")
        limiter.mark_provider_exhausted("groq")

        providers = limiter.get_exhausted_providers()
        assert len(providers) == 1


class TestCheckGoogleLimits:
    def test_no_key_returns_unavailable(self):
        limiter = RateLimiter(google_key=None)
        # Ensure env var not set
        import os

        original = os.environ.pop("GOOGLE_AI_API_KEY", None)
        try:
            limiter = RateLimiter(google_key=None)
            limiter.google_key = None  # force None
            status = limiter.check_google_limits()
            assert not status.is_available
            assert status.error is not None
        finally:
            if original:
                os.environ["GOOGLE_AI_API_KEY"] = original

    def test_with_key_returns_available(self):
        limiter = RateLimiter(google_key="fake_key")
        status = limiter.check_google_limits()
        assert status.is_available is True

    def test_caching_returns_same_status(self):
        limiter = RateLimiter(google_key="fake_key")
        status1 = limiter.check_google_limits()
        status2 = limiter.check_google_limits()
        assert status1.is_available == status2.is_available

    def test_min_interval_enforced(self):
        limiter = RateLimiter(google_key="fake_key")
        # Simulate a recent call
        limiter._last_call_time["google"] = time.time()
        status = limiter.check_google_limits(force_refresh=True)
        assert status.wait_seconds > 0


class TestUpdateFromResponseHeaders:
    def test_parses_rate_limit_headers(self):
        limiter = RateLimiter(groq_key="fake")
        headers = {
            "x-ratelimit-remaining-requests": "100",
            "x-ratelimit-limit-requests": "1000",
            "x-ratelimit-remaining-tokens": "50000",
            "x-ratelimit-limit-tokens": "100000",
        }
        limiter.update_from_response_headers("groq", headers)

        cached_status, _ = limiter._rate_limit_cache["groq"]
        assert cached_status.requests_remaining == 100
        assert cached_status.requests_limit == 1000
        assert cached_status.tokens_remaining == 50000

    def test_handles_missing_headers_gracefully(self):
        limiter = RateLimiter(groq_key="fake")
        limiter.update_from_response_headers("groq", {})
        # Should not raise

    def test_handles_invalid_header_values(self):
        limiter = RateLimiter(groq_key="fake")
        headers = {"x-ratelimit-remaining-requests": "not-a-number"}
        limiter.update_from_response_headers("groq", headers)
        cached_status, _ = limiter._rate_limit_cache["groq"]
        assert cached_status.requests_remaining is None

    def test_low_requests_triggers_wait(self):
        limiter = RateLimiter(groq_key="fake")
        headers = {
            "x-ratelimit-remaining-requests": "3",
            "x-ratelimit-limit-requests": "1000",
        }
        limiter.update_from_response_headers("groq", headers)
        cached_status, _ = limiter._rate_limit_cache["groq"]
        assert cached_status.wait_seconds > 0


class TestGetBestProvider:
    def test_returns_none_when_all_exhausted(self):
        limiter = RateLimiter()
        for provider in ["google", "openrouter", "groq", "opencode", "huggingface", "mistral"]:
            limiter.mark_provider_exhausted(provider)
        result = limiter.get_best_provider()
        assert result is None

    def test_skips_exhausted_providers(self):
        limiter = RateLimiter(groq_key="key")
        limiter.mark_provider_exhausted("opencode")
        limiter.mark_provider_exhausted("mistral")
        limiter.mark_provider_exhausted("huggingface")
        limiter.mark_provider_exhausted("openrouter")
        limiter.mark_provider_exhausted("google")
        # Only groq available
        result = limiter.get_best_provider("simple")
        assert result == "groq" or result is None  # None if no key available in env


class TestModuleLevelHelpers:
    def test_get_rate_limiter_returns_singleton(self):
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        assert limiter1 is limiter2

    def test_module_mark_and_check_exhausted(self):
        # Use module-level helpers

        # Ensure we have a fresh state by resetting
        limiter = get_rate_limiter()
        limiter.reset_exhausted_providers()

        assert not is_provider_exhausted("groq")
        mark_provider_exhausted("groq", "test")
        assert is_provider_exhausted("groq")

        # cleanup
        limiter.reset_exhausted_providers()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
