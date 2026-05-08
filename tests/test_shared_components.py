#!/usr/bin/env python3
"""Tests for shared_components module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from shared_components import (
    build_footer,
    build_header,
    get_footer_styles,
    get_header_styles,
    get_nav_links,
    get_theme_script,
)


class TestGetNavLinks:
    def test_returns_html_string(self):
        nav = get_nav_links()
        assert isinstance(nav, str)
        assert "<a" in nav

    def test_includes_archive_link(self):
        nav = get_nav_links()
        assert "/archive" in nav.lower()

    def test_marks_active_page(self):
        nav = get_nav_links(active_page="archive")
        # Some "active" indicator should be present when active_page is set
        assert "active" in nav.lower() or 'aria-current="page"' in nav.lower()


class TestBuildHeader:
    def test_returns_html_string(self):
        header = build_header()
        assert isinstance(header, str)
        assert len(header) > 0

    def test_includes_branding(self):
        header = build_header()
        assert "CMMC" in header.upper()

    def test_no_dailytrending_leak(self):
        # Regression: brand identity check
        header = build_header()
        assert "dailytrending" not in header.lower()

    def test_accepts_date_str(self):
        header = build_header(date_str="May 8, 2026")
        # date_str may or may not be rendered in header; just verify no crash
        assert isinstance(header, str)


class TestBuildFooter:
    def test_returns_html_string(self):
        footer = build_footer()
        assert isinstance(footer, str)
        assert "<footer" in footer or "footer" in footer.lower()

    def test_no_dailytrending_leak(self):
        # Regression: was 'Built on Daily Trending' link in shared_components
        footer = build_footer()
        assert "dailytrending" not in footer.lower()
        assert "Daily Trending" not in footer

    def test_includes_attribution(self):
        footer = build_footer()
        # Should include either CMMC Watch branding or the product attribution
        assert "CMMC" in footer or "Brad Shannon" in footer

    def test_accepts_date_str(self):
        footer = build_footer(date_str="May 8, 2026")
        assert "May 8, 2026" in footer or isinstance(footer, str)


class TestStyleHelpers:
    def test_header_styles_is_string(self):
        css = get_header_styles()
        assert isinstance(css, str)
        assert len(css) > 0

    def test_footer_styles_is_string(self):
        css = get_footer_styles()
        assert isinstance(css, str)
        assert len(css) > 0

    def test_footer_styles_includes_archive_btn(self):
        # Regression: .archive-btn was used but had no CSS
        css = get_footer_styles()
        assert ".archive-btn" in css
        assert "min-height" in css  # WCAG touch target

    def test_theme_script_is_javascript(self):
        js = get_theme_script()
        assert isinstance(js, str)
        # Should reference theme/dark-mode toggling
        assert "theme" in js.lower() or "dark" in js.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
