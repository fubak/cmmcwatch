#!/usr/bin/env python3
"""Tests for image fetcher module."""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import hashlib
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fetch_images import (
    FallbackImageGenerator,
    Image,
    ImageCache,
    ImageFetcher,
    KeyRotator,
    is_text_heavy_image,
)


class TestKeyRotator:
    """Test API key rotation functionality."""

    def test_rotator_initialization(self):
        """Test key rotator initialization."""
        keys = ["key1", "key2", "key3"]
        rotator = KeyRotator(keys, "TestService")

        assert rotator.keys == keys
        assert rotator.service_name == "TestService"
        assert rotator.current_index == 0
        assert len(rotator.exhausted_keys) == 0

    def test_get_current_key(self):
        """Test getting current key."""
        keys = ["key1", "key2"]
        rotator = KeyRotator(keys, "TestService")

        assert rotator.get_current_key() == "key1"

    def test_get_current_key_empty_list(self):
        """Test getting current key with empty key list."""
        rotator = KeyRotator([], "TestService")

        assert rotator.get_current_key() is None

    def test_rotate_to_next_key(self):
        """Test rotating to next key."""
        keys = ["key1", "key2", "key3"]
        rotator = KeyRotator(keys, "TestService")

        next_key = rotator.rotate()

        assert next_key == "key2"
        assert rotator.current_index == 1

    def test_rotate_wraps_around(self):
        """Test rotation wraps around to first key."""
        keys = ["key1", "key2"]
        rotator = KeyRotator(keys, "TestService")

        rotator.current_index = 1
        next_key = rotator.rotate()

        assert next_key == "key1"
        assert rotator.current_index == 0

    def test_mark_key_exhausted(self):
        """Test marking a key as exhausted."""
        keys = ["key1", "key2", "key3"]
        rotator = KeyRotator(keys, "TestService")

        rotator.mark_exhausted()

        assert "key1" in rotator.exhausted_keys
        assert len(rotator.exhausted_keys) == 1

    def test_rotation_skips_exhausted_keys(self):
        """Test that rotation skips exhausted keys."""
        keys = ["key1", "key2", "key3"]
        rotator = KeyRotator(keys, "TestService")

        # Exhaust key1
        rotator.mark_exhausted()

        # Rotate should skip key1
        next_key = rotator.rotate()
        assert next_key == "key2"

    def test_all_keys_exhausted(self):
        """Test when all keys are exhausted."""
        keys = ["key1", "key2"]
        rotator = KeyRotator(keys, "TestService")

        # Exhaust all keys
        rotator.mark_exhausted()
        rotator.rotate()
        rotator.mark_exhausted()

        # Should return None
        assert rotator.get_current_key() is None

    def test_reset_exhausted_keys(self):
        """Test resetting exhausted keys."""
        keys = ["key1", "key2"]
        rotator = KeyRotator(keys, "TestService")

        rotator.mark_exhausted()
        assert len(rotator.exhausted_keys) == 1

        rotator.reset()

        assert len(rotator.exhausted_keys) == 0
        assert rotator.current_index == 0

    def test_has_keys_property(self):
        """Test has_keys property."""
        rotator_with_keys = KeyRotator(["key1"], "Test")
        rotator_without_keys = KeyRotator([], "Test")

        assert rotator_with_keys.has_keys is True
        assert rotator_without_keys.has_keys is False

    def test_has_available_keys_property(self):
        """Test has_available_keys property."""
        keys = ["key1", "key2"]
        rotator = KeyRotator(keys, "Test")

        assert rotator.has_available_keys is True

        # Exhaust all keys
        rotator.mark_exhausted()
        rotator.rotate()
        rotator.mark_exhausted()

        assert rotator.has_available_keys is False


