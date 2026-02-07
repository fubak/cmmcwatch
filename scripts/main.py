#!/usr/bin/env python3
"""
CMMC Watch Pipeline - Daily CMMC/NIST compliance news aggregator.

Pipeline steps:
1. Archive previous website (if exists)
2. Collect CMMC trends from specialized sources
3. Fetch images for visual content
4. Generate design specification
5. Generate editorial article
6. Build the HTML website
7. Generate RSS feed
8. Generate PWA assets
9. Generate sitemap
10. Clean up old archives
"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from archive_manager import ArchiveManager
from collect_trends import TrendCollector
from config import (
    PROJECT_ROOT,
    setup_logging,
)
from editorial_generator import EditorialGenerator
from fetch_images import ImageFetcher
from generate_design import DesignGenerator
from generate_rss import generate_rss_feed
from pwa_generator import save_pwa_assets
from sitemap_generator import save_sitemap

# Setup logging
logger = setup_logging("pipeline")


def _to_dict(obj):
    """Convert a dataclass instance to dict, or return as-is if already a dict."""
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    return obj


def _to_dict_list(items):
    """Convert a list of dataclass instances or dicts to a list of dicts."""
    return [_to_dict(item) for item in items]


class CMMCWatchPipeline:
    """Orchestrates the CMMC Watch website generation pipeline."""

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or PROJECT_ROOT
        self.public_dir = self.project_root / "public"
        self.data_dir = self.project_root / "data"

        # Ensure directories exist
        self.public_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Load environment FIRST before initializing components that need API keys
        self._load_environment()

        # Initialize components
        self.trend_collector = TrendCollector()
        self.image_fetcher = ImageFetcher()
        self.design_generator = DesignGenerator()
        self.archive_manager = ArchiveManager(public_dir=str(self.public_dir))
        self.editorial_generator = EditorialGenerator(public_dir=self.public_dir)

        # Pipeline data
        self.trends = []
        self.images = []
        self.design = None
        self.keywords = []
        self.editorial_article = None

    def run(self, archive: bool = True, dry_run: bool = False) -> bool:
        """Run the complete pipeline."""
        logger.info("=" * 60)
        logger.info("CMMC WATCH - Daily Compliance News")
        logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        # Validate environment variables
        if not self._validate_environment():
            logger.error("Environment validation failed. Aborting.")
            return False

        try:
            # Step 1: Archive previous
            if archive:
                logger.info("[1/10] Archiving previous website...")
                # Load previous design to save with archive
                prev_design = None
                design_file = self.data_dir / "design.json"
                if design_file.exists():
                    try:
                        with open(design_file) as f:
                            prev_design = json.load(f)
                    except Exception:
                        pass
                self.archive_manager.archive_current(design=prev_design)

            # Step 2: Collect trends
            logger.info("[2/10] Collecting CMMC trends...")
            self.trends = self.trend_collector.collect_all()
            self.keywords = self.trend_collector.get_global_keywords()
            logger.info(f"Collected {len(self.trends)} CMMC trends")

            if len(self.trends) < 3:
                logger.error("Not enough trends collected. Aborting.")
                return False

            if dry_run:
                logger.info("Dry run - skipping build steps")
                return True

            # Step 3: Fetch images
            logger.info("[3/10] Fetching images...")
            image_keywords = (
                self.keywords[:5] if self.keywords else ["cybersecurity", "compliance"]
            )
            self.images = self.image_fetcher.fetch_for_keywords(image_keywords)
            logger.info(f"Fetched {len(self.images)} images")

            # Step 4: Generate design
            logger.info("[4/10] Generating design...")
            self.design = self._generate_design()
            logger.info(f"Theme: {self.design.get('theme_name', 'default')}")

            # Step 5: Generate editorial
            logger.info("[5/10] Generating editorial content...")
            self._generate_editorial()

            # Step 6: Build website
            logger.info("[6/10] Building website...")
            self._build_website()

            # Step 7: Generate RSS
            logger.info("[7/10] Generating RSS feed...")
            self._generate_rss()

            # Step 8: PWA assets
            logger.info("[8/10] Generating PWA assets...")
            save_pwa_assets(self.public_dir)

            # Step 9: Sitemap
            logger.info("[9/10] Generating sitemap...")
            save_sitemap(self.public_dir, base_url="https://cmmcwatch.com")

            # Step 10: Cleanup
            logger.info("[10/10] Cleaning up old archives...")
            removed = self.archive_manager.cleanup_old()
            logger.info(f"Removed {removed} old archives")

            # Save pipeline data
            self._save_data()

            logger.info("=" * 60)
            logger.info("PIPELINE COMPLETE")
            logger.info("=" * 60)
            return True

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    def _load_environment(self):
        """Load environment variables from .env file."""
        try:
            from dotenv import load_dotenv

            env_file = self.project_root / ".env"
            if env_file.exists():
                load_dotenv(env_file)
                logger.info(f"Loaded environment from {env_file}")
        except ImportError:
            pass

    def _validate_environment(self) -> bool:
        """
        Validate that required environment variables are set.

        Returns:
            True if all required variables are set, False otherwise
        """
        # At least one AI key is required
        ai_keys = [
            os.getenv("GROQ_API_KEY"),
            os.getenv("OPENROUTER_API_KEY"),
            os.getenv("GOOGLE_AI_API_KEY"),
        ]

        if not any(ai_keys):
            logger.error("Missing AI API key!")
            logger.error("At least one of these must be set:")
            logger.error("  - GROQ_API_KEY (recommended)")
            logger.error("  - OPENROUTER_API_KEY")
            logger.error("  - GOOGLE_AI_API_KEY")
            return False

        # Log which AI service will be used
        if os.getenv("GROQ_API_KEY"):
            logger.info("✓ Using Groq for AI generation")
        elif os.getenv("OPENROUTER_API_KEY"):
            logger.info("✓ Using OpenRouter for AI generation")
        elif os.getenv("GOOGLE_AI_API_KEY"):
            logger.info("✓ Using Google AI for AI generation")

        # Image keys are recommended but not required
        if not any([os.getenv("PEXELS_API_KEY"), os.getenv("UNSPLASH_ACCESS_KEY")]):
            logger.warning("⚠ No image API keys set - images may be limited")
            logger.warning("  Consider adding PEXELS_API_KEY or UNSPLASH_ACCESS_KEY")

        # LinkedIn is optional
        if not os.getenv("APIFY_API_KEY"):
            logger.info("ℹ LinkedIn scraping disabled (APIFY_API_KEY not set)")
        else:
            logger.info("✓ LinkedIn scraping enabled via Apify")

        return True

    def _generate_design(self) -> dict:
        """Generate or load design specification."""
        design_file = self.data_dir / "design.json"
        today = datetime.now().strftime("%Y-%m-%d")

        # Check for existing today's design
        if design_file.exists():
            try:
                with open(design_file) as f:
                    design = json.load(f)
                if design.get("design_seed") == today:
                    return design
            except Exception:
                pass

        # Generate new design - convert trends to dicts first
        design = self.design_generator.generate(
            trends=_to_dict_list(self.trends[:5]),
            keywords=self.keywords[:10],
        )

        # Convert to dict if needed
        design = _to_dict(design)

        design["design_seed"] = today
        return design

    def _generate_editorial(self):
        """Generate daily editorial article."""
        try:
            self.editorial_article = self.editorial_generator.generate_editorial(
                trends=_to_dict_list(self.trends[:20]),
                keywords=self.keywords,
                design=self.design,
            )

            if self.editorial_article:
                logger.info(
                    f"Editorial article generated: {self.editorial_article.title}"
                )
            else:
                logger.error(
                    "Editorial article generation returned None - check logs above for details"
                )

            # Generate articles index page (always regenerate to keep index current)
            self.editorial_generator.generate_articles_index(design=self.design)
        except Exception as e:
            logger.error(f"Editorial generation failed with exception: {e}")
            self.editorial_article = None

    def _build_website(self):
        """Build the main HTML website."""
        from build_website import BuildContext, WebsiteBuilder

        context = BuildContext(
            trends=_to_dict_list(self.trends),
            images=_to_dict_list(self.images),
            design=self.design,
            keywords=self.keywords,
            editorial_article=(
                _to_dict(self.editorial_article) if self.editorial_article else None
            ),
        )

        builder = WebsiteBuilder(context)
        html = builder.build()

        output_path = self.public_dir / "index.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"Website saved to {output_path}")

    def _generate_rss(self):
        """Generate RSS feed."""
        generate_rss_feed(
            trends=_to_dict_list(self.trends[:50]),
            output_path=self.public_dir / "feed.xml",
            title="CMMC Watch",
            description="Daily CMMC & Compliance News Aggregator",
            link="https://cmmcwatch.com",
        )
        logger.info(f"RSS feed saved to {self.public_dir / 'feed.xml'}")

    def _save_data(self):
        """Save pipeline data to JSON files."""
        # Save trends
        with open(self.data_dir / "trends.json", "w") as f:
            json.dump(_to_dict_list(self.trends), f, indent=2, default=str)

        # Save images
        with open(self.data_dir / "images.json", "w") as f:
            json.dump(_to_dict_list(self.images), f, indent=2, default=str)

        # Save design
        with open(self.data_dir / "design.json", "w") as f:
            json.dump(self.design, f, indent=2, default=str)

        logger.info(f"Pipeline data saved to {self.data_dir}")


def main():
    parser = argparse.ArgumentParser(description="CMMC Watch Pipeline")
    parser.add_argument("--no-archive", action="store_true", help="Skip archiving")
    parser.add_argument("--dry-run", action="store_true", help="Collect data only")
    args = parser.parse_args()

    pipeline = CMMCWatchPipeline()
    success = pipeline.run(archive=not args.no_archive, dry_run=args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
