# CLAUDE.md

Claude Code guidance for CMMC Watch - Daily CMMC/NIST compliance news aggregator.

**Live:** https://cmmcwatch.com | **Docs:** See README.md, CONTRIBUTING.md, ANALYSIS.md

## Commands

**Run:** `cd scripts && python main.py` | **No archive:** `--no-archive` | **Dry run:** `--dry-run` | **Test:** `pytest` | **Format:** `ruff format scripts/`

## Environment Variables

Required in `.env` or GitHub Secrets:
`GROQ_API_KEY` (primary AI) | `OPENROUTER_API_KEY` (backup) | `PEXELS_API_KEY` (primary images) | `UNSPLASH_ACCESS_KEY` (backup) | `APIFY_API_KEY` (LinkedIn) | `APIFY_ACTOR_ID` (LinkedIn scraper)

## Architecture

**Pipeline (10 steps in `main.py`):**
Archive → Collect CMMC trends → Fetch images → Generate design → Generate editorial → Build HTML → Generate RSS → PWA assets → Sitemap → Cleanup

| Module | Purpose |
|--------|---------|
| `main.py` | Pipeline orchestrator |
| `collect_trends.py` | CMMC RSS feeds, Reddit, LinkedIn |
| `fetch_images.py` | Pexels/Unsplash images |
| `fetch_linkedin_posts.py` | Apify LinkedIn scraper |
| `generate_design.py` | AI-driven design generation |
| `build_website.py` | HTML/CSS/JS builder |
| `editorial_generator.py` | Daily article generation |
| `generate_rss.py` | RSS 2.0 feed |
| `archive_manager.py` | 30-day snapshots |
| `config.py` | All constants and settings |

## Data Sources

**RSS Feeds:** FedScoop, DefenseScoop, Federal News Network, Nextgov, GovCon Wire, SecurityWeek, Cyberscoop, Breaking Defense, Defense One, Defense News, ExecutiveGov

**Reddit:** r/CMMC, r/NISTControls, r/FederalEmployees, r/cybersecurity, r/GovContracting

**LinkedIn Influencers:** Katie Arrington, Stacy Bostjanick, Matthew Travis, Summit 7 team (Scott Edwards, Jacob Horne, Daniel Akridge, Jacob Hill), Amira Armond

## CMMC Categories

1. **CMMC Program News** - Core CMMC keywords (cmmc, c3pao, cyber-ab)
2. **NIST & Compliance** - NIST 800-171, DFARS, FedRAMP, FISMA
3. **Defense Industrial Base** - DoD contractors, DIB news
4. **Federal Cybersecurity** - General federal cyber news

## GitHub Workflow

`daily-regenerate.yml` - Daily 6AM EST, push main, manual trigger