class TestImageCacheKeyGeneration:
    """Test image cache key generation (SHA256 hashing)."""

    def test_cache_key_generation(self):
        """Test that cache keys are generated using SHA256."""
        cache = ImageCache()

        key1 = cache._query_key("cybersecurity")
        key2 = cache._query_key("cybersecurity")

        # Same query should produce same key
        assert key1 == key2

        # Should be hex string (SHA256 truncated to 12 chars)
        assert len(key1) == 12
        assert all(c in "0123456789abcdef" for c in key1)

    def test_cache_key_normalization(self):
        """Test that cache keys normalize input."""
        cache = ImageCache()

        key1 = cache._query_key("CyberSecurity")
        key2 = cache._query_key("cybersecurity")
        key3 = cache._query_key("  cybersecurity  ")

        # All should produce same key (case-insensitive, trimmed)
        assert key1 == key2 == key3

    def test_different_queries_different_keys(self):
        """Test that different queries produce different keys."""
        cache = ImageCache()

        key1 = cache._query_key("cybersecurity")
        key2 = cache._query_key("compliance")

        assert key1 != key2

    def test_cache_key_uses_sha256(self):
        """Test that cache key is actually using SHA256."""
        cache = ImageCache()

        query = "test query"
        key = cache._query_key(query)

        # Compute expected SHA256
        expected = hashlib.sha256(query.lower().strip().encode()).hexdigest()[:12]

        assert key == expected


