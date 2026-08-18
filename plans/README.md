# Implementation Plans

Generated 2026-08-18 against `49416dc`, then executed in this session
instead of being left as handoff files. Status reflects the code as landed.

## Execution order & status

| Plan | Title | Priority | Effort | Depends on | Status |
|------|-------|----------|--------|------------|--------|
| 001 | Harden untrusted HTML/URLs | P1 | M | — | DONE |
| 002 | Classification: word boundaries, 6 categories, timestamps | P1 | M | tests in 001 | DONE |
| 003 | Single source of truth + sitemap 404s | P1 | S | — | DONE |
| 004 | Pipeline reliability (dry-run, MIN_TRENDS, editorial load, sections) | P1 | S | — | DONE |
| 005 | Pin apify-client; drop unused deps | P2 | S | — | DONE |
| 006 | PWA/OG icons + Saved page + homepage `?q=` | P2 | S | — | DONE |
| 007 | Federal Register + source health in the daily path | P2 | M | 003 | DONE |

## What landed (mapped to audit findings)

- Word-boundary `keyword_in_text` (`config.py`); used by collect/categorize/score
- Missing timestamps stay `None` (no fake “now”)
- Corroboration fields survive the Trend↔dict round-trip
- Validator prompt says 6 categories; invalid labels remapped; empty-URL semantic dedup
- Article HTML allowlist sanitizer; related-card escape; script-safe JSON
- Homepage/RSS drop `javascript:` and other non-http(s) URLs
- Hero CSS only accepts quote-safe https image URLs
- AI design colors must be `#hex`
- `_fetch_story_description` / og:image reject private/literal IPs
- `CMMC_RSS_FEEDS` derived from `source_catalog`
- Sitemap no longer advertises `/cmmc/`
- `--dry-run` skips archive; abort uses `MIN_TRENDS`
- Editorial load failure regenerates; validate/generate share 6 sections
- Groq first on complex editorial; Ollama only if env set
- LinkedIn last-fetched stored in unix seconds
- PWA writes `icon-192.png`, `icon-512.png`, `og-image.png`, `/saved/`
- Homepage search honors `?q=`
- Federal Register collector + catalog entry
- Source health runs in `main.py` (non-fatal)

## Findings considered and deferred

- Split Pages-deploy token from fetch job (workflow rewrite; MED risk)
- Parallel RSS / batched Apify (billing + bot-defense risk)
- Dual HTML chrome Jinja vs `shared_components` (partial: Saved + aria-current on both)
- Dual AI HTTP stacks in `story_validator` (prompt/allowlist only)
- Dual dedup merge-then-drop (corroboration now preserved; policy still two-pass)
- Full dated story corpus / newsletter ESP
- `.env.example` LinkedIn cleanup (file is permission-blocked from this agent)
- Dependabot / pip-audit CI job
- `ANALYSIS.md` body still historical after a supersede banner

## Dependency notes

Specs in `specs/content-rules.md` were updated to match the code (CW-CLASS-02, CW-FILTER-01, CW-SRC-01).
