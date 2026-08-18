#!/usr/bin/env python3
"""Tests for html_utils — URL, color, JSON, and article-HTML sanitizers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from html_utils import (
    css_safe_image_url,
    is_http_url,
    is_public_http_url,
    is_safe_hex_color,
    json_for_script,
    sanitize_article_html,
    sanitize_hex_color,
    sanitize_http_url,
)


class TestHttpUrl:
    def test_accepts_https(self):
        assert is_http_url("https://fedscoop.com/story")
        assert sanitize_http_url("https://fedscoop.com/story") == "https://fedscoop.com/story"

    def test_rejects_javascript(self):
        assert not is_http_url("javascript:alert(1)")
        assert sanitize_http_url("javascript:alert(1)") is None

    def test_rejects_data_and_userinfo(self):
        assert sanitize_http_url("data:text/html,x") is None
        assert sanitize_http_url("https://user:pass@evil.test/") is None

    def test_rejects_empty(self):
        assert sanitize_http_url("") is None
        assert sanitize_http_url(None) is None


class TestPublicHttpUrl:
    def test_rejects_loopback_and_metadata(self):
        assert not is_public_http_url("http://127.0.0.1/latest")
        assert not is_public_http_url("http://169.254.169.254/latest/meta-data")
        assert not is_public_http_url("http://localhost/admin")

    def test_accepts_public_host(self):
        assert is_public_http_url("https://csrc.nist.gov/news")


class TestHexColor:
    def test_valid_and_invalid(self):
        assert is_safe_hex_color("#0a0a0a")
        assert is_safe_hex_color("#fff")
        assert not is_safe_hex_color("red")
        assert not is_safe_hex_color("#zzzzzz")
        assert sanitize_hex_color("</style>", "#111111") == "#111111"


class TestJsonForScript:
    def test_escapes_script_breakout(self):
        payload = json_for_script({"mood": "</script><script>alert(1)</script>"})
        assert "<" not in payload
        assert "\\u003c" in payload


class TestCssSafeImageUrl:
    def test_rejects_quote_breakout(self):
        assert css_safe_image_url("https://img.test/x.jpg") == "https://img.test/x.jpg"
        assert css_safe_image_url("https://img.test/x.jpg')</style>") is None


class TestSanitizeArticleHtml:
    def test_strips_script_and_keeps_headings(self):
        raw = "<h2>The Lead</h2><p>Hello</p><script>alert(1)</script>"
        cleaned = sanitize_article_html(raw)
        assert "<h2>The Lead</h2>" in cleaned
        assert "<p>Hello</p>" in cleaned
        assert "script" not in cleaned.lower()

    def test_drops_event_handlers_and_bad_hrefs(self):
        raw = '<p onclick="x()">x</p><a href="javascript:alert(1)">go</a>'
        cleaned = sanitize_article_html(raw)
        assert "onclick" not in cleaned
        assert "javascript:" not in cleaned
        assert "<a>" in cleaned or "<a >" in cleaned or cleaned.startswith("<p>")
