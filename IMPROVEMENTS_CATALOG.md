# CMMC Watch Improvements Catalog

This file catalogs the source-ingestion and resilience improvements ported from `daily-trending-info`, and where they are implemented in this repository.

## 1) Canonical Source Catalog

Implemented in:
- `scripts/source_catalog.py`

What changed:
- Centralized all collector sources into typed `SourceSpec` entries.
- Added per-source metadata (`tier`, `source_type`, `risk`, `parser`, `fallback_url`).
- Added reusable profile maps:
  - `HEADER_PROFILES` for source-class request headers.
  - `DOMAIN_FETCH_PROFILES` for host-specific timeout/retry tuning.
- Added indexed access helpers:
  - `get_collector_sources()`
  - `get_health_sources()`
  - `get_source_by_key()`
  - `get_source_by_source_key()`

Why it matters:
- Removes source drift between collector and health checks.
- Makes source additions/removals explicit and reviewable.

## 2) Source Metadata Registry

Implemented in:
- `scripts/source_registry.py`

What changed:
- Added unified source metadata resolution for ranking and display:
  - `get_source_metadata()`
  - `source_metadata_dict()`
  - `format_source_label()`
  - `source_quality_multiplier()`
- Added exact metadata generated from the source catalog and prefix fallbacks.

Why it matters:
- Ranking can account for source quality/risk consistently.
- UI labels now include source-quality context.

## 3) Hardened RSS Fetching

Implemented in:
- `scripts/collect_trends.py`

What changed:
- Added feed runtime controls:
  - in-memory cache
  - persistent cache (`data/feed_runtime_cache.json`)
  - cooldown after repeated failures
  - host-specific retries and retry delays
  - fallback URL support
- Added content-type/feed-content validation before accepting responses.
- Added timestamp normalization helpers for heterogeneous feed and API timestamps.

Why it matters:
- Prevents repeated hard failures from taking down collection runs.
- Keeps pipeline productive when sources intermittently fail.

## 4) Deduplication Upgrade (Clustering + Corroboration)

Implemented in:
- `scripts/collect_trends.py`

What changed:
- Replaced simple title similarity dedup with clustered dedup using:
  - token overlap
  - jaccard similarity
  - semantic ratio (SequenceMatcher)
- Canonical trend selected by quality-aware score.
- Duplicates now merge corroborating source URLs and source diversity.

Why it matters:
- Reduces duplicate noise while preserving multi-source corroboration signals.

## 5) Quality-Aware Ranking

Implemented in:
- `scripts/collect_trends.py`
- `scripts/source_registry.py`

What changed:
- Final scoring now combines:
  - base relevance score
  - recency boost
  - source-quality multiplier
  - source-diversity boost

Why it matters:
- Promotes high-quality corroborated reporting over single-source low-signal posts.

## 6) Source Health Monitoring

Implemented in:
- `scripts/source_health_check.py`

What changed:
- Added parallel health checks for all cataloged sources.
- Adds clear source status classifications:
  - `healthy`
  - `degraded`
  - `flaky` (intermittent/retry-success)
  - `down`
- Supports fallback validation and writes `data/source_health.json`.

Why it matters:
- Provides daily operational visibility into failing or unstable sources.

## 7) Test Coverage for Resilience Paths

Implemented in:
- `tests/test_trend_collector.py`
- `tests/test_source_health_check.py`

What changed:
- Added tests for:
  - fallback feed usage
  - cached response usage during cooldown
  - corroboration-aware dedup behavior
  - quality-influenced ranking order
  - flaky source classification
  - fallback success classification
  - health source coverage for CMMC Reddit feeds

Why it matters:
- Reduces regression risk on the most failure-prone ingestion logic.

## 8) Runtime Artifact Hygiene

Implemented in:
- `.gitignore`

What changed:
- Added ignore rule for feed runtime cache:
  - `data/feed_runtime_cache.json`

Why it matters:
- Prevents ephemeral runtime cache files from polluting git history.
