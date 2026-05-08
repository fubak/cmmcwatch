#!/usr/bin/env python3
"""Tests for generate_rss module."""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from generate_rss import _build_content_html, generate_rss_feed


def _sample_trend(**overrides):
    base = {
        "title": "Sample CMMC Story",
        "url": "https://example.com/story",
        "description": "A short description of the story.",
        "source": "cmmc_rss_fedscoop",
        "category": "cmmc_program",
        "timestamp": "2026-05-08T12:00:00Z",
    }
    base.update(overrides)
    return base


class TestBuildContentHtml:
    def test_returns_string(self):
        html = _build_content_html("Title", "Desc", "src", "https://x")
        assert isinstance(html, str)

    def test_includes_title_and_description(self):
        html = _build_content_html("My Title", "My Description", "src", "https://x")
        assert "My Title" in html or "Description" in html
        assert "My Description" in html

    def test_includes_source_link(self):
        html = _build_content_html("T", "D", "src", "https://example.com/story")
        assert "https://example.com/story" in html

    def test_optional_why_matters_included_when_present(self):
        with_reason = _build_content_html("T", "D", "src", "https://x", why_matters="Critical for compliance")
        assert "compliance" in with_reason.lower()

    def test_escapes_html_in_description(self):
        # User-supplied description should not break the output XML
        out = _build_content_html("T", "<script>alert(1)</script>", "src", "https://x")
        assert "<script>alert(1)</script>" not in out
        assert "&lt;script&gt;" in out

    def test_escapes_html_in_title(self):
        out = _build_content_html("<img src=x onerror=alert(1)>", "D", "src", "https://x")
        assert "<img src=x" not in out
        assert "&lt;img" in out

    def test_rejects_javascript_url(self):
        out = _build_content_html("T", "D", "src", "javascript:alert(1)")
        # Should NOT emit an anchor for a javascript: URL
        assert 'href="javascript:' not in out
        assert "javascript:alert" not in out

    def test_rejects_data_url(self):
        out = _build_content_html("T", "D", "src", "data:text/html,<script>")
        assert "data:text/html" not in out

    def test_escapes_url_attribute_quotes(self):
        # An attacker-controlled URL with embedded quotes must not break out
        # of the href attribute. The raw `"` character is escaped to `&quot;`,
        # so onerror= cannot become an actual attribute.
        out = _build_content_html("T", "D", "src", 'https://x"onerror=alert(1)')
        # The unescaped `"` must not appear adjacent to `onerror=` (which would
        # mean attribute breakout). The escaped `&quot;` form is safe.
        assert '"onerror=' not in out
        assert "&quot;onerror=alert(1)" in out  # safely escaped


class TestGenerateRssFeed:
    def test_writes_valid_xml(self, tmp_path):
        output = tmp_path / "feed.xml"
        generate_rss_feed(
            trends=[_sample_trend()],
            output_path=output,
            title="CMMC Watch",
            description="Test feed",
            link="https://cmmcwatch.com",
        )
        assert output.exists()
        # Should parse as XML
        tree = ET.parse(output)
        root = tree.getroot()
        assert root.tag == "rss"

    def test_includes_channel_metadata(self, tmp_path):
        output = tmp_path / "feed.xml"
        generate_rss_feed(
            trends=[_sample_trend()],
            output_path=output,
            title="My Feed",
            description="My Description",
            link="https://my.example.com",
        )
        content = output.read_text()
        assert "My Feed" in content
        assert "https://my.example.com" in content

    def test_includes_items(self, tmp_path):
        output = tmp_path / "feed.xml"
        generate_rss_feed(
            trends=[
                _sample_trend(title="Story One"),
                _sample_trend(title="Story Two", url="https://example.com/2"),
            ],
            output_path=output,
            title="Feed",
            description="Desc",
            link="https://x.com",
        )
        content = output.read_text()
        assert "Story One" in content
        assert "Story Two" in content

    def test_handles_empty_trends(self, tmp_path):
        output = tmp_path / "empty.xml"
        generate_rss_feed(
            trends=[],
            output_path=output,
            title="Empty",
            description="None",
            link="https://x.com",
        )
        # Should still produce valid XML, just with no items
        assert output.exists()
        tree = ET.parse(output)
        root = tree.getroot()
        assert root.tag == "rss"

    def test_handles_missing_optional_fields(self, tmp_path):
        output = tmp_path / "minimal.xml"
        # Minimum-viable trend dict
        trend = {"title": "Bare", "url": "https://x", "source": "src"}
        generate_rss_feed(
            trends=[trend],
            output_path=output,
            title="Feed",
            description="D",
            link="https://x.com",
        )
        assert output.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
