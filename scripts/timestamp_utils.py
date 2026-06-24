#!/usr/bin/env python3
"""Timestamp parsing utilities for CMMC Watch.

Best-effort parsers for the many timestamp shapes that arrive from RSS feeds,
Reddit/LinkedIn APIs, and ad-hoc strings, normalised to naive UTC. Extracted
from collect_trends.py so this parsing concern (the source of issue #12) lives
in one tested place.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from config import setup_logging

logger = setup_logging("timestamp_utils")


def _normalize_datetime(value: datetime) -> datetime:
    """Normalize timezone-aware datetimes to naive UTC."""
    if value.tzinfo:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def parse_timestamp(value: Any) -> Optional[datetime]:
    """Best-effort timestamp parser for API and feed values."""
    if value is None:
        return None

    if isinstance(value, datetime):
        return _normalize_datetime(value)

    if isinstance(value, (int, float)):
        ts_value = float(value)
        if ts_value > 10_000_000_000:
            ts_value = ts_value / 1000.0
        try:
            return datetime.fromtimestamp(ts_value, tz=timezone.utc).replace(tzinfo=None)
        except (ValueError, OverflowError, OSError):
            return None

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None

        normalized = cleaned.replace("Z", "+00:00")
        try:
            return _normalize_datetime(datetime.fromisoformat(normalized))
        except ValueError:
            pass

        try:
            from email.utils import parsedate_to_datetime

            return _normalize_datetime(parsedate_to_datetime(cleaned))
        except (TypeError, ValueError):
            pass

        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue

    return None


def parse_feed_entry_timestamp(entry: Any) -> Optional[datetime]:
    """Extract timestamp from feedparser entry."""
    for parsed_key in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed_value = entry.get(parsed_key)
        if parsed_value:
            try:
                return datetime(*parsed_value[:6])
            except (TypeError, ValueError) as e:
                logger.debug(f"Could not build datetime from {parsed_key}: {e}")
                continue

    for key in ("published", "updated", "created", "dc_date", "pubDate"):
        parsed = parse_timestamp(entry.get(key))
        if parsed:
            return parsed
    return None
