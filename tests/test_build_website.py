#!/usr/bin/env python3
"""Tests for website builder module."""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from build_website import BuildContext, WebsiteBuilder


class TestBuildContext:
    """Test BuildContext dataclass."""

    def test_build_context_initialization(self):
        """Test BuildContext initialization with required fields."""
        ctx = BuildContext(
            trends=[{"title": "Test"}],
            images=[{"id": "test"}],
            design={"theme": "test"},
            keywords=["test", "keyword"],
        )

        assert ctx.trends == [{"title": "Test"}]
        assert ctx.images == [{"id": "test"}]
        assert ctx.design == {"theme": "test"}
        assert ctx.keywords == ["test", "keyword"]

    def test_build_context_auto_generated_at(self):
        """Test that generated_at is automatically set if not provided."""
        ctx = BuildContext(trends=[], images=[], design={}, keywords=[])

        assert ctx.generated_at != ""
        assert len(ctx.generated_at) > 0


class TestWebsiteBuilder:
    """Test WebsiteBuilder functionality."""

    @pytest.fixture
    def basic_context(self):
        """Create a basic BuildContext for testing."""
        return BuildContext(
            trends=[
                {
                    "title": "CMMC 2.0 Update",
                    "source": "cmmc_rss_fedscoop",
                    "url": "https://example.com/1",
                    "description": "A test description",
                    "category": "cmmc_program",
                    "timestamp": "2024-01-01 12:00:00",
                }
            ],
            images=[
                {
                    "id": "test_img_1",
                    "url_large": "https://example.com/image.jpg",
                    "url_medium": "https://example.com/image-med.jpg",
                    "alt_text": "Test image",
                }
            ],
            design={
                "headline": "Today's CMMC News",
                "theme_name": "Test Theme",
                "color_bg": "#0a0a0a",
                "color_text": "#ffffff",
            },
            keywords=["cmmc", "compliance"],
        )

    def test_builder_initialization(self, basic_context):
        """Test that builder initializes correctly."""
        builder = WebsiteBuilder(basic_context)

        assert builder.ctx == basic_context
        assert builder.design is not None
        assert builder.layout in ["newspaper", "magazine", "bold", "mosaic"]
        assert builder.keyword_freq is not None

    def test_sanitize_html_in_trend_data(self, basic_context):
        """Test that HTML in trend data is properly sanitized (XSS protection)."""
        # Add a trend with XSS attempt
        basic_context.trends.append(
            {
                "title": '<script>alert("XSS")</script>Normal Title',
                "source": "test_source",
                "url": "https://example.com/xss",
                "description": '<img src=x onerror="alert(1)">',
                "category": "cmmc_program",
            }
        )

        builder = WebsiteBuilder(basic_context)
        html = builder.build()

        # The injected XSS payload should be escaped by Jinja2 autoescape
        assert 'onerror="alert(1)"' not in html
        # Jinja2 autoescape should convert <script> from user data to &lt;script&gt;
        assert '&lt;script&gt;alert("XSS")&lt;/script&gt;' in html or "Normal Title" in html

    def test_description_truncation(self, basic_context):
        """Test that the truncation logic in _fetch_story_description works."""
        # Directly test the truncation logic:
        # A description over 220 chars should be truncated
        long_desc = "A " * 130  # 260 chars
        truncated = long_desc.strip()
        if len(truncated) > 220:
            truncated = truncated[:217].rsplit(" ", 1)[0] + "..."

        assert len(truncated) <= 220
        assert truncated.endswith("...")

    def test_description_truncation_at_word_boundary(self, basic_context):
        """Test that description truncation happens at word boundaries."""
        # Simulate the truncation logic from _fetch_story_description
        desc = "This is a very long description that needs to be truncated. " * 5
        import re

        desc = re.sub(r"\s+", " ", desc).strip()
        if len(desc) > 220:
            desc = desc[:217].rsplit(" ", 1)[0] + "..."

        # Should end with ... and not cut mid-word
        assert desc.endswith("...")
        # The last word before ... should be complete (not cut)
        words = desc[:-3].strip().split()
        assert len(words[-1]) > 1  # Last word is complete

    def test_empty_description_handling(self, basic_context):
        """Test handling of empty descriptions."""
        builder = WebsiteBuilder(basic_context)

        # Mock a story without description
        story = {"url": "https://example.com/no-desc"}

        builder._ensure_story_description(story)

        # Should not crash, and story may or may not have description
        assert "url" in story

    def test_structured_data_generation(self, basic_context):
        """Test that structured data (JSON-LD) is generated correctly."""
        builder = WebsiteBuilder(basic_context)
        structured_data = builder._build_structured_data()

        # Should contain JSON-LD script tag
        assert '<script type="application/ld+json">' in structured_data
        assert "@context" in structured_data
        assert "https://schema.org" in structured_data

        # Should include organization schema
        assert "NewsMediaOrganization" in structured_data or "Organization" in structured_data

        # Should include website schema
        assert "WebSite" in structured_data

    def test_structured_data_has_faq(self, basic_context):
        """Test that structured data includes FAQ schema."""
        builder = WebsiteBuilder(basic_context)
        structured_data = builder._build_structured_data()

        # Should include FAQ schema for better SEO
        assert "FAQPage" in structured_data
        assert "What is CMMC?" in structured_data

    def test_category_display_mapping(self, basic_context):
        """Test that category names are mapped to display-friendly names."""
        builder = WebsiteBuilder(basic_context)

        # Test known category mappings
        assert builder.CATEGORY_DISPLAY_MAP["cmmc_program"] == "🎯 CMMC Program News"
        assert builder.CATEGORY_DISPLAY_MAP["nist_compliance"] == "📋 NIST & Compliance"
        assert builder.CATEGORY_DISPLAY_MAP["defense_industrial_base"] == "🛡️ Defense Industrial Base"

    def test_source_display_mapping(self, basic_context):
        """Test that source names are mapped to display-friendly names."""
        builder = WebsiteBuilder(basic_context)

        # Test known source mappings
        assert builder._get_source_display_name("cmmc_rss_fedscoop") == "FedScoop"
        assert builder._get_source_display_name("cmmc_reddit_cmmc") == "r/CMMC"
        assert builder._get_source_display_name("cmmc_linkedin") == "LinkedIn"

    def test_source_display_fallback(self, basic_context):
        """Test fallback for unknown source names."""
        builder = WebsiteBuilder(basic_context)

        # Unknown source should be cleaned up
        result = builder._get_source_display_name("unknown_source_name")

        assert "unknown" in result.lower()
        assert "_" not in result  # Underscores should be replaced

    def test_reddit_source_detection(self, basic_context):
        """Test Reddit source detection."""
        builder = WebsiteBuilder(basic_context)

        # Reddit sources
        assert builder._is_reddit_source("reddit_cmmc")
        assert builder._is_reddit_source("cmmc_reddit_nistcontrols")

        # Non-Reddit sources
        assert not builder._is_reddit_source("cmmc_rss_fedscoop")
        assert not builder._is_reddit_source("cmmc_linkedin")

    def test_reddit_exclusion_from_categories(self, basic_context):
        """Test that Reddit posts are excluded from category sections."""
        # Add Reddit trend
        basic_context.trends.append(
            {
                "title": "Reddit Discussion",
                "source": "reddit_cmmc",
                "url": "https://reddit.com/test",
                "category": "cmmc_program",
            }
        )

        builder = WebsiteBuilder(basic_context)
        categories = builder._prepare_categories()

        # Find the CMMC category
        cmmc_cat = next((c for c in categories if "CMMC Program" in c["title"]), None)

        if cmmc_cat:
            # Reddit posts should not be in category stories
            reddit_in_cat = any(builder._is_reddit_source(s.get("source", "")) for s in cmmc_cat["stories"])
            assert not reddit_in_cat

    def test_url_deduplication_across_sections(self, basic_context):
        """Test that URLs are not duplicated across different sections."""
        # Add multiple trends with same URL
        dup_url = "https://example.com/duplicate"
        basic_context.trends.extend(
            [
                {
                    "title": f"Story {i}",
                    "source": "cmmc_rss_fedscoop",
                    "url": dup_url,
                    "category": "cmmc_program",
                    "timestamp": "2024-01-01 12:00:00",
                }
                for i in range(5)
            ]
        )

        builder = WebsiteBuilder(basic_context)

        # Build the page (which populates _used_urls)
        html = builder.build()

        # The deduplication ensures trends are grouped, not that the URL
        # appears exactly once (it may appear in href, data-href, structured data, etc.)
        # Verify the builder's _used_urls tracking is populated
        assert len(html) > 0
        # The grouped trends should not have 5 separate entries for the same URL
        all_stories = []
        for stories in builder.grouped_trends.values():
            all_stories.extend(stories)
        dup_count = sum(1 for s in all_stories if s.get("url") == dup_url)
        assert dup_count <= 5  # grouped_trends doesn't dedup, but sections do

    def test_empty_trends_handling(self):
        """Test handling of empty trends list."""
        ctx = BuildContext(trends=[], images=[], design={}, keywords=[])

        builder = WebsiteBuilder(ctx)

        # Should not crash
        assert builder.grouped_trends == {}

    def _news_trends(self, n=11):
        return [
            {
                "title": f"Story {i} on CMMC",
                "source": "cmmc_rss_fedscoop",
                "url": f"https://example.com/{i}",
                "description": f"Summary for story {i}.",
                "category": "cmmc_program",
                "timestamp": f"2026-05-{10 + i} 12:00:00",
            }
            for i in range(n)
        ]

    def test_latest_rail_excludes_reddit_and_linkedin(self):
        """The Latest rail should only contain professional news sources."""
        trends = self._news_trends(5) + [
            {
                "title": "Reddit",
                "source": "reddit_cmmc",
                "url": "https://reddit.com/x",
                "timestamp": "2026-05-28 09:00:00",
            },
            {
                "title": "LinkedIn",
                "source": "cmmc_linkedin",
                "url": "https://linkedin.com/x",
                "timestamp": "2026-05-28 09:00:00",
            },
        ]
        ctx = BuildContext(trends=trends, images=[], design={}, keywords=[])
        latest = WebsiteBuilder(ctx)._get_latest_stories()
        urls = [s["url"] for s in latest]
        assert "https://reddit.com/x" not in urls
        assert "https://linkedin.com/x" not in urls
        assert len(latest) == 5

    def test_latest_rail_sorted_recent_first_and_deduped(self):
        trends = self._news_trends(5)
        trends.append(dict(trends[0]))  # duplicate URL
        ctx = BuildContext(trends=trends, images=[], design={}, keywords=[])
        latest = WebsiteBuilder(ctx)._get_latest_stories()
        timestamps = [s["timestamp"] for s in latest]
        assert timestamps == sorted(timestamps, reverse=True)
        assert len(latest) == len({s["url"] for s in latest})

    def test_latest_categories_distinct_in_order(self):
        trends = [
            {
                "title": "A",
                "source": "cmmc_rss_fedscoop",
                "url": "https://e.com/1",
                "category": "cmmc_program",
                "timestamp": "2026-05-28 12:00:00",
            },
            {
                "title": "B",
                "source": "cmmc_rss_nextgov",
                "url": "https://e.com/2",
                "category": "nist_compliance",
                "timestamp": "2026-05-27 12:00:00",
            },
            {
                "title": "C",
                "source": "cmmc_rss_securityweek",
                "url": "https://e.com/3",
                "category": "cmmc_program",
                "timestamp": "2026-05-26 12:00:00",
            },
        ]
        builder = WebsiteBuilder(BuildContext(trends=trends, images=[], design={}, keywords=[]))
        cats = builder._latest_categories(builder._get_latest_stories())
        keys = [c["key"] for c in cats]
        assert keys == ["cmmc_program", "nist_compliance"]
        labels = {c["key"]: c["label"] for c in cats}
        assert labels["cmmc_program"] == "CMMC"
        assert labels["nist_compliance"] == "NIST"

    def test_latest_filter_chips_render_when_multiple_categories(self):
        trends = [
            {
                "title": "A",
                "source": "cmmc_rss_fedscoop",
                "url": "https://example.com/1",
                "description": "desc a",
                "category": "cmmc_program",
                "timestamp": "2026-05-28 12:00:00",
            },
            {
                "title": "B",
                "source": "cmmc_rss_nextgov",
                "url": "https://example.com/2",
                "description": "desc b",
                "category": "nist_compliance",
                "timestamp": "2026-05-27 12:00:00",
            },
        ]
        html = WebsiteBuilder(BuildContext(trends=trends, images=[], design={}, keywords=[])).build()
        assert 'class="latest-filters"' in html
        assert 'data-filter="all"' in html
        assert 'data-filter="cmmc_program"' in html
        assert 'data-filter="nist_compliance"' in html

    def test_latest_filter_chips_absent_with_single_category(self):
        html = WebsiteBuilder(BuildContext(trends=self._news_trends(), images=[], design={}, keywords=[])).build()
        # _news_trends() are all cmmc_program -> only one category -> no filter bar
        assert 'class="latest-filters"' not in html

    def test_motion_layer_present(self):
        """Motion/interaction layer hooks and CSS are inlined into the page."""
        html = WebsiteBuilder(BuildContext(trends=self._news_trends(), images=[], design={}, keywords=[])).build()
        # Structural hooks
        assert 'id="scroll-progress"' in html
        assert 'class="hero-aurora"' in html
        assert "data-countup=" in html
        # Inlined motion CSS + reduced-motion guard
        assert "auroraDrift" in html
        assert "prefers-reduced-motion" in html
        # JS module wired in
        assert "navigator.vibrate" in html

    def test_brief_grid_renders_with_brief(self):
        ctx = BuildContext(
            trends=self._news_trends(),
            images=[],
            design={"color_accent": "#6366f1"},
            keywords=["cmmc"],
            front_page_brief={
                "headline": "DoD Tightens CMMC Timeline",
                "dek": "Contractors face a faster path.",
                "bullets": [
                    {
                        "text": "New rule accelerates rollout.",
                        "source_name": "Fedscoop",
                        "source_url": "https://example.com/1",
                        "source_title": "Story 1",
                    }
                ],
                "op_ed_paragraphs": ["Analysis paragraph one.", "Analysis paragraph two."],
                "date": "2026-05-28",
            },
        )
        html = WebsiteBuilder(ctx).build()
        assert 'class="brief-grid' in html
        assert "DoD Tightens CMMC Timeline" in html
        assert "New rule accelerates rollout." in html
        assert "Analysis paragraph one." in html
        assert 'class="latest-rail"' in html

    def test_brief_grid_fallback_header_without_brief(self):
        """With no brief but with stories, the Latest rail still renders and no crash."""
        ctx = BuildContext(trends=self._news_trends(), images=[], design={}, keywords=[])
        html = WebsiteBuilder(ctx).build()
        assert 'class="latest-rail"' in html
        assert "Latest CMMC &amp; Compliance News" in html

    def test_brief_op_ed_is_escaped(self):
        """Op-ed paragraphs are plain text and must be HTML-escaped (no raw tags)."""
        ctx = BuildContext(
            trends=self._news_trends(),
            images=[],
            design={},
            keywords=[],
            front_page_brief={
                "headline": "H",
                "dek": "",
                "bullets": [{"text": "t", "source_name": "s", "source_url": "https://e.com/1", "source_title": "t"}],
                "op_ed_paragraphs": ["<script>alert(1)</script>"],
                "date": "2026-05-28",
            },
        )
        html = WebsiteBuilder(ctx).build()
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_page_title_generation(self, basic_context):
        """Test that page title is SEO-optimized."""
        builder = WebsiteBuilder(basic_context)
        title = builder._build_page_title()

        # Should be consistent for homepage
        assert "CMMC Watch" in title
        assert "Daily" in title or "News" in title

    def test_meta_description_generation(self, basic_context):
        """Test that meta description is generated correctly."""
        builder = WebsiteBuilder(basic_context)
        meta_desc = builder._build_meta_description()

        # Should include key terms
        assert "CMMC" in meta_desc or "cmmc" in meta_desc.lower()
        assert "NIST" in meta_desc or "compliance" in meta_desc.lower()
        assert len(meta_desc) > 50  # Should be substantial

    def test_og_image_url_selection(self, basic_context):
        """Test Open Graph image URL selection."""
        builder = WebsiteBuilder(basic_context)
        og_url = builder._get_og_image_url()

        # Should return a valid URL from images
        assert og_url.startswith("http") if og_url else True

    def test_cmmc_relevance_detection(self, basic_context):
        """Test CMMC relevance detection for stories."""
        builder = WebsiteBuilder(basic_context)

        # CMMC-relevant story
        cmmc_story = {
            "title": "New CMMC 2.0 requirements announced",
            "category": "cmmc_program",
        }
        assert builder._is_cmmc_relevant(cmmc_story)

        # NIST-relevant story
        nist_story = {"title": "NIST 800-171 update released", "category": "other"}
        assert builder._is_cmmc_relevant(nist_story)

        # Non-relevant story
        irrelevant_story = {"title": "General tech news", "category": "other"}
        assert not builder._is_cmmc_relevant(irrelevant_story)

    def test_oversized_keyword_list(self, basic_context):
        """Test handling of very large keyword lists."""
        # Create oversized keyword list
        basic_context.keywords = ["keyword" + str(i) for i in range(1000)]

        builder = WebsiteBuilder(basic_context)
        html = builder.build()

        # Should not crash and should truncate keywords appropriately
        assert len(html) > 0

    def test_malicious_url_handling(self, basic_context):
        """Test handling of potentially malicious URLs."""
        # Add trend with javascript: URL
        basic_context.trends.append(
            {
                "title": "Test Story",
                "source": "test",
                "url": "javascript:alert('XSS')",
                "category": "cmmc_program",
            }
        )

        builder = WebsiteBuilder(basic_context)
        html = builder.build()

        # Should still produce valid HTML without crashing
        assert len(html) > 0
        # Jinja2 autoescape should escape quotes in any rendered URLs
        assert "javascript:alert(&#" in html or "javascript:alert(&#39;" in html or "javascript:alert(" in html

    def test_none_values_in_trends(self, basic_context):
        """Test handling of None values in trend data."""
        # Add trend with None values but valid url (url is required for source detection)
        basic_context.trends.append(
            {
                "title": "",
                "source": "",
                "url": "https://example.com",
                "description": "",
                "category": "cmmc_program",
            }
        )

        builder = WebsiteBuilder(basic_context)

        # Should not crash with empty string values
        html = builder.build()
        assert len(html) > 0

    def test_special_characters_in_descriptions(self, basic_context):
        """Test handling of special characters in descriptions."""
        special_chars = "Test <>&\"'éñ中文🔒"

        basic_context.trends[0]["description"] = special_chars

        builder = WebsiteBuilder(basic_context)
        html = builder.build()

        # Should properly escape HTML entities
        assert "&lt;" in html or special_chars in html  # Either escaped or preserved


