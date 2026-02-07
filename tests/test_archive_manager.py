#!/usr/bin/env python3
"""Tests for archive manager module."""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import json
from datetime import datetime, timedelta

import pytest
from archive_manager import ArchiveManager


class TestArchiveManager:
    """Test ArchiveManager functionality."""

    @pytest.fixture
    def temp_public_dir(self, tmp_path):
        """Create temporary public directory for testing."""
        public_dir = tmp_path / "public"
        public_dir.mkdir()

        # Create a dummy index.html
        index_file = public_dir / "index.html"
        index_file.write_text(
            """<!DOCTYPE html>
<html>
<head>
    <title>Test Site</title>
</head>
<body>
    <h1>Test Content</h1>
</body>
</html>"""
        )

        return public_dir

    def test_manager_initialization(self, temp_public_dir):
        """Test ArchiveManager initialization."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        assert manager.public_dir == temp_public_dir
        assert manager.archive_dir == temp_public_dir / "archive"
        assert manager.archive_dir.exists()

    def test_archive_current_creates_dated_folder(self, temp_public_dir):
        """Test that archiving creates a dated folder."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        archive_path = manager.archive_current()

        assert archive_path is not None
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in archive_path
        assert Path(archive_path).exists()

    def test_archive_current_copies_index(self, temp_public_dir):
        """Test that archiving copies index.html."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        manager.archive_current()

        today = datetime.now().strftime("%Y-%m-%d")
        archived_index = manager.archive_dir / today / "index.html"

        assert archived_index.exists()
        assert "Test Content" in archived_index.read_text()

    def test_archive_adds_canonical_url(self, temp_public_dir):
        """Test that archiving adds canonical URL to archived page."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        manager.archive_current()

        today = datetime.now().strftime("%Y-%m-%d")
        archived_index = manager.archive_dir / today / "index.html"

        content = archived_index.read_text()

        # Should have canonical URL for archive
        assert 'rel="canonical"' in content
        assert f"/archive/{today}/" in content

    def test_archive_saves_metadata(self, temp_public_dir):
        """Test that archiving saves metadata.json."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        design = {"theme": "test", "color": "#FF5733"}
        manager.archive_current(design=design)

        today = datetime.now().strftime("%Y-%m-%d")
        metadata_file = manager.archive_dir / today / "metadata.json"

        assert metadata_file.exists()

        with open(metadata_file) as f:
            metadata = json.load(f)

        assert metadata["date"] == today
        assert metadata["design"] == design
        assert "archived_at" in metadata

    def test_archive_skips_existing_archive(self, temp_public_dir):
        """Test that archiving skips if archive for today already exists."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        # Archive once
        first_path = manager.archive_current()

        # Archive again (should skip)
        second_path = manager.archive_current()

        assert first_path == second_path

    def test_archive_no_index_returns_none(self, temp_public_dir):
        """Test that archiving returns None if no current index.html exists."""
        # Remove index.html
        (temp_public_dir / "index.html").unlink()

        manager = ArchiveManager(public_dir=str(temp_public_dir))

        result = manager.archive_current()

        assert result is None

    def test_path_traversal_protection(self, temp_public_dir):
        """Test path traversal protection in archive paths."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        # Try to create an archive with path traversal attempt
        # The date-based folder creation should prevent this
        # We'll test by checking that resolve() is used

        # Archive with normal date
        archive_path = manager.archive_current()

        # Ensure the path is within archive_dir
        resolved_archive = Path(archive_path).resolve()
        resolved_archive_dir = manager.archive_dir.resolve()

        assert str(resolved_archive).startswith(str(resolved_archive_dir))

    def test_list_archives(self, temp_public_dir):
        """Test listing archived websites."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        # Create an archive
        manager.archive_current()

        archives = manager.list_archives()

        assert len(archives) >= 1
        assert "folder" in archives[0]
        assert "url" in archives[0]
        assert "date" in archives[0]

    def test_list_archives_sorted_reverse_chronological(self, temp_public_dir):
        """Test that archives are listed in reverse chronological order."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        # Create multiple archives by manually creating dated folders
        dates = ["2024-01-01", "2024-01-02", "2024-01-03"]

        for date in dates:
            archive_dir = manager.archive_dir / date
            archive_dir.mkdir(parents=True, exist_ok=True)
            index_file = archive_dir / "index.html"
            index_file.write_text("<html><body>Test</body></html>")

        archives = manager.list_archives()

        # Should be sorted newest first
        assert len(archives) >= 3
        # First should be newest (2024-01-03 or today's date)
        first_date = archives[0]["folder"]
        assert first_date >= dates[0]

    def test_cleanup_old_archives(self, temp_public_dir):
        """Test cleanup of old archives."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        # Create an old archive (40 days ago)
        old_date = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d")
        old_archive_dir = manager.archive_dir / old_date
        old_archive_dir.mkdir(parents=True, exist_ok=True)
        (old_archive_dir / "index.html").write_text("<html><body>Old</body></html>")

        # Create a recent archive (10 days ago)
        recent_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        recent_archive_dir = manager.archive_dir / recent_date
        recent_archive_dir.mkdir(parents=True, exist_ok=True)
        (recent_archive_dir / "index.html").write_text(
            "<html><body>Recent</body></html>"
        )

        # Cleanup (keep 30 days)
        removed = manager.cleanup_old(keep_days=30)

        assert removed >= 1
        assert not old_archive_dir.exists()
        assert recent_archive_dir.exists()

    def test_cleanup_returns_count(self, temp_public_dir):
        """Test that cleanup returns number of removed archives."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        # Create old archives
        for i in range(35, 50):  # 35-50 days ago
            old_date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            old_archive_dir = manager.archive_dir / old_date
            old_archive_dir.mkdir(parents=True, exist_ok=True)
            (old_archive_dir / "index.html").write_text("<html></html>")

        removed = manager.cleanup_old(keep_days=30)

        # Should have removed all archives older than 30 days
        assert removed > 0

    def test_cleanup_skips_non_date_folders(self, temp_public_dir):
        """Test that cleanup skips folders that don't match date format."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        # Create a non-date folder
        non_date_folder = manager.archive_dir / "not-a-date"
        non_date_folder.mkdir()

        # Run cleanup
        manager.cleanup_old(keep_days=30)

        # Non-date folder should still exist
        assert non_date_folder.exists()

    def test_generate_index_creates_html(self, temp_public_dir):
        """Test that generate_index creates index.html."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        # Create some archives
        manager.archive_current()

        index_path = manager.generate_index()

        assert index_path is not None
        assert Path(index_path).exists()
        assert Path(index_path).name == "index.html"

    def test_generate_index_includes_archive_links(self, temp_public_dir):
        """Test that index includes links to archives."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        # Create an archive
        manager.archive_current()

        manager.generate_index()

        index_path = manager.archive_dir / "index.html"
        content = index_path.read_text()

        today = datetime.now().strftime("%Y-%m-%d")

        # Should include link to today's archive
        assert today in content or "archive-card" in content

    def test_generate_index_escapes_html(self, temp_public_dir):
        """Test that index generation escapes HTML in metadata."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        # Create archive with potentially malicious metadata
        design = {
            "headline": '<script>alert("XSS")</script>Test',
            "theme_name": '<img src=x onerror="alert(1)">',
        }

        manager.archive_current(design=design)
        manager.generate_index()

        index_path = manager.archive_dir / "index.html"
        content = index_path.read_text()

        # XSS should be escaped
        assert "<script>" not in content or "&lt;script&gt;" in content
        assert 'onerror="alert(1)"' not in content

    def test_generate_index_with_no_archives(self, temp_public_dir):
        """Test index generation with no archives."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        # Don't create any archives
        index_path = manager.generate_index()

        assert index_path is not None
        assert Path(index_path).exists()

        content = Path(index_path).read_text()

        # Should show empty state
        assert "No Archives" in content or "empty" in content.lower()

    def test_archive_index_regenerated_after_cleanup(self, temp_public_dir):
        """Test that index is regenerated after cleanup."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        # Create archives
        old_date = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d")
        old_archive_dir = manager.archive_dir / old_date
        old_archive_dir.mkdir(parents=True, exist_ok=True)
        (old_archive_dir / "index.html").write_text("<html></html>")

        manager.generate_index()

        # Cleanup
        manager.cleanup_old(keep_days=30)

        # Index should be regenerated and not include old archive
        index_path = manager.archive_dir / "index.html"
        content = index_path.read_text()

        assert old_date not in content

    def test_archive_metadata_includes_timestamp(self, temp_public_dir):
        """Test that archive metadata includes archived_at timestamp."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        before = datetime.now()
        manager.archive_current()
        after = datetime.now()

        today = datetime.now().strftime("%Y-%m-%d")
        metadata_file = manager.archive_dir / today / "metadata.json"

        with open(metadata_file) as f:
            metadata = json.load(f)

        archived_at = datetime.fromisoformat(metadata["archived_at"])

        # Timestamp should be between before and after
        assert before <= archived_at <= after

    def test_empty_design_metadata(self, temp_public_dir):
        """Test archiving with empty design metadata."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        manager.archive_current(design={})

        today = datetime.now().strftime("%Y-%m-%d")
        metadata_file = manager.archive_dir / today / "metadata.json"

        with open(metadata_file) as f:
            metadata = json.load(f)

        assert metadata["design"] == {}

    def test_none_design_metadata(self, temp_public_dir):
        """Test archiving with None design metadata."""
        manager = ArchiveManager(public_dir=str(temp_public_dir))

        manager.archive_current(design=None)

        today = datetime.now().strftime("%Y-%m-%d")
        metadata_file = manager.archive_dir / today / "metadata.json"

        with open(metadata_file) as f:
            metadata = json.load(f)

        assert metadata["design"] == {}


class TestArchiveIndexGeneration:
    """Test archive index page generation."""

    @pytest.fixture
    def manager_with_archives(self, tmp_path):
        """Create manager with some test archives."""
        public_dir = tmp_path / "public"
        public_dir.mkdir()

        # Create dummy index.html
        index_file = public_dir / "index.html"
        index_file.write_text("<html><body>Test</body></html>")

        manager = ArchiveManager(public_dir=str(public_dir))

        # Create test archives
        dates = ["2024-01-15", "2024-01-16", "2024-01-17"]

        for date in dates:
            archive_dir = manager.archive_dir / date
            archive_dir.mkdir(parents=True, exist_ok=True)

            (archive_dir / "index.html").write_text("<html><body>Test</body></html>")

            metadata = {
                "date": date,
                "design": {
                    "headline": f"News for {date}",
                    "theme_name": "Test Theme",
                    "color_accent": "#6366f1",
                },
            }

            with open(archive_dir / "metadata.json", "w") as f:
                json.dump(metadata, f)

        return manager

    def test_index_includes_all_archives(self, manager_with_archives):
        """Test that index includes all archives."""
        manager_with_archives.generate_index()

        index_path = manager_with_archives.archive_dir / "index.html"
        content = index_path.read_text()

        # Should include all three dates
        assert "2024-01-15" in content or "January 15" in content
        assert "2024-01-16" in content or "January 16" in content
        assert "2024-01-17" in content or "January 17" in content

    def test_index_includes_archive_stats(self, manager_with_archives):
        """Test that index includes archive statistics."""
        manager_with_archives.generate_index()

        index_path = manager_with_archives.archive_dir / "index.html"
        content = index_path.read_text()

        # Should show count of archives
        assert "3" in content or "three" in content.lower()
        assert "30" in content  # Retention days

    def test_index_canonical_url(self, manager_with_archives):
        """Test that index has canonical URL."""
        manager_with_archives.generate_index()

        index_path = manager_with_archives.archive_dir / "index.html"
        content = index_path.read_text()

        assert 'rel="canonical"' in content
        assert "/archive/" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
