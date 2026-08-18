# Content Rules

Business-language rules for what CMMC Watch publishes. See [README.md](README.md) for conventions.

## Classification (CW-CLASS)

### CW-CLASS-01 — Six valid story categories
Every published story is assigned exactly one of six categories: CMMC Program News,
NIST & Compliance, Intelligence Threats, Insider Threats, Defense Industrial Base,
Federal Cybersecurity. Stories that fit none of these are rejected.
- **Implemented by:** `scripts/story_validator.py:StoryValidator.VALID_CATEGORIES`
- **Verified by:** `tests/test_story_validator.py`
- **Note:** Category slugs are `cmmc_program`, `nist_compliance`,
  `intelligence_threats`, `insider_threats`, `defense_industrial_base`,
  `federal_cybersecurity`.

### CW-CLASS-02 — Keyword priority order
Relevance keywords are tiered by priority: CMMC-core terms (cmmc, c3pao, cyber-ab, …)
outrank NIST/compliance terms (nist 800-171, dfars, cui, fedramp, …), which outrank
intelligence-threat terms, then insider-threat terms, then Defense Industrial Base
terms, then federal cybersecurity as the fallback. Short tokens match on word
boundaries so “pla” does not classify “platform”.
- **Implemented by:** `scripts/config.py:keyword_in_text` plus
  `CMMC_CORE_KEYWORDS`, `NIST_KEYWORDS`, `INTELLIGENCE_KEYWORDS`,
  `INSIDER_THREAT_KEYWORDS`, `DIB_KEYWORDS`;
  `scripts/collect_trends.py:TrendCollector._categorize_trend`
- **Verified by:** `tests/test_config.py`, `tests/test_trend_collector.py`

## Filtering (CW-FILTER)

### CW-FILTER-01 — Keyword pre-filter before AI validation
A story must match at least one relevance keyword before it is sent to AI validation;
non-matching stories are dropped cheaply without an API call.
- **Implemented by:** `scripts/collect_trends.py` (`CMMC_KEYWORDS` via
  `keyword_in_text` in `_collect_rss_feeds` / `_collect_reddit` /
  `_collect_federal_register`). Specialty subs r/CMMC and r/NISTControls
  skip the keyword gate. LinkedIn influencer posts are curated and skip it.
- **Verified by:** `tests/test_config.py`, `tests/test_trend_collector.py`

### CW-FILTER-02 — Irrelevant-content patterns
Career/job posts, certification-training threads, generic Reddit megathreads/weekly
discussions, and personal career stories are rejected even if they match keywords.
Foreign-espionage stories are explicitly kept despite the non-US filter.
- **Implemented by:** `scripts/story_validator.py:StoryValidator.IRRELEVANT_PATTERNS`
- **Verified by:** `tests/test_story_validator.py`

### CW-FILTER-03 — AI relevance validation
Stories passing the keyword filter are batch-validated by an AI model for genuine
relevance to CMMC/compliance professionals and assigned a CW-CLASS-01 category.
- **Implemented by:** `scripts/story_validator.py:StoryValidator` (AI validation via
  `scripts/ai_providers.py`)
- **Verified by:** `tests/test_story_validator.py`

## Deduplication (CW-DEDUP)

### CW-DEDUP-01 — One story per event
Multiple articles covering the same event are clustered; one canonical story is kept
and duplicates are discarded.
- **Implemented by:** `scripts/story_validator.py:DuplicateCluster` and dedup logic in
  `StoryValidator`
- **Verified by:** `tests/test_story_validator.py`

## Freshness (CW-AGE)

### CW-AGE-01 — Maximum story age 14 days
Stories older than 14 days (e.g. old pinned posts) are never published.
- **Implemented by:** `scripts/story_validator.py:StoryValidator.MAX_STORY_AGE_DAYS`
- **Verified by:** `tests/test_story_validator.py`

## Sources (CW-SRC)

### CW-SRC-01 — Approved source list
Stories are collected only from the approved source registry: the RSS feed list,
approved subreddits (r/CMMC, r/NISTControls, r/FederalEmployees, r/cybersecurity),
and the curated LinkedIn influencer list. Adding a source means adding it to the
registry, not ad-hoc fetching.
- **Implemented by:** `scripts/source_catalog.py:COLLECTOR_SOURCES` (RSS, Reddit,
  Federal Register) and `scripts/config.py:CMMC_LINKEDIN_PROFILES`.
  `CMMC_RSS_FEEDS` is derived from the catalog and is not independently edited.
- **Verified by:** `tests/test_source_catalog.py`, `tests/test_config.py`