class TestImageCacheLogic:
    """Test image cache hit/miss logic."""

    @pytest.fixture
    def temp_cache(self, tmp_path):
        """Create temporary cache directory."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        return ImageCache(cache_dir=cache_dir)

    def test_cache_miss_on_uncached_query(self, temp_cache):
        """Test cache miss for uncached query."""
        assert not temp_cache.is_cached("new_query")

    def test_cache_hit_after_caching(self, temp_cache):
        """Test cache hit after caching results."""
        query = "test_query"
        images = [
            Image(
                id="test1",
                url_small="small",
                url_medium="med",
                url_large="large",
                url_original="orig",
                photographer="Test",
                photographer_url="http://test.com",
                source="pexels",
                alt_text="Test image",
            )
        ]

        temp_cache.cache_results(query, images)

        assert temp_cache.is_cached(query)

    def test_get_cached_images(self, temp_cache):
        """Test retrieving cached images."""
        query = "cybersecurity"
        images = [
            Image(
                id="img1",
                url_small="s1",
                url_medium="m1",
                url_large="l1",
                url_original="o1",
                photographer="Photographer 1",
                photographer_url="http://p1.com",
                source="pexels",
                alt_text="Image 1",
            ),
            Image(
                id="img2",
                url_small="s2",
                url_medium="m2",
                url_large="l2",
                url_original="o2",
                photographer="Photographer 2",
                photographer_url="http://p2.com",
                source="unsplash",
                alt_text="Image 2",
            ),
        ]

        temp_cache.cache_results(query, images)
        cached = temp_cache.get_cached(query)

        assert len(cached) == 2
        assert cached[0].id == "img1"
        assert cached[1].id == "img2"

    def test_cache_expiration(self, temp_cache):
        """Test that cache entries expire after max age."""
        query = "old_query"
        images = [
            Image(
                id="old",
                url_small="s",
                url_medium="m",
                url_large="l",
                url_original="o",
                photographer="P",
                photographer_url="http://p.com",
                source="pexels",
                alt_text="Old image",
            )
        ]

        # Cache with old timestamp
        key = temp_cache._query_key(query)
        temp_cache.index["images"] = {"old": images[0].__dict__}
        temp_cache.index["queries"] = {
            key: {
                "query": query,
                "timestamp": (datetime.now() - timedelta(days=100)).isoformat(),
                "image_ids": ["old"],
            }
        }

        # Should be expired (cache max age is 30 days by default)
        assert not temp_cache.is_cached(query)

    def test_cache_not_expired(self, temp_cache):
        """Test that recent cache entries are not expired."""
        query = "recent_query"
        images = [
            Image(
                id="recent",
                url_small="s",
                url_medium="m",
                url_large="l",
                url_original="o",
                photographer="P",
                photographer_url="http://p.com",
                source="pexels",
                alt_text="Recent image",
            )
        ]

        # Cache with recent timestamp
        temp_cache.cache_results(query, images)

        # Should not be expired
        assert temp_cache.is_cached(query)

    def test_cache_cleanup_on_max_entries(self, temp_cache):
        """Test that cache cleans up when max entries exceeded."""
        # Set a low max entries for testing (by modifying the limit temporarily)
        from fetch_images import CACHE_MAX_ENTRIES  # noqa: F811

        # Create many cache entries
        for i in range(10):
            query = f"query_{i}"
            images = [
                Image(
                    id=f"img_{i}",
                    url_small="s",
                    url_medium="m",
                    url_large="l",
                    url_original="o",
                    photographer="P",
                    photographer_url="http://p.com",
                    source="pexels",
                    alt_text=f"Image {i}",
                )
            ]
            temp_cache.cache_results(query, images)

        # Cache should limit entries
        stats = temp_cache.get_stats()
        assert stats["total_images"] <= CACHE_MAX_ENTRIES

    def test_get_random_cached_images(self, temp_cache):
        """Test getting random cached images as fallback."""
        # Add multiple images to cache
        for i in range(5):
            query = f"query_{i}"
            images = [
                Image(
                    id=f"img_{i}",
                    url_small="s",
                    url_medium="m",
                    url_large="l",
                    url_original="o",
                    photographer="P",
                    photographer_url="http://p.com",
                    source="pexels",
                    alt_text=f"Image {i}",
                )
            ]
            temp_cache.cache_results(query, images)

        random_images = temp_cache.get_random_cached(count=3)

        assert len(random_images) <= 3

    def test_cache_stats(self, temp_cache):
        """Test cache statistics."""
        # Add some cached data
        images = [
            Image(
                id="test",
                url_small="s",
                url_medium="m",
                url_large="l",
                url_original="o",
                photographer="P",
                photographer_url="http://p.com",
                source="pexels",
                alt_text="Test",
            )
        ]
        temp_cache.cache_results("test_query", images)

        stats = temp_cache.get_stats()

        assert "total_images" in stats
        assert "total_queries" in stats
        assert stats["total_images"] >= 1
        assert stats["total_queries"] >= 1


class TestImageURLValidation:
    """Test image URL validation."""

    def test_valid_image_urls(self):
        """Test that valid image URLs are accepted."""
        from collect_trends import TrendCollector

        collector = TrendCollector()

        assert collector._is_valid_image_url("https://example.com/image.jpg")
        assert collector._is_valid_image_url("https://cdn.example.com/photo.png")
        assert collector._is_valid_image_url("https://images.example.com/img.jpeg")

    def test_invalid_tracking_pixels(self):
        """Test that tracking pixels are rejected."""
        from collect_trends import TrendCollector

        collector = TrendCollector()

        # Tracking pixels should be rejected
        assert not collector._is_valid_image_url("https://example.com/pixel.gif")
        assert not collector._is_valid_image_url("https://example.com/1x1.png")
        assert not collector._is_valid_image_url("https://tracking.example.com/pixel")

    def test_empty_url(self):
        """Test that empty URLs are rejected."""
        from collect_trends import TrendCollector

        collector = TrendCollector()

        assert not collector._is_valid_image_url("")
        assert not collector._is_valid_image_url(None)


class TestTextHeavyImageFiltering:
    """Test filtering of text-heavy images (screenshots, infographics)."""

    def test_detect_screenshot_keywords(self):
        """Test detection of screenshot-related keywords."""
        assert is_text_heavy_image("Screenshot of website")
        assert is_text_heavy_image("Screen capture from app")
        assert is_text_heavy_image("This is a web page screenshot")

    def test_detect_infographic_keywords(self):
        """Test detection of infographic-related keywords."""
        assert is_text_heavy_image("Infographic about data")
        assert is_text_heavy_image("Chart showing statistics")
        assert is_text_heavy_image("Graph with data visualization")

    def test_detect_document_keywords(self):
        """Test detection of document-related keywords."""
        assert is_text_heavy_image("Document with text")
        assert is_text_heavy_image("Article text")
        assert is_text_heavy_image("Book page with writing")

    def test_detect_ui_keywords(self):
        """Test detection of UI/interface keywords."""
        assert is_text_heavy_image("Dashboard interface")
        assert is_text_heavy_image("Mobile app screen")
        assert is_text_heavy_image("User interface design")

    def test_clean_images_not_flagged(self):
        """Test that clean photographic images are not flagged."""
        assert not is_text_heavy_image("Sunset over mountains")
        assert not is_text_heavy_image("Portrait of person")
        assert not is_text_heavy_image("City skyline at night")
        assert not is_text_heavy_image("Abstract technology background")

    def test_case_insensitive_detection(self):
        """Test that detection is case-insensitive."""
        assert is_text_heavy_image("SCREENSHOT")
        assert is_text_heavy_image("Screenshot")
        assert is_text_heavy_image("screenshot")


class TestImageFetcher:
    """Test ImageFetcher functionality."""

    def test_fetcher_initialization(self):
        """Test ImageFetcher initialization."""
        fetcher = ImageFetcher(use_cache=False)

        assert fetcher.images == []
        assert len(fetcher.used_ids) == 0
        assert fetcher.session is not None

    def test_fetcher_with_cache(self, tmp_path):
        """Test ImageFetcher with caching enabled."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        with patch("fetch_images.IMAGE_CACHE_DIR", cache_dir):
            fetcher = ImageFetcher(use_cache=True)

            assert fetcher.cache is not None

    def test_fetcher_without_cache(self):
        """Test ImageFetcher with caching disabled."""
        fetcher = ImageFetcher(use_cache=False)

        assert fetcher.cache is None

    @patch("fetch_images.ImageFetcher.search_pexels")
    def test_search_tries_pexels_first(self, mock_pexels):
        """Test that search tries Pexels first."""
        mock_pexels.return_value = [
            Image(
                id="pexels_1",
                url_small="s",
                url_medium="m",
                url_large="l",
                url_original="o",
                photographer="P",
                photographer_url="http://p.com",
                source="pexels",
                alt_text="Test",
            )
        ]

        fetcher = ImageFetcher(use_cache=False)
        results = fetcher.search("test")

        mock_pexels.assert_called_once()
        assert len(results) == 1
        assert results[0].source == "pexels"

    @patch("fetch_images.ImageFetcher.search_unsplash")
    @patch("fetch_images.ImageFetcher.search_pexels")
    def test_search_falls_back_to_unsplash(self, mock_pexels, mock_unsplash):
        """Test that search falls back to Unsplash if Pexels fails."""
        mock_pexels.return_value = []
        mock_unsplash.return_value = [
            Image(
                id="unsplash_1",
                url_small="s",
                url_medium="m",
                url_large="l",
                url_original="o",
                photographer="P",
                photographer_url="http://p.com",
                source="unsplash",
                alt_text="Test",
            )
        ]

        fetcher = ImageFetcher(use_cache=False)
        results = fetcher.search("test")

        assert len(results) == 1
        assert results[0].source == "unsplash"

    def test_image_deduplication_by_id(self):
        """Test that images with same ID are not returned twice."""
        fetcher = ImageFetcher(use_cache=False)

        # Add same image ID to used_ids
        fetcher.used_ids.add("img_1")

        # Mock search to return that ID
        with patch.object(
            fetcher,
            "search_pexels",
            return_value=[
                Image(
                    id="img_1",
                    url_small="s",
                    url_medium="m",
                    url_large="l",
                    url_original="o",
                    photographer="P",
                    photographer_url="http://p.com",
                    source="pexels",
                    alt_text="Test",
                )
            ],
        ):
            results = fetcher.search("test")

            # Should be filtered out
            assert len(results) == 0


