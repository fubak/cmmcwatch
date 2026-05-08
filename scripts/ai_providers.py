#!/usr/bin/env python3
"""
Unified AI provider HTTP layer.

Single source of truth for chat-completion calls to OpenRouter, Groq,
OpenCode, Mistral, and Hugging Face. Handles rate-limit pre-checks,
429/503 retry-with-backoff, response-header-based rate-limit updates,
and consistent logging across both editorial and design generators.

Each provider returns either the generated text on success or None.
None is returned for: missing key, rate-limit-unavailable, all-models-failed,
network errors after retries.
"""

import logging
import os
import time
from typing import Optional

import requests

try:
    from rate_limiter import check_before_call, get_rate_limiter
except ImportError:
    from scripts.rate_limiter import check_before_call, get_rate_limiter

logger = logging.getLogger("pipeline")

MAX_RETRY_WAIT = 10  # seconds — cap for Retry-After backoff


# Per-provider config: endpoint, models, headers builder, env var.
# OpenAI-compatible providers (OpenRouter/Groq/OpenCode/Mistral) all use
# {messages, max_tokens, temperature} in and {choices[0].message.content} out.
_OPENAI_COMPAT_PROVIDERS = {
    "openrouter": {
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "models": [
            "meta-llama/llama-3.3-70b-instruct:free",
            "deepseek/deepseek-r1-0528:free",
            "google/gemma-3-27b-it:free",
        ],
        "key_env": "OPENROUTER_API_KEY",
        "extra_headers": {
            "HTTP-Referer": "https://cmmcwatch.com",
            "X-Title": "CMMC Watch",
        },
        "timeout": 60,
    },
    "groq": {
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "models": ["llama-3.3-70b-versatile"],
        "key_env": "GROQ_API_KEY",
        "extra_headers": {},
        "timeout": 45,
    },
    "opencode": {
        "endpoint": "https://opencode.ai/zen/v1/chat/completions",
        "models": ["glm-4.7-free", "minimax-m2.1-free"],
        "key_env": "OPENCODE_API_KEY",
        "extra_headers": {},
        "timeout": 60,
    },
    "mistral": {
        "endpoint": "https://api.mistral.ai/v1/chat/completions",
        "models": ["mistral-small-latest", "open-mistral-7b"],
        "key_env": "MISTRAL_API_KEY",
        "extra_headers": {},
        "timeout": 60,
    },
}


def _wait_for_rate_limit(provider: str) -> bool:
    """Run pre-call rate-limit check. Returns True if the call should proceed."""
    status = check_before_call(provider)
    if not status.is_available:
        logger.warning(f"  {provider} not available: {status.error}")
        return False
    if status.wait_seconds > 0:
        logger.info(f"  Waiting {status.wait_seconds:.1f}s for {provider} rate limit...")
        time.sleep(status.wait_seconds)
    return True


def _retry_after_seconds(headers, default: float = 10.0) -> float:
    """Parse Retry-After header into a bounded sleep duration."""
    raw = headers.get("Retry-After", str(default))
    try:
        return min(float(raw), MAX_RETRY_WAIT)
    except (ValueError, TypeError):
        return MAX_RETRY_WAIT


def call_openai_compatible(
    provider: str,
    prompt: str,
    max_tokens: int = 1000,
    max_retries: int = 1,
    session: Optional[requests.Session] = None,
) -> Optional[str]:
    """
    Call any OpenAI-compatible provider (openrouter, groq, opencode, mistral).

    Iterates the provider's free model list, retries on 429 with Retry-After
    backoff, returns the first successful completion text or None.
    """
    config = _OPENAI_COMPAT_PROVIDERS.get(provider)
    if config is None:
        raise ValueError(f"Unknown provider: {provider}")

    api_key = os.getenv(config["key_env"])
    if not api_key:
        return None

    if not _wait_for_rate_limit(provider):
        return None

    rate_limiter = get_rate_limiter()
    sess = session or requests
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        **config["extra_headers"],
    }

    for model in config["models"]:
        for attempt in range(max_retries):
            try:
                logger.info(f"  Trying {provider} {model} (attempt {attempt + 1}/{max_retries})")
                response = sess.post(
                    config["endpoint"],
                    headers=headers,
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": 0.7,
                    },
                    timeout=config["timeout"],
                )
                response.raise_for_status()
                rate_limiter.update_from_response_headers(provider, dict(response.headers))

                result = response.json().get("choices", [{}])[0].get("message", {}).get("content")
                if result:
                    logger.info(f"  {provider} success with {model}")
                    return result
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    wait = _retry_after_seconds(response.headers)
                    logger.info(
                        f"  {provider} {model} rate limited, waiting {wait}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait)
                    continue
                logger.warning(f"  {provider} {model} failed: {e}")
                break  # try next model
            except requests.exceptions.RequestException as e:
                logger.warning(f"  {provider} {model} failed: {e}")
                break  # try next model

    logger.warning(f"  All {provider} models failed")
    return None


def call_huggingface(
    prompt: str,
    max_tokens: int = 1000,
    max_retries: int = 1,
    session: Optional[requests.Session] = None,
) -> Optional[str]:
    """
    Call Hugging Face Inference API. Has divergent request/response shape
    (uses `inputs`/`parameters` and returns a list with `generated_text`),
    plus 503 handling for model-loading state.
    """
    api_key = os.getenv("HUGGINGFACE_API_KEY")
    if not api_key:
        return None

    if not _wait_for_rate_limit("huggingface"):
        return None

    rate_limiter = get_rate_limiter()
    sess = session or requests
    free_models = [
        "mistralai/Mistral-7B-Instruct-v0.3",
        "Qwen/Qwen2.5-7B-Instruct",
        "microsoft/Phi-3-mini-4k-instruct",
    ]

    for model in free_models:
        for attempt in range(max_retries):
            try:
                logger.info(f"  Trying Hugging Face {model} (attempt {attempt + 1}/{max_retries})")
                response = sess.post(
                    f"https://api-inference.huggingface.co/models/{model}",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "inputs": prompt,
                        "parameters": {
                            "max_new_tokens": max_tokens,
                            "temperature": 0.7,
                            "return_full_text": False,
                        },
                    },
                    timeout=60,
                )
                response.raise_for_status()
                rate_limiter.update_from_response_headers("huggingface", dict(response.headers))

                result = response.json()
                if isinstance(result, list) and result:
                    text = result[0].get("generated_text", "")
                    if text:
                        logger.info(f"  Hugging Face success with {model}")
                        return text
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    wait = _retry_after_seconds(response.headers)
                    logger.info(f"  Hugging Face {model} rate limited, waiting {wait}s")
                    time.sleep(wait)
                    continue
                if response.status_code == 503:
                    logger.info(f"  Hugging Face {model} loading, waiting {MAX_RETRY_WAIT}s...")
                    time.sleep(MAX_RETRY_WAIT)
                    continue
                logger.warning(f"  Hugging Face {model} failed: {e}")
                break  # try next model
            except requests.exceptions.RequestException as e:
                logger.warning(f"  Hugging Face {model} failed: {e}")
                break  # try next model

    logger.warning("  All Hugging Face models failed")
    return None