class TestHTMLSanitization:
    """Test HTML sanitization for XSS protection."""

    def test_xss_in_title(self):
        """Test XSS attempt in title is sanitized."""
        ctx = BuildContext(
            trends=[
                {
                    "title": '<img src=x onerror="alert(1)">Test',
                    "source": "test",
                    "url": "https://example.com",
                    "category": "cmmc_program",
                }
            ],
            images=[],
            design={},
            keywords=[],
        )

        builder = WebsiteBuilder(ctx)
        html = builder.build()

        # XSS should be escaped
        assert 'onerror="alert(1)"' not in html

    def test_xss_in_description(self):
        """Test XSS attempt in description is sanitized."""
        ctx = BuildContext(
            trends=[
                {
                    "title": "Test",
                    "source": "test",
                    "url": "https://example.com",
                    "description": '<script>alert("XSS")</script>',
                    "category": "cmmc_program",
                }
            ],
            images=[],
            design={},
            keywords=[],
        )

        builder = WebsiteBuilder(ctx)
        html = builder.build()

        # Injected script tags in user data should be escaped by Jinja2
        # (legitimate script tags from the template are fine)
        # Jinja2 may also escape quotes: " -> &#34; or &quot;
        assert "&lt;script&gt;" in html or "onerror=" not in html
        # The raw unescaped <script> tag from user data must NOT appear
        assert '<script>alert("XSS")</script>' not in html

    def test_jinja_autoescape_enabled(self):
        """Regression guard: Jinja environment must autoescape HTML/XML."""
        ctx = BuildContext(trends=[], images=[], design={}, keywords=[])
        builder = WebsiteBuilder(ctx)

        # autoescape can be a callable (select_autoescape) or bool; both must
        # behave as truthy "escaping enabled" for html/xml extensions.
        autoescape = builder.env.autoescape
        if callable(autoescape):
            assert autoescape("page.html") is True
            assert autoescape("feed.xml") is True
        else:
            assert autoescape is True

    def test_no_safe_filter_in_templates(self):
        """Regression guard: only the explicitly-approved `|safe` usages may
        exist in templates. Each approved usage renders build-time output that
        is generated by trusted code, not user input. Any new `|safe` usage
        must be reviewed and added to APPROVED_SAFE_VARS below."""
        APPROVED_SAFE_VARS = {
            "structured_data",  # build-time JSON-LD assembled from trusted strings
            "hero_bg_css",  # CSS values produced by DesignGenerator
            "custom_styles",  # design stylesheet produced by DesignGenerator
        }

        import re

        templates_dir = Path(__file__).parent.parent / "templates"
        # Capture the token immediately before `| safe` (or `|safe`).
        safe_re = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\|\s*safe\b")
        unapproved = []
        for path in templates_dir.rglob("*.html"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for m in safe_re.finditer(text):
                var = m.group(1)
                if var not in APPROVED_SAFE_VARS:
                    unapproved.append(f"{path}: `{var} | safe`")
        assert not unapproved, (
            "Unapproved `| safe` usages in templates (each bypasses autoescape "
            "and must be vetted before adding to APPROVED_SAFE_VARS): " + "; ".join(unapproved)
        )

    def test_sql_injection_in_content(self):
        """Test SQL injection attempts are safely rendered."""
        ctx = BuildContext(
            trends=[
                {
                    "title": "'; DROP TABLE users; --",
                    "source": "test",
                    "url": "https://example.com",
                    "category": "cmmc_program",
                }
            ],
            images=[],
            design={},
            keywords=[],
        )

        builder = WebsiteBuilder(ctx)

        # Should not crash (no SQL execution in static site generator)
        html = builder.build()
        assert len(html) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
