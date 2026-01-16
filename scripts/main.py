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

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from dataclasses import asdict
from typing import List

# Add scripts directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    setup_logging,
    PROJECT_ROOT,
    DATA_DIR,
    PUBLIC_DIR,
)
from collect_trends import TrendCollector, Trend
from fetch_images import ImageFetcher
from generate_design import DesignGenerator
from archive_manager import ArchiveManager
from generate_rss import generate_rss_feed
from editorial_generator import EditorialGenerator
from pwa_generator import save_pwa_assets
from sitemap_generator import save_sitemap
from shared_components import (
    build_header,
    build_footer,
    get_header_styles,
    get_footer_styles,
)

# Setup logging
logger = setup_logging("pipeline")


class CMMCWatchPipeline:
    """Orchestrates the CMMC Watch website generation pipeline."""

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or PROJECT_ROOT
        self.public_dir = self.project_root / "public"
        self.data_dir = self.project_root / "data"

        # Ensure directories exist
        self.public_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

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

        try:
            # Load environment
            self._load_environment()

            # Step 1: Archive previous
            if archive:
                logger.info("[1/10] Archiving previous website...")
                self.archive_manager.archive_current()

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
            save_pwa_assets(self.public_dir, site_name="CMMC Watch")

            # Step 9: Sitemap
            logger.info("[9/10] Generating sitemap...")
            save_sitemap(self.public_dir, base_url="https://cmmcwatch.info")

            # Step 10: Cleanup
            logger.info("[10/10] Cleaning up old archives...")
            removed = self.archive_manager.cleanup_old_archives()
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
        trends_for_design = []
        for t in self.trends[:5]:
            if hasattr(t, "__dataclass_fields__"):
                trends_for_design.append(asdict(t))
            else:
                trends_for_design.append(t)

        design = self.design_generator.generate(
            trends=trends_for_design,
            keywords=self.keywords[:10],
        )

        # Convert to dict if needed
        if hasattr(design, "__dataclass_fields__"):
            design = asdict(design)

        design["design_seed"] = today
        return design

    def _generate_editorial(self):
        """Generate daily editorial article."""
        try:
            # Convert trends to dict format
            trends_dict = []
            for t in self.trends[:20]:
                if hasattr(t, "__dataclass_fields__"):
                    trends_dict.append(asdict(t))
                else:
                    trends_dict.append(t)

            self.editorial_article = self.editorial_generator.generate_editorial(
                trends=trends_dict,
                keywords=self.keywords,
                design=self.design,
            )
            logger.info("Editorial article generated")
        except Exception as e:
            logger.warning(f"Editorial generation failed: {e}")
            self.editorial_article = None

    def _build_website(self):
        """Build the main HTML website."""
        from build_website import WebsiteBuilder, BuildContext

        # Prepare trends as dicts
        trends_dict = []
        for t in self.trends:
            if hasattr(t, "__dataclass_fields__"):
                trends_dict.append(asdict(t))
            else:
                trends_dict.append(t)

        # Prepare images as dicts
        images_dict = []
        for img in self.images:
            if hasattr(img, "__dataclass_fields__"):
                images_dict.append(asdict(img))
            else:
                images_dict.append(img)

        context = BuildContext(
            trends=trends_dict,
            images=images_dict,
            design=self.design,
            keywords=self.keywords,
            editorial_article=(
                asdict(self.editorial_article)
                if self.editorial_article
                and hasattr(self.editorial_article, "__dataclass_fields__")
                else self.editorial_article
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
        trends_dict = []
        for t in self.trends[:50]:
            if hasattr(t, "__dataclass_fields__"):
                trends_dict.append(asdict(t))
            else:
                trends_dict.append(t)

        generate_rss_feed(
            trends=trends_dict,
            output_path=self.public_dir / "feed.xml",
            site_title="CMMC Watch",
            site_description="Daily CMMC & Compliance News Aggregator",
            site_link="https://cmmcwatch.info",
        )
        logger.info(f"RSS feed saved to {self.public_dir / 'feed.xml'}")

    def _save_data(self):
        """Save pipeline data to JSON files."""
        # Save trends
        trends_dict = []
        for t in self.trends:
            if hasattr(t, "__dataclass_fields__"):
                trends_dict.append(asdict(t))
            else:
                trends_dict.append(t)

        with open(self.data_dir / "trends.json", "w") as f:
            json.dump(trends_dict, f, indent=2, default=str)

        # Save images
        images_dict = []
        for img in self.images:
            if hasattr(img, "__dataclass_fields__"):
                images_dict.append(asdict(img))
            else:
                images_dict.append(img)

        with open(self.data_dir / "images.json", "w") as f:
            json.dump(images_dict, f, indent=2, default=str)

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
