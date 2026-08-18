# Specs — Rules-as-Spec Layer

Plain-English statements of the editorial/classification rules this pipeline enforces,
each traceable to the code that implements it and the tests that verify it.

## Conventions

- Every rule has a stable ID: `CW-<AREA>-<NN>` (e.g. `CW-CLASS-01`). IDs are never reused.
- Each rule lists **Implemented by** (file:symbol) and **Verified by** (test file) links.
- Any PR that changes classification, filtering, or category behavior MUST update the
  matching rule here (or add a new one) and reference the rule ID in the PR description.
- If code and spec disagree, that is a bug in one of them — fix the mismatch, don't ignore it.

## Files

- [content-rules.md](content-rules.md) — story relevance, categories, filtering, dedup, freshness

## Areas

| Prefix | Area |
|--------|------|
| CW-CLASS | Story classification & categories |
| CW-FILTER | Relevance and irrelevance filtering |
| CW-DEDUP | Deduplication |
| CW-AGE | Freshness / age limits |
| CW-SRC | Source rules (feeds, Reddit, LinkedIn) |
