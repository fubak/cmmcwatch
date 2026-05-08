#!/usr/bin/env python3
"""Tests for pwa_generator module."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from pwa_generator import (
    generate_manifest,
    generate_offline_page,
    generate_pwa_icon_placeholder,
    generate_service_worker,
    save_pwa_assets,
)


class TestGenerateManifest:
    def test_returns_valid_json(self):
        manifest = json.loads(generate_manifest())
        assert isinstance(manifest, dict)

    def test_has_required_pwa_fields(self):
        manifest = json.loads(generate_manifest())
        for key in ("name", "short_name", "start_url", "display", "icons"):
            assert key in manifest, f"missing PWA field: {key}"

    def test_branding_is_cmmc_watch(self):
        manifest = json.loads(generate_manifest())
        assert manifest["name"] == "CMMC Watch"
        assert manifest["short_name"] == "CMMCWatch"

    def test_no_dailytrending_leak(self):
        # Regression: identity must not contain old brand
        assert "dailytrending" not in generate_manifest().lower()

    def test_background_color_is_neutral(self):
        # Was #0f0a1a (dark), now should be neutral white
        manifest = json.loads(generate_manifest())
        assert manifest["background_color"] == "#ffffff"

    def test_icons_have_required_sizes(self):
        manifest = json.loads(generate_manifest())
        sizes = {icon["sizes"] for icon in manifest["icons"]}
        assert "192x192" in sizes
        assert "512x512" in sizes

    def test_shortcuts_present(self):
        manifest = json.loads(generate_manifest())
        assert "shortcuts" in manifest
        assert len(manifest["shortcuts"]) >= 2


class TestGenerateServiceWorker:
    def test_contains_cache_name(self):
        sw = generate_service_worker()
        assert "CACHE_NAME" in sw

    def test_includes_offline_url(self):
        sw = generate_service_worker()
        assert "OFFLINE_URL" in sw
        assert "/offline.html" in sw

    def test_caches_homepage(self):
        sw = generate_service_worker()
        assert "'/'" in sw or '"/"' in sw

    def test_handles_install_event(self):
        sw = generate_service_worker()
        assert "addEventListener('install'" in sw

    def test_handles_fetch_event(self):
        sw = generate_service_worker()
        assert "addEventListener('fetch'" in sw

    def test_versioned_cache_name(self):
        sw = generate_service_worker()
        # Cache name uses today's date for versioning
        assert "cmmcwatch-v" in sw


class TestGenerateOfflinePage:
    def test_returns_valid_html(self):
        html = generate_offline_page()
        assert html.lstrip().startswith("<!DOCTYPE html>")
        assert "</html>" in html

    def test_mentions_offline(self):
        html = generate_offline_page()
        assert "Offline" in html

    def test_branding_is_cmmc_watch(self):
        html = generate_offline_page()
        assert "CMMC Watch" in html

    def test_has_retry_button(self):
        html = generate_offline_page()
        assert "location.reload()" in html


class TestGeneratePwaIconPlaceholder:
    def test_returns_svg(self):
        icon = generate_pwa_icon_placeholder()
        assert "<svg" in icon
        assert "</svg>" in icon


class TestSavePwaAssets:
    def test_writes_all_assets(self, tmp_path):
        save_pwa_assets(tmp_path)
        assert (tmp_path / "manifest.json").exists()
        assert (tmp_path / "sw.js").exists()
        assert (tmp_path / "offline.html").exists()
        # Icon may be PNG or SVG depending on path; check for either
        assert (tmp_path / "icons").exists() or (tmp_path / "icon.svg").exists()

    def test_manifest_is_valid_json(self, tmp_path):
        save_pwa_assets(tmp_path)
        manifest = json.loads((tmp_path / "manifest.json").read_text())
        assert manifest["name"] == "CMMC Watch"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
