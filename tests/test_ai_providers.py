#!/usr/bin/env python3
"""Tests for ai_providers shared HTTP layer."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
import requests
from ai_providers import (
    _OPENAI_COMPAT_PROVIDERS,
    _retry_after_seconds,
    call_google_ai,
    call_huggingface,
    call_ollama,
    call_openai_compatible,
)


def _mock_response(status=200, headers=None, json_body=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.headers = headers or {}
    resp.json = MagicMock(return_value=json_body or {})
    if status >= 400:
        err = requests.exceptions.HTTPError(response=resp)
        err.response = resp
        resp.raise_for_status = MagicMock(side_effect=err)
    else:
        resp.raise_for_status = MagicMock()
    return resp


class TestRetryAfter:
    def test_default_when_missing(self):
        assert _retry_after_seconds({}, default=5.0) == 5.0

    def test_parses_numeric(self):
        assert _retry_after_seconds({"Retry-After": "3"}) == 3.0

    def test_capped_to_max(self):
        # MAX_RETRY_WAIT is 10
        assert _retry_after_seconds({"Retry-After": "9999"}) == 10

    def test_invalid_value_uses_max(self):
        assert _retry_after_seconds({"Retry-After": "abc"}) == 10


class TestProviderConfig:
    def test_all_expected_providers_present(self):
        assert set(_OPENAI_COMPAT_PROVIDERS) == {"openrouter", "groq", "opencode", "mistral"}

    def test_each_provider_has_required_fields(self):
        for name, config in _OPENAI_COMPAT_PROVIDERS.items():
            assert "endpoint" in config, f"{name} missing endpoint"
            assert "models" in config and config["models"], f"{name} missing models"
            assert "key_env" in config, f"{name} missing key_env"
            assert "extra_headers" in config, f"{name} missing extra_headers"
            assert "timeout" in config, f"{name} missing timeout"

    def test_openrouter_has_branded_headers(self):
        headers = _OPENAI_COMPAT_PROVIDERS["openrouter"]["extra_headers"]
        assert "cmmcwatch.com" in headers.get("HTTP-Referer", "")
        assert "CMMC Watch" in headers.get("X-Title", "")
        # Regression: no DailyTrending leak
        assert "dailytrending" not in str(headers).lower()


class TestCallOpenAICompatible:
    def test_returns_none_when_no_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        result = call_openai_compatible("groq", "test prompt")
        assert result is None

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            call_openai_compatible("nonexistent", "prompt")

    def test_successful_call_returns_content(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "fake")
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(
            json_body={"choices": [{"message": {"content": "Hello world"}}]}
        )
        with patch("ai_providers._wait_for_rate_limit", return_value=True):
            result = call_openai_compatible("groq", "test", session=mock_session)
        assert result == "Hello world"

    def test_returns_none_when_rate_limit_unavailable(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "fake")
        with patch("ai_providers._wait_for_rate_limit", return_value=False):
            result = call_openai_compatible("groq", "test")
        assert result is None

    def test_429_triggers_retry(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "fake")
        mock_session = MagicMock()
        mock_session.post.side_effect = [
            _mock_response(status=429, headers={"Retry-After": "0"}),
            _mock_response(json_body={"choices": [{"message": {"content": "ok"}}]}),
        ]
        with patch("ai_providers._wait_for_rate_limit", return_value=True), patch("ai_providers.time.sleep"):
            result = call_openai_compatible("groq", "test", max_retries=2, session=mock_session)
        assert result == "ok"

    def test_non_429_http_error_breaks_to_next_model(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
        mock_session = MagicMock()
        # First model fails with 500; second succeeds
        mock_session.post.side_effect = [
            _mock_response(status=500),
            _mock_response(json_body={"choices": [{"message": {"content": "fallback"}}]}),
            _mock_response(json_body={"choices": [{"message": {"content": "third"}}]}),
        ]
        with patch("ai_providers._wait_for_rate_limit", return_value=True):
            result = call_openai_compatible("openrouter", "test", session=mock_session)
        assert result == "fallback"

    def test_network_error_breaks_to_next_model(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
        mock_session = MagicMock()
        mock_session.post.side_effect = [
            requests.exceptions.ConnectionError("network down"),
            _mock_response(json_body={"choices": [{"message": {"content": "recovered"}}]}),
            _mock_response(json_body={"choices": [{"message": {"content": "third"}}]}),
        ]
        with patch("ai_providers._wait_for_rate_limit", return_value=True):
            result = call_openai_compatible("openrouter", "test", session=mock_session)
        assert result == "recovered"

    def test_all_models_fail_returns_none(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(status=500)
        with patch("ai_providers._wait_for_rate_limit", return_value=True):
            result = call_openai_compatible("openrouter", "test", session=mock_session)
        assert result is None


class TestCallHuggingface:
    def test_returns_none_when_no_key(self, monkeypatch):
        monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
        assert call_huggingface("test") is None

    def test_successful_call_extracts_generated_text(self, monkeypatch):
        monkeypatch.setenv("HUGGINGFACE_API_KEY", "fake")
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(json_body=[{"generated_text": "hf output"}])
        with patch("ai_providers._wait_for_rate_limit", return_value=True):
            result = call_huggingface("test", session=mock_session)
        assert result == "hf output"

    def test_503_loading_triggers_retry(self, monkeypatch):
        monkeypatch.setenv("HUGGINGFACE_API_KEY", "fake")
        mock_session = MagicMock()
        mock_session.post.side_effect = [
            _mock_response(status=503),
            _mock_response(json_body=[{"generated_text": "loaded"}]),
        ]
        with patch("ai_providers._wait_for_rate_limit", return_value=True), patch("ai_providers.time.sleep"):
            result = call_huggingface("test", max_retries=2, session=mock_session)
        assert result == "loaded"

    def test_empty_response_falls_through(self, monkeypatch):
        monkeypatch.setenv("HUGGINGFACE_API_KEY", "fake")
        mock_session = MagicMock()
        # Empty list response from first model, valid from second
        mock_session.post.side_effect = [
            _mock_response(json_body=[]),
            _mock_response(json_body=[{"generated_text": "second"}]),
            _mock_response(json_body=[{"generated_text": "third"}]),
        ]
        with patch("ai_providers._wait_for_rate_limit", return_value=True):
            result = call_huggingface("test", session=mock_session)
        # Empty list breaks current attempt, next iteration of inner loop tries
        # but max_retries=1, so it moves to next model
        assert result == "second"


class TestCallGoogleAi:
    def test_returns_none_when_no_key(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
        assert call_google_ai("test") is None

    def test_explicit_key_overrides_env(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(
            json_body={"candidates": [{"content": {"parts": [{"text": "Hello"}]}}]}
        )
        with patch("ai_providers._wait_for_rate_limit", return_value=True):
            result = call_google_ai("test", session=mock_session, api_key="explicit-key")
        assert result == "Hello"

    def test_successful_call_extracts_text(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_AI_API_KEY", "fake")
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(
            json_body={"candidates": [{"content": {"parts": [{"text": "gemini output"}]}}]}
        )
        with patch("ai_providers._wait_for_rate_limit", return_value=True):
            result = call_google_ai("test", session=mock_session)
        assert result == "gemini output"

    def test_quota_429_marks_provider_exhausted(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_AI_API_KEY", "fake")
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(
            status=429,
            json_body={"error": {"message": "Quota exceeded for daily limit"}},
        )
        with (
            patch("ai_providers._wait_for_rate_limit", return_value=True),
            patch("ai_providers.mark_provider_exhausted") as mock_mark,
        ):
            result = call_google_ai("test", session=mock_session)
        assert result is None
        mock_mark.assert_called_once()
        assert mock_mark.call_args[0][0] == "google"

    def test_transient_429_retries(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_AI_API_KEY", "fake")
        mock_session = MagicMock()
        mock_session.post.side_effect = [
            _mock_response(status=429, headers={"Retry-After": "0"}, json_body={"error": "transient"}),
            _mock_response(json_body={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}),
        ]
        with patch("ai_providers._wait_for_rate_limit", return_value=True), patch("ai_providers.time.sleep"):
            result = call_google_ai("test", max_retries=2, session=mock_session)
        assert result == "ok"

    def test_empty_candidates_returns_none(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_AI_API_KEY", "fake")
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(json_body={"candidates": []})
        with patch("ai_providers._wait_for_rate_limit", return_value=True):
            result = call_google_ai("test", session=mock_session)
        assert result is None


class TestCallOllama:
    def test_successful_call_returns_text(self):
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(json_body={"response": "ollama output"})
        result = call_ollama("test", session=mock_session)
        assert result == "ollama output"

    def test_uses_custom_url(self):
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(json_body={"response": "ok"})
        call_ollama("test", session=mock_session, ollama_url="http://my-ollama:11434")
        url = mock_session.post.call_args[0][0]
        assert url.startswith("http://my-ollama:11434/api/generate")

    def test_connection_error_returns_none(self):
        mock_session = MagicMock()
        mock_session.post.side_effect = requests.exceptions.ConnectionError("refused")
        result = call_ollama("test", session=mock_session)
        assert result is None

    def test_empty_response_returns_none(self):
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(json_body={"response": ""})
        result = call_ollama("test", session=mock_session)
        assert result is None

    def test_passes_max_tokens_as_num_predict(self):
        mock_session = MagicMock()
        mock_session.post.return_value = _mock_response(json_body={"response": "x"})
        call_ollama("test", max_tokens=500, session=mock_session)
        body = mock_session.post.call_args.kwargs["json"]
        assert body["options"]["num_predict"] == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
