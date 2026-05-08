#!/usr/bin/env python3
"""Tests for collect_trends parsing helpers (no network required)."""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from collect_trends import _normalize_datetime, parse_feed_entry_timestamp, parse_timestamp


class TestNormalizeDatetime:
    def test_naive_datetime_passes_through(self):
        dt = datetime(2026, 5, 8, 12, 0, 0)
        result = _normalize_datetime(dt)
        assert result == dt
        assert result.tzinfo is None

    def test_aware_datetime_converted_to_naive_utc(self):
        # 2026-05-08T12:00:00 EST → 2026-05-08T17:00:00Z naive
        from datetime import timedelta as td

        eastern = timezone(td(hours=-5))
        dt = datetime(2026, 5, 8, 12, 0, 0, tzinfo=eastern)
        result = _normalize_datetime(dt)
        assert result.tzinfo is None
        assert result.hour == 17

    def test_utc_aware_strips_tzinfo(self):
        dt = datetime(2026, 5, 8, 12, 0, 0, tzinfo=timezone.utc)
        result = _normalize_datetime(dt)
        assert result.tzinfo is None
        assert result.hour == 12


class TestParseTimestamp:
    def test_none_returns_none(self):
        assert parse_timestamp(None) is None

    def test_empty_string_returns_none(self):
        assert parse_timestamp("") is None
        assert parse_timestamp("   ") is None

    def test_passes_through_datetime(self):
        dt = datetime(2026, 5, 8)
        result = parse_timestamp(dt)
        assert result == dt

    def test_unix_seconds(self):
        # 2026-01-01 UTC
        ts = 1767225600
        result = parse_timestamp(ts)
        assert result is not None
        assert result.year == 2026

    def test_unix_milliseconds(self):
        # detected as ms when > 10B
        ts_ms = 1767225600 * 1000
        result = parse_timestamp(ts_ms)
        assert result is not None
        assert result.year == 2026

    def test_iso_string_with_z_suffix(self):
        result = parse_timestamp("2026-05-08T12:00:00Z")
        assert result is not None
        assert result.year == 2026
        assert result.month == 5

    def test_iso_string_with_offset(self):
        result = parse_timestamp("2026-05-08T12:00:00+05:00")
        assert result is not None
        # Normalized to UTC: 12:00+05:00 → 07:00Z
        assert result.hour == 7

    def test_rfc822_format(self):
        result = parse_timestamp("Fri, 08 May 2026 12:00:00 +0000")
        assert result is not None
        assert result.year == 2026

    def test_date_only_yyyy_mm_dd(self):
        result = parse_timestamp("2026-05-08")
        assert result is not None
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 8

    def test_date_only_with_slashes(self):
        result = parse_timestamp("2026/05/08")
        assert result is not None
        assert result.year == 2026

    def test_garbage_returns_none(self):
        assert parse_timestamp("not a date") is None

    def test_invalid_unix_returns_none(self):
        # OverflowError on huge value
        assert parse_timestamp(1e30) is None


class TestParseFeedEntryTimestamp:
    def test_uses_published_parsed_struct(self):
        # feedparser provides time.struct_time-like tuples
        entry = {"published_parsed": (2026, 5, 8, 12, 0, 0, 0, 0, 0)}
        result = parse_feed_entry_timestamp(entry)
        assert result is not None
        assert result.year == 2026

    def test_falls_back_to_updated_parsed(self):
        entry = {"updated_parsed": (2026, 5, 8, 12, 0, 0, 0, 0, 0)}
        result = parse_feed_entry_timestamp(entry)
        assert result is not None
        assert result.year == 2026

    def test_falls_back_to_published_string(self):
        entry = {"published": "2026-05-08T12:00:00Z"}
        result = parse_feed_entry_timestamp(entry)
        assert result is not None
        assert result.year == 2026

    def test_returns_none_when_no_timestamp(self):
        entry = {"title": "no date"}
        result = parse_feed_entry_timestamp(entry)
        assert result is None

    def test_invalid_struct_skips_to_next(self):
        # When `published_parsed` is malformed, the helper must catch the
        # TypeError/ValueError and fall through to the `published` string
        # fallback rather than abandoning the entry.
        entry = {
            "published_parsed": ("not", "a", "tuple"),
            "published": "2026-05-08",
        }
        result = parse_feed_entry_timestamp(entry)
        assert result is not None
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