class TestFallbackImageGenerator:
    """Test fallback gradient generation."""

    def test_get_gradient(self):
        """Test getting a random gradient."""
        direction, color1, color2 = FallbackImageGenerator.get_gradient()

        assert direction in ["135deg", "180deg"]
        assert color1.startswith("#")
        assert color2.startswith("#")

    def test_get_gradient_css(self):
        """Test getting gradient as CSS."""
        css = FallbackImageGenerator.get_gradient_css()

        assert "linear-gradient" in css
        assert "deg" in css
        assert "#" in css

    def test_get_mesh_gradient_css(self):
        """Test getting mesh gradient as CSS."""
        css = FallbackImageGenerator.get_mesh_gradient_css()

        assert "radial-gradient" in css
        assert "#" in css


class TestImageDataclass:
    """Test Image dataclass."""

    def test_image_initialization(self):
        """Test Image initialization with required fields."""
        img = Image(
            id="test_1",
            url_small="https://example.com/small.jpg",
            url_medium="https://example.com/medium.jpg",
            url_large="https://example.com/large.jpg",
            url_original="https://example.com/original.jpg",
            photographer="Test Photographer",
            photographer_url="https://example.com/photographer",
            source="pexels",
            alt_text="Test image description",
        )

        assert img.id == "test_1"
        assert img.source == "pexels"
        assert img.photographer == "Test Photographer"

    def test_image_with_optional_fields(self):
        """Test Image with optional fields."""
        img = Image(
            id="test_2",
            url_small="s",
            url_medium="m",
            url_large="l",
            url_original="o",
            photographer="P",
            photographer_url="http://p.com",
            source="unsplash",
            alt_text="Test",
            color="#FF5733",
            width=1920,
            height=1080,
        )

        assert img.color == "#FF5733"
        assert img.width == 1920
        assert img.height == 1080


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
