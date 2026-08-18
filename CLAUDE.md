# CLAUDE.md

Claude Code guidance for CMMC Watch - Daily CMMC/NIST compliance news aggregator.

**Live:** https://cmmcwatch.com | **Docs:** See README.md, CONTRIBUTING.md, ANALYSIS.md

## Commands

**Run:** `cd scripts && python main.py` | **No archive:** `--no-archive` | **Dry run:** `--dry-run` | **Test:** `pytest` | **Format:** `ruff format scripts/`

## Tool Usage

Use `sg -l python` for code searches, `rg` for text/config, `fdfind` for file finding. See `~/.claude/CLAUDE.md`.

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
| `generate_design.py` | AI-driven design generation (color math → `color_utils`, animation → `content_animation`) |
| `build_website.py` | HTML/CSS/JS builder |
| `editorial_generator.py` | Daily article generation (page HTML → `article_renderer`/`articles_index_renderer`) |
| `article_renderer.py` | Article-page HTML renderer (pure; extracted from `editorial_generator`) |
| `articles_index_renderer.py` | Articles-index page HTML renderer (pure) |
| `generate_rss.py` | RSS 2.0 feed |
| `archive_manager.py` | 30-day snapshots |
| `ai_providers.py` | Shared HTTP layer for Groq/OpenRouter/Google AI/Mistral/HF/Ollama |
| `json_utils.py` | Shared LLM-JSON repair helpers (`parse_llm_json`, `repair_json`) |
| `timestamp_utils.py` | Feed/API timestamp parsing → naive UTC (used by `collect_trends`) |
| `color_utils.py` | WCAG contrast/luminance math (used by `generate_design`) |
| `content_animation.py` | News-sentiment → animation intensity (used by `generate_design`) |
| `image_utils.py` | Image-URL validation/sanitization + text-heavy image filter |
| `config.py` | All constants and settings (incl. `SITE_URL`, `SITE_NAME`) |

## Data Sources

**RSS Feeds:** 20 official/trade feeds in `scripts/source_catalog.py` (FedScoop, DefenseScoop, FNN, Nextgov, GovCon Wire, SecurityWeek, Cyberscoop, Breaking Defense, Defense One, Defense News, ExecutiveGov, Industrial Cyber, IntelNews, CSIS, Cyberpress, Reuters Security, DOJ, NIST CSRC, CMMC Audit, Cyber-AB). Also Federal Register API.

**Reddit:** r/CMMC, r/NISTControls, r/FederalEmployees, r/cybersecurity

**LinkedIn Influencers (9, via Apify):** Katie Arrington, Stacy Bostjanick, Matthew Travis, Summit 7 team (Scott Edwards, Jacob Horne, Daniel Akridge, Jacob Hill), Amira Armond, Joy Beland

## CMMC Categories

1. **CMMC Program News** - Core CMMC keywords (cmmc, c3pao, cyber-ab)
2. **NIST & Compliance** - NIST 800-171, DFARS, FedRAMP, FISMA
3. **Intelligence Threats** - Espionage, nation-state actors, APTs
4. **Insider Threats** - Insider risks, employee recruitment, data theft
5. **Defense Industrial Base** - DoD contractors, DIB news
6. **Federal Cybersecurity** - General federal cyber news

## Rules-as-Spec (specs/)

Editorial/classification rules are specified in plain English in `specs/` with stable
IDs (`CW-CLASS-01`, …), each mapped to implementing code and verifying tests. Any change
to classification, filtering, categories, dedup, freshness, or sources MUST update the
matching rule in `specs/content-rules.md` and reference its ID in the commit/PR.

## Continuous Improvement

- **After corrections**: Append the lesson to `tasks/lessons.md` — write the rule that would have prevented the mistake
- **Before marking done**: Prove it works — pipeline runs clean, HTML output valid, no regressions in RSS/sitemap
- **3+ step tasks**: Enter plan mode; STOP and re-plan immediately if confused
- **Session start**: Read `tasks/lessons.md` for relevant patterns before beginning work

## GitHub Workflow

`daily-regenerate.yml` - Daily 6AM EST, push main, manual trigger
`fix-articles.yml` - Manual trigger for emergency article-HTML regeneration
`tests.yml` - Runs ruff lint + format check + pytest on every push to main/claude/** and on PRs to main
