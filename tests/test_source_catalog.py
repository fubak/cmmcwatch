#!/usr/bin/env python3
"""Tests for source_catalog module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from source_catalog import (
    COLLECTOR_SOURCES,
    SourceSpec,
    get_collector_sources,
    get_health_sources,
    get_source_by_key,
    get_source_by_source_key,
)


class TestSourceSpec:
    def test_can_construct_minimal_spec(self):
        spec = SourceSpec(
            key="test_key",
            name="Test Source",
            url="https://example.com/feed",
            category="cmmc",
            kind="rss",
        )
        assert spec.key == "test_key"
        assert spec.url == "https://example.com/feed"
        assert spec.tier == 4  # default

    def test_default_values(self):
        spec = SourceSpec(key="k", name="n", url="https://x", category="c", kind="rss")
        assert spec.healthcheck is True
        assert spec.parser == "rss"
        assert spec.headers_profile == "default"
        assert spec.risk == "medium"


class TestGetCollectorSources:
    def test_cmmc_rss_group_returns_list(self):
        sources = get_collector_sources("cmmc_rss")
        assert isinstance(sources, list)
        assert len(sources) > 0

    def test_each_rss_source_has_url(self):
        sources = get_collector_sources("cmmc_rss")
        for spec in sources:
            assert spec.url, f"{spec.key} missing URL"

    def test_each_rss_source_uses_http(self):
        sources = get_collector_sources("cmmc_rss")
        for spec in sources:
            assert spec.url.startswith(("http://", "https://"))

    def test_unknown_group_returns_empty(self):
        sources = get_collector_sources("nonexistent_group")
        assert sources == []

    def test_returns_independent_list(self):
        # Should return a copy, so mutations don't affect the registry
        sources = get_collector_sources("cmmc_rss")
        original_len = len(sources)
        sources.append("garbage")
        assert len(get_collector_sources("cmmc_rss")) == original_len


class TestGetHealthSources:
    def test_returns_list(self):
        sources = get_health_sources()
        assert isinstance(sources, list)
        assert len(sources) > 0

    def test_includes_well_known_feed(self):
        sources = get_health_sources()
        keys = {s.key for s in sources}
        assert "cmmc_fedscoop" in keys

    def test_only_returns_healthcheck_enabled(self):
        sources = get_health_sources()
        for spec in sources:
            assert spec.healthcheck is True


class TestGetSourceByKey:
    def test_returns_spec_for_known_key(self):
        found = get_source_by_key("cmmc_fedscoop")
        assert found is not None
        assert found.key == "cmmc_fedscoop"

    def test_returns_none_for_unknown(self):
        assert get_source_by_key("nonexistent_key_xyz") is None


class TestGetSourceBySourceKey:
    def test_returns_spec_for_known_source_key(self):
        # Source keys are typically prefixed with collector name
        all_sources = list(COLLECTOR_SOURCES)
        first_with_skey = next((s for s in all_sources if s.source_key), None)
        if first_with_skey:
            found = get_source_by_source_key(first_with_skey.source_key)
            assert found is not None

    def test_returns_none_for_unknown(self):
        assert get_source_by_source_key("does_not_exist_xyz") is None


class TestCatalogIntegrity:
    def test_no_duplicate_keys(self):
        keys = [s.key for s in COLLECTOR_SOURCES]
        assert len(keys) == len(set(keys)), "Duplicate keys in catalog"

    def test_all_have_categories(self):
        for spec in COLLECTOR_SOURCES:
            assert spec.category, f"{spec.key} missing category"

    def test_all_have_valid_kind(self):
        for spec in COLLECTOR_SOURCES:
            assert spec.kind in ("rss", "json", "html"), f"{spec.key} has invalid kind: {spec.kind}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
