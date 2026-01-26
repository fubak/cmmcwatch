#!/usr/bin/env python3
"""Tests for main pipeline."""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from main import CMMCWatchPipeline


class TestPipeline:
    """Test pipeline initialization and basic functions."""

    def test_pipeline_initialization(self):
        """Test that pipeline initializes correctly."""
        pipeline = CMMCWatchPipeline()
        
        assert pipeline is not None
        assert pipeline.project_root is not None
        assert pipeline.public_dir is not None
        assert pipeline.data_dir is not None
        assert pipeline.trends == []
        assert pipeline.images == []

    def test_pipeline_directories_created(self):
        """Test that required directories are created."""
        pipeline = CMMCWatchPipeline()
        
        assert pipeline.public_dir.exists()
        assert pipeline.data_dir.exists()

    def test_validate_environment_no_keys(self, monkeypatch):
        """Test environment validation fails when no API keys set."""
        # Clear all API keys
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
        
        pipeline = CMMCWatchPipeline()
        assert pipeline._validate_environment() is False

    def test_validate_environment_with_groq(self, monkeypatch):
        """Test environment validation succeeds with Groq key."""
        monkeypatch.setenv("GROQ_API_KEY", "test_key")
        
        pipeline = CMMCWatchPipeline()
        assert pipeline._validate_environment() is True

    def test_validate_environment_with_openrouter(self, monkeypatch):
        """Test environment validation succeeds with OpenRouter key."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test_key")
        
        pipeline = CMMCWatchPipeline()
        assert pipeline._validate_environment() is True

    def test_validate_environment_with_google(self, monkeypatch):
        """Test environment validation succeeds with Google key."""
        monkeypatch.setenv("GOOGLE_AI_API_KEY", "test_key")
        
        pipeline = CMMCWatchPipeline()
        assert pipeline._validate_environment() is True


class TestPipelineIntegration:
    """Integration tests for pipeline (slow, requires API keys)."""

    @pytest.mark.slow
    @pytest.mark.skipif(
        not any([
            Path(__file__).parent.parent / ".env",
        ]),
        reason="Requires .env file with API keys"
    )
    def test_pipeline_dry_run(self):
        """Test pipeline dry run (collect data only)."""
        pipeline = CMMCWatchPipeline()
        result = pipeline.run(archive=False, dry_run=True)
        
        # Dry run should succeed and collect some trends
        assert result is True
        assert len(pipeline.trends) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
